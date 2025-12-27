import { ensureCsrfToken } from "../utils/csrf";

const BASE_V2 = "/api/companion/v2/";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
};

export type AIMode = "shadow_only" | "suggest_only" | "drafts" | "autopilot_limited";

export interface WorkspaceAISettings {
  ai_enabled: boolean;
  kill_switch?: boolean;
  ai_mode: AIMode;
  velocity_limit_per_minute: number;
  value_breaker_threshold: string;
  anomaly_stddev_threshold: string;
  trust_downgrade_rejection_rate: string;
  updated_at: string;
  created_at: string;
}

export interface AISettingsResponse {
  global_ai_enabled: boolean;
  settings: WorkspaceAISettings;
}

export interface BusinessPolicy {
  materiality_threshold: string;
  risk_appetite: "conservative" | "standard" | "aggressive";
  commingling_risk_vendors: string[];
  related_entities: Array<number | string>;
  intercompany_enabled: boolean;
  sector_archetype: string;
  updated_at: string;
  created_at: string;
}

export type ShadowEventStatus = "proposed" | "applied" | "accepted" | "rejected" | "superseded";

export interface ShadowEventSplit {
  account_id: number;
  account_name?: string;
  account_type?: string;
  amount: string;
  description?: string;
}

export interface ShadowEvent {
  id: string;
  event_type: string;
  status: ShadowEventStatus;
  bank_transaction?: number | null;
  source_command?: string | null;
  data: Record<string, any>;
  actor: string;
  confidence_score: string | null;
  logic_trace_id: string;
  rationale: string;
  business_profile_constraint: string;
  human_in_the_loop: Record<string, any>;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ApplyResultResponse {
  shadow_event: ShadowEvent;
  result: Record<string, any>;
}

const apiFetchV2 = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { method = "GET", body } = options;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (method !== "GET") {
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const csrf = await ensureCsrfToken();
    if (csrf) headers["X-CSRFToken"] = csrf;
  }

  const res = await fetch(`${BASE_V2}${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json().catch(() => ({})) : {};

  if (!res.ok) {
    const message = (data as any)?.detail || "Request failed";
    throw new Error(message);
  }

  return data as T;
};

export const fetchAISettingsV2 = (opts?: { workspace_id?: number }) => {
  const qs = new URLSearchParams();
  if (opts?.workspace_id) qs.set("workspace_id", String(opts.workspace_id));
  const suffix = qs.toString();
  return apiFetchV2<AISettingsResponse>(`settings/${suffix ? `?${suffix}` : ""}`);
};

export const patchAISettingsV2 = (patch: Partial<WorkspaceAISettings>, opts?: { workspace_id?: number }) => {
  const qs = new URLSearchParams();
  if (opts?.workspace_id) qs.set("workspace_id", String(opts.workspace_id));
  const suffix = qs.toString();
  return apiFetchV2<AISettingsResponse>(`settings/${suffix ? `?${suffix}` : ""}`, { method: "PATCH", body: patch });
};

export const fetchBusinessPolicyV2 = () => apiFetchV2<BusinessPolicy>("policy/");
export const patchBusinessPolicyV2 = (patch: Partial<BusinessPolicy>) =>
  apiFetchV2<BusinessPolicy>("policy/", { method: "PATCH", body: patch });

export const listShadowEventsV2 = (params?: { status?: string; event_type?: string; subject_object_id?: number; limit?: number }) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.subject_object_id) qs.set("subject_object_id", String(params.subject_object_id));
  if (params?.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString();
  return apiFetchV2<ShadowEvent[]>(`shadow-events/${suffix ? `?${suffix}` : ""}`);
};

export const applyShadowEventV2 = (id: string, override_splits?: any[]) =>
  apiFetchV2<ApplyResultResponse>(`shadow-events/${id}/apply/`, {
    method: "POST",
    body: override_splits ? { override_splits } : {},
  });

export const rejectShadowEventV2 = (id: string, reason?: string) =>
  apiFetchV2<ShadowEvent>(`shadow-events/${id}/reject/`, { method: "POST", body: { reason: reason || "" } });

export const listProposalsV2 = (params?: { workspace_id?: number; event_type?: string; subject_object_id?: number; limit?: number }) => {
  const qs = new URLSearchParams();
  if (params?.workspace_id) qs.set("workspace_id", String(params.workspace_id));
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.subject_object_id) qs.set("subject_object_id", String(params.subject_object_id));
  if (params?.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString();
  return apiFetchV2<ShadowEvent[]>(`proposals/${suffix ? `?${suffix}` : ""}`);
};

export const applyProposalV2 = (id: string, opts?: { workspace_id?: number; override_splits?: any[] }) =>
  apiFetchV2<ApplyResultResponse>(`proposals/${id}/apply/`, {
    method: "POST",
    body: {
      ...(opts?.workspace_id ? { workspace_id: opts.workspace_id } : {}),
      ...(opts?.override_splits ? { override_splits: opts.override_splits } : {}),
    },
  });

export const rejectProposalV2 = (id: string, opts?: { workspace_id?: number; reason?: string }) =>
  apiFetchV2<ShadowEvent>(`proposals/${id}/reject/`, {
    method: "POST",
    body: {
      ...(opts?.workspace_id ? { workspace_id: opts.workspace_id } : {}),
      reason: opts?.reason || "",
    },
  });
