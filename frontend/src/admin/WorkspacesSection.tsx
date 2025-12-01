import React, { useEffect, useMemo, useState } from "react";
import { fetchWorkspaces, updateWorkspace, type Paginated, type Workspace } from "./api";
import { Card, SimpleTable, StatusPill } from "./AdminUI";

type WorkspaceForm = {
  name: string;
  plan: string;
  status: string;
  is_deleted: boolean;
};

export const WorkspacesSection: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [page, setPage] = useState(1);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [form, setForm] = useState<WorkspaceForm | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspaces = async (opts?: { page?: number; search?: string }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWorkspaces({ page: opts?.page, search: opts?.search });
      const payload = res as Paginated<Workspace>;
      setWorkspaces(payload.results || []);
      setNext(payload.next || null);
      setPrevious(payload.previous || null);
      if (payload.results?.length) {
        const first = payload.results[0];
        setSelected((current) => current ?? first);
        setForm((current) => current ?? toForm(first));
      } else {
        setSelected(null);
        setForm(null);
      }
    } catch (err: any) {
      setError(err?.message || "Unable to load workspaces");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspaces({ page, search });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const toForm = (ws: Workspace): WorkspaceForm => ({
    name: ws.name || "",
    plan: ws.plan || "",
    status: ws.status || "active",
    is_deleted: ws.is_deleted,
  });

  const handleSelect = (ws: Workspace) => {
    setSelected(ws);
    setForm(toForm(ws));
    setMessage(null);
    setError(null);
  };

  const handleSave = async () => {
    if (!selected || !form) return;
    if (form.is_deleted && !selected.is_deleted) {
      const ok = window.confirm(
        "Soft-delete this workspace? The books remain in the database but the workspace will be inaccessible to the owner."
      );
      if (!ok) return;
    }
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await updateWorkspace(selected.id, form);
      setWorkspaces((list) => list.map((w) => (w.id === updated.id ? updated : w)));
      setSelected(updated);
      setForm(toForm(updated));
      setMessage("Saved");
    } catch (err: any) {
      setError(err?.message || "Unable to save workspace");
    } finally {
      setSaving(false);
    }
  };

  const tableRows = useMemo(
    () =>
      workspaces.map((w) => [
        <button
          key={`name-${w.id}`}
          className="text-left text-sm font-semibold text-slate-900"
          onClick={() => handleSelect(w)}
        >
          {w.name}
        </button>,
        <span key={`owner-${w.id}`} className="text-xs text-slate-700">
          {w.owner_email}
        </span>,
        <span key={`plan-${w.id}`} className="text-xs text-slate-700">
          {w.plan || "—"}
        </span>,
        <StatusPill
          key={`status-${w.id}`}
          tone={w.status === "active" ? "good" : w.status === "suspended" ? "warning" : "bad"}
          label={w.status}
        />,
        <span key={`unrec-${w.id}`} className="text-xs text-slate-700">
          {w.unreconciled_count ?? "—"}
        </span>,
        <StatusPill
          key={`ledger-${w.id}`}
          tone={w.ledger_status === "balanced" ? "good" : "warning"}
          label={w.ledger_status || "—"}
        />,
      ]),
    [workspaces]
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Workspaces</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Tenant control: plan, status, soft-delete, and reconciliation health at a glance.
          </p>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card title="All workspaces" subtitle="Search by name or owner email.">
          <div className="flex items-center gap-2 mb-3">
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              onBlur={() => loadWorkspaces({ page: 1, search })}
              placeholder="Search workspaces…"
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            />
            <button
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              onClick={() => loadWorkspaces({ page: 1, search })}
            >
              Search
            </button>
          </div>
          {loading ? (
            <p className="text-sm text-slate-600">Loading workspaces…</p>
          ) : error ? (
            <p className="text-sm text-rose-700">{error}</p>
          ) : (
            <>
              <SimpleTable
                headers={["Workspace", "Owner", "Plan", "Status", "Unreconciled", "Ledger"]}
                rows={tableRows}
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

        <Card title="Workspace details" subtitle={selected?.name || "Select a workspace"}>
          {selected && form ? (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Name</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Plan</label>
                <input
                  value={form.plan}
                  onChange={(e) => setForm({ ...form, plan: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Status</label>
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                >
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={form.is_deleted}
                  onChange={(e) => setForm({ ...form, is_deleted: e.target.checked })}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                Soft-delete
              </label>
              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-400 disabled:opacity-60"
                >
                  {saving ? "Saving…" : "Save changes"}
                </button>
              </div>
              {message && <p className="text-xs text-emerald-700">{message}</p>}
              {error && <p className="text-xs text-rose-700">{error}</p>}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select a workspace to view details.</p>
          )}
        </Card>
      </div>
    </div>
  );
};
