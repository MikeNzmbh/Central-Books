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
  focus_items?: string[];
}

export type CompanionActionPayload = Record<string, any>;

export interface CompanionAction {
  id: number;
  context?: CompanionContext;
  action_type:
  | "bank_match_review"
  | "send_invoice_reminder"
  | "categorize_expenses_batch"
  | "overdue_invoice_reminders"
  | "uncategorized_expense_review"
  | "uncategorized_transactions_cleanup"
  | "reconciliation_period_to_close"
  | "inactive_customers_followup"
  | "spike_expense_category_review"
  | "old_unreconciled_investigate"
  | "suspense_balance_review";
  status: "open" | "applied" | "dismissed";
  confidence: number;
  summary: string;
  payload: CompanionActionPayload;
  created_at: string;
  source_snapshot_id?: number | null;
  short_title: string;
  severity: "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  impact?: string | null;
}

export type CompanionActionBehavior = "review" | "autofix" | "close";

export const ACTION_BEHAVIOR_MAP: Record<CompanionAction["action_type"], CompanionActionBehavior> = {
  bank_match_review: "autofix",  // Applies/accepts a suggested match
  overdue_invoice_reminders: "review",
  uncategorized_expense_review: "review",
  old_unreconciled_investigate: "review",
  suspense_balance_review: "review",
  inactive_customers_followup: "review",
  spike_expense_category_review: "review",
  send_invoice_reminder: "autofix",
  categorize_expenses_batch: "autofix",
  uncategorized_transactions_cleanup: "autofix",
  reconciliation_period_to_close: "close",
};

export function getPrimaryButtonLabel(action: CompanionAction): string {
  const behavior = ACTION_BEHAVIOR_MAP[action.action_type] || "review";

  // Special case for bank matching
  if (action.action_type === "bank_match_review") {
    return "Match";
  }

  switch (behavior) {
    case "review":
      return "Review";
    case "autofix":
      return "Fix now";
    case "close":
      return "Close period";
    default:
      return "Review";
  }
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
  context_reasons?: string[];
  context_severity?: string | null;
  focus_items?: string[];
  voice?: CompanionVoice;
  radar?: CompanionRadar;
  story?: CompanionStory;
}

// Focus modes for the Companion voice layer
export type FocusMode = "all_clear" | "watchlist" | "fire_drill";

// Deterministic voice snapshot (no LLM calls)
export interface CompanionVoice {
  greeting: string;              // "Good morning, Mike — you're in good shape today. 👌"
  focus_mode: FocusMode;         // "all_clear" | "watchlist" | "fire_drill"
  tone_tagline: string;          // "A few small things to tidy up."
  primary_call_to_action: string | null;  // "Review 3 unreconciled transactions in Banking."
}

// Risk Radar - 4-axis stability scoring
export interface CompanionRadarAxis {
  score: number;       // 0-100 stability score
  open_issues: number; // Count of open issues for this axis
}

export interface CompanionRadar {
  cash_reconciliation: CompanionRadarAxis;
  revenue_invoices: CompanionRadarAxis;
  expenses_receipts: CompanionRadarAxis;
  tax_compliance: CompanionRadarAxis;
}

// Story Mode - Weekly narrative from DeepSeek Reasoner
export interface CompanionStory {
  overall_summary: string;
  timeline_bullets: string[];
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

export const fetchCompanionOverview = (
  context?: CompanionContext,
  periodStart?: string,
  periodEnd?: string
) => {
  const params = new URLSearchParams();
  if (context) params.set("context", context);
  if (periodStart) params.set("period_start", periodStart);
  if (periodEnd) params.set("period_end", periodEnd);
  const suffix = params.toString();
  return apiFetch<CompanionOverview>(`overview/${suffix ? `?${suffix}` : ""}`);
};

export const fetchCompanionActions = () => apiFetch<CompanionAction[]>("actions/");

export const applyCompanionAction = (id: number) => apiFetch<CompanionAction>(`actions/${id}/apply/`, { method: "POST" });

export const dismissCompanionAction = (id: number) =>
  apiFetch<CompanionAction>(`actions/${id}/dismiss/`, { method: "POST" });

export const markCompanionContextSeen = (context: CompanionContext) =>
  apiFetch<{ ok: boolean }>("context-seen/", { method: "POST", body: { context } });
