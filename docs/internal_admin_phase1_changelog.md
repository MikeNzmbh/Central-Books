# Central Admin Phase 1 Changelog

## Summary
Implemented Phase 1 of Central Admin architecture aligned with Gemini spec.

---

## New Models

### `AdminApprovalRequest`
Maker-Checker workflow for high-risk admin actions.

| Field | Description |
|-------|-------------|
| `initiator_admin` | Admin who created request (Maker) |
| `approver_admin` | Admin who approved/rejected (Checker) |
| `action_type` | Type: TAX_PERIOD_RESET, LEDGER_ADJUST, WORKSPACE_DELETE, etc. |
| `status` | PENDING, APPROVED, REJECTED, EXPIRED |
| `workspace` | Target workspace (optional) |
| `target_user` | Target user (optional) |
| `payload` | JSON action-specific data |
| `reason` | Justification for action |

### `AdminAuditLog` Enhancements
- `actor_role`: Captures admin role at time of action
- `user_agent`: Browser/client info

---

## New API Endpoints

### Workspace 360 "God View"
`GET /api/internal-admin/workspaces/<id>/overview/`

Returns aggregated data:
```json
{
  "workspace": { "id", "name", "created_at" },
  "owner": { "id", "email", "full_name" },
  "banking": { "account_count", "unreconciled_count", "accounts" },
  "ledger_health": { "unbalanced_entries", "orphan_accounts", "total_accounts" },
  "invoices": { "total", "draft", "sent", "paid" },
  "expenses": { "total", "uncategorized", "total_amount" },
  "tax": { "has_tax_guardian", "last_period", "open_anomalies" },
  "ai": { "last_monitor_run", "open_ai_flags" }
}
```

### Approvals (Maker-Checker)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/internal-admin/approvals/` | GET | List pending approvals |
| `/api/internal-admin/approvals/` | POST | Create request (Maker) |
| `/api/internal-admin/approvals/<id>/approve/` | POST | Approve (Checker) |
| `/api/internal-admin/approvals/<id>/reject/` | POST | Reject (Checker) |

---

## Files Changed

| File | Change |
|------|--------|
| `internal_admin/models.py` | Added `AdminApprovalRequest`, enhanced `AdminAuditLog` |
| `internal_admin/utils.py` | Enhanced `log_admin_action` with actor_role/user_agent |
| `internal_admin/approval_utils.py` | **NEW** - Maker-Checker workflow functions |
| `internal_admin/views.py` | Added `Workspace360View`, `AdminApprovalViewSet` |
| `internal_admin/urls.py` | Registered new endpoints |
| `internal_admin/migrations/0006_central_admin_phase1.py` | **NEW** migration |

---

## How to Use

### Workspace 360 Panel
Navigate to Workspaces section in internal admin, then access:
```
/api/internal-admin/workspaces/{workspace_id}/overview/
```

### Maker-Checker Workflow
```python
# Create approval request (Maker)
POST /api/internal-admin/approvals/
{
  "action_type": "TAX_PERIOD_RESET",
  "workspace_id": 123,
  "reason": "Customer requested reset",
  "payload": {"period_id": 456}
}

# Approve (Checker - different admin)
POST /api/internal-admin/approvals/{id}/approve/

# Or reject
POST /api/internal-admin/approvals/{id}/reject/
{ "reason": "Insufficient justification" }
```

---

## Not Yet Wired (Phase 3+)
- Actual execution of approved actions (approval marks as APPROVED but doesn't trigger downstream logic)
- AI kill switches and PII break-glass

---

## Phase 2 Additions

### Frontend Components

#### `Workspace360Section.tsx`
Unified "God View" for any workspace, displaying:
- Owner & plan info
- Banking: accounts, unreconciled count, last import
- Ledger health: unbalanced entries, orphan accounts
- Invoices: status breakdown (draft/sent/paid)
- Expenses: totals, uncategorized count
- Tax Guardian: status, anomaly counts
- Bank accounts table

#### `ApprovalsSection.tsx`
Maker-Checker workflow UI with:
- Pending approvals list
- Approve/Reject buttons
- Action type labels and status pills
- Request details (reason, payload, expiry)
- Role-based action visibility

### API Types & Functions (api.ts)
- `Workspace360` type with full interface
- `fetchWorkspace360(workspaceId)` function
- `ApprovalRequest`, `ApprovalList`, `ApprovalActionType`, `ApprovalStatus` types
- `fetchApprovals()` function
- `createApprovalRequest(data)` function
- `approveRequest(id)` function
- `rejectRequest(id, reason)` function

### Audit Logging
Already wired to key actions:
- `impersonation.created`, `impersonation.accepted`, `impersonation.stopped`
- `feature_flag.updated`
- `admin_invite.created`, `admin_invite.revoked`

