# LLM Safety & Token Usage (Companion v3)

- Deterministic first: anomaly detection, finance snapshot, tax guardian, radar, coverage, close-readiness run without LLM.
- HEAVY_REASONING (`deepseek-reasoner`) ONLY for:
  - High-Risk Critic (`audit_high_risk_transaction`).
  - Top anomaly explanations (max 3) via `apply_llm_explanations`.
  - Story generation (background, cached).
- LIGHT_CHAT (`deepseek-chat`) for:
  - Surface subtitles.
  - Optional Finance Companion narrative (opt-in via `finance_narrative=1`).
  - Optional Tax Guardian observer summary (on-demand):
    - CLI: `python manage.py tax_llm_enrich_period --business-id=... --period=...`
    - API: `POST /api/tax/periods/<period_key>/llm-enrich/` (throttled; snapshot must exist)
  - Issue refinement paths already in place.
- Guardrails:
  - All LLM calls go through `_invoke_llm` with timeouts and JSON stripping.
  - Invalid/timeout responses fall back to deterministic text; severity/task_code never change.
  - No auto-posting or balance movement is triggered by LLM output.
- Testing:
  - New unit tests mock LLM responses (anomaly explanations) and ensure graceful fallback when `llm_client` returns `None`.
