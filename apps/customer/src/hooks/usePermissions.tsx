/**
 * RBAC v1: Permissions Hook
 * 
 * Provides role-based access control utilities for the frontend.
 * Reads role and permissions from the auth context (populated by /api/auth/me).
 */

import { useAuth, Workspace } from "../contexts/AuthContext";

// Available role constants (matching backend Role enum)
export const ROLES = {
    OWNER: "OWNER",
    SYSTEM_ADMIN: "SYSTEM_ADMIN",
    CONTROLLER: "CONTROLLER",
    CASH_MANAGER: "CASH_MANAGER",
    AP_SPECIALIST: "AP_SPECIALIST",
    AR_SPECIALIST: "AR_SPECIALIST",
    BOOKKEEPER: "BOOKKEEPER",
    VIEW_ONLY: "VIEW_ONLY",
    EXTERNAL_ACCOUNTANT: "EXTERNAL_ACCOUNTANT",
    AUDITOR: "AUDITOR",
} as const;

export type RoleValue = (typeof ROLES)[keyof typeof ROLES];

export interface PermissionResult {
    /** Current workspace info (null if not in a workspace) */
    workspace: Workspace | null;
    /** Current role string (e.g., "OWNER", "BOOKKEEPER") */
    role: string | null;
    /** Human-readable role label */
    roleLabel: string | null;
    /** Whether user is the workspace owner */
    isOwner: boolean;
    /** List of permission action strings the user has */
    permissions: string[];
    /** Check if user has permission for a specific action (optionally requiring a level) */
    can: (action: string, level?: "view" | "edit" | "approve") => boolean;
    /** Check if user has one of the given roles */
    hasRole: (...roles: string[]) => boolean;
    /** Whether user can view bank balances */
    canViewBankBalance: boolean;
    /** Whether user can manage team members */
    canManageTeam: boolean;
    /** Whether user can manage tax settings */
    canManageTax: boolean;
    /** Whether user can create invoices */
    canCreateInvoices: boolean;
    /** Whether user can create expenses */
    canCreateExpenses: boolean;
}

/**
 * Hook to access RBAC permissions in components.
 * 
 * Usage:
 * ```tsx
 * function MyComponent() {
 *   const { can, role, isOwner } = usePermissions();
 *   
 *   return (
 *     <div>
 *       <p>Your role: {role}</p>
 *       {can("invoices.create") && <button>Create Invoice</button>}
 *       {isOwner && <button>Manage Team</button>}
 *     </div>
 *   );
 * }
 * ```
 */
export function usePermissions(): PermissionResult {
    const { auth } = useAuth();
    const workspace = auth.user?.workspace ?? null;
    const role = workspace?.role ?? null;
    const roleLabel = workspace?.roleLabel ?? null;
    const isOwner = workspace?.isOwner ?? false;
    const permissions = workspace?.permissions ?? [];
    const permissionLevels = workspace?.permissionLevels ?? {};

    const LEVEL_ORDER: Record<string, number> = { none: 0, view: 1, edit: 2, approve: 3 };
    const ACTION_ALIASES: Record<string, string> = {
        "bank.view_balance": "bank.accounts.view_balance",
    };

    const can = (action: string, level: "view" | "edit" | "approve" = "view"): boolean => {
        const candidates = [action, ACTION_ALIASES[action], ...Object.entries(ACTION_ALIASES).filter(([, v]) => v === action).map(([k]) => k)].filter(
            Boolean,
        ) as string[];

        for (const candidate of candidates) {
            const actualLevel = permissionLevels[candidate];
            if (actualLevel && (LEVEL_ORDER[actualLevel] ?? 0) >= (LEVEL_ORDER[level] ?? 1)) {
                return true;
            }
        }

        if (!permissions.length) return false;
        return candidates.some((candidate) => permissions.includes(candidate));
    };

    const hasRole = (...roles: string[]): boolean => {
        if (!role) return false;
        return roles.includes(role);
    };

    // Convenience computed permissions
    const canViewBankBalance = can("bank.view_balance");
    const canManageTeam = can("users.manage_roles");
    const canManageTax = can("tax.settings.manage");
    const canCreateInvoices = can("invoices.create");
    const canCreateExpenses = can("expenses.create");

    return {
        workspace,
        role,
        roleLabel,
        isOwner,
        permissions,
        can,
        hasRole,
        canViewBankBalance,
        canManageTeam,
        canManageTax,
        canCreateInvoices,
        canCreateExpenses,
    };
}

/**
 * Component wrapper that only renders children if user has permission.
 * 
 * Usage:
 * ```tsx
 * <RequirePermission action="invoices.create">
 *   <CreateInvoiceButton />
 * </RequirePermission>
 * ```
 */
export function RequirePermission({
    action,
    fallback = null,
    children,
}: {
    action: string;
    fallback?: React.ReactNode;
    children: React.ReactNode;
}) {
    const { can } = usePermissions();
    return <>{can(action) ? children : fallback}</>;
}

/**
 * Component wrapper that only renders children if user has one of the roles.
 * 
 * Usage:
 * ```tsx
 * <RequireRole roles={["OWNER", "CONTROLLER"]}>
 *   <AdminDashboard />
 * </RequireRole>
 * ```
 */
export function RequireRole({
    roles,
    fallback = null,
    children,
}: {
    roles: string[];
    fallback?: React.ReactNode;
    children: React.ReactNode;
}) {
    const { hasRole } = usePermissions();
    return <>{hasRole(...roles) ? children : fallback}</>;
}
