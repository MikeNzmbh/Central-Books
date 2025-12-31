import React, { useEffect, useState } from "react";

type Env = "prod" | "staging";

type OperationsMetrics = {
    openTickets: number;
    pendingApprovals: number;
    failingBankFeeds: number;
    reconciliationBacklog: number;
    taxIssues: number;
};

type OperationsQueue = {
    id: string;
    name: string;
    count: number;
    slaLabel: string;
    status: "healthy" | "warning" | "critical";
};

type OperationsTaskBucket = {
    label: string;
    tasks: OperationsTask[];
};

type OperationsTask = {
    id: string;
    kind: "bank" | "recon" | "tax" | "ai" | "support";
    title: string;
    workspace: string;
    age: string;
    priority: "low" | "medium" | "high";
    slaBreached: boolean;
};

type SystemsHealthItem = {
    id: string;
    name: string;
    status: "healthy" | "degraded" | "down";
    latencyLabel: string;
    errorRateLabel: string;
};

type ActivityItem = {
    id: string;
    time: string;
    actor: string;
    scope: string;
    action: string;
    impact: "low" | "medium" | "high";
};

type OperationsOverviewResponse = {
    env: Env;
    windowHours: number;
    metrics: OperationsMetrics;
    queues: OperationsQueue[];
    buckets: OperationsTaskBucket[];
    systems: SystemsHealthItem[];
    activity: ActivityItem[];
};

function useInternalAdminOperations() {
    const [env, setEnv] = useState<Env>("prod");
    const [windowHours, setWindowHours] = useState<number>(24);
    const [data, setData] = useState<OperationsOverviewResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchData = async () => {
        try {
            setLoading(true);
            setError(null);
            const params = new URLSearchParams({ env, window_hours: String(windowHours) });
            const res = await fetch(`/api/admin/operations-overview/?${params.toString()}`, {
                credentials: "include",
            });
            if (!res.ok) {
                throw new Error(`Request failed with status ${res.status}`);
            }
            const json = (await res.json()) as OperationsOverviewResponse;
            setData(json);
        } catch (e: any) {
            setError(e?.message ?? "Unable to load operations overview");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60_000);
        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [env, windowHours]);

    return { env, setEnv, windowHours, setWindowHours, data, loading, error, refetch: fetchData };
}

function StatusPill({ label, tone }: { label: string; tone: "success" | "warning" | "danger" | "neutral" }) {
    const base = "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium";
    const map: Record<typeof tone, string> = {
        success: "bg-emerald-50 text-emerald-700 border border-emerald-100",
        warning: "bg-amber-50 text-amber-700 border border-amber-100",
        danger: "bg-rose-50 text-rose-700 border border-rose-100",
        neutral: "bg-slate-50 text-slate-700 border border-slate-100",
    } as any;
    return <span className={`${base} ${map[tone]}`}>{label}</span>;
}

function MetricCard({ title, value, subtitle, tone }: { title: string; value: string; subtitle?: string; tone?: "default" | "warning" | "danger" }) {
    const toneClass =
        tone === "danger"
            ? "ring-rose-100"
            : tone === "warning"
                ? "ring-amber-100"
                : "ring-slate-100";
    return (
        <div className={`flex flex-col justify-between rounded-2xl bg-white px-4 py-3 shadow-sm ring-1 ${toneClass}`}>
            <div className="text-xs font-medium tracking-wide text-slate-500 uppercase">{title}</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
            {subtitle && <div className="mt-1 text-xs text-slate-500">{subtitle}</div>}
        </div>
    );
}

function OperationsDashboardHeader(props: {
    env: Env;
    setEnv: (env: Env) => void;
    windowHours: number;
    setWindowHours: (h: number) => void;
    onRefresh: () => void;
}) {
    const { env, setEnv, windowHours, setWindowHours, onRefresh } = props;
    return (
        <div className="flex items-start justify-between gap-4">
            <div>
                <div className="text-xs font-semibold tracking-[0.16em] text-emerald-700 uppercase">Internal admin</div>
                <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">Operations control center</h1>
                <p className="mt-1 text-sm text-slate-500 max-w-xl">
                    Live view of workloads, queues, and system health across all tenants. Designed for support, ops, and finance teams
                    to keep Clover Books running smoothly.
                </p>
            </div>
            <div className="flex flex-col items-end gap-2">
                <div className="flex gap-2">
                    <select
                        value={env}
                        onChange={(e) => setEnv(e.target.value as Env)}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm"
                    >
                        <option value="prod">Prod</option>
                        <option value="staging">Staging</option>
                    </select>
                    <select
                        value={windowHours}
                        onChange={(e) => setWindowHours(Number(e.target.value))}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm"
                    >
                        <option value={1}>Last 1 hour</option>
                        <option value={6}>Last 6 hours</option>
                        <option value={24}>Last 24 hours</option>
                        <option value={72}>Last 3 days</option>
                        <option value={168}>Last 7 days</option>
                    </select>
                    <button
                        type="button"
                        onClick={onRefresh}
                        className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800"
                    >
                        Refresh
                    </button>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Core systems healthy
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">SUPERADMIN</span>
                </div>
            </div>
        </div>
    );
}

