# Companion v2 Changelog (Dec 11, 2025)

- Canonical task catalog added in `core/companion_tasks.py` and documented in `docs/companion_tasks_catalog.md`; playbook steps now emit `task_code`/`requires_premium` aligned to R1/I1/B1… and close-readiness reasons are tagged (B1/G1/C1).
- Playbook labels now use canonical tasks for deterministic wording, and coverage fallbacks map to R2/I1/B1 with premium flags surfaced to the UI.
- Close-readiness messages include task codes plus structured `blocking_items` so downstream surfaces can explain blockers more clearly.
- High-risk Critic skeleton added: `audit_high_risk_transaction` (HEAVY_REASONING, threshold >$5k or bulk) with persisted `HighRiskAudit` records and reconciliation UI badge/copy for ok/warn/fail verdicts.
- Gap analysis snapshot captured in `docs/companion_v2_gap_analysis.md` to show pre-v2 state; catalog lives in `docs/companion_tasks_catalog.md`.

Tests/Build:
- `python3 manage.py test core.tests.test_companion_coverage core.tests.test_companion_issues_api core.tests.test_companion_radar core.tests.test_companion_story core.tests.test_high_risk_critic`
- `cd frontend && npm run build`
  (LLM calls log expected network failures in tests; no assertions depend on external APIs.)
