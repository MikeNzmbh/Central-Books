import { buildApiUrl } from "./base";
import { ensureCsrfToken } from "./csrf";

export type Paginated<T> = {
  results: T[];
  next: string | null;
  previous: string | null;
  count?: number;
};

export type AuthResponse = {
  authenticated: boolean;
  user: {
    id: number;
    email: string;
    fullName?: string;
    isStaff?: boolean;
    internalAdmin?: {
      role?: string;
      canAccessInternalAdmin?: boolean;
    } | null;
  } | null;
};

export type OverviewMetrics = {
  active_users_30d: number;
  unreconciled_transactions: number;
  ai_flagged_open_issues: number;
  failed_invoice_emails_24h: number;
  api_p95_response_ms_1h: number;
};

export type AdminUser = {
  id: number;
  email: string;
  full_name?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  last_login?: string | null;
  admin_role?: string | null;
  workspace_count?: number;
};

export type Workspace = {
  id: number;
  name: string;
  owner_email?: string;
  plan?: string | null;
  status?: string;
  is_deleted?: boolean;
};

export type AISettings = {
  ai_enabled: boolean;
  kill_switch: boolean;
  ai_mode: string;
  velocity_limit_per_minute: number;
  value_breaker_threshold: string;
  anomaly_stddev_threshold: string;
  trust_downgrade_rejection_rate: string;
  updated_at: string;
};

export type AISettingsResponse = {
  global_ai_enabled: boolean;
  settings: AISettings;
};

export type IntegrityReport = {
  id: number | string;
  period_start: string;
  period_end: string;
  summary: string;
  flagged_items: unknown;
  created_at: string;
};

export type AuditEntry = {
  id: number;
  timestamp: string;
  admin_email?: string | null;
  actor_role?: string | null;
  action: string;
  object_type: string;
  object_id: string;
  level?: string;
  category?: string | null;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  params?: Record<string, string | number | undefined | null>;
  headers?: Record<string, string>;
};

const buildQuery = (params?: RequestOptions["params"]) => {
  if (!params) return "";
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    qs.set(key, String(value));
  });
  const query = qs.toString();
  return query ? `?${query}` : "";
};

const apiJson = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const method = options.method ?? "GET";
  const query = buildQuery(options.params);
  const url = buildApiUrl(`${path}${query}`);
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers || {}),
  };

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (method !== "GET") {
    const csrf = await ensureCsrfToken();
    if (csrf) headers["X-CSRFToken"] = csrf;
  }

  const res = await fetch(url, {
    method,
    headers,
    body,
    credentials: "include",
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail || data?.error || data?.message || `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data as T;
};

export const fetchAuthMe = () => apiJson<AuthResponse>("/api/auth/me");

export const login = (username: string, password: string) =>
  apiJson("/api/auth/login/", { method: "POST", body: { username, password } });

export const fetchOverviewMetrics = () =>
  apiJson<OverviewMetrics>("/api/admin/overview-metrics/");

export const fetchUsers = (params?: RequestOptions["params"]) =>
  apiJson<Paginated<AdminUser>>("/api/admin/users/", { params });

export const fetchWorkspaces = (params?: RequestOptions["params"]) =>
  apiJson<Paginated<Workspace>>("/api/admin/workspaces/", { params });

export const fetchAISettings = (workspaceId: number) =>
  apiJson<AISettingsResponse>("/api/admin/ai/settings/", { params: { workspace_id: workspaceId } });

export const updateAISettings = (workspaceId: number, body: Partial<AISettings>) =>
  apiJson<AISettingsResponse>("/api/admin/ai/settings/", {
    method: "PATCH",
    params: { workspace_id: workspaceId },
    body,
  });

export const fetchIntegrityReports = (workspaceId: number) =>
  apiJson<IntegrityReport[]>("/api/admin/ai/integrity-reports/", {
    params: { workspace_id: workspaceId },
  });

export const fetchAuditLog = (params?: RequestOptions["params"]) =>
  apiJson<Paginated<AuditEntry>>("/api/admin/audit-log/", { params });
