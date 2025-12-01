import React, { useEffect, useMemo, useState } from "react";
import { fetchAuditLog, type AuditEntry, type Paginated } from "./api";
import { Card, SimpleTable } from "./AdminUI";

type Range = "24h" | "7d" | "30d" | "all";

const rangeToDate = (range: Range) => {
  const now = new Date();
  if (range === "all") return null;
  const date = new Date(now);
  if (range === "24h") date.setDate(now.getDate() - 1);
  if (range === "7d") date.setDate(now.getDate() - 7);
  if (range === "30d") date.setDate(now.getDate() - 30);
  return date.toISOString();
};

export const AuditLogSection: React.FC = () => {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [page, setPage] = useState(1);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState("");
  const [adminFilter, setAdminFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [range, setRange] = useState<Range>("7d");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async (opts?: { page?: number }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAuditLog({
        page: opts?.page,
        action: actionFilter || undefined,
        admin_user: adminFilter || undefined,
        level: levelFilter || undefined,
        category: categoryFilter || undefined,
        start: rangeToDate(range) || undefined,
      });
      const payload = res as Paginated<AuditEntry>;
      setEntries(payload.results || []);
      setNext(payload.next || null);
      setPrevious(payload.previous || null);
    } catch (err: any) {
      setError(err?.message || "Unable to load audit log");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs({ page });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, actionFilter, adminFilter, range, levelFilter, categoryFilter]);

  const actions = useMemo(() => {
    const set = new Set(entries.map((e) => e.action));
    return Array.from(set);
  }, [entries]);

  const rows = useMemo(
    () =>
      entries.map((e) => [
        <span key={`time-${e.id}`} className="text-xs text-slate-500">
          {new Date(e.timestamp).toLocaleString()}
        </span>,
        <span key={`admin-${e.id}`} className="text-xs text-slate-800">
          {e.admin_email || "—"}
        </span>,
        <span key={`action-${e.id}`} className="text-xs font-semibold text-slate-900">
          {e.action}
        </span>,
        <span key={`level-${e.id}`} className="text-[11px] font-semibold text-slate-700">
          {e.level || "INFO"}
        </span>,
        <span key={`category-${e.id}`} className="text-xs text-slate-600">
          {e.category || "—"}
        </span>,
        <span key={`obj-${e.id}`} className="text-xs text-slate-700">
          {e.object_type} · {e.object_id || "—"}
        </span>,
        <span key={`ip-${e.id}`} className="text-[11px] text-slate-500">
          {e.remote_ip || "—"}
        </span>,
      ]),
    [entries]
  );

  return (
    <Card title="Audit log" subtitle="All admin actions are captured and immutable.">
      <div className="flex flex-wrap gap-2 mb-3">
        <select
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <input
          value={adminFilter}
          onChange={(e) => {
            setAdminFilter(e.target.value);
            setPage(1);
          }}
          placeholder="Admin email"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
        />
        <select
          value={levelFilter}
          onChange={(e) => {
            setLevelFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
        >
          <option value="">All levels</option>
          <option value="INFO">Info</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
        </select>
        <input
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(1);
          }}
          placeholder="Category"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
        />
        <div className="flex items-center gap-1 text-xs text-slate-700">
          {(["24h", "7d", "30d", "all"] as Range[]).map((r) => (
            <button
              key={r}
              onClick={() => {
                setRange(r);
                setPage(1);
              }}
              className={`rounded-full border px-3 py-1.5 ${
                range === r ? "border-slate-300 bg-slate-100 font-semibold" : "border-slate-200 bg-white"
              }`}
            >
              Last {r === "all" ? "all" : r}
            </button>
          ))}
        </div>
        <button
          onClick={() => loadLogs({ page: 1 })}
          className="ml-auto rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-slate-600">Loading audit log…</p>
      ) : error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : (
        <>
          <SimpleTable
            headers={["Timestamp", "Admin", "Action", "Level", "Category", "Object", "IP"]}
            rows={rows}
          />
          <div className="flex items-center justify-between mt-3 text-xs text-slate-600">
            <button
              disabled={!previous}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-full border border-slate-200 px-3 py-1.5 disabled:opacity-50"
            >
              Prev
            </button>
            <span>Page {page}</span>
            <button
              disabled={!next}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-full border border-slate-200 px-3 py-1.5 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </>
      )}
    </Card>
  );
};
