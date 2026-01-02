"""
Tests for companion_voice module - deterministic voice generation.
"""
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from core.companion_voice import (
    build_voice_snapshot,
    build_greeting,
    build_tone_tagline,
    determine_focus_mode,
    get_time_of_day,
    CompanionVoiceSnapshot,
)


class TestDetermineFocusMode(TestCase):
    """Tests for focus mode determination."""
    
    def test_all_clear_with_no_issues(self):
        """No issues should return all_clear."""
        result = determine_focus_mode(critical_count=0, high_count=0, medium_count=0, low_count=0)
        self.assertEqual(result, "all_clear")
    
    def test_all_clear_with_only_low_issues(self):
        """Only low severity issues should return all_clear."""
        result = determine_focus_mode(critical_count=0, high_count=0, medium_count=0, low_count=5)
        self.assertEqual(result, "all_clear")
    
    def test_watchlist_with_medium_issues(self):
        """Medium issues should return watchlist."""
        result = determine_focus_mode(critical_count=0, high_count=0, medium_count=2, low_count=1)
        self.assertEqual(result, "watchlist")
    
    def test_fire_drill_with_high_issues(self):
        """High issues should return fire_drill."""
        result = determine_focus_mode(critical_count=0, high_count=1, medium_count=0, low_count=0)
        self.assertEqual(result, "fire_drill")
    
    def test_fire_drill_with_critical_issues(self):
        """Critical issues should return fire_drill."""
        result = determine_focus_mode(critical_count=1, high_count=0, medium_count=0, low_count=0)
        self.assertEqual(result, "fire_drill")
    
    def test_fire_drill_priority_over_watchlist(self):
        """High issues take priority over medium issues."""
        result = determine_focus_mode(critical_count=0, high_count=1, medium_count=5, low_count=10)
        self.assertEqual(result, "fire_drill")


class TestBuildGreeting(TestCase):
    """Tests for greeting generation."""
    
    @patch('core.companion_voice.get_time_of_day', return_value='morning')
    def test_greeting_all_clear_with_name(self, mock_tod):
        """All clear greeting includes emoji."""
        result = build_greeting("Mike", "all_clear")
        self.assertIn("Mike", result)
        self.assertIn("morning", result)
        self.assertIn("👌", result)
    
    @patch('core.companion_voice.get_time_of_day', return_value='afternoon')
    def test_greeting_watchlist_with_name(self, mock_tod):
        """Watchlist greeting is more casual."""
        result = build_greeting("Sarah", "watchlist")
        self.assertIn("Sarah", result)
        self.assertIn("Hey", result)
    
    @patch('core.companion_voice.get_time_of_day', return_value='evening')
    def test_greeting_fire_drill_with_name(self, mock_tod):
        """Fire drill greeting is urgent but not panicked."""
        result = build_greeting("John", "fire_drill")
        self.assertIn("John", result)
        self.assertIn("Heads up", result)
    
    @patch('core.companion_voice.get_time_of_day', return_value='morning')
    def test_greeting_without_name(self, mock_tod):
        """Fallback when no name is provided."""
        result = build_greeting(None, "all_clear")
        self.assertIn("there", result)


class TestBuildToneTagline(TestCase):
    """Tests for tone tagline generation."""
    
    def test_all_clear_tagline(self):
        result = build_tone_tagline("all_clear")
        self.assertIn("No major issues", result)
    
    def test_watchlist_tagline(self):
        result = build_tone_tagline("watchlist")
        self.assertIn("urgent", result.lower())
    
    def test_fire_drill_tagline(self):
        result = build_tone_tagline("fire_drill")
        self.assertIn("fix", result.lower())


class TestBuildVoiceSnapshot(TestCase):
    """Tests for complete voice snapshot building."""
    
    @patch('core.companion_voice.get_time_of_day', return_value='afternoon')
    def test_snapshot_all_clear(self, mock_tod):
        """All clear snapshot has correct structure."""
        result = build_voice_snapshot(
            user_name="Mike",
            issues=[],
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        
        self.assertIsInstance(result, CompanionVoiceSnapshot)
        self.assertEqual(result.focus_mode, "all_clear")
        self.assertIn("Mike", result.greeting)
        self.assertIsNone(result.primary_call_to_action)
    
    @patch('core.companion_voice.get_time_of_day', return_value='morning')
    def test_snapshot_with_issues(self, mock_tod):
        """Snapshot with issues includes primary CTA."""
        issues = [
            {"title": "Review overdue invoices", "severity": "high", "surface": "invoices"},
            {"title": "Clear suspense balance", "severity": "medium", "surface": "bank"},
        ]
        
        result = build_voice_snapshot(
            user_name="Sarah",
            issues=issues,
        )
        
        self.assertEqual(result.focus_mode, "fire_drill")
        self.assertIn("Sarah", result.greeting)
        self.assertIsNotNone(result.primary_call_to_action)
        self.assertIn("overdue invoices", result.primary_call_to_action.lower())


class TestGetTimeOfDay(TestCase):
    """Tests for time of day helper."""
    
    @patch('core.companion_voice.datetime')
    def test_morning(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 1, 1, 9, 0, 0)
        result = get_time_of_day()
        self.assertEqual(result, "morning")
    
    @patch('core.companion_voice.datetime')
    def test_afternoon(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 1, 1, 14, 0, 0)
        result = get_time_of_day()
        self.assertEqual(result, "afternoon")
    
    @patch('core.companion_voice.datetime')
    def test_evening(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 1, 1, 20, 0, 0)
        result = get_time_of_day()
        self.assertEqual(result, "evening")
