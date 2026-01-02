# Agentic Accounting OS: Agents & Communication

This document consolidates the roles, capabilities, and technical communication specifications for the specialized AI Employee agents within the Clover Books ecosystem.

---

## 👥 AI Employee Roster

The system operates via five specialized agents, each with a defined role, risk level, and specific capabilities.

| Agent | Role | Risk Level | Capabilities |
| :--- | :--- | :--- | :--- |
| **OperationsAgent** | Workflow orchestration & monitoring | Medium | `summarize_workflow_run`, `propose_retry_plan` |
| **SupportAgent** | User assistance & onboarding | Low | `answer_user_question`, `suggest_onboarding_steps` |
| **SalesAgent** | Demo generation & pricing proposals | Low | `generate_demo_script`, `propose_pricing_tiers` |
| **EngineeringAgent** | Error analysis & debugging | Medium | `summarize_error_logs`, `suggest_fix_priors` |
| **DataIntegrityAgent** | Data validation & anomaly detection | High | `scan_for_schema_drift`, `flag_suspicious_transactions` |

---

## 🛰️ Multi-Agent Communication Spec

Inter-agent messaging is structured, typed, and prioritized to ensure reliability and auditability.

### Message Schema
```python
@dataclass
class AgentMessage:
    id: str                           # Unique identifier
    type: MessageType                 # Message category (TASK_REQUEST, ALERT, etc.)
    sender: str                       # Sending agent role
    recipient: str                    # Target agent (or "*" for broadcast)
    subject: str                      # Brief description
    payload: Dict[str, Any]           # Message content
    priority: MessagePriority         # URGENT, HIGH, NORMAL, LOW
    correlation_id: Optional[str]     # ID to link related message chains
    timestamp: datetime               # Creation time
    status: MessageStatus             # PENDING, DELIVERED, ACKNOWLEDGED, FAILED
```

### Communication Patterns
- **Direct Messaging**: Agent A to Agent B (e.g., Compliance to Audit).
- **Broadcasting**: Supervisor to all agents (e.g., System Maintenance).
- **Pub/Sub**: Agents subscribe to specific topics (e.g., `compliance_issues`).
- **Request/Reply**: Structured task delegation with result reporting.

---

## ⚡ Proposed Improvements & Roadmap

Based on the current "deterministic-first" architecture, the following upgrades are recommended to reach "Production-Grade" autonomy:

### 1. Robust AI Extraction (Receipts/Invoices)
- **Current**: Deterministic mockup or best-effort.
- **Improvement**: Integrate **LangChain/Pydantic** with **DeepSeek-V3** or **GPT-4o** for high-accuracy JSON extraction from messy OCR text.
- **Benefit**: Reduces manual corrections for vendor/amount extraction.

### 2. Multi-Agent Vector Memory
- **Current**: Stateless per-run context.
- **Improvement**: Shared **Pinecone** or **pgvector** store where agents can "remember" previous user corrections or edge cases across different workflows.
- **Benefit**: The "SupportAgent" can learn that "Starbucks" is always "Travel & Entertainment" for a specific user.

### 3. Human-in-the-Loop "Handback"
- **Current**: Autonomous run with summary.
- **Improvement**: Explicit `HANDOFF_TO_HUMAN` message type that triggers a UI notification in the Companion Control Tower when confidence is low (< 80%).
- **Benefit**: Increases safety for "High Risk" tasks like Data Integrity.

### 4. Real-time Streaming Traces
- **Current**: Result returned at end of workflow.
- **Improvement**: Use **Django Channels (WebSockets)** to stream agent "thoughts" (e.g., "EngineeringAgent is analyzing logs...") to the frontend in real-time.
- **Benefit**: Better transparency for the user during long-running audits.

### 5. Automated Regression Testing (Agentic Eval)
- **Current**: Standard Vitest UI tests.
- **Improvement**: Create an **"EvaluatorAgent"** that runs daily against a set of "Golden Receipts" to measure extraction accuracy and regression.
