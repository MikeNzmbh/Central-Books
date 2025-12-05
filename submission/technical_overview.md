# Technical Overview

*For Engineers and Reviewers*

---

## 1. High-Level Architecture

### Request Flow

```
User → Web Demo UI → POST /agentic/demo/receipts-run/
                              ↓
                     WorkflowGraph.run()
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓         ↓           ↓           ↓         ↓         ↓
     ingest → extract → normalize → generate → compliance → audit
        ↓         ↓           ↓         entries       ↓         ↓
   RawDocument  Extracted  Normalized  JournalEntry ComplianceCheck AuditReport
                Document   Transaction
                              ↓
                     WorkflowRunResult
                              ↓
                     JSON Response
```

### Component Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| **Models** | `agentic_core/models/` | Pydantic schemas for all data types |
| **Engine** | `agentic/engine/` | Processing modules (ingestion, normalization, entry generation, compliance, audit) |
| **Agents** | `agentic/agents/` | AI Employee agents with profiles and capabilities |
| **Workflows** | `agentic/workflows/` | DAG-based orchestration engine |
| **Interfaces** | `agentic/interfaces/` | CLI, HTTP API, and web views |

---

## 2. Core Data Models

### Document Models

```python
# agentic/workflows/steps/receipts_pipeline.py

@dataclass
class RawDocument:
    id: str
    filename: str
    content: str = ""
    source: str = "upload"
    mime_type: str = "application/pdf"

@dataclass
class ExtractedDocument:
    id: str
    raw_document_id: str
    vendor_name: str = "Unknown Vendor"
    total_amount: Decimal = Decimal("0")
    currency: str = "USD"
    txn_date: str = ""
    category_code: str = "6000"
    line_items: List[dict] = field(default_factory=list)
```

### Transaction Model

```python
@dataclass
class NormalizedTransaction:
    id: str
    description: str
    amount: Decimal
    currency: str = "USD"
    date: str = ""
    category_code: str = "6000"
    source_document_id: str = ""
```

### Journal Entry Model

```python
# agentic/engine/entry_generation/double_entry_generator.py

@dataclass
class JournalLine:
    account_code: str
    account_name: str
    side: str  # "debit" or "credit"
    amount: Decimal

@dataclass
class GeneratedEntry:
    entry_id: str
    date: str
    description: str
    lines: List[JournalLine]
    is_balanced: bool
    total_debits: Decimal
    total_credits: Decimal
```

### Compliance Models

```python
# agentic/engine/compliance/__init__.py

class ComplianceIssue(BaseModel):
    code: str           # e.g. "CURRENCY_MISMATCH"
    message: str
    severity: str       # "info", "low", "medium", "high", "critical"
    transaction_id: Optional[str] = None
    suggestion: Optional[str] = None

class ComplianceCheckResult(BaseModel):
    issues: List[ComplianceIssue] = []
    is_compliant: bool = True
```

### Audit Models

```python
# agentic/engine/audit/__init__.py

class AuditFinding(BaseModel):
    code: str           # e.g. "UNUSUAL_SCALE"
    message: str
    severity: str
    transaction_id: Optional[str] = None
    journal_entry_id: Optional[str] = None
    suggestion: Optional[str] = None

class AuditReport(BaseModel):
    findings: List[AuditFinding] = []
    risk_level: str = "low"  # "low", "medium", "high"
```

---

## 3. Workflow Engine

### WorkflowGraph API

```python
# agentic/workflows/graph/workflow_graph.py

class WorkflowGraph:
    def __init__(self, name: str):
        """Initialize a named workflow."""

    def add_step(self, name: str, fn: Callable[[Dict], None]) -> None:
        """Register a step function."""

    def add_edge(self, from_step: str, to_step: str) -> None:
        """Define dependency between steps."""

    def run(self, initial_context: Dict) -> WorkflowRunResult:
        """Execute steps in topological order."""
```

### Step Registration

