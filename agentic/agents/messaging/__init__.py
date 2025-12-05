"""
Messaging package for inter-agent communication.

Provides:
- AgentMessage: Structured message format
- MessageRouter: Routes messages between agents
- MessageBus: Central message bus for pub/sub
"""

from .protocol import (
    AgentMessage,
    MessageType,
    MessagePriority,
    MessageRouter,
    MessageBus,
    get_message_bus,
    send_message,
    alert_agent,
    request_task,
)

__all__ = [
    "AgentMessage",
    "MessageType",
    "MessagePriority",
    "MessageRouter",
    "MessageBus",
    "get_message_bus",
    "send_message",
    "alert_agent",
    "request_task",
]
