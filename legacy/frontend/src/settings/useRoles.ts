import { useCallback, useMemo, useState } from "react";
import { getCsrfToken } from "../utils/csrf";
import type { PermissionLevel, PermissionScope } from "../permissions/permissionsRegistry";

export interface RoleSummary {
  id: number;
  key: string;
  label: string;
  is_builtin: boolean;
  updated_at?: string | null;
}

export interface SoDWarning {
  id: string;
  severity: "low" | "medium" | "high";
  message: string;
  actions: string[];
}

export type RolePermissionEntry = {
  level: PermissionLevel;
  scope?: PermissionScope;
};

export interface RoleDetail {
  id: number;
  key: string;
  label: string;
  is_builtin: boolean;
  permissions: Record<string, RolePermissionEntry>;
}

export function useRoles() {
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [activeRole, setActiveRole] = useState<RoleDetail | null>(null);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [loadingRole, setLoadingRole] = useState(false);
  const [savingRole, setSavingRole] = useState(false);
  const [warnings, setWarnings] = useState<SoDWarning[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshRoles = useCallback(async () => {
    setLoadingRoles(true);
    setError(null);
    try {
      const res = await fetch("/api/settings/roles/", { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Unable to load roles.");
      setRoles(data.roles || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load roles.");
    } finally {
      setLoadingRoles(false);
    }
  }, []);

  const loadRole = useCallback(async (roleId: number) => {
    setLoadingRole(true);
    setError(null);
    setWarnings([]);
    try {
      const res = await fetch(`/api/settings/roles/${roleId}/`, { credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Unable to load role.");
      setActiveRole(data.role as RoleDetail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load role.");
    } finally {
      setLoadingRole(false);
    }
  }, []);

  const createRole = useCallback(async (label: string, cloneFromId?: number) => {
    setSavingRole(true);
    setError(null);
    try {
      const csrfToken = getCsrfToken();
      const res = await fetch("/api/settings/roles/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ label, clone_from_id: cloneFromId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Unable to create role.");
      await refreshRoles();
      const role = data.role as RoleSummary;
      if (role?.id) await loadRole(role.id);
      return role;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create role.");
      return null;
    } finally {
      setSavingRole(false);
    }
  }, [loadRole, refreshRoles]);

  const saveRole = useCallback(
    async (role: RoleDetail, ignoreWarnings = false) => {
      setSavingRole(true);
      setError(null);
      try {
        const csrfToken = getCsrfToken();
        const res = await fetch(`/api/settings/roles/${role.id}/`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            label: role.label,
            permissions: role.permissions,
            ignore_warnings: ignoreWarnings,
          }),
        });
        const data = await res.json();
        if (res.status === 409) {
          setWarnings((data?.warnings || []) as SoDWarning[]);
          return { ok: false, warnings: (data?.warnings || []) as SoDWarning[] };
        }
        if (!res.ok) throw new Error(data?.error || "Unable to save role.");
        setWarnings((data?.warnings || []) as SoDWarning[]);
        setActiveRole(data.role as RoleDetail);
        await refreshRoles();
        return { ok: true, warnings: (data?.warnings || []) as SoDWarning[] };
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to save role.");
        return { ok: false, warnings: [] as SoDWarning[] };
      } finally {
        setSavingRole(false);
      }
    },
    [refreshRoles],
  );

  const deleteRole = useCallback(
    async (roleId: number) => {
      setSavingRole(true);
      setError(null);
      try {
        const csrfToken = getCsrfToken();
        const res = await fetch(`/api/settings/roles/${roleId}/`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrfToken },
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || "Unable to delete role.");
        if (activeRole?.id === roleId) setActiveRole(null);
        await refreshRoles();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to delete role.");
        return false;
      } finally {
        setSavingRole(false);
      }
    },
    [activeRole?.id, refreshRoles],
  );

  const roleKeyById = useMemo(() => new Map(roles.map((r) => [r.id, r.key])), [roles]);

  return {
    roles,
    activeRole,
    setActiveRole,
    roleKeyById,
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
  };
}

