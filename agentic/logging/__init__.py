"""
Agentic Logging Package

Logging, tracing, and event recording for the agentic system:
- tracing: Execution tracing for observability
- events: Event logging for audit trails
- logs: Log file storage
"""

__all__ = ["trace_event", "log_event"]

from agentic.logging.tracing import trace_event
from agentic.logging.events import log_event
