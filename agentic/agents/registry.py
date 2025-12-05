"""
Agent Registry - Central registry of all AI Employee agents.

Provides:
- AGENT_CLASSES: Dict mapping role names to agent classes
- get_agent(role): Factory function to instantiate agents
- list_agent_profiles(): Get all agent profiles
"""

from typing import Dict, Type

from agentic_core.agents.base_agent import BaseAgent
from agentic.agents.shared.profile import AgentProfile
from agentic.agents.operations.operations_agent import OperationsAgent
from agentic.agents.support.support_agent import SupportAgent
from agentic.agents.sales.sales_agent import SalesAgent
from agentic.agents.engineering.engineering_agent import EngineeringAgent
from agentic.agents.data_integrity.data_integrity_agent import DataIntegrityAgent


# Type alias for agent classes
AgentClass = Type[BaseAgent]

# Central registry mapping role names to agent classes
AGENT_CLASSES: Dict[str, AgentClass] = {
    "operations": OperationsAgent,
    "support": SupportAgent,
    "sales": SalesAgent,
    "engineering": EngineeringAgent,
    "data_integrity": DataIntegrityAgent,
}


def get_agent(role: str) -> BaseAgent:
    """
    Factory function to instantiate an agent by role.

    Args:
        role: The agent role (operations, support, sales, engineering, data_integrity)

    Returns:
        Instantiated agent of the specified role.

    Raises:
        ValueError: If the role is not recognized.
    """
    cls = AGENT_CLASSES.get(role)
    if not cls:
        valid_roles = ", ".join(AGENT_CLASSES.keys())
        raise ValueError(f"Unknown agent role: '{role}'. Valid roles: {valid_roles}")
    return cls()


def list_agent_profiles() -> Dict[str, AgentProfile]:
    """
    Get all registered agent profiles.

    Returns:
        Dict mapping role names to AgentProfile instances.
    """
    return {
        role: cls.profile
        for role, cls in AGENT_CLASSES.items()
    }


def get_agent_profile(role: str) -> AgentProfile:
    """
    Get the profile for a specific agent role.

    Args:
        role: The agent role.

    Returns:
        The AgentProfile for that role.

    Raises:
        ValueError: If the role is not recognized.
    """
    cls = AGENT_CLASSES.get(role)
    if not cls:
        raise ValueError(f"Unknown agent role: '{role}'")
    return cls.profile


def list_agents_by_risk_level(risk_level: str) -> Dict[str, AgentProfile]:
    """
    Get agents filtered by risk level.

    Args:
        risk_level: One of "low", "medium", "high"

    Returns:
        Dict of matching agent profiles.
    """
    return {
        role: cls.profile
        for role, cls in AGENT_CLASSES.items()
        if cls.profile.risk_level == risk_level
    }


def get_agent_capabilities(role: str) -> list:
    """
    Get the capabilities list for a specific agent.

    Args:
        role: The agent role.

    Returns:
        List of capability strings.
    """
    profile = get_agent_profile(role)
    return list(profile.capabilities)
