import { buildApiUrl } from "./base";

export type HealthResponse = {
  status: string;
};

export type InternalAdmin = {
  role?: string;
  canAccessInternalAdmin?: boolean;
  adminPanelAccess?: boolean;
  canManageAdminUsers?: boolean;
  canGrantSuperadmin?: boolean;
};

export type Workspace = {
  businessId: number;
  businessName: string;
  role: string;
  roleLabel: string;
  roleDescription: string;
  roleColor: string;
  permissions: string[];
  permissionLevels?: Record<string, string>;
  isOwner: boolean;
  department: string | null;
  region: string | null;
};

export type User = {
  id?: number;
  email: string;
  name?: string | null;
  username?: string;
  firstName?: string;
  lastName?: string;
  fullName?: string;
  first_name?: string;
  last_name?: string;
  is_admin?: boolean;
  role?: string | null;
  isStaff?: boolean;
  isSuperuser?: boolean;
  is_staff?: boolean;
  is_superuser?: boolean;
  internalAdmin?: InternalAdmin | null;
  workspace?: Workspace | null;
};

export type AuthResponse = {
  authenticated: boolean;
  user: User;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

let accessToken: string | null = null;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

export const getAccessToken = () => accessToken;

const apiJson = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const method = options.method ?? "GET";
  const shouldAttachAuth = options.auth ?? true;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (shouldAttachAuth && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const res = await fetch(buildApiUrl(path), {
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

export const fetchHealth = () => apiJson<HealthResponse>("/healthz");

export const login = (email: string, password: string) =>
  apiJson<TokenResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false }).then((data) => {
    setAccessToken(data.access_token);
    return data;
  });

export const refresh = () =>
  apiJson<TokenResponse>("/auth/refresh", { method: "POST", auth: false }).then((data) => {
    setAccessToken(data.access_token);
    return data;
  });

export const logout = () =>
  apiJson<{ ok: boolean }>("/auth/logout", { method: "POST", auth: false }).finally(() => {
    setAccessToken(null);
  });

export const fetchMe = () => apiJson<AuthResponse>("/me");
