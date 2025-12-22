import React, { useEffect, useMemo, useState } from "react";
import {
  fetchSupportTickets,
  updateSupportTicket,
  addSupportTicketNote,
  createSupportTicket,
  type Paginated,
  type SupportTicket,
} from "./api";
import { Card, SimpleTable, StatusPill } from "./AdminUI";

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "OPEN", label: "Open" },
  { value: "IN_PROGRESS", label: "In progress" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "CLOSED", label: "Closed" },
];

const PRIORITY_OPTIONS = [
  { value: "", label: "All" },
  { value: "LOW", label: "Low" },
  { value: "NORMAL", label: "Normal" },
  { value: "HIGH", label: "High" },
  { value: "URGENT", label: "Urgent" },
];

type Role = "support" | "finance" | "engineer" | "superadmin";

export const SupportSection: React.FC<{ role?: Role }> = ({ role = "superadmin" }) => {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canEdit = role !== "support";

  // New ticket state
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [newSubject, setNewSubject] = useState("");
  const [newPriority, setNewPriority] = useState("NORMAL");
  const [creating, setCreating] = useState(false);

  const loadTickets = async (opts?: { page?: number }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSupportTickets({
        page: opts?.page ?? page,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        search: search || undefined,
      });
      const payload = res as Paginated<SupportTicket>;
      setTickets(payload.results || []);
      setNext(payload.next || null);
      setPrevious(payload.previous || null);
      if (payload.results?.length) {
        setSelected((current) => current ?? payload.results[0]);
      } else {
        setSelected(null);
      }
    } catch (err: any) {
      setError(err?.message || "Unable to load tickets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTickets({ page });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter, priorityFilter]);

  const refreshSelected = (updated: SupportTicket) => {
    setTickets((existing) => existing.map((t) => (t.id === updated.id ? updated : t)));
    setSelected(updated);
  };

  const handleSave = async () => {
    if (!selected || !canEdit) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateSupportTicket(selected.id, {
        status: selected.status,
        priority: selected.priority,
      });
      refreshSelected(updated);
    } catch (err: any) {
      setError(err?.message || "Unable to update ticket");
    } finally {
      setSaving(false);
    }
  };

  const handleAddNote = async () => {
    if (!selected || !noteBody.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await addSupportTicketNote(selected.id, noteBody.trim());
      refreshSelected(updated);
      setNoteBody("");
    } catch (err: any) {
      setError(err?.message || "Unable to add note");
    } finally {
      setSaving(false);
    }
  };

  const handleCreateTicket = async () => {
    if (!newSubject.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createSupportTicket({
        subject: newSubject.trim(),
        priority: newPriority,
        status: "OPEN",
      });
      setTickets((existing) => [created, ...existing]);
      setSelected(created);
      setNewSubject("");
      setNewPriority("NORMAL");
      setShowNewTicket(false);
    } catch (err: any) {
      setError(err?.message || "Unable to create ticket");
    } finally {
      setCreating(false);
    }
  };

  const rows = useMemo(
    () =>
      tickets.map((t) => [
        <button
          key={`subject-${t.id}`}
          onClick={() => setSelected(t)}
          className="text-left text-sm font-semibold text-slate-900"
        >
          {t.subject}
        </button>,
        <span key={`user-${t.id}`} className="text-xs text-slate-700">
          {t.user_email || "—"}
        </span>,
        <span key={`workspace-${t.id}`} className="text-xs text-slate-700">
          {t.workspace_name || "—"}
        </span>,
        <StatusPill
          key={`status-${t.id}`}
          tone={t.status === "CLOSED" ? "neutral" : t.status === "RESOLVED" ? "good" : "warning"}
          label={t.status.replace("_", " ")}
        />,
        <span key={`priority-${t.id}`} className="text-xs font-semibold text-slate-800">
          {t.priority}
        </span>,
        <span key={`created-${t.id}`} className="text-xs text-slate-500">
          {new Date(t.created_at).toLocaleString()}
        </span>,
      ]),
    [tickets]
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Support tickets</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Central queue for customer issues. Triage, update status, and leave internal notes.
          </p>
        </div>
        <button
          onClick={() => setShowNewTicket(!showNewTicket)}
          className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-400"
        >
          {showNewTicket ? "Cancel" : "+ New Ticket"}
        </button>
      </header>

      {/* New Ticket Form */}
      {showNewTicket && (
        <Card title="Create new ticket" subtitle="Enter ticket details">
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Subject *</label>
              <input
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
                placeholder="Describe the issue..."
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Priority</label>
              <select
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
              >
                <option value="LOW">Low</option>
                <option value="NORMAL">Normal</option>
                <option value="HIGH">High</option>
                <option value="URGENT">Urgent</option>
              </select>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreateTicket}
                disabled={!newSubject.trim() || creating}
                className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-400 disabled:opacity-60"
              >
                {creating ? "Creating..." : "Create Ticket"}
              </button>
              <button
                onClick={() => setShowNewTicket(false)}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
            {error && <p className="text-xs text-rose-700">{error}</p>}
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card title="Tickets" subtitle="Filter by status, priority, or search by subject/email/workspace.">
          <div className="flex flex-wrap gap-2 mb-3">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            >
              {PRIORITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onBlur={() => {
                setPage(1);
                loadTickets({ page: 1 });
              }}
              placeholder="Search subject, user, workspace..."
              className="flex-1 min-w-[200px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            />
            <button
              onClick={() => loadTickets({ page: 1 })}
              className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm"
            >
              Apply
            </button>
          </div>
          {loading ? (
            <p className="text-sm text-slate-600">Loading tickets…</p>
          ) : error ? (
            <p className="text-sm text-rose-700">{error}</p>
          ) : (
            <>
              <SimpleTable
                headers={["Subject", "User", "Workspace", "Status", "Priority", "Created"]}
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

        <Card
          title={selected?.subject || "Select a ticket"}
          subtitle={selected ? selected.user_email || selected.workspace_name || "Unassigned" : ""}
        >
          {selected ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 text-sm text-slate-800">
                <div>
                  <p className="text-xs text-slate-500">Status</p>
                  <select
                    value={selected.status}
                    disabled={!canEdit}
                    onChange={(e) => setSelected({ ...selected, status: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50 disabled:opacity-50"
                  >
                    {STATUS_OPTIONS.filter((o) => o.value).map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Priority</p>
                  <select
                    value={selected.priority}
                    disabled={!canEdit}
                    onChange={(e) => setSelected({ ...selected, priority: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50 disabled:opacity-50"
                  >
                    {PRIORITY_OPTIONS.filter((o) => o.value).map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="text-xs text-slate-600">
                Source: <span className="font-semibold text-slate-800">{selected.source}</span>
              </p>
              <p className="text-xs text-slate-500">
                Created {new Date(selected.created_at).toLocaleString()} · Updated{" "}
                {new Date(selected.updated_at).toLocaleString()}
              </p>
              {canEdit && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-400 disabled:opacity-60"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              )}

              <div className="border-t border-slate-200 pt-3">
                <h4 className="text-sm font-semibold text-slate-900 mb-2">Notes</h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {selected.notes && selected.notes.length > 0 ? (
                    selected.notes.map((note) => (
                      <div key={note.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <p className="text-xs text-slate-700">{note.body}</p>
                        <p className="text-[11px] text-slate-500 mt-1">
                          {note.admin_email || "Admin"} · {new Date(note.created_at).toLocaleString()}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-600">No notes yet.</p>
                  )}
                </div>
                <div className="mt-3 space-y-2">
                  <textarea
                    value={noteBody}
                    onChange={(e) => setNoteBody(e.target.value)}
                    placeholder="Add an internal note…"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                  />
                  <button
                    onClick={handleAddNote}
                    disabled={!noteBody.trim() || saving}
                    className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Add note
                  </button>
                </div>
              </div>
              {error && <p className="text-xs text-rose-700">{error}</p>}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select a ticket to view details.</p>
          )}
        </Card>
      </div>
    </div>
  );
};
