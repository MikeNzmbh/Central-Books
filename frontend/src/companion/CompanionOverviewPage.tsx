import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
  Settings,
  Zap,
  Clock,
  TrendingUp,
  Sparkles,
  FileText,
  CreditCard,
  BookOpen,
  Landmark,
} from "lucide-react";

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

// Radar axis type
interface RadarAxis {
  score: number;
  open_issues: number;
}

// Radar type
interface CompanionRadar {
  cash_reconciliation: RadarAxis;
  revenue_invoices: RadarAxis;
  expenses_receipts: RadarAxis;
  tax_compliance: RadarAxis;
}

// Story type
interface CompanionStory {
  overall_summary: string;
  timeline_bullets: string[];
}

// Coverage axis type
interface CoverageAxis {
  coverage_percent: number;
  total_items: number;
  covered_items: number;
}

// Coverage type (books is optional - may be omitted until we have real metrics)
interface CompanionCoverage {
  receipts: CoverageAxis;
  invoices: CoverageAxis;
  banking: CoverageAxis;
  books?: CoverageAxis;  // Optional: omitted when no real books metrics available
}

// Close-readiness type
interface CloseReadiness {
  status: "ready" | "not_ready";
  blocking_reasons: string[];
}

// Playbook step type
interface PlaybookStep {
  label: string;
  surface: "receipts" | "invoices" | "bank" | "books";
  severity: "low" | "medium" | "high";
  url: string;
  issue_id?: number | null;
}

interface CompanionSummary {
  ai_companion_enabled: boolean;
  surfaces: {
    receipts: SurfaceSummary;
    invoices: SurfaceSummary;
    books_review: SurfaceSummary;
    bank_review: SurfaceSummary;
  };
  global: {
    headline_issue?: { id: number; title: string; severity: string; surface: string };
    open_issues_total?: number;
    open_issues_by_severity?: Record<string, number>;
    open_issues_by_surface?: Record<string, number>;
    last_books_review: {
      run_id: number;
      period_start: string;
      period_end: string;
      overall_risk_score?: string | number | null;
      risk_level?: RiskLevel | null;
      trace_id?: string | null;
    } | null;
    high_risk_items_30d: Record<string, number>;
    agent_retries_30d: number;
  };
  radar?: CompanionRadar;
  story?: CompanionStory;
  coverage?: CompanionCoverage;
  close_readiness?: CloseReadiness;
  playbook?: PlaybookStep[];
}

interface SurfaceConfig {
  key: string;
  title: string;
  icon: React.FC<{ className?: string }>;
  href: string;
}

type CompanionIssue = {
  id: number;
  title: string;
  severity: string;
  surface: string;
  recommended_action?: string;
};

// --- SURFACE CONFIG -------------------------------------------------------

const surfaceConfigs: SurfaceConfig[] = [
  { key: "receipts", title: "Receipts", icon: FileText, href: "/receipts" },
  { key: "invoices", title: "Invoices", icon: CreditCard, href: "/invoices/ai/" },
  { key: "books_review", title: "Books Review", icon: BookOpen, href: "/books-review" },
  { key: "bank_review", title: "Bank Review", icon: Landmark, href: "/bank-review" },
];

// --- COMPONENTS -----------------------------------------------------------

const StatusBadge: React.FC<{ children: React.ReactNode; variant?: string; className?: string }> = ({
  children,
  variant = "neutral",
  className = ""
}) => {
  const styles: Record<string, string> = {
    neutral: "bg-slate-100 text-slate-600 border-slate-200",
    success: "bg-emerald-50 text-emerald-700 border-emerald-200/60",
    warning: "bg-amber-50 text-amber-700 border-amber-200/60",
    error: "bg-rose-50 text-rose-700 border-rose-200/60",
    blue: "bg-blue-50 text-blue-900 border-blue-200/60",
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-md border ${styles[variant] || styles.neutral} ${className}`}>
      {children}
    </span>
  );
};

const SeverityPill: React.FC<{ value: string }> = ({ value }) => {
  const map: Record<string, string> = {
    high: "bg-rose-100 text-rose-700 border border-rose-200",
    medium: "bg-amber-100 text-amber-800 border border-amber-200",
    low: "bg-slate-100 text-slate-700 border border-slate-200",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${map[value] || map.low}`}>
      {value}
    </span>
  );
};

