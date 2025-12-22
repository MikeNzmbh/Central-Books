# Admin Control Coverage Audit

**Date:** 2025-12-16  
**Scope:** Central Books / CERN Books Django + React monorepo

---

## Section 1: Inventory

### Backend API Endpoints Coverage

| Domain | View File | Endpoints | RBAC Status | Notes |
|--------|-----------|-----------|-------------|-------|
| **Tax Guardian** | `views_tax_guardian.py` | 13 endpoints | ❌ `@login_required` only | No permission checks. Critical gap. |
| **Tax Settings** | `views_tax_settings.py` | 1 endpoint | ❌ `@login_required` only | Should use `tax.settings.manage` |
| **Tax Catalog** | `views_tax_catalog.py` | 9 endpoints | ⚠️ Legacy `is_staff` | Uses `is_staff/is_superuser` check |
| **Tax Import** | `views_tax_import.py` | 2 endpoints | ⚠️ Legacy `is_staff` | Uses `is_staff/is_superuser` check |
| **Tax Product Rules** | `views_tax_product_rules.py` | 2 endpoints | ❌ `@login_required` only | No permission checks |
| **Tax Documents** | `views_tax_documents.py` | 2 endpoints | ❌ `@login_required` only | Drilldown views unguarded |
| **Banking / Feeds** | `views_bank_audit.py` | 1 endpoint | ❌ `@login_required` only | Health check API |
| **Bank Review** | `views_bank_review.py` | 4 endpoints | ❌ `@login_required` only | Companion bank review |
| **Reconciliation** | `views_reconciliation.py` | 30+ endpoints | ⚠️ Partial (`is_staff` at line 1068) | One `is_staff` check, rest unguarded |
| **Invoices** | `views_invoices.py` | 7 endpoints | ❌ `@login_required` only | Create/approve/discard unguarded |
| **Expenses/Receipts** | `views_receipts.py` | Multiple | ❌ `@login_required` only | Upload/approve unguarded |
| **Companion/AI** | `views_companion.py` | 6 endpoints | ❌ `@login_required` only | LLM actions unguarded |
| **Dashboard** | `views_dashboard.py` | 1 endpoint | ❌ `@login_required` only | Dashboard API |
| **List APIs** | `views_list_apis.py` | 10 endpoints | ❌ `@login_required` only | Invoice/expense list APIs |
| **Accounts/CoA** | `views_accounts.py` | 6 endpoints | ❌ `@login_required` only | CoA management |
| **Memberships** | `views_memberships.py` | 4 endpoints | ✅ Uses `has_permission()` | Correctly protected |
| **Roles** | `views_roles.py` | 4 endpoints | ✅ Uses `has_permission()` | Correctly protected |
| **Auth** | `views_auth.py` | Multiple | ⚠️ Uses `is_staff/is_superuser` | For staff fallback |
| **Reports** | `views_reports.py` | Multiple | ❌ `@login_required` only | Export reports unguarded |

### Frontend Pages Coverage

| Page | File | Uses `usePermissions()` | Status |
|------|------|------------------------|--------|
| **Banking & Feeds** | `BankingAccountsAndFeedPage.tsx` | ✅ Yes (`canViewBankBalance`) | Protected |
| **Account Settings** | `AccountSettingsPage.tsx` | ✅ Yes (`isOwner`) | Protected |
| **Tax Guardian** | `TaxGuardianPage.tsx` | ❌ No | Gap |
| **Tax Settings** | `TaxSettingsPage.tsx` | ❌ No | Gap |
| **Tax Product Rules** | `TaxProductRulesPage.tsx` | ❌ No | Gap |
| **Tax Catalog** | `TaxCatalogPage.tsx` | ⚠️ Uses `isStaff` | Legacy check |
| **Reconciliation** | `ReconciliationPage.tsx` | ❌ No | Gap |
| **Invoices** | `InvoicesListPage.tsx` | ❌ No | Gap |
| **Expenses** | `ExpensesListPage.tsx` | ❌ No | Gap |
| **Receipts** | `ReceiptsPage.tsx` | ❌ No | Gap |
| **Bank Review** | `BankReviewPage.tsx` | ❌ No | Gap |
| **Books Review** | `BooksReviewPage.tsx` | ❌ No | Gap |
| **Companion Overview** | `CompanionOverviewPage.tsx` | ❌ No | Gap |
| **Customers** | `CustomersPage.tsx` | ❌ No | Gap |
| **Suppliers** | `SuppliersPage.tsx` | ❌ No | Gap |
| **Products** | `ProductsPage.tsx` | ❌ No | Gap |
| **Categories** | `CategoriesPage.tsx` | ❌ No | Gap |
| **Journal Entries** | `JournalEntriesPage.tsx` | ❌ No | Gap |
| **Transactions** | `TransactionsPage.tsx` | ❌ No | Gap |
| **Roles Settings** | `RolesSettingsPage.tsx` | ❌ No (but parent uses it) | Implicit |

