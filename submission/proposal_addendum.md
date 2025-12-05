# Agentic Accounting OS V2 — Residency Proposal Addendum

*Extension to Phase 8 submission*

---

## Executive Summary

Since our initial proposal, we have expanded the Agentic Accounting OS from a single receipts workflow to a comprehensive multi-agent platform with:

- **3 new workflows**: Invoice processing, Bank statement reconciliation, Multi-document routing
- **Multi-agent collaboration**: Message-passing protocol for agent-to-agent communication
- **Long-term memory**: Vector store for patterns, vendors, and transaction history
- **Supervisor agent**: Autonomous orchestration with failure recovery
- **Evaluation engine**: Confidence and risk scoring system

This addendum documents these expansions and their alignment with Residency goals.

---

## Architecture V2

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SUPERVISOR AGENT                                │
│  • Monitors all workflows    • Retries failed steps                 │
│  • Enforces safety rules     • Produces daily logs                  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ↓                    ↓                    ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ RECEIPTS        │  │ INVOICES        │  │ BANK STATEMENTS │
│ 6 steps         │  │ 10 steps        │  │ 10 steps        │
│ • Ingest        │  │ • Ingest        │  │ • Ingest        │
│ • Extract       │  │ • Extract       │  │ • Parse CSV/PDF │
│ • Normalize     │  │ • Classify      │  │ • Classify      │
│ • Entries       │  │ • Tax extract   │  │ • Deduplicate   │
│ • Compliance    │  │ • Vendor match  │  │ • Reconcile     │
│ • Audit         │  │ • Entries       │  │ • Entries       │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │    MULTI-AGENT MESSAGING      │
              │  AgentMessage • MessageRouter │
              │  MessageBus • Pub/Sub         │
              └───────────────┬───────────────┘
                              ↓
         ┌────────────────────┼────────────────────┐
         ↓                    ↓                    ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   COMPLIANCE    │  │     AUDIT       │  │  DATA INTEGRITY │
│     AGENT       │←→│     AGENT       │←→│     AGENT       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │       MEMORY SYSTEM           │
              │  VectorStore • Embeddings     │
              │  Retrieval API                │
              └───────────────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │     EVALUATION ENGINE         │
              │  Extraction • Transactions    │
              │  Compliance • Audit • Quality │
              └───────────────────────────────┘
```

---

## New Capabilities

### 1. Invoice Processing Workflow

**Pipeline**: `ingest → extract → classify_lines → extract_tax → match_vendor → normalize → generate_entries → match_payments → compliance → audit`

**Features**:
- Line-item classification into expense categories
- Tax amount extraction and validation
- Vendor recognition and matching
- Invoice-to-payment matching proposals
- Double-entry journal generation with AP handling

### 2. Bank Statement Workflow

**Pipeline**: `ingest → parse → normalize → classify → deduplicate → reconcile → flag_suspense → generate_entries → compliance → audit`

**Features**:
- CSV/PDF parsing
- Transaction classification
- Duplicate detection via fingerprinting
- Reconciliation proposals with confidence scores
- Suspense account flagging

### 3. Multi-Document Workflow

**Pipeline**: `ingest → detect_types → route → process_* → aggregate → compliance → audit`

**Features**:
- Automatic document type detection
- Routing to appropriate sub-pipelines
- Result aggregation across document types
- Unified compliance and audit

### 4. Multi-Agent Messaging

**Protocol**:
- `AgentMessage`: Typed messages with priority, expiration, correlation
- `MessageRouter`: Direct and pattern-based routing
- `MessageBus`: Pub/sub for topic-based communication

**Message Types**:
- `TASK_REQUEST/RESPONSE`: Request agent to perform task
- `ALERT`: Urgent notification
- `FLAG`: Non-urgent review flag
- `HANDOFF`: Context transfer between agents
- `WORKFLOW_*`: Workflow lifecycle events

### 5. Memory System

**Components**:
- `VectorStore`: In-memory vector storage with cosine similarity
- `EmbeddingStore`: Domain-specific embeddings (vendors, transactions, patterns)
- `RetrievalAPI`: Multi-strategy retrieval (similarity, recency, frequency, hybrid)

**Use Cases**:
- Vendor matching for new transactions
- Pattern recognition for compliance/audit
- Context retrieval for agent decisions

### 6. Supervisor Agent

**Capabilities**:
- Workflow monitoring with step-level tracking
- Failure detection and recovery decisions
- Retry/skip/escalate/reassign logic
- Safety rule enforcement
- Human-readable daily logs

**Tools**:
- `get_workflow_status(workflow_id)`
- `retry_step(workflow_id, step_name)`
- `escalate(workflow_id, reason)`
- `send_message(recipient, subject, content)`

### 7. Evaluation Engine

**Scoring Categories**:

| Category | Formula | Weight Distribution |
|----------|---------|---------------------|
| Extraction Confidence | field_completeness×0.4 + vendor_match×0.3 + amount_parse×0.3 | |
| Transaction Accuracy | category×0.35 + amount×0.35 + date×0.15 + vendor×0.15 | |
| Compliance Risk | 1.0 - (issue_count × 0.1 × severity_weight) | |
| Audit Risk | 1.0 - (finding_count × 0.15 × severity_weight) | |
| Journal Quality | balance_score×0.7 + completeness×0.3 | |

---

## Safety Mechanisms

1. **No Direct Money Movement**: All entries are proposals requiring human approval
2. **Confidence Thresholds**: Low-confidence results flagged automatically
3. **Human-in-the-Loop**: High-risk decisions escalated to humans
4. **Audit Trail**: All agent messages and decisions logged
5. **Supervisor Oversight**: Failed workflows tracked and reported
6. **Safety Rules**: High-value transactions (>$10K) flagged

---

## 30-Day Roadmap

### Week 1: Integration & Testing
- [ ] Integrate new workflows with Django API
- [ ] Add CLI demos for invoice and bank statement
- [ ] Write comprehensive tests for all pipelines
- [ ] Deploy to staging environment

### Week 2: LLM Integration
- [ ] Replace deterministic extraction with LLM parsing
- [ ] Implement confidence scoring from model outputs
- [ ] Add vector embeddings with real embedding model
- [ ] Test with diverse document formats

### Week 3: Advanced Features
- [ ] Implement Operations agent task dispatching
- [ ] Add inter-agent collaboration scenarios
- [ ] Build approval queue for high-risk entries
- [ ] Enhance memory system with real vector DB

### Week 4: Evaluation & Polish
- [ ] Run accuracy evaluation on labeled dataset
- [ ] Measure false positive/negative rates
- [ ] Conduct user testing with accountants
- [ ] Prepare final demo and documentation

---

## Research Angles

1. **Agent Orchestration**: How do multiple specialized agents collaborate on complex financial workflows?

2. **Confidence-Scored Reasoning**: Can we quantify model uncertainty for accounting decisions?

3. **Pattern Memory**: How do agents learn from past transactions and audit findings?

4. **Anomaly Detection**: What patterns indicate fraud, error, or unusual but legitimate activity?

5. **Human-AI Collaboration**: How do we balance autonomy with oversight for high-stakes decisions?

---

## Conclusion

The Agentic Accounting OS V2 demonstrates that LLMs can orchestrate complex, multi-step financial workflows with:
- Structured agent collaboration
- Long-term memory for context
- Autonomous failure recovery
- Quantified confidence and risk

This expansion positions the project for deeper research into agentic financial systems during the Residency.

---

*December 2024*
