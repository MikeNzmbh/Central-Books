import React, { useMemo, useState } from "react";
import { Info, AlertTriangle, CheckCircle2, Clock, ChevronRight, Sparkles } from "lucide-react";

// -----------------------------------------------------------------------------
// Types & Interfaces
// -----------------------------------------------------------------------------

export type RadarAxisKey = "reconciliation" | "ledger" | "invoices" | "expenses" | "taxFx" | "bank";

export type CompanionInsightSeverity = "info" | "warning" | "critical";

export interface CompanionInsight {
    id: string;
    title: string;
    message: string;
    severity: CompanionInsightSeverity;
    categoryLabel?: string;
}

export type CompanionTaskSeverity = "low" | "medium" | "high" | "info";

export interface CompanionTask {
    id: string;
    title: string;
    subtitle: string;
    severity: CompanionTaskSeverity;
    confidenceLabel?: string;
    categoryLabel?: string;
    ctaLabel?: string;
    secondaryLabel?: string;
}

export interface CompanionBreakdown {
    dateLabel: string;
    reconciliation: number;
    ledgerIntegrity: number;
    invoices: number;
    expenses: number;
    taxFx: number;
    bank: number;
}

export interface DashboardCompanionPanelProps {
    greetingName?: string;
    headline?: string;
    aiSummary?: string;
    breakdown: CompanionBreakdown;
    insights: CompanionInsight[];
    tasks: CompanionTask[];
    onTaskPrimary?: (taskId: string) => void;
    onTaskSecondary?: (taskId: string) => void;
    onOpenFullCompanion?: () => void;
}

// -----------------------------------------------------------------------------
// Constants & Styles
// -----------------------------------------------------------------------------

const severitySortOrder: CompanionTaskSeverity[] = ["high", "medium", "low", "info"];

const severityLabels: Record<CompanionTaskSeverity, string> = {
    high: "HIGH PRIORITY",
    medium: "MEDIUM PRIORITY",
    low: "LOW PRIORITY",
    info: "INFO",
};

const severityStyles: Record<CompanionTaskSeverity, string> = {
    high: "bg-red-50 text-red-700 border-red-100",
    medium: "bg-amber-50 text-amber-700 border-amber-100",
    low: "bg-emerald-50 text-emerald-700 border-emerald-100",
    info: "bg-sky-50 text-sky-700 border-sky-100",
};

const insightStyles: Record<CompanionInsightSeverity, string> = {
    info: "bg-blue-50 text-slate-900 border-blue-100",
    warning: "bg-amber-50 text-amber-900 border-amber-100",
    critical: "bg-red-50 text-red-900 border-red-100",
};

// -----------------------------------------------------------------------------
// Helper Components
// -----------------------------------------------------------------------------

function BreakdownRow(props: { label: string; value: number; tone?: "primary" | "neutral" }) {
    const { label, value, tone = "neutral" } = props;
    const width = Math.max(4, Math.min(100, value));
    const isPrimary = tone === "primary";

    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                <span>{label}</span>
                <span className="font-mono-soft text-slate-700">{value}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                    className={
                        "h-2 rounded-full transition-all duration-500 " +
                        (isPrimary
                            ? "bg-gradient-to-r from-emerald-400 via-sky-400 to-blue-500"
                            : "bg-slate-300")
                    }
                    style={{ width: `${width}%` }}
                />
            </div>
        </div>
    );
}

