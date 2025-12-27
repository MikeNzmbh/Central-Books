import React, { useState, useEffect } from "react";
import { RefreshCw, Check, Clock, AlertTriangle, ChevronRight, ExternalLink, CheckCircle2 } from "lucide-react";
import { getSeverityLabel, getSeverityColors, ACTION_LABELS, toCustomerCopy, getEmptyState } from "./companionCopy";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface CloseReadiness {
    score: number;
    status: "ready" | "not_ready";
    blockers: number;
    warnings: number;
}

interface CloseItem {
    id: number;
    title: string;
    severity: "high" | "medium" | "low";
    domain: string;
    status: "open" | "applied" | "dismissed" | "snoozed";
    actionable: boolean;
    target_url?: string;
    action_kind?: "apply" | "review" | "link";
}

interface CloseData {
    period_key?: string;
    readiness?: CloseReadiness;
    items?: CloseItem[];
}

// ─────────────────────────────────────────────────────────────────────────────
// CloseAssistantDrawer Component
// ─────────────────────────────────────────────────────────────────────────────

export const CloseAssistantDrawer: React.FC = () => {
    const [data, setData] = useState<CloseData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [processingId, setProcessingId] = useState<number | null>(null);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch("/api/agentic/close/", {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!res.ok) throw new Error("Failed to load close data");
            const json = await res.json();
            setData({
                period_key: json.session?.period_key,
                readiness: json.readiness,
                items: (json.issues || []).filter((i: any) => i.status === "open"),
            });
        } catch (err: any) {
            setError(err.message || "Failed to load");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleItemAction = async (item: CloseItem, action: "apply" | "dismiss") => {
        setProcessingId(item.id);
        try {
            const endpoint = action === "apply"
                ? `/api/agentic/close/issues/${item.id}/apply/`
                : `/api/agentic/close/issues/${item.id}/dismiss/`;
            const res = await fetch(endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
            });
            if (!res.ok) throw new Error(`Failed to ${action}`);
            // Refresh data
            await loadData();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setProcessingId(null);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <RefreshCw className="w-5 h-5 animate-spin text-slate-400" />
                <span className="ml-2 text-sm text-slate-500">Loading close assistant...</span>
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

    const items = data?.items || [];
    const readiness = data?.readiness;

    if (items.length === 0 && readiness?.status === "ready") {
        return (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                <div className="w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center mb-4">
                    <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 mb-1">Ready to close!</h3>
                <p className="text-slate-600">All items have been reviewed for this period.</p>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            {/* Period header */}
            {data?.period_key && (
                <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Clock className="w-4 h-4" />
                    <span>Period: <span className="font-medium text-slate-700">{data.period_key}</span></span>
                </div>
            )}

            {/* Readiness summary */}
            {readiness && (
                <div className={`rounded-xl p-4 border ${readiness.status === "ready"
                        ? "bg-emerald-50 border-emerald-200"
                        : "bg-slate-100 border-slate-200"
                    }`}>
                    <div className="flex items-center justify-between mb-2">
                        <span className={`text-sm font-semibold ${readiness.status === "ready" ? "text-emerald-700" : "text-slate-700"
                            }`}>
                            {readiness.status === "ready" ? "Close-ready" : "Not close-ready"}
                        </span>
                        <span className={`text-2xl font-bold ${readiness.score >= 80 ? "text-emerald-600" :
                                readiness.score >= 50 ? "text-slate-700" : "text-rose-600"
                            }`}>
                            {readiness.score}%
                        </span>
                    </div>
                    <div className="h-2 rounded-full bg-white/60 overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all ${readiness.score >= 80 ? "bg-emerald-500" :
                                    readiness.score >= 50 ? "bg-slate-500" : "bg-rose-500"
                                }`}
                            style={{ width: `${readiness.score}%` }}
                        />
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-xs">
                        {readiness.blockers > 0 && (
                            <span className="text-rose-600 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                {readiness.blockers} blocker{readiness.blockers !== 1 ? "s" : ""}
                            </span>
                        )}
                        {readiness.warnings > 0 && (
                            <span className="text-slate-600">
                                {readiness.warnings} warning{readiness.warnings !== 1 ? "s" : ""}
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* Checklist */}
            {items.length > 0 && (
                <section>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
                        Items to review ({items.length})
                    </h3>
                    <div className="space-y-2">
                        {items.map((item) => {
                            const colors = getSeverityColors(item.severity);
                            const isProcessing = processingId === item.id;

                            return (
                                <div
                                    key={item.id}
                                    className={`rounded-lg border p-3 ${colors.border} bg-white hover:shadow-sm transition-shadow`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${colors.bg} ${colors.text}`}>
                                                    {getSeverityLabel(item.severity)}
                                                </span>
                                                <span className="text-[10px] uppercase text-slate-400">{item.domain}</span>
                                            </div>
                                            <p className="font-medium text-slate-900 text-sm">
                                                {toCustomerCopy(item.title)}
                                            </p>
                                        </div>
                                        {item.target_url && (
                                            <a
                                                href={item.target_url}
                                                className="shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50"
                                            >
                                                <ExternalLink className="w-4 h-4" />
                                            </a>
                                        )}
                                    </div>

                                    {/* Actions */}
                                    {item.actionable && (
                                        <div className="flex items-center gap-2 mt-3">
                                            {item.action_kind === "apply" && (
                                                <button
                                                    onClick={() => handleItemAction(item, "apply")}
                                                    disabled={isProcessing}
                                                    className="px-2.5 py-1 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-1"
                                                >
                                                    <Check className="w-3 h-3" />
                                                    {isProcessing ? "..." : ACTION_LABELS.apply}
                                                </button>
                                            )}
                                            {item.action_kind === "review" && item.target_url && (
                                                <a
                                                    href={item.target_url}
                                                    className="px-2.5 py-1 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 flex items-center gap-1"
                                                >
                                                    <ChevronRight className="w-3 h-3" />
                                                    {ACTION_LABELS.review}
                                                </a>
                                            )}
                                            <button
                                                onClick={() => handleItemAction(item, "dismiss")}
                                                disabled={isProcessing}
                                                className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 text-xs font-medium hover:bg-slate-200 disabled:opacity-50"
                                            >
                                                {ACTION_LABELS.dismiss}
                                            </button>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

            {items.length === 0 && (
                <div className="text-center py-8 text-slate-500 text-sm">
                    {getEmptyState("close")}
                </div>
            )}
        </div>
    );
};

export default CloseAssistantDrawer;