function QueuesPanel({ queues }: { queues: OperationsQueue[] }) {
    return (
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold text-slate-900">Operational queues</h2>
                    <p className="mt-1 text-xs text-slate-500">Work waiting in line. Higher counts with breached SLA require attention.</p>
                </div>
                <button className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                    View all queues
                </button>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {queues.map((q) => {
                    const tone: "success" | "warning" | "danger" =
                        q.status === "healthy" ? "success" : q.status === "warning" ? "warning" : "danger";
                    return (
                        <div key={q.id} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                            <div>
                                <div className="text-xs font-medium text-slate-800">{q.name}</div>
                                <div className="mt-1 text-[11px] text-slate-500">SLA: {q.slaLabel}</div>
                            </div>
                            <div className="text-right">
                                <div className="text-sm font-semibold text-slate-900">{q.count}</div>
                                <div className="mt-1">
                                    <StatusPill
                                        label={q.status === "healthy" ? "On target" : q.status === "warning" ? "At risk" : "Breached"}
                                        tone={tone}
                                    />
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function SystemsHealthPanel({ systems }: { systems: SystemsHealthItem[] }) {
    return (
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold text-slate-900">Systems health</h2>
                    <p className="mt-1 text-xs text-slate-500">Core pipelines and engines powering operations.</p>
                </div>
            </div>
            <div className="mt-3 divide-y divide-slate-100">
                {systems.map((s) => {
                    const tone: "success" | "warning" | "danger" =
                        s.status === "healthy" ? "success" : s.status === "degraded" ? "warning" : "danger";
                    return (
                        <div key={s.id} className="flex items-center justify-between py-2.5">
                            <div>
                                <div className="text-xs font-medium text-slate-900">{s.name}</div>
                                <div className="mt-1 text-[11px] text-slate-500">
                                    Latency {s.latencyLabel} · Errors {s.errorRateLabel}
                                </div>
                            </div>
                            <StatusPill
                                label={s.status === "healthy" ? "Healthy" : s.status === "degraded" ? "Degraded" : "Down"}
                                tone={tone}
                            />
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function ActivityPanel({ items }: { items: ActivityItem[] }) {
    return (
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold text-slate-900">Recent operational activity</h2>
                    <p className="mt-1 text-xs text-slate-500">Latest high-impact changes from admins and automation.</p>
                </div>
                <button className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                    Open audit log
                </button>
            </div>
            <div className="mt-3 max-h-64 space-y-2 overflow-auto">
                {items.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-6 text-center text-xs text-slate-500">
                        No recent high-impact actions in this window.
                    </div>
                ) : (
                    items.map((item) => {
                        const tone: "success" | "warning" | "danger" | "neutral" =
                            item.impact === "low" ? "neutral" : item.impact === "medium" ? "warning" : "danger";
                        return (
                            <div
                                key={item.id}
                                className="flex items-start justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
                            >
                                <div>
                                    <div className="text-xs font-medium text-slate-900">{item.action}</div>
                                    <div className="mt-1 text-[11px] text-slate-500">
                                        {item.actor} · {item.scope}
                                    </div>
                                </div>
                                <div className="flex flex-col items-end gap-1">
                                    <div className="text-[11px] text-slate-400">{item.time}</div>
                                    <StatusPill
                                        label={item.impact === "low" ? "Low" : item.impact === "medium" ? "Medium" : "High"}
                                        tone={tone}
                                    />
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}

const KIND_LABELS: Record<OperationsTask["kind"], string> = {
    bank: "Bank",
    recon: "Reconciliation",
    tax: "Tax",
    ai: "AI",
    support: "Support",
};

function OperationsBoard({ buckets }: { buckets: OperationsTaskBucket[] }) {
    return (
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold text-slate-900">Operations board</h2>
                    <p className="mt-1 text-xs text-slate-500">Today's workload grouped by urgency. Use this to coordinate the ops standup.</p>
                </div>
                <button className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                    Export as CSV
                </button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
                {buckets.map((bucket) => (
                    <div key={bucket.label} className="flex flex-col rounded-xl bg-slate-50 p-3">
                        <div className="flex items-center justify-between">
                            <div className="text-xs font-semibold text-slate-800">{bucket.label}</div>
                            <span className="text-[11px] text-slate-400">{bucket.tasks.length} items</span>
                        </div>
                        <div className="mt-2 space-y-2 overflow-auto">
                            {bucket.tasks.length === 0 ? (
                                <div className="rounded-lg border border-dashed border-slate-200 bg-white px-2 py-4 text-center text-[11px] text-slate-400">
                                    Nothing in this bucket.
                                </div>
                            ) : (
                                bucket.tasks.map((task) => {
                                    const priorityTone: "success" | "warning" | "danger" | "neutral" =
                                        task.priority === "low" ? "neutral" : task.priority === "medium" ? "warning" : "danger";
                                    return (
                                        <button
                                            key={task.id}
                                            className="w-full rounded-lg bg-white px-2.5 py-2 text-left text-xs transition hover:bg-slate-100"
                                        >
                                            <div className="flex items-center justify-between gap-1">
                                                <div className="font-medium text-slate-900 truncate">{task.title}</div>
                                                <StatusPill
                                                    label={task.priority === "low" ? "Low" : task.priority === "medium" ? "Medium" : "High"}
                                                    tone={priorityTone}
                                                />
                                            </div>
                                            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
                                                <span className="truncate">{task.workspace}</span>
                                                <span>{task.age}</span>
                                            </div>
                                            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                                                <span>{KIND_LABELS[task.kind]}</span>
                                                {task.slaBreached && <span className="text-rose-500">SLA breached</span>}
                                            </div>
                                        </button>
                                    );
                                })
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function OverviewSection() {
    const { env, setEnv, windowHours, setWindowHours, data, loading, error, refetch } = useInternalAdminOperations();

    const metrics = data?.metrics;

    return (
        <div className="space-y-6">
            <OperationsDashboardHeader
                env={env}
                setEnv={setEnv}
                windowHours={windowHours}
                setWindowHours={setWindowHours}
                onRefresh={refetch}
            />

            {error && (
                <div className="rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs text-rose-700">
                    {error}
                </div>
            )}

            <div className="grid gap-3 md:grid-cols-5">
                <MetricCard
                    title="Open support tickets"
                    value={metrics ? String(metrics.openTickets) : loading ? "…" : "0"}
                    subtitle="Across all tenants in this window"
                />
                <MetricCard
                    title="Pending approvals"
                    value={metrics ? String(metrics.pendingApprovals) : loading ? "…" : "0"}
                    subtitle="Maker-checker queue"
                    tone={metrics && metrics.pendingApprovals > 0 ? "warning" : "default"}
                />
                <MetricCard
                    title="Workspaces with failing feeds"
                    value={metrics ? String(metrics.failingBankFeeds) : loading ? "…" : "0"}
                    subtitle="Bank feeds with sync errors"
                    tone={metrics && metrics.failingBankFeeds > 0 ? "danger" : "default"}
                />
                <MetricCard
                    title="Reconciliation backlog"
                    value={metrics ? String(metrics.reconciliationBacklog) : loading ? "…" : "0"}
                    subtitle="Unreconciled items older than 30d"
                    tone={metrics && metrics.reconciliationBacklog > 0 ? "warning" : "default"}
                />
                <MetricCard
                    title="Open tax issues"
                    value={metrics ? String(metrics.taxIssues) : loading ? "…" : "0"}
                    subtitle="Late filings and anomalies"
                    tone={metrics && metrics.taxIssues > 0 ? "danger" : "default"}
                />
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2">
                    <OperationsBoard buckets={data?.buckets ?? []} />
                </div>
                <div className="space-y-4">
                    <QueuesPanel queues={data?.queues ?? []} />
                    <SystemsHealthPanel systems={data?.systems ?? []} />
                </div>
            </div>

            <ActivityPanel items={data?.activity ?? []} />
        </div>
    );
}

export default OverviewSection;
