# Companion v2 Gap Analysis

Date: 2025-12-11

Note: This snapshot reflects the state before the v2 changes in this branch; gaps listed here are addressed in the implementation that follows.

## Radar, Coverage, Close-Readiness, Playbook
- Radar: `core/companion_issues.build_companion_radar` (deterministic; scores per surface) is called from `core/views_companion.api_companion_summary`.
- Coverage: `core/companion_issues.build_companion_coverage` (receipts/invoices/banking only) is also wired into `api_companion_summary`.
- Close-readiness: `core/companion_issues.evaluate_period_close_readiness` (thresholded unreconciled bank items + suspense balance + open high issues) is invoked in `api_companion_summary`.
- Playbook: `core/companion_issues.build_companion_playbook` builds steps from ranked `CompanionIssue` rows, then adds a coverage filler if room; `api_companion_summary` surfaces it to the UI.

## How Playbook Labels Are Formed Today
- Label builder lives in `core/companion_issues._build_action_label`. It inspects `issue.surface`, `issue.data`, and `issue.title` to craft strings such as “Reconcile 9 unmatched bank transactions” or falls back to `issue.title`. There is no canonical task mapping; labels vary by issue payload.

## DeepSeek Call Sites
- Books Review: `core/llm_reasoning.reason_about_books_review` (profile `LLMProfile.LIGHT_CHAT`) is called from the books review workflow (`core/agentic_books_review` via view `core/views_books_review.py`).
- Bank Review: `core/llm_reasoning.reason_about_bank_review` (profile `LLMProfile.LIGHT_CHAT`) is invoked by `core/agentic_bank_review.run_bank_reconciliation_workflow`, which is triggered from `core/views_bank_review.api_bank_review_run`.
- Companion Story: `core/llm_reasoning.generate_companion_story` (profile `LLMProfile.LIGHT_CHAT`, short timeout) is only executed in background via `core/companion_story.regenerate_companion_story`; `api_companion_summary` fetches cached output only.
- Surface Subtitles: `core/llm_reasoning.generate_surface_subtitles` (profile `LLMProfile.LIGHT_CHAT`) runs inside `api_companion_summary` when `business.ai_companion_enabled` is true; deterministic subtitle fallback is used otherwise.
- Other DeepSeek usage: `companion/llm.generate_companion_narrative` uses `LLMProfile.HEAVY_REASONING` for dashboard narratives but is separate from the Companion summary API.

## Notable Gaps vs. Requested Spec
- No canonical task catalog: playbook/close-readiness labels are issue-driven and not tied to the R1/I1/B1… task set.
- No high-risk “Critic” path: transactions >$5k are not audited by a generator+critic flow; existing bank review only scores risk heuristically and may auto-create matches without a second AI audit.
- High-risk thresholds differ: companion issue severity heuristics flag items around ~$1k, not the >$5k threshold in the new spec.
- Premium task handling absent: revenue recognition (I2) or bulk adjustments are not flagged as premium/coming-soon anywhere.
- Coverage omits books/tax surfaces; close-readiness messages do not reference canonical tasks (B1/G1/C1/C2).
- Subtitles and story already use DeepSeek as planned, but story/subtitles both use the LIGHT_CHAT profile; heavy reasoning is not reserved for high-stakes checks.
