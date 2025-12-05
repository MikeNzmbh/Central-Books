# Agentic Accounting OS — Residency Submission

> An autonomous accounting engine built on top of CERN Books SaaS

---

## What Is This?

The **Agentic Accounting OS** is a multi-agent system that automates bookkeeping, reconciliation, compliance, and audit. It sits alongside an existing Django-based accounting SaaS (CERN Books) and adds an intelligent, workflow-driven layer for processing financial documents.

This is **not a chatbot**. It's an autonomous pipeline that:
- Ingests receipts, invoices, and bank statements
- Extracts structured data (vendor, amount, category)
- Generates balanced double-entry journal entries
- Runs compliance checks (currency, thresholds, balance)
- Performs audit analysis (anomaly detection, suspense accounts)

---

## V2 Architecture

```
Supervisor Agent → Workflow Monitoring → Failure Recovery
       ↓
┌──────────────────────────────────────────┐
│  Receipts │ Invoices │ Bank Statements  │
└──────────────────────────────────────────┘
       ↓
Multi-Agent Messaging ←→ Memory System
       ↓
Evaluation Engine → Confidence Scores
```

### New in V2
- **3 new workflows**: Invoice, Bank Statement, Multi-Document
- **Multi-agent messaging**: Agent-to-agent communication protocol
- **Memory system**: Vector store for patterns and context
- **Supervisor agent**: Autonomous failure recovery
- **Evaluation engine**: Confidence and risk scoring
- **Safety guardrails**: 8 enforced safety policies

---

## What the Demo Showcases

### Receipts-to-Journal-Entries Workflow

A 6-step pipeline that transforms raw documents into audited journal entries:

```
ingest → extract → normalize → generate_entries → compliance → audit
```

- **Input**: Receipt files (filename + content)
- **Output**: Balanced journal entries, compliance status, audit report

### Multi-Agent "AI Employee" Layer

Five specialized agents with distinct roles:

| Agent | Role | Risk Level |
|-------|------|------------|
| OperationsAgent | Workflow orchestration | Medium |
| SupportAgent | User assistance | Low |
| SalesAgent | Demo generation | Low |
| EngineeringAgent | Error analysis | Medium |
| DataIntegrityAgent | Anomaly detection | High |

### Three Ways to Run

1. **CLI Demo**: `python -m agentic.workflows.cli_receipts_demo`
2. **HTTP API**: `POST /agentic/demo/receipts-run/`
3. **Web UI**: `GET /agentic/demo/receipts/`

---

## Experiments & Results

We evaluated three processing modes:

| Mode | Extraction | Journal | Compliance | Audit | **Composite** |
|------|------------|---------|------------|-------|---------------|
| baseline_heuristic | 0.60 | 0.50 | 0.75 | 0.75 | **0.64** |
| rag_single_agent | 0.60 | 0.50 | 0.75 | 0.75 | **0.64** |
| agentic_full | 0.75 | 0.60 | 0.85 | 0.90 | **0.76** |

→ Full analysis: [experiments_summary.md](./experiments_summary.md)

---

## Safety & Governance

The system enforces 8 safety policies:

| Policy | Severity |
|--------|----------|
| LLM Cannot Move Money | Critical |
| LLM Cannot Approve Entries | Critical |
| No Data Fabrication | Critical |
| Human Approval Required | High |
| Tenant Isolation | High |
| No PII Leakage | High |
| High-Value Review | Medium |
| Complete Audit Trail | Medium |

→ Full documentation: [safety_and_governance.md](./safety_and_governance.md)

---

## Agentic Console Demo

The Agentic Console provides a visual interface for workflow monitoring:

- **Workflow runs**: List of all executed workflows
- **Step timeline**: Visual progress through pipeline steps
- **Journal entries**: Debit/credit breakdown with balance validation
- **Compliance & Audit**: Issues and findings with severity
- **Raw JSON**: Full output for debugging

→ Access at: `GET /agentic/demo/console/`

---

## Architecture Diagram

→ Full Mermaid diagram: [architecture_v2_diagram.mmd](./architecture_v2_diagram.mmd)

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [proposal_draft.md](./proposal_draft.md) | Residency application narrative |
| [proposal_addendum.md](./proposal_addendum.md) | V2 expansion details |
| [technical_overview.md](./technical_overview.md) | Architecture deep-dive |
| [demo_instructions.md](./demo_instructions.md) | Step-by-step setup guide |
| [sample_output.json](./sample_output.json) | Example API response |
| [experiments_summary.md](./experiments_summary.md) | Baseline comparison results |
| [safety_and_governance.md](./safety_and_governance.md) | Safety policies and guardrails |
| [workflow_graph_v2.md](./workflow_graph_v2.md) | Pipeline specifications |
| [multi_agent_spec.md](./multi_agent_spec.md) | Messaging protocol |
| [roadmap_30_days.md](./roadmap_30_days.md) | Production scaling plan |

---

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd <project>
pip install -r requirements.txt
python manage.py migrate

# Run CLI demos
python -m agentic.workflows.cli_receipts_demo
python -m agentic.data_synthesis.cli_generate_sample
python -m agentic.experiments.cli_run_all

# Or start servers for web demo
python manage.py runserver  # Terminal 1
cd frontend && npm run dev  # Terminal 2
# Open: http://localhost:8000/agentic/demo/receipts/
```

---

## Residency Checklist

- [x] Core Pydantic models (documents, ledger, compliance, audit)
- [x] 5 AI employee agents with capabilities
- [x] WorkflowGraph engine with step orchestration
- [x] Receipts workflow (6 steps)
- [x] Invoice workflow (10 steps)
- [x] Bank statement workflow (10 steps)
- [x] Multi-document workflow (9 steps)
- [x] Multi-agent messaging protocol
- [x] Memory system with vector store
- [x] Supervisor agent with failure recovery
- [x] Evaluation engine with scoring
- [x] 8 safety policies
- [x] 5 runtime guardrails
- [x] Synthetic data generator
- [x] Experiment runner with baselines
- [x] Agentic Console UI
- [x] Django API endpoints
- [x] CLI demonstrations
- [x] Complete documentation

---

*Built for OpenAI Residency — December 2024*

