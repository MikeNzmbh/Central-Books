import React, { useEffect, useMemo, useState } from "react";
import { fetchUsers, startImpersonation, updateUser, type Paginated, type User } from "./api";
import { Card, SimpleTable, StatusPill } from "./AdminUI";

type UserForm = {
  first_name: string;
  last_name: string;
  email: string;
  is_active: boolean;
};

export const UsersSection: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [page, setPage] = useState(1);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [googleFilter, setGoogleFilter] = useState<"all" | "yes" | "no">("all");
  const [selected, setSelected] = useState<User | null>(null);
  const [form, setForm] = useState<UserForm | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [impersonateLoading, setImpersonateLoading] = useState<number | null>(null);

  const formatDate = (value?: string | null, withTime = false) => {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    const formatter = new Intl.DateTimeFormat(
      undefined,
      withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }
    );
    return formatter.format(date);
  };

  const loadUsers = async (opts?: { page?: number; search?: string }) => {
    setLoading(true);
    setError(null);
    const targetPage = opts?.page ?? page;
    const query = (opts?.search ?? search ?? "").trim();
    try {
      const res = await fetchUsers({
        page: targetPage,
        q: query || undefined,
        is_active: statusFilter === "all" ? undefined : statusFilter === "active" ? "true" : "false",
        has_google: googleFilter === "all" ? undefined : googleFilter === "yes" ? "true" : "false",
      });
      const payload = res as Paginated<User>;
      setUsers(payload.results || []);
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
      setError(err?.message || "Unable to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers({ page, search });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter, googleFilter]);

  const toForm = (user: User): UserForm => ({
    first_name: user.first_name || "",
    last_name: user.last_name || "",
    email: user.email || "",
    is_active: user.is_active,
  });

  const handleSelect = (user: User) => {
    setSelected(user);
    setForm(toForm(user));
    setMessage(null);
    setError(null);
  };

  const handleSave = async () => {
    if (!selected || !form) return;
    const isSuspending = selected.is_active && !form.is_active;
    if (isSuspending && !window.confirm("Suspend this user? They won’t be able to log in until reactivated.")) {
      return;
    }
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await updateUser(selected.id, form);
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
      setSelected(updated);
      setForm(toForm(updated));
      setMessage("Saved");
    } catch (err: any) {
      setError(err?.message || "Unable to save user");
    } finally {
      setSaving(false);
    }
  };

  const handleImpersonate = async (userId: number) => {
    setImpersonateLoading(userId);
    setError(null);
    setMessage(null);
    try {
      const { redirect_url } = await startImpersonation(userId);
      if (redirect_url) {
        window.location.href = redirect_url;
      }
    } catch (err: any) {
      setError(err?.message || "Unable to start impersonation");
    } finally {
      setImpersonateLoading(null);
    }
  };

  const buildAuthSummary = (user: User) => {
    const providers = user.auth_providers || [];
    const hasGoogle = user.has_google_login || providers.includes("google");
    const parts = [];
    if (user.has_usable_password) parts.push("Password");
    if (hasGoogle) parts.push("Google");
    const rest = providers.filter((p) => p !== "google");
    if (rest.length) parts.push(rest.join(", "));
    return parts.length ? parts.join(" + ") : "Unknown";
  };

  const tableRows = useMemo(
    () =>
      users.map((u) => [
        <button
          key={`name-${u.id}`}
          className="text-left text-sm font-semibold text-slate-900"
          onClick={() => handleSelect(u)}
        >
          {u.full_name || `${u.first_name || ""} ${u.last_name || ""}` || u.email}
        </button>,
        <span key={`email-${u.id}`} className="text-xs text-slate-700">
          {u.email}
        </span>,
        <StatusPill
          key={`status-${u.id}`}
          tone={u.is_active ? "good" : "warning"}
          label={u.is_active ? "Active" : "Suspended"}
        />,
        <span key={`login-${u.id}`} className="text-xs text-slate-500">
          {formatDate(u.last_login, true)}
        </span>,
        <span key={`joined-${u.id}`} className="text-xs text-slate-500">
          {formatDate(u.date_joined)}
        </span>,
        <span key={`workspace-${u.id}`} className="text-xs text-slate-700">
          {u.workspace_count ?? 0}
        </span>,
        <span key={`auth-${u.id}`} className="text-xs text-slate-700">
          {buildAuthSummary(u)}
        </span>,
      ]),
    [users]
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Users</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Global user management across all tenants. Suspend, edit email, or impersonate for support.
          </p>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card title="All users" subtitle="Search by name or email.">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              onBlur={() => loadUsers({ page: 1, search })}
              placeholder="Search users…"
              aria-label="Search users"
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            />
            <button
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              onClick={() => {
                setPage(1);
                loadUsers({ page: 1, search });
              }}
            >
              Search
            </button>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as typeof statusFilter);
                setPage(1);
              }}
              aria-label="Status filter"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <select
              value={googleFilter}
              onChange={(e) => {
                setGoogleFilter(e.target.value as typeof googleFilter);
                setPage(1);
              }}
              aria-label="Google login filter"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
            >
              <option value="all">All auth</option>
              <option value="yes">Has Google</option>
              <option value="no">No Google</option>
            </select>
          </div>
          {loading ? (
            <p className="text-sm text-slate-600">Loading users…</p>
          ) : error ? (
            <p className="text-sm text-rose-700">{error}</p>
          ) : (
            <>
              <SimpleTable
                headers={["Name", "Email", "Status", "Last login", "Joined", "Workspaces", "Auth"]}
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

        <Card title="User details" subtitle={selected?.email || "Select a user"}>
          {selected && form ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
                <div>
                  <p className="font-semibold text-slate-800">Auth</p>
                  <p>{buildAuthSummary(selected)}</p>
                  <p>
                    Password set:{" "}
                    <span className="font-semibold">{selected.has_usable_password ? "Yes" : "No"}</span>
                  </p>
                  <p>Linked social: {selected.social_account_count ?? (selected.auth_providers?.length || 0)}</p>
                </div>
                <div>
                  <p className="font-semibold text-slate-800">Access</p>
                  <p>Role: {selected.admin_role || "—"}</p>
                  <p>Staff: {selected.is_staff ? "Yes" : "No"} · Superuser: {selected.is_superuser ? "Yes" : "No"}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
                <div>
                  <p className="font-semibold text-slate-800">Activity</p>
                  <p>Last login: {formatDate(selected.last_login, true)}</p>
                  <p>Joined: {formatDate(selected.date_joined)}</p>
                </div>
                <div>
                  <p className="font-semibold text-slate-800">Workspaces</p>
                  <p>Count: {selected.workspace_count ?? 0}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">First name</label>
                  <input
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">Last name</label>
                  <input
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Email</label>
                <input
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                Active
              </label>
              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-400 disabled:opacity-60"
                >
                  {saving ? "Saving…" : "Save changes"}
                </button>
                <button
                  onClick={() => selected && handleImpersonate(selected.id)}
                  disabled={!selected || impersonateLoading === selected.id}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-60"
                >
                  {impersonateLoading === selected?.id ? "Starting…" : "Impersonate"}
                </button>
              </div>
              {message && <p className="text-xs text-emerald-700">{message}</p>}
              {error && <p className="text-xs text-rose-700">{error}</p>}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select a user to view details.</p>
          )}
        </Card>
      </div>
    </div>
  );
};
