"""
Shared utilities for all agents.

Exports:
- AgentProfile: Pydantic model for agent configuration
"""

from agentic.agents.shared.profile import AgentProfile, AgentRole

__all__ = ["AgentProfile", "AgentRole"]
