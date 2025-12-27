import React, { useCallback, useEffect, useState } from "react";
import {
    fetchApprovals,
    approveRequest,
    rejectRequest,
    createApprovalRequest,
    breakGlassApproval,
    type ApprovalRequest,
    type ApprovalList,
    type ApprovalActionType,
    type ApprovalStatus,
} from "./api";

// ----------------------
// Types
// ----------------------

type RiskLevel = "low" | "medium" | "high";

// ----------------------
// Helpers
// ----------------------

function classNames(...classes: (string | false | null | undefined)[]) {
    return classes.filter(Boolean).join(" ");
}

const riskColors: Record<RiskLevel, string> = {
    low: "bg-emerald-50 text-emerald-700 border-emerald-100",
    medium: "bg-amber-50 text-amber-700 border-amber-100",
    high: "bg-rose-50 text-rose-700 border-rose-100",
};

const statusColors: Record<string, string> = {
    PENDING: "bg-blue-50 text-blue-700 border-blue-100",
    APPROVED: "bg-emerald-50 text-emerald-700 border-emerald-100",
    REJECTED: "bg-rose-50 text-rose-700 border-rose-100",
    EXPIRED: "bg-slate-50 text-slate-600 border-slate-100",
    FAILED: "bg-rose-50 text-rose-700 border-rose-100",
};

const ACTION_TYPES: { value: ApprovalActionType; label: string; risk: RiskLevel }[] = [
    { value: "TAX_PERIOD_RESET", label: "Reset Tax Period", risk: "high" },
    { value: "LEDGER_ADJUST", label: "Ledger Adjustment", risk: "medium" },
    { value: "WORKSPACE_DELETE", label: "Delete Workspace", risk: "high" },
    { value: "BULK_REFUND", label: "Bulk Refund", risk: "high" },
    { value: "USER_BAN", label: "Ban User", risk: "high" },
    { value: "USER_REACTIVATE", label: "Reactivate User", risk: "high" },
    { value: "USER_PRIVILEGE_CHANGE", label: "Change User Privileges", risk: "high" },
    { value: "PASSWORD_RESET_LINK", label: "Create Password Reset Link", risk: "high" },
    { value: "FEATURE_FLAG_CRITICAL", label: "Toggle Critical Feature", risk: "medium" },
];

function getActionTypeLabel(type: string): string {
    const found = ACTION_TYPES.find(a => a.value === type);
    return found?.label || type.replace(/_/g, " ");
}

function getRiskLevel(actionType: string): RiskLevel {
    const found = ACTION_TYPES.find(a => a.value === actionType);
    return found?.risk || "low";
}

function getInitials(email: string | null): string {
    if (!email) return "?";
    const name = email.split("@")[0];
    const parts = name.split(/[._-]/);
    return parts.slice(0, 2).map(p => p[0]?.toUpperCase() || "").join("");
}

// ----------------------
// Main Page
// ----------------------

interface Role {
    level: number;
}

interface ApprovalsSectionProps {
    role?: Role;
}

