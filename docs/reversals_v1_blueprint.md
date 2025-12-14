# Central Books (CERN) – Reversals, Credits, Refunds & Allocations (v1 Blueprint)

This document is the **implementation source-of-truth** for adding customer/vendor reversals on top of:

- `docs/tax_engine_v1_blueprint.md` (Tax Engine v1 + `TransactionLineTaxDetail`)
- `docs/tax_guardian.md` (Tax Guardian / snapshots / anomalies)

The intent is **deterministic accounting**, an **immutability mindset**, and **explicit allocations** (no “$0 payments” hacks).

---

## 1) Principles & Invariants

### 1.1 Immutability (Document-Level)

- “Posted” documents are treated as immutable events.
- Changes happen via new documents (credits/refunds), or explicit `VOIDED`.
- We don’t implement cryptographic hashing in v1, but we design as if we could later.

Practical v1 enforcement:
- Hard block edits to money + tax fields after `POSTED` (model `clean()` + service layer guards).
- Allow only safe fields post-posting: `notes`, `external_reference`, `attachments` (if any).

### 1.2 Allocation Is First-Class

- Linkage between **credit-like** and **debit-like** documents is explicit via `Allocation`.
- Supports:
  - One credit → many invoices/bills.
  - One invoice/bill → many credits/deposits/payments.
  - Partial allocations.
- Allocation must be validated (no over-allocation; business + currency compatible).

### 1.3 Deterministic Tax Integration (No LLM)

- Credits/refunds integrate by writing signed `TransactionLineTaxDetail` rows.
- Tax Guardian continues to work by aggregating `TransactionLineTaxDetail` (no special-cases in snapshots).
- “Tax DNA inheritance” is the default for reversals linked to a source document.

---

## 2) Terminology

- **Posting**: creating the canonical accounting effects (JournalEntry + tax detail rows) for a document.
- **Available amount**: a credit/deposit’s remaining amount that can still be applied/refunded.
- **Applied amount**: sum of allocations consuming a document’s available amount.
- **Tax DNA**: jurisdiction stack + effective rates + component breakdown as captured by the *source* document’s persisted `TransactionLineTaxDetail`.
- **Customer deposit / retainer**: unapplied cash recorded as a **liability** (never P&L income).

---

## 3) Scope & v1 Constraints

### In scope (v1)

- Customer-side:
  - Credit Memos (posting) + allocations to invoices
  - Customer Deposits (overpayments/unapplied cash) + apply to invoices
  - Customer Refunds (cash out) tied to a credit memo and/or deposit
- Vendor-side (minimal v1):
  - Vendor Credits + Vendor Refunds (optional v1; full AP workflow can be Phase 2)
- Deterministic tax integration:
  - Signed `TransactionLineTaxDetail` and Tax Guardian correctness

### Not in scope (v1)

- Inventory-aware returns (COGS, stock moves)
- Jurisdiction-specific prior-period adjustment boxes
- Fully generalized multi-line documents (invoices/credits remain “single-line” in current core)
- Celery/background processing
- New LLM features

---

## 4) Where the Code Lives (Recommended Layout)

### Recommendation: new Django app `reversals`

Rationale:
- Keeps `core/models.py` from becoming even more monolithic.
- Reversals are a cross-cutting subledger concern (AR/AP + allocations + cash movements).
- Still integrates cleanly with existing `core` posting patterns and `taxes` engine.

Proposed structure:

- `reversals/models.py` — new document + allocation models
- `reversals/services/`:
  - `posting.py` — deterministic JournalEntry creation
  - `tax_inheritance.py` — copy/scale Tax DNA
  - `allocations.py` — validation + apply/unapply
  - `balances.py` — compute remaining amounts + invoice/bill balances
- `reversals/views.py` — Option B JSON APIs (function-based views are consistent with current code)
- `reversals/urls.py` — mounted from `core/urls.py` under `/api/reversals/...`
- `reversals/tests/` — focused unit tests around posting + tax details + allocation validation

