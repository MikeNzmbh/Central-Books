"""
Agent Profile Model

Defines the AgentProfile Pydantic model that describes an AI Employee's
identity, capabilities, risk level, and configuration.

This is the core schema shared by all agent classes.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AgentProfile(BaseModel):
    """
    Profile describing an AI Employee agent.

    This model defines the identity, capabilities, and configuration
    for each agent role in the system.

    Attributes:
        name: Human-readable agent name.
        role: Agent role identifier (matches registry key).
        description: Detailed description of the agent's purpose.
        capabilities: List of capability strings the agent can perform.
        max_parallel_tasks: Maximum concurrent tasks this agent can handle.
        risk_level: Risk classification for operations this agent performs.
        llm_model: Default LLM model to use for this agent.
        system_prompt: System prompt defining agent behavior.
        tools: List of tool names this agent can use.
        owner_team: Optional team that owns/maintains this agent.
    """

    name: str
    role: Literal["operations", "support", "sales", "engineering", "data_integrity"]
    description: str
    capabilities: List[str] = Field(default_factory=list)
    max_parallel_tasks: int = 1
    risk_level: Literal["low", "medium", "high"] = "medium"
    llm_model: str = "gpt-4.1-mini"
    system_prompt: str = ""
    tools: List[str] = Field(default_factory=list)
    owner_team: Optional[str] = None

    class Config:
        frozen = True  # Profiles are immutable


# Type alias for role literals
AgentRole = Literal["operations", "support", "sales", "engineering", "data_integrity"]
