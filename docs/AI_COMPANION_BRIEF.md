# Clover Books — AI Companion Brief

*Technical overview of AI stack and safety design for residency reviewers*

---

## AI Stack Overview

Clover Books uses a **dual-provider architecture**:

| Provider | Model | Use Case | Latency |
|----------|-------|----------|---------|
| **DeepSeek** | `deepseek-chat` | Text reasoning, insights, narratives | 2-10s |
| **OpenAI** | `gpt-4o-mini` | Vision/OCR for receipt extraction | 3-8s |

### Why Two Providers?

1. **Cost optimization**: DeepSeek is significantly cheaper for text tasks
2. **Capability matching**: OpenAI excels at vision; DeepSeek excels at reasoning
3. **Fallback resilience**: If one provider is down, core features still work

---

## LLM Integration Layer

### Key Components

```
companion/llm.py
├── LLMProfile enum           # LIGHT_CHAT, HEAVY_REASONING
├── call_deepseek_reasoning() # Core text LLM wrapper
├── call_vision_model()       # OpenAI vision wrapper
└── _is_llm_enabled()         # Feature flag check

core/llm_reasoning.py
├── reason_about_books_review()    # Books Review LLM call
├── reason_about_bank_review()     # Bank Review LLM call
├── reason_about_receipts_run()    # Receipts analysis
├── refine_companion_issues()      # Issue refinement
├── generate_companion_story()     # Weekly narrative
└── Pydantic models for validation
```

### LLMProfile Design

Originally designed with two profiles:

```python
class LLMProfile(str, Enum):
    HEAVY_REASONING = "deepseek-reasoner"  # R1 model
    LIGHT_CHAT = "deepseek-chat"           # Chat model
```

**Current status**: All surfaces use `LIGHT_CHAT` because `deepseek-reasoner` doesn't reliably follow JSON formatting instructions.

### Configuration

```bash
COMPANION_LLM_ENABLED=true
COMPANION_LLM_API_BASE=https://api.deepseek.com/v1
COMPANION_LLM_API_KEY=<your-key>
COMPANION_LLM_MODEL=deepseek-chat
COMPANION_LLM_TIMEOUT_SECONDS=60
COMPANION_LLM_MAX_TOKENS=2048
OPENAI_API_KEY=<your-key>
```

---

## Safety Design: Deterministic-First

### Core Principle

**LLM is best-effort, deterministic is guaranteed.**

Every AI surface follows this pattern:

```
1. Run deterministic checks (always)
2. If AI enabled AND no timeout → run LLM
3. Validate LLM output against schema
4. Combine results (deterministic + AI if available)
5. User reviews and approves
```

### No Auto-Posting

| Action | Allowed? |
|--------|----------|
| AI suggests journal entry | ✅ Yes |
| AI auto-posts to ledger | ❌ Never |
| AI categorizes expense | ✅ Suggestion only |
| AI moves money | ❌ Never |

### Validation Layers

```python
# All LLM outputs validated with Pydantic
class BooksReviewLLMResult(BaseModel):
    explanations: list[str]
    ranked_issues: list[BooksRankedIssue]
    suggested_checks: list[str]

# Invalid JSON → graceful fallback to deterministic
try:
    result = BooksReviewLLMResult.model_validate(parsed_json)
except ValidationError:
    return None  # Fallback path
```

### Timeout & Fallback

```python
# Every LLM call has a timeout
timeout = getattr(settings, "COMPANION_LLM_TIMEOUT_SECONDS", 60)

# Timeout → return None → deterministic results shown
if not raw:
    return None
```

---

## How Each Surface Uses AI

### 1. Receipts AI

**Provider**: OpenAI GPT-4o-mini (vision)

**Flow**:
1. User uploads receipt image
2. Image sent to GPT-4o-mini with extraction prompt
3. Response: vendor, amount, date, line items
4. DeepSeek suggests account classification (optional)
5. User reviews and approves

**Deterministic fallback**: Manual entry form

### 2. Invoices AI

**Provider**: DeepSeek (optional insights)

**Flow**:
1. Invoice status changes trigger Companion strip update
2. DeepSeek generates contextual insight (if enabled)
3. Risk scoring based on due date, amount, customer history

**Deterministic fallback**: Status-based messaging

### 3. Books Review

**Provider**: DeepSeek

**Flow**:
1. User selects date range
2. **Deterministic checks run first**:
   - `LARGE_ENTRY`: Above threshold
   - `POSSIBLE_DUPLICATE`: Same desc/date/amount
   - `OUTLIER_AMOUNT`: Statistical outliers
   - `ADJUSTMENT_ENTRY`: Manual adjustments
3. If AI enabled: `reason_about_books_review()` called
4. Results combined: deterministic findings + Neural Analysis

**Key function**: `core/agentic_books_review.py` → `run_books_review_workflow()`

### 4. Bank Review

**Provider**: DeepSeek

**Flow**:
1. User selects bank account and date range
2. Deterministic checks for unmatched transactions
3. If AI enabled: `reason_about_bank_review()` called
4. AI highlights discrepancies with explanations

### 5. Companion Control Tower

**Provider**: DeepSeek

**Components**:

| Component | AI Involvement |
|-----------|----------------|
| Radar | Calculated deterministically from run data |
| Coverage | Calculated deterministically |
| Close-Readiness | Calculated deterministically |
| Playbook | Aggregated from issues (deterministic) |
| Story | **LLM-generated** weekly narrative |
| Issues | Aggregated + optionally **LLM-refined** |

---

## Companion Control Tower Details

### Radar Calculation

4-axis stability score (0-100):

```python
radar = {
    "cash_reconciliation": calculate_bank_health(),
    "revenue_invoices": calculate_invoice_health(),
    "expenses_receipts": calculate_expense_health(),
    "tax_compliance": calculate_tax_health()
}
```

### Story Generation

**Prompt structure**:
```
You are "CERN Companion," an AI accounting controller.
STYLE: Calm, friendly, professional. Be concise.
INPUT: Radar scores, recent metrics, recent issues, focus_mode.
TASK: Write one-sentence summary + 2-4 timeline bullets.
OUTPUT: JSON only.
```

**Fallback**: Generic deterministic summary if LLM fails.

---

## Limitations & Open Questions

### Current Limitations

1. **No real-time streaming**: LLM responses are synchronous
2. **No conversation memory**: Each call is stateless
3. **Single-model per task**: No model chaining or ensemble
4. **Limited evals**: No automated accuracy benchmarks yet

### Open Questions for Residency

1. **Evaluation framework**: How to measure LLM quality for accounting?
2. **Anomaly detection**: Can we detect fraud patterns?
3. **Multi-document reasoning**: Correlating invoices ↔ payments ↔ bank
4. **Personalization**: Learning user preferences over time
5. **Multi-tenant safety**: Guaranteeing data isolation in embeddings

### Desired Experiments

| Experiment | Goal |
|------------|------|
| Evals suite | Measure extraction/classification accuracy |
| RAG for context | Use historical transactions as context |
| Agent-to-agent | Compliance agent ↔ Audit agent communication |
| Anomaly detection | Pattern-based fraud flagging |

---

*December 2024*
