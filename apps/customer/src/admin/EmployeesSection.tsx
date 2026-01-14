import React, { useCallback, useEffect, useMemo, useState } from "react";
import { backendUrl } from "../utils/apiClient";
import {
  deleteEmployee,
  fetchEmployees,
  inviteEmployee,
  reactivateEmployee,
  resendInvite,
  suspendEmployee,
  updateEmployee,
  type Employee,
  type InviteEmployeePayload,
  type Paginated,
} from "./api";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui";

type StaffPrimaryRole = "none" | "support" | "finance" | "engineering" | "superadmin";
type InviteRole = Exclude<StaffPrimaryRole, "none">;

const PAGE_SIZE = 50;

const toInitial = (name: string) => (name?.trim()?.[0] || "?").toUpperCase();

const formatRelative = (value: string | null | undefined) => {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const ms = Date.now() - d.getTime();
  const minutes = Math.round(ms / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
};

const daysUntil = (value: string | null | undefined) => {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  const ms = d.getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
};

const accessLabelForRole = (role: string) => {
  const normalized = (role || "none").toLowerCase();
  if (normalized === "superadmin") return "Superadmin";
  if (normalized === "engineering") return "Admin";
  if (normalized === "finance") return "Operations";
  if (normalized === "support") return "View only";
  return "No access";
};

const accessToneForRole = (role: string) => {
  const normalized = (role || "none").toLowerCase();
  if (normalized === "superadmin") return "bg-slate-900 text-white";
  if (normalized === "engineering") return "bg-slate-100 text-slate-900";
  if (normalized === "finance") return "bg-slate-100 text-slate-900";
  if (normalized === "support") return "bg-slate-100 text-slate-900";
  return "bg-slate-50 text-slate-600 border border-slate-200";
};

const statusChip = (employee: Employee) => {
  const invite = employee.invite || null;
  const inviteStatus = invite?.status || null;

  if (employee.is_active_employee && employee.admin_panel_access) {
    return { label: "Active", tone: "bg-emerald-50 text-emerald-700 border border-emerald-100" };
  }
  if (!employee.is_active_employee && inviteStatus === "pending") {
    return { label: "Pending invite", tone: "bg-slate-50 text-slate-700 border border-slate-200" };
  }
  if (!employee.is_active_employee && inviteStatus === "expired") {
    return { label: "Invite expired", tone: "bg-amber-50 text-amber-700 border border-amber-100" };
  }
  if (!employee.is_active_employee) {
    return { label: "Suspended", tone: "bg-rose-50 text-rose-700 border border-rose-100" };
  }
  return { label: "No admin access", tone: "bg-slate-50 text-slate-600 border border-slate-200" };
};

const inviteLink = (url: string) => (url.startsWith("http") ? url : backendUrl(url));

const NotAuthorized: React.FC = () => (
  <Card className="border-none bg-white/90 shadow-sm">
    <CardHeader>
      <CardTitle>Not authorized</CardTitle>
      <CardDescription>You don’t have permission to manage employee admin access.</CardDescription>
    </CardHeader>
  </Card>
);

export const EmployeesSection: React.FC<{
  canManageAdminUsers: boolean;
  canGrantSuperadmin: boolean;
}> = ({ canManageAdminUsers, canGrantSuperadmin }) => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<InviteRole>("support");
  const [inviteSaving, setInviteSaving] = useState(false);

  const [roleOpen, setRoleOpen] = useState(false);
  const [roleEmployee, setRoleEmployee] = useState<Employee | null>(null);
  const [nextRole, setNextRole] = useState<StaffPrimaryRole>("support");
  const [roleSaving, setRoleSaving] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState<null | { kind: "deactivate" | "reactivate" | "remove"; employee: Employee }>(null);
  const [confirmText, setConfirmText] = useState("");
  const [confirmSaving, setConfirmSaving] = useState(false);

  const loadEmployees = useCallback(async () => {
    if (!canManageAdminUsers) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined | null> = {
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
      };
      const data: Paginated<Employee> = await fetchEmployees(params);
      setEmployees(data.results || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load employees");
    } finally {
      setLoading(false);
    }
  }, [canManageAdminUsers, page, search]);

  useEffect(() => {
    loadEmployees();
  }, [loadEmployees]);

  const sortedEmployees = useMemo(() => {
    return [...employees].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  }, [employees]);

  const onInvite = async () => {
    setInviteSaving(true);
    setNotice(null);
    setError(null);
    try {
      const payload: InviteEmployeePayload = {
        email: inviteEmail.trim(),
        full_name: inviteName.trim() || undefined,
        role: inviteRole,
      };
      const created = await inviteEmployee(payload);
      setInviteOpen(false);
      setInviteName("");
      setInviteEmail("");
      setInviteRole("support");
      await loadEmployees();
      if (created.invite?.email_send_failed) {
        setNotice("Invite created but email failed. Copy the invite link and share it manually.");
      } else {
        setNotice("Invite sent.");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to send invite");
    } finally {
      setInviteSaving(false);
    }
  };

  const openChangeRole = (employee: Employee) => {
    setRoleEmployee(employee);
    const current = (employee.primary_admin_role || "support").toLowerCase() as StaffPrimaryRole;
    setNextRole(current || "support");
    setRoleOpen(true);
    setNotice(null);
    setError(null);
  };

  const onSaveRole = async () => {
    if (!roleEmployee) return;
    if (nextRole === "superadmin" && !canGrantSuperadmin) {
      setError("You can’t grant Superadmin.");
      return;
    }
    setRoleSaving(true);
    setNotice(null);
    setError(null);
    try {
      const patch: Record<string, unknown> = {
        primary_admin_role: nextRole,
      };
      if (roleEmployee.is_active_employee) {
        patch["admin_panel_access"] = nextRole !== "none";
      }
      await updateEmployee(roleEmployee.id, patch);
      setRoleOpen(false);
      setRoleEmployee(null);
      await loadEmployees();
      setNotice("Role updated.");
    } catch (err: any) {
      setError(err?.message || "Failed to update role");
    } finally {
      setRoleSaving(false);
    }
  };

  const onResendInvite = async (employee: Employee) => {
    setNotice(null);
    setError(null);
    try {
      const updated = await resendInvite(employee.id);
      setEmployees((prev) => prev.map((e) => (e.id === employee.id ? updated : e)));
      setNotice("Invite resent.");
    } catch (err: any) {
      setError(err?.message || "Failed to resend invite");
    }
  };

  const onCopyInvite = async (employee: Employee) => {
    const url = employee.invite?.invite_url;
    if (!url) return;
    setNotice(null);
    setError(null);
    try {
      await navigator.clipboard.writeText(inviteLink(url));
      setNotice("Invite link copied.");
    } catch {
      setError("Could not copy invite link.");
    }
  };

  const onConfirm = async () => {
    const state = confirmOpen;
    if (!state) return;
    const employee = state.employee;
    setConfirmSaving(true);
    setNotice(null);
    setError(null);
    try {
      if (state.kind === "deactivate") {
        const updated = await suspendEmployee(employee.id);
        setEmployees((prev) => prev.map((e) => (e.id === employee.id ? updated : e)));
        setNotice("Employee deactivated.");
      } else if (state.kind === "reactivate") {
        const updated = await reactivateEmployee(employee.id);
        setEmployees((prev) => prev.map((e) => (e.id === employee.id ? updated : e)));
        setNotice("Employee reactivated.");
      } else if (state.kind === "remove") {
        await deleteEmployee(employee.id);
        setEmployees((prev) => prev.filter((e) => e.id !== employee.id));
        setNotice("Employee removed.");
      }
      setConfirmOpen(null);
      setConfirmText("");
    } catch (err: any) {
      setError(err?.message || "Action failed");
    } finally {
      setConfirmSaving(false);
    }
  };

  if (!canManageAdminUsers) return <NotAuthorized />;

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Employees</h2>
          <p className="text-sm text-slate-600">Admin access and invites for internal staff.</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="rounded-full border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-slate-600">
            {employees.length} loaded
          </Badge>
          <Button className="rounded-full" onClick={() => setInviteOpen(true)}>
            Invite employee
          </Button>
        </div>
      </header>

      <div className="flex items-center gap-2">
        <div className="flex-1">
          <Input
            placeholder="Search name or email"
            className="h-10 rounded-full border-slate-200 bg-white"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Button variant="outline" className="rounded-full" onClick={loadEmployees} disabled={loading}>
          Search
        </Button>
      </div>

      {error && (
        <Card className="border-rose-200 bg-rose-50">
          <CardContent className="p-4 text-sm text-rose-700">{error}</CardContent>
        </Card>
      )}
      {notice && (
        <Card className="border-slate-200 bg-white">
          <CardContent className="p-4 text-sm text-slate-700">{notice}</CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {loading && (
          <Card className="border-none bg-white/90 shadow-sm">
            <CardContent className="p-6 text-sm text-slate-600">Loading…</CardContent>
          </Card>
        )}

        {!loading && sortedEmployees.length === 0 && (
          <Card className="border-none bg-white/90 shadow-sm">
            <CardHeader>
              <CardTitle>No employees</CardTitle>
              <CardDescription>Invite a teammate to get started.</CardDescription>
            </CardHeader>
          </Card>
        )}

        {!loading &&
          sortedEmployees.map((employee) => {
            const accessLabel = accessLabelForRole(employee.primary_admin_role);
            const accessTone = accessToneForRole(employee.primary_admin_role);
            const status = statusChip(employee);
            const invite = employee.invite || null;
            const expiresInDays = daysUntil(invite?.expires_at || null);
            const lastLogin = formatRelative(employee.last_login);

            const subline =
              invite?.status === "pending"
                ? `Invite sent · Expires in ${expiresInDays ?? "?"} days`
                : invite?.status === "expired"
                  ? "Invite expired"
                  : employee.is_active_employee && employee.admin_panel_access && lastLogin
                    ? `Active · Last login ${lastLogin}`
                    : employee.is_active_employee && employee.admin_panel_access
                      ? "Active"
                      : employee.is_active_employee
                        ? "Employee record exists"
                        : "Inactive";

            const showResend = !employee.is_active_employee && !!invite;
            const showReactivate = !employee.is_active_employee && !invite;
            const showDeactivate = employee.is_active_employee;

            return (
              <Card
                key={employee.id}
                className="rounded-2xl border border-slate-200/60 bg-white shadow-sm hover:shadow-md transition-shadow"
              >
                <CardContent className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-10 w-10 shrink-0 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center font-semibold">
                      {toInitial(employee.name)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-900">{employee.name}</p>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${status.tone}`}>
                          {status.label}
                        </span>
                      </div>
                      <p className="truncate text-xs text-slate-500">
                        {employee.email}
                        {employee.department ? ` · ${employee.department}` : ""}
                        {employee.title ? ` · ${employee.title}` : ""}
                      </p>
                      <p className="text-[11px] text-slate-500">{subline}</p>
                      {invite?.email_send_failed && (
                        <p className="text-[11px] text-amber-700 mt-1">
                          Invite created but email failed. Copy the link and share it manually.
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-2">
                    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${accessTone}`}>
                      {accessLabel}
                    </span>

                    <div className="flex items-center gap-1">
                      {showResend && (
                        <>
                          <Button variant="outline" size="sm" className="rounded-full" onClick={() => onResendInvite(employee)}>
                            Resend invite
                          </Button>
                          <Button variant="outline" size="sm" className="rounded-full" onClick={() => onCopyInvite(employee)} disabled={!invite?.invite_url}>
                            Copy link
                          </Button>
                        </>
                      )}

                      <Button variant="ghost" size="sm" className="rounded-full" onClick={() => openChangeRole(employee)}>
                        Change role
                      </Button>

                      {showDeactivate && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="rounded-full text-slate-600"
                          onClick={() => setConfirmOpen({ kind: "deactivate", employee })}
                        >
                          Deactivate
                        </Button>
                      )}

                      {showReactivate && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="rounded-full text-slate-600"
                          onClick={() => setConfirmOpen({ kind: "reactivate", employee })}
                        >
                          Reactivate
                        </Button>
                      )}

                      {canGrantSuperadmin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="rounded-full text-rose-600 hover:text-rose-700"
                          onClick={() => setConfirmOpen({ kind: "remove", employee })}
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
      </div>

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          className="rounded-full"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Prev
        </Button>
        <p className="text-xs text-slate-500">Page {page}</p>
        <Button variant="outline" className="rounded-full" onClick={() => setPage((p) => p + 1)}>
          Next
        </Button>
      </div>

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Invite employee</DialogTitle>
            <DialogDescription>Send an invite link to grant internal admin access.</DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Full name</label>
              <Input value={inviteName} onChange={(e) => setInviteName(e.target.value)} placeholder="Jane Doe" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Email</label>
              <Input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="jane@cloverbooks.com" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Role</label>
              <Select value={inviteRole} onValueChange={(v: any) => setInviteRole(v as InviteRole)}>
                <SelectTrigger className="h-10 border-slate-200 bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border-slate-200 bg-white">
                  <SelectItem value="support">View only</SelectItem>
                  <SelectItem value="finance">Operations</SelectItem>
                  <SelectItem value="engineering">Admin</SelectItem>
                  <SelectItem value="superadmin" disabled={!canGrantSuperadmin}>
                    Superadmin
                  </SelectItem>
                </SelectContent>
              </Select>
              {!canGrantSuperadmin && (
                <p className="text-[11px] text-slate-500">Superadmin invites require Primary Admin.</p>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" className="rounded-full" onClick={() => setInviteOpen(false)} disabled={inviteSaving}>
              Cancel
            </Button>
            <Button
              className="rounded-full"
              onClick={onInvite}
              disabled={inviteSaving || !inviteEmail.trim()}
            >
              {inviteSaving ? "Sending…" : "Send invite"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={roleOpen} onOpenChange={setRoleOpen}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Change role</DialogTitle>
            <DialogDescription>
              {roleEmployee ? `Update access for ${roleEmployee.email}.` : "Update access."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Select value={nextRole} onValueChange={(v: any) => setNextRole(v as StaffPrimaryRole)}>
              <SelectTrigger className="h-10 border-slate-200 bg-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="border-slate-200 bg-white">
                <SelectItem value="none">No access</SelectItem>
                <SelectItem value="support">View only</SelectItem>
                <SelectItem value="finance">Operations</SelectItem>
                <SelectItem value="engineering">Admin</SelectItem>
                <SelectItem value="superadmin" disabled={!canGrantSuperadmin}>
                  Superadmin
                </SelectItem>
              </SelectContent>
            </Select>

            {nextRole === "superadmin" && (
              <Card className="border-slate-200 bg-slate-50">
                <CardContent className="p-4 text-xs text-slate-700">
                  Superadmin grants powerful access. Only Primary Admin can assign this role.
                </CardContent>
              </Card>
            )}
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" className="rounded-full" onClick={() => setRoleOpen(false)} disabled={roleSaving}>
              Cancel
            </Button>
            <Button className="rounded-full" onClick={onSaveRole} disabled={roleSaving}>
              {roleSaving ? "Saving…" : "Save"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!confirmOpen} onOpenChange={(open) => !open && setConfirmOpen(null)}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>
              {confirmOpen?.kind === "remove"
                ? "Remove employee"
                : confirmOpen?.kind === "deactivate"
                  ? "Deactivate employee"
                  : "Reactivate employee"}
            </DialogTitle>
            <DialogDescription>
              {confirmOpen?.kind === "remove"
                ? "This is permanent. Type REMOVE to confirm."
                : confirmOpen?.kind === "deactivate"
                  ? "This removes access but preserves history. Type DEACTIVATE to confirm."
                  : "This restores access with the same role. Type REACTIVATE to confirm."}
            </DialogDescription>
          </DialogHeader>

          <Input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={confirmOpen?.kind === "remove" ? "REMOVE" : confirmOpen?.kind === "deactivate" ? "DEACTIVATE" : "REACTIVATE"}
            aria-label="Confirm action"
          />

          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              className="rounded-full"
              onClick={() => {
                setConfirmOpen(null);
                setConfirmText("");
              }}
              disabled={confirmSaving}
            >
              Cancel
            </Button>
            <Button
              variant={confirmOpen?.kind === "remove" ? "destructive" : "default"}
              className="rounded-full"
              onClick={onConfirm}
              disabled={
                confirmSaving ||
                (confirmOpen?.kind === "remove" && confirmText.trim().toUpperCase() !== "REMOVE") ||
                (confirmOpen?.kind === "deactivate" && confirmText.trim().toUpperCase() !== "DEACTIVATE") ||
                (confirmOpen?.kind === "reactivate" && confirmText.trim().toUpperCase() !== "REACTIVATE")
              }
            >
              {confirmSaving ? "Working…" : confirmOpen?.kind === "remove" ? "Remove" : confirmOpen?.kind === "deactivate" ? "Deactivate" : "Reactivate"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
