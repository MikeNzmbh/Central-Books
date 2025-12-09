import React, { useEffect, useMemo, useState } from "react";

import type { CompanionOverview, CompanionInsight, CompanionAction } from "./api";
import { applyCompanionAction, dismissCompanionAction, fetchCompanionOverview, getPrimaryButtonLabel, ACTION_BEHAVIOR_MAP } from "./api";
import CompanionThinkingScreen from "./CompanionThinkingScreen";

const severityStyles: Record<CompanionInsight["severity"], string> = {
  info: "bg-sky-50 text-sky-700 border border-sky-100",
  warning: "bg-amber-50 text-amber-700 border border-amber-100",
  critical: "bg-rose-50 text-rose-700 border border-rose-100",
};

const actionSeverityLabel: Record<string, string> = {
  CRITICAL: "Critical priority",
  HIGH: "High priority",
  MEDIUM: "Medium priority",
  LOW: "Low priority",
  INFO: "Info",
};

const actionSeverityOrder: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  INFO: 4,
};

const CompanionPanel: React.FC = () => {
  const [data, setData] = useState<CompanionOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<{
    summary: string | null;
    context_summary?: string | null;
    insight_explanations: Record<string, string>;
    action_explanations?: Record<string, string>;
  }>({
    summary: null,
    context_summary: null,
    insight_explanations: {},
    action_explanations: {},
  });
  const [actions, setActions] = useState<CompanionAction[]>([]);
  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const searchParams = new URLSearchParams(window.location.search);
  const periodStart = searchParams.get("period_start") || searchParams.get("start_date") || undefined;
  const periodEnd = searchParams.get("period_end") || searchParams.get("end_date") || undefined;

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchCompanionOverview(undefined, periodStart, periodEnd)
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
        const msg = err?.message || "Companion temporarily unavailable.";
        setError(msg === "Request failed" ? "Companion temporarily unavailable." : msg);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [periodEnd, periodStart]);

  const healthScore = data?.health_index?.score ?? null;
  const breakdownEntries = useMemo(
    () => Object.entries(data?.health_index?.breakdown || {}),
    [data?.health_index?.breakdown]
  );
  const activeInsights = useMemo(() => {
    const insights = data?.insights || data?.top_insights || [];
    return insights.filter((insight) => !insight.is_dismissed);
  }, [data?.insights, data?.top_insights]);
  const contextReasons = (data?.context_reasons as string[]) || [];
  const contextAllClear = (data?.context_all_clear as boolean | undefined) ?? (activeInsights.length === 0 && (actions?.length || 0) === 0);
  const contextSummary =
    data?.llm_narrative?.context_summary ||
    narrative.context_summary ||
    data?.llm_narrative?.summary ||
    narrative.summary ||
    null;
  const contextSeverity = ((data?.context_severity as string | undefined) || "INFO").toUpperCase();
  const focusItems = ((data?.llm_narrative?.focus_items as string[] | undefined) || []).slice(0, 3);
  const hasCriticalInsight = activeInsights.some((insight) => insight.severity === "critical");
  const sortedActions = useMemo(
    () =>
      [...actions].sort((a, b) => {
        const rankA = actionSeverityOrder[a.severity || "INFO"] ?? 10;
        const rankB = actionSeverityOrder[b.severity || "INFO"] ?? 10;
        if (rankA !== rankB) return rankA - rankB;
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }),
    [actions]
  );
  const priorityActions = sortedActions.slice(0, 2);
  const narrativeSummary =
    (contextSummary && !contextAllClear ? contextSummary : null) ??
    narrative.summary ??
    (!hasCriticalInsight
      ? "I checked your books and everything looks fine for now. Keep reconciling regularly."
      : "Here are the priorities I'm watching based on your data.");

  const handlePrimaryAction = async (action: CompanionAction) => {
    const behavior = ACTION_BEHAVIOR_MAP[action.action_type] || "review";

    try {
      setActionBusy(action.id);

      if (behavior === "review") {
        // Navigate to the target page (automatically dismisses)
        const targetUrl = action.payload?.metadata?.target_url;
        if (targetUrl) {
          // Dismiss the action first, then navigate
          await dismissCompanionAction(action.id);
          window.location.href = targetUrl;
        } else {
          // Fallback: navigate based on context
          const context = action.context || action.payload?.metadata?.target_context;
          if (context === "invoices") window.location.href = "/ invoices/";
          else if (context === "expenses") window.location.href = "/expenses/";
          else if (context === "bank") window.location.href = "/banking/";
          else if (context === "reconciliation") window.location.href = "/reconciliation/";
          await dismissCompanionAction(action.id);
        }
      } else {
        // Auto-fix and close actions: call apply
        await applyCompanionAction(action.id);
        // Refresh after apply
        const refreshed = await fetchCompanionOverview();
        setData(refreshed);
        setActions(refreshed.actions || []);
      }
    } catch (err: any) {
      setError(err?.message || "Unable to perform action.");
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
    <div className="companion-glow" data-testid="companion-glow">
      <div className="companion-glow-inner border border-white/60 p-4 sm:p-5 shadow-sm flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Companion</p>
            <p className="mt-1 text-sm text-slate-600">Health pulse and focus areas per workspace.</p>
            <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-[2px] text-[11px] font-semibold text-slate-600">
              {contextSeverity === "HIGH" || contextSeverity === "CRITICAL"
                ? "Needs attention"
                : contextSeverity === "MEDIUM"
                  ? "Watch"
                  : "Info"}
            </span>
          </div>
        </div>

        {loading && (
          <CompanionThinkingScreen
            surfaceLabel="Dashboard"
            firstName="there"
            headline="I'm checking in on your business right now…"
          />
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
              {focusItems.length ? (
                <ul className="mt-2 ml-1 list-disc space-y-1 pl-4 text-[13px] text-slate-700">
                  {focusItems.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-700 whitespace-pre-line">
                  {narrativeSummary}
                </p>
              )}
              {contextAllClear && contextReasons.length ? (
                <ul className="mt-2 ml-1 list-disc space-y-1 pl-4 text-[12px] text-slate-600">
                  {contextReasons.slice(0, 2).map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              ) : null}
              {!contextAllClear && !actions.length && contextReasons.length ? (
                <ul className="mt-2 ml-1 list-disc space-y-1 pl-4 text-[12px] text-slate-600">
                  {contextReasons.slice(0, 2).map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              ) : null}
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

            {sortedActions.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">Suggested actions</p>
                  <span className="text-[11px] text-slate-500">{sortedActions.length} pending</span>
                </div>
                {priorityActions.length ? (
                  <div className="rounded-2xl border border-amber-100 bg-amber-50/80 px-3 py-2 text-[12px] text-amber-800">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center rounded-full bg-white px-2 py-[2px] text-[10px] font-semibold text-amber-700">
                        Priority
                      </span>
                      {priorityActions.map((action) => (
                        <span key={action.id} className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-[2px] text-[11px] font-semibold text-amber-800">
                          {action.short_title || action.summary}
                          <span className="text-[10px] font-semibold uppercase">
                            {actionSeverityLabel[action.severity] || action.severity}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="space-y-2">
                  {sortedActions.map((action) => (
                    <article
                      key={action.id}
                      className="rounded-2xl border border-slate-100 bg-white px-3 py-3 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex flex-col gap-1">
                          <p className="text-sm font-semibold text-slate-900">{action.summary}</p>
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600">
                            <span className="rounded-full bg-slate-100 px-2 py-[2px] uppercase">
                              {actionSeverityLabel[action.severity] || action.severity}
                            </span>
                            {action.short_title && <span className="text-slate-500">{action.short_title}</span>}
                          </span>
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
                          onClick={() => handlePrimaryAction(action)}
                          disabled={actionBusy === action.id}
                        >
                          {actionBusy === action.id ? "Working..." : getPrimaryButtonLabel(action)}
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
    </div>
  );
};

export default CompanionPanel;
