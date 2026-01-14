import React, { useCallback, useEffect, useMemo, useState } from "react";
import { getCsrfToken } from "../utils/csrf";
import { PERMISSIONS, type PermissionLevel, type PermissionScopeType } from "../permissions/permissionsRegistry";
import type { RoleSummary } from "./useRoles";

type OverrideRow = {
  action: string;
  effect: "ALLOW" | "DENY";
  level_override?: PermissionLevel | null;
  scope_override?: any;
};

type UserRow = {
  user_id: number;
  email: string;
  full_name: string;
  membership_id: number;
  role_key: string;
  role_definition_id: number | null;
  overrides: OverrideRow[];
};

const LEVELS: { value: PermissionLevel | ""; label: string }[] = [
  { value: "", label: "Default" },
  { value: "none", label: "None" },
  { value: "view", label: "View" },
  { value: "edit", label: "Edit" },
  { value: "approve", label: "Approve" },
];

const SCOPES: { value: PermissionScopeType; label: string }[] = [
  { value: "all", label: "All" },
  { value: "own_department", label: "Own department" },
  { value: "own_created", label: "Own created" },
  { value: "selected_accounts", label: "Selected accounts" },
];

function parseAccountIds(raw: string): number[] {
  return raw
    .split(/[,\s]+/g)
    .map((v) => v.trim())
    .filter(Boolean)
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n))
    .map((n) => Math.trunc(n));
}

