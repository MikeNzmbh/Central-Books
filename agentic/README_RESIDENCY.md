# Agentic Accounting OS — Residency Demo

> A multi-agent system for accounting, reconciliation, compliance, and audit — built on top of existing bookkeeping SaaS.

---

## Project Overview

The Agentic Accounting OS is an autonomous accounting engine that processes financial documents through a structured workflow. It extracts data, normalizes transactions, generates double-entry journal entries, and runs compliance/audit checks — all without manual intervention.

**Key capabilities:**
- **Document processing**: Ingest receipts, invoices, and statements
- **Intelligent extraction**: Parse vendor, amount, and category from documents
- **Journal entry generation**: Create balanced double-entry bookkeeping entries
- **Compliance checking**: Flag currency mismatches, unusual amounts, unbalanced entries
- **Audit detection**: Identify unusual scales, suspense account usage

---

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    AGENTIC ACCOUNTING OS                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ agentic_core│    │   engine    │    │   agents    │       │
│  │   models    │    │             │    │             │       │
│  │  ─────────  │    │  ─────────  │    │  ─────────  │       │
│  │ • documents │    │ • ingestion │    │ • operations│       │
│  │ • ledger    │    │ • normalize │    │ • support   │       │
│  │ • compliance│    │ • entry_gen │    │ • sales     │       │
│  │ • audit     │    │ • compliance│    │ • engineering│      │
│  │ • reporting │    │ • audit     │    │ • data_integ│       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                                │
│  ┌─────────────┐    ┌─────────────────────────────────┐       │
│  │  workflows  │    │          interfaces             │       │
│  │  ─────────  │    │    ─────────────────────────    │       │
│  │ • graph     │    │    • CLI demo                   │       │
│  │ • steps     │    │    • HTTP API                   │       │
│  │ • receipts  │    │    • Web Demo UI                │       │
│  └─────────────┘    └─────────────────────────────────┘       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Components

| Layer | Purpose |
|-------|---------|
| **agentic_core** | Pydantic models for documents, ledger, compliance, audit |
| **engine** | Processing modules: ingestion, normalization, entry generation |
| **agents** | AI Employee agents with specialized roles |
| **workflows** | DAG-based workflow orchestration |
| **interfaces** | CLI, HTTP API, and web demo UI |

---

## Agents ("AI Employees")

The system includes 5 specialized AI agents:

### OperationsAgent
- **Role**: Workflow orchestration and system monitoring
- **Capabilities**: `summarize_workflow_run`, `propose_retry_plan`
- **Risk Level**: Medium
- **Owner**: Platform Team

### SupportAgent
- **Role**: User assistance and onboarding
- **Capabilities**: `answer_user_question`, `suggest_onboarding_steps`
- **Risk Level**: Low
- **Owner**: Support Team

### SalesAgent
- **Role**: Demo generation and pricing proposals
- **Capabilities**: `generate_demo_script`, `propose_pricing_tiers`
- **Risk Level**: Low
- **Owner**: Sales Team

### EngineeringAgent
- **Role**: Error analysis and debugging
- **Capabilities**: `summarize_error_logs`, `suggest_fix_priors`
- **Risk Level**: Medium
- **Owner**: Engineering Team

### DataIntegrityAgent
- **Role**: Data validation and anomaly detection
- **Capabilities**: `scan_for_schema_drift`, `flag_suspicious_transactions`
- **Risk Level**: High
- **Owner**: Data Team

---

## Receipts Demo Workflow

The flagship demo is a 6-step receipts-to-journal-entries workflow:

```
uploaded_files → ingest → extract → normalize → generate_entries → compliance → audit
```

### Pipeline Steps

| Step | Input | Output |
|------|-------|--------|
| **ingest** | Raw files | `RawDocument[]` |
| **extract** | `RawDocument[]` | `ExtractedDocument[]` (vendor, amount, category) |
| **normalize** | `ExtractedDocument[]` | `NormalizedTransaction[]` |
| **generate_entries** | `NormalizedTransaction[]` | `JournalEntry[]` (balanced double-entry) |
| **compliance** | Transactions + Entries | `ComplianceCheckResult` |
| **audit** | Transactions + Entries | `AuditReport` |

