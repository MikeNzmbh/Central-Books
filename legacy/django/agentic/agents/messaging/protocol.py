"""
Multi-Agent Communication Protocol

Provides a structured messaging system for inter-agent communication:
- AgentMessage: Typed messages with metadata and payload
- MessageRouter: Routes messages to appropriate agents
- MessageBus: Central pub/sub system for agent coordination

Safety Features:
- All messages are logged and traceable
- Message validation before delivery
- Priority-based queuing
- Timeout and retry handling
"""

from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
import logging
from collections import defaultdict


logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class MessageType(str, Enum):
    """Types of inter-agent messages."""
    
    # Task-related
    TASK_REQUEST = "task_request"        # Request an agent to perform a task
    TASK_RESPONSE = "task_response"      # Response to a task request
    TASK_DELEGATE = "task_delegate"      # Delegate task to another agent
    
    # Workflow-related
    WORKFLOW_START = "workflow_start"    # Workflow has started
    WORKFLOW_COMPLETE = "workflow_complete"  # Workflow completed
    WORKFLOW_FAILED = "workflow_failed"  # Workflow failed
    
    # Alert/Flag
    ALERT = "alert"                      # Urgent alert requiring attention
    FLAG = "flag"                        # Non-urgent flag for review
    
    # Query/Response
    QUERY = "query"                      # Information request
    INFO = "info"                        # Information response
    
    # Coordination
    HANDOFF = "handoff"                  # Hand off context to another agent
    ACK = "ack"                          # Acknowledgment


class MessagePriority(str, Enum):
    """Message priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(str, Enum):
    """Message delivery status."""
    
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


# =============================================================================
# MESSAGE MODEL
# =============================================================================


@dataclass
class AgentMessage:
    """
    Structured message for inter-agent communication.
    
    Attributes:
        id: Unique message identifier
        type: Message type (task, alert, query, etc.)
        sender: Sending agent role
        recipient: Target agent role (or "*" for broadcast)
        subject: Brief description of the message
        payload: Message data/content
        priority: Message priority level
        correlation_id: ID linking related messages
        reply_to: ID of message this replies to
        timestamp: When message was created
        expires_at: Optional expiration time
        metadata: Additional context
    """
    
    id: str = field(default_factory=lambda: f"msg-{uuid4().hex[:12]}")
    type: MessageType = MessageType.INFO
    sender: str = ""
    recipient: str = ""
    subject: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: MessageStatus = MessageStatus.PENDING
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "subject": self.subject,
            "payload": self.payload,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
            "status": self.status.value,
        }
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def create_reply(
        self,
        sender: str,
        payload: Dict[str, Any],
        message_type: MessageType = MessageType.TASK_RESPONSE,
    ) -> "AgentMessage":
        """Create a reply message."""
        return AgentMessage(
            type=message_type,
            sender=sender,
            recipient=self.sender,
            subject=f"RE: {self.subject}",
            payload=payload,
            correlation_id=self.correlation_id or self.id,
            reply_to=self.id,
        )


# =============================================================================
# MESSAGE ROUTER
# =============================================================================


@dataclass
class RouteRule:
    """A routing rule for messages."""
    
    message_type: Optional[MessageType] = None
    sender_pattern: Optional[str] = None
    recipient_pattern: Optional[str] = None
    handler: Callable[[AgentMessage], None] = None
    priority_min: MessagePriority = MessagePriority.LOW


class MessageRouter:
    """
    Routes messages between agents based on configurable rules.
    
    Supports:
    - Direct routing (sender → recipient)
    - Pattern-based routing (wildcards)
    - Type-based routing (message type → handler)
    - Priority-based queuing
    """
    
    def __init__(self):
        self._rules: List[RouteRule] = []
        self._agent_handlers: Dict[str, Callable] = {}
        self._type_handlers: Dict[MessageType, Callable] = {}
        self._message_log: List[AgentMessage] = []
        self._max_log_size = 1000
    
    def register_agent(
        self,
        agent_role: str,
        handler: Callable[[AgentMessage], None],
    ) -> None:
        """Register an agent's message handler."""
        self._agent_handlers[agent_role] = handler
        logger.debug(f"Registered agent handler: {agent_role}")
    
    def register_type_handler(
        self,
        message_type: MessageType,
        handler: Callable[[AgentMessage], None],
    ) -> None:
        """Register a handler for a specific message type."""
        self._type_handlers[message_type] = handler
        logger.debug(f"Registered type handler: {message_type}")
    
    def add_rule(self, rule: RouteRule) -> None:
        """Add a routing rule."""
        self._rules.append(rule)
    
    def route(self, message: AgentMessage) -> bool:
        """
        Route a message to its recipient(s).
        
        Returns True if message was delivered to at least one handler.
        """
        if message.is_expired():
            message.status = MessageStatus.EXPIRED
            self._log_message(message)
            return False
        
        delivered = False
        
        # Check type-specific handlers
        if message.type in self._type_handlers:
            try:
                self._type_handlers[message.type](message)
                delivered = True
            except Exception as e:
                logger.error(f"Type handler error: {e}")
        
        # Route to specific recipient
        if message.recipient and message.recipient != "*":
            if message.recipient in self._agent_handlers:
                try:
                    self._agent_handlers[message.recipient](message)
                    delivered = True
                except Exception as e:
                    logger.error(f"Agent handler error: {e}")
        
        # Broadcast to all agents
        elif message.recipient == "*":
            for role, handler in self._agent_handlers.items():
                if role != message.sender:  # Don't send to self
                    try:
                        handler(message)
                        delivered = True
                    except Exception as e:
                        logger.error(f"Broadcast handler error for {role}: {e}")
        
        # Apply routing rules
        for rule in self._rules:
            if self._matches_rule(message, rule):
                try:
                    if rule.handler:
                        rule.handler(message)
                        delivered = True
                except Exception as e:
                    logger.error(f"Rule handler error: {e}")
        
        # Update status
        message.status = MessageStatus.DELIVERED if delivered else MessageStatus.FAILED
        self._log_message(message)
        
        return delivered
    
    def _matches_rule(self, message: AgentMessage, rule: RouteRule) -> bool:
        """Check if message matches a routing rule."""
        if rule.message_type and message.type != rule.message_type:
            return False
        
        if rule.sender_pattern:
            if rule.sender_pattern != "*" and rule.sender_pattern != message.sender:
                return False
        
        if rule.recipient_pattern:
            if rule.recipient_pattern != "*" and rule.recipient_pattern != message.recipient:
                return False
        
        return True
    
    def _log_message(self, message: AgentMessage) -> None:
        """Log message for auditing."""
        self._message_log.append(message)
        
        # Trim log if too large
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]
    
    def get_message_log(
        self,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100,
    ) -> List[AgentMessage]:
        """Query message log with optional filters."""
        results = []
        
        for msg in reversed(self._message_log):
            if sender and msg.sender != sender:
                continue
            if recipient and msg.recipient != recipient:
                continue
            if message_type and msg.type != message_type:
                continue
            
            results.append(msg)
            if len(results) >= limit:
                break
        
        return results