Fallback (acceptable): put models in `core/models.py` and services under `core/services/reversals_*` if you want fewer Django plumbing changes.

---

## 5) Data Model (Django)

### 5.1 Shared fields (document mixin pattern)

All posted documents should standardize:

- `business` (FK)
- `currency` (3-char)
- `issue_date` / `posting_date` (date)
- `status` (`DRAFT`, `POSTED`, `VOIDED`, plus doc-specific)
- `number` (string; optional v1)
- `memo` / `notes`
- `posted_journal_entry` linkage (consistent with `Invoice`/`Expense` patterns)
  - Prefer: `GenericRelation("core.JournalEntry", ...)` if we keep the same “source_object” linkage.

### 5.2 Allocation model (first-class)

Goal: represent “apply X of source to Y target” deterministically.

Model sketch:

```python
class Allocation(models.Model):
    business = models.ForeignKey("core.Business", on_delete=models.CASCADE)

    # Subledger “direction” helps reporting and validation (optional but useful).
    class LedgerSide(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer (AR)"
        VENDOR = "VENDOR", "Vendor (AP)"
    ledger_side = models.CharField(max_length=12, choices=LedgerSide.choices)

    source_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    source_object_id = models.PositiveIntegerField()
    source_object = GenericForeignKey("source_content_type", "source_object_id")

    target_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    target_object_id = models.PositiveIntegerField()
    target_object = GenericForeignKey("target_content_type", "target_object_id")

    amount = models.DecimalField(max_digits=12, decimal_places=2)  # always positive
    currency = models.CharField(max_length=3)
    allocated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    # Optional: groups multiple allocations into one “apply” operation for audit/UI.
    operation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
```

Validation rules (service-layer + DB constraints where possible):
- `amount > 0`
- `source.business == target.business == allocation.business`
- same currency (v1), or explicit FX fields (phase 2+)
- `sum(allocations.amount for source) <= source.total_amount`
- `sum(allocations.amount for target) <= target.open_amount` (where “open” is deterministic)

### 5.3 Customer documents

#### A) `PendingCredit` (non-posting; Phase 2 if invoice generation is not present)

States: `DRAFT` → `ACTIVE` → `CONSUMED` / `CANCELLED`

Fields:
- `business`, `customer`
- `amount`, `currency`
- `status`, `created_at`, `activated_at`, `consumed_at`
- `reason` / `memo`

Consumption behavior:
- When generating a new invoice for the customer, convert into a “discount line” (future: multi-line).
- If invoices remain single-line, v1 UI can still show pending credits as a queue item, but true “line conversion” is Phase 2.

#### B) `CustomerCreditMemo` (posting)

Purpose: reverse an already-posted invoice (partial or full).

States:
- `DRAFT` → `POSTED` → (`VOIDED`)
- `APPLIED` is derived: `available_amount == 0` and `status == POSTED`

Key fields:
- `business`, `customer`
- `source_invoice` (nullable FK to `core.Invoice`)
- `posting_date`
- `net_amount`, `tax_amount`, `gross_amount`
- `tax_group` (optional; if linked to invoice, inherit)
- `status`, `void_reason`, `voided_at`

Tax DNA (critical):
- If `source_invoice` exists, **inherit tax details by copying** the invoice’s `TransactionLineTaxDetail` rows and writing them as **negative** amounts for the credit memo.
- If no source invoice, compute tax deterministically using current tax engine rules (less ideal, but allowed).

Ledger posting (canonical):
- Debit revenue (or contra-revenue) for net amount.
- Debit sales tax payable for tax amount (reducing liability).
- Credit Accounts Receivable for gross amount.

#### C) `CustomerDeposit` (posting; unapplied cash / overpayments)

Purpose: record cash received that is **not** yet tied to an invoice (liability, not income).

States:
- `DRAFT` → `POSTED` → (`VOIDED`)
- `APPLIED` is derived: `available_amount == 0` and `status == POSTED`

Fields:
- `business`, `customer`
- `bank_account` (FK to `core.BankAccount` or `core.Account`)
- `posting_date`
- `amount`, `currency`
- `status`

