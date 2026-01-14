# Central Admin Phase 1 Architecture

## 1. Gemini Spec Summary

The Central Admin strategic spec outlines a **sovereign control plane** for Central Books. Key principles:

### 1.1 Hexagonal Architecture
- Admin actions go through domain APIs, never raw DB manipulation
- Admin API is a superset of User API with privileged methods
- Same validation chains as user actions (balance checks, audit trails, lock periods)

### 1.2 Log-First / Event-Driven
- Every action is an event in a unified stream
- "Time travel" debugging capability
- Admin view = user view + diagnostic overlays

### 1.3 Safety Primitives
- **Maker-Checker**: Dual approval for high-risk actions
- **Immutable Audit Trails**: Every action logged to tamper-proof storage
- **PII Masking**: Default masking with "break glass" reveal
- **AI Kill Switches**: Global and scoped agent halts

---

## 2. Current → Spec Domain Mapping

| Current Module | Gemini Spec Domain | Status |
|----------------|-------------------|--------|
| Overview metrics | Customer/Workspace 360 (partial) | ✅ Exists |
| Users + Workspaces | Customer 360 core | ✅ Exists |
| Banking section | Bank Feed Debugger (partial) | ✅ Exists |
| Reconciliation metrics | Ledger Repair Workbench (read-only) | ✅ Exists |
| Ledger health | Ledger Repair Workbench (read-only) | ✅ Exists |
| Invoices/Expenses audit | Ledger observability | ✅ Exists |
| Feature flags | Feature Flag Manager | ✅ Exists |
| AI monitoring | AI Observability (basic) | ✅ Exists |
| Audit & logs | Immutable Audit Trail | ✅ Exists |
| Support tickets | Support Context | ✅ Exists |
| Impersonation | "Login As" with safety | ✅ Exists |
| — | Maker-Checker workflow | ❌ Missing |
| — | Workspace 360 unified view | ❌ Missing |
| — | Tax debug console | ❌ Missing |
| — | Bank sync history/debug | ❌ Missing |
| — | AdminApprovalRequest model | ❌ Missing |

---

## 3. Phase 1 Scope

### 3.1 Event/Audit Logging Enhancement
**Goal**: Align with "log-first" spec  
**Changes**:
- Extend `AdminAuditLog` with `actor_role`, `user_agent` fields
- Enhance `log_admin_action` helper with role capture
- Wire to key actions: impersonation, flag changes, invites, deactivation

### 3.2 Workspace 360 Panel
**Goal**: "God View lite" – single pane of glass  
**New Endpoint**: `GET /api/internal-admin/workspaces/<id>/overview/`  
**Aggregates**:
- Owner & plan info
- Banking: accounts, last sync, unreconciled count
- Ledger health: unbalanced entries, orphan accounts
- Invoices: status breakdown, issues
- Expenses: totals, uncategorized
- Tax: guardian status, anomaly counts
- AI: monitoring summary

### 3.3 Maker-Checker Skeleton
**Goal**: Foundation for dual approval workflows  
**New Model**: `AdminApprovalRequest`  
**Fields**: initiator, approver, status, action_type, payload, reason  
**Actions**: create, approve, reject  
**Initial Types**: `TAX_PERIOD_RESET`, `LEDGER_ADJUST` (not wired yet)

### 3.4 Tax/Bank Debug Surfaces
**Goal**: Read-only debug visibility  
**Tax**: Show guardian status, last period, anomaly counts  
**Bank**: Show sync history (last N attempts, status, errors)

---

## 4. Non-Goals (Phase 1)

- Full Ledger Repair Workbench with AJE UI
- CQRS/Kafka/gRPC infrastructure
- AI kill switches
- PII break-glass mechanism
- Full Maker-Checker wiring to all actions
