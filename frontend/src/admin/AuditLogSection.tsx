import React, { useEffect, useMemo, useState, useCallback } from "react";
import { fetchAuditLog, type AuditEntry, type Paginated } from "./api";

// ----------------------
// Types  
// ----------------------

type RiskLevel = "low" | "medium" | "high" | "critical";
type AuditOutcome = "success" | "failure";
type TabFilter = "all" | "security" | "impersonation" | "config";

interface AuditFilters {
  search: string;
  dateRange: "24h" | "7d" | "30d" | "90d" | "all";
  risk: RiskLevel | "all";
  category: string;
  outcome: AuditOutcome | "all";
  actor: string;
  tab: TabFilter;
}

interface AuditSummary {
  total_events: number;
  security_events: number;
  impersonations_today: number;
  high_risk_events_24h: number;
}

// ----------------------
// Helpers
// ----------------------

function riskFromLevel(level: string | undefined): RiskLevel {
  switch (level) {
    case "ERROR": return "high";
    case "WARNING": return "medium";
    default: return "low";
  }
}

function riskLabel(level: RiskLevel) {
  switch (level) {
    case "low": return "Low";
    case "medium": return "Medium";
    case "high": return "High";
    case "critical": return "Critical";
  }
}

function riskBadgeClass(level: RiskLevel) {
  switch (level) {
    case "low": return "bg-emerald-50 text-emerald-700 border-emerald-100";
    case "medium": return "bg-amber-50 text-amber-800 border-amber-100";
    case "high": return "bg-rose-50 text-rose-700 border-rose-100";
    case "critical": return "bg-red-50 text-red-700 border-red-100";
    default: return "bg-slate-50 text-slate-700 border-slate-100";
  }
}

function formatTimestamp(ts: string) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function rangeToDate(range: string): string | null {
  const now = new Date();
  if (range === "all") return null;
  const date = new Date(now);
  if (range === "24h") date.setDate(now.getDate() - 1);
  if (range === "7d") date.setDate(now.getDate() - 7);
  if (range === "30d") date.setDate(now.getDate() - 30);
  if (range === "90d") date.setDate(now.getDate() - 90);
  return date.toISOString();
}

function getActorInitials(email: string | null): string {
  if (!email) return "?";
  const name = email.split("@")[0];
  const parts = name.split(/[._-]/);
  return parts.slice(0, 2).map(p => p[0]?.toUpperCase() || "").join("");
}

// ----------------------
// Detail Drawer
// ----------------------

interface LogDetailDrawerProps {
  entry: AuditEntry | null;
  onClose: () => void;
}

