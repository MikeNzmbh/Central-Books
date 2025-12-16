import React, { useEffect, useMemo, useState } from "react";
import { PERMISSION_CATEGORIES, getPermissionsByCategory, type PermissionLevel, type PermissionScopeType } from "../permissions/permissionsRegistry";
import { useRoles, type RoleDetail } from "./useRoles";

const LEVELS: { value: PermissionLevel; label: string }[] = [
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

function ensureRolePermission(role: RoleDetail, action: string) {
  const existing = role.permissions[action];
  if (existing) return existing;
  return { level: "none" as PermissionLevel, scope: { type: "all" as PermissionScopeType } };
}

function parseAccountIds(raw: string): number[] {
  return raw
    .split(/[,\s]+/g)
    .map((v) => v.trim())
    .filter(Boolean)
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n))
    .map((n) => Math.trunc(n));
}

export const RolesSettingsPage: React.FC = () => {
  const {
    roles,
    activeRole,
    setActiveRole,
    loadingRoles,
    loadingRole,
    savingRole,
    warnings,
    error,
    refreshRoles,
    loadRole,
    createRole,
    saveRole,
    deleteRole,
  } = useRoles();

  const [activeCategory, setActiveCategory] = useState<string>("Global");

  useEffect(() => {
    refreshRoles();
  }, [refreshRoles]);

  const categories = useMemo(() => PERMISSION_CATEGORIES as unknown as string[], []);
  const perms = useMemo(() => getPermissionsByCategory(activeCategory), [activeCategory]);

  const updateRole = (updater: (role: RoleDetail) => RoleDetail) => {
    if (!activeRole) return;
    setActiveRole(updater(activeRole));
  };

  const handleCreate = async () => {
    const label = prompt("Role name (e.g. “AP Specialist (Marketing)”)");
    if (!label) return;
    const cloneFromId = activeRole?.id;
    await createRole(label, cloneFromId);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="rounded-3xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Roles</h3>
            <p className="text-xs text-slate-500">Templates and custom roles per workspace.</p>
          </div>
          <button
            type="button"
            onClick={handleCreate}
            className="rounded-2xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
            disabled={savingRole}
          >
            New role
          </button>
        </div>
        <div className="max-h-[620px] overflow-y-auto p-2">
          {loadingRoles ? (
            <div className="px-3 py-4 text-sm text-slate-500">Loading roles…</div>
          ) : (
            <div className="space-y-1">
              {roles.map((role) => {
                const isActive = activeRole?.id === role.id;
                return (
                  <button
                    key={role.id}
                    type="button"
                    onClick={() => loadRole(role.id)}
                    className={[
                      "w-full text-left rounded-2xl px-3 py-2.5 transition border",
                      isActive
                        ? "bg-slate-900 text-white border-slate-900"
                        : "bg-white text-slate-800 border-transparent hover:bg-slate-50",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold truncate">{role.label}</div>
                        <div className={isActive ? "text-[11px] text-slate-300" : "text-[11px] text-slate-500"}>
                          {role.key}
                        </div>
                      </div>
                      <span
                        className={[
                          "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                          role.is_builtin
                            ? isActive
                              ? "border-white/20 text-white/90"
                              : "border-slate-200 bg-slate-50 text-slate-600"
                            : isActive
                              ? "border-white/20 text-white/90"
                              : "border-sky-200 bg-sky-50 text-sky-700",
                        ].join(" ")}
                      >
                        {role.is_builtin ? "Template" : "Custom"}
                      </span>
                    </div>
                  </button>
                );
              })}
              {!roles.length && <div className="px-3 py-4 text-sm text-slate-500">No roles found.</div>}
            </div>
          )}
        </div>
      </aside>

      <section className="rounded-3xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-slate-900">Role editor</h3>
              <p className="text-xs text-slate-500">
                Set permission levels and scopes. Changes affect new requests immediately.
              </p>
            </div>
            {activeRole && (
              <div className="flex items-center gap-2">
                {!activeRole.is_builtin && (
                  <button
                    type="button"
                    onClick={async () => {
                      if (!confirm("Delete this custom role?")) return;
                      await deleteRole(activeRole.id);
                    }}
                    className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    disabled={savingRole}
                  >
                    Delete
                  </button>
                )}
                <button
                  type="button"
                  onClick={async () => {
                    if (!activeRole) return;
                    const result = await saveRole(activeRole, false);
                    if (!result.ok && result.warnings?.length) return;
                  }}
                  className="rounded-2xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
                  disabled={!activeRole || savingRole}
                >
                  {savingRole ? "Saving…" : "Save"}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="p-6">
          {error && (
            <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}

          {warnings?.length ? (
            <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="font-semibold">Segregation of duties warnings</div>
                  <ul className="text-xs space-y-1">
                    {warnings.map((w) => (
                      <li key={w.id}>
                        <span className="font-semibold">{w.severity.toUpperCase()}</span> — {w.message}
                      </li>
                    ))}
                  </ul>
                </div>
                {activeRole && (
                  <button
                    type="button"
                    onClick={async () => {
                      await saveRole(activeRole, true);
                    }}
                    className="shrink-0 rounded-2xl bg-amber-700 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-60"
                    disabled={savingRole}
                  >
                    Save anyway
                  </button>
                )}
              </div>
            </div>
          ) : null}

          {!activeRole ? (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
              Select a role on the left to edit its permissions.
            </div>
          ) : loadingRole ? (
            <div className="text-sm text-slate-500">Loading role…</div>
          ) : (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-600">Role name</label>
                  <input
                    type="text"
                    value={activeRole.label}
                    onChange={(e) => updateRole((r) => ({ ...r, label: e.target.value }))}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-600">Key</label>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    {activeRole.key}{" "}
                    <span className="ml-2 text-[11px] text-slate-500">
                      {activeRole.is_builtin ? "Template" : "Custom"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-2">
                  {categories.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setActiveCategory(category)}
                      className={[
                        "w-full rounded-xl px-3 py-2 text-left text-sm font-medium transition",
                        activeCategory === category ? "bg-white shadow-sm text-slate-900" : "text-slate-600 hover:bg-white/60",
                      ].join(" ")}
                    >
                      {category}
                    </button>
                  ))}
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{activeCategory}</div>
                      <div className="text-xs text-slate-500">Choose a level and scope for each action.</div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    {perms.map((p) => {
                      const entry = ensureRolePermission(activeRole, p.action);
                      const scopeType = (entry.scope?.type || "all") as PermissionScopeType;
                      const selectedAccounts = scopeType === "selected_accounts" ? (entry.scope?.account_ids || []) : [];
                      return (
                        <div key={p.action} className="rounded-2xl border border-slate-200 bg-white p-4">
                          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <div className="text-sm font-semibold text-slate-900">{p.label}</div>
                                {p.sensitive ? (
                                  <span className="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                                    Sensitive
                                  </span>
                                ) : null}
                              </div>
                              <div className="mt-1 text-xs text-slate-500">{p.description}</div>
                              <div className="mt-2 text-[11px] text-slate-400">{p.action}</div>
                            </div>

                            <div className="grid gap-2 md:grid-cols-2 md:items-start">
                              <div className="space-y-1">
                                <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                  Level
                                </label>
                                <select
                                  value={entry.level}
                                  onChange={(e) =>
                                    updateRole((r) => ({
                                      ...r,
                                      permissions: {
                                        ...r.permissions,
                                        [p.action]: { ...ensureRolePermission(r, p.action), level: e.target.value as PermissionLevel },
                                      },
                                    }))
                                  }
                                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                >
                                  {LEVELS.map((l) => (
                                    <option key={l.value} value={l.value}>
                                      {l.label}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div className="space-y-1">
                                <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                  Scope
                                </label>
                                <select
                                  value={scopeType}
                                  onChange={(e) =>
                                    updateRole((r) => ({
                                      ...r,
                                      permissions: {
                                        ...r.permissions,
                                        [p.action]: {
                                          ...ensureRolePermission(r, p.action),
                                          scope: { type: e.target.value as PermissionScopeType },
                                        },
                                      },
                                    }))
                                  }
                                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                                >
                                  {SCOPES.map((s) => (
                                    <option key={s.value} value={s.value}>
                                      {s.label}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            </div>
                          </div>

                          {scopeType === "selected_accounts" ? (
                            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                Bank account IDs
                              </label>
                              <input
                                type="text"
                                value={selectedAccounts.join(", ")}
                                onChange={(e) =>
                                  updateRole((r) => ({
                                    ...r,
                                    permissions: {
                                      ...r.permissions,
                                      [p.action]: {
                                        ...ensureRolePermission(r, p.action),
                                        scope: { type: "selected_accounts", account_ids: parseAccountIds(e.target.value) },
                                      },
                                    },
                                  }))
                                }
                                placeholder="e.g. 12, 15, 19"
                                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                              />
                              <div className="mt-1 text-xs text-slate-500">
                                This is enforced server-side when context includes <code>bank_account_id</code>.
                              </div>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}

                    {!perms.length && (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                        No permissions defined for this category yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default RolesSettingsPage;

