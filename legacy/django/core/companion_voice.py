"""
Companion Voice Layer - 100% Deterministic (No LLM)

This module provides the voice/personality layer for the AI Companion.
All values are computed deterministically from metrics and issues.

NO LLM CALLS in this module - greetings and focus modes must be fast.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence

FocusMode = Literal["all_clear", "watchlist", "fire_drill"]


@dataclass
class CompanionVoiceSnapshot:
    """
    Deterministic voice snapshot for the Companion UI.
    
    All fields are computed without LLM calls, ensuring fast response times.
    """
    greeting: str                         # "Good morning, Mike — you're in good shape today. 👌"
    focus_mode: FocusMode                 # "all_clear" | "watchlist" | "fire_drill"
    tone_tagline: str                     # "A few small things to tidy up."
    primary_call_to_action: str | None    # "Review 3 unreconciled transactions in Banking."


def get_time_of_day() -> str:
    """
    Returns 'morning', 'afternoon', or 'evening' based on current server time.
    """
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    else:
        return "evening"


def determine_focus_mode(
    critical_count: int = 0,
    high_count: int = 0,
    medium_count: int = 0,
    low_count: int = 0,
) -> FocusMode:
    """
    Determines focus mode based on issue severity counts.
    
    - fire_drill: Any critical or high severity issues
    - watchlist: Medium severity issues present, no critical/high
    - all_clear: No issues or only low severity
    """
    if critical_count > 0 or high_count > 0:
        return "fire_drill"
    if medium_count > 0:
        return "watchlist"
    return "all_clear"


def build_greeting(user_name: str | None, focus_mode: FocusMode) -> str:
    """
    Builds a personalized greeting based on user name and focus mode.
    
    Examples:
    - all_clear: "Good morning, Mike — you're in good shape today. 👌"
    - watchlist: "Hey Mike, a couple of things could use your eye today."
    - fire_drill: "Heads up, Mike — there are some urgent accounting issues to handle."
    """
    tod = get_time_of_day()
    name = user_name.strip().split()[0] if user_name and user_name.strip() else "there"
    
    if focus_mode == "all_clear":
        return f"Good {tod}, {name} — you're in good shape today. 👌"
    elif focus_mode == "watchlist":
        return f"Hey {name}, a couple of things could use your eye today."
    else:  # fire_drill
        return f"Heads up, {name} — there are some urgent accounting issues to handle."


def build_tone_tagline(focus_mode: FocusMode) -> str:
    """
    Returns a short tagline matching the focus mode.
    """
    if focus_mode == "all_clear":
        return "No major issues. Just keep things running smoothly."
    elif focus_mode == "watchlist":
        return "Nothing urgent, but worth reviewing soon."
    else:  # fire_drill
        return "Let's fix the most important problems first."


def build_primary_cta(issues: Sequence) -> str | None:
    """
    Builds the primary call-to-action from the highest-priority open issue.
    
    Args:
        issues: List of CompanionIssue objects (or dicts with severity, title, surface).
    
    Returns:
        A CTA string like "Review 7 overdue invoices in Sales." or None.
    """
    if not issues:
        return None
    
    # Priority order for severities
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    
    def get_sort_key(issue):
        """Get sort key for issue prioritization."""
        # Get severity
        if hasattr(issue, "severity"):
            sev = issue.severity
        else:
            sev = issue.get("severity", "low")
        sev_rank = severity_order.get(str(sev).lower(), 4)
        
        # Get created_at timestamp (newer first, so negate)
        created_at = getattr(issue, "created_at", None) or issue.get("created_at")
        if created_at and hasattr(created_at, "timestamp"):
            ts = -created_at.timestamp()
        else:
            ts = 0
        
        return (sev_rank, ts)
    
    # Sort by severity, then by created_at if available
    sorted_issues = sorted(issues, key=get_sort_key)
    
    top_issue = sorted_issues[0]
    
    # Extract issue details
    if hasattr(top_issue, "title"):
        title = top_issue.title
        surface = getattr(top_issue, "surface", "")
    else:
        title = top_issue.get("title", "")
        surface = top_issue.get("surface", "")
    
    # Human-readable surface names
    surface_names = {
        "bank": "Banking",
        "invoices": "Invoices",
        "expenses": "Expenses",
        "receipts": "Receipts",
        "reconciliation": "Reconciliation",
        "books": "Books Review",
        "tax": "Tax",
    }
    surface_label = surface_names.get(surface, surface.title() if surface else "")
    
    if surface_label:
        return f"{title} in {surface_label}."
    return f"{title}."


def build_voice_snapshot(
    user_name: str | None,
    issues: Sequence = (),
    severity_counts: dict | None = None,
) -> CompanionVoiceSnapshot:
    """
    Builds a complete voice snapshot for the Companion UI.
    
    This function is 100% deterministic - NO LLM CALLS.
    
    Args:
        user_name: The user's first name (or None for fallback).
        issues: List of open CompanionIssue objects for CTA generation.
        severity_counts: Dict with keys 'critical', 'high', 'medium', 'low' 
                         containing counts. If None, derived from issues.
    
    Returns:
        CompanionVoiceSnapshot with greeting, focus_mode, tagline, and CTA.
    """
    # Derive severity counts from issues if not provided
    if severity_counts is None:
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        for issue in issues:
            sev = getattr(issue, "severity", issue.get("severity", "low")).lower()
            if sev in severity_counts:
                severity_counts[sev] += 1
    
    # Determine focus mode
    focus_mode = determine_focus_mode(
        critical_count=severity_counts.get("critical", 0),
        high_count=severity_counts.get("high", 0),
        medium_count=severity_counts.get("medium", 0),
        low_count=severity_counts.get("low", 0),
    )
    
    # Build components
    greeting = build_greeting(user_name, focus_mode)
    tagline = build_tone_tagline(focus_mode)
    primary_cta = build_primary_cta(issues)
    
    return CompanionVoiceSnapshot(
        greeting=greeting,
        focus_mode=focus_mode,
        tone_tagline=tagline,
        primary_call_to_action=primary_cta,
    )
