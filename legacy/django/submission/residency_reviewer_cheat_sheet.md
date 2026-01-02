# Reviewer Cheat Sheet

*30-second overview*

---

## What It Does

- **Input**: Receipts, invoices, bank statements (raw files)
- **Output**: Balanced journal entries, compliance status, audit report
- **Result**: Automated bookkeeping with human-in-the-loop safety

---

## Why It Matters

- 60% of SMBs spend 5+ hrs/week on manual bookkeeping
- 40% of small business failures linked to cash flow issues
- Chatbots answer questions; this system **does the work**

---

## Technical Novelty

- **Multi-agent orchestration**: 5 specialized agents collaborate via message bus
- **DAG-based workflows**: 4 pipelines (35 total steps) with error recovery
- **Memory system**: Vector store for patterns, vendors, audit flags
- **Evaluation engine**: Quantified accuracy scoring across extraction, journal, compliance, audit
- **Supervisor agent**: Autonomous failure detection and recovery

---

## Safety

| Policy | Enforcement |
|--------|-------------|
| LLM can't move money | Proposals only, human approval required |
| LLM can't post entries | Approval token required |
| Tenant isolation | Vector memory partitioned by business |
| No PII leakage | Output validation, log masking |
| Audit trail | Every action logged |

---

## Scope

| Component | Count |
|-----------|-------|
| Pydantic models | 20+ |
| Agent types | 5 |
| Workflow pipelines | 4 |
| Total workflow steps | 35 |
| Safety policies | 8 |
| Runtime guardrails | 5 |
| CLI demos | 3 |

---

## Why This Applicant

- Built full system in weeks (14 phases, 100+ files)
- Understands accounting fundamentals + agent architecture
- Experience with production Django/React systems
- Emerging market perspective (Africa, underbanked SMBs)

---

## One-Liner

> An autonomous financial engine that transforms raw documents into audited double-entry journal entries—with multi-agent collaboration, vector memory, and safety-by-design.

---

*December 2024*
