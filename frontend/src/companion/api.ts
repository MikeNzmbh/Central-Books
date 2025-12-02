import { parseCookies } from "../utils/cookies";

const BASE = "/api/companion/";

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
};

export interface HealthIndex {
  score: number;
  created_at: string;
  breakdown: Record<string, number>;
  raw_metrics: Record<string, number>;
}

export interface CompanionInsight {
  id: number;
  domain: string;
  title: string;
  body: string;
  severity: "info" | "warning" | "critical";
  suggested_actions: { label: string; action?: string }[];
  created_at: string;
  is_dismissed?: boolean;
  dismissed_at?: string | null;
}

export interface CompanionNarrative {
  summary: string | null;
  insight_explanations: Record<string, string>;
  action_explanations?: Record<string, string>;
}

export interface CompanionActionPayload {
  bank_transaction_id: number;
  journal_entry_id: number;
  amount: string;
  date: string;
  currency?: string;
}

export interface CompanionAction {
  id: number;
  action_type: "bank_match_review";
  status: "open" | "applied" | "dismissed";
  confidence: number;
  summary: string;
  payload: CompanionActionPayload;
  created_at: string;
  source_snapshot_id?: number | null;
}

export interface CompanionOverview {
  health_index: HealthIndex | null;
  insights?: CompanionInsight[];
  top_insights?: CompanionInsight[];
  raw_metrics: Record<string, number>;
  next_refresh_at: string | null;
  llm_narrative: CompanionNarrative | null;
  actions?: CompanionAction[];
}

const apiFetch = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { method = "GET", body } = options;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (method !== "GET" && body !== undefined) {
    headers["Content-Type"] = "application/json";
    const csrf = parseCookies(document.cookie).csrftoken;
    if (csrf) {
      headers["X-CSRFToken"] = csrf;
    }
  }

  const res = await fetch(`${BASE}${path}`, {
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

export const fetchCompanionOverview = () => apiFetch<CompanionOverview>("overview/");

export const fetchCompanionActions = () => apiFetch<CompanionAction[]>("actions/");

export const applyCompanionAction = (id: number) => apiFetch<CompanionAction>(`actions/${id}/apply/`, { method: "POST" });

export const dismissCompanionAction = (id: number) =>
  apiFetch<CompanionAction>(`actions/${id}/dismiss/`, { method: "POST" });
