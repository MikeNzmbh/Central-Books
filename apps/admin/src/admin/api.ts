import { buildApiUrl } from "../api/base";
import { getAccessToken } from "../api/client";

const BASE = "/api/admin/";

export type Paginated<T> = {
  results: T[];
  next: string | null;
  previous: string | null;
  count?: number;
};

export type OverviewMetrics = {
  active_users_30d: number;
  active_users_30d_change_pct: number;
  unreconciled_transactions: number;
  unreconciled_transactions_older_60d: number;
  unbalanced_journal_entries: number;
  api_error_rate_1h_pct: number;
  api_p95_response_ms_1h: number;
  ai_flagged_open_issues: number;
  failed_invoice_emails_24h: number;
  workspaces_health: WorkspaceHealth[];
};

export type WorkspaceHealth = {
  id: number;
  name: string;
  owner_email: string;
  plan: string | null;
  unreconciled_count: number;
  ledger_status: string;
};

export type User = {
  id: number;
  email: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  date_joined?: string | null;
  is_active: boolean;
  admin_role?: string | null;
  last_login?: string | null;
  is_staff?: boolean;
  is_superuser?: boolean;
  workspace_count?: number;
  has_usable_password?: boolean;
  auth_providers?: string[];
  has_google_login?: boolean;
  social_account_count?: number;
};

export type ApprovalRequiredBase = {
  approval_required: true;
  approval_request_id: string;
  approval_status: ApprovalStatus;
};

export type ApprovalAcceptedResult<T> = T | (ApprovalRequiredBase & T);

export type Workspace = {
  id: number;
  name: string;
  owner_email: string;
  plan: string | null;
  status: string;
  is_deleted: boolean;
  created_at: string;
  bank_setup_completed?: boolean;
  unreconciled_count?: number;
  ledger_status?: string;
};

export type BankAccount = {
  id: number;
  workspace_name: string;
  owner_email: string;
  bank_name: string;
  name: string;
  account_number_mask: string;
  usage_role: string;
  is_active: boolean;
  last_imported_at: string | null;
  status: string;
  unreconciled_count: number;
};

export type AuditEntry = {
  id: number;
  timestamp: string;
  admin_email: string | null;
  actor_role?: string;
  action: string;
  object_type: string;
  object_id: string;
  extra: Record<string, unknown>;
  remote_ip: string | null;
  user_agent?: string;
  request_id?: string;
  level?: "INFO" | "WARNING" | "ERROR";
  category?: string | null;
};

export type SupportTicket = {
  id: number;
  subject: string;
  status: string;
  priority: string;
  source: string;
  created_at: string;
  updated_at: string;
  user_email?: string | null;
  workspace_name?: string | null;
  notes?: SupportTicketNote[];
};

export type SupportTicketNote = {
  id: number;
  admin_email: string | null;
  body: string;
  created_at: string;
};

export type FeatureFlag = {
  id: number;
  key: string;
  label: string;
  description: string;
  is_enabled: boolean;
  rollout_percent: number;
  created_at: string;
  updated_at: string;
};

export type Employee = {
  id: number;
  user_id: number;
  name: string;
  email: string;
  title: string;
  department: string;
  admin_panel_access: boolean;
  primary_admin_role: string;
  is_active_employee: boolean;
  last_login: string | null;
  workspace_scope: Record<string, unknown>;
  invite?: {
    id: string;
    status: "pending" | "expired";
    invited_at: string;
    expires_at: string | null;
    invite_url: string;
    email_send_failed: boolean;
    email_last_error?: string;
  } | null;
  manager?: { id: number; name: string; email: string } | null;
  created_at?: string;
  updated_at?: string;
  recent_admin_actions?: Array<Record<string, unknown>>;
};

export type EmployeeWritePayload = {
  user_id?: number;
  email?: string;
  display_name?: string;
  title?: string;
  department?: string;
  admin_panel_access?: boolean;
  primary_admin_role?: string;
  is_active_employee?: boolean;
  manager_id?: number | null;
  workspace_scope?: Record<string, unknown>;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  params?: Record<string, string | number | undefined | null>;
};

type ApiError = {
  status: number;
  message: string;
  data?: any;
};

const buildUrl = (path: string, params?: RequestOptions["params"]) => {
  const base = buildApiUrl(path);
  if (!params) return base;
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      qs.append(key, String(value));
    }
  });
  const query = qs.toString();
  if (!query) return base;
  return `${base}${base.includes("?") ? "&" : "?"}${query}`;
};

const apiFetch = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { method = "GET", body, params } = options;
  const url = buildUrl(`${BASE}${path}`, params);
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json().catch(() => ({})) : {};

  if (!res.ok) {
    const error: ApiError = {
      status: res.status,
      message: data?.detail || data?.message || "Request failed",
      data,
    };
    throw error;
  }

  return data as T;
};

export const fetchOverviewMetrics = () => apiFetch<OverviewMetrics>("overview-metrics/");

export const fetchUsers = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<User>>("users/", { params });

export type UpdateUserResponse = User | (ApprovalRequiredBase & { user: User });