### Management Commands

| Command | File | Status | Risk |
|---------|------|--------|------|
| `tax_llm_enrich_period` | `taxes/management/commands/` | No auth (CLI) | LOW (CLI only) |
| `tax_refresh_period` | `taxes/management/commands/` | No auth (CLI) | LOW (CLI only) |
| `tax_nudge_notifications` | `taxes/management/commands/` | No auth (CLI) | LOW (CLI only) |
| `tax_watchdog_period` | `taxes/management/commands/` | No auth (CLI) | LOW (CLI only) |
| `align_legacy_tax_accounts` | `taxes/management/commands/` | No auth (CLI) | LOW (CLI only) |

---

## Section 2: Gaps

### HIGH Priority Gaps

1. **Tax Guardian APIs have no RBAC protection**
   - 13 endpoints callable by any logged-in user
   - Includes: reset period, file return, unfile, payments, exports, LLM enrich
   - File: `core/views_tax_guardian.py`

2. **Reconciliation APIs mostly unprotected**
   - 30+ endpoints with only `@login_required`
   - Critical actions: complete session, reset, match/unmatch, create adjustments
   - File: `core/views_reconciliation.py`

3. **Invoice/Expense mutation APIs unprotected**
   - Create, edit, delete, void, approve endpoints have no role checks
   - Files: `core/views_invoices.py`, `core/views_receipts.py`

4. **Tax Catalog/Import use legacy `is_staff` checks**
   - Should use new RBAC permission engine
   - Files: `core/views_tax_catalog.py`, `core/views_tax_import.py`

### MEDIUM Priority Gaps

5. **Frontend Tax Guardian page has no permission guards**
   - Reset, Unfile, File, LLM Enrich buttons visible to everyone
   - File: `frontend/src/companion/TaxGuardianPage.tsx`

6. **Companion/AI endpoints unprotected**
   - LLM observer actions callable without role check
   - No "enable/disable AI" workspace toggle exists
   - File: `core/views_companion.py`

7. **Tax Settings API has no RBAC**
   - Filing cadence, nexus, registrations editable by any user
   - File: `core/views_tax_settings.py`

8. **Report export endpoints unprotected**
   - P&L, Balance Sheet, Cashflow exports lack role checks
   - File: `core/views_reports.py`

### LOW Priority Gaps

9. **Most frontend pages don't use `usePermissions()`**
   - 30 of 32 pages have no client-side permission checks
   - Buttons visible even if backend would reject

10. **No admin toggle for AI/LLM features per workspace**
    - No setting to enable/disable Companion AI
    - No visibility into who can use LLM enrichment

11. **Customer/Supplier/Product pages unprotected**
    - Basic CRUD operations have no role checks
    - Files: Various views

---

## Section 3: Risk Assessment

| Gap ID | Description | Risk Level | Impact |
|--------|-------------|------------|--------|
| 1 | Tax Guardian APIs unprotected | **HIGH** | Unauthorized tax filing, period resets |
| 2 | Reconciliation APIs unprotected | **HIGH** | Unauthorized bank matching, session manipulation |
| 3 | Invoice/Expense mutations unprotected | **HIGH** | Unauthorized financial document creation |
| 4 | Tax Catalog `is_staff` checks | **MEDIUM** | Staff-only but bypasses RBAC model |
| 5 | Frontend Tax Guardian no guards | **MEDIUM** | Poor UX, actions fail silently |
| 6 | Companion/AI unprotected | **MEDIUM** | LLM calls by unauthorized users |
| 7 | Tax Settings no RBAC | **MEDIUM** | Unauthorized config changes |
| 8 | Report exports unprotected | **LOW** | Data exposure risk |
| 9 | Frontend pages missing permission checks | **LOW** | UX inconsistency |
| 10 | No AI workspace toggle | **LOW** | Missing admin control surface |

---

## Section 4: Recommendations

### Backend Changes

#### Phase 1: Add Permission Guards to Critical Endpoints

**Tax Guardian** (`core/views_tax_guardian.py`):
- Add `@require_permission("tax.file_return")` to file return endpoint
- Add `@require_permission("tax.reset_period")` to reset endpoint

**Reconciliation** (`core/views_reconciliation.py`):
- Add `@require_permission("bank.reconcile")` to session operations

**Invoices/Expenses** (`core/views_invoices.py`, `core/views_receipts.py`):
- Add `@require_permission("invoices.create")` to creation endpoints

