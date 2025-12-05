# Multi-Agent Communication Specification

*Technical specification for inter-agent messaging*

---

## Overview

The multi-agent communication system enables structured collaboration between AI employee agents. It provides:

- **Typed Messages**: Defined message types for common operations
- **Priority Queuing**: Urgent messages processed first
- **Pub/Sub Topics**: Subscribe to categories of messages
- **Correlation Tracking**: Link related messages
- **Safety Logging**: All messages logged for audit

---

## Message Schema

```python
@dataclass
class AgentMessage:
    id: str                           # Unique identifier
    type: MessageType                 # Message category
    sender: str                       # Sending agent role
    recipient: str                    # Target agent (or "*" for broadcast)
    subject: str                      # Brief description
    payload: Dict[str, Any]           # Message content
    priority: MessagePriority         # LOW/NORMAL/HIGH/URGENT
    correlation_id: Optional[str]     # Links related messages
    reply_to: Optional[str]           # ID of message being replied to
    timestamp: datetime               # Creation time
    expires_at: Optional[datetime]    # Optional expiration
    metadata: Dict[str, Any]          # Additional context
    status: MessageStatus             # PENDING/DELIVERED/ACKNOWLEDGED/FAILED
```

---

## Message Types

| Type | Purpose | Sender → Recipient |
|------|---------|-------------------|
| `TASK_REQUEST` | Request task execution | Any → Specific agent |
| `TASK_RESPONSE` | Task completion result | Agent → Requester |
| `TASK_DELEGATE` | Forward task | Agent → Agent |
| `WORKFLOW_START` | Workflow began | Engine → Supervisor |
| `WORKFLOW_COMPLETE` | Workflow finished | Engine → Supervisor |
| `WORKFLOW_FAILED` | Workflow failed | Engine → Supervisor |
| `ALERT` | Urgent notification | Any → Any |
| `FLAG` | Non-urgent flag | Any → Any |
| `QUERY` | Information request | Any → Any |
| `INFO` | Information response | Any → Requester |
| `HANDOFF` | Context transfer | Agent → Agent |
| `ACK` | Acknowledgment | Any → Sender |

---

## Priority Levels

| Priority | Use Case | Processing Order |
|----------|----------|------------------|
| `URGENT` | Security, fraud detection | Immediate |
| `HIGH` | Failed workflows, compliance | Next cycle |
| `NORMAL` | Standard operations | Queue order |
| `LOW` | Background, non-critical | When idle |

---

## Communication Patterns

### Direct Messaging

```python
# Agent A sends to Agent B
send_message(
    sender="compliance",
    recipient="audit",
    message_type=MessageType.FLAG,
    subject="Unusual transaction pattern",
    payload={"transaction_id": "txn-123", "pattern": "round_number"},
)
```

### Broadcasting

```python
# Publish to all subscribed agents
bus.broadcast(AgentMessage(
    sender="supervisor",
    type=MessageType.ALERT,
    subject="System maintenance",
    payload={"action": "pause_workflows"},
))
```

### Pub/Sub Topics

```python
# Subscribe to topic
bus.subscribe("audit", "compliance_issues", handler)

# Publish to topic
bus.publish("compliance_issues", message)
```

### Request/Reply

```python
# Send request
request = request_task(
    sender="operations",
    recipient="data_integrity",
    task_name="validate_entries",
    task_params={"entries": [...]}
)

# Reply
reply = request.create_reply(
    sender="data_integrity",
    payload={"valid": True, "issues": []},
)
```

---

## Agent-to-Agent Collaboration Example

```
┌──────────────┐    FLAG: Unusual pattern    ┌──────────────┐
│  Compliance  │ ─────────────────────────→  │    Audit     │
│    Agent     │                             │    Agent     │
└──────────────┘                             └──────┬───────┘
                                                    │
                              QUERY: Error logs     │
                                                    ↓
                                            ┌──────────────┐
                                            │ Engineering  │
                                            │    Agent     │
                                            └──────┬───────┘
                                                    │
                                        REPORT: Analysis    
                                                    ↓
                                            ┌──────────────┐
                                            │  Supervisor  │
                                            │    Agent     │
                                            └──────────────┘
```

---

## Safety Guardrails

1. **Message Expiration**: Stale messages auto-expire
2. **Logging**: All messages recorded for audit
3. **Rate Limiting**: Prevent message flooding (future)
4. **Validation**: Payloads validated before routing
5. **Source Verification**: Sender identity verified

---

## Logging Format

```json
{
  "timestamp": "2024-12-05T12:00:00Z",
  "message_id": "msg-abc123",
  "type": "TASK_REQUEST",
  "sender": "compliance",
  "recipient": "audit",
  "subject": "Review flagged transaction",
  "priority": "high",
  "status": "delivered",
  "correlation_id": "workflow-xyz"
}
```

---

## Integration Points

| Component | Integration |
|-----------|-------------|
| WorkflowGraph | Publishes lifecycle events |
| SupervisorAgent | Subscribes to all events |
| Individual Agents | Register handlers with router |
| Memory System | Can query for context |

---

*December 2024*
