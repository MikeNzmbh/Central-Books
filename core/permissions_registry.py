from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PermissionSpec:
    action: str
    category: str
    label: str
    description: str
    sensitive: bool = False


# NOTE: This registry is the canonical list used by RBAC v2 UI + APIs.
# Keep action strings stable; add new actions rather than renaming.
PERMISSION_SPECS: list[PermissionSpec] = [
    PermissionSpec(
        action="users.manage_roles",
        category="Global",
        label="Manage users & roles",
        description="Invite users, change roles, and remove users from the workspace.",
    ),
    PermissionSpec(
        action="workspace.settings",
        category="Global",
        label="Manage workspace settings",
        description="Update workspace-level settings and configuration.",
    ),
    PermissionSpec(
        action="settings.roles.manage",
        category="Global",
        label="Manage role definitions",
        description="Create, edit, and delete custom roles and permission matrices.",
    ),
    PermissionSpec(
        action="settings.users.manage_overrides",
        category="Global",
        label="Manage user overrides",
        description="Apply per-user permission overrides on top of role definitions.",
    ),
    # Banking & Reconciliation
    PermissionSpec(
        action="bank.accounts.view_balance",
        category="Banking",
        label="View bank balances",
        description="Reveal bank account balances and running balances (sensitive).",
        sensitive=True,
    ),
    PermissionSpec(
        action="bank.view_transactions",
        category="Banking",
        label="View bank transactions",
        description="View bank feed transactions and details.",
    ),
    PermissionSpec(
        action="bank.import",
        category="Banking",
        label="Import bank transactions",
        description="Import bank feeds or upload transaction files.",
    ),
    PermissionSpec(
        action="bank.reconcile",
        category="Reconciliation",
        label="Reconcile bank accounts",
        description="Create and complete reconciliation sessions and matching.",
    ),
    # Invoices (AR)
    PermissionSpec(
        action="invoices.view",
        category="Invoices",
        label="View invoices",
        description="View customer invoices and invoice details.",
    ),
    PermissionSpec(
        action="invoices.create",
        category="Invoices",
        label="Create invoices",
        description="Create new invoices.",
    ),
    PermissionSpec(
        action="invoices.edit",
        category="Invoices",
        label="Edit invoices",
        description="Edit draft invoices and invoice fields.",
    ),
    PermissionSpec(
        action="invoices.delete",
        category="Invoices",
        label="Void invoices",
        description="Void/soft-delete posted invoices.",
    ),
    PermissionSpec(
        action="invoices.send",
        category="Invoices",
        label="Send invoices",
        description="Send invoices to customers.",
    ),
    # Expenses / Bills (AP)
    PermissionSpec(
        action="expenses.view",
        category="Expenses",
        label="View expenses",
        description="View expenses and bills.",
    ),
    PermissionSpec(
        action="expenses.create",
        category="Expenses",
        label="Create expenses",
        description="Create new expenses.",
    ),
    PermissionSpec(
        action="expenses.edit",
        category="Expenses",
        label="Edit expenses",
        description="Edit expenses and bill fields.",
    ),
    PermissionSpec(
        action="expenses.delete",
        category="Expenses",
        label="Void expenses",
        description="Void/soft-delete expenses.",
    ),
    PermissionSpec(
        action="expenses.pay",
        category="Expenses",
        label="Pay bills/expenses",
        description="Initiate or mark bills/expenses as paid.",
    ),
    PermissionSpec(
        action="suppliers.manage",
        category="Expenses",
        label="Manage suppliers",
        description="Create and edit supplier records.",
    ),
    PermissionSpec(
        action="suppliers.view",
        category="Expenses",
        label="View suppliers",
        description="View supplier records.",
    ),
    PermissionSpec(
        action="vendor.edit_payment_details",
        category="Expenses",
        label="Edit vendor payment details",
        description="Edit sensitive supplier bank/payment details (high risk).",
        sensitive=True,
    ),
    # Customers / Products
    PermissionSpec(
        action="customers.view",
        category="Customers",
        label="View customers",
        description="View customer records.",
    ),
    PermissionSpec(
        action="customers.manage",
        category="Customers",
        label="Manage customers",
        description="Create and edit customer records.",
    ),
    PermissionSpec(
        action="products.view",
        category="Products",
        label="View products & services",
        description="View product/service catalog.",
    ),
    PermissionSpec(
        action="products.manage",
        category="Products",
        label="Manage products & services",
        description="Create and edit product/service catalog.",
    ),
    PermissionSpec(
        action="categories.view",
        category="Products",
        label="View categories",
        description="View categories.",
    ),
    PermissionSpec(
        action="categories.manage",
        category="Products",
        label="Manage categories",
        description="Create and edit categories.",
    ),
    # Tax
    PermissionSpec(
        action="tax.view_periods",
        category="Tax",
        label="View tax periods",
        description="View tax periods and filing status.",
    ),
    PermissionSpec(
        action="tax.settings.manage",
        category="Tax",
        label="Manage tax settings",
        description="Configure tax registration and rates.",
    ),
    PermissionSpec(
        action="tax.catalog.manage",
        category="Tax",
        label="Manage tax catalog",
        description="Create and edit tax codes and product rules.",
    ),
    PermissionSpec(
        action="tax.file_return",
        category="Tax",
        label="File tax returns",
        description="Submit/lock a tax return for filing.",
    ),
    PermissionSpec(
        action="tax.reset_period",
        category="Tax",
        label="Reset tax period",
        description="Reset a tax period (destructive).",
    ),
    # Ledger / Reports / Audit / AI
    PermissionSpec(
        action="gl.view",
        category="Ledger",
        label="View general ledger",
        description="View ledger and journal lines.",
    ),
    PermissionSpec(
        action="gl.journal_entry",
        category="Ledger",
        label="Create journal entries",
        description="Create manual journal entries.",
    ),
    PermissionSpec(
        action="gl.close_period",
        category="Ledger",
        label="Close period",
        description="Close/lock accounting periods.",
    ),
    PermissionSpec(
        action="reports.view_pl",
        category="Reporting",
        label="View Profit & Loss",
        description="View Profit & Loss reports.",
    ),
    PermissionSpec(
        action="reports.view_balance_sheet",
        category="Reporting",
        label="View Balance Sheet",
        description="View Balance Sheet reports.",
    ),
    PermissionSpec(
        action="reports.view_cashflow",
        category="Reporting",
        label="View Cashflow",
        description="View cashflow reports.",
    ),
    PermissionSpec(
        action="reports.export",
        category="Reporting",
        label="Export reports",
        description="Export reports and datasets.",
    ),
    PermissionSpec(
        action="audit.view_log",
        category="Audit",
        label="View audit log",
        description="View audit logs and high-risk events.",
    ),
    PermissionSpec(
        action="companion.view",
        category="AI",
        label="View AI Companion",
        description="Access AI companion views and summaries.",
    ),
    PermissionSpec(
        action="companion.actions",
        category="AI",
        label="Run AI actions",
        description="Run AI-assisted actions (categorization, suggestions) with human-in-the-loop.",
    ),
]


ACTION_ALIASES: dict[str, str] = {
    # RBAC v1 -> v2 canonical
    "bank.view_balance": "bank.accounts.view_balance",
}


def equivalent_actions(action: str) -> list[str]:
    """
    Return a short list of equivalent action keys (action + known aliases).
    """
    if not action:
        return []
    aliases: list[str] = [action]
    mapped = ACTION_ALIASES.get(action)
    if mapped and mapped not in aliases:
        aliases.append(mapped)
    # Also allow reverse lookup (v2 -> v1)
    for k, v in ACTION_ALIASES.items():
        if v == action and k not in aliases:
            aliases.append(k)
    return aliases


def is_sensitive_action(action: str) -> bool:
    if not action:
        return False
    for candidate in equivalent_actions(action):
        for spec in PERMISSION_SPECS:
            if spec.action == candidate:
                return spec.sensitive
    return False


def iter_permission_specs() -> Iterable[PermissionSpec]:
    return PERMISSION_SPECS
