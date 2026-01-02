"""
Tests for the centralized tone system in core/llm_tone.py.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from core.llm_tone import (
    get_time_of_day,
    get_greeting,
    build_companion_preamble,
    determine_risk_level,
    RISK_TONE_MAP,
)


class TestGetTimeOfDay:
    """Tests for get_time_of_day function."""

    def test_morning_hours(self):
        """Morning is 5:00 - 11:59."""
        for hour in [5, 6, 7, 8, 9, 10, 11]:
            with patch("core.llm_tone.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2025, 12, 8, hour, 30, 0)
                assert get_time_of_day() == "morning", f"Hour {hour} should be morning"

    def test_afternoon_hours(self):
        """Afternoon is 12:00 - 16:59."""
        for hour in [12, 13, 14, 15, 16]:
            with patch("core.llm_tone.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2025, 12, 8, hour, 30, 0)
                assert get_time_of_day() == "afternoon", f"Hour {hour} should be afternoon"

    def test_evening_hours(self):
        """Evening is 17:00 - 4:59."""
        for hour in [17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4]:
            with patch("core.llm_tone.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2025, 12, 8, hour, 30, 0)
                assert get_time_of_day() == "evening", f"Hour {hour} should be evening"


class TestGetGreeting:
    """Tests for get_greeting function."""

    def test_with_user_name_low_risk(self):
        """Low risk greeting is casual with trailing comma."""
        result = get_greeting("Mike Johnson", "low", "morning")
        assert result == "Good morning Mike,"

    def test_with_user_name_medium_risk(self):
        """Medium risk greeting is warm 'Hi' style."""
        result = get_greeting("Mike", "medium", "afternoon")
        assert result == "Hi Mike,"

    def test_with_user_name_high_risk(self):
        """High risk greeting is professional."""
        result = get_greeting("Mike", "high", "evening")
        assert result == "Good evening Mike,"

    def test_with_user_name_critical_risk(self):
        """Critical risk greeting is professional."""
        result = get_greeting("Mike", "critical", "morning")
        assert result == "Good morning Mike,"

    def test_without_user_name_low_medium(self):
        """Fallback greeting for low/medium risk when no name."""
        result = get_greeting(None, "low", "evening")
        assert result == "Hi there,"
        result = get_greeting(None, "medium", "morning")
        assert result == "Hi there,"

    def test_without_user_name_high_critical(self):
        """Fallback greeting for high/critical risk when no name."""
        result = get_greeting(None, "high", "afternoon")
        assert result == "Good afternoon,"
        result = get_greeting(None, "critical", "evening")
        assert result == "Good evening,"

    def test_with_empty_string_name(self):
        """Fallback greeting when empty string provided."""
        result = get_greeting("", "medium", "morning")
        assert result == "Hi there,"

    def test_with_whitespace_only_name(self):
        """Fallback greeting when whitespace-only name provided."""
        result = get_greeting("   ", "high", "afternoon")
        assert result == "Good afternoon,"


class TestBuildCompanionPreamble:
    """Tests for build_companion_preamble function."""

    def test_includes_user_name(self):
        """Preamble includes the user's name."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="medium", surface="books")
        assert "Mike" in preamble
        assert "named Mike" in preamble

    def test_fallback_without_name(self):
        """Preamble has fallback when no name provided."""
        preamble = build_companion_preamble(user_name=None, risk_level="medium", surface="books")
        assert "the user" in preamble.lower()

    def test_low_risk_tone_instruction(self):
        """Low risk level produces friendly tone instruction."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="low", surface="receipts")
        assert "friendly" in preamble.lower() or "warm" in preamble.lower()
        # Check example is included
        assert "receipts for Friday" in preamble or "well managed" in preamble

    def test_medium_risk_tone_instruction(self):
        """Medium risk level produces calm, helpful tone instruction."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="medium", surface="invoices")
        assert "calm" in preamble.lower() or "helpful" in preamble.lower()

    def test_high_risk_tone_instruction(self):
        """High risk level produces clear, firm tone instruction."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="high", surface="bank")
        assert "clear" in preamble.lower() or "firm" in preamble.lower()

    def test_critical_risk_tone_instruction(self):
        """Critical risk level produces direct, urgent tone instruction."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="critical", surface="issues")
        assert "direct" in preamble.lower() or "urgent" in preamble.lower()

    def test_includes_safety_constraints(self):
        """Preamble includes safety rules."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="medium", surface="books")
        assert "never say you took action" in preamble.lower() or "never break these" in preamble.lower()
        assert "proposals only" in preamble.lower() or "decides" in preamble.lower()

    def test_includes_surface_context(self):
        """Preamble includes surface-specific context."""
        for surface, expected_keyword in [
            ("receipts", "expense receipts"),
            ("invoices", "sales invoices"),
            ("books", "general ledger"),
            ("bank", "bank transactions"),
            ("issues", "financial health"),
        ]:
            preamble = build_companion_preamble(user_name="Mike", risk_level="low", surface=surface)
            assert expected_keyword in preamble.lower(), f"Surface '{surface}' should mention '{expected_keyword}'"

    def test_invalid_risk_level_defaults_to_medium(self):
        """Invalid risk level defaults to medium."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="invalid", surface="books")
        # Should not raise, should use medium
        assert "calm" in preamble.lower() or "helpful" in preamble.lower()

    def test_greeting_example_included(self):
        """Preamble includes a greeting example for the LLM to follow."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="low", surface="books")
        assert "Good" in preamble  # Should have greeting example
        assert "Mike," in preamble  # With trailing comma

    def test_example_tone_included(self):
        """Preamble includes an example of the right tone."""
        preamble = build_companion_preamble(user_name="Mike", risk_level="low", surface="receipts")
        assert "EXAMPLE OF THE RIGHT TONE" in preamble
        assert "receipts" in preamble.lower()


class TestDetermineRiskLevel:
    """Tests for determine_risk_level function."""

    def test_critical_when_compliance_flag(self):
        """Returns critical when compliance_flag is True."""
        assert determine_risk_level(compliance_flag=True) == "critical"

    def test_critical_when_critical_count(self):
        """Returns critical when critical_count > 0."""
        assert determine_risk_level(critical_count=1) == "critical"

    def test_high_when_many_high_risk(self):
        """Returns high when high_risk_count >= 5."""
        assert determine_risk_level(high_risk_count=5) == "high"
        assert determine_risk_level(high_risk_count=10) == "high"

    def test_high_when_many_unreconciled(self):
        """Returns high when unreconciled_count >= 10."""
        assert determine_risk_level(unreconciled_count=10) == "high"

    def test_medium_when_some_high_risk(self):
        """Returns medium when some high_risk_count."""
        assert determine_risk_level(high_risk_count=2) == "medium"

    def test_medium_when_some_unreconciled(self):
        """Returns medium when some unreconciled_count."""
        assert determine_risk_level(unreconciled_count=3) == "medium"

    def test_low_when_all_clear(self):
        """Returns low when no issues."""
        assert determine_risk_level() == "low"
        assert determine_risk_level(high_risk_count=0, unreconciled_count=0) == "low"


class TestRiskToneMap:
    """Tests for the RISK_TONE_MAP configuration."""

    def test_all_risk_levels_defined(self):
        """All expected risk levels are defined."""
        expected_levels = {"low", "medium", "high", "critical"}
        assert set(RISK_TONE_MAP.keys()) == expected_levels

    def test_each_level_has_required_keys(self):
        """Each risk level config has tone, instruction, greeting_style, and example."""
        for level, config in RISK_TONE_MAP.items():
            assert "tone" in config, f"Risk level '{level}' missing 'tone'"
            assert "instruction" in config, f"Risk level '{level}' missing 'instruction'"
            assert "greeting_style" in config, f"Risk level '{level}' missing 'greeting_style'"
            assert "example" in config, f"Risk level '{level}' missing 'example'"
            assert len(config["tone"]) > 0, f"Risk level '{level}' has empty 'tone'"
            assert len(config["instruction"]) > 0, f"Risk level '{level}' has empty 'instruction'"
            assert len(config["example"]) > 0, f"Risk level '{level}' has empty 'example'"