function InsightBadge({ severity }: { severity: CompanionInsightSeverity }) {
    const icon = severity === "critical" ? <AlertTriangle className="h-3 w-3" /> : <Info className="h-3 w-3" />;
    const label = severity === "critical" ? "ALERT" : severity === "warning" ? "NOTICE" : "INFO";
    const styles =
        severity === "critical"
            ? "bg-red-50 text-red-700 border-red-100"
            : severity === "warning"
                ? "bg-amber-50 text-amber-700 border-amber-100"
                : "bg-sky-50 text-sky-700 border-sky-100";

    return (
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${styles}`}>
            {icon}
            <span>{label}</span>
        </span>
    );
}

function InsightCard({ insight }: { insight: CompanionInsight }) {
    const styles = insightStyles[insight.severity];

    return (
        <div className={`rounded-xl border px-3 py-3 transition-all hover:shadow-md ${styles}`}>
            <div className="flex items-start justify-between gap-2">
                <div className="space-y-1.5">
                    <InsightBadge severity={insight.severity} />
                    <div className="text-sm font-semibold text-slate-900">{insight.title}</div>
                    <p className="text-xs text-slate-700 leading-relaxed">{insight.message}</p>
                </div>
                {insight.categoryLabel ? (
                    <span className="rounded-full bg-white/60 px-2 py-0.5 text-[10px] font-medium text-slate-500 border border-black/5">
                        {insight.categoryLabel}
                    </span>
                ) : null}
            </div>
        </div>
    );
}

function TaskCard({ task, onPrimary, onSecondary }: { task: CompanionTask; onPrimary?: () => void; onSecondary?: () => void }) {
    const severity = task.severity;
    const severityLabel = severityLabels[severity];
    const severityClass = severityStyles[severity];

    return (
        <div className="group rounded-2xl border border-slate-100 bg-white px-4 py-4 shadow-sm transition-all hover:shadow-md hover:border-slate-200 flex flex-col gap-3">
            <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${severityClass}`}>
                            {severity === "high" && <AlertTriangle className="h-3 w-3" />}
                            {severity === "medium" && <Clock className="h-3 w-3" />}
                            {severity === "low" && <CheckCircle2 className="h-3 w-3" />}
                            {severity === "info" && <Info className="h-3 w-3" />}
                            <span>{severityLabel}</span>
                        </span>
                        {task.categoryLabel ? (
                            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                {task.categoryLabel}
                            </span>
                        ) : null}
                        {task.confidenceLabel ? (
                            <span className="rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                                {task.confidenceLabel}
                            </span>
                        ) : null}
                    </div>
                    <div>
                        <div className="text-sm font-semibold text-slate-900">{task.title}</div>
                        <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{task.subtitle}</p>
                    </div>
                </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-1">
                {onPrimary && (
                    <button
                        type="button"
                        onClick={onPrimary}
                        className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800 transition active:scale-95"
                    >
                        {task.ctaLabel ?? "Review"}
                    </button>
                )}
                {onSecondary && (
                    <button
                        type="button"
                        onClick={onSecondary}
                        className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition active:scale-95"
                    >
                        {task.secondaryLabel ?? "Dismiss"}
                    </button>
                )}
            </div>
        </div>
    );
}

// -----------------------------------------------------------------------------
// Main Component: DashboardCompanionPanel
// -----------------------------------------------------------------------------

