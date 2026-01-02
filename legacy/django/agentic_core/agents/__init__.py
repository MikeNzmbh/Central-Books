"""
Agent subpackage for the agentic accounting core.

This subpackage contains the agent framework including:
- BaseAgent: Abstract base class for all agents
- AccountingAgent: Specialized agent for journal entry generation

Future agents (Phase 2+):
- ComplianceAgent: Regulatory and policy compliance checking
- AuditAgent: Anomaly detection and audit analysis
- WorkflowOrchestrator: Multi-agent coordination
"""

from agentic_core.agents.base_agent import BaseAgent
from agentic_core.agents.accounting_agent import AccountingAgent

__all__ = [
    "BaseAgent",
    "AccountingAgent",
]