Ledger posting:
- Debit bank/cash
- Credit `Customer Deposits` (new default liability account; e.g., code `2100`)

Applying deposit to invoice (allocation + posting):
- Create `Allocation(source=deposit, target=invoice, amount=x)`
- Create JournalEntry:
  - Debit Customer Deposits (reduce liability)
  - Credit Accounts Receivable (reduce AR)

#### D) `CustomerRefund` (posting; cash outflow)

Purpose: money paid back to customer (bank outflow).

States: `DRAFT` → `POSTED` → `VOIDED`

Fields:
- `business`, `customer`
- `bank_account`
- `posting_date`
- `amount`, `currency`
- Optional link targets:
  - `credit_memo` (nullable FK)
  - `deposit` (nullable FK)
  - (optional) `source_invoice` for UI context

Posting modes (deterministic):
- If refunding a **credit memo balance**: Debit AR, Credit bank
- If refunding a **deposit liability**: Debit Customer Deposits, Credit bank
- One-step “refund receipt” UX can be implemented as a convenience that *creates* a credit memo + refund atomically, rather than inventing a separate posting mode.

### 5.4 Vendor documents (two options)

Option A (Phase 2 recommended): introduce true accrual `Bill` model (AP posting on bill receipt).
Option B (v1 minimal): treat existing `Expense` as bill-like, but note current code only posts on “paid”.

#### A) `VendorCredit`

States: `DRAFT` → `POSTED` → `VOIDED` (applied derived)

Fields:
- `business`, `supplier`
- `source_expense`/`source_bill` (nullable)
- `posting_date`
- `net_amount`, `tax_amount`, `gross_amount`
- `tax_group` (optional; inherit if linked)

Tax DNA:
- If linked to a purchase document, copy its tax details and negate.

Ledger posting (true AP workflow):
- Debit Accounts Payable (reduce liability)
- Credit expense/COGS (reverse)
- Credit Tax Recoverable for recoverable components (reverse ITC)

#### B) `VendorRefund`

States: `DRAFT` → `POSTED` → `VOIDED`

Fields:
- `business`, `supplier`
- `bank_account`
- Optional: `vendor_credit` link

Ledger posting:
- Debit bank (cash inflow)
- Credit AP (clears vendor credit balance)

---

## 6) Balance & “Remaining Amount” Semantics

### 6.1 Available amount computation

For any “source” credit-like object:

```
available = total_amount - sum(Allocation.amount where source=this)
```

Derived status rules:
- If `status == POSTED` and `available == 0` → “Applied” badge in UI.

### 6.2 Invoice open balance computation (v1)

Long-term: invoice balance should be derived from allocations and cash events.

Incremental v1 approach (minimize breakage):
- Keep `core.Invoice.balance` as a denormalized field.
- Recompute it in the allocation service when allocations affecting the invoice change.

Invoice open amount:

```
invoice_open = invoice.gross_total - sum(allocations.amount where target=invoice)
```

Status mapping:
- `invoice_open == 0` → `PAID` (meaning “settled”, not necessarily cash)
- `0 < invoice_open < gross_total` → `PARTIAL`
- `invoice_open == gross_total` → `SENT` (or `DRAFT` if still draft)

Important: we must **decouple “cash receipt posting” from `Invoice.status == PAID`**.
Otherwise, settling via a credit memo would incorrectly create a Bank vs AR entry.

Recommended fix (Phase 1):
- Introduce `CustomerPayment`/`CustomerDeposit` as the only way to post cash receipt entries.
- Leave invoice `PAID` as a derived subledger state (no GL posting side effects).

---

## 7) Tax Engine v1 Integration Details

### 7.1 Tax DNA inheritance (copy, don’t recalc)

For credit memos/vendor credits linked to a source document:

1. Load source `TransactionLineTaxDetail` rows (component + jurisdiction + amounts).
2. Determine credit ratio:
   - v1 single-line: `ratio = credit_net / source_net` (clamp 0..1)
