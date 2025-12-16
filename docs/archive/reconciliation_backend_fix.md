# Reconciliation backend fixes (Clover Books)

## What was broken
- All `/api/reconciliation/...` calls were returning HTTP 500, leaving the UI with empty dropdowns and “Everything is reconciled” despite real data.
- Currency lookups referenced a non-existent `bank_account.currency` field, causing crashes.
- No defensive handling for missing bank accounts/periods; empty data resulted in exceptions instead of empty payloads.

## Key changes
- Backend
  - `api_reconciliation_config` now safely returns reconcilable bank accounts (empty list when none).
  - New endpoints:
    - `api/reconciliation/periods/` → period options per bank account (empty list when no transactions).
    - `api/reconciliation/feed/` → grouped transactions and balances for a bank account + period, never 500; validates inputs.
  - Shared helpers for parsing periods and building period options from transaction months.
  - Session/feed responses use the business currency to avoid attribute errors.
- Frontend
  - Reconciliation page now loads accounts → periods → feed using the new endpoints.
  - Shows clear empty states and retry handling; disables selectors appropriately.
  - Mount event hides server-side fallback shell.
- Tests
  - Added coverage for config no-accounts, periods empty, feed empty, and feed with one transaction.

## API contracts
- `GET /api/reconciliation/config/` → list of `{id, name, currency, bankLabel, isDefault}`; returns `[]` if none (or `{accounts: [...]}` when `include_meta=1`).
- `GET /api/reconciliation/periods/?bank_account_id=` → `{"bank_account_id": "...", "periods": []}`
- `GET /api/reconciliation/feed/?bank_account_id=&period_id=YYYY-MM` → `{"bank_account": {...}, "period": {...}, "periods": [...], "session": {...}, "transactions": {"new":[],"suggested":[],"matched":[],"partial":[],"excluded":[]}}`

## How to reproduce the fixed flow
1. Open Banking → Reconciliation.
2. Bank dropdown loads reconcilable bank accounts (empty state if none).
3. Selecting a bank loads periods; selecting a period loads the feed.
4. Feed shows grouped transactions for the selected month; no HTTP 500s.

## Files touched
- Backend: `core/views_reconciliation.py`, `core/urls.py`
- Frontend: `frontend/src/reconciliation/ReconciliationPage.tsx`, `frontend/src/reconciliation/reconciliation-entry.tsx`, `templates/reconciliation/reconciliation_page.html`
- Tests: `core/tests/test_reconciliation_api.py`
- Docs: `docs/reconciliation_backend_fix.md`
