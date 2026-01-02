import React, { useEffect, useMemo, useState } from "react";
import { fetchBankAccounts, type BankAccount, type Paginated } from "./api";
import { Card, SimpleTable, StatusPill } from "./AdminUI";

export const BankingSection: React.FC = () => {
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [filtered, setFiltered] = useState<BankAccount[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAccounts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchBankAccounts();
      const payload = res as Paginated<BankAccount>;
      const list = payload.results || (Array.isArray(res) ? (res as unknown as BankAccount[]) : []);
      setAccounts(list);
      setFiltered(list);
    } catch (err: any) {
      setError(err?.message || "Unable to load bank accounts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    const q = search.toLowerCase();
    setFiltered(
      accounts.filter(
        (a) =>
          a.workspace_name.toLowerCase().includes(q) ||
          a.bank_name.toLowerCase().includes(q) ||
          a.name.toLowerCase().includes(q)
      )
    );
  }, [search, accounts]);

  const rows = useMemo(
    () =>
      filtered.map((b) => [
        <span key={`bank-${b.id}`} className="text-xs text-slate-800">
          {b.bank_name || "—"}
        </span>,
        <span key={`nick-${b.id}`} className="text-xs text-slate-700">
          {b.name}
        </span>,
        <span key={`ws-${b.id}`} className="text-xs text-slate-700">
          {b.workspace_name}
        </span>,
        <StatusPill
          key={`status-${b.id}`}
          tone={b.status === "ok" ? "good" : b.status === "error" ? "bad" : "warning"}
          label={b.status === "ok" ? "Healthy" : b.status === "error" ? "Error" : "Disconnected"}
        />,
        <span key={`sync-${b.id}`} className="text-xs text-slate-500">
          {b.last_imported_at ? new Date(b.last_imported_at).toLocaleString() : "—"}
        </span>,
        <span key={`unrec-${b.id}`} className="text-xs text-slate-800">
          {b.unreconciled_count ?? "—"}
        </span>,
      ]),
    [filtered]
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Banking & feeds</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Monitor bank connections, CSV imports, and unreconciled cash lines. Use this to debug feed errors and
            keep the banking brain clean.
          </p>
        </div>
        <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
          View import jobs
        </button>
      </header>
      <Card title="Bank feeds overview">
        <div className="flex items-center gap-2 mb-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by workspace or bank…"
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
          />
        </div>
        {loading ? (
          <p className="text-sm text-slate-600">Loading bank accounts…</p>
        ) : error ? (
          <p className="text-sm text-rose-700">{error}</p>
        ) : (
          <SimpleTable
            headers={["Bank", "Account", "Workspace", "Status", "Last sync", "Unreconciled"]}
            rows={rows}
          />
        )}
      </Card>
    </div>
  );
};
