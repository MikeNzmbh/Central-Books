# AI Companion Overview Dashboard

Purpose: give a single pane over all AI Companion surfaces (receipts, invoices, books review, bank review) so founders/bookkeepers can see health and risk at a glance.

## Data sources
- Aggregates run models: `ReceiptRun`, `InvoiceRun`, `BooksReviewRun`, `BankReviewRun`.
- API: `GET /api/agentic/companion/summary`
  - Includes `ai_companion_enabled`
  - Per-surface recent runs + 30-day totals
  - Global section: last Books Review (risk + trace_id), high-risk item counts, agent_retries_30d.

## UI
- Page at `/ai-companion` (sidebar “AI Companion”):
  - Banner showing if `ai_companion_enabled` is ON/OFF (link to settings when OFF).
  - Global cards: last Books Review risk/period (console link via `trace_id`), last 30-day high-risk counts and agent retries.
  - Tiles for Receipts, Invoices, Books Review, Bank Review:
    - Latest run date, risk badge, key metrics.
    - “View details” links to their respective pages.

## Debugging
- Use the summary API to verify counts.
- For detailed traces, follow the surface links; trace_id links land in `/agentic/console?trace=<trace_id>`.
