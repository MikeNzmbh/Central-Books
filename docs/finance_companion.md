# Finance Companion (Deterministic Snapshot)

Endpoint: `/api/agentic/companion/summary` now includes `finance_snapshot`.

## Data (no LLM required)
- Cash health: ending cash (bank balances), approx monthly burn (last 90d bank tx), runway months.
- Revenue/expense trend: last 6 months from GL income/expense lines.
- AR health: aging buckets (current, 30/60/90/120) from invoices; total overdue.

## Optional Narrative
- Opt-in via `finance_narrative=1` query param when AI Companion is enabled.
- Uses `deepseek-chat` (LIGHT_CHAT) for a single-sentence summary, token-light, never blocking.

## Frontend
- Companion Overview shows a small Finance Companion card with cash, runway, AR overdue, and an ✨ badge when the narrative is AI-generated.
