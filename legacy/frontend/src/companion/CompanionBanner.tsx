/**
 * CompanionBanner - Smart AI Companion banner for each surface
 * 
 * Uses radar, coverage, and playbook data to display personalized
 * status and guidance per surface.
 */
import React, { useMemo } from "react";
import { Sparkles, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useCompanionSummary, type CompanionSummary, type FocusMode } from "./useCompanionSummary";
import { useAuth } from "../contexts/AuthContext";

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

export type BannerSurface = "receipts" | "invoices" | "books" | "bank" | "banking";

export type BannerStatus = "all_clear" | "watchlist" | "fire_drill" | "unavailable";

export interface BannerViewModel {
    greeting: string;
    headline: string;
    subtitle: string;
    status: BannerStatus;
    statusLabel: string;
    isLlmSubtitle: boolean;  // true if subtitle came from DeepSeek
}

export interface CompanionBannerProps {
    surface: BannerSurface;
    className?: string;
    onViewMore?: () => void;
}

// ---------------------------------------------------------------------------
// CONSTANTS
// ---------------------------------------------------------------------------

// Surface to radar axis mapping
const SURFACE_TO_RADAR_AXIS: Record<BannerSurface, keyof NonNullable<CompanionSummary["radar"]>> = {
    receipts: "expenses_receipts",
    invoices: "revenue_invoices",
    books: "tax_compliance",
    bank: "cash_reconciliation",
    banking: "cash_reconciliation",
};

// Surface to coverage domain mapping
const SURFACE_TO_COVERAGE_DOMAIN: Record<BannerSurface, keyof NonNullable<CompanionSummary["coverage"]>> = {
    receipts: "receipts",
    invoices: "invoices",
    books: "books",
    bank: "banking",
    banking: "banking",
};

// Status pill styling
const STATUS_STYLES: Record<BannerStatus, {
    label: string;
    badgeClass: string;
    dotClass: string;
}> = {
    all_clear: {
        label: "On track",
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
        dotClass: "bg-emerald-500",
    },
    watchlist: {
        label: "Needs attention",
        badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
        dotClass: "bg-amber-500",
    },
    fire_drill: {
        label: "Action required",
        badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
        dotClass: "bg-rose-500",
    },
    unavailable: {
        label: "Companion temporarily unavailable",
        badgeClass: "bg-slate-50 text-slate-500 border-slate-200",
        dotClass: "bg-slate-400",
    },
};

// Headline templates per surface and status
const HEADLINES: Record<BannerSurface, Record<BannerStatus, string>> = {
    receipts: {
        all_clear: "Your recent receipts look tidy — nothing high-risk is showing up.",
        watchlist: "A few receipts need a second look — mostly about categories.",
        fire_drill: "Several receipts are blocking clean books — let's clear those next.",
        unavailable: "Here's what your Companion will suggest as soon as it's back online.",
    },
    invoices: {
        all_clear: "Your invoices look steady — most of your billed revenue is on track.",
        watchlist: "You've got a few invoices to keep an eye on — some are drifting past due.",
        fire_drill: "There are invoices that need your attention — overdue items are building up.",
        unavailable: "Here's what your Companion will suggest as soon as it's back online.",
    },
    books: {
        all_clear: "Your books for this period look solid — nothing critical is standing out.",
        watchlist: "Your books are mostly fine, but there are a few items worth reviewing.",
        fire_drill: "There are issues in your books that could affect tax or reporting — let's handle those soon.",
        unavailable: "Here's what your Companion will suggest as soon as it's back online.",
    },
    bank: {
        all_clear: "Your bank feeds look calm — cash and books are lining up well.",
        watchlist: "Some bank transactions still need review — your cash picture isn't fully locked in.",
        fire_drill: "Your cash view is fuzzy — unreconciled bank items are piling up.",
        unavailable: "Here's what your Companion will suggest as soon as it's back online.",
    },
    banking: {
        all_clear: "Your bank feeds look calm — cash and books are lining up well.",
        watchlist: "Some bank transactions still need review — your cash picture isn't fully locked in.",
        fire_drill: "Your cash view is fuzzy — unreconciled bank items are piling up.",
        unavailable: "Here's what your Companion will suggest as soon as it's back online.",
    },
};

// ---------------------------------------------------------------------------
// HELPERS
// ---------------------------------------------------------------------------

