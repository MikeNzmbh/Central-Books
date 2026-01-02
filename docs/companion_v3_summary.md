# Companion v3 Summary

What changed
- Anomaly Detection: Books/Bank review endpoints now emit structured anomalies (code, severity, impact_area, task_code) with optional HEAVY_REASONING explanations. Rules cover unreconciled bank aging, suspense balances, unbalanced entries, retained earnings rollforward, AR aging, and tax balance sanity.
- Finance Companion: `/api/agentic/companion/summary` adds `finance_snapshot` (cash/runway, revenue/expense trends, AR aging) with optional LIGHT_CHAT one-liner narrative.
- Tax Guardian: Deterministic tax checks (negative tax payable/receivable) exposed via `tax_guardian` in summary.
- Task Catalog: Expanded canonical tasks (overdue invoice chase, retained earnings validation, tax tie-out) in `core/companion_tasks.py` and docs.
- Frontend: Companion overview shows Finance Companion + Tax Guardian cards; Books Review page shows anomalies with AI/auto badges.
- Safety: HEAVY_REASONING limited to critic, anomaly explanations, and story; LIGHT_CHAT for light narratives; deterministic fallbacks everywhere.

Deterministic Tax Guardian v1
- Seeded CA/US jurisdictions, linked tax components, and expanded anomalies (rate mismatch, missing tax, rounding, exempt taxed, negative net).
- Tax radar axis + close-readiness blocker hook into TaxAnomaly (no LLM); playbook steps map anomaly codes to T1–T3 tasks.
- Companion summary now returns a `tax` block (snapshot net tax + anomaly counts) powering the Tax Guardian UI; still deterministic-only.

Positioning vs Intuit Assist
- Control Tower view now couples anomaly detection, finance snapshot, and tax guardrails tailored to micro-SMBs, keeping LLMs optional and bounded while surfacing clear task-mapped actions.
