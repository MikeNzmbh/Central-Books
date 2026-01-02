export type PermissionLevel = "none" | "view" | "edit" | "approve";

export type PermissionScopeType = "all" | "own_department" | "own_created" | "selected_accounts";

export interface PermissionScope {
  type: PermissionScopeType;
  account_ids?: number[];
}

export interface PermissionSpec {
  action: string;
  category: string;
  label: string;
  description: string;
  sensitive?: boolean;
}

export const PERMISSION_CATEGORIES = [
  "Global",
  "Banking",
  "Reconciliation",
  "Invoices",
  "Expenses",
  "Customers",
  "Products",
  "Tax",
  "Ledger",
  "Reporting",
  "Audit",
  "AI",
] as const;

export const PERMISSIONS: PermissionSpec[] = [
  {
    action: "users.manage_roles",
    category: "Global",
    label: "Manage users & roles",
    description: "Invite users, change roles, and remove users from the workspace.",
  },
  {
    action: "workspace.settings",
    category: "Global",
    label: "Manage workspace settings",
    description: "Update workspace-level settings and configuration.",
  },
  {
    action: "settings.roles.manage",
    category: "Global",
    label: "Manage role definitions",
    description: "Create, edit, and delete custom roles and permission matrices.",
  },
  {
    action: "settings.users.manage_overrides",
    category: "Global",
    label: "Manage user overrides",
    description: "Apply per-user permission overrides on top of role definitions.",
  },
  {
    action: "bank.accounts.view_balance",
    category: "Banking",
    label: "View bank balances",
    description: "Reveal bank account balances and running balances (sensitive).",
    sensitive: true,
  },
  {
    action: "bank.view_transactions",
    category: "Banking",
    label: "View bank transactions",
    description: "View bank feed transactions and details.",
  },
  {
    action: "bank.import",
    category: "Banking",
    label: "Import bank transactions",
    description: "Import bank feeds or upload transaction files.",
  },
  {
    action: "bank.reconcile",
    category: "Reconciliation",
    label: "Reconcile bank accounts",
    description: "Create and complete reconciliation sessions and matching.",
  },
  {
    action: "invoices.view",
    category: "Invoices",
    label: "View invoices",
    description: "View customer invoices and invoice details.",
  },
  {
    action: "invoices.create",
    category: "Invoices",
    label: "Create invoices",
    description: "Create new invoices.",
  },
  {
    action: "invoices.edit",
    category: "Invoices",
    label: "Edit invoices",
    description: "Edit draft invoices and invoice fields.",
  },
  {
    action: "invoices.delete",
    category: "Invoices",
    label: "Void invoices",
    description: "Void/soft-delete posted invoices.",
  },
  {
    action: "invoices.send",
    category: "Invoices",
    label: "Send invoices",
    description: "Send invoices to customers.",
  },
  {
    action: "expenses.view",
    category: "Expenses",
    label: "View expenses",
    description: "View expenses and bills.",
  },
  {
    action: "expenses.create",
    category: "Expenses",
    label: "Create expenses",
    description: "Create new expenses.",
  },
  {
    action: "expenses.edit",
    category: "Expenses",
    label: "Edit expenses",
    description: "Edit expenses and bill fields.",
  },
  {
    action: "expenses.delete",
    category: "Expenses",
    label: "Void expenses",
    description: "Void/soft-delete expenses.",
  },
  {
    action: "expenses.pay",
    category: "Expenses",
    label: "Pay bills/expenses",
    description: "Initiate or mark bills/expenses as paid.",
  },
  {
    action: "suppliers.view",
    category: "Expenses",
    label: "View suppliers",
    description: "View supplier records.",
  },
  {
    action: "suppliers.manage",
    category: "Expenses",
    label: "Manage suppliers",
    description: "Create and edit supplier records.",
  },
  {
    action: "vendor.edit_payment_details",
    category: "Expenses",
    label: "Edit vendor payment details",
    description: "Edit sensitive supplier bank/payment details (high risk).",
    sensitive: true,
  },
  {
    action: "customers.view",
    category: "Customers",
    label: "View customers",
    description: "View customer records.",
  },
  {
    action: "customers.manage",
    category: "Customers",
    label: "Manage customers",
    description: "Create and edit customer records.",
  },
  {
    action: "products.view",
    category: "Products",
    label: "View products & services",
    description: "View product/service catalog.",
  },
  {
    action: "products.manage",
    category: "Products",
    label: "Manage products & services",
    description: "Create and edit product/service catalog.",
  },
  {
    action: "categories.view",
    category: "Products",
    label: "View categories",
    description: "View categories.",
  },
  {
    action: "categories.manage",
    category: "Products",
    label: "Manage categories",
    description: "Create and edit categories.",
  },
  {
    action: "tax.view_periods",
    category: "Tax",
    label: "View tax periods",
    description: "View tax periods and filing status.",
  },
  {
    action: "tax.settings.manage",
    category: "Tax",
    label: "Manage tax settings",
    description: "Configure tax registration and rates.",
  },
  {
    action: "tax.catalog.manage",
    category: "Tax",
    label: "Manage tax catalog",
    description: "Create and edit tax codes and product rules.",
  },
  {
    action: "tax.file_return",
    category: "Tax",
    label: "File tax returns",
    description: "Submit/lock a tax return for filing.",
  },
  {
    action: "tax.reset_period",
    category: "Tax",
    label: "Reset tax period",
    description: "Reset a tax period (destructive).",
  },
  {
    action: "gl.view",
    category: "Ledger",
    label: "View general ledger",
    description: "View ledger and journal lines.",
  },
  {
    action: "gl.journal_entry",
    category: "Ledger",
    label: "Create journal entries",
    description: "Create manual journal entries.",
  },
  {
    action: "gl.close_period",
    category: "Ledger",
    label: "Close period",
    description: "Close/lock accounting periods.",
  },
  {
    action: "reports.view_pl",
    category: "Reporting",
    label: "View Profit & Loss",
    description: "View Profit & Loss reports.",
  },
  {
    action: "reports.view_balance_sheet",
    category: "Reporting",
    label: "View Balance Sheet",
    description: "View Balance Sheet reports.",
  },
  {
    action: "reports.view_cashflow",
    category: "Reporting",
    label: "View Cashflow",
    description: "View cashflow reports.",
  },
  {
    action: "reports.export",
    category: "Reporting",
    label: "Export reports",
    description: "Export reports and datasets.",
  },
  {
    action: "audit.view_log",
    category: "Audit",
    label: "View audit log",
    description: "View audit logs and high-risk events.",
  },
  {
    action: "companion.view",
    category: "AI",
    label: "View AI Companion",
    description: "Access AI companion views and summaries.",
  },
  {
    action: "companion.actions",
    category: "AI",
    label: "Run AI actions",
    description: "Run AI-assisted actions (categorization, suggestions) with human-in-the-loop.",
  },
  {
    action: "companion.shadow.write",
    category: "AI",
    label: "Write AI Proposals",
    description: "Allow writing AI proposals (never posts canonical entries).",
  },
  {
    action: "companion.shadow.wipe",
    category: "AI",
    label: "Clear AI Proposals",
    description: "Clear AI proposals for a workspace (safe; does not affect canonical ledger).",
  },
];

export function getPermissionsByCategory(category: string): PermissionSpec[] {
  return PERMISSIONS.filter((p) => p.category === category);
}