/**
 * Get time-based greeting prefix
 */
function getGreetingPrefix(): "Good morning" | "Good afternoon" | "Good evening" {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return "Good morning";
    if (hour >= 12 && hour < 18) return "Good afternoon";
    return "Good evening";
}

/**
 * Build greeting with optional name
 */
function buildGreeting(firstName?: string | null): string {
    const prefix = getGreetingPrefix();
    if (firstName && firstName.trim()) {
        return `${prefix}, ${firstName.trim().split(" ")[0]}`;
    }
    return prefix;
}

/**
 * Determine status from radar score and issues
 */
function determineStatus(
    score: number | undefined,
    hasHighSeverityIssues: boolean,
    aiEnabled: boolean,
    summaryAvailable: boolean
): BannerStatus {
    if (!summaryAvailable || !aiEnabled) {
        // Still show deterministic status if we have data
        if (summaryAvailable && score !== undefined) {
            if (score >= 80 && !hasHighSeverityIssues) return "all_clear";
            if (score >= 50) return "watchlist";
            return "fire_drill";
        }
        return "unavailable";
    }

    if (score === undefined) return "unavailable";
    if (score >= 80 && !hasHighSeverityIssues) return "all_clear";
    if (score >= 50) return "watchlist";
    return "fire_drill";
}

/**
 * Build subtitle from LLM (primary) or deterministic fallback
 * Returns both the subtitle and whether it came from LLM
 */
function buildSubtitle(
    surface: BannerSurface,
    summary: CompanionSummary | null,
    status: BannerStatus
): { text: string; isLlm: boolean } {
    if (status === "unavailable") {
        return { text: "Companion will be back shortly with suggestions for this area.", isLlm: false };
    }

    // PRIMARY: Use DeepSeek-generated subtitle if available
    const llmSubtitles = summary?.llm_subtitles;
    if (llmSubtitles) {
        const surfaceKey = surface === "banking" ? "bank" : surface;
        const llmSubtitle = llmSubtitles[surfaceKey as keyof typeof llmSubtitles];
        if (llmSubtitle && llmSubtitle.trim()) {
            return { text: llmSubtitle, isLlm: true };
        }
    }

    // FALLBACK: Deterministic subtitle (only when LLM failed)
    // Check for high-severity playbook step for this surface
    const playbook = summary?.playbook || [];
    const surfaceStep = playbook.find(
        (step) => step.surface === surface ||
            (surface === "banking" && step.surface === "bank") ||
            (surface === "bank" && step.surface === "bank")
    );

    if (surfaceStep && (surfaceStep.severity === "high" || surfaceStep.severity === "medium")) {
        return { text: `Top next step: ${surfaceStep.label}`, isLlm: false };
    }

    // Fall back to coverage
    const coverageDomain = SURFACE_TO_COVERAGE_DOMAIN[surface];
    const coverage = summary?.coverage?.[coverageDomain];

    if (coverage) {
        const pct = Math.round(coverage.coverage_percent);
        if (pct >= 90) {
            return { text: `You've covered about ${pct}% of this area right now.`, isLlm: false };
        }
        if (pct >= 60) {
            return { text: `You're about ${pct}% of the way through — a bit more attention here will close the loop.`, isLlm: false };
        }
        return { text: `Coverage is still light here (~${pct}%). Spending a few minutes will make this much more reliable.`, isLlm: false };
    }

    return { text: "Companion is analyzing this area.", isLlm: false };
}

/**
 * Build the complete view model
 */
function buildViewModel(
    surface: BannerSurface,
    summary: CompanionSummary | null,
    firstName: string | undefined,
    hasError: boolean
): BannerViewModel {
    const greeting = buildGreeting(firstName);

    // If no summary or error, return fallback
    if (!summary || hasError) {
        return {
            greeting,
            headline: HEADLINES[surface].unavailable,
            subtitle: "Companion is temporarily unavailable for this area.",
            status: "unavailable",
            statusLabel: STATUS_STYLES.unavailable.label,
            isLlmSubtitle: false,
        };
    }

    // Determine status from radar
    const radarAxis = SURFACE_TO_RADAR_AXIS[surface];
    const axisData = summary.radar?.[radarAxis];
    const score = axisData?.score;
    const openIssues = axisData?.open_issues || 0;
    const hasHighSeverityIssues = openIssues > 0 && (summary.global?.open_issues_by_severity?.high || 0) > 0;

    const status = determineStatus(
        score,
        hasHighSeverityIssues,
        summary.ai_companion_enabled,
        true
    );

    const headline = HEADLINES[surface][status];
    const subtitleResult = buildSubtitle(surface, summary, status);

    return {
        greeting,
        headline,
        subtitle: subtitleResult.text,
        status,
        statusLabel: STATUS_STYLES[status].label,
        isLlmSubtitle: subtitleResult.isLlm,
    };
}

