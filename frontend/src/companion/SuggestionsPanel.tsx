import React, { useState, useEffect, useMemo } from "react";
import { RefreshCw, Check, X, ExternalLink, AlertCircle } from "lucide-react";
import {
    getSeverityLabel,
    getSeverityColors,
    getSurfaceLabel,
    ACTION_LABELS,
    CONFIRMATION_TEMPLATES,
    getEmptyState,
    toCustomerCopy,
    formatChangePreview,
} from "./companionCopy";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface SuggestionItem {
    id: string;
    customer_title: string;
    customer_description: string;
    severity: "high" | "medium" | "low";
    surface: string;
    action_kind: "apply" | "review";
    target_url?: string;
    metadata?: Record<string, any>;
    status: "open" | "applied" | "dismissed";
    cta?: {
        label?: string;
        action_type?: string;
        payload?: Record<string, any>;
        requires_confirm?: boolean;
        risk_level?: string;
        target_url?: string;
    };
}

interface SuggestionsPanelProps {
    /** Optional surface filter */
    surface?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// SuggestionsPanel Component
// ─────────────────────────────────────────────────────────────────────────────

export const SuggestionsPanel: React.FC<SuggestionsPanelProps> = ({ surface }) => {
    const [items, setItems] = useState<SuggestionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [processingId, setProcessingId] = useState<string | null>(null);
    const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [dismissNoteId, setDismissNoteId] = useState<string | null>(null);
    const [dismissNote, setDismissNote] = useState("");
    const [activeTab, setActiveTab] = useState<"all" | "attention">("all");
    const [query, setQuery] = useState("");

    // Fetch suggestions
    const loadSuggestions = async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            if (surface) params.set("surface", surface);
            const res = await fetch(`/api/companion/v2/shadow-events/?${params}`, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!res.ok) throw new Error("Failed to load suggestions");
            const data = await res.json();
            // Map API response to our format
            const mapped: SuggestionItem[] = (data.events || data.items || []).map((e: any) => ({
                id: e.id || e.dedupe_key,
                customer_title: toCustomerCopy(e.customer_title || e.title) || "Suggested change",
                customer_description: toCustomerCopy(e.customer_description || e.description) || "",
                severity: e.risk_level || e.severity || "low",
                surface: e.surface || e.domain || "general",
                action_kind: e.customer_action_kind === "apply" ? "apply" : "review",
                target_url: e.target_url || e.cta?.target_url || e.cta?.payload?.target_url || e.cta_url,
                metadata: e.metadata || {},
                status: e.status || "open",
                cta: e.cta || null,
            }));
            setItems(mapped.filter((i) => i.status === "open"));
        } catch (err: any) {
            setError(err.message || "Failed to load");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSuggestions();
    }, [surface]);

    const attentionCount = useMemo(() => items.filter((i) => i.severity !== "low").length, [items]);
    const filteredItems = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        return items.filter((item) => {
            const needsAttention = item.severity !== "low";
            if (activeTab === "attention" && !needsAttention) return false;
            if (!normalizedQuery) return true;
            return (
                item.customer_title.toLowerCase().includes(normalizedQuery) ||
                item.customer_description.toLowerCase().includes(normalizedQuery)
            );
        });
    }, [items, activeTab, query]);

    // Group by surface
    const grouped = useMemo(() => {
        const groups: Record<string, SuggestionItem[]> = {};
        for (const item of filteredItems) {
            const key = item.surface || "general";
            if (!groups[key]) groups[key] = [];
            groups[key].push(item);
        }
        return groups;
    }, [filteredItems]);

    // Apply action
    const handleApply = async (item: SuggestionItem) => {
        setProcessingId(item.id);
        try {
            const res = await fetch(`/api/companion/v2/shadow-events/${item.id}/apply/`, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
            });
            if (!res.ok) throw new Error("Failed to apply");
            setItems((prev) => prev.filter((i) => i.id !== item.id));
            setToast({ type: "success", message: CONFIRMATION_TEMPLATES.applySuccess });
            setConfirmingId(null);
        } catch (err: any) {
            setToast({ type: "error", message: err.message || CONFIRMATION_TEMPLATES.applyError });
        } finally {
            setProcessingId(null);
        }
    };

    // Dismiss action
    const handleDismiss = async (item: SuggestionItem, note?: string) => {
        // High severity requires note
        if (item.severity === "high" && !note) {
            setDismissNoteId(item.id);
            return;
        }
        setProcessingId(item.id);
        try {
            const res = await fetch(`/api/companion/v2/shadow-events/${item.id}/reject/`, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reason: note || "Dismissed by user" }),
            });
            if (!res.ok) throw new Error("Failed to dismiss");
            setItems((prev) => prev.filter((i) => i.id !== item.id));
            setToast({ type: "success", message: CONFIRMATION_TEMPLATES.dismissSuccess });
            setDismissNoteId(null);
            setDismissNote("");
        } catch (err: any) {
            setToast({ type: "error", message: err.message });
        } finally {
            setProcessingId(null);
        }
    };

    // Clear toast after 4s
    useEffect(() => {
        if (toast) {
            const timer = setTimeout(() => setToast(null), 4000);
            return () => clearTimeout(timer);
        }
    }, [toast]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <RefreshCw className="w-5 h-5 animate-spin text-slate-400" />
                <span className="ml-2 text-sm text-slate-500">Loading suggestions...</span>
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

    if (items.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mb-3">
                    <Check className="w-6 h-6 text-emerald-500" />
                </div>
                <p className="text-slate-600">{getEmptyState("suggestions")}</p>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            {/* Toast */}
            {toast && (
                <div
                    className={`fixed top-4 right-4 z-[60] px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${toast.type === "success"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                >
                    {toast.message}
                </div>
            )}

            {/* Controls */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
                    <button
                        onClick={() => setActiveTab("all")}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-md ${activeTab === "all"
                            ? "bg-slate-900 text-white"
                            : "text-slate-600 hover:text-slate-800"
                            }`}
                    >
                        All ({items.length})
                    </button>
                    <button
                        onClick={() => setActiveTab("attention")}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-md ${activeTab === "attention"
                            ? "bg-slate-900 text-white"
                            : "text-slate-600 hover:text-slate-800"
                            }`}
                    >
                        Needs attention ({attentionCount})
                    </button>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                    <label className="flex items-center gap-2 text-xs text-slate-500">
                        <input
                            type="checkbox"
                            checked={activeTab === "attention"}
                            onChange={() => setActiveTab(activeTab === "attention" ? "all" : "attention")}
                            className="rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                        />
                        Only show items needing attention
                    </label>
                    <input
                        type="search"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search suggestions"
                        className="w-full sm:w-64 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900/20"
                    />
                </div>
            </div>

            {filteredItems.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-500 text-center">
                    No items match your filters.
                </div>
            ) : (
                Object.entries(grouped).map(([surfaceKey, surfaceItems]) => (
                <section key={surfaceKey}>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
                        {getSurfaceLabel(surfaceKey)} ({surfaceItems.length})
                    </h3>
                    <div className="space-y-3">
                        {surfaceItems.map((item) => {
                            const colors = getSeverityColors(item.severity);
                            const isProcessing = processingId === item.id;
                            const isConfirming = confirmingId === item.id;
                            const isDismissing = dismissNoteId === item.id;

                            return (
                                <div
                                    key={item.id}
                                    className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
                                >
                                    {/* Header */}
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span
                                                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${colors.bg} ${colors.text} ${colors.border}`}
                                                >
                                                    {getSeverityLabel(item.severity)}
                                                </span>
                                            </div>
                                            <h4 className="font-medium text-slate-900">{item.customer_title}</h4>
                                            {item.customer_description && (
                                                <p className="text-sm text-slate-600 mt-1">{item.customer_description}</p>
                                            )}
                                        </div>
                                    </div>

                                    {/* Confirmation dialog */}
                                    {isConfirming && (
                                        <div className="mt-4 p-3 rounded-lg bg-slate-50 border border-slate-200">
                                            <p className="text-sm font-semibold text-slate-900 mb-1">Apply this change</p>
                                            <p className="text-xs text-slate-500 mb-2">What this will do:</p>
                                            {(() => {
                                                const preview = formatChangePreview(item.customer_title, item.metadata);
                                                const details = preview.details.length > 0 ? preview.details : ["Update this item in your books."];
                                                return (
                                                    <ul className="text-sm text-slate-600 space-y-1 mb-3">
                                                        {details.map((detail, idx) => (
                                                            <li key={idx}>• {detail}</li>
                                                        ))}
                                                    </ul>
                                                );
                                            })()}
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleApply(item)}
                                                    disabled={isProcessing}
                                                    className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
                                                >
                                                    {isProcessing ? "Applying..." : ACTION_LABELS.apply}
                                                </button>
                                                <button
                                                    onClick={() => setConfirmingId(null)}
                                                    className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Dismiss note dialog (for high severity) */}
                                    {isDismissing && (
                                        <div className="mt-4 p-3 rounded-lg bg-slate-50 border border-slate-200">
                                            <p className="text-sm font-medium text-slate-700 mb-2">
                                                Please provide a reason for dismissing:
                                            </p>
                                            <textarea
                                                value={dismissNote}
                                                onChange={(e) => setDismissNote(e.target.value)}
                                                placeholder="Why are you dismissing this suggestion?"
                                                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                rows={2}
                                            />
                                            <div className="flex gap-2 mt-2">
                                                <button
                                                    onClick={() => handleDismiss(item, dismissNote)}
                                                    disabled={!dismissNote.trim() || isProcessing}
                                                    className="px-3 py-1.5 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
                                                >
                                                    {isProcessing ? "Dismissing..." : "Dismiss"}
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setDismissNoteId(null);
                                                        setDismissNote("");
                                                    }}
                                                    className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Actions */}
                                    {!isConfirming && !isDismissing && (
                                        <div className="flex items-center gap-2 mt-4">
                                            {item.action_kind === "apply" && (
                                                <button
                                                    onClick={() => setConfirmingId(item.id)}
                                                    disabled={isProcessing}
                                                    className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-1.5"
                                                >
                                                    <Check className="w-3.5 h-3.5" />
                                                    {ACTION_LABELS.apply}
                                                </button>
                                            )}
                                            {item.action_kind === "review" && item.target_url && (
                                                <a
                                                    href={item.target_url}
                                                    className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 flex items-center gap-1.5"
                                                >
                                                    <ExternalLink className="w-3.5 h-3.5" />
                                                    {ACTION_LABELS.review}
                                                </a>
                                            )}
                                            {item.action_kind === "review" && !item.target_url && (
                                                <span
                                                    className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-400 text-sm font-medium flex items-center gap-1.5 cursor-not-allowed"
                                                    title="Link not available yet"
                                                >
                                                    <AlertCircle className="w-3.5 h-3.5" />
                                                    {ACTION_LABELS.review}
                                                </span>
                                            )}
                                            <button
                                                onClick={() => handleDismiss(item)}
                                                disabled={isProcessing}
                                                className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 text-sm font-medium hover:bg-slate-200 disabled:opacity-50 flex items-center gap-1.5"
                                            >
                                                <X className="w-3.5 h-3.5" />
                                                {ACTION_LABELS.dismiss}
                                            </button>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </section>
                ))
            )}
        </div>
    );
};

export default SuggestionsPanel;