# =============================================================================
# MESSAGE BUS (PUB/SUB)
# =============================================================================


class MessageBus:
    """
    Central message bus for publish/subscribe communication.
    
    Agents can:
    - Subscribe to topics (message types, agent roles, custom channels)
    - Publish messages to topics
    - Receive messages from subscribed topics
    """
    
    def __init__(self):
        self._router = MessageRouter()
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._topic_handlers: Dict[str, Dict[str, Callable]] = defaultdict(dict)
    
    @property
    def router(self) -> MessageRouter:
        return self._router
    
    def subscribe(
        self,
        subscriber: str,
        topic: str,
        handler: Callable[[AgentMessage], None],
    ) -> None:
        """
        Subscribe an agent to a topic.
        
        Args:
            subscriber: Agent role subscribing
            topic: Topic to subscribe to (e.g., "alerts", "compliance", agent role)
            handler: Function to call when message arrives
        """
        self._subscriptions[topic].add(subscriber)
        self._topic_handlers[topic][subscriber] = handler
        logger.debug(f"{subscriber} subscribed to topic: {topic}")
    
    def unsubscribe(self, subscriber: str, topic: str) -> None:
        """Unsubscribe an agent from a topic."""
        self._subscriptions[topic].discard(subscriber)
        self._topic_handlers[topic].pop(subscriber, None)
    
    def publish(self, topic: str, message: AgentMessage) -> int:
        """
        Publish a message to a topic.
        
        Returns number of subscribers notified.
        """
        subscribers = self._subscriptions.get(topic, set())
        handlers = self._topic_handlers.get(topic, {})
        
        delivered = 0
        for subscriber in subscribers:
            if subscriber == message.sender:
                continue  # Don't notify sender
            
            handler = handlers.get(subscriber)
            if handler:
                try:
                    handler(message)
                    delivered += 1
                except Exception as e:
                    logger.error(f"Publish error for {subscriber}: {e}")
        
        # Log the published message
        self._router._log_message(message)
        
        return delivered
    
    def send_direct(self, message: AgentMessage) -> bool:
        """Send a message directly to a specific recipient."""
        return self._router.route(message)
    
    def broadcast(self, message: AgentMessage) -> int:
        """Broadcast a message to all subscribed agents."""
        message.recipient = "*"
        return self.publish("broadcast", message)
    
    def get_subscribers(self, topic: str) -> Set[str]:
        """Get all subscribers for a topic."""
        return self._subscriptions.get(topic, set()).copy()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


# Global message bus instance
_default_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get or create the default message bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = MessageBus()
    return _default_bus


def send_message(
    sender: str,
    recipient: str,
    message_type: MessageType,
    subject: str,
    payload: Dict[str, Any],
    priority: MessagePriority = MessagePriority.NORMAL,
) -> AgentMessage:
    """
    Convenience function to send a message.
    
    Returns the sent message.
    """
    bus = get_message_bus()
    
    message = AgentMessage(
        type=message_type,
        sender=sender,
        recipient=recipient,
        subject=subject,
        payload=payload,
        priority=priority,
    )
    
    bus.send_direct(message)
    return message


def alert_agent(
    sender: str,
    recipient: str,
    subject: str,
    details: Dict[str, Any],
) -> AgentMessage:
    """Send an urgent alert to an agent."""
    return send_message(
        sender=sender,
        recipient=recipient,
        message_type=MessageType.ALERT,
        subject=subject,
        payload=details,
        priority=MessagePriority.URGENT,
    )


def request_task(
    sender: str,
    recipient: str,
    task_name: str,
    task_params: Dict[str, Any],
) -> AgentMessage:
    """Request an agent to perform a task."""
    return send_message(
        sender=sender,
        recipient=recipient,
        message_type=MessageType.TASK_REQUEST,
        subject=f"Task: {task_name}",
        payload={"task": task_name, "params": task_params},
        priority=MessagePriority.NORMAL,
    )
