# Companion v2 Runbook (Ops / Support)

This runbook describes safe operations for Companion v2 under `docs/COMPANION_BLUEPRINT.md`.

## 1) Safety Model (Quick Reminder)

- **Canonical Ledger (Stream A)** is immutable financial truth.
- **Shadow Ledger (Stream B)** holds Companion proposals/drafts only and is wipeable.
- Promotion from Shadow → Canonical happens only via **Apply\*** commands executed by deterministic backend handlers and gated by:
  - RBAC
  - period locks
  - deterministic validation (sum-of-splits, account types, etc.)
  - kill switch + circuit breakers

## 2) Enable/Disable Companion

Companion is gated by **three** switches (all must allow):

1) **Global kill switch**
- Setting: `COMPANION_AI_GLOBAL_ENABLED` (Django settings)
- If `False`, all propose/apply endpoints return a 403-style error.

2) **Workspace feature flag**
- Field: `core.Business.ai_companion_enabled`
- If `False`, Companion is disabled for that workspace.

3) **Per-workspace AI settings**
- Model: `companion.WorkspaceAISettings`
- Key fields:
  - `ai_enabled` (boolean)
  - `kill_switch` (boolean; overrides `ai_enabled`)
  - `ai_mode`: `shadow_only | suggest_only | drafts | autopilot_limited`

### Recommended operational modes

- **`shadow_only`**: proposals only; no apply/promote.
- **`suggest_only`**: human-triggered apply allowed; no autopilot.
- **`drafts`**: human-triggered apply allowed; batching UX can be added.
- **`autopilot_limited`**: not enabled by default; requires additional governance and monitoring.

## 3) Review Proposals (Shadow Ledger)

### UI
- Navigate to `Companion v2 → Shadow Ledger Proposals` (route: `/ai-companion/proposals`).
- The page lists **proposed** shadow events and shows:
  - transaction description/date/amount (when linked to a bank transaction)
  - proposed split(s)
  - confidence + rationale
  - questions / risk reasons (if present)

### API
- List proposals:
  - `GET /api/companion/v2/proposals/?workspace_id=<id>`
- Inspect a specific shadow event:
  - `GET /api/companion/v2/shadow-events/<shadow_event_id>/`

## 4) Apply / Reject Proposals

### Reject
- UI: click **Reject** on a proposal.
- API:
  - `POST /api/companion/v2/proposals/<id>/reject/` with body `{ "workspace_id": <id>, "reason": "…" }`

### Apply (Promote to Canonical)

**Preconditions**
- Workspace AI mode must allow apply (`suggest_only`, `drafts`, or `autopilot_limited`).
- The workspace must not be kill-switched (`kill_switch=false`, `ai_enabled=true`, `ai_companion_enabled=true`, global enabled).
- The transaction date must not fall in a locked/closed period (period lock rules).
- The user must have RBAC permission `companion.actions` (typically OWNER/CONTROLLER/BOOKKEEPER).

**Important**
- In `shadow_only`, apply is blocked by design (Tier 0 simulation mode).

**UI**
- If apply is disabled due to `shadow_only`, the proposals page shows a warning and can prompt workspace managers to switch modes.

**API**
- Apply a proposal:
  - `POST /api/companion/v2/proposals/<id>/apply/` with body `{ "workspace_id": <id> }`
- Provenance lookup (“why did Companion do this?”):
  - `GET /api/companion/v2/provenance/?shadow_event_id=<shadow_event_id>`

## 5) Circuit Breakers (Responding to Trips)

Circuit breakers are recorded in `companion.AICircuitBreakerEvent`.

### Velocity breaker
- Trigger: too many Companion commands in a minute.
- Symptom: propose/apply endpoints start returning 403 errors with “Velocity circuit breaker tripped.”
- Response:
  - verify no runaway job/loop is calling propose endpoints
  - temporarily set `WorkspaceAISettings.ai_enabled=false` or `kill_switch=true`
  - investigate recent `AICommandRecord` rows to identify the caller

### Value breaker
- Trigger: transaction amount ≥ `WorkspaceAISettings.value_breaker_threshold`
- Behavior:
  - proposal is still created
  - proposal metadata should reflect forced review (`tier` raised; `risk_reasons` includes value breaker)
- Response:
  - ensure UI presents these as high-friction review items
  - do not enable autopilot behaviors for these

### Trust breaker (if enabled)
- Trigger: high rejection rate.
- Response:
  - downgrade workspace mode (e.g., from `autopilot_limited` → `suggest_only`)
  - review rejected items and update BusinessPolicy/rules as needed

## 6) Auditor (“Checker”) / Integrity Reports

Companion runs a rules-first auditor job that scans canonical entries linked via provenance and writes `AIIntegrityReport`.

- Generate reports (management command):
  - `python manage.py companion_run_auditor --workspace-id <id> --days 7`
- Fetch reports:
  - `GET /api/companion/v2/integrity-reports/` (workspace-scoped)

## 7) Clearing Shadow Ledger

Use with care; clearing Shadow events does not affect Canonical.

- API:
  - `POST /api/companion/v2/shadow-events/wipe/?status=proposed`
- Requires RBAC permission `companion.shadow.wipe`.

