"""
Tests for Companion Story Generation (item 12).

Tests the generate_companion_story function with mocked DeepSeek calls.
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase

from core.llm_reasoning import (
    generate_companion_story,
    CompanionStoryResult,
    STORY_TIMEOUT_SECONDS,
)


class TestGenerateCompanionStory(TestCase):
    """Tests for generate_companion_story function."""
    
    def setUp(self):
        self.radar = {
            "cash_reconciliation": {"score": 85, "open_issues": 1},
            "revenue_invoices": {"score": 90, "open_issues": 0},
            "expenses_receipts": {"score": 75, "open_issues": 2},
            "tax_compliance": {"score": 95, "open_issues": 0},
        }
        self.recent_metrics = {
            "open_issues_total": 3,
            "agent_retries_30d": 2,
        }
        self.recent_issues = [
            {"title": "Unreconciled bank transactions", "severity": "medium", "surface": "bank"},
            {"title": "High-risk receipts detected", "severity": "high", "surface": "receipts"},
        ]
    
    def test_success_returns_story_result(self):
        """Successful LLM call should return CompanionStoryResult with required fields."""
        mock_response = '''
        {
            "overall_summary": "Great week! Minor issues in banking to review.",
            "timeline_bullets": [
                "Monday: 3 new bank transactions imported",
                "Wednesday: High-risk receipt flagged"
            ]
        }
        '''
        
        mock_client = MagicMock(return_value=mock_response)
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=self.recent_issues,
            focus_mode="watchlist",
            llm_client=mock_client,
        )
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, CompanionStoryResult)
        self.assertEqual(result.overall_summary, "Great week! Minor issues in banking to review.")
        self.assertEqual(len(result.timeline_bullets), 2)
        self.assertIn("Monday", result.timeline_bullets[0])
    
    def test_timeout_returns_none(self):
        """Timeout should return None so caller can use fallback."""
        # Simulate timeout by returning None (what _invoke_llm does on timeout)
        mock_client = MagicMock(return_value=None)
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=self.recent_issues,
            focus_mode="watchlist",
            llm_client=mock_client,
        )
        
        self.assertIsNone(result)
    
    def test_invalid_json_returns_none(self):
        """Invalid JSON response should return None."""
        mock_client = MagicMock(return_value="This is not valid JSON")
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=self.recent_issues,
            focus_mode="watchlist",
            llm_client=mock_client,
        )
        
        self.assertIsNone(result)
    
    def test_missing_required_field_returns_none(self):
        """Response missing required field should return None."""
        # Missing overall_summary
        mock_response = '{"timeline_bullets": ["Item 1"]}'
        mock_client = MagicMock(return_value=mock_response)
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=self.recent_issues,
            focus_mode="watchlist",
            llm_client=mock_client,
        )
        
        self.assertIsNone(result)
    
    def test_exception_returns_none(self):
        """Exception should return None so caller can use fallback."""
        mock_client = MagicMock(side_effect=Exception("Connection error"))
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=self.recent_issues,
            focus_mode="watchlist",
            llm_client=mock_client,
        )
        
        self.assertIsNone(result)
    
    def test_uses_reasonable_timeout_by_default(self):
        """Story generation should use STORY_TIMEOUT_SECONDS by default (15s for reasoner)."""
        # The constant should be 15 seconds (enough for chain-of-thought)
        self.assertEqual(STORY_TIMEOUT_SECONDS, 15)
    
    def test_empty_issues_still_works(self):
        """Empty issues list should not break story generation."""
        mock_response = '''
        {
            "overall_summary": "All clear this week!",
            "timeline_bullets": []
        }
        '''
        mock_client = MagicMock(return_value=mock_response)
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=[],
            focus_mode="all_clear",
            llm_client=mock_client,
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.overall_summary, "All clear this week!")
        self.assertEqual(result.timeline_bullets, [])
    
    def test_markdown_wrapped_json_is_parsed(self):
        """JSON wrapped in markdown code block should be parsed correctly."""
        mock_response = '''```json
        {
            "overall_summary": "Summary text here",
            "timeline_bullets": ["Bullet 1"]
        }
        ```'''
        mock_client = MagicMock(return_value=mock_response)
        
        result = generate_companion_story(
            first_name="Mike",
            radar=self.radar,
            recent_metrics=self.recent_metrics,
            recent_issues=self.recent_issues,
            focus_mode="watchlist",
            llm_client=mock_client,
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.overall_summary, "Summary text here")
