import { buildApiUrl, getAccessToken } from "@/api/client";
import { ensureCsrfToken } from "@/utils/csrf";

export type EngineQueueItem = {
  id: number;
  work_type: string;
  surface: string;
  status: string;
  risk_level: "low" | "medium" | "high" | string;
  title: string;
  summary: string;
  action_id?: number | null;
  target_url?: string | null;
  due_at?: string | null;
};

export type EngineQueuesPayload = {
  generated_at: string;
  mode: string;
  trust_score: number;
  stats: {
    ready: number;
    needs_attention: number;
    waiting_approval: number;
    applied_last_day: number;
    dismissed_last_day: number;
    breaker_events_last_day: number;
  };
  ready_queue: EngineQueueItem[];
  needs_attention_queue: EngineQueueItem[];
  job_totals?: {
    queued: number;
    running: number;
    blocked: number;
    failed: number;
    succeeded: number;
    canceled: number;
  } | null;
  job_by_agent?: Array<{ agent: string; queued: number; running: number; blocked: number }> | null;
  top_blockers?: Array<{ kind: string; status: string; reason: string; updated_at: string }> | null;
};

export type EngineQueuesResult = {
  source: "snapshot" | "live";
  stale: boolean;
  data: EngineQueuesPayload;
};

export type EngineStatusPayload = {
  ok: boolean;
  tenant_id: number;
  mode: string;
  breakers: {
    recent: number;
    ok: boolean;
  };
  budgets: { tokens_per_day: number; tool_calls_per_day: number; runs_per_day: number };
  last_tick_at?: string | null;
  last_materialized_at?: string | null;
  engine_version: string;
  mock_mode: { llm: string; tools: string };
};

const buildHeaders = async (method: "GET" | "POST") => {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    const csrf = await ensureCsrfToken();
    if (csrf) headers["X-CSRFToken"] = csrf;
  }
  return headers;
};

export async function fetchCockpitQueues(): Promise<EngineQueuesResult | null> {
  try {
    const res = await fetch(buildApiUrl("/api/companion/cockpit/queues"), {
      credentials: "same-origin",
      headers: await buildHeaders("GET"),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const payload = data?.data || data;
    if (!payload) return null;
    return {
      source: data?.source || "live",
      stale: Boolean(data?.stale),
      data: payload as EngineQueuesPayload,
    };
  } catch {
    return null;
  }
}

export async function fetchCockpitStatus(): Promise<EngineStatusPayload | null> {
  try {
    const res = await fetch(buildApiUrl("/api/companion/cockpit/status"), {
      credentials: "same-origin",
      headers: await buildHeaders("GET"),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data as EngineStatusPayload;
  } catch {
    return null;
  }
}

export async function tickEngine(tenantId?: number | "all"): Promise<boolean> {
  try {
    const res = await fetch(buildApiUrl("/api/companion/autonomy/tick"), {
      method: "POST",
      credentials: "same-origin",
      headers: await buildHeaders("POST"),
      body: JSON.stringify({ tenant: tenantId === "all" ? "all" : undefined, tenant_id: tenantId }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function materializeEngine(tenantId?: number | "all"): Promise<boolean> {
  try {
    const res = await fetch(buildApiUrl("/api/companion/autonomy/materialize"), {
      method: "POST",
      credentials: "same-origin",
      headers: await buildHeaders("POST"),
      body: JSON.stringify({ tenant: tenantId === "all" ? "all" : undefined, tenant_id: tenantId }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function applyEngineBatch(actionIds: number[]): Promise<boolean> {
  try {
    const res = await fetch(buildApiUrl("/api/companion/autonomy/actions/batch-apply"), {
      method: "POST",
      credentials: "same-origin",
      headers: await buildHeaders("POST"),
      body: JSON.stringify({ action_ids: actionIds }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
