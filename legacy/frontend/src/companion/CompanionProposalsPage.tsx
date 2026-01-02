import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { useAISettings } from "./useAISettings";
import { useCompanionProposals } from "./useCompanionProposals";
import type { ShadowEvent } from "./apiV2";
import { usePermissions } from "../hooks/usePermissions";

type Cluster = {
  key: string;
  title: string;
  events: ShadowEvent[];
  safeBatchApprove: boolean;
};

function riskReasons(event: ShadowEvent): string[] {
  const hil = event.human_in_the_loop || {};
  const rr = hil.risk_reasons;
  return Array.isArray(rr) ? rr.map(String) : [];
}

function proposalGroup(event: ShadowEvent): string {
  const meta = (event.metadata || {}) as any;
  const group = meta.proposal_group || meta.proposalGroup || meta.cluster || "";
  return String(group || "").trim() || event.event_type || "Proposals";
}

function proposalQuestions(event: ShadowEvent): string[] {
  const meta = (event.metadata || {}) as any;
  const qs = meta.questions;
  return Array.isArray(qs) ? qs.map(String) : [];
}

function eventLabel(event: ShadowEvent): string {
  const data = event.data || {};
  return (
    data.bank_transaction_description ||
    (data.splits?.[0]?.description as string) ||
    event.event_type ||
    "Proposal"
  );
}

function formatMoney(raw: any): string {
  const n = Number(raw);
  if (Number.isFinite(n)) return n.toFixed(2);
  return String(raw ?? "");
}

