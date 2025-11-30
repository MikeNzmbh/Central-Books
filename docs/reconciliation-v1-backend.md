Reconciliation V1 Backend
=========================

Domain model
------------
- `BankAccount` (with optional linked `Account`) drives which ledger account and bank feed to use.
- `BankTransaction` holds imported bank lines. Statuses are simplified to `new/matched/partial/excluded` in the API; underlying model values are preserved.
- `ReconciliationSession` represents a statement period (`statement_start_date`, `statement_end_date`, `opening_balance`, `closing_balance`, `status`).
- `BankReconciliationMatch` links a bank transaction to a `JournalEntry` when matched.
- `JournalEntry`/`JournalLine` provide the ledger side. Balances are derived from lines on the linked bank ledger account.

API surface
-----------
All endpoints return JSON with clean 4xx errors instead of 500s.

- `GET /api/reconciliation/accounts/`
  - Returns active bank accounts: `[{"id": 1, "name": "...", "currency": "USD"}]`.
- `GET /api/reconciliation/accounts/<account_id>/periods/`
  - Monthly buckets from bank transaction dates; falls back to the current month: `[{id: "2024-05", start_date: "...", end_date: "...", is_locked: false}]`.
- `GET /api/reconciliation/session/?account=<id>&start=<YYYY-MM-DD>&end=<YYYY-MM-DD>`
  - Creates/loads the session for the period and returns `{session, feed, bank_account, period, periods}`.
  - `session` keys: `id`, `bank_account`, `period_start`, `period_end`, `opening_balance`, `statement_ending_balance`, `ledger_ending_balance`, `difference`, `status`, `reconciled_percent`, `total_transactions`, `unreconciled_count`.
  - `feed` buckets: `new`, `matched`, `partial`, `excluded`; each item includes `id`, `date`, `description`, `amount`, `currency`, `status`, `includedInSession`.
- `POST /api/reconciliation/session/<id>/set_statement_balance/`
  - Body: `{"statement_ending_balance": "123.45"}` (optional `opening_balance`).
  - Returns refreshed session + feed.
- `POST /api/reconciliation/session/<id>/match/`
  - Body: `{"transaction_id": <bank_tx_id>, "journal_entry_id": <optional je id>}`.
  - If no `journal_entry_id` is provided, the backend attempts an auto-match on the bank ledger account (amount/date window).
- `POST /api/reconciliation/session/<id>/unmatch/`
  - Body: `{"transaction_id": <bank_tx_id>}`. Clears matches and resets statuses.
- `POST /api/reconciliation/session/<id>/exclude/`
  - Body: `{"transaction_id": <bank_tx_id>, "excluded": true|false}`. Marks/unmarks a line as excluded.
- `POST /api/reconciliation/session/<id>/complete/`
  - Completes the period when the difference is within $0.01; otherwise returns 400.

Balance rules
-------------
- `opening_balance`: ledger balance for the linked bank account as of the day before `period_start`.
- `ledger_ending_balance`: ledger balance as of `period_end`.
- `statement_ending_balance`: stored in `ReconciliationSession.closing_balance`; seeded to the ledger ending balance on first creation.
- `difference = statement_ending_balance - ledger_ending_balance` (quantized to 2 decimals).
- Progress metrics count `matched + excluded` as reconciled; `new + partial` remain unreconciled.

Limitations & assumptions
-------------------------
- Matching is 1:1 in V1; split/complex matching is not exposed via the API.
- Auto-match only considers journal lines on the bank ledger account within the ReconciliationEngine date/amount tolerance.
- Excluding a bank line does not change ledger balances; it simply removes the line from the active feed.
- Periods are monthly only; when no transactions exist, a synthetic current-month period is returned.
- If a bank account has no linked ledger account, balances default to 0.00 but the endpoints remain usable.