export const updateUser = (id: number, payload: Record<string, unknown>) =>
  apiFetch<UpdateUserResponse>(`users/${id}/`, { method: "PATCH", body: payload });

export type PasswordResetResponse = {
  success: boolean;
  reset_url: string;
  message: string;
};

export type PasswordResetApprovalResponse = ApprovalRequiredBase;

export const resetPassword = (id: number, reason: string) =>
  apiFetch<PasswordResetApprovalResponse>(`users/${id}/reset-password/`, {
    method: "POST",
    body: { reason },
  });

export const fetchWorkspaces = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<Workspace>>("workspaces/", { params });

export const fetchEmployees = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<Employee>>("employees/", { params });

export const fetchEmployee = (id: number) => apiFetch<Employee>(`employees/${id}/`);

export const createEmployee = (payload: EmployeeWritePayload) =>
  apiFetch<Employee>("employees/", { method: "POST", body: payload });

export const updateEmployee = (id: number, payload: EmployeeWritePayload) =>
  apiFetch<Employee>(`employees/${id}/`, { method: "PATCH", body: payload });

export const suspendEmployee = (id: number) =>
  apiFetch<Employee>(`employees/${id}/suspend/`, { method: "POST", body: {} });

export const reactivateEmployee = (id: number) =>
  apiFetch<Employee>(`employees/${id}/reactivate/`, { method: "POST", body: {} });

export const deleteEmployee = (id: number) =>
  apiFetch<{ success: boolean }>(`employees/${id}/delete/`, { method: "POST", body: {} });

export type InviteEmployeePayload = {
  email: string;
  full_name?: string;
  role: "support" | "finance" | "engineering" | "superadmin";
};

export const inviteEmployee = (payload: InviteEmployeePayload) =>
  apiFetch<Employee>("employees/invite/", { method: "POST", body: payload });

export const resendInvite = (employeeId: number) =>
  apiFetch<Employee>(`employees/${employeeId}/resend-invite/`, { method: "POST", body: {} });

export const revokeInvite = (employeeId: number) =>
  apiFetch<Employee>(`employees/${employeeId}/revoke-invite/`, { method: "POST", body: {} });

export type UpdateWorkspaceResponse = Workspace | (ApprovalRequiredBase & { workspace: Workspace });

export const updateWorkspace = (id: number, payload: Record<string, unknown>) =>
  apiFetch<UpdateWorkspaceResponse>(`workspaces/${id}/`, { method: "PATCH", body: payload });

export const fetchBankAccounts = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<BankAccount>>("bank-accounts/", { params });

export const fetchAuditLog = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<AuditEntry>>("audit-log/", { params });

export const fetchSupportTickets = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<SupportTicket>>("support-tickets/", { params });

export const updateSupportTicket = (id: number, payload: Partial<SupportTicket>) =>
  apiFetch<SupportTicket>(`support-tickets/${id}/`, { method: "PATCH", body: payload });

export const addSupportTicketNote = (id: number, body: string) =>
  apiFetch<SupportTicket>(`support-tickets/${id}/add_note/`, { method: "POST", body: { body } });

export interface CreateSupportTicketPayload {
  subject: string;
  priority?: string;
  status?: string;
  user_id?: number | null;
  workspace_id?: number | null;
}

export const createSupportTicket = (payload: CreateSupportTicketPayload) =>
  apiFetch<SupportTicket>("support-tickets/", { method: "POST", body: payload });

export const fetchFeatureFlags = () => apiFetch<FeatureFlag[]>("feature-flags/");

export type UpdateFeatureFlagResponse = FeatureFlag | ApprovalRequiredBase;

export const updateFeatureFlag = (id: number, payload: Record<string, unknown>) =>
  apiFetch<UpdateFeatureFlagResponse>(`feature-flags/${id}/`, { method: "PATCH", body: payload });

export const startImpersonation = async (userId: number, reason: string) => {
  return apiFetch<{ redirect_url: string }>("impersonations/", {
    method: "POST",
    body: { user_id: userId, reason },
  });
};

// Reconciliation Metrics
export type ReconciliationMetrics = {
  total_unreconciled: number;
  aging: {
    "0_30_days": number;
    "30_60_days": number;
    "60_90_days": number;
    over_90_days: number;
  };
  top_workspaces: Array<{
    id: number;
    name: string;
    unreconciled_count: number;
  }>;
  recent_sessions: Array<{
    id: number;
    workspace: string;
    status: string;
    matched_count: number;
    created_at: string;
  }>;
};

export const fetchReconciliationMetrics = () =>
  apiFetch<ReconciliationMetrics>("reconciliation-metrics/");

// Ledger Health
export type LedgerHealth = {
  summary: {
    unbalanced_entries: number;
    orphan_accounts: number;
    suspense_with_balance: number;
  };
  unbalanced_entries: Array<{
    id: number;
    workspace: string;
    date: string | null;
    description: string;
    debit_total: number;
    credit_total: number;
    difference: number;
  }>;
  orphan_accounts: Array<{
    id: number;
    code: string;
    name: string;
    workspace: string;
  }>;
  suspense_balances: Array<{
    id: number;
    code: string;
    name: string;
    workspace: string;
    balance: number;
  }>;
};

