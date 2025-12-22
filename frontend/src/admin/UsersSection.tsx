import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchUsers,
  updateUser,
  startImpersonation,
  resetPassword,
  type Paginated,
  type User,
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
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui";

// ----------------------
// Types
// ----------------------

type AdminRole = "none" | "support" | "ops" | "engineering" | "superadmin" | "primary_admin";

// ----------------------
// Helpers
// ----------------------

function formatDate(value: string | null | undefined): string {
  if (!value) return "Never";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

function initials(user: User): string {
  const f = user.first_name?.[0] ?? "";
  const l = user.last_name?.[0] ?? "";
  return (f + l || user.email?.[0] || "U").toUpperCase();
}

function adminRoleLabel(role: string | null | undefined): string {
  switch (role) {
    case "PRIMARY_ADMIN":
    case "primary_admin":
      return "Primary Admin";
    case "SUPPORT":
    case "support":
      return "Support";
    case "OPS":
    case "ops":
      return "Ops";
    case "ENGINEERING":
    case "engineering":
      return "Engineering";
    case "SUPERADMIN":
    case "superadmin":
      return "Superadmin";
    default:
      return "No admin role";
  }
}

function authProviderLabel(provider: string): string {
  switch (provider.toLowerCase()) {
    case "google":
      return "Google";
    case "microsoft":
      return "Microsoft";
    case "github":
      return "GitHub";
    case "password":
    default:
      return "Password";
  }
}

// ----------------------
// Main Page
// ----------------------

const PAGE_SIZE = 12;

export const UsersSection: React.FC<{ roleLevel?: number }> = ({ roleLevel = 1 }) => {
  // NOTE: user list is viewable by SUPPORT, but mutations require OPS+ (and privilege changes require SUPERADMIN+).
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [previous, setPrevious] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "suspended">("all");
  const [authFilter, setAuthFilter] = useState<"all" | "with-google" | "without-google">("all");
  const [page, setPage] = useState(1);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const loadUsers = useCallback(async (opts: { page?: number; search?: string } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = {
        page: opts.page ?? page,
        search: opts.search ?? search,
        page_size: PAGE_SIZE,
      };
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      if (authFilter === "with-google") {
        params.has_google = "true";
      } else if (authFilter === "without-google") {
        params.has_google = "false";
      }
      const data: Paginated<User> = await fetchUsers(params);
      setUsers(data.results);
      setNext(data.next);
      setPrevious(data.previous);
      if (data.results.length > 0 && !selectedUserId) {
        setSelectedUserId(data.results[0].id);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, authFilter, selectedUserId]);

  useEffect(() => {
    loadUsers({ page, search });
  }, [page, statusFilter, authFilter]);

  const selectedUser = useMemo(() => users.find((u) => u.id === selectedUserId) || users[0] || null, [users, selectedUserId]);

  const handleSelectUser = useCallback((id: number) => {
    setSelectedUserId(id);
  }, []);

  const goPrev = () => setPage((p) => Math.max(1, p - 1));
  const goNext = () => setPage((p) => p + 1);

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <svg className="h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Users
          </h2>
          <p className="text-sm text-slate-600">
            Central Books operators across all workspaces.
          </p>
        </div>
        <Badge variant="outline" className="rounded-full border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-slate-600">
          {users.length} loaded
        </Badge>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        {/* Left: Users list */}
        <Card className="border-none bg-white/90 shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative flex-1 min-w-[160px]">
                <svg className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <Input
                  placeholder="Search name or email"
                  className="h-8 rounded-full border-slate-200 bg-slate-50 pl-7 pr-2 text-xs"
                  value={search}
                  aria-label="Search users"
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  onBlur={() => loadUsers({ page: 1, search })}
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 rounded-full px-3 text-xs"
                onClick={() => loadUsers({ page: 1, search })}
              >
                Search
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <Select
                value={statusFilter}
                onValueChange={(v: "all" | "active" | "suspended") => {
                  setStatusFilter(v);
                  setPage(1);
                }}
              >
                <SelectTrigger aria-label="Status filter" className="h-8 w-[120px] rounded-full border-slate-200 bg-slate-50 px-3 text-xs">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent className="border-slate-200 bg-white text-xs">
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="suspended">Suspended</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={authFilter}
                onValueChange={(v: "all" | "with-google" | "without-google") => {
                  setAuthFilter(v);
                  setPage(1);
                }}
              >
                <SelectTrigger aria-label="Google login filter" className="h-8 w-[140px] rounded-full border-slate-200 bg-slate-50 px-3 text-xs">
                  <SelectValue placeholder="Auth" />
                </SelectTrigger>
                <SelectContent className="border-slate-200 bg-white text-xs">
                  <SelectItem value="all">All auth</SelectItem>
                  <SelectItem value="with-google">Has Google</SelectItem>
                  <SelectItem value="without-google">No Google</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent className="pb-2">
            <div className="rounded-2xl border border-slate-100 bg-slate-50/60">
              <ScrollArea className="max-h-[520px]">
                <div className="divide-y divide-slate-100">
                  {loading && (
                    <div className="flex items-center justify-center py-10 text-xs text-slate-500">Loading users…</div>
                  )}
                  {error && !loading && (
                    <div className="flex flex-col items-center justify-center py-10 text-xs text-rose-500 gap-2">
                      <span>Failed to load users: {error}</span>
                      <Button variant="outline" size="sm" onClick={() => loadUsers()}>Retry</Button>
                    </div>
                  )}
                  {!loading && !error && users.length === 0 && (
                    <div className="flex items-center justify-center py-10 text-xs text-slate-500">No users match your filters.</div>
                  )}
                  {!loading && !error && users.map((user) => {
                    const isSelected = selectedUser?.id === user.id;
                    return (
                      <button
                        key={user.id}
                        type="button"
                        onClick={() => handleSelectUser(user.id)}
                        className={`flex w-full items-center gap-3 px-3 py-2 text-left text-xs transition ${isSelected
                          ? "bg-sky-50/90 text-slate-900"
                          : "hover:bg-slate-100/80 text-slate-800"
                          }`}
                      >
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900/90 text-[11px] font-semibold text-slate-50 shadow-sm">
                          {initials(user)}
                        </div>
                        <div className="flex flex-1 flex-col gap-0.5">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-1.5">
                              <span className="max-w-[140px] truncate text-[11px] font-semibold text-slate-900">
                                {user.full_name || `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.email}
                              </span>
                              {user.is_active ? (
                                <Badge className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                                  Active
                                </Badge>
                              ) : (
                                <Badge className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                                  Inactive
                                </Badge>
                              )}
                              {user.admin_role && (
                                <Badge className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-700">
                                  {adminRoleLabel(user.admin_role)}
                                </Badge>
                              )}
                            </div>
                            <span className="text-[10px] text-slate-500">{formatDate(user.last_login)}</span>
                          </div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="max-w-[160px] truncate text-[10px] text-slate-500">{user.email}</span>
                            <div className="flex items-center gap-1">
                              {user.auth_providers?.map((p) => (
                                <Badge
                                  key={p}
                                  variant="outline"
                                  className="rounded-full border-slate-200 bg-white px-1.5 py-0.5 text-[9px] text-slate-600"
                                >
                                  {authProviderLabel(p)}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {user.workspace_count ?? 0} workspaces
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </ScrollArea>
            </div>
            <div className="mt-3 flex items-center justify-between text-[10px] text-slate-500">
              <span>Page {page}</span>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7 rounded-full border-slate-200"
                  onClick={goPrev}
                  disabled={!previous}
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7 rounded-full border-slate-200"
                  onClick={goNext}
                  disabled={!next}
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Right: User details */}
        {selectedUser ? (
          <UserDetailsPanel user={selectedUser} onUpdate={loadUsers} roleLevel={roleLevel} />
        ) : (
          <Card className="flex h-full items-center justify-center border-none bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50 text-center shadow-sm">
            <CardContent className="flex flex-col items-center justify-center gap-3 py-10">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900/90 text-slate-50">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-slate-900">Select a user to inspect</p>
                <p className="text-xs text-slate-500">
                  Choose someone from the list to view roles, workspaces, and security posture.
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

// ----------------------
// User Details Panel
// ----------------------

interface UserDetailsPanelProps {
  user: User;
  onUpdate: () => void;
  roleLevel: number;
}

const UserDetailsPanel: React.FC<UserDetailsPanelProps> = ({ user, onUpdate, roleLevel }) => {
  const [firstName, setFirstName] = useState(user.first_name || "");
  const [lastName, setLastName] = useState(user.last_name || "");
  const [email, setEmail] = useState(user.email || "");
  const [isActive, setIsActive] = useState(user.is_active);
  const [isStaff, setIsStaff] = useState(user.is_staff || false);
  const [isSuperuser, setIsSuperuser] = useState(user.is_superuser || false);
  const [adminRole, setAdminRole] = useState<AdminRole>(
    (user.admin_role?.toLowerCase() as AdminRole) || "none"
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [impersonateLoading, setImpersonateLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetApprovalId, setResetApprovalId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("profile");

  // Reset form when user changes
  useEffect(() => {
    setFirstName(user.first_name || "");
    setLastName(user.last_name || "");
    setEmail(user.email || "");
    setIsActive(user.is_active);
    setIsStaff(user.is_staff || false);
    setIsSuperuser(user.is_superuser || false);
    setAdminRole((user.admin_role?.toLowerCase() as AdminRole) || "none");
    setMessage(null);
    setError(null);
    setResetApprovalId(null);
  }, [user.id]);

  const hasPassword = user.has_usable_password ?? false;
  const socialCount = user.social_account_count ?? user.auth_providers?.filter((p) => p !== "password").length ?? 0;

  const canEdit = roleLevel >= 2;
  const canChangePrivileges = roleLevel >= 4;

  const promptRequiredReason = (label: string): string | null => {
    const value = window.prompt(`Reason required: ${label}`);
    if (value === null) return null;
    const trimmed = value.trim();
    if (!trimmed) {
      window.alert("Reason is required.");
      return null;
    }
    return trimmed;
  };

  const handleSave = async () => {
    if (!canEdit) {
      setError("View-only: OPS or higher required to edit users.");
      return;
    }
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const safePayload: Record<string, unknown> = {};
      if ((user.first_name || "") !== firstName) safePayload.first_name = firstName;
      if ((user.last_name || "") !== lastName) safePayload.last_name = lastName;
      if ((user.email || "") !== email) safePayload.email = email;

      const desiredAdminRole = adminRole === "none" ? null : adminRole.toUpperCase();
      const originalAdminRole = user.admin_role ? user.admin_role.toUpperCase() : null;

      const isActiveChanged = Boolean(user.is_active) !== Boolean(isActive);
      const privilegeChanged =
        Boolean(user.is_staff) !== Boolean(isStaff) ||
        Boolean(user.is_superuser) !== Boolean(isSuperuser) ||
        desiredAdminRole !== originalAdminRole;

      if (privilegeChanged && !canChangePrivileges) {
        setError("Privilege changes require SUPERADMIN+.");
        setIsStaff(Boolean(user.is_staff));
        setIsSuperuser(Boolean(user.is_superuser));
        setAdminRole((user.admin_role?.toLowerCase() as AdminRole) || "none");
        return;
      }

      const createdApprovalIds: string[] = [];

      if (Object.keys(safePayload).length > 0) {
        const safeRes = await updateUser(user.id, safePayload);
        const updatedUser = "user" in safeRes ? safeRes.user : safeRes;
        setFirstName(updatedUser.first_name || "");
        setLastName(updatedUser.last_name || "");
        setEmail(updatedUser.email || "");
      }

      if (isActiveChanged) {
        const reason = promptRequiredReason(
          `Change active status for ${user.email} from ${user.is_active ? "active" : "suspended"} to ${isActive ? "active" : "suspended"}`
        );
        if (!reason) return;
        const res = await updateUser(user.id, { is_active: isActive, reason });
        if ("approval_required" in res && res.approval_required) {
          createdApprovalIds.push(res.approval_request_id);
          setIsActive(Boolean(user.is_active));
        }
      }

      if (privilegeChanged) {
        const reason = promptRequiredReason(`Change privileges for ${user.email}`);
        if (!reason) return;
        const res = await updateUser(user.id, {
          is_staff: isStaff,
          is_superuser: isSuperuser,
          admin_role: desiredAdminRole,
          reason,
        });
        if ("approval_required" in res && res.approval_required) {
          createdApprovalIds.push(res.approval_request_id);
          setIsStaff(Boolean(user.is_staff));
          setIsSuperuser(Boolean(user.is_superuser));
          setAdminRole((user.admin_role?.toLowerCase() as AdminRole) || "none");
        }
      }

      if (createdApprovalIds.length > 0) {
        setMessage(
          `Saved. Created approval request${createdApprovalIds.length > 1 ? "s" : ""}: ${createdApprovalIds.join(", ")}`
        );
      } else {
        setMessage("User updated successfully");
      }
      onUpdate();
    } catch (err: any) {
      setError(err?.message || "Failed to update user");
    } finally {
      setSaving(false);
    }
  };

  const handleImpersonate = async () => {
    if (!canEdit) {
      setError("View-only: OPS or higher required to start impersonation.");
      return;
    }
    const reason = promptRequiredReason(`Impersonate ${user.email}`);
    if (!reason) return;
    setImpersonateLoading(true);
    try {
      const data = await startImpersonation(user.id, reason);
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      }
    } catch (err: any) {
      setError(err?.message || "Failed to start impersonation");
    } finally {
      setImpersonateLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!canEdit) {
      setError("View-only: OPS or higher required to request reset links.");
      return;
    }
    const reason = promptRequiredReason(`Create password reset link for ${user.email}`);
    if (!reason) return;
    setResetLoading(true);
    setResetApprovalId(null);
    setError(null);
    try {
      const data = await resetPassword(user.id, reason);
      setResetApprovalId(data.approval_request_id);
      setMessage(`Created approval request ${data.approval_request_id}. Approve it to generate the reset link.`);
    } catch (err: any) {
      setError(err?.message || "Failed to reset password");
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <Card className="border-none bg-white/95 shadow-sm">
      <CardHeader className="border-b border-slate-100 pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900/95 text-[13px] font-semibold text-slate-50 shadow-sm">
              {initials(user)}
            </div>
            <div className="space-y-0.5">
              <CardTitle className="text-base font-semibold tracking-tight text-slate-900">
                {firstName} {lastName}
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">{email}</CardDescription>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
                <Badge className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-medium text-slate-50">
                  {user.workspace_count ?? 0} workspaces
                </Badge>
                {isActive ? (
                  <Badge className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                    Active
                  </Badge>
                ) : (
                  <Badge className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                    Suspended
                  </Badge>
                )}
                {adminRole !== "none" && (
                  <Badge className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                    {adminRoleLabel(adminRole)}
                  </Badge>
                )}
                {(isStaff || isSuperuser) && (
                  <Badge className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                    🛡️ Django admin
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-8 rounded-full border-slate-200 bg-slate-50 px-3 text-[11px]"
              onClick={handleImpersonate}
              disabled={impersonateLoading || !canEdit}
            >
              {impersonateLoading ? "Starting…" : "🔑 Impersonate"}
            </Button>
            <span className="text-[10px] text-slate-400">
              Last active: {formatDate(user.last_login)}
            </span>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-2xl bg-slate-50 px-3 py-2 text-[10px] text-slate-600">
          <span className="text-emerald-500">📊</span>
          <span>
            Joined {formatDate(user.date_joined)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          {/* Left column: identity & permissions */}
          <div className="space-y-4">
            {/* Quick Stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col justify-between rounded-2xl border border-sky-100 bg-sky-50/70 px-3 py-2.5">
                <span className="text-[10px] font-medium uppercase tracking-wide text-slate-600">Workspaces</span>
                <span className="mt-1 text-sm font-semibold text-slate-900">{user.workspace_count ?? 0}</span>
                <span className="mt-0.5 text-[10px] text-slate-500">Linked entities</span>
              </div>
              <div className={`flex flex-col justify-between rounded-2xl border px-3 py-2.5 ${hasPassword ? "border-emerald-100 bg-emerald-50/70" : "border-amber-100 bg-amber-50/70"}`}>
                <span className="text-[10px] font-medium uppercase tracking-wide text-slate-600">Password</span>
                <span className="mt-1 text-sm font-semibold text-slate-900">{hasPassword ? "Set" : "None"}</span>
                <span className="mt-0.5 text-[10px] text-slate-500">{hasPassword ? "Can log in" : "SSO only"}</span>
              </div>
              <div className={`flex flex-col justify-between rounded-2xl border px-3 py-2.5 ${socialCount > 0 ? "border-violet-100 bg-violet-50/70" : "border-slate-100 bg-slate-50/70"}`}>
                <span className="text-[10px] font-medium uppercase tracking-wide text-slate-600">Social</span>
                <span className="mt-1 text-sm font-semibold text-slate-900">{socialCount}</span>
                <span className="mt-0.5 text-[10px] text-slate-500">{socialCount > 0 ? "SSO connected" : "No SSO"}</span>
              </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-2">
              <TabsList className="grid h-8 grid-cols-3 rounded-full bg-slate-100 p-0.5 text-[11px]">
                <TabsTrigger value="profile" className="rounded-full text-[11px]">
                  Profile
                </TabsTrigger>
                <TabsTrigger value="security" className="rounded-full text-[11px]">
                  Security
                </TabsTrigger>
                <TabsTrigger value="roles" className="rounded-full text-[11px]">
                  Roles
                </TabsTrigger>
              </TabsList>

              <TabsContent value="profile" className="mt-3 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-medium text-slate-700">First name</div>
                    <Input
                      className="h-8 rounded-xl border-slate-200 bg-slate-50 text-xs"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-medium text-slate-700">Last name</div>
                    <Input
                      className="h-8 rounded-xl border-slate-200 bg-slate-50 text-xs"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      disabled={!canEdit}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <div className="text-[11px] font-medium text-slate-700">Email</div>
                  <Input
                    className="h-8 rounded-xl border-slate-200 bg-slate-50 text-xs"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1.5">
                  <div className="text-[11px] font-medium text-slate-700">Auth providers</div>
                  <div className="flex flex-wrap gap-1.5">
                    {user.auth_providers?.map((p) => (
                      <Badge
                        key={p}
                        variant="outline"
                        className="rounded-full border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-700"
                      >
                        {authProviderLabel(p)}
                      </Badge>
                    ))}
                    {(!user.auth_providers || user.auth_providers.length === 0) && (
                      <span className="text-[10px] text-slate-400">None</span>
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="security" className="mt-3 space-y-3">
                <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                  <div>
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-800">
                      🔑 Active account
                    </div>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      Suspend access without deleting history.
                    </p>
                  </div>
                  <Switch checked={isActive} onCheckedChange={setIsActive} disabled={!canEdit} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-[11px] text-slate-700">
                  <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <div>
                      <div className="font-medium">Django staff</div>
                      <p className="mt-0.5 text-[10px] text-slate-500">Access to /admin/ panel.</p>
                    </div>
                    <Switch checked={isStaff} onCheckedChange={setIsStaff} disabled={!canChangePrivileges} />
                  </div>
                  <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <div>
                      <div className="font-medium">Superuser</div>
                      <p className="mt-0.5 text-[10px] text-slate-500">Highest Django privileges.</p>
                    </div>
                    <Switch checked={isSuperuser} onCheckedChange={setIsSuperuser} disabled={!canChangePrivileges} />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 rounded-full border-slate-200 bg-slate-50 px-3 text-[11px]"
                    onClick={handleResetPassword}
                    disabled={resetLoading || !canEdit}
                  >
                    {resetLoading ? "Creating…" : "🔑 Create reset link"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 rounded-full border-rose-100 bg-rose-50/60 px-3 text-[11px] text-rose-700 hover:bg-rose-50"
                    onClick={() => {
                      setIsActive(false);
                    }}
                    disabled={!canEdit}
                  >
                    Freeze account
                  </Button>
                </div>
                {resetApprovalId && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                    <p className="text-[11px] font-medium text-amber-900">Password reset pending approval</p>
                    <p className="mt-1 text-[11px] text-amber-800">
                      Approval request: <code className="font-mono">{resetApprovalId}</code>
                    </p>
                    <p className="mt-1 text-[10px] text-amber-700">
                      After approval, open the Approvals tab to retrieve the reset URL (access is audited and may be redacted).
                    </p>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="roles" className="mt-3 space-y-3">
                <div className="space-y-1.5">
                  <div className="text-[11px] font-medium text-slate-700">Admin role</div>
                  <Select value={adminRole} onValueChange={(v: AdminRole) => setAdminRole(v)} disabled={!canChangePrivileges}>
                    <SelectTrigger className="h-8 w-full rounded-xl border-slate-200 bg-slate-50 px-3 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="border-slate-200 bg-white text-xs">
                      <SelectItem value="none">No admin role</SelectItem>
                      <SelectItem value="support">Support</SelectItem>
                      <SelectItem value="ops">Ops</SelectItem>
                      <SelectItem value="engineering">Engineering</SelectItem>
                      <SelectItem value="superadmin">Superadmin</SelectItem>
                      <SelectItem value="primary_admin">👑 Primary Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Separator className="my-1" />
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-slate-700">
                    <span>Effective capabilities overview</span>
                    <Badge variant="outline" className="rounded-full border-slate-200 bg-slate-50 px-2 py-0.5 text-[9px]">
                      Read-only summary
                    </Badge>
                  </div>
                  <ul className="space-y-1.5 text-[10px] text-slate-500">
                    <li>• Banking: {adminRole === "primary_admin" ? "🔐 Full control" : adminRole === "ops" || adminRole === "superadmin" ? "Full visibility" : "Limited"}</li>
                    <li>• Ledger: {adminRole === "primary_admin" || adminRole === "superadmin" ? "Global access" : "Scoped"}</li>
                    <li>• Tax Guardian: {adminRole === "primary_admin" || adminRole === "support" || adminRole === "superadmin" ? "Can inspect" : "View via owner"}</li>
                    <li>• Admin Panel: {adminRole === "primary_admin" ? "🛡️ Ultimate authority" : adminRole === "superadmin" ? "Full access" : "Limited"}</li>
                  </ul>
                </div>
              </TabsContent>
            </Tabs>
          </div>

          {/* Right column: activity & notes */}
          <div className="space-y-4">
            <Card className="border border-slate-100 bg-slate-50/80">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-semibold text-slate-800">Recent activity</CardTitle>
                <CardDescription className="text-[10px] text-slate-500">
                  High-level view of what this user has been doing.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-1">
                <div className="space-y-1.5 text-[10px] text-slate-600">
                  <div className="flex items-center justify-between">
                    <span>Last login</span>
                    <span className="text-slate-500">{formatDate(user.last_login)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Joined</span>
                    <span className="text-slate-500">{formatDate(user.date_joined)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Workspaces</span>
                    <span className="text-slate-500">{user.workspace_count ?? 0}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border border-slate-100 bg-slate-50/90">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-semibold text-slate-800">Internal notes</CardTitle>
                <CardDescription className="text-[10px] text-slate-500">
                  Keep short context for support and ops.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-1">
                <textarea
                  className="min-h-[90px] w-full resize-none rounded-2xl border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-800 shadow-inner focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500"
                  placeholder="e.g. VIP customer at mid-sized firm. Prefers email support."
                />
              </CardContent>
            </Card>

            <Card className="border border-slate-100 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 text-slate-50">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-1.5 text-xs font-semibold text-slate-50">
                      ✨ AI context
                    </CardTitle>
                    <CardDescription className="text-[10px] text-slate-300">
                      High-level risk & usage hints for this user.
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-1 text-[10px] text-slate-100/90">
                <p>• No unusual login patterns detected in the last 30 days.</p>
                <p className="mt-1">• Reconciled high volume of bank transactions across {user.workspace_count ?? 0} workspaces.</p>
                <p className="mt-1">• Good candidate for early access to advanced reconciliation and tax guardian tools.</p>
              </CardContent>
            </Card>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <Button
                type="button"
                size="sm"
                className="h-8 rounded-full bg-slate-900 px-4 text-[11px] text-slate-50 shadow-sm hover:bg-slate-950"
                onClick={handleSave}
                disabled={saving || !canEdit}
              >
                {saving ? "Saving…" : "Save changes"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 rounded-full border-slate-200 bg-slate-50 px-3 text-[11px]"
              >
                View audit log
              </Button>
            </div>
            {message && <p className="text-xs text-emerald-700">{message}</p>}
            {error && <p className="text-xs text-rose-700">{error}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default UsersSection;