export const UserRoleOverridesPanel: React.FC<{ roles: RoleSummary[] }> = ({ roles }) => {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedUserId, setExpandedUserId] = useState<number | null>(null);
  const [draftOverrides, setDraftOverrides] = useState<Record<number, OverrideRow[]>>({});

  const roleOptions = useMemo(
    () =>
      roles.map((r) => ({
        id: r.id,
        label: `${r.label}${r.is_builtin ? " (Template)" : ""}`,
      })),
    [roles],
  );

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/settings/users/", { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Unable to load users.");
      setUsers((data.users || []) as UserRow[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load users.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const updateUserMembership = useCallback(
    async (userId: number, payload: any) => {
      setSaving(true);
      setError(null);
      try {
        const csrfToken = getCsrfToken();
        const res = await fetch(`/api/settings/users/${userId}/membership/`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || "Unable to update user.");
        await loadUsers();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to update user.");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [loadUsers],
  );

  const permissionOptions = useMemo(
    () =>
      PERMISSIONS.map((p) => ({
        action: p.action,
        label: `${p.label} — ${p.action}`,
      })),
    [],
  );

  return (
    <div className="rounded-3xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-100">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">User assignments</h3>
            <p className="text-xs text-slate-500">Assign roles and apply per-user overrides.</p>
          </div>
          <button
            type="button"
            onClick={loadUsers}
            className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            disabled={loading || saving}
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="p-6">
        {error && (
          <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-sm text-slate-500">Loading users…</div>
        ) : (
          <div className="space-y-3">
            {users.map((u) => {
              const expanded = expandedUserId === u.user_id;
              const overrides = draftOverrides[u.user_id] ?? u.overrides ?? [];
              return (
                <div key={u.user_id} className="rounded-2xl border border-slate-200 bg-white">
                  <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-900 truncate">{u.full_name}</div>
                      <div className="text-xs text-slate-500 truncate">{u.email}</div>
                    </div>
                    <div className="flex flex-col gap-2 md:flex-row md:items-center">
                      <select
                        value={u.role_definition_id ?? ""}
                        onChange={async (e) => {
                          const nextId = e.target.value ? Number(e.target.value) : null;
                          await updateUserMembership(u.user_id, { role_definition_id: nextId });
                        }}
                        disabled={saving}
                        className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                      >
                        {roleOptions.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          setExpandedUserId(expanded ? null : u.user_id);
                          if (!expanded) {
                            setDraftOverrides((prev) => ({ ...prev, [u.user_id]: (u.overrides || []).map((o) => ({ ...o })) }));
                          }
                        }}
                        className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                        disabled={saving}
                      >
                        {expanded ? "Hide overrides" : `Overrides (${(u.overrides || []).length})`}
                      </button>
                    </div>
                  </div>

                  {expanded ? (
                    <div className="border-t border-slate-100 p-4 bg-slate-50">
                      <div className="space-y-3">
                        {(overrides.length ? overrides : [{ action: "", effect: "ALLOW" as const }]).map((o, idx) => {
                          const scopeType = (o.scope_override?.type || "all") as PermissionScopeType;
                          const accountIds = scopeType === "selected_accounts" ? (o.scope_override?.account_ids || []) : [];
                          return (
                            <div key={`${u.user_id}-${idx}`} className="rounded-2xl border border-slate-200 bg-white p-3">
                              <div className="grid gap-2 md:grid-cols-4">
                                <div className="md:col-span-2">
                                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Action</label>
                                  <select
                                    value={o.action}
                                    onChange={(e) => {
                                      const next = [...overrides];
                                      next[idx] = { ...next[idx], action: e.target.value };
                                      setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                                    }}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                  >
                                    <option value="">Select an action…</option>
                                    {permissionOptions.map((p) => (
                                      <option key={p.action} value={p.action}>
                                        {p.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>

                                <div>
                                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Effect</label>
                                  <select
                                    value={o.effect}
                                    onChange={(e) => {
                                      const next = [...overrides];
                                      next[idx] = { ...next[idx], effect: e.target.value as "ALLOW" | "DENY" };
                                      setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                                    }}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                  >
                                    <option value="ALLOW">Allow</option>
                                    <option value="DENY">Deny</option>
                                  </select>
                                </div>

                                <div>
                                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Level</label>
                                  <select
                                    value={(o.level_override as any) ?? ""}
                                    onChange={(e) => {
                                      const next = [...overrides];
                                      next[idx] = { ...next[idx], level_override: (e.target.value || null) as any };
                                      setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                                    }}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                  >
                                    {LEVELS.map((l) => (
                                      <option key={l.value || "default"} value={l.value}>
                                        {l.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              </div>

                              <div className="mt-3 grid gap-2 md:grid-cols-3">
                                <div>
                                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Scope</label>
                                  <select
                                    value={scopeType}
                                    onChange={(e) => {
                                      const next = [...overrides];
                                      next[idx] = { ...next[idx], scope_override: { type: e.target.value } };
                                      setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                                    }}
                                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                  >
                                    {SCOPES.map((s) => (
                                      <option key={s.value} value={s.value}>
                                        {s.label}
                                      </option>
                                    ))}
                                  </select>
                                </div>

                                {scopeType === "selected_accounts" ? (
                                  <div className="md:col-span-2">
                                    <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                      Bank account IDs
                                    </label>
                                    <input
                                      type="text"
                                      value={accountIds.join(", ")}
                                      onChange={(e) => {
                                        const next = [...overrides];
                                        next[idx] = {
                                          ...next[idx],
                                          scope_override: { type: "selected_accounts", account_ids: parseAccountIds(e.target.value) },
                                        };
                                        setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                                      }}
                                      className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                      placeholder="e.g. 12, 15"
                                    />
                                  </div>
                                ) : null}
                              </div>

                              <div className="mt-3 flex justify-end">
                                <button
                                  type="button"
                                  onClick={() => {
                                    const next = overrides.filter((_, i) => i !== idx);
                                    setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                                  }}
                                  className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                                >
                                  Remove
                                </button>
                              </div>
                            </div>
                          );
                        })}

                        <div className="flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() => {
                              const next = [...overrides, { action: "", effect: "ALLOW" as const, level_override: null, scope_override: { type: "all" } }];
                              setDraftOverrides((prev) => ({ ...prev, [u.user_id]: next }));
                            }}
                            className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            Add override
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              const cleaned = (draftOverrides[u.user_id] || [])
                                .filter((row) => row.action && row.effect)
                                .map((row) => ({
                                  action: row.action,
                                  effect: row.effect,
                                  level_override: row.level_override || null,
                                  scope_override: row.scope_override ?? null,
                                }));
                              await updateUserMembership(u.user_id, { overrides: cleaned });
                            }}
                            disabled={saving}
                            className="rounded-2xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                          >
                            {saving ? "Saving…" : "Save overrides"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}

            {!users.length && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                No users found for this workspace.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default UserRoleOverridesPanel;

