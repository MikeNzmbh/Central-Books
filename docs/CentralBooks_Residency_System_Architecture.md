# Central Books — System Architecture

*Technical architecture reference for AI Residency reviewers*

---

## System Overview

Central Books is a Django-based accounting platform with a React frontend. The system features:

- **Core Accounting**: Invoices, expenses, receipts, journal entries, chart of accounts
- **Banking**: Bank accounts, transactions, reconciliation
- **AI Surfaces**: Receipts AI, Invoices AI, Books Review, Bank Review
- **Companion Control Tower**: Unified AI-powered dashboard for financial health monitoring

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                           REACT FRONTEND                              │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Dashboard │ Invoices │ Expenses │ Receipts │ Banking │ COA  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    AI COMPANION SURFACES                      │    │
│  │  Books Review │ Bank Review │ Receipts AI │ Companion Tower   │    │
│  └──────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────┐
│                           DJANGO BACKEND                              │
├──────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │   core/views    │  │  companion/llm  │  │   agentic/engine    │  │
│  │   (REST API)    │  │  (LLM wrapper)  │  │   (workflows)       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  core/models    │  │ llm_reasoning   │  │  views_companion    │  │
│  │  (Django ORM)   │  │ (structured)    │  │  (Control Tower)    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────┐
│                         EXTERNAL SERVICES                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │   PostgreSQL    │  │   DeepSeek API  │  │   OpenAI API        │  │
│  │   (Database)    │  │   (Text LLM)    │  │   (Vision/OCR)      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Django Models (core/models.py)

### Business & Users

| Model | Purpose |
|-------|---------|
| `Business` | Multi-tenant business entity. All data is scoped to a business. |
| `UserBusinessMembership` | Links users to businesses with roles. |

### Chart of Accounts

| Model | Purpose |
|-------|---------|
| `Account` | Chart of accounts entries (assets, liabilities, income, expenses). |
| `TaxRate` | Tax rates for invoices/expenses. |
| `TaxGroup` | Groups of tax rates for complex scenarios. |

### Transactions

| Model | Purpose |
|-------|---------|
| `Invoice` | Sales invoices with status tracking (DRAFT/SENT/PAID/OVERDUE). |
| `InvoiceItem` | Line items on invoices. |
| `Expense` | Business expenses with category/supplier/receipt. |
| `ExpenseCategory` | Expense classification. |
| `Supplier` | Vendor/supplier records. |
| `Customer` | Customer records. |

### Ledger

| Model | Purpose |
|-------|---------|
| `JournalEntry` | Double-entry journal entries. |
| `JournalLine` | Debit/credit lines within journal entries. |

### Banking

| Model | Purpose |
|-------|---------|
| `BankAccount` | Bank accounts (manual or connected). |
| `BankTransaction` | Imported bank transactions. |
| `ReconciliationMatch` | Links bank transactions to journal entries. |

### AI Surfaces

| Model | Purpose |
|-------|---------|
| `ReceiptRun` | Receipt AI processing runs with OCR results. |
| `BooksReviewRun` | Books Review audit runs with findings. |
| `BankReviewRun` | Bank Review reconciliation analysis runs. |
| `CompanionIssue` | Aggregated issues from all AI surfaces. |

---

## LLM Integration

### Provider Architecture

Central Books uses two LLM providers:

| Provider | Model | Use Case |
|----------|-------|----------|
| **DeepSeek** | `deepseek-chat` | Text reasoning, insights, narratives, JSON output |
| **OpenAI** | `gpt-4o-mini` | Vision/OCR for receipt extraction |

### LLMProfile Enum (companion/llm.py)

```python
class LLMProfile(str, Enum):
    HEAVY_REASONING = "deepseek-reasoner"  # Currently unused (JSON issues)
    LIGHT_CHAT = "deepseek-chat"           # Primary model for all surfaces
```

> **Note**: `deepseek-reasoner` (R1) was originally intended for complex analysis but doesn't follow JSON formatting instructions reliably. All surfaces now use `deepseek-chat` for consistent structured output.

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `call_deepseek_reasoning()` | `companion/llm.py` | Core LLM call wrapper with timeout/retry |
| `call_companion_llm()` | `companion/llm.py` | Alias for reasoning calls |
| `call_vision_model()` | `companion/llm.py` | OpenAI vision API for OCR |

### LLM Call Flow

```
User Action → Django View → _invoke_llm() → call_companion_llm()
                                ↓
                    DeepSeek API (with timeout)
                                ↓
                    Pydantic validation (BooksReviewLLMResult, etc.)
                                ↓
                    Structured response or graceful fallback
```

---

## AI Surfaces

### 1. Receipts AI

**Purpose**: Extract data from receipt images and suggest journal entries.

**Flow**:
1. User uploads receipt image
2. `call_vision_model()` → GPT-4o-mini extracts vendor, amount, date, line items
3. DeepSeek suggests account classification
4. User reviews and approves posting

**Key Files**:
- `core/views.py` → `receipt_ocr_view`
- `companion/llm.py` → `call_vision_model()`
- `templates/receipts/`

### 2. Invoices AI

**Purpose**: Risk scoring and insights for invoice management.

**Flow**:
1. Invoice created/updated
2. Companion strip shows contextual insights
3. Status changes tracked with AI commentary

**Key Files**:
- `core/views.py` → `invoice_*` views
- `core/llm_reasoning.py` → `reason_about_invoices_run()`

### 3. Books Review

**Purpose**: Ledger-wide audit with deterministic checks + AI insights.

