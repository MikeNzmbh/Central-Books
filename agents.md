# Agentic Accounting OS: Agents & Communication

This document describes the current agentic stack in Clover Books (Rust-first) and how agent output is represented, queued, and surfaced in the Control Tower.

---

## System Map

- Companion Autonomy Engine (CAE): Generates work items and recommendations, persists them, and materializes queue snapshots for the Control Tower.
- Companion Core: Deterministic issues, audits, and radar endpoints used by the UI.
- Agentic Surfaces: Receipts/invoices are stored in agentic document tables and reflected as CAE work items; companion summary/issues read from CAE + document runs.

---

## CAE Agent Roster

Risk is assigned per work item (amount-based) rather than per agent.

| Agent | Focus | Inputs | Primary Outputs |
| :--- | :--- | :--- | :--- |
| **OrchestratorAgent** | Aggregates reconciliation + categorization results and emits a summary signal | Agent outputs | Merged `AgentOutput` with `orchestrator_summary` signal |
| **ReconciliationAgent** | Finds unmatched bank transactions | `core_banktransaction` with `status = 'NEW'` | `match_bank` work items + evidence refs |
| **CategorizationAgent** | Finds uncategorized bank transactions | `core_banktransaction` with `category_id IS NULL` | `categorize_tx` work items + evidence refs |

Narrative card generation happens in the scheduler via the narrative builder (not a standalone `AgentName`), producing customer-safe rationale cards per work item.

---

## Communication Model (CAE Records)

Work flows through persisted records (no message bus). Core record types:

- WorkItem: queueable unit with `work_type`, `surface`, `status`, `risk_level`, `requires_approval`, and structured `inputs`/`state`.
- ActionRecommendation: proposed `apply` or `review` action with `preview_effects`; status transitions `proposed -> applied/dismissed`.
- ApprovalRequest: `pending`, `approved`, or `rejected`; can require a reason before action is taken.
- RationaleCard: structured `sections` plus `customer_safe_text` for UI explainability.
- Claim + Evidence: internal audit trail; evidence links use `internal://` references.
- AgentRun + Job: execution tracking for engine runs and per-agent jobs.
- ToolCall: LLM or fetch usage with budget, allowlist, and cost metadata.
- CircuitBreakerEvent: budget or velocity trip events used to compute trust and engine mode.
- QueueSnapshot / Snapshot: materialized queue state for the Control Tower.
- AuditLog: system and user actions recorded for traceability.

Agent output shape: `AgentOutput { signals, recommendations, evidence_refs, work_items }`.

---

## Lifecycle

1. Engine tick runs reconciliation and categorization per tenant.
2. Agents emit work item seeds plus signals and evidence refs.
3. Scheduler upserts work items, assigns default recommendations, and generates rationale cards.
4. High-risk items move to `waiting_approval` and can create approval requests.
5. Actions are applied individually or via batch apply; audit logs capture outcomes.
6. Materialize snapshots for Control Tower queues and status endpoints.

---

## Risk, Policy, and Safety Controls

- Risk tiers are amount-based defaults: `>= 5000` high, `>= 1000` medium, else low; `None` defaults to medium.
- Approval threshold: `ENGINE_APPROVAL_AMOUNT_THRESHOLD` (default `1000`).
- Engine modes: `suggest_only`, `drafts`, `autopilot_limited`, derived from trust score and breaker activity.
- Budgets: `ENGINE_BUDGET_TOKENS_PER_DAY`, `ENGINE_BUDGET_TOOL_CALLS_PER_DAY`, `ENGINE_BUDGET_RUNS_PER_DAY`.
- Allowlists: `ENGINE_LLM_ALLOWED_MODELS`, `ENGINE_ALLOWLIST_DOMAINS`.
- Mock toggles: `LLM_MODE`, `TOOL_MODE`.
- Customer-safe copy normalizes internal terms before surfacing text in the UI.

---

## APIs and Surfaces (Current)

- CAE: `/api/companion/autonomy/*`, `/api/companion/cockpit/*`
- Companion core: `/api/companion/issues`, `/api/companion/audits`, `/api/companion/radar`
- Agentic stubs: `/api/agentic/receipts/*`, `/api/agentic/invoices/*`, `/api/agentic/companion/*`

---

## Current Scope and Gaps

- CAE agents only cover banking work items (unmatched and uncategorized transactions).
- ToolGateway defaults to a stub provider unless a real LLM provider is wired in.
- Agentic receipts/invoices + companion summary/issues are wired to Rust tables and CAE, but extraction/classification is still heuristic until a real LLM provider is wired.
- Provenance and integrity report endpoints are still not implemented on the Rust side.

---

## Roadmap (Near-Term)

- Implement a real LLM provider in ToolGateway with allowlist + budget enforcement.
- Replace agentic receipts/invoices stubs with a real extraction pipeline or bridge the legacy flow.
- Expand CAE to additional surfaces (receipts, invoices, books review) and unify Control Tower data sources.
- Add regression evaluation fixtures for agent outputs and rationale cards.
