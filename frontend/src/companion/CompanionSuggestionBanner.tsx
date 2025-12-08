import React from "react";
import { AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";

// -----------------------------------------------------------------------------
// TYPES
// -----------------------------------------------------------------------------

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type FocusMode = "all_clear" | "watchlist" | "fire_drill";

export interface CompanionSuggestion {
    id: string;
    label: string;
}

export interface CompanionSuggestionBannerProps {
    userName?: string | null;
    riskLevel: RiskLevel;
    sentimentLabel: string; // e.g. "Needs attention", "All good", "Critical"
    toneSubtitle: string; // short secondary line matching risk
    suggestions: CompanionSuggestion[];
    onViewMore?: () => void;
    isLoading?: boolean;
    // New voice fields from backend
    greeting?: string;          // Backend-provided greeting
    focusMode?: FocusMode;      // Backend-provided focus mode
    primaryCTA?: string | null; // Backend-provided call to action
}

// -----------------------------------------------------------------------------
// STYLES
// -----------------------------------------------------------------------------

const riskStyles: Record<RiskLevel, {
    label: string;
    badgeClass: string;
    dotClass: string;
    iconColor: string;
}> = {
    low: {
        label: "Low risk",
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
        dotClass: "bg-emerald-500",
        iconColor: "text-emerald-500",
    },
    medium: {
        label: "Needs attention",
        badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
        dotClass: "bg-amber-500",
        iconColor: "text-amber-500",
    },
    high: {
        label: "High risk",
        badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
        dotClass: "bg-rose-500",
        iconColor: "text-rose-500",
    },
    critical: {
        label: "Critical",
        badgeClass: "bg-rose-100 text-rose-800 border-rose-300",
        dotClass: "bg-rose-600",
        iconColor: "text-rose-600",
    },
};

// Focus mode styles for the pill
const focusModeStyles: Record<FocusMode, {
    label: string;
    badgeClass: string;
    dotClass: string;
}> = {
    all_clear: {
        label: "All clear",
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
        dotClass: "bg-emerald-500",
    },
    watchlist: {
        label: "Worth reviewing",
        badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
        dotClass: "bg-amber-500",
    },
    fire_drill: {
        label: "Needs attention",
        badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
        dotClass: "bg-rose-500",
    },
};

// -----------------------------------------------------------------------------
// HELPER: Get time-aware greeting
// -----------------------------------------------------------------------------

function getTimeOfDay(): "morning" | "afternoon" | "evening" {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return "morning";
    if (hour >= 12 && hour < 17) return "afternoon";
    return "evening";
}

function getGreeting(userName?: string | null): string {
    const tod = getTimeOfDay();
    const timeGreeting = `Good ${tod}`;
    return userName ? `${timeGreeting}, ${userName}` : timeGreeting;
}

// -----------------------------------------------------------------------------
// LOADING STATE
// -----------------------------------------------------------------------------

const LoadingSkeleton: React.FC = () => (
    <section className="companion-glow-inner w-full overflow-hidden">
        <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between bg-gradient-to-b from-white to-slate-50/50">
            <div className="flex flex-1 items-start gap-4">
                <div className="space-y-2 flex-1">
                    <div className="h-4 w-64 animate-pulse rounded-full bg-slate-100" />
                    <div className="h-3 w-48 animate-pulse rounded-full bg-slate-100" />
                </div>
            </div>
            <div className="h-7 w-24 animate-pulse rounded-full bg-slate-100" />
        </div>
    </section>
);

// -----------------------------------------------------------------------------
// MAIN COMPONENT
// -----------------------------------------------------------------------------

export const CompanionSuggestionBanner: React.FC<CompanionSuggestionBannerProps> = ({
    userName,
    riskLevel,
    sentimentLabel,
    toneSubtitle,
    suggestions,
    onViewMore,
    isLoading = false,
    // New voice fields
    greeting: backendGreeting,
    focusMode,
    primaryCTA,
}) => {
    if (isLoading) {
        return <LoadingSkeleton />;
    }

    const risk = riskStyles[riskLevel] || riskStyles.low;
    const focus = focusMode ? focusModeStyles[focusMode] : null;

    // Prefer backend greeting, fallback to computed
    const displayGreeting = backendGreeting || getGreeting(userName);

    // Use focus mode styling if available, otherwise use risk styling
    const badgeStyle = focus || risk;
    const badgeLabel = focus?.label || sentimentLabel || risk.label;

    return (
        <section className="companion-glow-inner w-full overflow-hidden">
            <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between bg-gradient-to-b from-white to-slate-50/50">
                {/* Left: Greeting + sentiment */}
                <div className="flex flex-1 items-start gap-4">
                    <div className="space-y-1 flex-1">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                            <p className="text-sm font-medium text-slate-900">
                                {displayGreeting}
                            </p>

                            <span
                                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeStyle.badgeClass}`}
                            >
                                <span className={`h-1.5 w-1.5 rounded-full ${badgeStyle.dotClass}`} />
                                {badgeLabel}
                            </span>
                        </div>

                        <div className="text-xs text-slate-600 flex items-center gap-1.5">
                            {focusMode === "all_clear" || riskLevel === "low" ? (
                                <CheckCircle2 className={`h-3.5 w-3.5 ${risk.iconColor}`} />
                            ) : (
                                <AlertTriangle className={`h-3.5 w-3.5 ${risk.iconColor}`} />
                            )}
                            <span>{toneSubtitle}</span>
                        </div>

                        {/* Primary CTA from backend */}
                        {primaryCTA && (
                            <div className="mt-2 text-sm text-slate-700 font-medium">
                                • {primaryCTA}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: View button */}
                <div className="mt-2 shrink-0 sm:mt-0 flex items-center gap-3">
                    {suggestions.length > 0 && (
                        <div className="hidden sm:flex items-center rounded-full bg-white border border-slate-200 px-3 py-1 text-xs text-slate-600 shadow-sm">
                            <Sparkles className="mr-1.5 h-3.5 w-3.5 text-sky-500" />
                            {suggestions.length === 1 ? "1 suggested action" : `${suggestions.length} suggested actions`}
                        </div>
                    )}

                    <button
                        type="button"
                        onClick={onViewMore}
                        className="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-colors shadow-sm"
                    >
                        View details
                    </button>
                </div>
            </div>

            {/* Divider */}
            {suggestions.length > 0 && <div className="h-px w-full bg-slate-200/80" />}

            {/* Suggestions list */}
            {suggestions.length > 0 && (
                <div className="px-5 pb-4 pt-3 bg-slate-50/80">
                    <ul className="flex flex-wrap gap-3 text-xs text-slate-700">
                        {suggestions.slice(0, 3).map((item) => (
                            <li
                                key={item.id}
                                className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 shadow-sm border border-slate-200"
                            >
                                <span className="flex h-3 w-3 items-center justify-center rounded-full border border-slate-400/60 text-[0.5rem] text-slate-500">
                                    !
                                </span>
                                <span>{item.label}</span>
                            </li>
                        ))}
                        {suggestions.length > 3 && (
                            <li className="inline-flex items-center text-slate-500 px-2">
                                + {suggestions.length - 3} more in Companion panel
                            </li>
                        )}
                    </ul>
                </div>
            )}
        </section>
    );
};

export default CompanionSuggestionBanner;
