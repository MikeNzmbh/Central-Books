"""
Companion Story Generation - Event-driven, background processing.

This module handles:
1. Computing data fingerprints to detect meaningful changes
2. Regenerating stories via DeepSeek (background only, never on page load)
3. Managing the dirty/clean state for periodic processing
"""
import hashlib
import json
import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from core.models import Business, CompanionStory, CompanionStoryState
from core.companion_issues import build_companion_radar, CompanionIssue
from core.llm_reasoning import generate_companion_story as call_deepseek_story

logger = logging.getLogger(__name__)

# Fallback story when DeepSeek fails or hasn't generated yet
FALLBACK_STORY = {
    "overall_summary": "Your financial data is being analyzed. Check back soon for personalized insights.",
    "timeline_bullets": [],
}

# Minimum seconds between regenerations (5 minutes)
REGENERATION_DEBOUNCE_SECONDS = 300


def compute_fingerprint(radar: dict, issues: list) -> str:
    """
    Compute a hash of the input data used for story generation.
    If fingerprint matches existing story, skip regeneration.
    """
    # Only hash the parts that affect the story
    data = {
        "radar": radar,
        "issues": [
            {"title": getattr(i, "title", str(i)), "severity": getattr(i, "severity", "low")}
            for i in issues[:10]
        ],
    }
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def mark_story_dirty(business: Business) -> None:
    """
    Mark a business's story as needing regeneration.
    Called from Django signals when data changes.
    """
    state, _ = CompanionStoryState.objects.get_or_create(business=business)
    if not state.needs_regeneration:
        state.needs_regeneration = True
        state.last_requested_at = timezone.now()
        state.save(update_fields=["needs_regeneration", "last_requested_at"])
        logger.debug("Marked story dirty for business %s", business.id)


def regenerate_companion_story(business_id: int) -> Optional[CompanionStory]:
    """
    Regenerate the Companion story for a business.
    
    This function:
    1. Computes current data fingerprint
    2. Skips if fingerprint matches and debounce not expired
    3. Calls DeepSeek with generous timeout (60s)
    4. Stores result (or fallback) in CompanionStory
    
    Should only be called from background jobs, never from page load.
    """
    try:
        business = Business.objects.select_related("owner_user").get(id=business_id)
    except Business.DoesNotExist:
        logger.warning("Business %s not found for story regeneration", business_id)
        return None

    # 1. Build deterministic inputs
    radar = build_companion_radar(business)
    issues = list(
        CompanionIssue.objects.filter(business=business, status="open")
        .order_by("-created_at")[:10]
    )

    # 2. Compute fingerprint
    new_fingerprint = compute_fingerprint(radar, issues)

    # 3. Check existing story
    existing = CompanionStory.objects.filter(business=business).first()
    
    if existing:
        # Skip if fingerprint matches (nothing changed) AND it's not a fallback story
        is_fallback = (
            existing.story_json.get("overall_summary") == FALLBACK_STORY["overall_summary"]
        )
        if existing.data_fingerprint == new_fingerprint and not is_fallback:
            logger.info("Skipping story regeneration for %s - fingerprint unchanged", business.name)
            return existing
        
        # Skip if regenerated recently (debounce) AND it's not a fallback
        age_seconds = (timezone.now() - existing.generated_at).total_seconds()
        if age_seconds < REGENERATION_DEBOUNCE_SECONDS and not is_fallback:
            logger.info("Skipping story regeneration for %s - debounce (%ds ago)", business.name, int(age_seconds))
            return existing

    # 4. Get user's first name
    first_name = "there"
    if hasattr(business, "owner_user") and business.owner_user:
        first_name = business.owner_user.first_name or business.owner_user.email.split("@")[0]

    # 5. Determine focus_mode from radar scores
    radar_scores = [axis.get("score", 100) for axis in radar.values() if isinstance(axis, dict)]
    avg_score = sum(radar_scores) / len(radar_scores) if radar_scores else 100
    has_high_issues = any(i.severity == "high" for i in issues if hasattr(i, "severity"))
    
    if avg_score < 50 or has_high_issues:
        focus_mode = "fire_drill"
    elif avg_score < 80:
        focus_mode = "watchlist"
    else:
        focus_mode = "all_clear"

    # 6. Call DeepSeek with generous timeout (background job, no page blocking)
    logger.info("Regenerating story for business %s (focus_mode=%s)", business.name, focus_mode)
    
    try:
        story_result = call_deepseek_story(
            first_name=first_name,
            radar=radar,
            recent_issues=issues,
            recent_metrics={},  # Could add more metrics if needed
            focus_mode=focus_mode,
            timeout_seconds=60,  # Generous timeout for background
        )
    except Exception as exc:
        logger.warning("DeepSeek story generation failed for %s: %s", business.name, exc)
        story_result = None

    # 6. Build story JSON (use result or fallback)
    if story_result and hasattr(story_result, "overall_summary"):
        story_json = {
            "overall_summary": story_result.overall_summary,
            "timeline_bullets": story_result.timeline_bullets or [],
        }
    else:
        story_json = FALLBACK_STORY.copy()

    # 7. Store in database
    story, created = CompanionStory.objects.update_or_create(
        business=business,
        defaults={
            "story_json": story_json,
            "data_fingerprint": new_fingerprint,
        },
    )
    
    action = "Created" if created else "Updated"
    logger.info("%s story for %s: %s", action, business.name, story_json.get("overall_summary", "")[:50])
    
    return story


def regenerate_dirty_stories() -> int:
    """
    Process all businesses marked as needing story regeneration.
    Called from management command or Celery beat.
    
    Returns the number of stories regenerated.
    """
    dirty_states = CompanionStoryState.objects.filter(needs_regeneration=True)
    count = 0
    
    for state in dirty_states:
        try:
            regenerate_companion_story(business_id=state.business_id)
            state.needs_regeneration = False
            state.save(update_fields=["needs_regeneration"])
            count += 1
        except Exception as exc:
            logger.error("Failed to regenerate story for business %s: %s", state.business_id, exc)
    
    if count:
        logger.info("Regenerated %d companion stories", count)
    
    return count


def get_cached_story(business: Business) -> dict:
    """
    Get the cached story for a business, or fallback if none exists.
    This is what api_companion_summary should call - fast, no LLM.
    """
    try:
        story = CompanionStory.objects.get(business=business)
        return story.story_json
    except CompanionStory.DoesNotExist:
        # No story yet - mark dirty for next cron run
        mark_story_dirty(business)
        return FALLBACK_STORY.copy()
