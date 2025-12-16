/**
 * Team Management Component
 * 
 * Allows workspace owners to invite, manage, and remove team members.
 * Uses the RBAC v1 membership API.
 */

import React, { useCallback, useEffect, useState } from "react";
import { getCsrfToken } from "../utils/csrf";

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

interface Member {
    id: number;
    user_id: number;
    email: string;
    username: string;
    full_name: string;
    role: string;
    role_label: string;
    role_description: string;
    role_color: string;
    department: string | null;
    region: string | null;
    is_active: boolean;
    is_effective: boolean;
    expires_at: string | null;
    created_at: string;
    created_by: string | null;
}

interface RoleOption {
    value: string;
    label: string;
    description: string;
    color: string;
}

// ---------------------------------------------------------------------------
// ROLE COLORS
// ---------------------------------------------------------------------------

const ROLE_COLORS: Record<string, string> = {
    purple: "bg-purple-50 text-purple-700 border-purple-200",
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    sky: "bg-sky-50 text-sky-700 border-sky-200",
    slate: "bg-slate-50 text-slate-600 border-slate-200",
    indigo: "bg-indigo-50 text-indigo-700 border-indigo-200",
    rose: "bg-rose-50 text-rose-700 border-rose-200",
    gray: "bg-gray-50 text-gray-600 border-gray-200",
};

function getRoleClasses(color: string): string {
    return ROLE_COLORS[color] || ROLE_COLORS.gray;
}

// ---------------------------------------------------------------------------
// MAIN COMPONENT
// ---------------------------------------------------------------------------