export const ApprovalsSection: React.FC<ApprovalsSectionProps> = ({ role }) => {
    const [data, setData] = useState<ApprovalList | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [selected, setSelected] = useState<ApprovalRequest | null>(null);

    const [statusFilter, setStatusFilter] = useState<ApprovalStatus>("PENDING");
    const [search, setSearch] = useState("");
    const [liveMode, setLiveMode] = useState(false);

    // Create modal state
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [newActionType, setNewActionType] = useState<ApprovalActionType>("TAX_PERIOD_RESET");
    const [newReason, setNewReason] = useState("");
    const [creating, setCreating] = useState(false);

    const loadApprovals = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchApprovals({ status: statusFilter, search: search || undefined });
            setData(result);
        } catch (err: any) {
            setError(err?.message || "Failed to load approvals");
        } finally {
            setLoading(false);
        }
    }, [statusFilter, search]);

    useEffect(() => {
        loadApprovals();
    }, [loadApprovals]);

    // Live polling
    useEffect(() => {
        if (!liveMode) return;
        const interval = setInterval(loadApprovals, 15000);
        return () => clearInterval(interval);
    }, [liveMode, loadApprovals]);

    // Keep selected in sync with data
    useEffect(() => {
        if (selected && data?.results) {
            const updated = data.results.find(r => r.id === selected.id);
            if (updated) setSelected(updated);
        }
    }, [data, selected?.id]);

    const handleApprove = async (requestId: string) => {
        if (!confirm("Are you sure you want to approve this request?")) return;
        setActionLoading(requestId);
        try {
            await approveRequest(requestId);
            loadApprovals();
            setSelected(null);
        } catch (err: any) {
            alert(err?.message || "Failed to approve");
        } finally {
            setActionLoading(null);
        }
    };

    const handleReject = async (requestId: string) => {
        const reason = prompt("Enter rejection reason (optional):");
        if (reason === null) return;
        setActionLoading(requestId);
        try {
            await rejectRequest(requestId, reason);
            loadApprovals();
            setSelected(null);
        } catch (err: any) {
            alert(err?.message || "Failed to reject");
        } finally {
            setActionLoading(null);
        }
    };

    const handleCreateRequest = async () => {
        if (!newReason.trim()) {
            alert("Please provide a reason for this request.");
            return;
        }
        if (!role || role.level < 2) {
            alert("OPS or higher required to create approval requests.");
            return;
        }
        setCreating(true);
        try {
            await createApprovalRequest({
                action_type: newActionType,
                reason: newReason.trim(),
            });
            setShowCreateModal(false);
            setNewReason("");
            setNewActionType("TAX_PERIOD_RESET");
            // Refresh list and switch to pending
            setStatusFilter("PENDING");
            loadApprovals();
        } catch (err: any) {
            alert(err?.message || "Failed to create request");
        } finally {
            setCreating(false);
        }
    };

    const requiredApproverLevel = (actionType: ApprovalActionType): number => {
        if (actionType === "WORKSPACE_DELETE") return 4;
        if (actionType === "USER_PRIVILEGE_CHANGE") return 4;
        if (actionType === "FEATURE_FLAG_CRITICAL") return 4;
        return 2;
    };

    const canApprove = (req: ApprovalRequest) => Boolean(role && role.level >= requiredApproverLevel(req.action_type));
    const canOps = Boolean(role && role.level >= 2);

    const handleBreakGlass = async (requestId: string) => {
        if (!canOps) {
            alert("OPS or higher required for break-glass.");
            return;
        }
        const reason = prompt("Enter break-glass reason (required):");
        if (reason === null) return;
        if (!reason.trim()) {
            alert("Reason is required.");
            return;
        }
        const ttlStr = prompt("TTL minutes (optional, max 60):", "10");
        let ttlMinutes: number | undefined = undefined;
        if (ttlStr !== null && ttlStr.trim() !== "") {
            const parsed = Number(ttlStr);
            if (!Number.isNaN(parsed) && parsed > 0) ttlMinutes = parsed;
        }
        setActionLoading(`breakglass:${requestId}`);
        try {
            await breakGlassApproval(requestId, reason.trim(), ttlMinutes);
            await loadApprovals();
        } catch (err: any) {
            alert(err?.message || "Failed to break-glass");
        } finally {
            setActionLoading(null);
        }
    };
    const summary = data?.summary;

    return (
        <div className="space-y-4">
            {/* Header */}
            <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-xl font-semibold tracking-tight text-slate-900">Approval Queue</h1>
                    <p className="mt-1 text-sm text-slate-600">
                        {summary?.total_pending === 0
                            ? "Maker-Checker workflow for high-risk admin actions."
                            : summary?.total_pending === 1
                                ? "1 pending approval request"
                                : `${summary?.total_pending || 0} pending approval requests`}
                        {" "}Actions require dual approval before execution.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {canOps && (
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700"
                        >
                            + New Request
                        </button>
                    )}
                    <label className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 cursor-pointer">
                        <input
                            type="checkbox"
                            className="h-3 w-3 rounded border-slate-300 text-emerald-600"
                            checked={liveMode}
                            onChange={(e) => setLiveMode(e.target.checked)}
                        />
                        Live tail
                    </label>
                    <button
                        onClick={loadApprovals}
                        disabled={loading}
                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
                    >
                        🔄 Refresh
                    </button>
                </div>
            </header>

            {/* Summary Cards */}
            <div className="grid gap-3 sm:grid-cols-4">
                <SummaryCard label="Pending approvals" value={summary?.total_pending ?? 0} tone="blue" helper={summary?.high_risk_pending ? `${summary.high_risk_pending} high risk` : "All caught up"} />
                <SummaryCard label="Requests today" value={summary?.total_today ?? 0} tone="emerald" helper="Last 24 hours" />
                <SummaryCard label="High-risk pending" value={summary?.high_risk_pending ?? 0} tone="rose" helper="Require senior checker" />
                <SummaryCard label="Avg. response time" value={summary?.avg_response_minutes_24h ?? "–"} suffix={summary?.avg_response_minutes_24h ? "min" : undefined} tone="slate" helper="Completed in last 24h" />
            </div>

            {/* Main content grid */}
            <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.35fr)]">
                {/* Left: Queue list */}
                <section className="rounded-2xl border border-slate-200 bg-white px-4 pb-4 pt-3 shadow-sm">
                    <div className="mb-3 flex flex-wrap items-center gap-3">
                        {/* Status tabs */}
                        <div className="inline-flex rounded-full bg-slate-100 p-1 text-xs font-medium text-slate-600">
                            {(["PENDING", "APPROVED", "REJECTED", "EXPIRED", "FAILED"] as const).map((status) => (
                                <button
                                    key={status}
                                    type="button"
                                    onClick={() => setStatusFilter(status)}
                                    className={classNames(
                                        "rounded-full px-3 py-1 capitalize transition",
                                        statusFilter === status ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                                    )}
                                >
                                    {status.charAt(0) + status.slice(1).toLowerCase()}
                                </button>
                            ))}
                        </div>

                        <div className="flex flex-1 items-center justify-end gap-2">
                            <div className="relative w-48">
                                <span className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate-400 text-xs">🔍</span>
                                <input
                                    type="search"
                                    placeholder="Search user, workspace, action…"
                                    className="h-8 w-full rounded-full border border-slate-200 bg-slate-50 pl-7 pr-3 text-xs text-slate-700 placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:outline-none"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                    onKeyDown={(e) => e.key === "Enter" && loadApprovals()}
                                />
                            </div>
                        </div>
                    </div>

                    <div className="relative mt-1">
                        {loading && (
                            <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-white/60">
                                <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-500 shadow-sm">
                                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                                    Loading approvals…
                                </div>
                            </div>
                        )}

                        {error && (
                            <div className="rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                                {error}
                            </div>
                        )}

                        {!loading && !error && (data?.results.length ?? 0) === 0 && (
                            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center">
                                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50">
                                    <span className="text-lg">✅</span>
                                </div>
                                <p className="text-sm font-medium text-slate-900">No {statusFilter.toLowerCase()} approvals</p>
                                <p className="mt-1 text-xs text-slate-600">No approval requests matching your filters at this time.</p>
                                {statusFilter === "PENDING" && canOps && (
                                    <button
                                        onClick={() => setShowCreateModal(true)}
                                        className="mt-3 inline-flex items-center gap-1 rounded-full bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
                                    >
                                        + Create first request
                                    </button>
                                )}
                            </div>
                        )}

                        {!loading && !error && (data?.results.length ?? 0) > 0 && (
                            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100 bg-white max-h-[480px] overflow-y-auto">
                                {data?.results.map((req) => {
                                    const risk = getRiskLevel(req.action_type);
                                    return (
                                        <li
                                            key={req.id}
                                            className={classNames(
                                                "cursor-pointer px-4 py-3 text-xs transition hover:bg-slate-50",
                                                selected?.id === req.id && "bg-slate-50"
                                            )}
                                            onClick={() => setSelected(req)}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex flex-1 items-start gap-3">
                                                    <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-[10px] font-semibold text-slate-700">
                                                        {getInitials(req.initiator.email)}
                                                    </div>
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-2">
                                                            <p className="font-medium text-slate-900">{getActionTypeLabel(req.action_type)}</p>
                                                            {req.workspace && (
                                                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                                                    {req.workspace.name}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <p className="mt-0.5 text-[11px] text-slate-600">
                                                            Maker <span className="font-medium">{req.initiator.email}</span> • {new Date(req.created_at).toLocaleString()}
                                                            {req.expires_at && req.status === "PENDING" && <> • Expires {new Date(req.expires_at).toLocaleString()}</>}
                                                        </p>
                                                        {req.reason && (
                                                            <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">Reason: {req.reason}</p>
                                                        )}
                                                    </div>
                                                </div>
                                                <div className="flex flex-col items-end gap-1">
                                                    <span className={classNames("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize", riskColors[risk])}>
                                                        {risk} risk
                                                    </span>
                                                    <span className={classNames("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize", statusColors[req.status])}>
                                                        {req.status.toLowerCase()}
                                                    </span>
                                                </div>
                                            </div>
                                        </li>
                                    );
                                })}
                            </ul>
                        )}

                        {!loading && !error && (
                            <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                                <p>Showing <span className="font-medium">{data?.results.length ?? 0}</span> requests</p>
                            </div>
                        )}
                    </div>
                </section>

                {/* Right: Detail & About */}
                <section className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm min-h-[220px]">
                        {selected ? (
                            <ApprovalDetailCard
                                request={selected}
                                canApprove={canApprove(selected) && selected.status === "PENDING"}
                                onApprove={() => handleApprove(selected.id)}
                                onReject={() => handleReject(selected.id)}
                                canBreakGlass={canOps}
                                onBreakGlass={() => handleBreakGlass(selected.id)}
                                loading={actionLoading === selected.id}
                                breakGlassLoading={actionLoading === `breakglass:${selected.id}`}
                            />
                        ) : (
                            <div className="flex h-full min-h-[180px] flex-col items-center justify-center text-center">
                                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100">
                                    <span className="text-lg text-slate-500">🧾</span>
                                </div>
                                <p className="text-sm font-medium text-slate-900">Select a request to review</p>
                                <p className="mt-1 text-xs text-slate-600">Choose an approval from the list to see full details, diffs, and actions.</p>
                            </div>
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
                        <h2 className="text-xs font-semibold tracking-wide text-slate-700">About Maker-Checker</h2>
                        <p className="mt-1 text-xs text-slate-600">
                            Dual-approval workflow for high-risk internal actions. Maker submits a request, Checker reviews and approves or rejects.
                        </p>
                        <dl className="mt-3 grid gap-3 text-xs text-slate-600 sm:grid-cols-2">
                            <div>
                                <dt className="font-medium text-slate-800">Maker</dt>
                                <dd className="mt-0.5">Initiates the high-risk action and provides reasoning.</dd>
                            </div>
                            <div>
                                <dt className="font-medium text-slate-800">Checker</dt>
                                <dd className="mt-0.5">Reviews the request and approves or rejects.</dd>
                            </div>
                            <div>
                                <dt className="font-medium text-slate-800">Guardrails</dt>
                                <dd className="mt-0.5">Same person cannot be Maker and Checker. Auto-expires after 24h.</dd>
                            </div>
                            <div>
                                <dt className="font-medium text-slate-800">Examples</dt>
                                <dd className="mt-0.5">Large refunds, tax resets, workspace deletions.</dd>
                            </div>
                        </dl>
                    </div>
                </section>
            </div>

            {/* Create Request Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm">
                    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-base font-semibold text-slate-900">New Approval Request</h2>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="text-slate-400 hover:text-slate-600"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-slate-700 mb-1">Action Type</label>
                                <select
                                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-emerald-400 focus:outline-none"
                                    value={newActionType}
                                    onChange={(e) => setNewActionType(e.target.value as ApprovalActionType)}
                                >
                                    {ACTION_TYPES.map((action) => (
                                        <option key={action.value} value={action.value}>
                                            {action.label} ({action.risk} risk)
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-slate-700 mb-1">Reason / Justification</label>
                                <textarea
                                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-emerald-400 focus:outline-none"
                                    rows={4}
                                    placeholder="Explain why this action is needed and provide any relevant context..."
                                    value={newReason}
                                    onChange={(e) => setNewReason(e.target.value)}
                                />
                            </div>

                            <div className="flex items-center justify-end gap-2 pt-2">
                                <button
                                    onClick={() => setShowCreateModal(false)}
                                    className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleCreateRequest}
                                    disabled={creating || !newReason.trim()}
                                    className="rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
                                >
                                    {creating ? "Creating…" : "Submit Request"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// ----------------------
// Summary Card
// ----------------------

interface SummaryCardProps {
    label: string;
    value: number | string;
    suffix?: string;
    helper?: string;
    tone: "blue" | "emerald" | "rose" | "slate";
}

function SummaryCard({ label, value, suffix, helper, tone }: SummaryCardProps) {
    const toneClasses: Record<string, string> = {
        blue: "border-blue-100 bg-blue-50/70",
        emerald: "border-emerald-100 bg-emerald-50/70",
        rose: "border-rose-100 bg-rose-50/70",
        slate: "border-slate-100 bg-slate-50/70",
    };

    return (
        <div className={classNames("rounded-2xl border px-3 py-2.5", toneClasses[tone])}>
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-600">{label}</p>
            <div className="mt-1 flex items-baseline gap-1">
                <span className="text-lg font-semibold text-slate-900">{value}</span>
                {suffix && <span className="text-[11px] text-slate-500">{suffix}</span>}
            </div>
            {helper && <p className="mt-0.5 text-[11px] text-slate-600">{helper}</p>}
        </div>
    );
}

// ----------------------
// Detail Card
// ----------------------

interface ApprovalDetailCardProps {
    request: ApprovalRequest;
    canApprove: boolean;
    onApprove: () => void;
    onReject: () => void;
    canBreakGlass: boolean;
    onBreakGlass: () => void;
    loading: boolean;
    breakGlassLoading: boolean;
}

function ApprovalDetailCard({ request, canApprove, onApprove, onReject, canBreakGlass, onBreakGlass, loading, breakGlassLoading }: ApprovalDetailCardProps) {
    const risk = getRiskLevel(request.action_type);
    const created = new Date(request.created_at);
    const resolved = request.resolved_at ? new Date(request.resolved_at) : null;
    const expires = request.expires_at ? new Date(request.expires_at) : null;
    const redactedKeysRaw = (request.payload as any)?._redacted;
    const redactedKeys = Array.isArray(redactedKeysRaw) ? redactedKeysRaw.filter((k) => typeof k === "string") : [];
    const resetUrl = (request.payload as any)?.reset_url;
    const resetUrlRedacted = redactedKeys.includes("reset_url");
    const hasResetUrl = typeof resetUrl === "string" && resetUrl.length > 0;

    return (
        <div className="space-y-3 text-xs text-slate-700">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <h2 className="text-sm font-semibold text-slate-900">{getActionTypeLabel(request.action_type)}</h2>
                    <p className="mt-0.5 text-[11px] text-slate-600">Request ID <span className="font-mono text-[11px]">{request.id.slice(0, 8)}...</span></p>
                </div>
                <div className="flex flex-col items-end gap-1">
                    <span className={classNames("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize", riskColors[risk])}>
                        {risk} risk
                    </span>
                    <span className={classNames("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize", statusColors[request.status])}>
                        {request.status.toLowerCase()}
                    </span>
                </div>
            </div>

            {request.status === "FAILED" && request.execution_error && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2">
                    <p className="text-[11px] font-semibold text-rose-900">Execution error</p>
                    <p className="mt-1 whitespace-pre-wrap text-[11px] text-rose-800">{request.execution_error}</p>
                </div>
            )}

            {request.reason && (
                <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <p className="text-[11px] font-semibold text-slate-800">Maker reason</p>
                    <p className="mt-1 text-[11px] text-slate-700">{request.reason}</p>
                </div>
            )}

            {request.rejection_reason && (
                <div className="rounded-xl bg-rose-50 px-3 py-2">
                    <p className="text-[11px] font-semibold text-rose-800">Rejection reason</p>
                    <p className="mt-1 text-[11px] text-rose-700">{request.rejection_reason}</p>
                </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <p className="text-[11px] font-semibold text-slate-800">Maker</p>
                    <p className="mt-0.5 text-[11px] text-slate-800">{request.initiator.email || `User #${request.initiator.id}`}</p>
                </div>
                {request.approver && (
                    <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                        <p className="text-[11px] font-semibold text-slate-800">Checker</p>
                        <p className="mt-0.5 text-[11px] text-slate-800">{request.approver.email || `User #${request.approver.id}`}</p>
                    </div>
                )}
                {request.workspace && (
                    <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                        <p className="text-[11px] font-semibold text-slate-800">Workspace</p>
                        <p className="mt-0.5 text-[11px] text-slate-800">{request.workspace.name || `#${request.workspace.id}`}</p>
                    </div>
                )}
                {request.target_user && (
                    <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                        <p className="text-[11px] font-semibold text-slate-800">Target User</p>
                        <p className="mt-0.5 text-[11px] text-slate-800">{request.target_user.email || `#${request.target_user.id}`}</p>
                    </div>
                )}
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-100 bg-white px-3 py-2.5">
                    <p className="text-[11px] font-semibold text-slate-800">Created</p>
                    <p className="mt-0.5 text-[11px] text-slate-700">{created.toLocaleString()}</p>
                </div>
                {resolved && (
                    <div className="rounded-xl border border-slate-100 bg-white px-3 py-2.5">
                        <p className="text-[11px] font-semibold text-slate-800">Resolved</p>
                        <p className="mt-0.5 text-[11px] text-slate-700">{resolved.toLocaleString()}</p>
                    </div>
                )}
                {expires && request.status === "PENDING" && (
                    <div className="rounded-xl border border-slate-100 bg-white px-3 py-2.5">
                        <p className="text-[11px] font-semibold text-slate-800">Expires</p>
                        <p className="mt-0.5 text-[11px] text-slate-700">{expires.toLocaleString()}</p>
                    </div>
                )}
            </div>

            {request.action_type === "PASSWORD_RESET_LINK" && (
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <p className="text-[11px] font-semibold text-slate-800">Password reset link</p>
                    {hasResetUrl ? (
                        <div className="mt-1 flex flex-col gap-2">
                            <code className="block rounded bg-white px-2 py-1 text-[11px] font-mono text-slate-900 select-all break-all">
                                {resetUrl}
                            </code>
                            <button
                                type="button"
                                className="self-start rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
                                onClick={() => navigator.clipboard?.writeText(String(resetUrl))}
                            >
                                Copy link
                            </button>
                        </div>
                    ) : resetUrlRedacted ? (
                        <div className="mt-1 space-y-2">
                            <p className="text-[11px] text-slate-700">Reset URL is redacted.</p>
                            <button
                                type="button"
                                disabled={!canBreakGlass || breakGlassLoading}
                                className="rounded-full border border-amber-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                                onClick={onBreakGlass}
                            >
                                {breakGlassLoading ? "Revealing…" : "Break-glass reveal"}
                            </button>
                            <p className="text-[10px] text-slate-500">Break-glass access is audited and time-limited.</p>
                        </div>
                    ) : (
                        <p className="mt-1 text-[11px] text-slate-700">Approve the request to generate the reset URL.</p>
                    )}
                </div>
            )}

            {Object.keys(request.payload).length > 0 && (
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <p className="text-[11px] font-semibold text-slate-800">Payload</p>
                    <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-slate-900/95 p-2 text-[10px] leading-relaxed text-slate-50">
                        {JSON.stringify(request.payload, null, 2)}
                    </pre>
                </div>
            )}

            {canApprove && (
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                    <button
                        onClick={onReject}
                        disabled={loading}
                        className="rounded-full border border-rose-200 bg-white px-4 py-1.5 text-[11px] font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                    >
                        Reject
                    </button>
                    <button
                        onClick={onApprove}
                        disabled={loading}
                        className="rounded-full bg-emerald-600 px-4 py-1.5 text-[11px] font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
                    >
                        {loading ? "Processing…" : "Approve"}
                    </button>
                </div>
            )}
        </div>
    );
}

export default ApprovalsSection;