**Flow**:
1. User selects date range and runs review
2. Deterministic checks run first (duplicates, outliers, large entries, adjustments)
3. If AI enabled: `reason_about_books_review()` generates Neural Analysis
4. Results saved to `BooksReviewRun` model

**Key Files**:
- `core/agentic_books_review.py` → `run_books_review_workflow()`
- `core/llm_reasoning.py` → `reason_about_books_review()`
- `frontend/src/books-review/`

**Deterministic Checks**:
- `LARGE_ENTRY`: Entries above threshold
- `POSSIBLE_DUPLICATE`: Same desc/date/amount
- `OUTLIER_AMOUNT`: Statistical outliers
- `ADJUSTMENT_ENTRY`: Manual adjustments
- `UNBALANCED`: Dr ≠ Cr

### 4. Bank Review

**Purpose**: Per-account reconciliation analysis.

**Flow**:
1. User selects bank account and date range
2. Deterministic checks for unmatched transactions
3. AI insights on discrepancies

**Key Files**:
- `core/views.py` → `api_bank_review_*`
- `core/llm_reasoning.py` → `reason_about_bank_review()`

---

## Companion Control Tower

The Companion Control Tower aggregates insights from all AI surfaces into a single dashboard.

### Components

| Component | Purpose | Data Source |
|-----------|---------|-------------|
| **Radar** | 4-axis stability scores | Calculated from recent runs |
| **Coverage** | % of transactions reviewed | Run counts vs. transaction counts |
| **Close-Readiness** | Month-end checklist | Task completion status |
| **Playbook** | Prioritized actions | Aggregated from issues |
| **Story** | Weekly narrative | LLM-generated summary |
| **Issues** | Aggregated findings | All surfaces |

### Radar Axes

```python
{
    "cash_reconciliation": 0-100,    # Bank matching health
    "revenue_invoices": 0-100,       # Invoice collection health
    "expenses_receipts": 0-100,      # Expense documentation health
    "tax_compliance": 0-100          # Tax filing readiness
}
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agentic/companion/summary` | GET | Full Control Tower data |
| `/api/agentic/companion/issues` | GET | Aggregated issues list |
| `/api/companion/overview/` | GET | Per-context summaries |
| `/api/agentic/books-review/run` | POST | Run Books Review |
| `/api/agentic/books-review/runs` | GET | List Books Review runs |
| `/api/agentic/bank-review/run` | POST | Run Bank Review |

### Key Files

- `core/views_companion.py` → `api_companion_summary()`
- `core/llm_reasoning.py` → `generate_companion_story()`
- `frontend/src/companion/`

---

## Deterministic-First Architecture

All AI surfaces follow a **deterministic-first** pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                      USER REQUEST                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              DETERMINISTIC ENGINE (always runs)              │
│  • Rule-based checks                                         │
│  • Statistical analysis                                      │
│  • Pattern matching                                          │
│  • Guaranteed to complete                                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │    AI COMPANION ENABLED?       │
              └───────────────┬───────────────┘
                    │                   │
                   YES                  NO
                    │                   │
                    ▼                   │
┌─────────────────────────────┐         │
│   LLM REASONING (optional)  │         │
│  • DeepSeek API call        │         │
│  • Timeout: 60s             │         │
│  • Graceful fallback        │         │
└─────────────────────────────┼─────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                  COMBINED RESULT                             │
│  • Deterministic findings (always present)                   │
│  • AI insights (if available)                                │
│  • Graceful degradation on LLM failure                       │
└─────────────────────────────────────────────────────────────┘
```

### Safety Guarantees

1. **No auto-posting**: AI suggests, human approves
2. **No data fabrication**: LLM outputs validated against input data
3. **Tenant isolation**: All queries scoped to user's business
4. **Timeout handling**: LLM calls have configurable timeouts
5. **Graceful fallback**: LLM failure → deterministic results only
6. **Audit trail**: All runs logged with timestamps and trace IDs

---

## Directory Structure

```
Central-Books/
├── core/                      # Main Django app
│   ├── models.py              # All database models
│   ├── views.py               # API views and endpoints
│   ├── views_companion.py     # Companion Control Tower views
│   ├── agentic_books_review.py # Books Review workflow
│   ├── llm_reasoning.py       # Structured LLM calls + Pydantic models
│   ├── llm_tone.py            # Personalization for LLM prompts
│   └── pdf_utils.py           # PDF generation (reportlab)
├── companion/                 # LLM integration layer
│   ├── llm.py                 # LLM call wrappers (DeepSeek, OpenAI)
│   └── ...
├── agentic/                   # Agentic workflow engine
│   ├── agents/                # AI employee agents
│   ├── engine/                # Processing modules
│   ├── workflows/             # Pipeline definitions
│   └── interfaces/            # API routers
├── agentic_core/              # Shared Pydantic models
├── frontend/                  # React + Vite frontend
│   ├── src/
│   │   ├── books-review/      # Books Review UI
│   │   ├── companion/         # Companion components
│   │   ├── reconciliation/    # Banking reconciliation
│   │   └── ...
│   └── ...
├── templates/                 # Django templates
├── docs/                      # Documentation
├── .env.example               # Environment variable template
├── requirements.txt           # Python dependencies
└── render.yaml                # Render.com deployment config
```

---

## Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test core.tests

# Run with verbose output
python manage.py test --verbosity=2
```

> **Note**: Some tests mock external LLM calls. Set `COMPANION_LLM_ENABLED=false` for deterministic-only testing.

---

*Last updated: December 2024*
