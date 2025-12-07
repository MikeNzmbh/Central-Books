# Bank Review Companion – Ops Notes

Read-only reconciliation companion that reviews bank lines against the ledger to surface unmatched or risky transactions.

## Flow

1. POST `/api/agentic/bank-review/run` with `lines` (JSON array of `{date, description, amount, external_id?}`) and optional `period_start`/`period_end`.
2. `BankReviewRun` is created and `run_bank_reconciliation_workflow` executes:
   - Attempts matching bank lines to journal entries (exact date/amount; companion adds fuzzy description matching).
   - Classifies each line (`MATCHED`, `UNMATCHED`, `PARTIAL_MATCH`, `DUPLICATE`).
   - Emits `audit_flags`, `audit_score`, `audit_explanations`, `matched_journal_ids`.
3. Results persisted on `BankTransactionReview` rows; run gets `metrics`, `overall_risk_score`, and `trace_id`.
4. GET `/api/agentic/bank-review/runs` lists runs; GET `/api/agentic/bank-review/run/<id>` returns metrics + per-line findings. UI at `/bank-review` shows runs, metrics, line-level risk, and “View in console” via `trace_id` (`/agentic/console?trace=<trace_id>`).

## Toggle semantics

- **OFF (`ai_companion_enabled=False`)**: Basic rule-based matching (exact date/amount), unmatched flagged, risk scored conservatively.
- **ON (`ai_companion_enabled=True`)**: Adds fuzzy/heuristic matching on descriptions, reflection pass when unmatched/flagged, increments `agent_retries`, richer explanations.

## Metrics & risk

- Run metrics: `transactions_total`, `transactions_reconciled`, `transactions_unreconciled`, `transactions_high_risk`, `agent_retries`.
- Per line: `audit_flags`, `audit_score`, `audit_explanations`, `status`, `matched_journal_ids`.
- `overall_risk_score` (0–100) and derived risk badges in UI.

## Debugging

- Inspect run detail API/UI for line-level flags and scores.
- Follow `trace_id` in the agent console to see matching attempts and reflection events.