const LogDetailDrawer: React.FC<LogDetailDrawerProps> = ({ entry, onClose }) => {
  if (!entry) return null;

  const risk = riskFromLevel(entry.level);

  return (
    <div className="fixed inset-0 z-40 flex items-stretch justify-end bg-slate-900/30 backdrop-blur-sm">
      <div className="h-full w-full max-w-xl bg-white shadow-2xl border-l border-slate-200 flex flex-col">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-slate-900 text-slate-50 text-xs">⏱</div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Audit Event Details</h2>
              <p className="text-xs text-slate-500">{formatTimestamp(entry.timestamp)}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Summary</h3>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-sm text-slate-900">{entry.action} on {entry.object_type}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1">
                  🏷️ {entry.category || "general"}
                </span>
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 border text-xs font-medium ${riskBadgeClass(risk)}`}>
                  ⚠️ {riskLabel(risk)} risk
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1">
                  ✅ {entry.level || "INFO"}
                </span>
                {entry.request_id && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1">
                    🔎 <span className="font-mono text-[11px]">{entry.request_id}</span>
                  </span>
                )}
              </div>
            </div>
          </section>

          <section className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Actor</h3>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 space-y-1 text-xs text-slate-700">
                <div className="flex items-center gap-2 text-sm">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-700">
                    {getActorInitials(entry.admin_email)}
                  </div>
                  <div>
                    <div className="font-medium text-slate-900">{entry.admin_email || "System"}</div>
                    {entry.actor_role && (
                      <div className="text-[11px] text-slate-500">{entry.actor_role}</div>
                    )}
                  </div>
                </div>
                {entry.remote_ip && (
                  <div className="flex items-center justify-between pt-2">
                    <span className="text-slate-500">IP</span>
                    <span className="font-mono text-[11px] text-slate-700">{entry.remote_ip}</span>
                  </div>
                )}
                {entry.user_agent && (
                  <div className="pt-2">
                    <div className="text-slate-500">User agent</div>
                    <div className="mt-1 rounded-xl border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-[10px] text-slate-700 break-all">
                      {entry.user_agent}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Target</h3>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 space-y-2 text-xs text-slate-700">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Object</span>
                  <span className="text-[11px] text-slate-800">{entry.object_type}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">ID</span>
                  <span className="text-[11px] text-slate-800">{entry.object_id || "—"}</span>
                </div>
              </div>
            </div>
          </section>

          {entry.extra && Object.keys(entry.extra).length > 0 && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Extra Details</h3>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-mono text-slate-700 max-h-52 overflow-auto">
                <pre className="whitespace-pre-wrap break-all">{JSON.stringify(entry.extra, null, 2)}</pre>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
};

// ----------------------
// Main Page
// ----------------------

export const AuditLogSection: React.FC = () => {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [liveMode, setLiveMode] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditEntry | null>(null);

  const [filters, setFilters] = useState<AuditFilters>({
    search: "",
    dateRange: "7d",
    risk: "all",
    category: "",
    outcome: "all",
    actor: "",
    tab: "all",
  });

  const loadLogs = useCallback(async (opts?: { page?: number }) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined | null> = {
        page: opts?.page ?? page,
        start: rangeToDate(filters.dateRange) || undefined,
        action: filters.search || undefined,
        admin_user: filters.actor || undefined,
        level: filters.risk === "high" || filters.risk === "critical" ? "ERROR" : filters.risk === "medium" ? "WARNING" : undefined,
        category: filters.category || undefined,
      };
      // Add tab-based scope filtering
      if (filters.tab === "security") params.category = "security";
      if (filters.tab === "impersonation") params.action = "IMPERSONATE";
      if (filters.tab === "config") params.category = "config";

      const res: Paginated<AuditEntry> = await fetchAuditLog(params);
      setEntries(res.results || []);
      setNext(res.next || null);
      setPrevious(res.previous || null);
    } catch (err: any) {
      setError(err?.message || "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    loadLogs({ page });
  }, [page, filters.dateRange, filters.risk, filters.category, filters.tab, filters.actor]);

  // Live mode polling
  useEffect(() => {
    if (!liveMode) return;
    const interval = setInterval(() => loadLogs({ page: 1 }), 15000);
    return () => clearInterval(interval);
  }, [liveMode, loadLogs]);

  const handleFilterChange = (partial: Partial<AuditFilters>) => {
    setFilters((prev) => ({ ...prev, ...partial }));
    setPage(1);
  };

  const uniqueActors = useMemo(() => {
    const map = new Map<string, string>();
    entries.forEach((e) => {
      if (e.admin_email && !map.has(e.admin_email)) {
        map.set(e.admin_email, e.admin_email);
      }
    });
    return Array.from(map.values());
  }, [entries]);

  // Compute summary stats from loaded entries
  const summary: AuditSummary = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    return {
      total_events: entries.length,
      security_events: entries.filter(e => e.category === "security" || e.action?.includes("LOGIN")).length,
      impersonations_today: entries.filter(e => e.action?.includes("IMPERSONATE") && e.timestamp.startsWith(today)).length,
      high_risk_events_24h: entries.filter(e => e.level === "ERROR" || e.level === "WARNING").length,
    };
  }, [entries]);

  return (
    <div className="flex h-full w-full flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-slate-900 text-slate-50 shadow-sm">⏱</div>
          <div>
            <h1 className="text-base font-semibold text-slate-900">Audit & Logs</h1>
            <p className="text-xs text-slate-500">Immutable trail of every sensitive action across all workspaces.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <label className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 cursor-pointer">
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50">
              <span className={`h-2 w-2 rounded-full ${liveMode ? "bg-emerald-500 animate-pulse" : "bg-slate-300"}`} />
            </span>
            Live tail
            <input
              type="checkbox"
              checked={liveMode}
              onChange={(e) => setLiveMode(e.target.checked)}
              className="h-3 w-3 rounded border-slate-300 text-emerald-600"
            />
          </label>
          <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-black">
            📥 Export CSV
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>Total events</span>
            <span>📊</span>
          </div>
          <div className="mt-2 flex items-end justify-between">
            <span className="text-xl font-semibold text-slate-900">{summary.total_events}</span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-600">
              Last {filters.dateRange === "all" ? "all" : filters.dateRange}
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>Security events</span>
            <span>🛡️</span>
          </div>
          <div className="mt-2 flex items-end justify-between">
            <span className="text-xl font-semibold text-slate-900">{summary.security_events}</span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-600">Logins, role changes</span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>Impersonations today</span>
            <span>👤</span>
          </div>
          <div className="mt-2 flex items-end justify-between">
            <span className="text-xl font-semibold text-slate-900">{summary.impersonations_today}</span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-600">All impersonate_start / end</span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>High risk (24h)</span>
            <span className="text-rose-500">⚠️</span>
          </div>
          <div className="mt-2 flex items-end justify-between">
            <span className="text-xl font-semibold text-rose-600">{summary.high_risk_events_24h}</span>
            <span className="rounded-full bg-rose-50 px-2 py-1 text-[11px] text-rose-700">Requires regular review</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white">
              🎛️ Filters
            </div>
            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
              <select
                className="bg-transparent text-[11px] text-slate-700 focus:outline-none"
                value={filters.dateRange}
                onChange={(e) => handleFilterChange({ dateRange: e.target.value as AuditFilters["dateRange"] })}
              >
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
                <option value="all">All time</option>
              </select>
            </div>

            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
              <select
                className="bg-transparent text-[11px] text-slate-700 focus:outline-none"
                value={filters.risk}
                onChange={(e) => handleFilterChange({ risk: e.target.value as RiskLevel | "all" })}
              >
                <option value="all">All risks</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1">
              <select
                className="bg-transparent text-[11px] text-slate-700 focus:outline-none"
                value={filters.actor}
                onChange={(e) => handleFilterChange({ actor: e.target.value })}
              >
                <option value="">All actors</option>
                {uniqueActors.map((actor) => (
                  <option key={actor} value={actor}>{actor}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs">🔍</span>
              <input
                type="text"
                className="h-8 w-56 rounded-full border border-slate-200 bg-slate-50 pl-7 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:bg-white focus:outline-none"
                placeholder="Search by actor, IP, action…"
                value={filters.search}
                onChange={(e) => handleFilterChange({ search: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && loadLogs({ page: 1 })}
              />
            </div>
            <button
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
              onClick={() => handleFilterChange({ search: "", risk: "all", category: "", actor: "" })}
            >
              🔄 Reset
            </button>
          </div>
        </div>

        {/* Tab Filters */}
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-[11px] font-medium text-slate-600">
          {(["all", "security", "impersonation", "config"] as TabFilter[]).map((tab) => (
            <button
              key={tab}
              className={`rounded-full px-2.5 py-1 transition ${filters.tab === tab
                ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200 mb-accent-underline"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              onClick={() => handleFilterChange({ tab })}
            >
              {tab === "all" ? "All activity" : tab === "security" ? "Security-sensitive" : tab === "impersonation" ? "Impersonations" : "Config & flags"}
            </button>
          ))}
        </div>
      </div>

      {/* Logs Table */}
      <div className="flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 text-[11px] text-slate-500">
          <span>Showing {entries.length} events {filters.search && "• filtered"}</span>
          <div className="flex items-center gap-2">
            <span>Page {page}</span>
            <div className="inline-flex overflow-hidden rounded-full border border-slate-200 bg-slate-50">
              <button
                className="px-2 py-1 text-[11px] text-slate-600 disabled:opacity-40"
                disabled={!previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Prev
              </button>
              <button
                className="border-l border-slate-200 px-2 py-1 text-[11px] text-slate-600 disabled:opacity-40"
                disabled={!next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </div>

        <div className="relative max-h-[520px] overflow-y-auto">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/50">
              <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm">
                <span className="h-2 w-2 animate-ping rounded-full bg-slate-400" />
                Loading audit events…
              </div>
            </div>
          )}

          {error && !loading && (
            <div className="flex h-48 items-center justify-center px-4">
              <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-center text-xs text-rose-700">
                {error}
              </div>
            </div>
          )}

          {!error && entries.length === 0 && !loading && (
            <div className="flex h-48 flex-col items-center justify-center gap-2 px-4 text-center text-xs text-slate-500">
              <span className="text-2xl">📋</span>
              <p>No audit events match your filters yet.</p>
              <p className="max-w-xs">Try widening the date range or clearing filters to see more activity.</p>
            </div>
          )}

          <table className="min-w-full text-left text-[11px]">
            <thead className="sticky top-0 z-0 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Actor</th>
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Object</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Risk</th>
                <th className="px-4 py-2 font-medium text-right">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((log) => {
                const risk = riskFromLevel(log.level);
                return (
                  <tr
                    key={log.id}
                    className="cursor-pointer bg-white/80 hover:bg-slate-50"
                    onClick={() => setSelectedLog(log)}
                  >
                    <td className="whitespace-nowrap px-4 py-2 text-[11px] text-slate-500">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="max-w-[180px] px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-semibold text-slate-700">
                          {getActorInitials(log.admin_email)}
                        </div>
                        <div className="truncate">
                          <div className="truncate font-medium text-slate-900">{log.admin_email || "System"}</div>
                        </div>
                      </div>
                    </td>
                    <td className="max-w-[220px] px-4 py-2">
                      <div className="truncate text-[11px] font-semibold text-slate-800">{log.action}</div>
                    </td>
                    <td className="max-w-[160px] px-4 py-2">
                      <div className="truncate text-[11px] text-slate-700">{log.object_type} • {log.object_id || "—"}</div>
                    </td>
                    <td className="px-4 py-2 text-[11px] text-slate-600">{log.category || "—"}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border ${riskBadgeClass(risk)}`}>
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {riskLabel(risk)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-[10px] text-slate-500">
                      {log.remote_ip || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Drawer */}
      <LogDetailDrawer entry={selectedLog} onClose={() => setSelectedLog(null)} />
    </div>
  );
};

export default AuditLogSection;
