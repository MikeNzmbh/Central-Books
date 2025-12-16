# Tax Guardian (Deterministic, Free)

Purpose: Lightweight, deterministic sales tax/GST/HST checks for Canada/US micro-SMBs.

## Checks (period = current month unless specified)
- Deterministic anomalies (no LLM):
  - `T1_RATE_MISMATCH` – applied rate differs from configured rate.
  - `T3_MISSING_TAX` – registered business with taxable sales but no tax collected.
  - `T4_ROUNDING_ANOMALY` – document tax_total differs from summed line tax by > $0.02.
  - `T5_EXEMPT_TAXED` – EXEMPT/ZERO-RATED product rule but tax applied.
  - `T6_NEGATIVE_BALANCE` – net tax negative beyond tolerance.
- Surfaced via TaxAnomaly records (OPEN only) and exposed in `/api/agentic/companion/summary`:
```json
{
  "tax": {
    "period_key": "2025-04",
    "has_snapshot": true,
    "net_tax": 110.0,
    "jurisdictions": [
      {"code": "CA-ON", "taxable_sales": 1000.0, "tax_collected": 130.0, "tax_on_purchases": 20.0, "net_tax": 110.0}
    ],
    "anomaly_counts": {"low": 0, "medium": 1, "high": 1},
    "anomalies": [
      {"code": "T4_ROUNDING_ANOMALY", "severity": "medium", "description": "...", "task_code": "T3"}
    ]
  },
  "tax_guardian": {
    "status": "all_clear" | "issues",
    "issues": [
      {"code": "T4_ROUNDING_ANOMALY", "severity": "medium", "description": "...", "task_code": "T3"}
    ]
  }
}
```

## UI
- Companion Overview shows “Tax Guardian” with net tax + anomaly badges; issues map to task codes for playbook/close alignment.

## Tax Payments, Remaining Balance & Status Semantics

Tax Guardian tracks real-world settlement activity against each period via `TaxPayment`.

- `TaxPayment.bank_account`: optional link to the originating cash/bank account for reconciliation.
- `TaxPayment.kind` is explicit:
  - `PAYMENT` = money paid **to** the tax authority
  - `REFUND` = money received **from** the tax authority
- `TaxPayment.amount` is always **positive** (direction comes from `kind`).
- API totals:
  - `payments_payment_total` = sum of `PAYMENT.amount`
  - `payments_refund_total` = sum of `REFUND.amount`
  - `payments_total` (legacy) / `payments_net_total` = `payments_payment_total - payments_refund_total` (signed net settlement)
- `remaining_balance` (API field) is computed deterministically as:
  - `remaining_balance = net_tax - payments_total` (i.e., subtract the signed net settlement)
  - `> 0` means the business still owes tax
  - `< 0` means the authority still owes the business (refund/credit)

`payment_status` is derived with a small tolerance (~$0.01):

- `NO_LIABILITY` — `|net_tax|` is within tolerance of $0.
- For liabilities (`net_tax > 0`):
  - `UNPAID`, `PARTIALLY_PAID`, `PAID`, `OVERPAID`
- For refunds (`net_tax < 0`):
  - `REFUND_DUE`, `REFUND_PARTIALLY_RECEIVED`, `REFUND_RECEIVED`, `REFUND_OVERRECEIVED`

### Reset / Unfile behaviour

`POST /api/tax/periods/<period_key>/reset/` reopens a filed period for recomputation but **does not delete** existing `TaxPayment` rows. If a recompute changes `net_tax`, the UI will reflect this via `remaining_balance` and (where applicable) `OVERPAID` / `REFUND_OVERRECEIVED`.

### Duplicate submissions

The payments API does not currently implement idempotency keys; clients should avoid double-submitting (e.g., disable the save button while requests are in-flight).

## LLM
- No LLM required; optional LIGHT_CHAT explanations can be added later without changing the deterministic result.