const CompanionProposalsPage: React.FC = () => {
  const { workspace, can } = usePermissions();
  const { data: settings, loading: settingsLoading, patch: patchSettings } = useAISettings({
    workspaceId: workspace?.businessId,
  });
  const { events, loading, error, refresh, apply, reject, counts } = useCompanionProposals({
    workspaceId: workspace?.businessId,
  });
  const [selected, setSelected] = useState<ShadowEvent | null>(null);
  const [busyCluster, setBusyCluster] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const applyDisabled =
    !settings?.global_ai_enabled ||
    !settings?.settings?.ai_enabled ||
    !!settings?.settings?.kill_switch ||
    settings?.settings?.ai_mode === "shadow_only";

  const clusters: Cluster[] = useMemo(() => {
    const grouped = new Map<string, ShadowEvent[]>();
    for (const e of events) {
      const key = proposalGroup(e);
      grouped.set(key, [...(grouped.get(key) || []), e]);
    }
    const out: Cluster[] = [];
    for (const [key, clusterEvents] of grouped.entries()) {
      const safeBatchApprove = clusterEvents.every(
        (e) => riskReasons(e).length === 0 && proposalQuestions(e).length === 0,
      );
      out.push({
        key,
        title: `${key} (${clusterEvents.length})`,
        events: clusterEvents,
        safeBatchApprove,
      });
    }
    return out.sort((a, b) => b.events.length - a.events.length);
  }, [events]);

  const onApproveCluster = async (cluster: Cluster) => {
    if (!cluster.safeBatchApprove || applyDisabled) return;
    setBusyCluster(cluster.key);
    setActionError(null);
    try {
      for (const e of cluster.events) {
        await apply(e.id);
      }
    } catch (e: any) {
      setActionError(e?.message || "Failed to apply proposal");
    } finally {
      setBusyCluster(null);
    }
  };

  const onApproveOne = async (event: ShadowEvent) => {
    if (applyDisabled) return;
    setActionError(null);
    try {
      await apply(event.id);
    } catch (e: any) {
      setActionError(e?.message || "Failed to apply proposal");
    }
  };

  const onRejectOne = async (event: ShadowEvent) => {
    setActionError(null);
    try {
      await reject(event.id, "Rejected in UI");
    } catch (e: any) {
      setActionError(e?.message || "Failed to reject proposal");
    }
  };

  const onSwitchToSuggestOnly = async () => {
    if (!can("workspace.manage_ai", "edit")) return;
    const ok = window.confirm(
      "Switch AI mode from shadow_only → suggest_only?\n\nThis enables applying proposals (human-triggered) into the canonical ledger. Autopilot remains disabled.",
    );
    if (!ok) return;
    setActionError(null);
    try {
      await patchSettings({ ai_mode: "suggest_only" });
    } catch (e: any) {
      setActionError(e?.message || "Failed to switch AI mode");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Companion v2</p>
            <h1 className="text-2xl font-semibold text-slate-900">Shadow Ledger Proposals</h1>
            <p className="text-sm text-slate-600 mt-1">
              {settingsLoading ? (
                "Loading settings…"
              ) : (
                <>
                  Mode: <span className="font-medium">{settings?.settings.ai_mode || "unknown"}</span>{" "}
                  <span className="text-slate-400">·</span>{" "}
                  Global: <span className="font-medium">{settings?.global_ai_enabled ? "on" : "off"}</span>
                </>
              )}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link to="/" className="text-sm text-slate-600 hover:text-slate-900">
              Back to Companion
            </Link>
            <button
              className="inline-flex items-center gap-2 rounded-md bg-white border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              onClick={refresh}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        <div className="mt-6 bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-700">
              <span className="font-medium">{counts.total}</span> proposals
            </div>
            <div className="text-xs text-slate-500">
              {Object.entries(counts.byType).map(([k, v]) => (
                <span key={k} className="ml-3">
                  {k}: {v}
                </span>
              ))}
            </div>
          </div>
        </div>

        {applyDisabled && !settingsLoading && (
          <div className="mt-4 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg p-3 text-sm flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="font-medium">Apply is disabled in shadow-only mode.</div>
              <div className="text-amber-800">
                You can review and reject proposals. To promote into the canonical ledger, switch to suggest-only.
              </div>
            </div>
            {can("workspace.manage_ai", "edit") && (
              <button
                className="shrink-0 rounded-md bg-amber-900 text-white px-3 py-2 text-sm hover:bg-amber-950"
                onClick={onSwitchToSuggestOnly}
              >
                Switch to suggest-only
              </button>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>
        )}
        {actionError && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{actionError}</div>
        )}

        <div className="mt-6 grid grid-cols-1 gap-4">
          {clusters.length === 0 && !loading ? (
            <div className="bg-white border border-slate-200 rounded-xl p-6 text-slate-600 text-sm">
              No proposals found.
            </div>
          ) : (
            clusters.map((cluster) => (
              <div key={cluster.key} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
                  <div className="font-medium text-slate-900">{cluster.title}</div>
                  <div className="flex items-center gap-2">
                    {cluster.safeBatchApprove && (
                      <button
                        className="rounded-md bg-emerald-600 text-white px-3 py-1.5 text-sm hover:bg-emerald-700 disabled:opacity-60"
                        onClick={() => onApproveCluster(cluster)}
                        disabled={busyCluster === cluster.key}
                      >
                        {busyCluster === cluster.key ? "Approving…" : "Approve cluster"}
                      </button>
                    )}
                    {!cluster.safeBatchApprove && (
                      <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-1">
                        Mixed / high risk — review individually
                      </span>
                    )}
                  </div>
                </div>

                <div className="divide-y divide-slate-100">
                  {cluster.events.map((e) => {
                    const data = e.data || {};
                    const splits = (data.splits || []) as any[];
                    const amount = data.bank_transaction_amount;
                    const label = eventLabel(e);
                    const rr = riskReasons(e);
                    const qs = proposalQuestions(e);
                    return (
                      <div key={e.id} className="px-4 py-3 flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-slate-900 truncate">{label}</div>
                          <div className="text-xs text-slate-500 mt-1">
                            {data.bank_transaction_date ? data.bank_transaction_date : ""} · <span className="font-mono-soft">${formatMoney(amount)}</span>
                            {splits?.[0]?.account_name ? ` · → ${splits[0].account_name}` : ""}
                          </div>
                          {rr.length > 0 && (
                            <div className="mt-2 text-xs text-amber-700">
                              Risk: {rr.join(", ")}
                            </div>
                          )}
                          {qs.length > 0 && (
                            <div className="mt-2 text-xs text-slate-700">
                              <div className="font-semibold text-slate-700">Questions</div>
                              <ul className="list-disc pl-5 mt-1 space-y-0.5">
                                {qs.map((q, i) => (
                                  <li key={i}>{q}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm hover:bg-slate-50"
                            onClick={() => setSelected(e)}
                          >
                            Why
                          </button>
                          <button
                            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm hover:bg-slate-50"
                            onClick={() => void onRejectOne(e)}
                          >
                            Reject
                          </button>
                          <button
                            className={`rounded-md px-3 py-1.5 text-sm ${applyDisabled
                                ? "bg-slate-200 text-slate-500 cursor-not-allowed"
                                : "bg-blue-600 text-white hover:bg-blue-700"
                              }`}
                            onClick={() => void onApproveOne(e)}
                            disabled={applyDisabled}
                          >
                            Approve
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {selected && (
          <div className="fixed inset-0 bg-black/30 flex items-end sm:items-center justify-center p-4" onClick={() => setSelected(null)}>
            <div
              className="w-full max-w-2xl bg-white rounded-xl shadow-lg border border-slate-200 p-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-widest text-slate-500">Explainability</div>
                  <div className="text-lg font-semibold text-slate-900">{eventLabel(selected)}</div>
                </div>
                <button className="text-slate-500 hover:text-slate-900" onClick={() => setSelected(null)}>
                  Close
                </button>
              </div>

              <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Actor</div>
                  <div className="font-mono text-xs mt-1">{selected.actor}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Confidence</div>
                  <div className="mt-1">{selected.confidence_score ?? "n/a"}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Logic Trace</div>
                  <div className="font-mono text-xs mt-1">{selected.logic_trace_id || "n/a"}</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-xs text-slate-500">Policy Constraint</div>
                  <div className="mt-1">{selected.business_profile_constraint || "n/a"}</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="text-xs font-semibold uppercase tracking-widest text-slate-500">Rationale</div>
                <div className="mt-2 text-sm text-slate-800 whitespace-pre-wrap">
                  {selected.rationale || "No rationale provided."}
                </div>
              </div>

              {proposalQuestions(selected).length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-semibold uppercase tracking-widest text-slate-500">Questions</div>
                  <ul className="mt-2 text-sm text-slate-800 list-disc pl-5 space-y-1">
                    {proposalQuestions(selected).map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanionProposalsPage;