export function DashboardCompanionPanel(props: DashboardCompanionPanelProps) {
    const {
        greetingName,
        headline = "Financial Health Dashboard",
        aiSummary,
        breakdown,
        insights,
        tasks,
        onTaskPrimary,
        onTaskSecondary,
        onOpenFullCompanion,
    } = props;

    const [activeFilter, setActiveFilter] = useState<CompanionTaskSeverity | "all">("all");

    const filteredTasks = useMemo(() => {
        const sorted = [...tasks].sort((a, b) => severitySortOrder.indexOf(a.severity) - severitySortOrder.indexOf(b.severity));
        if (activeFilter === "all") return sorted;
        return sorted.filter((t) => t.severity === activeFilter);
    }, [tasks, activeFilter]);

    const greeting = useMemo(() => {
        const hour = new Date().getHours();
        let base = "Hello";
        if (hour < 12) base = "Good morning";
        else if (hour < 18) base = "Good afternoon";
        else base = "Good evening";
        return greetingName ? `${base}, ${greetingName}` : base;
    }, [greetingName]);

    const summaryCopy = useMemo(() => {
        if (aiSummary) return aiSummary;
        if (tasks.length > 0) {
            const issueLabel = tasks.length === 1 ? "issue" : "issues";
            const pronoun = tasks.length === 1 ? "it" : "them";
            return `You have ${tasks.length} open ${issueLabel} in your books — let's tackle ${pronoun} to get back on track.`;
        }
        return "Everything looks on track — keep reconciling regularly.";
    }, [aiSummary, tasks.length]);

    const summaryHint = "Stay on top of reconciliation for best results.";

    return (
        <section className="relative rounded-[2.5rem] bg-gradient-to-br from-white via-slate-50 to-slate-100 p-1 ring-1 ring-slate-200/60 shadow-[0_0_60px_-15px_rgba(99,102,241,0.25),0_0_30px_-10px_rgba(59,130,246,0.15)] font-sans">
            <div className="relative z-10 rounded-[2.2rem] border border-white/60 bg-white/90 px-6 py-6 sm:px-8 sm:py-8">
                <div className="flex flex-col gap-8">

                    {/* Header */}
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="space-y-1">
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Companion</span>
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-emerald-700">
                                    <Sparkles className="h-2.5 w-2.5" />
                                    Live
                                </span>
                            </div>

                            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{headline}</h2>
                            <p className="text-sm text-slate-500 max-w-2xl leading-relaxed">
                                {greeting}. We're monitoring your reconciliation, invoices, expenses, tax, and bank health in real-time.
                            </p>
                        </div>

                        {onOpenFullCompanion && (
                            <button
                                type="button"
                                onClick={onOpenFullCompanion}
                                className="group inline-flex items-center justify-center gap-1 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 hover:text-slate-900 transition-all"
                            >
                                Explore Insights
                                <ChevronRight className="h-3 w-3 text-slate-400 group-hover:text-slate-600 transition-colors" />
                            </button>
                        )}
                    </div>

                    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.8fr)_minmax(0,1.2fr)]">

                        {/* Left Column: Breakdown & Summary */}
                        <div className="flex flex-col gap-6">
                            {/* Summary Card */}
                            <div className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50/50 to-white p-6 shadow-sm">
                                <div className="flex items-start gap-4">
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg shadow-slate-300">
                                        <Sparkles className="h-5 w-5" />
                                    </div>
                                    <div className="space-y-1">
                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-400">Intelligent Summary</div>
                                        <p className="text-sm leading-relaxed text-slate-700 font-medium">
                                            {summaryCopy}
                                        </p>
                                        <p className="text-xs text-slate-500">
                                            {summaryHint}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Breakdown Bars */}
                            <div className="rounded-3xl border border-slate-100 bg-slate-50/50 p-6">
                                <div className="mb-4 flex items-center justify-between">
                                    <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Performance Metrics</span>
                                    <span className="text-[10px] font-medium text-slate-400 bg-white px-2 py-1 rounded-full shadow-sm">
                                        Snapshot: {breakdown.dateLabel}
                                    </span>
                                </div>
                                <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
                                    <div className="space-y-3">
                                        <BreakdownRow label="Reconciliation" value={breakdown.reconciliation} tone="primary" />
                                        <BreakdownRow label="Ledger Integrity" value={breakdown.ledgerIntegrity} />
                                        <BreakdownRow label="Invoices" value={breakdown.invoices} />
                                    </div>
                                    <div className="space-y-3">
                                        <BreakdownRow label="Expenses" value={breakdown.expenses} />
                                        <BreakdownRow label="Tax Compliance" value={breakdown.taxFx} />
                                        <BreakdownRow label="Bank Feeds" value={breakdown.bank} />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Right Column: Insights & Tasks */}
                        <div className="flex flex-col gap-4">

                            {/* Filter Tabs */}
                            <div className="flex items-center justify-between">
                                <div className="text-xs font-bold uppercase tracking-widest text-slate-400">Requires Attention</div>
                                <div className="flex rounded-lg bg-slate-100 p-0.5">
                                    {["all", "high"].map((sev) => (
                                        <button
                                            key={sev}
                                            onClick={() => setActiveFilter(sev as CompanionTaskSeverity | "all")}
                                            className={`rounded-md px-2.5 py-1 text-[10px] font-bold uppercase transition-all ${activeFilter === sev ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                                                }`}
                                        >
                                            {sev.toUpperCase()}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Scrollable Area */}
                            <div className="flex flex-col gap-3 max-h-[400px] overflow-y-auto pr-2 -mr-2 custom-scrollbar">
                                {/* Render Insights First if critical */}
                                {insights.filter(i => i.severity === 'critical').map(insight => (
                                    <InsightCard key={insight.id} insight={insight} />
                                ))}

                                {/* Render Tasks */}
                                {filteredTasks.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 py-10 text-center">
                                        <CheckCircle2 className="mb-2 h-6 w-6 text-slate-300" />
                                        <p className="text-xs font-medium text-slate-500">No active tasks in this view.</p>
                                    </div>
                                ) : (
                                    filteredTasks.map((task) => (
                                        <TaskCard
                                            key={task.id}
                                            task={task}
                                            onPrimary={onTaskPrimary ? () => onTaskPrimary(task.id) : undefined}
                                            onSecondary={onTaskSecondary ? () => onTaskSecondary(task.id) : undefined}
                                        />
                                    ))
                                )}

                                {/* Render remaining insights */}
                                {insights.filter(i => i.severity !== 'critical').map(insight => (
                                    <InsightCard key={insight.id} insight={insight} />
                                ))}
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        </section>
    );
}

export default DashboardCompanionPanel;