// ---------------------------------------------------------------------------
// LOADING SKELETON
// ---------------------------------------------------------------------------

const LoadingSkeleton: React.FC = () => (
    <div className="animate-pulse flex gap-4 items-center">
        <div className="h-8 w-8 rounded-full bg-blue-200/50" />
        <div className="flex-1 space-y-2">
            <div className="h-4 w-3/4 rounded bg-blue-200/50" />
            <div className="h-3 w-1/2 rounded bg-blue-200/50" />
        </div>
    </div>
);

// ---------------------------------------------------------------------------
// MAIN COMPONENT
// ---------------------------------------------------------------------------

export const CompanionBanner: React.FC<CompanionBannerProps> = ({
    surface,
    className = "",
    onViewMore,
}) => {
    const { auth } = useAuth();
    const { summary, isLoading, error } = useCompanionSummary();

    const firstName = auth?.user?.firstName;

    // Build view model
    const viewModel = useMemo(
        () => buildViewModel(surface, summary, firstName, !!error),
        [surface, summary, firstName, error]
    );

    const style = STATUS_STYLES[viewModel.status];

    // Choose icon based on status
    const StatusIcon = viewModel.status === "all_clear" ? CheckCircle2 :
        viewModel.status === "fire_drill" ? AlertTriangle :
            viewModel.status === "watchlist" ? AlertTriangle :
                Sparkles;

    const iconColor = viewModel.status === "all_clear" ? "text-emerald-500" :
        viewModel.status === "fire_drill" ? "text-rose-500" :
            viewModel.status === "watchlist" ? "text-amber-500" :
                "text-blue-500";

    return (
        <div
            className={`relative overflow-hidden rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50 via-blue-50/80 to-white px-5 py-4 shadow-sm ${className}`}
            data-testid="companion-banner"
        >
            {/* Subtle glow effect */}
            <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-blue-200/30 blur-2xl" />
            <div className="absolute -left-4 -bottom-4 h-16 w-16 rounded-full bg-blue-100/40 blur-xl" />

            <div className="relative z-10">
                {isLoading ? (
                    <LoadingSkeleton />
                ) : (
                    <div className="flex items-start gap-4">
                        {/* Icon */}
                        <div className="shrink-0 mt-0.5">
                            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-slate-100">
                                <StatusIcon className={`h-5 w-5 ${iconColor}`} />
                            </div>
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                            {/* Greeting + Status pill */}
                            <div className="flex items-center justify-between gap-3 mb-1">
                                <span className="text-sm font-medium text-slate-600">
                                    {viewModel.greeting}
                                </span>
                                <span
                                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${style.badgeClass}`}
                                >
                                    <span className={`h-1.5 w-1.5 rounded-full ${style.dotClass}`} />
                                    {viewModel.statusLabel}
                                </span>
                            </div>

                            {/* Headline */}
                            <p className="text-sm text-slate-800 leading-snug">
                                {viewModel.headline}
                            </p>

                            {/* Subtitle with source indicator */}
                            <div className="mt-1 flex items-center gap-2">
                                <p className="text-xs text-slate-500">
                                    {viewModel.subtitle}
                                </p>
                                {viewModel.status !== "unavailable" && (
                                    <span
                                        className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${viewModel.isLlmSubtitle
                                                ? "bg-purple-50 text-purple-700 border border-purple-200"
                                                : "bg-slate-50 text-slate-500 border border-slate-200"
                                            }`}
                                        title={viewModel.isLlmSubtitle ? "Generated by AI Companion" : "Calculated automatically"}
                                    >
                                        {viewModel.isLlmSubtitle ? "✨ AI" : "📊 Auto"}
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* View More button */}
                        {onViewMore && (
                            <button
                                type="button"
                                onClick={onViewMore}
                                className="shrink-0 text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
                            >
                                View details →
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default CompanionBanner;