export const TeamManagement: React.FC = () => {
    const [members, setMembers] = useState<Member[]>([]);
    const [roles, setRoles] = useState<RoleOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    // Invite form state
    const [showInviteForm, setShowInviteForm] = useState(false);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("BOOKKEEPER");
    const [inviteDepartment, setInviteDepartment] = useState("");

    // Edit modal state
    const [editingMember, setEditingMember] = useState<Member | null>(null);
    const [editRole, setEditRole] = useState("");

    // Fetch members
    const fetchMembers = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("/api/workspace/memberships/", {
                credentials: "same-origin",
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || "Failed to load team members");
            }
            const data = await res.json();
            setMembers(data.memberships || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load team members");
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch available roles
    const fetchRoles = useCallback(async () => {
        try {
            const res = await fetch("/api/workspace/roles/", {
                credentials: "same-origin",
            });
            if (res.ok) {
                const data = await res.json();
                setRoles(data.roles || []);
            }
        } catch {
            // Roles are optional, use defaults
        }
    }, []);

    useEffect(() => {
        fetchMembers();
        fetchRoles();
    }, [fetchMembers, fetchRoles]);

    // Invite new member
    const handleInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inviteEmail.trim()) {
            setError("Email is required");
            return;
        }

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            const csrfToken = getCsrfToken();
            const res = await fetch("/api/workspace/memberships/create/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    email: inviteEmail.trim().toLowerCase(),
                    role: inviteRole,
                    department: inviteDepartment.trim(),
                }),
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || data.errors?.email || "Failed to invite member");
            }

            setMembers((prev) => [data.membership, ...prev]);
            setInviteEmail("");
            setInviteDepartment("");
            setShowInviteForm(false);
            setSuccess(`Invited ${data.membership.email} as ${data.membership.role_label}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to invite member");
        } finally {
            setSaving(false);
        }
    };

    // Update member role
    const handleUpdateRole = async () => {
        if (!editingMember) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            const csrfToken = getCsrfToken();
            const res = await fetch(`/api/workspace/memberships/${editingMember.id}/`, {
                method: "PATCH",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ role: editRole }),
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || "Failed to update role");
            }

            setMembers((prev) =>
                prev.map((m) => (m.id === editingMember.id ? data.membership : m))
            );
            setEditingMember(null);
            setSuccess(`Updated ${data.membership.email} to ${data.membership.role_label}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update role");
        } finally {
            setSaving(false);
        }
    };

    // Remove member
    const handleRemove = async (member: Member) => {
        if (!confirm(`Remove ${member.email} from the workspace?`)) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            const csrfToken = getCsrfToken();
            const res = await fetch(`/api/workspace/memberships/${member.id}/`, {
                method: "DELETE",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrfToken,
                },
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || "Failed to remove member");
            }

            setMembers((prev) => prev.filter((m) => m.id !== member.id));
            setSuccess(`Removed ${member.email} from workspace`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to remove member");
        } finally {
            setSaving(false);
        }
    };

    // Toggle active status
    const handleToggleActive = async (member: Member) => {
        setSaving(true);
        setError(null);

        try {
            const csrfToken = getCsrfToken();
            const res = await fetch(`/api/workspace/memberships/${member.id}/`, {
                method: "PATCH",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ is_active: !member.is_active }),
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || "Failed to update member");
            }

            setMembers((prev) =>
                prev.map((m) => (m.id === member.id ? data.membership : m))
            );
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update member");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Alerts */}
            {error && (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
                    {error}
                </div>
            )}
            {success && (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
                    {success}
                </div>
            )}

            {/* Header with Invite Button */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-slate-900">Team Members</h3>
                    <p className="text-sm text-slate-500">
                        Manage who has access to your workspace and their roles.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={() => setShowInviteForm(!showInviteForm)}
                    className="inline-flex items-center rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
                >
                    {showInviteForm ? "Cancel" : "Invite team member"}
                </button>
            </div>

            {/* Invite Form */}
            {showInviteForm && (
                <form
                    onSubmit={handleInvite}
                    className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-4"
                >
                    <div className="grid gap-4 sm:grid-cols-3">
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-600">Email address</label>
                            <input
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="colleague@company.com"
                                required
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-600">Role</label>
                            <select
                                value={inviteRole}
                                onChange={(e) => setInviteRole(e.target.value)}
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                            >
                                {roles.length > 0 ? (
                                    roles.map((role) => (
                                        <option key={role.value} value={role.value}>
                                            {role.label}
                                        </option>
                                    ))
                                ) : (
                                    <>
                                        <option value="BOOKKEEPER">Bookkeeper</option>
                                        <option value="CONTROLLER">Controller</option>
                                        <option value="CASH_MANAGER">Cash Manager</option>
                                        <option value="AP_SPECIALIST">AP Specialist</option>
                                        <option value="AR_SPECIALIST">AR Specialist</option>
                                        <option value="VIEW_ONLY">View Only</option>
                                        <option value="EXTERNAL_ACCOUNTANT">External Accountant</option>
                                        <option value="AUDITOR">Auditor</option>
                                    </>
                                )}
                            </select>
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-600">Department (optional)</label>
                            <input
                                type="text"
                                value={inviteDepartment}
                                onChange={(e) => setInviteDepartment(e.target.value)}
                                placeholder="e.g., Marketing"
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                            />
                        </div>
                    </div>
                    <div className="flex justify-end">
                        <button
                            type="submit"
                            disabled={saving}
                            className="inline-flex items-center rounded-2xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-emerald-300"
                        >
                            {saving ? "Sending invite…" : "Send invite"}
                        </button>
                    </div>
                </form>
            )}

            {/* Members List */}
            {loading ? (
                <div className="text-center py-8 text-slate-500">Loading team members…</div>
            ) : members.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                    No team members yet. Invite someone to get started.
                </div>
            ) : (
                <div className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white">
                    {members.map((member) => (
                        <div
                            key={member.id}
                            className={`flex flex-wrap items-center justify-between gap-4 px-4 py-4 ${!member.is_effective ? "opacity-60" : ""
                                }`}
                        >
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-sm font-semibold text-slate-600">
                                    {member.full_name?.[0]?.toUpperCase() || member.email[0].toUpperCase()}
                                </div>
                                <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                        <p className="text-sm font-semibold text-slate-900 truncate">
                                            {member.full_name || member.email}
                                        </p>
                                        <span
                                            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${getRoleClasses(
                                                member.role_color
                                            )}`}
                                        >
                                            {member.role_label}
                                        </span>
                                        {!member.is_active && (
                                            <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
                                                Inactive
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-slate-500 truncate">
                                        {member.email}
                                        {member.department && ` · ${member.department}`}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                {member.role !== "OWNER" && (
                                    <>
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setEditingMember(member);
                                                setEditRole(member.role);
                                            }}
                                            className="rounded-full border border-slate-200 px-3 py-1 font-semibold text-slate-700 hover:bg-slate-50"
                                        >
                                            Change role
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => handleToggleActive(member)}
                                            disabled={saving}
                                            className="rounded-full border border-slate-200 px-3 py-1 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                                        >
                                            {member.is_active ? "Deactivate" : "Activate"}
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => handleRemove(member)}
                                            disabled={saving}
                                            className="rounded-full border border-rose-200 px-3 py-1 font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                                        >
                                            Remove
                                        </button>
                                    </>
                                )}
                                {member.role === "OWNER" && (
                                    <span className="text-slate-400">Workspace owner</span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Edit Role Modal */}
            {editingMember && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
                    <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
                        <h3 className="text-lg font-semibold text-slate-900">
                            Change role for {editingMember.full_name || editingMember.email}
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                            Select a new role for this team member.
                        </p>
                        <div className="mt-4 space-y-3">
                            {(roles.length > 0 ? roles : [
                                { value: "BOOKKEEPER", label: "Bookkeeper", description: "Broad operational access", color: "sky" },
                                { value: "CONTROLLER", label: "Controller", description: "Full accounting access", color: "blue" },
                                { value: "CASH_MANAGER", label: "Cash Manager", description: "Banking and reconciliation", color: "emerald" },
                                { value: "AP_SPECIALIST", label: "AP Specialist", description: "Bills and suppliers", color: "amber" },
                                { value: "AR_SPECIALIST", label: "AR Specialist", description: "Invoices and customers", color: "amber" },
                                { value: "VIEW_ONLY", label: "View Only", description: "Read-only access", color: "slate" },
                            ]).map((role) => (
                                <label
                                    key={role.value}
                                    className={`flex items-center gap-3 rounded-xl border p-3 cursor-pointer transition ${editRole === role.value
                                            ? "border-slate-900 bg-slate-50"
                                            : "border-slate-200 hover:border-slate-300"
                                        }`}
                                >
                                    <input
                                        type="radio"
                                        name="role"
                                        value={role.value}
                                        checked={editRole === role.value}
                                        onChange={(e) => setEditRole(e.target.value)}
                                        className="h-4 w-4 border-slate-300 text-slate-900 focus:ring-slate-900"
                                    />
                                    <div>
                                        <p className="text-sm font-semibold text-slate-900">{role.label}</p>
                                        <p className="text-xs text-slate-500">{role.description}</p>
                                    </div>
                                </label>
                            ))}
                        </div>
                        <div className="mt-6 flex justify-end gap-3">
                            <button
                                type="button"
                                onClick={() => setEditingMember(null)}
                                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleUpdateRole}
                                disabled={saving}
                                className="rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-slate-400"
                            >
                                {saving ? "Saving…" : "Save changes"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Role Descriptions */}
            <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
                    Role Permissions
                </h4>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 text-xs">
                    <div>
                        <span className="font-semibold text-slate-700">Controller:</span>{" "}
                        <span className="text-slate-500">Full GL, tax, reporting</span>
                    </div>
                    <div>
                        <span className="font-semibold text-slate-700">Cash Manager:</span>{" "}
                        <span className="text-slate-500">Banking, bank balances</span>
                    </div>
                    <div>
                        <span className="font-semibold text-slate-700">Bookkeeper:</span>{" "}
                        <span className="text-slate-500">Invoices, bills, reconcile</span>
                    </div>
                    <div>
                        <span className="font-semibold text-slate-700">AP Specialist:</span>{" "}
                        <span className="text-slate-500">Bills only, no bank balances</span>
                    </div>
                    <div>
                        <span className="font-semibold text-slate-700">AR Specialist:</span>{" "}
                        <span className="text-slate-500">Invoices only</span>
                    </div>
                    <div>
                        <span className="font-semibold text-slate-700">View Only:</span>{" "}
                        <span className="text-slate-500">Read-only access</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TeamManagement;
