import React, { useState, useEffect, useMemo } from "react";
import { RefreshCw, Check, AlertTriangle, AlertCircle, Info } from "lucide-react";
import { getSeverityLabel, getSeverityColors, getSurfaceLabel, getEmptyState, toCustomerCopy, ACTION_LABELS } from "./companionCopy";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Issue {
    id: number;
    title: string;
    severity: "high" | "medium" | "low";
    surface: string;
    recommended_action?: string;
    target_url?: string;
    created_at?: string;
}

interface IssuesPanelProps {
    /** Optional surface filter */
    surface?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// IssuesPanel Component
// ─────────────────────────────────────────────────────────────────────────────

export const IssuesPanel: React.FC<IssuesPanelProps> = ({ surface }) => {
    const [issues, setIssues] = useState<Issue[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadIssues = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({ status: "open" });
            if (surface) params.set("surface", surface);
            const res = await fetch(`/api/agentic/companion/issues?${params}`, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!res.ok) throw new Error("Failed to load issues");
            const data = await res.json();
            setIssues(data.issues || []);
        } catch (err: any) {
            setError(err.message || "Failed to load");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadIssues();
    }, [surface]);

    // Sort by severity (high first)
    const sortedIssues = useMemo(() => {
        const severityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
        return [...issues].sort(
            (a, b) => (severityOrder[a.severity] ?? 3) - (severityOrder[b.severity] ?? 3)
        );
    }, [issues]);

    // Group by severity
    const grouped = useMemo(() => {
        const groups: Record<string, Issue[]> = { high: [], medium: [], low: [] };
        for (const issue of sortedIssues) {
            const key = issue.severity || "low";
            if (!groups[key]) groups[key] = [];
            groups[key].push(issue);
        }
        return groups;
    }, [sortedIssues]);

    const severityIcons: Record<string, React.ReactNode> = {
        high: <AlertTriangle className="w-4 h-4 text-rose-500" />,
        medium: <AlertCircle className="w-4 h-4 text-slate-500" />,
        low: <Info className="w-4 h-4 text-slate-400" />,
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <RefreshCw className="w-5 h-5 animate-spin text-slate-400" />
                <span className="ml-2 text-sm text-slate-500">Loading issues...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6">
                <div className="rounded-lg bg-rose-50 border border-rose-200 p-4 text-rose-700 text-sm">
                    {error}
                </div>
            </div>
        );
    }

    if (issues.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mb-3">
                    <Check className="w-6 h-6 text-emerald-500" />
                </div>
                <p className="text-slate-600">{getEmptyState("issues")}</p>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            {/* Summary bar */}
            <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-500">{issues.length} open issues</span>
                {grouped.high.length > 0 && (
                    <span className="flex items-center gap-1 text-rose-600">
                        <span className="w-2 h-2 rounded-full bg-rose-500" />
                        {grouped.high.length} needs attention
                    </span>
                )}
            </div>

            {/* Issues by severity */}
            {(["high", "medium", "low"] as const).map((severity) => {
                const items = grouped[severity];
                if (items.length === 0) return null;

                const colors = getSeverityColors(severity);

                return (
                    <section key={severity}>
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3 flex items-center gap-2">
                            {severityIcons[severity]}
                            {getSeverityLabel(severity)} ({items.length})
                        </h3>
                        <div className="space-y-2">
                            {items.map((issue) => (
                                <div
                                    key={issue.id}
                                    className={`rounded-lg border p-3 ${colors.border} ${colors.bg} hover:shadow-sm transition-shadow`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                            <p className={`font-medium ${colors.text}`}>
                                                {toCustomerCopy(issue.title)}
                                            </p>
                                            {issue.recommended_action && (
                                                <p className="text-xs text-slate-500 mt-1">
                                                    {toCustomerCopy(issue.recommended_action)}
                                                </p>
                                            )}
                                            <div className="flex items-center gap-2 mt-2 text-[10px] text-slate-400">
                                                <span className="uppercase">{getSurfaceLabel(issue.surface)}</span>
                                                {issue.created_at && (
                                                    <>
                                                        <span>•</span>
                                                        <span>{new Date(issue.created_at).toLocaleDateString()}</span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        {issue.target_url ? (
                                            <a
                                                href={issue.target_url}
                                                className="shrink-0 px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-xs text-slate-600 hover:bg-slate-50"
                                            >
                                                {ACTION_LABELS.review}
                                            </a>
                                        ) : (
                                            <span
                                                className="shrink-0 px-2.5 py-1 rounded-lg bg-slate-100 text-xs text-slate-400 cursor-not-allowed"
                                                title="Link not available yet"
                                            >
                                                {ACTION_LABELS.review}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </section>
                );
            })}
        </div>
    );
};

export default IssuesPanel;