Steps are plain functions that mutate a context dictionary:

```python
def ingest_step(context: Dict[str, Any]) -> None:
    uploaded = context.get("uploaded_files", [])
    docs = []
    for f in uploaded:
        docs.append(RawDocument(id=..., filename=...))
    context["documents"] = docs
```

### Execution Model

1. `_topological_sort()` orders steps by dependencies (Kahn's algorithm)
2. For each step:
   - Check if dependencies failed (skip if so)
   - Record `started_at` timestamp
   - Execute step function
   - Record `finished_at` and `duration_ms`
   - Capture errors without halting pipeline
3. Collect artifacts from final context
4. Return `WorkflowRunResult`

### Result Structure

```python
class WorkflowRunResult(BaseModel):
    workflow_name: str
    status: str  # "success" | "partial" | "failed"
    started_at: datetime
    finished_at: datetime
    steps: List[WorkflowStepResult]
    artifacts: Dict[str, Any]
    duration_ms: float
```

### Why This Design?

- **Deterministic**: Same inputs produce same outputs (no hidden state)
- **Testable**: Each step can be unit tested in isolation
- **Observable**: Every step's timing and status is recorded
- **Resilient**: Failed steps don't crash the entire pipeline

---

## 4. Agents Layer

### Base Agent (agentic_core)

```python
# agentic_core/agents/base_agent.py

class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self):
        self._trace: Optional[AgentTrace] = None
        self._llm_calls: List[LLMCallMetadata] = []

    @abstractmethod
    async def run(self, input_context: Dict) -> Dict:
        """Execute the agent's main task."""

    def register_tool(self, name: str, fn: Callable) -> None:
        """Register a callable tool for the agent."""
```

### Agent Profiles

Each agent has a frozen profile:

```python
# agentic/agents/shared/profile.py

class AgentProfile(BaseModel):
    name: str
    role: str
    description: str
    capabilities: Tuple[str, ...]
    max_parallel_tasks: int = 1
    risk_level: str  # "low", "medium", "high"
    llm_model: str = "gpt-4"
    tools: Tuple[str, ...] = ()
    owner_team: str = "platform"

    class Config:
        frozen = True
```

### Registered Agents

| Agent | Role | Capabilities | Risk |
|-------|------|--------------|------|
| OperationsAgent | Workflow orchestration | `summarize_workflow_run`, `propose_retry_plan` | Medium |
| SupportAgent | User assistance | `answer_user_question`, `suggest_onboarding_steps` | Low |
| SalesAgent | Demo generation | `generate_demo_script`, `propose_pricing_tiers` | Low |
| EngineeringAgent | Error analysis | `summarize_error_logs`, `suggest_fix_priors` | Medium |
| DataIntegrityAgent | Anomaly detection | `scan_for_schema_drift`, `flag_suspicious_transactions` | High |

### Registry API

```python
# agentic/agents/registry.py

def get_agent(role: str) -> BaseAgent:
    """Factory function to instantiate an agent by role."""

def list_agent_profiles() -> Dict[str, AgentProfile]:
    """Return all registered agent profiles."""
```

### Future Collaboration

The registry enables:
- Dynamic agent discovery
- Operations agent dispatching tasks to specialized agents
- Risk-based approval routing

---

## 5. Demo API

### Endpoint

```
POST /agentic/demo/receipts-run/
```

### Request Schema

```json
{
  "documents": [
    {
      "filename": "receipt.pdf",
      "content": "Office Depot - $89.99 - office supplies"
    }
  ]
}
```

### Response Schema

```json
{
  "workflow_name": "receipts_to_journal_entries",
  "status": "success",
  "duration_ms": 1.23,
  "steps": [
    {
      "name": "ingest",
      "status": "success",
      "duration_ms": 0.01,
      "error": null
    }
  ],
  "extracted_documents": [
    {
      "id": "ext-1",
      "vendor_name": "Office Depot",
      "total_amount": "89.99",
      "currency": "USD",
      "category_code": "6100"
    }
  ],
  "transactions": [
    {
      "id": "txn-ext-1",
      "description": "Receipt from Office Depot",
      "amount": "89.99",
      "currency": "USD",
      "category_code": "6100"
    }
  ],
  "journal_entries": [
    {
      "entry_id": "je-txn-ext-1",
      "description": "Receipt from Office Depot",
      "lines": [
        {"account_code": "6100", "account_name": "Office Supplies", "side": "debit", "amount": "89.99"},
        {"account_code": "1000", "account_name": "Cash/Bank", "side": "credit", "amount": "89.99"}
      ],
      "is_balanced": true,
      "total_debits": "89.99",
      "total_credits": "89.99"
    }
  ],
  "compliance": {
    "issues": [],
    "is_compliant": true
  },
  "audit": {
    "findings": [],
    "risk_level": "low"
  },
  "summary": "Processed 1 document(s), produced 1 journal entries.",
  "notes": null
}
```

### Interface Reuse

The same workflow engine powers:
- **CLI demo**: `python -m agentic.workflows.cli_receipts_demo`
- **Web UI**: React component at `/agentic/demo/receipts/`
- **Automated tests**: pytest fixtures call `build_receipts_workflow()`

---

## 6. Testing Strategy

### Test Modules

| Module | Location | Validates |
|--------|----------|-----------|
| `test_receipts_workflow.py` | `agentic/workflows/tests/` | Workflow builds, runs, produces correct artifacts |
| `test_compliance_and_audit.py` | `agentic/engine/tests/` | Compliance flags issues, audit detects anomalies |
| `test_receipts_demo_api.py` | `agentic/interfaces/api/tests/` | API returns correct response, handles errors |
| `test_agents_basic.py` | `agentic/agents/tests/` | Registry works, agents instantiate, methods execute |

### What Each Validates

**Workflow Tests**:
- Pipeline builds with 6 steps
- All steps succeed with sample input
- Context keys are populated correctly
- `WorkflowRunResult` is serializable

**Compliance Tests**:
- Currency mismatch detection
- Unusual amount flagging (>$100K)
- Unbalanced entry detection
- `is_compliant` logic

**Audit Tests**:
- Unusual scale detection (>3x average)
- Suspense account flagging
- Risk level calculation

**API Tests**:
- 200 OK for valid request
- 400 for missing documents
- Response includes all expected fields
- Demo page renders

### Running Tests

```bash
# Django tests
python manage.py test agentic

# Or with pytest (if installed)
pytest agentic/
```

---

## Appendix: File Structure

```
agentic/
├── __init__.py
├── README_RESIDENCY.md
├── agents/
│   ├── __init__.py
│   ├── registry.py
│   ├── shared/profile.py
│   ├── operations/operations_agent.py
│   ├── support/support_agent.py
│   ├── sales/sales_agent.py
│   ├── engineering/engineering_agent.py
│   ├── data_integrity/data_integrity_agent.py
│   └── tests/test_agents_basic.py
├── engine/
│   ├── __init__.py
│   ├── ingestion/receipt_ingestor.py
│   ├── normalization/transaction_normalizer.py
│   ├── entry_generation/double_entry_generator.py
│   ├── compliance/__init__.py
│   ├── audit/__init__.py
│   └── tests/test_compliance_and_audit.py
├── workflows/
│   ├── __init__.py
│   ├── graph/workflow_graph.py
│   ├── steps/receipts_pipeline.py
│   ├── cli_receipts_demo.py
│   └── tests/test_receipts_workflow.py
└── interfaces/
    ├── __init__.py
    ├── views.py
    └── api/
        ├── __init__.py
        ├── agentic_api_router.py
        ├── schemas.py
        └── tests/test_receipts_demo_api.py

agentic_core/
├── __init__.py
├── README.md
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

*December 2024*
