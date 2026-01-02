# Agentic Accounting OS: AI Employees for Finance, Audit, and Compliance

*Residency Proposal Draft*

---

## Problem & Motivation

Small businesses and early-stage startups face a persistent challenge: **bookkeeping is tedious, error-prone, and expensive**.

### The Pain Points

- **Cost barrier**: Professional accountants charge $50–200/hour. Early-stage companies often can't afford dedicated finance staff.

- **DIY mistakes**: Founders doing their own books make classification errors, forget to reconcile, and miss compliance deadlines.

- **Tool limitations**: Existing accounting software (QuickBooks, Xero, Wave) are essentially CRUD dashboards. They don't *do* the work—they just *store* it.

- **AI gaps**: Current "AI-powered" solutions are mostly RAG chatbots that answer questions. They don't autonomously process documents, generate journal entries, or flag audit risks.

### The Opportunity

What if accounting software could **think and act** like a team of specialized employees?

- An **ingestion agent** that reads receipts and extracts vendor, amount, and category
- A **bookkeeper agent** that generates balanced double-entry journal entries
- A **compliance agent** that flags currency mismatches and unusual amounts
- An **auditor agent** that detects anomalies and suspense account usage

This is what the Agentic Accounting OS provides.

---

## Proposed Solution

I've built a working prototype of an **agentic accounting engine** that sits on top of an existing bookkeeping SaaS (Clover Books, a Django-based invoicing and expense tracking app).

### What It Does

1. **Receipts Workflow**
   - Accepts document uploads (filename + content)
   - Extracts vendor name, amount, and expense category
   - Normalizes into structured transactions
   - Generates balanced double-entry journal entries
   - Runs compliance checks (currency, thresholds, balance validation)
   - Performs audit analysis (scale anomalies, suspense account detection)

2. **Multi-Agent Layer**
   - 5 specialized "AI employee" agents with distinct roles and risk levels
   - Central registry for discovery and invocation
   - Designed for future agent-to-agent collaboration

3. **Three Interfaces**
   - CLI demo for quick testing
   - HTTP API for programmatic access
   - Web UI for interactive exploration

### Design Principles

- **Deterministic schemas**: All data flows through Pydantic models with strict typing
- **LLM as advisor, not authority**: The system proposes entries and flags—humans approve and commit
- **Traceable execution**: Every step records timing, status, and artifacts
- **Testable by design**: Workflow logic is pure functions operating on context dictionaries

---

## Agentic Architecture

### Core Components

```
agentic/
├── engine/           # Processing modules
│   ├── ingestion/    # Document intake
│   ├── normalization/# Data standardization
│   ├── entry_generation/  # Journal entry creation
│   ├── compliance/   # Policy checks
│   └── audit/        # Anomaly detection

├── agents/           # AI Employee agents
│   ├── registry.py   # Central discovery
│   ├── operations/   # Workflow orchestration
│   ├── support/      # User assistance
│   ├── sales/        # Demo generation
│   ├── engineering/  # Error analysis
│   └── data_integrity/  # Data validation

├── workflows/        # Orchestration
│   ├── graph/        # WorkflowGraph engine
│   └── steps/        # Concrete pipelines

└── interfaces/       # External access
    ├── api/          # HTTP endpoints
    └── views.py      # Web demo
```

### Workflow Engine

The `WorkflowGraph` class provides DAG-based orchestration:

- **Step registration**: Named functions that mutate a context dictionary
- **Edge-based dependencies**: Steps execute in topological order
- **Rich results**: `WorkflowRunResult` captures per-step timing, status, and artifacts
- **Error isolation**: Failed steps don't crash the pipeline—they're recorded and skipped

### Agent Collaboration Model

Agents are registered in a central registry with:

- **Profile metadata**: Name, role, capabilities, risk level
- **Invocation methods**: Each agent exposes domain-specific functions
- **Future routing**: Operations agent can dispatch tasks to specialized agents

---

## Why This Fits the Residency

### Real-World Domain

Accounting is a $500B+ industry with clear rules (GAAP, double-entry) and measurable outcomes (balanced books, clean audits). This provides a grounded environment for agentic research.

### Safety by Design

- LLMs never directly move money
- All entries are *proposals* that require human approval
- Compliance and audit layers catch anomalies before commit
- Full execution traces for debugging and review

### Research Angles

1. **Agent orchestration**: How do multiple specialized agents collaborate on financial workflows?
2. **Confidence scoring**: Can we quantify model uncertainty for journal entry classifications?
3. **Anomaly detection**: What patterns indicate fraud, error, or unusual but legitimate activity?
4. **Human-in-the-loop**: How do we balance autonomy with oversight for high-stakes financial decisions?

---

## Roadmap During Residency

### Phase 1: Expand Workflows (Weeks 1–2)
- Add bank statement reconciliation workflow
- Add invoice processing workflow
- Implement multi-document batch processing

### Phase 2: Improve Intelligence (Weeks 3–4)
- Replace mock extraction with LLM-based parsing
- Add confidence scores to journal entry proposals
- Train anomaly detection on real financial patterns

### Phase 3: Agent Collaboration (Weeks 5–6)
- Implement Operations agent task routing
- Add inter-agent communication protocol
- Build approval queue for high-risk entries

### Phase 4: Evaluation & Iteration (Weeks 7–8)
- Measure classification accuracy on labeled dataset
- Calculate false positive/negative rates for audit flags
- User testing with real accountants

### Deliverables
- Production-ready receipts + bank statement workflows
- Evaluation framework for financial agent systems
- Research writeup on agentic accounting architecture

---

## Conclusion

The Agentic Accounting OS demonstrates that LLMs can do more than chat—they can orchestrate complex, multi-step financial workflows with appropriate safeguards.

This project combines:
- A real production codebase (Django + React)
- Structured agent architecture (5 specialized roles)
- Working demo (CLI + API + Web UI)
- Clear safety model (proposals, not commits)

I'm excited to deepen this work during the Residency, exploring how agentic systems can bring intelligence to the unglamorous but critical work of bookkeeping.

---

*December 2024*