const Card: React.FC<{ children: React.ReactNode; className?: string; noPadding?: boolean }> = ({
  children,
  className = "",
  noPadding = false
}) => (
  <div className={`bg-white border border-slate-200/80 shadow-[0_2px_8px_rgba(0,0,0,0.02)] rounded-xl overflow-hidden hover:shadow-[0_4px_16px_rgba(0,0,0,0.04)] hover:border-slate-300 transition-all duration-300 ${className}`}>
    {noPadding ? children : <div className="p-5">{children}</div>}
  </div>
);

const RadialProgress: React.FC<{ percentage: number; size?: number; strokeWidth?: number; color?: string }> = ({
  percentage,
  size = 60,
  strokeWidth = 5,
  color = "#10b981"
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90 w-full h-full">
        <circle
          className="text-slate-100"
          strokeWidth={strokeWidth}
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <motion.circle
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: "easeOut" }}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeLinecap="round"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-sm font-bold text-slate-700">
        {percentage}
      </div>
    </div>
  );
};

const MiniTrend: React.FC = () => (
  <div className="flex items-end gap-[2px] h-6">
    {[40, 65, 50, 80, 55, 90, 75].map((h, i) => (
      <motion.div
        key={i}
        initial={{ height: 0 }}
        animate={{ height: `${h}%` }}
        transition={{ delay: i * 0.05, duration: 0.5 }}
        className="w-1.5 bg-blue-100 rounded-sm"
      />
    ))}
  </div>
);

const formatTimeAgo = (isoDate: string): string => {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays === 1) return "Yesterday";
  return `${diffDays} days ago`;
};

// --- MAIN COMPONENT -------------------------------------------------------