### Example Input

```
Office Depot – $89.99 – office supplies
Starbucks – $15.50 – client meeting
GitHub – $49 – SaaS subscription
```

### Example Output (Shortened)

```json
{
  "workflow_name": "receipts_to_journal_entries",
  "status": "success",
  "steps": [
    {"name": "ingest", "status": "success"},
    {"name": "extract", "status": "success"},
    {"name": "normalize", "status": "success"},
    {"name": "generate_entries", "status": "success"},
    {"name": "compliance", "status": "success"},
    {"name": "audit", "status": "success"}
  ],
  "journal_entries": [
    {
      "description": "Receipt from Office Depot",
      "lines": [
        {"account": "6100 Office Supplies", "debit": "$89.99"},
        {"account": "1000 Cash/Bank", "credit": "$89.99"}
      ],
      "is_balanced": true
    }
  ],
  "compliance": {"is_compliant": true, "issues": []},
  "audit": {"risk_level": "low", "findings": []}
}
```

---

## How to Run

### CLI Demo

```bash
python -m agentic.workflows.cli_receipts_demo
```

### HTTP API

```bash
# Run the server
python manage.py runserver

# POST to the API
curl -X POST http://localhost:8000/agentic/demo/receipts-run/ \
  -H "Content-Type: application/json" \
  -d '{"documents": [{"filename": "receipt.pdf", "content": "Office Depot $89.99"}]}'
```

### Web Demo

1. Start the Django server: `python manage.py runserver`
2. Start Vite dev server: `cd frontend && npm run dev`
3. Open: `http://localhost:8000/agentic/demo/receipts/`

---

## Why This Is Agentic / Residency-Grade

### 1. Autonomous Workflow Graph
- Steps execute in topological order
- Error handling with step-level status tracking
- Configurable edges and dependencies

### 2. Multiple Specialized Agents
- 5 distinct AI employees with clear roles
- Risk-level classification (low/medium/high)
- Capability-based invocation

### 3. Structured Traces & Artifacts
- `WorkflowRunResult` with per-step timing
- Serializable artifacts for downstream processing
- Compliance and audit trails

### 4. Safety by Design
- **Deterministic core**: All demo logic is deterministic
- **LLM optional**: Current implementation requires no live LLM calls
- **Validation layers**: Compliance checks catch issues before commit

### 5. Production-Ready Structure
- Pydantic models for type safety
- Django integration for enterprise deployment
- React frontend for user interaction

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agentic/status/` | GET | System health check |
| `/agentic/workflows/` | GET | List available workflows |
| `/agentic/agents/` | GET | List registered agents |
| `/agentic/demo/receipts-run/` | POST | Run receipts workflow |
| `/agentic/demo/receipts/` | GET | Web demo UI |

---

## Project Structure

```
agentic/
├── __init__.py
├── README_RESIDENCY.md          # This file
├── agents/                       # AI Employee agents
│   ├── registry.py
│   ├── shared/profile.py
│   ├── operations/
│   ├── support/
│   ├── sales/
│   ├── engineering/
│   └── data_integrity/
├── engine/                       # Processing modules
│   ├── ingestion/
│   ├── normalization/
│   ├── entry_generation/
│   ├── compliance/
│   ├── audit/
│   └── prompts/
├── workflows/                    # Workflow orchestration
│   ├── graph/workflow_graph.py
│   ├── steps/receipts_pipeline.py
│   └── cli_receipts_demo.py
└── interfaces/                   # External interfaces
    ├── api/agentic_api_router.py
    └── views.py

agentic_core/                     # Shared Pydantic models
├── models/
│   ├── documents.py
│   ├── ledger.py
│   ├── compliance.py
│   ├── audit.py
│   └── reporting.py
├── agents/
│   ├── base_agent.py
│   └── accounting_agent.py
└── workflows/
    └── receipts_workflow.py
```

---

## Next Steps

- [ ] Add real OCR/LLM extraction
- [ ] Implement vector memory for context
- [ ] Add approval workflows
- [ ] Build agent-to-agent communication
- [ ] Add real-time streaming updates

---

*Built for Residency Demo — December 2024*
