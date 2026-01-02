"""
Tests for AI Employee Agents

Covers:
- Profile validation (role matches registry key, capabilities exist)
- get_agent() factory function
- Core method invocations for each agent
"""

import pytest
import asyncio
from typing import Dict

from agentic.agents.registry import (
    AGENT_CLASSES,
    get_agent,
    list_agent_profiles,
    get_agent_profile,
)
from agentic.agents.shared.profile import AgentProfile
from agentic.agents.operations import OperationsAgent
from agentic.agents.support import SupportAgent
from agentic.agents.sales import SalesAgent
from agentic.agents.engineering import EngineeringAgent
from agentic.agents.data_integrity import DataIntegrityAgent
from agentic_core.models.base import AgentTrace


class TestAgentRegistry:
    """Tests for the agent registry."""

    def test_registry_has_all_agents(self):
        """Registry contains all 5 agent types."""
        expected_roles = {"operations", "support", "sales", "engineering", "data_integrity"}
        assert set(AGENT_CLASSES.keys()) == expected_roles

    def test_get_agent_returns_correct_type(self):
        """get_agent() returns the correct agent class instance."""
        ops_agent = get_agent("operations")
        assert isinstance(ops_agent, OperationsAgent)

        support_agent = get_agent("support")
        assert isinstance(support_agent, SupportAgent)

        sales_agent = get_agent("sales")
        assert isinstance(sales_agent, SalesAgent)

        eng_agent = get_agent("engineering")
        assert isinstance(eng_agent, EngineeringAgent)

        data_agent = get_agent("data_integrity")
        assert isinstance(data_agent, DataIntegrityAgent)

    def test_get_agent_raises_for_unknown_role(self):
        """get_agent() raises ValueError for unknown roles."""
        with pytest.raises(ValueError) as exc_info:
            get_agent("unknown_role")
        assert "Unknown agent role" in str(exc_info.value)

    def test_list_agent_profiles(self):
        """list_agent_profiles() returns all profiles."""
        profiles = list_agent_profiles()
        assert len(profiles) == 5
        for role, profile in profiles.items():
            assert isinstance(profile, AgentProfile)
            assert profile.role == role


class TestAgentProfiles:
    """Tests for agent profile definitions."""

    @pytest.mark.parametrize("role", list(AGENT_CLASSES.keys()))
    def test_profile_role_matches_registry_key(self, role: str):
        """Each agent's profile.role matches its registry key."""
        profile = get_agent_profile(role)
        assert profile.role == role

    @pytest.mark.parametrize("role", list(AGENT_CLASSES.keys()))
    def test_profile_has_capabilities(self, role: str):
        """Each agent has at least one capability."""
        profile = get_agent_profile(role)
        assert len(profile.capabilities) > 0

    @pytest.mark.parametrize("role", list(AGENT_CLASSES.keys()))
    def test_profile_has_required_fields(self, role: str):
        """Each profile has all required fields populated."""
        profile = get_agent_profile(role)
        assert profile.name  # Non-empty
        assert profile.description
        assert profile.llm_model
        assert profile.system_prompt

    def test_risk_levels(self):
        """Verify expected risk levels for each agent."""
        expected_risks = {
            "operations": "medium",
            "support": "low",
            "sales": "low",
            "engineering": "medium",
            "data_integrity": "high",
        }
        for role, expected_risk in expected_risks.items():
            profile = get_agent_profile(role)
            assert profile.risk_level == expected_risk, f"{role} should be {expected_risk}"


class TestOperationsAgent:
    """Tests for OperationsAgent methods."""

    def test_summarize_workflow_run_success(self):
        """summarize_workflow_run returns summary for successful trace."""
        agent = OperationsAgent()
        trace = AgentTrace(
            agent_name="test_workflow",
            status="success",
            duration_ms=1500.0,
        )
        trace.add_step("Step 1")
        trace.add_step("Step 2")

        result = asyncio.run(agent.summarize_workflow_run(trace))
        assert isinstance(result, str)
        assert "test_workflow" in result
        assert "success" in result.lower()
        assert len(result) > 20

    def test_propose_retry_plan(self):
        """propose_retry_plan returns non-empty list of suggestions."""
        agent = OperationsAgent()
        errors = ["Connection timeout", "Rate limit exceeded"]

        result = asyncio.run(agent.propose_retry_plan(errors))
        assert isinstance(result, list)
        assert len(result) >= 2