const CompanionOverviewPage: React.FC = () => {
  const [summary, setSummary] = useState<CompanionSummary | null>(null);
  const [healthScore, setHealthScore] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [issues, setIssues] = useState<CompanionIssue[]>([]);

  const loadSummary = async () => {
    setLoading(true);
    try {
      // Fetch both APIs in parallel - summary for surfaces, issues for checklist
      const [summaryRes, issuesRes] = await Promise.all([
        fetch("/api/agentic/companion/summary"),
        fetch("/api/agentic/companion/issues?status=open"),
      ]);

      const summaryText = await summaryRes.text();
      let summaryJson: any = null;
      try {
        summaryJson = JSON.parse(summaryText);
      } catch {
        throw new Error("Server returned an unexpected response.");
      }
      if (!summaryRes.ok) throw new Error(summaryJson.error || "Failed to load summary");
      setSummary(summaryJson);

      const issuesText = await issuesRes.text();
      try {
        const issuesJson = JSON.parse(issuesText);
        if (issuesRes.ok && Array.isArray(issuesJson.issues)) {
          setIssues((issuesJson.issues as any[]).slice(0, 5));
        }
      } catch {
        // ignore issues parse errors
      }

      // Health score will use fallback calculation (line 271)
    } catch (err: any) {
      console.error("[DEBUG] Error loading summary:", err);
      setError(err?.message || "Failed to load summary");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  // Compute derived values from API data (with defensive null checks)
  const highRiskCounts = summary?.global?.high_risk_items_30d || { receipts: 0, invoices: 0, bank_transactions: 0 };
  const totalHighRisk = (highRiskCounts.receipts || 0) + (highRiskCounts.invoices || 0) + (highRiskCounts.bank_transactions || 0);
  const agentRetries = summary?.global?.agent_retries_30d || 0;

  // Use backend health score if available, otherwise compute fallback
  const displayHealthScore = healthScore ?? Math.max(0, Math.min(100, 100 - totalHighRisk * 2 - Math.floor(agentRetries / 2)));

  // Efficiency: assume 99%+ if low retries
  const efficiency = agentRetries < 5 ? "99.5%" : agentRetries < 20 ? "98.2%" : "95.0%";

  // Build surface data from API
  const getSurfaceData = (key: string) => {
    if (!summary) return { lastRun: "No runs", health: 0, highRisk: 0, statusMessage: "Loading...", openIssues: 0, highRiskIssues: 0, headline: null as any };

    const surfaceKey = key as keyof CompanionSummary["surfaces"];
    const surface = summary.surfaces?.[surfaceKey];
    const latest = surface?.recent_runs?.[0];

    if (!latest) return { lastRun: "No runs yet", health: 100, highRisk: 0, statusMessage: "Ready to start", openIssues: surface?.open_issues_count || 0, highRiskIssues: surface?.high_risk_issues_count || 0, headline: surface?.headline_issue || null };

    const highRisk = latest.high_risk_count || 0;
    const docs = latest.documents_total || latest.transactions_total || 0;
    const health = highRisk === 0 ? 100 : highRisk <= 2 ? 85 : highRisk <= 5 ? 65 : 40;

    let statusMessage = "All synced";
    if (highRisk > 0) statusMessage = `${highRisk} items need review`;
    else if (latest.unreconciled && latest.unreconciled > 0) statusMessage = `${latest.unreconciled} unreconciled`;

    return {
      lastRun: formatTimeAgo(latest.created_at),
      health,
      highRisk,
      docs,
      statusMessage,
      riskLevel: latest.risk_level,
      openIssues: surface?.open_issues_count || 0,
      highRiskIssues: surface?.high_risk_issues_count || 0,
      headline: surface?.headline_issue || null,
    };
  };

  // Build activity log from recent runs (with defensive null checks)
  let activityLog: { id: string; timestamp: string; surface: string; action: string; details: string; status: string }[] = [];
  try {
    if (summary?.surfaces) {
      activityLog = [
        ...(summary.surfaces.receipts?.recent_runs?.slice(0, 1).map(r => ({
          id: `r-${r.id}`,
          timestamp: r.created_at ? new Date(r.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }) : "--:--",
          surface: "Receipts",
          action: `Run #${r.id}`,
          details: `${r.documents_total || 0} docs processed`,
          status: (r.high_risk_count || 0) > 0 ? "warning" : "success",
        })) || []),
        ...(summary.surfaces.invoices?.recent_runs?.slice(0, 1).map(r => ({
          id: `i-${r.id}`,
          timestamp: r.created_at ? new Date(r.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }) : "--:--",
          surface: "Invoices",
          action: `Run #${r.id}`,
          details: `${r.documents_total || 0} docs processed`,
          status: (r.high_risk_count || 0) > 0 ? "warning" : "success",
        })) || []),
        ...(summary.surfaces.bank_review?.recent_runs?.slice(0, 1).map(r => ({
          id: `b-${r.id}`,
          timestamp: r.created_at ? new Date(r.created_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }) : "--:--",
          surface: "Bank Review",
          action: `Run #${r.id}`,
          details: `${r.transactions_total || 0} transactions`,
          status: (r.unreconciled || 0) > 0 ? "warning" : "success",
        })) || []),
      ].slice(0, 4);
    }
  } catch (e) {
    console.error("Error building activityLog:", e);
    activityLog = [];
  }

  // Issues from high-risk items (for fallback display)
  const highRiskIssues = (highRiskCounts.receipts || 0) > 0 ? [{
    id: 1,
    surface: "Receipts",
    description: `${highRiskCounts.receipts} high-risk receipts pending review`,
    severity: "high",
  }] : [];

  const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const item = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4 } }
  };

  if (loading && !summary) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mx-auto mb-3" />
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
    <div className="min-h-screen bg-slate-50/50 font-sans text-slate-900 pb-12">

      {/* Subtle Mesh Gradient Background */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-40">
        <div className="absolute top-0 left-0 w-full h-[500px] bg-gradient-to-b from-blue-50/50 to-transparent" />
        <div className="absolute top-[-100px] right-[-100px] w-[500px] h-[500px] rounded-full bg-blue-100/30 blur-[100px]" />
        <div className="absolute top-[100px] left-[-100px] w-[400px] h-[400px] rounded-full bg-blue-900/10 blur-[80px]" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-8">

        {/* --- Header --- */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-10"
        >
          <div>
            <div className="flex items-baseline gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                Financial Overwatch
              </h1>
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-100">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide">Live</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="/settings/account"
              className="h-9 px-4 rounded-lg bg-white border border-slate-200 text-slate-600 text-sm font-medium shadow-sm hover:bg-slate-50 hover:border-slate-300 transition-all flex items-center gap-2"
            >
              <Settings className="w-4 h-4" />
              Configure
            </a>
            <button
              onClick={loadSummary}
              disabled={loading}
              className="h-9 px-4 rounded-lg bg-blue-950 text-white text-sm font-medium shadow-md shadow-blue-900/20 hover:bg-blue-900 hover:shadow-lg transition-all flex items-center gap-2 group disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : 'group-hover:rotate-180'} transition-transform duration-500`} />
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>
        </motion.header>

        {summary && !summary.ai_companion_enabled && (
          <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 text-amber-800 px-4 py-3 text-sm">
            AI Companion is disabled in Settings.{" "}
            <a className="underline font-semibold" href="/settings/account">Go to settings</a>
          </div>
        )}

        {/* --- Risk Radar Section --- */}
        {summary?.radar && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6"
          >
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Risk Radar
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(summary.radar).map(([key, axis]) => {
                const labels: Record<string, string> = {
                  cash_reconciliation: "Cash & Reconciliation",
                  revenue_invoices: "Revenue & Invoices",
                  expenses_receipts: "Expenses & Receipts",
                  tax_compliance: "Tax & Compliance",
                };
                const scoreColor = axis.score >= 80 ? "text-emerald-600" :
                  axis.score >= 50 ? "text-amber-600" : "text-rose-600";
                return (
                  <div
                    key={key}
                    className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div className="text-xs font-medium text-slate-500">
                      {labels[key] || key}
                    </div>
                    <div className="mt-1.5 flex items-baseline justify-between">
                      <span className={`text-2xl font-bold ${scoreColor}`}>
                        {axis.score}
                      </span>
                      <span className="text-xs text-slate-400">
                        {axis.open_issues === 0 ? "✓ Clear" : `${axis.open_issues} open`}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${axis.score >= 80 ? "bg-emerald-500" :
                          axis.score >= 50 ? "bg-amber-500" : "bg-rose-500"
                          }`}
                        style={{ width: `${axis.score}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.section>
        )}

        {/* --- Story Section --- */}
        {summary?.story && summary.story.overall_summary && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-6 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm"
          >
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              This Week's Story
            </h3>
            <p className="mt-2 text-sm text-slate-800 leading-relaxed">
              {summary.story.overall_summary}
            </p>
            {summary.story.timeline_bullets?.length > 0 && (
              <ul className="mt-3 space-y-2">
                {summary.story.timeline_bullets.map((item, idx) => (
                  <li key={idx} className="flex gap-3 text-sm text-slate-700">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            )}
          </motion.section>
        )}

        {/* --- Coverage Section --- */}
        {summary?.coverage && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="mb-6"
          >
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Coverage
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(summary.coverage).map(([key, axis]) => {
                const labels: Record<string, string> = {
                  receipts: "Receipts",
                  invoices: "Invoices",
                  banking: "Banking",
                  books: "Books",
                };
                const pctColor = axis.coverage_percent >= 80 ? "text-emerald-600" :
                  axis.coverage_percent >= 50 ? "text-amber-600" : "text-rose-600";
                return (
                  <div
                    key={key}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2.5"
                  >
                    <div className="text-xs font-medium text-slate-500">
                      {labels[key] || key}
                    </div>
                    <div className="mt-1 flex items-baseline justify-between">
                      <span className={`text-xl font-semibold ${pctColor}`}>
                        {axis.coverage_percent.toFixed(0)}%
                      </span>
                      <span className="text-[0.7rem] text-slate-500">
                        {axis.covered_items}/{axis.total_items}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.section>
        )}

        {/* --- Close-Readiness + Playbook Row --- */}
        <div className="grid gap-4 mb-6 lg:grid-cols-2">
          {/* Close-Readiness Pill */}
          {summary?.close_readiness && (
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
            >
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Close Readiness
              </h3>
              <div className="mt-2 flex items-center gap-2">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${summary.close_readiness.status === "ready"
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-amber-100 text-amber-800"
                  }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${summary.close_readiness.status === "ready" ? "bg-emerald-500" : "bg-amber-500"
                    }`} />
                  {summary.close_readiness.status === "ready" ? "Close-ready" : "Not close-ready"}
                </span>
                {summary.close_readiness.blocking_reasons.length > 0 && (
                  <span className="text-xs text-slate-500">
                    ({summary.close_readiness.blocking_reasons.length} blocker{summary.close_readiness.blocking_reasons.length > 1 ? "s" : ""})
                  </span>
                )}
              </div>
              {summary.close_readiness.blocking_reasons.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {summary.close_readiness.blocking_reasons.slice(0, 3).map((reason, idx) => (
                    <li key={idx} className="flex gap-2">
                      <span className="text-amber-500">•</span>
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              )}
            </motion.section>
          )}

          {/* Today's Playbook */}
          {summary?.playbook && summary.playbook.length > 0 && (
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
            >
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Today's Playbook
              </h3>
              <ul className="mt-2 space-y-1.5 text-sm text-slate-800">
                {summary.playbook.map((step, idx) => {
                  const badgeColor = step.severity === "high"
                    ? "bg-rose-100 text-rose-700"
                    : step.severity === "medium"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-700";
                  return (
                    <li key={idx} className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`shrink-0 h-5 w-5 rounded-full flex items-center justify-center text-[0.65rem] font-bold ${badgeColor}`}>
                          {idx + 1}
                        </span>
                        <Link
                          to={step.url}
                          className="text-left truncate hover:underline"
                        >
                          {step.label}
                        </Link>
                      </div>
                      <span className="shrink-0 text-[0.65rem] uppercase tracking-wide text-slate-500">
                        {step.surface}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </motion.section>
          )}
        </div>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="space-y-6"
        >

          {/* --- Bento Grid Hero --- */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

            {/* Health Stats */}
            <motion.div variants={item} className="md:col-span-1">
              <Card className="h-full bg-gradient-to-br from-white to-slate-50/50">
                <div className="flex flex-col h-full justify-between">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">System Health</p>
                      <div className="mt-1 flex items-baseline gap-1">
                        <span className="text-3xl font-bold text-slate-900">{displayHealthScore}</span>
                        <span className="text-sm text-slate-400 font-medium">/ 100</span>
                      </div>
                    </div>
                    <RadialProgress percentage={displayHealthScore} size={52} color="#10b981" />
                  </div>
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <div className="flex items-center gap-2 text-xs text-emerald-700 font-medium">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {totalHighRisk === 0 ? "All systems nominal" : `${totalHighRisk} items need attention`}
                    </div>
                  </div>
                </div>
              </Card>
            </motion.div>

            {/* Efficiency Stats */}
            <motion.div variants={item} className="md:col-span-1">
              <Card className="h-full">
                <div className="flex flex-col h-full justify-between">
                  <div>
                    <div className="flex justify-between items-start">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Agent Efficiency</p>
                      <Zap className="w-4 h-4 text-amber-500" />
                    </div>
                    <div className="mt-1 flex items-baseline gap-1">
                      <span className="text-3xl font-bold text-slate-900">{efficiency}</span>
                    </div>
                  </div>
                  <div className="mt-4 flex items-end justify-between">
                    <MiniTrend />
                    <span className="text-[10px] text-slate-400 font-mono">24H TREND</span>
                  </div>
                </div>
              </Card>
            </motion.div>

            {/* Active Risks */}
            <motion.div variants={item} className="md:col-span-2">
              <Card className={`h-full border-l-4 ${totalHighRisk > 0 ? 'border-l-amber-500' : 'border-l-emerald-500'}`}>
                <div className="flex h-full items-center justify-between gap-6">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <AlertTriangle className={`w-4 h-4 ${totalHighRisk > 0 ? 'text-amber-500' : 'text-slate-400'}`} />
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Risk Assessment</p>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">
                      {totalHighRisk > 0 ? "Attention Required" : "Ledger Secure"}
                    </h3>
                    <p className="text-sm text-slate-500 mt-1">
                      {totalHighRisk > 0 ? `${totalHighRisk} high-risk items pending review.` : "No high-risk items detected."}
                    </p>
                  </div>

                  <div className="flex gap-3">
                    <div className="text-center px-4 py-2 bg-slate-50 rounded-lg border border-slate-100">
                      <p className="text-xs text-slate-400 uppercase">Receipts</p>
                      <p className={`text-xl font-bold ${(highRiskCounts.receipts || 0) > 0 ? 'text-amber-600' : 'text-slate-700'}`}>
                        {highRiskCounts.receipts || 0}
                      </p>
                    </div>
                    <div className="text-center px-4 py-2 bg-slate-50 rounded-lg border border-slate-100">
                      <p className="text-xs text-slate-400 uppercase">Bank</p>
                      <p className="text-xl font-bold text-slate-700">{highRiskCounts.bank_transactions || 0}</p>
                    </div>
                    <div className="text-center px-4 py-2 bg-slate-50 rounded-lg border border-slate-100">
                      <p className="text-xs text-slate-400 uppercase">Invoices</p>
                      <p className="text-xl font-bold text-slate-700">{highRiskCounts.invoices || 0}</p>
                    </div>
                  </div>
                </div>
              </Card>
            </motion.div>
          </div>

          {/* --- Main Content Split --- */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Left Column: Surfaces (2/3) */}
            <div className="lg:col-span-2 space-y-6">

              {/* Today's checklist */}
              <Card>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-rose-600" />
                      Today's checklist
                    </h3>
                    <p className="text-xs text-slate-500">
                      Top open issues across surfaces. The companion suggests, you decide.
                    </p>
                  </div>
                  <a href="/ai-companion/issues" className="text-xs font-semibold text-sky-700 hover:text-sky-900">
                    View all →
                  </a>
                </div>
                {issues.length === 0 ? (
                  <div className="text-sm text-slate-500">No open issues. Your books look clean for now.</div>
                ) : (
                  <div className="space-y-2">
                    {issues.map((issue) => (
                      <div key={issue.id} className="border border-slate-200 rounded-lg p-3 flex items-start gap-3 bg-slate-50">
                        <SeverityPill value={issue.severity} />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] uppercase text-slate-500">{issue.surface}</span>
                            <span className="font-semibold text-slate-900">{issue.title}</span>
                          </div>
                          <div className="text-xs text-slate-600">
                            {issue.recommended_action || "Review this item"}
                          </div>
                        </div>
                        <a href="/ai-companion/issues" className="text-xs text-sky-700 hover:text-sky-900">
                          View details
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Issue counts by surface */}
              <Card>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {surfaceConfigs.map((config) => {
                    const surfaceKey = config.key === "books_review" ? "books" : config.key === "bank_review" ? "bank" : config.key;
                    const surfaceData = summary?.surfaces[config.key as keyof typeof summary.surfaces];
                    return (
                      <div key={config.key} className="border border-slate-100 rounded-lg p-3 bg-slate-50">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-slate-800">{config.title}</span>
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
                            Open: {surfaceData?.open_issues_count || 0}
                          </span>
                        </div>
                        <div className="text-xs text-slate-600 mt-1">
                          High-risk: {surfaceData?.high_risk_issues_count || 0}
                        </div>
                        {surfaceData?.headline_issue && (
                          <div className="text-xs text-slate-600 mt-1">
                            Headline: {surfaceData.headline_issue.title}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Card>

              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-900" />
                  Active Surfaces
                </h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {surfaceConfigs.map((config) => {
                  const data = getSurfaceData(config.key);
                  const Icon = config.icon;

                  return (
                    <motion.div variants={item} key={config.key}>
                      <a href={config.href} className="block">
                        <Card className="h-full group hover:ring-1 hover:ring-blue-900/20 cursor-pointer relative">
                          {data.highRisk > 0 && (
                            <div className="absolute top-3 right-3 w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                          )}

                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-600 group-hover:bg-blue-50 group-hover:text-blue-950 transition-colors">
                                <Icon className="w-5 h-5" />
                              </div>
                              <div>
                                <h4 className="font-semibold text-slate-900 text-sm group-hover:text-blue-900 transition-colors">{config.title}</h4>
                                <p className="text-[11px] text-slate-400 font-medium uppercase tracking-wide flex items-center gap-1">
                                  <Clock className="w-3 h-3" /> {data.lastRun}
                                </p>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-3">
                            <div className="flex justify-between items-center text-xs">
                              <span className="text-slate-500 font-medium">Health Status</span>
                              <span className={`font-bold ${data.health === 100 ? 'text-emerald-600' : data.health > 70 ? 'text-slate-700' : 'text-amber-600'}`}>
                                {data.health}%
                              </span>
                            </div>

                            <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${data.health}%` }}
                                className={`h-full rounded-full ${data.health === 100 ? 'bg-emerald-500' : data.health > 70 ? 'bg-blue-900' : 'bg-amber-500'}`}
                              />
                            </div>

                            <div className="pt-3 border-t border-slate-50 flex items-center justify-between">
                              <span className="text-xs text-slate-500">{data.statusMessage}</span>
                              <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-blue-400 transform group-hover:translate-x-1 transition-all" />
                            </div>
                          </div>
                        </Card>
                      </a>
                    </motion.div>
                  );
                })}
              </div>
            </div>

            {/* Right Column: Intelligence Feed (1/3) */}
            <div className="lg:col-span-1 space-y-6">
              <motion.div variants={item} className="h-full">
                <Card noPadding className="h-full flex flex-col">
                  <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-blue-900" />
                      Intelligence Feed
                    </h3>
                    <StatusBadge variant="blue">Live</StatusBadge>
                  </div>

                  <div className="p-4 flex-1 overflow-y-auto max-h-[500px]">

                    {/* Suggestions Section */}
                    <div className="mb-6">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3 pl-1">Insights</p>
                      <div className="space-y-3">
                        <div className="p-3 rounded-lg bg-gradient-to-r from-blue-50/50 to-white border border-blue-100 hover:border-blue-200 transition-colors cursor-pointer group">
                          <div className="flex items-start gap-2">
                            <TrendingUp className="w-4 h-4 text-blue-950 mt-0.5" />
                            <div>
                              <h5 className="text-xs font-semibold text-slate-800 group-hover:text-blue-900">AI Companion Active</h5>
                              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                                {summary?.ai_companion_enabled ? "All AI agents are monitoring your financial data." : "Enable AI Companion in settings for automated insights."}
                              </p>
                            </div>
                          </div>
                        </div>
                        {agentRetries > 0 && (
                          <div className="p-3 rounded-lg bg-gradient-to-r from-amber-50/50 to-white border border-amber-100 hover:border-amber-200 transition-colors cursor-pointer group">
                            <div className="flex items-start gap-2">
                              <RefreshCw className="w-4 h-4 text-amber-600 mt-0.5" />
                              <div>
                                <h5 className="text-xs font-semibold text-slate-800 group-hover:text-amber-900">Agent Retries</h5>
                                <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                                  {agentRetries} retries in the last 30 days. Consider reviewing error patterns.
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Activity Timeline */}
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3 pl-1">Activity Log</p>
                      {activityLog.length === 0 ? (
                        <p className="text-xs text-slate-400 pl-1">No recent activity</p>
                      ) : (
                        <div className="relative pl-3 space-y-6 before:absolute before:left-[19px] before:top-2 before:bottom-2 before:w-px before:bg-slate-200">
                          {activityLog.map((log) => (
                            <div key={log.id} className="relative flex gap-3 group">
                              <div className={`z-10 w-3 h-3 mt-1 rounded-full border-2 border-white ring-1 flex-shrink-0 ${log.status === 'success' ? 'bg-emerald-500 ring-emerald-200' :
                                log.status === 'warning' ? 'bg-amber-500 ring-amber-200' : 'bg-slate-400 ring-slate-200'
                                }`} />

                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-semibold text-slate-700 group-hover:text-blue-900 transition-colors">{log.action}</span>
                                  <span className="text-[10px] text-slate-400 font-mono">{log.timestamp}</span>
                                </div>
                                <p className="text-[11px] text-slate-500 mt-0.5">
                                  <span className="font-medium text-slate-600">{log.surface}</span> • {log.details}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                  </div>

                  <div className="p-3 border-t border-slate-100 bg-slate-50/30">
                    <a
                      href="/agentic/console"
                      className="block w-full py-2 text-xs font-medium text-slate-500 hover:text-blue-900 hover:bg-white border border-transparent hover:border-slate-200 rounded-md transition-all text-center"
                    >
                      View Full System Logs
                    </a>
                  </div>
                </Card>
              </motion.div>
            </div>

          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default CompanionOverviewPage;
