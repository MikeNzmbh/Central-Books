# Anomaly Detection (Companion v3)

Scope: Micro-SMBs, deterministic-first with optional DeepSeek overlays. Endpoints remain `/api/agentic/books-review/*` and `/api/agentic/bank-review/*` but responses now include `anomalies`.

## Surfaces & Impact Areas
- Reconciliation: unreconciled bank aging, suspense balances.
- P&L: unbalanced entries, retained earnings rollforward checks.
- AR: overdue buckets (30/60/90+).
- Tax: negative tax payable/receivable and tax balance sanity checks.

## Response Shape
Each run response now includes:
```json
{
  "anomalies": [
    {
      "code": "BANK_UNRECONCILED_AGING",
      "surface": "bank",
      "impact_area": "reconciliation",
      "severity": "medium|high",
      "explanation": "string",
      "task_code": "B1",
      "explanation_source": "auto|ai",
      "linked_issue_id": null
    }
  ]
}
```

## Deterministic Rules (examples)
- Bank: unreconciled transactions >14 days old, severity escalated by count.
- Books: suspense/clearing balances; unbalanced entries; retained earnings rollforward mismatch.
- AR: overdue invoices (30/60/90+).
- Tax: negative tax payable/receivable.

## LLM Overlay (token-limited)
- Top anomalies (max 3) may receive HEAVY_REASONING short explanations (`explanation_source="ai"`).
- Never alters severity or task_code; no auto-posting.
