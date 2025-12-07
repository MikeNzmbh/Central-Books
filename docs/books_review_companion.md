# Books Review Companion – Ops Notes

Ledger-wide, read-only review for a selected period. Surfaces risk, anomalies, and findings; never posts or edits data.

## Flow

1. POST `/api/agentic/books-review/run` with `period_start`/`period_end` creates a `BooksReviewRun` and triggers `run_books_review_workflow`.
2. Workflow loads posted journal entries for the business/period and runs checks:
   - Rule-based anomalies (large entries, adjustment patterns, possible duplicates).
   - If `ai_companion_enabled` is **on**: outlier detection vs average amounts + reflection pass (agent_retries).
3. Results include:
   - `metrics`: journals_total, journals_high_risk, journals_with_warnings, accounts_touched, agent_retries, trace_events.
   - `findings`: `{code, severity, message, references}` list.
   - `overall_risk_score` (0–100), `trace_id` for console debugging.
4. GET `/api/agentic/books-review/run/<id>` returns run metadata + findings. GET `/api/agentic/books-review/runs` lists recent runs.

## Toggle semantics

- **OFF (`ai_companion_enabled=False`)**: Only basic rule checks run; conservative scoring, no reflection retries.
- **ON (`ai_companion_enabled=True`)**: Adds richer heuristics (outlier checks vs averages) and a reflection pass; `agent_retries` increments when that pass runs.

## UI

- `/books-review` page lets users pick a period, run a review, view runs, and see findings. Risk badge and metrics per run; findings list with severity; “View in console” uses `trace_id` (`/agentic/console?trace=<trace_id>`).

## Debugging

- Use the run detail API or UI to inspect `findings` and `metrics`.
- Follow the trace via `trace_id` in the agent console to see workflow events and reflection passes.