3. Create new `TransactionLineTaxDetail` rows for the credit document:
   - `taxable_amount_* = - round(source_taxable_amount_* * ratio)`
   - `tax_amount_* = - round(source_tax_amount_* * ratio)`
   - preserve `tax_component`, `tax_group`, `jurisdiction_code`, `is_recoverable`
   - set `transaction_date = credit.posting_date` (v1 constraint: current-period adjustment)
4. Ensure dust-sweeping/rounding keeps sum(component taxes) aligned to credit’s total tax (±$0.01 tolerance).

Why copy is required:
- It guarantees the reversal uses the **same jurisdiction stack + effective rates** as the original invoice/bill, even if rates changed since.

### 7.2 Signed tax details require small engine hardening

Today, `TaxEngine.calculate_for_line` + `taxes/postings.py` assume tax amounts are non-negative.
To support reversals safely:

- Update dust-sweeper in `taxes/services.py` to allow negative tax adjustments (preserve sign).
- Update `taxes/postings.py` helpers to handle negative amounts by flipping debit/credit sides:
  - Sales tax payable reversal (negative tax) should **debit** the liability account.
  - Recoverable tax reversal (negative) should **credit** the recoverable asset account.

### 7.3 Purchases vs Sales classification in snapshots

Tax snapshot aggregation currently infers “purchase” vs “sale” via content type checks (Invoice vs Expense) and otherwise falls back to `detail.is_recoverable` — which is **not reliable** for new document types.

v1 fix (recommended):
- Add `document_side` field to `TransactionLineTaxDetail`:
  - `SALE` / `PURCHASE`
- Populate it for all newly-created details (including inherited copies).
- Update `_aggregate_from_tax_details` to prefer `document_side` when present, fallback to existing logic for legacy rows.

This avoids misclassifying credit memo tax rows as purchases when a component is recoverable.

---

## 8) Posting & Journals (Deterministic)

### 8.1 Default chart of accounts additions (v1)

Add to `core/accounting_defaults.py`:

- `2100` — Customer Deposits (Liability)
- (Optional but better) `4020` — Sales Returns & Allowances (Income-type contra account)
- (Optional) `5020` — Purchase Returns (Expense-type contra)

### 8.2 Posting functions (service layer)

Pattern to follow: `core/accounting_posting.py` (idempotent, atomic).

New deterministic posting entrypoints:

- `post_customer_credit_memo(credit_memo)`
- `post_customer_deposit(deposit)`
- `post_customer_refund(refund)`
- `post_vendor_credit(vendor_credit)` (phase 2 if AP workflow enabled)
- `post_vendor_refund(vendor_refund)` (phase 2)

Idempotency:
- Mirror current approach: check for existing `JournalEntry` by `(source_content_type, source_object_id, description contains “…”)`.
- For allocation-generated postings (deposit apply/refund), use `JournalEntry.allocation_operation_id` for true idempotency.

---

## 9) API Surface (Option B JSON)

Design goals:
- Minimal endpoints that map directly to UI actions.
- Deterministic server-side validation.
- Clear error messages for over-allocation / invalid transitions.

### 9.1 Customer APIs

- `GET /api/reversals/customers/<customer_id>/summary/`
  - totals: open AR, open credits, deposit balance, last activity
- `GET /api/reversals/customers/<customer_id>/credit-memos/`
- `POST /api/reversals/customer-credit-memos/` (create draft)
- `POST /api/reversals/customer-credit-memos/<id>/post/`
- `POST /api/reversals/customer-credit-memos/<id>/void/`
- `POST /api/reversals/customer-credit-memos/<id>/allocate/`
  - payload: `{ allocations: [{ invoice_id, amount }] }`

- `GET /api/reversals/customers/<customer_id>/deposits/`
- `POST /api/reversals/customer-deposits/` (create+post)
- `POST /api/reversals/customer-deposits/<id>/apply/`
  - payload: `{ allocations: [{ invoice_id, amount }] }`

- `GET /api/reversals/customers/<customer_id>/refunds/`
- `POST /api/reversals/customer-refunds/` (create+post)

