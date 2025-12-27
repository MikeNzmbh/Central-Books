import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  CreditCard,
  FileText,
  BookOpen,
  Landmark,
  RefreshCw,
  Settings,
} from "lucide-react";
import { toCustomerCopy } from "./companionCopy";

// --- TYPES ----------------------------------------------------------------

type RiskLevel = "low" | "medium" | "high" | "unknown" | "none";

interface RunSummary {
  id: number;
  created_at: string;
  period_start?: string | null;
  period_end?: string | null;
  risk_level?: RiskLevel | null;
  documents_total?: number;
  high_risk_count?: number;
  errors_count?: number;
  transactions_total?: number;
  unreconciled?: number;
  trace_id?: string | null;
}

interface SurfaceSummary {
  recent_runs: RunSummary[];
  totals_last_30_days: Record<string, number>;
  open_issues_count?: number;
  high_risk_issues_count?: number;
  headline_issue?: { id: number; title: string; severity: string } | null;
}

interface CloseReadiness {
  status: "ready" | "not_ready";
  blocking_reasons: string[];
  blocking_items?: { reason: string; task_code?: string | null; surface?: string | null }[];
}

interface CompanionSummary {
  ai_companion_enabled: boolean;
  surfaces: {
    receipts: SurfaceSummary;
    invoices: SurfaceSummary;
    books_review: SurfaceSummary;
    bank_review: SurfaceSummary;
  };
  global?: {
    open_issues_total?: number;
    open_issues_by_severity?: Record<string, number>;
    open_issues_by_surface?: Record<string, number>;
    high_risk_items_30d?: Record<string, number>;
    agent_retries_30d?: number;
  };
  close_readiness?: CloseReadiness;
  generated_at?: string;
  stale?: boolean;
  feed_generated_at?: string;
  feed_stale?: boolean;
}

type CompanionIssue = {
  id: number;
  title: string;
  severity: string;
  surface: string;
  recommended_action?: string;
};

interface SurfaceConfig {
  key: keyof CompanionSummary["surfaces"];
  title: string;
  icon: React.FC<{ className?: string }>;
  surfaceFilter: string;
}

// --- UTILITIES ------------------------------------------------------------

const formatTimeAgo = (isoDate: string): string => {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? "s" : ""} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays === 1) return "Yesterday";
  return `${diffDays} days ago`;
};

// --- SURFACE CONFIG -------------------------------------------------------

const surfaceConfigs: SurfaceConfig[] = [
  { key: "receipts", title: "Receipts", icon: FileText, surfaceFilter: "receipts" },
  { key: "invoices", title: "Invoices", icon: CreditCard, surfaceFilter: "invoices" },
  { key: "books_review", title: "Books", icon: BookOpen, surfaceFilter: "books" },
  { key: "bank_review", title: "Bank", icon: Landmark, surfaceFilter: "bank" },
];

// --- COMPONENT ------------------------------------------------------------

