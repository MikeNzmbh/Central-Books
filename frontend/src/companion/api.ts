import { parseCookies } from "../utils/cookies";

const BASE = "/api/companion/";

type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
};

export type CompanionContext =
  | "dashboard"
  | "bank"
  | "reconciliation"
  | "invoices"
  | "expenses"
  | "reports"
  | "tax_fx";

export interface HealthIndex {
  score: number;
  created_at: string;
  breakdown: Record<string, number>;
  raw_metrics: Record<string, number>;
}

export interface CompanionInsight {
  id: number;
  context?: CompanionContext;
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
  context_summary?: string | null;
}

export type CompanionActionPayload = Record<string, any>;

export interface CompanionAction {
  id: number;
  context?: CompanionContext;
  action_type: "bank_match_review" | "send_invoice_reminder" | "categorize_expenses_batch";
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
  context?: CompanionContext | null;
  context_all_clear?: boolean;
  context_metrics?: Record<string, any>;
  has_new_actions?: boolean;
  new_actions_count?: number;
}

const apiFetch = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { method = "GET", body } = options;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (method !== "GET") {
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
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

export const fetchCompanionOverview = (context?: CompanionContext) =>
  apiFetch<CompanionOverview>(`overview/${context ? `?context=${context}` : ""}`);

export const fetchCompanionActions = () => apiFetch<CompanionAction[]>("actions/");

export const applyCompanionAction = (id: number) => apiFetch<CompanionAction>(`actions/${id}/apply/`, { method: "POST" });

export const dismissCompanionAction = (id: number) =>
  apiFetch<CompanionAction>(`actions/${id}/dismiss/`, { method: "POST" });

export const markCompanionContextSeen = (context: CompanionContext) =>
  apiFetch<{ ok: boolean }>("context-seen/", { method: "POST", body: { context } });
