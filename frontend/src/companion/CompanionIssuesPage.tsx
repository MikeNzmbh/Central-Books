import React, { useEffect, useMemo, useState } from "react";

type Issue = {
  id: number;
  surface: string;
  severity: string;
  status: string;
  title: string;
  recommended_action?: string;
  estimated_impact?: string;
  run_type?: string;
  run_id?: number | null;
  created_at: string;
  trace_id?: string;
};

type FilterState = {
  status: string;
  surface: string;
  severity: string;
};

const StatusPill: React.FC<{ value: string }> = ({ value }) => {
  const map: Record<string, string> = {
    open: "bg-emerald-100 text-emerald-800",
    snoozed: "bg-amber-100 text-amber-800",
    resolved: "bg-slate-200 text-slate-700",
  };
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${map[value] || "bg-slate-100 text-slate-700"}`}>{value}</span>;
};

const SeverityPill: React.FC<{ value: string }> = ({ value }) => {
  const map: Record<string, string> = {
    high: "bg-rose-100 text-rose-700",
    medium: "bg-amber-100 text-amber-800",
    low: "bg-slate-200 text-slate-700",
  };
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${map[value] || "bg-slate-100 text-slate-700"}`}>{value}</span>;
};

const CompanionIssuesPage: React.FC = () => {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [filters, setFilters] = useState<FilterState>({ status: "open", surface: "", severity: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadIssues = async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.surface) params.set("surface", filters.surface);
    if (filters.severity) params.set("severity", filters.severity);
    try {
      const res = await fetch(`/api/agentic/companion/issues?${params.toString()}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to load issues");
      setIssues(json.issues || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load issues");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIssues();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.status, filters.surface, filters.severity]);

  const surfaces = useMemo(() => ["", "receipts", "invoices", "books", "bank"], []);
  const severities = useMemo(() => ["", "low", "medium", "high"], []);

  const updateStatus = async (id: number, next: string) => {
    try {
      const res = await fetch(`/api/agentic/companion/issues/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to update");
      setIssues((prev) => prev.map((i) => (i.id === id ? { ...i, status: json.status } : i)));
    } catch (err: any) {
      setError(err?.message || "Failed to update issue");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase text-slate-500 font-semibold">AI Companion</p>
            <h1 className="text-2xl font-semibold">Issues</h1>
            <p className="text-sm text-slate-500">Cross-surface checklist surfaced by the companion.</p>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap gap-3">
          <div>
            <span className="text-xs text-slate-600">Status</span>
            <select
              className="mt-1 border border-slate-200 rounded px-2 py-1 text-sm"
              value={filters.status}
              onChange={(e) => setFilters((p) => ({ ...p, status: e.target.value }))}
            >
              <option value="open">Open</option>
              <option value="snoozed">Snoozed</option>
              <option value="resolved">Resolved</option>
              <option value="">All</option>
            </select>
          </div>
          <div>
            <span className="text-xs text-slate-600">Surface</span>
            <select
              className="mt-1 border border-slate-200 rounded px-2 py-1 text-sm"
              value={filters.surface}
              onChange={(e) => setFilters((p) => ({ ...p, surface: e.target.value }))}
            >
              {surfaces.map((s) => (
                <option key={s || "all"} value={s}>
                  {s || "All"}
                </option>
              ))}
            </select>
          </div>
          <div>
            <span className="text-xs text-slate-600">Severity</span>
            <select
              className="mt-1 border border-slate-200 rounded px-2 py-1 text-sm"
              value={filters.severity}
              onChange={(e) => setFilters((p) => ({ ...p, severity: e.target.value }))}
            >
              {severities.map((s) => (
                <option key={s || "all"} value={s}>
                  {s || "All"}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && <div className="rounded-lg bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3">{error}</div>}

        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="text-left px-3 py-2">Severity</th>
                <th className="text-left px-3 py-2">Surface</th>
                <th className="text-left px-3 py-2">Title</th>
                <th className="text-left px-3 py-2">Action</th>
                <th className="text-left px-3 py-2">Impact</th>
                <th className="text-left px-3 py-2">Status</th>
                <th className="text-left px-3 py-2">Created</th>
                <th className="text-left px-3 py-2">Link</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-3 py-4 text-center text-slate-500">
                    Loading…
                  </td>
                </tr>
              ) : issues.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-4 text-center text-slate-500">
                    No issues found for this filter.
                  </td>
                </tr>
              ) : (
                issues.map((issue) => (
                  <tr key={issue.id} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <SeverityPill value={issue.severity} />
                    </td>
                    <td className="px-3 py-2 capitalize">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 text-[11px]">{issue.surface}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 font-semibold text-slate-800">
                      {issue.title}
                      {issue.estimated_impact && (
                        <div className="text-xs text-slate-500">Impact: {issue.estimated_impact}</div>
                      )}
                      {issue.run_id ? (
                        <div className="text-[11px] text-slate-500">From run #{issue.run_id}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 text-slate-700 text-sm">{issue.recommended_action || "—"}</td>
                    <td className="px-3 py-2 text-slate-600 text-sm">{issue.estimated_impact || "—"}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <StatusPill value={issue.status} />
                        {issue.status !== "resolved" && (
                          <button
                            className="text-xs text-sky-700 hover:text-sky-900"
                            onClick={() => updateStatus(issue.id, issue.status === "open" ? "snoozed" : "open")}
                          >
                            {issue.status === "open" ? "Snooze" : "Reopen"}
                          </button>
                        )}
                        {issue.status !== "resolved" && (
                          <button
                            className="text-xs text-emerald-700 hover:text-emerald-900"
                            onClick={() => updateStatus(issue.id, "resolved")}
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-slate-500 text-xs">{new Date(issue.created_at).toLocaleString()}</td>
                    <td className="px-3 py-2">
                      {issue.trace_id ? (
                        <a className="text-xs text-sky-700" href={`/agentic/console?trace=${encodeURIComponent(issue.trace_id)}`}>
                          Trace
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default CompanionIssuesPage;