const CompanionControlTowerPage: React.FC = () => {
  const [summary, setSummary] = useState<CompanionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [issues, setIssues] = useState<CompanionIssue[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Clover Books · Companion Control Tower";
  }, []);

  const loadSummary = async () => {
    setLoading(true);
    try {
      const [summaryRes, issuesRes] = await Promise.all([
        fetch("/api/agentic/companion/summary", {
          method: "GET",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        }),
        fetch("/api/agentic/companion/issues?status=open", {
          method: "GET",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        }),
      ]);

      const summaryJson = await summaryRes.json();
      if (!summaryRes.ok) throw new Error(summaryJson.error || "Failed to load summary");
      setSummary(summaryJson);

      const issuesJson = await issuesRes.json();
      if (!issuesRes.ok) throw new Error(issuesJson.error || "Failed to load issues");
      setIssues(issuesJson.issues || []);

      setLastUpdatedAt(new Date().toISOString());
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to load summary");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  const totalOpenIssues = summary?.global?.open_issues_total ?? issues.length;
  const highSeverityIssues = summary?.global?.open_issues_by_severity?.high ??
    issues.filter((i) => i.severity === "high").length;

  const highRiskCounts = summary?.global?.high_risk_items_30d || { receipts: 0, invoices: 0, bank_transactions: 0 };
  const totalHighRisk = (highRiskCounts.receipts || 0) + (highRiskCounts.invoices || 0) + (highRiskCounts.bank_transactions || 0);
  const agentRetries = summary?.global?.agent_retries_30d || 0;
  const healthScore = Math.max(0, Math.min(100, 100 - totalHighRisk * 2 - Math.floor(agentRetries / 2)));

  const focusItems = useMemo(() => issues.slice(0, 3), [issues]);

  const getSurfaceData = (key: keyof CompanionSummary["surfaces"]) => {
    if (!summary) return { lastRun: "No runs", status: "Syncing", openIssues: 0 };
    const surface = summary.surfaces[key];
    const latest = surface?.recent_runs?.[0];
    return {
      lastRun: latest?.created_at ? formatTimeAgo(latest.created_at) : "No runs yet",
      status: surface?.open_issues_count ? `${surface.open_issues_count} open` : "All clear",
      openIssues: surface?.open_issues_count || 0,
    };
  };

  if (loading && !summary) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-slate-300 border-t-transparent mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading Companion data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-8">
        <div className="p-4 text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/60 text-slate-900 pb-12">
      <div className="relative max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Companion Control Tower</h1>
            <p className="text-sm text-slate-500 mt-1">
              A calm, always-on view of your books and what needs attention.
            </p>
            {lastUpdatedAt && (
              <p className="text-xs text-slate-400 mt-1">
                Updated {formatTimeAgo(lastUpdatedAt)}
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <a
              href="/settings/account"
              className="h-9 px-4 rounded-lg bg-white border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition"
            >
              <Settings className="w-4 h-4" />
              Configure
            </a>
            <Link
              to="?panel=suggestions"
              className="h-9 px-4 rounded-lg bg-white border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition"
            >
              AI Suggestions
            </Link>
            <button
              onClick={loadSummary}
              disabled={loading}
              className="h-9 px-4 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition flex items-center gap-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>
        </div>

        {summary && !summary.ai_companion_enabled && (
          <div className="mb-6 rounded-lg border border-slate-200 bg-slate-100 text-slate-700 px-4 py-3 text-sm">
            Companion is disabled in Settings. {""}
            <a className="underline font-semibold" href="/settings/account">Go to settings</a>
          </div>
        )}

        {/* Top cards */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Health Pulse */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Activity className="w-4 h-4" />
                Health Pulse
              </div>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                highSeverityIssues > 0 ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"
              }`}>
                {highSeverityIssues > 0 ? "Needs attention" : "All clear"}
              </span>
            </div>
            <div className="mt-3 flex items-end justify-between">
              <div>
                <div className="text-3xl font-semibold text-slate-900">{healthScore}</div>
                <div className="text-xs text-slate-500">Health score</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium text-slate-700">{totalOpenIssues} open items</div>
                <div className="text-xs text-slate-400">{highSeverityIssues} need attention</div>
              </div>
            </div>
            <div className="mt-4 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full rounded-full bg-slate-900" style={{ width: `${healthScore}%` }} />
            </div>
          </div>

          {/* Today's Focus */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <AlertTriangle className="w-4 h-4" />
                Today's Focus
              </div>
              <Link to="?panel=issues" className="text-xs text-slate-500 hover:text-slate-700">
                Open issues
              </Link>
            </div>
            {focusItems.length === 0 ? (
              <div className="mt-4 flex items-center gap-3 text-sm text-slate-600">
                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                Nothing urgent right now.
              </div>
            ) : (
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {focusItems.map((item) => (
                  <li key={item.id} className="flex items-start gap-2">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-slate-400" />
                    <span>{toCustomerCopy(item.title)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Close Readiness */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Clock className="w-4 h-4" />
                Close Readiness
              </div>
              <Link to="?panel=close" className="text-xs text-slate-500 hover:text-slate-700">
                Open close panel
              </Link>
            </div>
            {summary?.close_readiness ? (
              <div className="mt-3">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    summary.close_readiness.status === "ready"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-700"
                  }`}>
                    {summary.close_readiness.status === "ready" ? "Close-ready" : "Not close-ready"}
                  </span>
                  {summary.close_readiness.blocking_reasons.length > 0 && (
                    <span className="text-xs text-slate-500">
                      {summary.close_readiness.blocking_reasons.length} blocker{summary.close_readiness.blocking_reasons.length > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                {summary.close_readiness.blocking_reasons.length > 0 && (
                  <ul className="mt-2 text-xs text-slate-600 space-y-1">
                    {summary.close_readiness.blocking_reasons.slice(0, 2).map((reason, idx) => (
                      <li key={idx}>• {toCustomerCopy(reason)}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-600">Set up close readiness to track month-end progress.</p>
            )}
          </div>
        </div>

        {/* Surfaces grid */}
        <div className="mt-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Surfaces</h2>
            <Link to="?panel=suggestions" className="text-xs text-slate-500 hover:text-slate-700">
              View all suggestions
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {surfaceConfigs.map((surface) => {
              const data = getSurfaceData(surface.key);
              const Icon = surface.icon;
              return (
                <Link
                  key={surface.key}
                  to={`?panel=suggestions&surface=${surface.surfaceFilter}`}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm hover:shadow-md transition"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <Icon className="w-4 h-4" />
                      {surface.title}
                    </div>
                    <span className="text-[11px] text-slate-400">{data.lastRun}</span>
                  </div>
                  <div className="mt-3 text-sm text-slate-700 font-medium">{data.status}</div>
                  <div className="mt-1 text-xs text-slate-400">Open items: {data.openIssues}</div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CompanionControlTowerPage;