export const fetchLedgerHealth = () => apiFetch<LedgerHealth>("ledger-health/");

// Invoices Audit
export type InvoicesAudit = {
  summary: {
    total: number;
    draft: number;
    sent: number;
    paid: number;
    issues: number;
  };
  status_distribution: Record<string, number>;
  recent_issues: Array<{
    id: number;
    workspace: string;
    customer: string;
    status: string;
    total: number;
    created_at: string | null;
  }>;
};

export const fetchInvoicesAudit = () => apiFetch<InvoicesAudit>("invoices-audit/");

// Expenses Audit
export type ExpensesAudit = {
  summary: {
    total_expenses: number;
    total_receipts: number;
    uncategorized: number;
    pending_receipts: number;
  };
  expense_distribution: Record<string, number>;
  receipt_distribution: Record<string, number>;
  top_workspaces: Array<{
    id: number;
    name: string;
    count: number;
    total: number;
  }>;
};

export const fetchExpensesAudit = () => apiFetch<ExpensesAudit>("expenses-audit/");

// ============================================================
// PHASE 2: Workspace 360 "God View"
// ============================================================

export type Workspace360 = {
  workspace: {
    id: number;
    name: string;
    created_at: string | null;
  };
  owner: {
    id: number | null;
    email: string | null;
    full_name: string | null;
  };
  plan: string | null;
  banking: {
    account_count: number;
    accounts: Array<{
      id: number;
      name: string;
      bank_name: string;
      is_active: boolean;
      last_imported_at: string | null;
    }>;
    unreconciled_count: number;
  };
  ledger_health: {
    unbalanced_entries: number;
    orphan_accounts: number;
    total_accounts: number;
    total_entries: number;
  };
  invoices: {
    total: number;
    draft: number;
    sent: number;
    paid: number;
  };
  expenses: {
    total: number;
    uncategorized: number;
    total_amount: number;
  };
  tax: {
    has_tax_guardian: boolean;
    last_period: {
      id: number;
      start_date: string;
      end_date: string;
      status: string;
    } | null;
    open_anomalies: {
      high: number;
      medium: number;
      low: number;
    };
  };
  ai: {
    last_monitor_run: string | null;
    open_ai_flags: number;
  };
};

export const fetchWorkspace360 = (workspaceId: number) =>
  apiFetch<Workspace360>(`workspaces/${workspaceId}/overview/`);

// ============================================================
// PHASE 2: Maker-Checker Approvals
// ============================================================

export type ApprovalActionType =
  | "TAX_PERIOD_RESET"
  | "LEDGER_ADJUST"
  | "WORKSPACE_DELETE"
  | "BULK_REFUND"
  | "USER_BAN"
  | "USER_REACTIVATE"
  | "USER_PRIVILEGE_CHANGE"
  | "PASSWORD_RESET_LINK"
  | "FEATURE_FLAG_CRITICAL";

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED" | "FAILED";

export type ApprovalRequest = {
  id: string;
  action_type: ApprovalActionType;
  initiator: {
    id: number;
    email: string | null;
  };
  approver: {
    id: number;
    email: string | null;
  } | null;
  workspace: {
    id: number;
    name: string | null;
  } | null;
  target_user: {
    id: number;
    email: string | null;
  } | null;
  reason: string;
  rejection_reason?: string;
  payload: Record<string, unknown>;
  status: ApprovalStatus;
  execution_error?: string;
  created_at: string;
  resolved_at: string | null;
  expires_at: string | null;
};

export type ApprovalsSummary = {
  total_pending: number;
  total_today: number;
  high_risk_pending: number;
  avg_response_minutes_24h: number | null;
};

export type ApprovalList = {
  results: ApprovalRequest[];
  count: number;
  summary: ApprovalsSummary;
};

export const fetchApprovals = (params?: { status?: string; search?: string }) =>
  apiFetch<ApprovalList>("approvals/", { params });

export const createApprovalRequest = async (data: {
  action_type: ApprovalActionType;
  reason: string;
  workspace_id?: number;
  target_user_id?: number;
  payload?: Record<string, unknown>;
}) => apiFetch<{ id: string; status: string; created_at?: string }>("approvals/", { method: "POST", body: data });

export const approveRequest = async (requestId: string) => {
  return apiFetch<{ id: string; status: string; resolved_at?: string; execution_error?: string }>(
    `approvals/${requestId}/approve/`,
    { method: "POST", body: {} }
  );
};

export const rejectRequest = async (requestId: string, reason?: string) => {
  return apiFetch<{ id: string; status: string; resolved_at?: string }>(
    `approvals/${requestId}/reject/`,
    { method: "POST", body: { reason: reason || "" } }
  );
};

export const breakGlassApproval = async (requestId: string, reason: string, ttlMinutes?: number) => {
  return apiFetch<{ success: boolean; expires_at: string }>(
    `approvals/${requestId}/break-glass/`,
    {
      method: "POST",
      body: { reason, ttl_minutes: ttlMinutes },
    }
  );
};
