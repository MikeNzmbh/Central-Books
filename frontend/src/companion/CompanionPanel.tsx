import React, { useEffect, useMemo, useState } from "react";

import type { CompanionOverview, CompanionInsight, CompanionAction } from "./api";
import { applyCompanionAction, dismissCompanionAction, fetchCompanionOverview } from "./api";

const severityStyles: Record<CompanionInsight["severity"], string> = {
  info: "bg-sky-50 text-sky-700 border border-sky-100",
  warning: "bg-amber-50 text-amber-700 border border-amber-100",
  critical: "bg-rose-50 text-rose-700 border border-rose-100",
};

const CompanionPanel: React.FC = () => {
  const [data, setData] = useState<CompanionOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<{
    summary: string | null;
    insight_explanations: Record<string, string>;
    action_explanations?: Record<string, string>;
  }>({
    summary: null,
    insight_explanations: {},
    action_explanations: {},
  });
  const [actions, setActions] = useState<CompanionAction[]>([]);
  const [actionBusy, setActionBusy] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchCompanionOverview()
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setError(null);
        if (payload.health_index?.created_at) {
          setLastUpdated(payload.health_index.created_at);
        }
        if (payload.llm_narrative) {
          setNarrative({
            summary: payload.llm_narrative.summary,
            insight_explanations: payload.llm_narrative.insight_explanations || {},
            action_explanations: payload.llm_narrative.action_explanations || {},
          });
        } else {
          setNarrative({ summary: null, insight_explanations: {}, action_explanations: {} });
        }
        setActions(payload.actions || []);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.message || "Unable to load Companion data.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const healthScore = data?.health_index?.score ?? null;
  const breakdownEntries = useMemo(
    () => Object.entries(data?.health_index?.breakdown || {}),
    [data?.health_index?.breakdown]
  );
  const activeInsights = useMemo(() => {
    const insights = data?.insights || data?.top_insights || [];
    return insights.filter((insight) => !insight.is_dismissed);
  }, [data?.insights, data?.top_insights]);
  const hasCriticalInsight = activeInsights.some((insight) => insight.severity === "critical");
  const narrativeSummary =
    narrative.summary ??
    (!hasCriticalInsight
      ? "I checked your books and everything looks fine for now. Keep reconciling regularly."
      : "Here are the priorities I'm watching based on your data.");

  const handleApply = async (id: number) => {
    try {
      setActionBusy(id);
      await applyCompanionAction(id);
      // Refresh actions/overview
      const refreshed = await fetchCompanionOverview();
      setData(refreshed);
      setActions(refreshed.actions || []);
    } catch (err: any) {
      setError(err?.message || "Unable to apply action.");
    } finally {
      setActionBusy(null);
    }
  };

  const handleDismiss = async (id: number) => {
    try {
      setActionBusy(id);
      await dismissCompanionAction(id);
      const refreshed = await fetchCompanionOverview();
      setData(refreshed);
      setActions(refreshed.actions || []);
    } catch (err: any) {
      setError(err?.message || "Unable to dismiss action.");
    } finally {
      setActionBusy(null);
    }
  };

  return (
    <div className="rounded-3xl border border-slate-100 bg-white/95 p-4 sm:p-5 shadow-sm flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Companion</p>
          <p className="mt-1 text-sm text-slate-600">Health pulse and focus areas per workspace.</p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold text-slate-50">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          {healthScore !== null ? `Health ${healthScore}/100` : "Loading"}
        </span>
      </div>

      {loading && (
        <div className="space-y-3 text-sm text-slate-500">
          <div className="h-3 w-28 animate-pulse rounded-full bg-slate-100" />
          <div className="h-2 w-full animate-pulse rounded-full bg-slate-100" />
          <div className="h-2 w-5/6 animate-pulse rounded-full bg-slate-100" />
        </div>
      )}

      {error && !loading && (
        <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="rounded-2xl border border-slate-100 bg-white p-3 shadow-sm">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-slate-500">
              <span>AI Companion</span>
            </div>
            <p className="mt-2 text-sm text-slate-700 whitespace-pre-line">
              {narrativeSummary}
            </p>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {/* Breakdown - Left 50% */}
            <div className="rounded-2xl bg-slate-50/80 border border-slate-100 p-3">
              <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-slate-500">
                <span>Breakdown</span>
                {lastUpdated && (
                  <span className="text-slate-400">
                    {new Date(lastUpdated).toLocaleDateString()}
                  </span>
                )}
              </div>
              <div className="mt-2 grid gap-2">
                {breakdownEntries.length ? (
                  breakdownEntries.map(([key, value]) => (
                    <div key={key}>
                      <div className="flex items-center justify-between gap-3 text-[12px] text-slate-700">
                        <span className="capitalize truncate">{key.replace("_", " ")}</span>
                        <span className="font-semibold text-slate-900 shrink-0">{value}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-sky-400 to-slate-900 transition-all"
                          style={{ width: `${Math.min(100, value)}%` }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No breakdown yet. Add activity to this workspace.</p>
                )}
              </div>
            </div>

            {/* Insights - Right 50% */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">Insights</p>
                <span className="text-[11px] text-slate-500">
                  {activeInsights.length ? `${activeInsights.length} active` : "All clear"}
                </span>
              </div>
              <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                {activeInsights.length ? (
                  activeInsights.slice(0, 3).map((insight) => (
                    <article
                      key={insight.id}
                      className="rounded-2xl border border-slate-100 bg-white px-3 py-2.5 shadow-sm"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold ${severityStyles[insight.severity]}`}
                        >
                          {insight.severity.toUpperCase()}
                        </div>
                      </div>
                      <h3 className="mt-1.5 text-sm font-semibold text-slate-900">{insight.title}</h3>
                      <p className="mt-1 text-[13px] text-slate-600 line-clamp-2">{insight.body}</p>
                      {narrative.insight_explanations?.[String(insight.id)] && (
                        <p className="mt-1 text-[12px] text-slate-500">
                          {narrative.insight_explanations[String(insight.id)]}
                        </p>
                      )}
                    </article>
                  ))
                ) : (
                  <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                    No open alerts. Keep reconciling and logging activity to stay healthy.
                  </div>
                )}
              </div>
            </div>
          </div>

          {actions.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">Suggested actions</p>
                <span className="text-[11px] text-slate-500">{actions.length} pending</span>
              </div>
              <div className="space-y-2">
                {actions.map((action) => (
                  <article
                    key={action.id}
                    className="rounded-2xl border border-slate-100 bg-white px-3 py-3 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-col gap-1">
                        <p className="text-sm font-semibold text-slate-900">{action.summary}</p>
                        {narrative.action_explanations?.[String(action.id)] && (
                          <p className="text-[12px] text-slate-500">
                            {narrative.action_explanations[String(action.id)]}
                          </p>
                        )}
                        {action.confidence ? (
                          <span className="text-[11px] text-slate-500">
                            Confidence {(Number(action.confidence) * 100).toFixed(0)}%
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-full bg-emerald-600 px-3 py-1 text-[12px] font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                        onClick={() => handleApply(action.id)}
                        disabled={actionBusy === action.id}
                      >
                        {actionBusy === action.id ? "Applying..." : "Apply"}
                      </button>
                      <button
                        className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[12px] font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
                        onClick={() => handleDismiss(action.id)}
                        disabled={actionBusy === action.id}
                      >
                        {actionBusy === action.id ? "Working..." : "Dismiss"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default CompanionPanel;