class TestSupportAgent:
    """Tests for SupportAgent methods."""

    def test_answer_user_question(self):
        """answer_user_question returns a non-empty answer."""
        agent = SupportAgent()

        result = asyncio.run(agent.answer_user_question(
            question="How do I create an invoice?",
            context_summary="New user, retail business",
        ))
        assert isinstance(result, str)
        assert len(result) > 20

    def test_suggest_onboarding_steps(self):
        """suggest_onboarding_steps returns ordered list."""
        agent = SupportAgent()

        result = asyncio.run(agent.suggest_onboarding_steps({
            "name": "Test Business",
            "type": "ecommerce",
        }))
        assert isinstance(result, list)
        assert len(result) >= 5


class TestSalesAgent:
    """Tests for SalesAgent methods."""

    def test_generate_demo_script(self):
        """generate_demo_script returns formatted script."""
        agent = SalesAgent()

        result = asyncio.run(agent.generate_demo_script({
            "invoicing": True,
            "banking": True,
            "reports": True,
        }))
        assert isinstance(result, str)
        assert "##" in result  # Has markdown headers
        assert len(result) > 100

    def test_propose_pricing_tiers(self):
        """propose_pricing_tiers returns list of tier dicts."""
        agent = SalesAgent()

        result = asyncio.run(agent.propose_pricing_tiers("startup"))
        assert isinstance(result, list)
        assert len(result) >= 2
        assert all("name" in tier for tier in result)
        assert all("features" in tier for tier in result)


class TestEngineeringAgent:
    """Tests for EngineeringAgent methods."""

    def test_summarize_error_logs(self):
        """summarize_error_logs returns analysis string."""
        agent = EngineeringAgent()
        logs = [
            "Connection timeout to database",
            "Timeout waiting for response",
            "KeyError: 'user_id'",
        ]

        result = asyncio.run(agent.summarize_error_logs(logs))
        assert isinstance(result, str)
        assert "Timeout" in result or "error" in result.lower()

    def test_suggest_fix_priors(self):
        """suggest_fix_priors returns list of suggestions."""
        agent = EngineeringAgent()

        result = asyncio.run(agent.suggest_fix_priors(
            stack_trace="KeyError: 'missing_key' in process_data",
            module_hint="data_processor",
        ))
        assert isinstance(result, list)
        assert len(result) > 0


class TestDataIntegrityAgent:
    """Tests for DataIntegrityAgent methods."""

    def test_scan_for_schema_drift(self):
        """scan_for_schema_drift returns analysis dict."""
        agent = DataIntegrityAgent()
        events = [
            {"id": 1, "name": "Event 1", "amount": 100},
            {"id": 2, "name": "Event 2"},  # Missing amount
            {"id": 3, "name": "Event 3", "amount": "300"},  # String instead of int
        ]

        result = asyncio.run(agent.scan_for_schema_drift(events))
        assert isinstance(result, dict)
        assert "drift_detected" in result
        assert "findings" in result

    def test_flag_suspicious_transactions(self):
        """flag_suspicious_transactions returns list of flagged items."""
        agent = DataIntegrityAgent()
        transactions = [
            {"id": "1", "amount": 100, "description": "Office supplies"},
            {"id": "2", "amount": 1000000, "description": "Cash withdrawal"},  # Suspicious
            {"id": "3", "amount": 50, "description": "Subscription"},
        ]

        result = asyncio.run(agent.flag_suspicious_transactions(transactions))
        assert isinstance(result, list)
        # The large cash withdrawal should be flagged
        suspicious_ids = [f["transaction_id"] for f in result]
        assert "2" in suspicious_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