### 9.2 Vendor APIs (Phase 2+ recommended)

- `GET /api/reversals/suppliers/<supplier_id>/summary/`
- `GET /api/reversals/suppliers/<supplier_id>/vendor-credits/`
- `POST /api/reversals/vendor-credits/`
- `POST /api/reversals/vendor-credits/<id>/post/`
- `POST /api/reversals/vendor-credits/<id>/allocate/` (apply to bills)
- `GET /api/reversals/suppliers/<supplier_id>/vendor-refunds/`
- `POST /api/reversals/vendor-refunds/`

### 9.3 Tax drilldowns (nice-to-have v1)

Extend `core/views_tax_documents.py` + React drilldown component to support:
- `customer_credit_memo`
- `vendor_credit`
- (optionally) deposit and refund (usually no tax)

---

## 10) UI Plan (React)

### 10.1 Customers page (`frontend/src/customers/CustomersPage.tsx`)

Add:
- Summary widgets:
  - Open AR
  - Open credits (credit memos available)
  - Deposit balance
- “Credits & Refunds” section (either a new tab or inside Overview):
  - Pending Credits (Phase 2)
  - Credit Memos table:
    - status (Draft/Posted/Applied/Voided)
    - amount, available amount
    - linked invoices (from allocations)
  - Refunds table:
    - posting date, amount, bank account, status

Actions:
- “Issue credit memo” modal:
  - choose invoice (optional but recommended)
  - amount (net or gross, v1 choose one and derive)
  - posting date
  - notes
- “Apply credit” modal:
  - select credit memo
  - allocate to one or more invoices
- “Record refund” modal:
  - choose bank account
  - choose source (credit memo or deposit)

Implementation hooks:
- `frontend/src/customers/useCustomerReversals.ts` (fetch summary + tables)
- `frontend/src/customers/useAllocate.ts` (apply allocations; handle validation errors)

### 10.2 Suppliers page (`frontend/src/suppliers/SuppliersPage.tsx`)

Phase 2:
- Refactor to match the Customers Apple-style layout (split list + detail).
- Add vendor credits/refunds tables and allocation UI (mirror customer experience).

---

## 11) Incremental Delivery Plan

### Phase 1 (Customer credit memos + tax correctness)

1. Add `reversals` app models:
   - `CustomerCreditMemo`, `CustomerDeposit`, `CustomerRefund`, `Allocation`
2. Implement posting services for credit memo + deposit + refund.
3. Implement Tax DNA inheritance (copy/scale source invoice `TransactionLineTaxDetail`).
4. Harden tax engine + postings for signed tax details:
   - dust-sweeper sign handling
   - journal tax line helpers handle negative amounts
   - (recommended) `TransactionLineTaxDetail.document_side`
5. Add APIs for CustomersPage tables + actions.
6. Update CustomersPage UI to show credits/refunds + apply flows.

### Phase 2 (Payments + deposits fully integrated, vendor side)

1. Introduce true “cash receipt” flows:
   - record deposit vs direct invoice payment
2. Decouple invoice settlement state from GL cash postings (remove “Invoice paid” side effects).
3. Add vendor credits/refunds with a real AP workflow (new `Bill` model or extend `Expense` posting semantics carefully).

### Phase 3+ (polish and expansion)

- Multi-line invoices + line-level credits (true per-line DNA inheritance)
- Prior-period adjustment UX (jurisdiction-specific boxes)
- Inventory-aware returns
- Idempotency keys for all POST endpoints
- Audit trail surfaces (who posted/voided/applied)

---

## 12) Open Questions (Decide Before Coding)

1. **Invoice payment posting deprecation**: do we remove/disable `post_invoice_paid()` or gate it behind an explicit “cash payment” document?
2. **Contra accounts**: do we introduce `Sales Returns` (preferred) or debit `4010 Sales` directly (simpler)?
3. **Single vs multi-currency**: v1 can enforce “same currency only” for allocations; do we need FX now?
4. **Vendor side timing**: ship customer side first, or implement vendor credit/refund concurrently?

