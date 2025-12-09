/**
 * Companion Summary Hook
 * 
 * Centralized hook for fetching /api/agentic/companion/summary
 * Provides caching and error handling to avoid duplicate fetches
 */
import { useState, useEffect, useCallback } from "react";
import { parseCookies } from "../utils/cookies";

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

export type FocusMode = "all_clear" | "watchlist" | "fire_drill";

export interface CompanionRadarAxis {
    score: number;
    open_issues: number;
}

export interface CompanionRadar {
    cash_reconciliation: CompanionRadarAxis;
    revenue_invoices: CompanionRadarAxis;
    expenses_receipts: CompanionRadarAxis;
    tax_compliance: CompanionRadarAxis;
}

export interface CompanionCoverageAxis {
    coverage_percent: number;
    total_items: number;
    covered_items: number;
}

export interface CompanionCoverage {
    receipts: CompanionCoverageAxis;
    invoices: CompanionCoverageAxis;
    banking: CompanionCoverageAxis;
    books?: CompanionCoverageAxis; // Optional - backend may not return this
}

export interface CompanionCloseReadiness {
    status: "ready" | "not_ready";
    blocking_reasons: string[];
}

export interface CompanionPlaybookStep {
    label: string;
    surface: string;
    severity: string;
    url: string;
    issue_id: number | null;
}

export interface CompanionStory {
    overall_summary: string;
    timeline_bullets: string[];
}

export interface CompanionVoice {
    greeting: string;
    focus_mode: FocusMode;
    tone_tagline: string;
    primary_call_to_action: string | null;
}

export interface CompanionSummary {
    ai_companion_enabled: boolean;
    radar?: CompanionRadar;
    coverage?: CompanionCoverage;
    close_readiness?: CompanionCloseReadiness;
    playbook?: CompanionPlaybookStep[];
    story?: CompanionStory;
    voice?: CompanionVoice;
    llm_subtitles?: {
        receipts: string;
        invoices: string;
        books: string;
        bank: string;
    } | null;
    global?: {
        open_issues_total?: number;
        open_issues_by_severity?: Record<string, number>;
        open_issues_by_surface?: Record<string, number>;
    };
}

// ---------------------------------------------------------------------------
// CACHE
// ---------------------------------------------------------------------------

// Simple in-memory cache with TTL
let cachedSummary: CompanionSummary | null = null;
let cacheTimestamp: number = 0;
const CACHE_TTL_MS = 30000; // 30 seconds

// ---------------------------------------------------------------------------
// HOOK
// ---------------------------------------------------------------------------

export interface UseCompanionSummaryResult {
    summary: CompanionSummary | null;
    isLoading: boolean;
    error: Error | null;
    refetch: () => Promise<void>;
}

export function useCompanionSummary(): UseCompanionSummaryResult {
    const [summary, setSummary] = useState<CompanionSummary | null>(cachedSummary);
    const [isLoading, setIsLoading] = useState<boolean>(!cachedSummary);
    const [error, setError] = useState<Error | null>(null);

    const fetchSummary = useCallback(async () => {
        // Check cache first
        const now = Date.now();
        if (cachedSummary && now - cacheTimestamp < CACHE_TTL_MS) {
            setSummary(cachedSummary);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const cookies = parseCookies(document.cookie || "");
            const csrfToken = cookies.csrftoken;
            const headers: Record<string, string> = {
                Accept: "application/json",
            };
            if (csrfToken) {
                headers["X-CSRFToken"] = csrfToken;
            }

            const response = await fetch("/api/agentic/companion/summary", {
                method: "GET",
                credentials: "same-origin",
                headers,
            });

            if (!response.ok) {
                throw new Error(`Request failed with status ${response.status}`);
            }

            const data: CompanionSummary = await response.json();

            // Update cache
            cachedSummary = data;
            cacheTimestamp = Date.now();

            setSummary(data);
        } catch (err) {
            setError(err instanceof Error ? err : new Error("Unknown error"));
            setSummary(null);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSummary();
    }, [fetchSummary]);

    return {
        summary,
        isLoading,
        error,
        refetch: fetchSummary,
    };
}

// ---------------------------------------------------------------------------
// UTILITY: Clear cache (for testing)
// ---------------------------------------------------------------------------

export function clearCompanionSummaryCache(): void {
    cachedSummary = null;
    cacheTimestamp = 0;
}
