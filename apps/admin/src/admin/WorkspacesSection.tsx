import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchWorkspaces,
  updateWorkspace,
  type Paginated,
  type Workspace,
} from "./api";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
  Input,
  ScrollArea,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Separator,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui";

// ----------------------
// Helpers
// ----------------------

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

function statusLabel(status: string): string {
  switch (status) {
    case "active": return "Active";
    case "suspended": return "Suspended";
    case "soft_deleted": return "Soft deleted";
    default: return status || "Unknown";
  }
}

function statusColorClasses(status: string): string {
  switch (status) {
    case "active": return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "suspended": return "bg-amber-50 text-amber-700 border-amber-200";
    case "soft_deleted": return "bg-rose-50 text-rose-700 border-rose-200";
    default: return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

function ledgerStatusLabel(status: string | undefined): string {
  switch (status) {
    case "balanced": return "Balanced";
    case "unbalanced": return "Unbalanced";
    case "warning": return "Needs review";
    default: return status || "Unknown";
  }
}

function ledgerStatusClasses(status: string | undefined): string {
  switch (status) {
    case "balanced": return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "unbalanced": return "bg-rose-50 text-rose-700 border-rose-200";
    case "warning": return "bg-amber-50 text-amber-700 border-amber-200";
    default: return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

function planBadgeClasses(plan: string | null): string {
  if (plan === "Pro" || plan === "Enterprise") return "bg-slate-900 text-slate-50";
  return "bg-slate-100 text-slate-700";
}

// ----------------------
// Page
// ----------------------

const PAGE_SIZE = 12;

export const WorkspacesSection: React.FC<{ roleLevel?: number }> = ({ roleLevel = 1 }) => {
  // NOTE: this section is viewable by SUPPORT, but mutations require OPS+.
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const loadWorkspaces = useCallback(async (opts: { page?: number; search?: string } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = {
        page: opts.page ?? page,
        search: opts.search ?? search,
        page_size: PAGE_SIZE,
      };
      const data: Paginated<Workspace> = await fetchWorkspaces(params);
      setWorkspaces(data.results);
      setNext(data.next);
      setPrevious(data.previous);
      if (data.results.length > 0 && !selectedId) {
        setSelectedId(data.results[0].id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load workspaces");
    } finally {
      setLoading(false);
    }
  }, [page, search, selectedId]);

  useEffect(() => {
    loadWorkspaces({ page, search });
  }, [page]);

  const selected = useMemo(
    () => workspaces.find((w) => w.id === selectedId) || workspaces[0] || null,
    [workspaces, selectedId]
  );

  const handleSelectWorkspace = useCallback((id: number) => {
    setSelectedId(id);
  }, []);

  const goPrev = () => setPage((p) => Math.max(1, p - 1));
  const goNext = () => setPage((p) => p + 1);
  const totalPages = next || previous ? (next ? page + 1 : page) : page;

  return (
    <div className="min-h-screen space-y-4">
      {/* Page Header */}
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">Workspaces</h1>
          <p className="mt-1 text-sm text-slate-600">
            Cross-tenant control for all Clover Books workspaces. Search, inspect, and govern ledgers from one Apple-clean console.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8 rounded-full px-3 text-xs border-slate-200">
            ⚙️ Admin policy ▾
          </Button>
          <Button size="sm" className="h-8 rounded-full bg-slate-900 px-3 text-xs text-slate-50 hover:bg-black">
            🔄 Sync metrics
          </Button>
        </div>
      </header>

      {/* Two Column Layout */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)] xl:grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)]">

        {/* LEFT: Workspace List */}
        <section className="flex flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white/80 p-3 shadow-sm backdrop-blur" style={{ height: "70vh" }}>
          <div className="flex items-center gap-2 px-1 pb-3">
            <div className="relative flex-1">
              <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              </span>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadWorkspaces({ page: 1, search })}
                placeholder="Search by workspace or owner…"
                className="h-8 w-full rounded-full border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-900 outline-none placeholder:text-slate-400 focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">
              {workspaces.length} visible
            </span>
          </div>

          <div className="flex-1 overflow-hidden rounded-2xl border border-slate-100 bg-slate-50/60">
            {/* Table Header */}
            <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2 text-[11px] font-medium text-slate-500">
              <span>Workspace</span>
              <div className="grid grid-cols-3 gap-2 text-right">
                <span>Unreconciled</span>
                <span>Ledger</span>
                <span>Plan</span>
              </div>
            </div>

            {/* Workspace List */}
            <div className="h-full overflow-y-auto">
              {loading && (
                <div className="flex h-32 items-center justify-center text-xs text-slate-500">
                  ⏳ Loading workspaces…
                </div>
              )}
              {!loading && error && (
                <div className="flex h-32 flex-col items-center justify-center gap-2 text-xs text-rose-500">
                  <span>{error}</span>
                  <Button variant="outline" size="sm" onClick={() => loadWorkspaces()}>Retry</Button>
                </div>
              )}
              {!loading && !error && workspaces.length === 0 && (
                <div className="flex h-32 items-center justify-center text-xs text-slate-500">
                  No workspaces match this search.
                </div>
              )}
              {!loading && !error && workspaces.map((ws) => {
                const isSelected = selected?.id === ws.id;
                return (
                  <button
                    key={ws.id}
                    type="button"
                    onClick={() => handleSelectWorkspace(ws.id)}
                    className={`group flex w-full items-stretch gap-2 border-b border-slate-100 px-3 py-2.5 text-left text-xs transition ${isSelected ? "bg-white shadow-sm" : "bg-slate-50/0 hover:bg-white"
                      }`}
                  >
                    <div className="flex min-w-0 flex-1 flex-col">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-medium text-slate-900">{ws.name}</p>
                          <p className="truncate text-[11px] text-slate-500">{ws.owner_email}</p>
                        </div>
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border ${statusColorClasses(ws.status)}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${ws.status === "active" ? "bg-emerald-500" : ws.status === "suspended" ? "bg-amber-500" : "bg-rose-500"}`} />
                          {statusLabel(ws.status)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-[10px] text-slate-500">
                        <span className="inline-flex items-center gap-1">
                          👥 — users
                        </span>
                        <span>Last activity {formatDate(ws.created_at)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-[11px] text-slate-600">
                      <span className="w-[72px] text-right">{ws.unreconciled_count ?? 0} tx</span>
                      <span className={`inline-flex min-w-[86px] justify-end rounded-full px-2 py-0.5 text-[10px] font-medium border ${ledgerStatusClasses(ws.ledger_status)}`}>
                        {ledgerStatusLabel(ws.ledger_status)}
                      </span>
                      <span className="w-[72px] text-right">{ws.plan || "—"}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Pagination */}
          <div className="mt-3 flex items-center justify-between px-1 text-[11px] text-slate-500">
            <span>Page {page} of {totalPages}</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={!previous}
                onClick={goPrev}
                className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 disabled:opacity-40"
              >
                Prev
              </button>
              <button
                type="button"
                disabled={!next}
                onClick={goNext}
                className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </section>

        {/* RIGHT: Workspace Details */}
        {selected ? (
          <WorkspaceDetailsPanel workspace={selected} onUpdate={loadWorkspaces} roleLevel={roleLevel} />
        ) : (
          <div className="flex h-full items-center justify-center rounded-3xl border border-slate-100 bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 p-10 text-center shadow-sm">
            <div className="flex flex-col items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-slate-50">🏢</div>
              <p className="text-sm font-medium text-slate-900">Select a workspace</p>
              <p className="text-xs text-slate-500">Choose one from the list to inspect.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ----------------------
// Workspace Details Panel
// ----------------------

interface WorkspaceDetailsPanelProps {
  workspace: Workspace;
  onUpdate: () => void;
  roleLevel: number;
}

const WorkspaceDetailsPanel: React.FC<WorkspaceDetailsPanelProps> = ({ workspace, onUpdate, roleLevel }) => {
  const [name, setName] = useState(workspace.name || "");
  const [plan, setPlan] = useState(workspace.plan || "");
  const [status, setStatus] = useState(workspace.status || "active");
  const [isDeleted, setIsDeleted] = useState(workspace.is_deleted);
  const [notes, setNotes] = useState("");
  const [aiInsights, setAiInsights] = useState("Good candidate for new beta features and stress tests.");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("ai");
  const [show360, setShow360] = useState(true);

  useEffect(() => {
    setName(workspace.name || "");
    setPlan(workspace.plan || "");
    setStatus(workspace.status || "active");
    setIsDeleted(workspace.is_deleted);
    setMessage(null);
    setError(null);
  }, [workspace.id]);

  const canEdit = roleLevel >= 2;
  const canDelete = roleLevel >= 4;

  const handleSave = async () => {
    if (!canEdit) {
      setError("View-only: OPS or higher required to edit workspaces.");
      return;
    }
    const wantsDelete = Boolean(isDeleted) && !workspace.is_deleted;
    if (wantsDelete && !canDelete) {
      setError("Soft-delete requires superadmin approval rights.");
      return;
    }
    const payload: Record<string, unknown> = { name, plan: plan || null, status, is_deleted: isDeleted };
    if (wantsDelete) {
      const reason = window.prompt("Reason required: Soft-delete workspace (approval required)");
      if (reason === null) return;
      if (!reason.trim()) {
        window.alert("Reason is required.");
        return;
      }
      payload.reason = reason.trim();
    }
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const res = await updateWorkspace(workspace.id, payload);
      if ("approval_required" in res && res.approval_required) {
        setMessage(`Saved. Created approval request: ${res.approval_request_id}`);
        setIsDeleted(Boolean(workspace.is_deleted));
      } else {
        setMessage("Workspace updated successfully");
      }
      onUpdate();
    } catch (err: any) {
      setError(err?.message || "Failed to update workspace");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="flex flex-col gap-3" style={{ height: "70vh" }}>
      {/* Header Card with gradient glow effect */}
      <div className="rounded-3xl border border-slate-100 bg-gradient-to-br from-slate-50 via-white to-slate-50 p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!canEdit}
                className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-900 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
              />
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium ${planBadgeClasses(plan)}`}>
                ✨ {plan || "No"} plan
              </span>
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium border ${statusColorClasses(status)}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${status === "active" ? "bg-emerald-500" : status === "suspended" ? "bg-amber-500" : "bg-rose-500"}`} />
                {statusLabel(status)}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              Owner<span className="font-medium text-slate-800"> {workspace.owner_email?.split("@")[0] || "Unknown"}</span> · {workspace.owner_email}
            </p>
            <p className="mt-0.5 text-[11px] text-slate-400">
              Created {formatDate(workspace.created_at)} · Last activity {formatDate(workspace.created_at)}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className="inline-flex items-center gap-1 rounded-2xl bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-slate-50">
              ✨ Internal control plane
            </span>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !canEdit}
              className="inline-flex items-center gap-1 rounded-2xl bg-slate-900 px-3 py-1.5 text-[11px] font-medium text-slate-50 shadow-sm hover:bg-black disabled:opacity-50"
            >
              {saving ? "⏳ Saving…" : "💾 Save changes"}
            </button>
          </div>
        </div>

        {/* Stats Row – 4 columns */}
        <div className="mt-4 grid gap-3 grid-cols-4">
          <div className="rounded-2xl bg-slate-900 text-slate-50 px-3.5 py-3">
            <p className="text-[11px] text-slate-300">Members</p>
            <p className="mt-1 text-lg font-semibold">—</p>
            <p className="mt-0.5 text-[11px] text-slate-300">Across all roles</p>
          </div>
          <div className="rounded-2xl bg-slate-50 px-3.5 py-3 border border-slate-100">
            <p className="text-[11px] text-slate-500">Unreconciled</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{(workspace.unreconciled_count ?? 0).toLocaleString()}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">Bank lines pending review</p>
          </div>
          <div className="rounded-2xl bg-slate-50 px-3.5 py-3 border border-slate-100">
            <p className="text-[11px] text-slate-500">Ledger status</p>
            <p className="mt-1 flex items-center gap-1.5">
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium border ${ledgerStatusClasses(workspace.ledger_status)}`}>
                {ledgerStatusLabel(workspace.ledger_status)}
              </span>
            </p>
            <p className="mt-0.5 text-[11px] text-slate-500">Derived from last close</p>
          </div>
          <div className="rounded-2xl bg-slate-50 px-3.5 py-3 border border-slate-100">
            <p className="text-[11px] text-slate-500">Connections</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">— banks</p>
            <p className="mt-0.5 text-[11px] text-slate-500">—</p>
          </div>
        </div>
      </div>

      {/* Tabs Row with Soft-delete + Hide 360° */}
      <div className="flex items-center justify-between gap-2">
        <div className="inline-flex rounded-full bg-slate-100 p-0.5 text-[11px] font-medium text-slate-600">
          {["Overview", "Security & limits", "Billing", "Activity & notes", "AI & automation"].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab.toLowerCase().replace(/ & /g, "_").replace(/ /g, "_"))}
              className={`rounded-full px-3 py-1 ${activeTab === tab.toLowerCase().replace(/ & /g, "_").replace(/ /g, "_")
                  ? "bg-white text-slate-900 shadow-sm"
                  : ""
                }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-[11px]">
          <label className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={isDeleted}
              onChange={(e) => setIsDeleted(e.target.checked)}
              disabled={!canDelete}
              className="h-3 w-3 rounded border-slate-300 text-slate-900"
            />
            Soft delete tenant
          </label>
          <button
            type="button"
            onClick={() => setShow360((v) => !v)}
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-700"
          >
            🌐 {show360 ? "Hide 360°" : "Show 360°"}
          </button>
        </div>
      </div>

      {/* Main content: Left Tab + Right 360° */}
      <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.2fr)]">
        {/* Left: Tab Content */}
        <div className="flex min-h-0 flex-col gap-3">
          {/* AI & automation tab (dark) */}
          {activeTab === "ai_&_automation" && (
            <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-700 bg-slate-950 p-3 text-slate-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span>✨</span>
                  <span className="text-xs font-medium">AI & automation</span>
                </div>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">Disabled</span>
              </div>
              <p className="text-[11px] text-slate-200">
                Control whether this workspace participates in Companion suggestions, tax nudges, and automated workflows.
              </p>
              <textarea
                value={aiInsights}
                onChange={(e) => setAiInsights(e.target.value)}
                placeholder="Workspace-specific AI notes, risk flags, or beta enrollment details."
                className="min-h-[96px] w-full resize-none rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-[11px] text-slate-100 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-500/50"
              />
            </div>
          )}

          {/* Overview tab */}
          {activeTab === "overview" && (
            <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-3 text-[11px] text-slate-700">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-900">Workspace profile</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">Owner & plan</span>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <div className="space-y-1">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">Owner</p>
                  <p className="text-xs font-medium text-slate-900">{workspace.owner_email}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">Created</p>
                  <p className="text-xs font-medium text-slate-900">{formatDate(workspace.created_at)}</p>
                </div>
              </div>
            </div>
          )}

          {/* Security tab */}
          {activeTab === "security_&_limits" && (
            <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-3 text-[11px] text-slate-700">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-900">Security & limits</span>
                <span>🛡️</span>
              </div>
              <div className="space-y-1">
                <p className="text-[10px] uppercase tracking-wide text-slate-400">Status</p>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  disabled={!canEdit}
                  className="h-8 w-full rounded-xl border border-slate-200 bg-slate-50 px-2 text-[11px] text-slate-900 focus:border-sky-400 focus:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="active">Active</option>
                  <option value="suspended">Suspended</option>
                  <option value="soft_deleted">Soft deleted</option>
                </select>
              </div>
              <p className="text-[11px] text-slate-500">Limits are derived from plan. Per-tenant overrides will be available later.</p>
            </div>
          )}

          {/* Billing tab */}
          {activeTab === "billing" && (
            <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-3 text-[11px] text-slate-700">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-900">Billing</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">Plan & invoice links</span>
              </div>
              <div className="space-y-1">
                <p className="text-[10px] uppercase tracking-wide text-slate-400">Plan</p>
                <select
                  value={plan || ""}
                  onChange={(e) => setPlan(e.target.value)}
                  disabled={!canEdit}
                  className="h-8 w-full rounded-xl border border-slate-200 bg-slate-50 px-2 text-[11px] text-slate-900 focus:border-sky-400 focus:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="">No plan</option>
                  <option value="Free">Free</option>
                  <option value="Starter">Starter</option>
                  <option value="Pro">Pro</option>
                  <option value="Enterprise">Enterprise</option>
                </select>
              </div>
              <p className="text-[11px] text-slate-500">Billing integration cards (Stripe, invoices) coming soon.</p>
            </div>
          )}

          {/* Activity & notes tab */}
          {activeTab === "activity_&_notes" && (
            <div className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-100 bg-white/80 p-3 text-[11px] text-slate-700">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-900">Internal notes</span>
                <span>ℹ️</span>
              </div>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add internal context for support and success teams. Customers never see this."
                className="min-h-[96px] w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-900 outline-none focus:border-sky-400 focus:bg-white"
              />
            </div>
          )}
        </div>

        {/* Right: 360° view + Recent activity */}
        <div className="flex min-h-0 flex-col gap-3">
          {show360 && (
            <div className="flex-1 rounded-2xl border border-slate-100 bg-white/90 p-3 text-[11px] text-slate-700">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span>🌐</span>
                  <span className="text-xs font-medium text-slate-900">360° workspace view</span>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">Read-only diagnostic</span>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="flex flex-col gap-2 rounded-2xl bg-slate-50 p-3 border border-slate-100">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">Reconciliation</p>
                  <p className="text-xs font-semibold text-slate-900">{(workspace.unreconciled_count ?? 0).toLocaleString()} unreconciled lines</p>
                  <p className="text-[11px] text-slate-600">Use the banking & reconciliation console to drill into specific statements and matches.</p>
                </div>
                <div className="flex flex-col gap-2 rounded-2xl bg-slate-50 p-3 border border-slate-100">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">Tax Guardian</p>
                  <p className="text-xs font-semibold text-slate-900">Linked to Tax Guardian periods</p>
                  <p className="text-[11px] text-slate-600">Open anomalies, due dates, and filing workflow live under the Tax Guardian console.</p>
                </div>
                <div className="flex flex-col gap-2 rounded-2xl bg-slate-50 p-3 border border-slate-100">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">Health & alerts</p>
                  <p className="text-xs font-semibold text-slate-900">Ledger {ledgerStatusLabel(workspace.ledger_status)}</p>
                  <p className="text-[11px] text-slate-600">Any AI nudges, anomaly clusters, or failed jobs related to this workspace will aggregate here.</p>
                </div>
              </div>
            </div>
          )}

          {/* Recent admin activity (dark) */}
          <div className="rounded-2xl border border-slate-100 bg-slate-900 px-3.5 py-3 text-[11px] text-slate-50">
            <div className="flex items-start gap-2">
              <span className="text-sky-300">📊</span>
              <div className="flex-1">
                <p className="text-xs font-semibold">Recent admin activity</p>
                <p className="mt-0.5 text-[11px] text-slate-300">
                  Recent changes, reconciliations, and tax filings for this workspace will surface here to shorten debugging loops.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {message && <p className="text-xs text-emerald-700">{message}</p>}
      {error && <p className="text-xs text-rose-700">{error}</p>}
    </section>
  );
};

export default WorkspacesSection;
