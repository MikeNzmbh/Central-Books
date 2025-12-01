import { parseCookies } from "../utils/cookies";

const BASE = "/api/internal-admin/";

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
  action: string;
  object_type: string;
  object_id: string;
  extra: Record<string, unknown>;
  remote_ip: string | null;
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
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.append(key, String(value));
      }
    });
  }
  return url.pathname + url.search;
};

const apiFetch = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { method = "GET", body, params } = options;
  const url = buildUrl(`${BASE}${path}`, params);
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    const csrf = parseCookies(document.cookie).csrftoken;
    if (csrf) {
      headers["X-CSRFToken"] = csrf;
    }
  }

  const res = await fetch(url, {
    method,
    headers,
    credentials: "same-origin",
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

export const updateUser = (id: number, payload: Partial<User>) =>
  apiFetch<User>(`users/${id}/`, { method: "PATCH", body: payload });

export const fetchWorkspaces = (params?: Record<string, string | number | undefined | null>) =>
  apiFetch<Paginated<Workspace>>("workspaces/", { params });

export const updateWorkspace = (id: number, payload: Partial<Workspace>) =>
  apiFetch<Workspace>(`workspaces/${id}/`, { method: "PATCH", body: payload });

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

export const fetchFeatureFlags = () => apiFetch<FeatureFlag[]>("feature-flags/");

export const updateFeatureFlag = (id: number, payload: Partial<FeatureFlag>) =>
  apiFetch<FeatureFlag>(`feature-flags/${id}/`, { method: "PATCH", body: payload });

export const startImpersonation = async (userId: number) => {
  return apiFetch<{ redirect_url: string }>("impersonations/", {
    method: "POST",
    body: { user_id: userId },
  });
};
