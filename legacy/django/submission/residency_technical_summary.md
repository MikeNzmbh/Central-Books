# Technical Summary

*High-density architecture overview for engineers*

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SUPERVISOR AGENT                         │
│         Monitors → Detects Failures → Decides Recovery      │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                      WORKFLOW ENGINE                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Receipts │  │ Invoices │  │  Bank    │  │Multi-Document│  │
│  │ 6 steps  │  │ 10 steps │  │Statements│  │  9 steps     │  │
│  └────┬─────┘  └────┬─────┘  │ 10 steps │  └──────┬───────┘  │
│       │             │        └────┬─────┘         │          │
│       └─────────────┴─────────────┴───────────────┘          │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                       AGENT LAYER                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │ Operations │  │ Compliance │  │   Audit    │ ← Messaging  │
│  │   Agent    │  │   Agent    │  │   Agent    │   Protocol   │
│  └────────────┘  └────────────┘  └────────────┘              │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                      MEMORY + EVAL                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐              │
│  │VectorStore │  │ Embeddings │  │  Scorer    │              │
│  └────────────┘  └────────────┘  └────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
Document Upload
     │
     ▼
┌─────────────────┐
│    Ingestion    │ → RawDocument
└────────┬────────┘
         ▼
┌─────────────────┐
│   Extraction    │ → ExtractedDocument (vendor, amount, date, lines)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Normalization  │ → NormalizedTransaction (category, currency)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Entry Generator │ → JournalEntry (DR/CR lines, balanced)
└────────┬────────┘
         ▼
┌─────────────────┐
│   Compliance    │ → ComplianceResult (issues, severity)
└────────┬────────┘
         ▼
┌─────────────────┐
│     Audit       │ → AuditReport (findings, risk_level)
└────────┬────────┘
         ▼
   Human Review → Posting
```

---

## Core Models (Pydantic)

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `RawDocument` | Uploaded file | filename, content, doc_type |
| `ExtractedDocument` | Parsed data | vendor, amount, date, line_items |
| `NormalizedTransaction` | Standardized | category_code, currency, merchant |
| `JournalEntry` | Ledger entry | lines[], is_balanced, total_dr, total_cr |
| `ComplianceResult` | Check output | is_compliant, issues[] |
| `AuditReport` | Risk assessment | risk_level, findings[] |

---

## Workflow DAG

**WorkflowGraph**: Directed acyclic graph executor
- Nodes: Step functions `(ctx) → ctx`
- Edges: Dependencies between steps
- Execution: Topological sort, parallel where possible

**Example (Receipts)**:
```
ingest → extract → normalize → generate → compliance → audit
   ↓                              ↑
   └──────────────────────────────┘ (all feed into final steps)
```

**Error Handling**:
- Step failures logged, workflow continues (partial success)
- Supervisor monitors, decides: retry | skip | escalate | abort

---

## Messaging Protocol

```python
AgentMessage:
  id: UUID
  type: TASK_REQUEST | ALERT | FLAG | HANDOFF | WORKFLOW_*
  sender: str        # "compliance"
  recipient: str     # "audit" or "*" for broadcast
  payload: Dict
  priority: LOW | NORMAL | HIGH | URGENT
  correlation_id: Optional[UUID]  # Links related messages
```

**MessageBus**: Pub/sub + direct routing
- Agents subscribe to topics
- Supervisor subscribes to all
- Full logging for audit trail

---

## Memory System

**VectorStore**: In-memory (prod: ChromaDB/Pinecone)
- `add(content, embedding, metadata)`
- `search(query, top_k)` → cosine similarity

**EmbeddingStore**: Domain-specific wrappers
- Vendor embeddings (name → vector)
- Transaction patterns (for anomaly detection)
- Audit patterns (learned red flags)

**RetrievalAPI**: Multi-strategy
- Similarity, Recency, Frequency, Hybrid

---

## Safety Enforcement

**8 Policies** (critical → medium):
1. No money movement
2. No entry approval
3. No data fabrication
4. Human approval required
5. Tenant isolation
6. No PII leakage
7. High-value review
8. Audit trail

**5 Guardrails**:
- `validate_journal_entry()` → balanced, valid accounts
- `validate_llm_output()` → no injection, no PII
- `validate_cross_tenant()` → isolation enforced
- `validate_transaction_amount()` → threshold flagging
- `validate_prompt_injection()` → jailbreak detection

---

## Evaluation

**Scorer** computes:
| Metric | Weight | Method |
|--------|--------|--------|
| Extraction | 25% | Field completeness, vendor match |
| Journal | 30% | Entry count, balance validation |
| Compliance | 25% | Issue detection accuracy |
| Audit | 20% | Risk level alignment |

**Experiments**: baseline_heuristic vs. rag_single_agent vs. agentic_full
- Results: Agentic outperforms by ~15-20% composite

---

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Django 4.x, DRF, Postgres |
| Frontend | React 18, TypeScript, Vite |
| Models | Pydantic v2 |
| Async | asyncio (optional) |
| Memory | In-memory (prod: ChromaDB) |
| LLM | Placeholder (prod: GPT-4/Claude) |

---

## Code Organization

```
agentic/
├── agents/          # Agent definitions + registry
│   ├── messaging/   # Protocol + bus
│   └── supervisor/  # Failure recovery
├── engine/          # Processing modules
│   ├── ingestion/
│   ├── normalization/
│   ├── entry_generation/
│   ├── compliance/
│   ├── audit/
│   └── evaluation/  # Scorer
├── workflows/       # Pipeline definitions
│   └── steps/       # Receipts, invoices, bank, multi-doc
├── memory/          # VectorStore + retrieval
├── safety/          # Policies + guards
├── data_synthesis/  # Test scenario generation
├── experiments/     # Baseline runner
└── interfaces/      # Django views + API
```

---

*December 2024*