#### Phase 2: Replace Legacy `is_staff` Checks

**Tax Catalog** (`core/views_tax_catalog.py:16`):
- Replace `is_staff/is_superuser` with `has_permission(user, business, "tax.catalog.manage")`

**Tax Import** (`core/views_tax_import.py:23`):
- Same pattern - replace `is_staff` check

### Frontend Changes

#### Phase 2: Wire Sensitive Components to `usePermissions()`

**Tax Guardian** (`frontend/src/companion/TaxGuardianPage.tsx`):
- Hide Reset button unless `can("tax.reset_period")`
- Hide File Return button unless `can("tax.file_return")`

**Reconciliation** (`frontend/src/reconciliation/ReconciliationPage.tsx`):
- Hide Complete button unless `can("bank.reconcile")`

### New Permissions to Add

Add to `permissions_registry.py`:
- `tax.guardian.reset_period` - Reset tax period (destructive)
- `tax.guardian.llm_enrich` - Run LLM enrichment
- `reconciliation.complete_session` - Complete reconciliation session
- `reconciliation.reset_session` - Reset reconciliation session (destructive)
- `companion.ai.enabled` - Use Companion AI

---

## Implementation Plan

### Phase 1: Fix Missing Backend Guards (HIGH Priority)

| Step | File | Action | Est. Time |
|------|------|--------|-----------|
| 1.1 | `views_tax_guardian.py` | Add `@require_permission` to all 13 endpoints | 2h |
| 1.2 | `views_reconciliation.py` | Add `@require_permission` to session ops | 2h |
| 1.3 | `views_invoices.py` | Add permission checks to mutations | 1h |
| 1.4 | `views_receipts.py` | Add permission checks to mutations | 1h |
| 1.5 | `views_companion.py` | Add permission checks to AI actions | 1h |

### Phase 2: Replace Legacy Checks + Frontend Wiring (MEDIUM Priority)

| Step | File | Action | Est. Time |
|------|------|--------|-----------|
| 2.1 | `views_tax_catalog.py` | Replace `is_staff` with `has_permission()` | 1h |
| 2.2 | `views_tax_import.py` | Replace `is_staff` with `has_permission()` | 30m |
| 2.3 | `TaxGuardianPage.tsx` | Add `usePermissions()` to hide buttons | 1h |
| 2.4 | `ReconciliationPage.tsx` | Add `usePermissions()` to sensitive actions | 1h |
| 2.5 | `InvoicesListPage.tsx` | Add `usePermissions()` | 30m |
| 2.6 | `ExpensesListPage.tsx` | Add `usePermissions()` | 30m |

### Phase 3: Admin Settings Surfaces (MEDIUM Priority)

| Step | Action | Est. Time |
|------|--------|-----------|
| 3.1 | Add new permissions to `permissions_registry.py` | 1h |
| 3.2 | Create "AI & Automation" settings section | 2h |
| 3.3 | Add workspace-level AI toggle model field | 1h |
| 3.4 | Create API endpoint for workspace AI settings | 1h |

### Phase 4: Tests (LOW Priority)

| Step | Action | Est. Time |
|------|--------|-----------|
| 4.1 | Add permission tests for Tax Guardian endpoints | 2h |
| 4.2 | Add permission tests for Reconciliation endpoints | 2h |
| 4.3 | Add frontend unit tests for permission gating | 2h |

---

## Code Pointers Summary

| File | Function/Line | Recommended Change |
|------|---------------|-------------------|
| `core/views_tax_guardian.py` | All `api_*` functions | Add `@require_permission("tax.*")` |
| `core/views_tax_catalog.py:16` | `_require_staff_or_superuser()` | Replace with `has_permission()` |
| `core/views_tax_import.py:23` | Staff check | Replace with `has_permission()` |
| `core/views_reconciliation.py:1068` | `is_staff` check | Replace with `has_permission()` |
| `frontend/src/companion/TaxGuardianPage.tsx` | Reset/File buttons | Wrap in `{can("tax.reset_period") && ...}` |
| `frontend/src/reconciliation/ReconciliationPage.tsx` | Complete button | Wrap in `{can("bank.reconcile") && ...}` |
| `core/permissions_registry.py` | `PERMISSION_SPECS` | Add new tax/reconciliation/AI permissions |

---

## Summary

**Current Coverage:** ~15% of sensitive endpoints properly protected  
**Target Coverage:** 100%  
**Estimated Total Effort:** 20-25 hours

**Key Wins:**
1. Phase 1 alone covers the highest-risk gaps (Tax Guardian + Reconciliation)
2. The permission engine infrastructure already exists - just needs wiring
3. Frontend `usePermissions()` hook already works correctly
