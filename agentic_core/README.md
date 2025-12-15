# Agentic Accounting Core

**Version:** 0.1.0  
**Phase:** 1 - Core Architecture

A foundational subsystem for building an AI-powered agentic accounting operating system. This package provides the architecture for autonomous document processing, journal entry generation, compliance checking, and audit analysis.

---

## Architecture Overview

```
agentic_core/
├── __init__.py              # Package root with re-exports
├── README.md                # This file
├── models/                  # Pydantic data models
│   ├── base.py             # AgentTrace, LLMCallMetadata
│   ├── documents.py        # RawDocument, ExtractedDocument
│   ├── ledger.py           # NormalizedTransaction, JournalEntryProposal
│   ├── compliance.py       # ComplianceIssue, ComplianceCheckResult
│   ├── audit.py            # AuditFinding, AuditReport
│   └── reporting.py        # PlAccountRow, PlReport
├── agents/                  # Agent framework
│   ├── base_agent.py       # BaseAgent abstract class
│   └── accounting_agent.py # Double-entry journal generation
└── workflows/               # End-to-end pipelines
    └── receipts_workflow.py # Document → Journal Entry workflow
```

---

## Quick Start

### Running the Demo

```bash
# From the project root
cd /path/to/project

# Run the receipts workflow demo
python -m agentic_core.workflows.receipts_workflow
```

Expected output:
```
============================================================
Agentic Accounting OS - Receipts Workflow Demo
============================================================

Running demo with synthetic documents...

Status: success
Summary: Processed 3 document(s). Extracted 3 document(s) successfully...
Duration: 12.34ms

Normalized Transactions:
  - Receipt from Vendor from office_supplies_receipt.pdf: 100.00 USD
  ...

Journal Entry Proposals:
  Entry: Receipt from Vendor from office_supplies_receipt.pdf
    6000: DR 100.00
    1000: CR 100.00
    Balanced: ✓
```

---

## Core Concepts

### 1. Data Models (Pydantic)

All data structures are defined as Pydantic models for:
- Type safety and validation
- JSON serialization/deserialization
- Auto-generated documentation

**Key Models:**

| Model | Purpose |
|-------|---------|
| `AgentTrace` | Captures full execution trace for observability |
| `RawDocument` | Represents uploaded documents before processing |
| `ExtractedDocument` | OCR/parsed document with structured data |
| `NormalizedTransaction` | Standardized transaction for accounting |
| `JournalEntryProposal` | Balanced double-entry journal entry |
| `ComplianceIssue` | Regulatory/policy violation finding |
| `AuditFinding` | Anomaly or audit observation |

### 2. Agent Framework

The `BaseAgent` class provides:
- **LLM Call Management:** Automatic logging, retry, and tracing
- **Tool Registration:** Register callable tools agents can use
- **Execution Tracing:** Full observability via `AgentTrace`
- **Async Support:** Native async/await with sync wrapper

```python
from agentic_core.agents import AccountingAgent

agent = AccountingAgent(llm_client=openai_client)
proposals, trace = await agent.execute(
    transactions=normalized_txns,
    chart_of_accounts=coa_data,
)
```

### 3. Workflows

Workflows orchestrate multiple agents and processing steps:

```python
from agentic_core.workflows import ReceiptsWorkflow

workflow = ReceiptsWorkflow(llm_client=openai_client)
result = await workflow.run(documents=[raw_doc1, raw_doc2])

print(result.summary)
print(f"Generated {len(result.proposals)} journal entries")
```

---

## How It Fits Into the Full System

This subsystem is designed to be the foundation for:

### Phase 2: Additional Agents
- **ComplianceAgent:** Check transactions against regulations
- **AuditAgent:** Detect anomalies and generate findings
- **WorkflowOrchestrator:** Coordinate multi-agent pipelines

### Phase 3: Integration
- Connect to Django models (Account, JournalEntry, etc.)
- Wire up API endpoints for document upload
- Build real-time processing queues

### Phase 4: Employee Agents
- **OpsAgent:** Operations and support tasks
- **EngineeringAgent:** Code review and deployment
- **FinanceAgent:** AR/AP management

### Future Vision
```
                    ┌─────────────────┐
                    │  User Uploads   │
                    │   Documents     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Extraction     │
                    │  Agent (OCR)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Accounting     │
                    │  Agent          │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────────┐ ┌───▼───┐ ┌───────▼───────┐
     │  Compliance     │ │ Audit │ │   Reporting   │
     │  Agent          │ │ Agent │ │   Agent       │
     └────────┬────────┘ └───┬───┘ └───────┬───────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  Human Review   │
                    │  (if needed)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Posted to      │
                    │  General Ledger │
                    └─────────────────┘
```

---

## Development Notes

### Requirements
- Python 3.10+
- Pydantic 2.x
- OpenAI Python SDK (optional, for LLM features)

### No Django Integration Yet
This package is intentionally decoupled from Django. It:
- Does NOT modify any Django models
- Does NOT create database migrations
- Does NOT expose API endpoints

Integration will happen in Phase 2.

### Placeholder Functions
The following functions need real implementations:
- `extract_documents()` → Integrate OCR/Vision API
- `normalize_documents_to_transactions()` → Add ML categorization

### TODO Markers
Search for `TODO` comments in the codebase for planned improvements.

---

## API Reference

### Creating an Accounting Agent

```python
from agentic_core.agents import AccountingAgent

agent = AccountingAgent(
    llm_client=openai_client,  # Optional
    default_model="gpt-4",
    default_expense_account="6000",
    default_income_account="4000",
    default_asset_account="1000",
    suspense_account="9999",
)
```

### Processing Documents

```python
from agentic_core.workflows import ReceiptsWorkflow
from agentic_core.models import RawDocument

# Create document references
doc = RawDocument(
    filename="receipt.pdf",
    mime_type="application/pdf",
    storage_path="/uploads/receipt.pdf",
)

# Run workflow
workflow = ReceiptsWorkflow(llm_client=client)
result = await workflow.run(documents=[doc])

# Access results
for proposal in result.proposals:
    if proposal.is_balanced:
        print(f"Ready to post: {proposal.description}")
```

### Inspecting Traces

```python
trace = result.trace

print(f"Agent: {trace.agent_name}")
print(f"Duration: {trace.duration_ms}ms")
print(f"LLM Calls: {len(trace.llm_calls)}")
print(f"Total Tokens: {trace.total_tokens_used}")

for step in trace.steps:
    print(f"  - {step}")
```

---

## License

Internal use only. Part of the Clover Books / CloverBooks project.

---

## Contact

For questions about this subsystem, reach out to the core team.
