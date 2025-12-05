"""
Agentic Agents Package

Multi-role AI Employee agents for business automation:
- OperationsAgent: Workflow management and process automation
- SupportAgent: Customer support and help desk
- SalesAgent: Sales assistance and revenue optimization
- EngineeringAgent: Development and technical support
- DataIntegrityAgent: Data quality and validation

Exports:
- Agent classes
- Registry functions
- AgentProfile model
"""

from agentic.agents.shared.profile import AgentProfile, AgentRole
from agentic.agents.registry import (
    AGENT_CLASSES,
    get_agent,
    list_agent_profiles,
    get_agent_profile,
    get_agent_capabilities,
)
from agentic.agents.operations.operations_agent import OperationsAgent
from agentic.agents.support.support_agent import SupportAgent
from agentic.agents.sales.sales_agent import SalesAgent
from agentic.agents.engineering.engineering_agent import EngineeringAgent
from agentic.agents.data_integrity.data_integrity_agent import DataIntegrityAgent

__all__ = [
    # Profile model
    "AgentProfile",
    "AgentRole",
    # Registry
    "AGENT_CLASSES",
    "get_agent",
    "list_agent_profiles",
    "get_agent_profile",
    "get_agent_capabilities",
    # Agent classes
    "OperationsAgent",
    "SupportAgent",
    "SalesAgent",
    "EngineeringAgent",
    "DataIntegrityAgent",
]
