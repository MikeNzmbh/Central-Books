import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { CompanionAction, CompanionContext, CompanionInsight, CompanionOverview } from "./api";
import { fetchCompanionOverview, markCompanionContextSeen } from "./api";

const CACHE_TTL_MS = 60_000;

type CacheEntry = {
  data: CompanionOverview | null;
  error: Error | null;
  fetchedAt: number;
};

let cachedOverview: Record<string, CacheEntry | null> = {};
let inFlight: Record<string, Promise<CompanionOverview> | null> = {};

export type UseCompanionContextResult = {
  isLoading: boolean;
  error: Error | null;
  healthSnippet: {
    score: number | null;
    statusText: string;
  } | null;
  contextInsights: CompanionInsight[];
  contextActions: CompanionAction[];
  contextAllClear: boolean;
  contextNarrative: string | null;
  contextReasons: string[];
  contextSummary: string | null;
  contextSeverity: string | null;
  focusItems: string[];
  highestSeverity: string | null;
  hasCriticalOrHigh: boolean;
  hasNewActions: boolean;
  newActionsCount: number;
  markContextSeen: () => Promise<void>;
};

function deriveHealthSnippet(score: number | null | undefined): UseCompanionContextResult["healthSnippet"] {
  if (score === null || score === undefined) return null;
  if (score >= 80) return { score, statusText: "Healthy" };
  if (score >= 60) return { score, statusText: "Steady, keep an eye" };
  if (score >= 40) return { score, statusText: "Needs attention" };
  return { score, statusText: "At risk" };
}

function isCacheFresh(entry: CacheEntry | null) {
  if (!entry) return false;
  return Date.now() - entry.fetchedAt < CACHE_TTL_MS;
}

export function useCompanionContext(context: CompanionContext): UseCompanionContextResult {
  const params = new URLSearchParams(window.location.search);
  const periodStart = params.get("period_start") || params.get("start_date") || "";
  const periodEnd = params.get("period_end") || params.get("end_date") || "";
  const cacheKey = `${context || "default"}:${periodStart}:${periodEnd}`;
  const [data, setData] = useState<CompanionOverview | null>(cachedOverview[cacheKey]?.data ?? null);
  const [isLoading, setIsLoading] = useState(!isCacheFresh(cachedOverview[cacheKey] || null));
  const [error, setError] = useState<Error | null>(cachedOverview[cacheKey]?.error ?? null);
  const markSeenOnceRef = useRef(false);

  useEffect(() => {
    let mounted = true;
    if (isCacheFresh(cachedOverview[cacheKey] || null)) {
      setIsLoading(false);
      setError(cachedOverview[cacheKey]?.error ?? null);
      setData(cachedOverview[cacheKey]?.data ?? null);
      return () => {
        mounted = false;
      };
    }

    setIsLoading(true);
    if (!inFlight[cacheKey]) {
      inFlight[cacheKey] = fetchCompanionOverview(context, periodStart || undefined, periodEnd || undefined)
        .then((payload) => {
          cachedOverview[cacheKey] = { data: payload, error: null, fetchedAt: Date.now() };
          return payload;
        })
        .catch((err) => {
          const normalizedError = err instanceof Error ? err : new Error("Unable to load Companion data.");
          cachedOverview[cacheKey] = { data: null, error: normalizedError, fetchedAt: Date.now() };
          throw normalizedError;
        })
        .finally(() => {
          inFlight[cacheKey] = null;
        });
    }

    const pending = inFlight[cacheKey];
    pending
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setError(null);
      })
      .catch((err: Error) => {
        if (!mounted) return;
        setError(err);
        setData(cachedOverview[cacheKey]?.data ?? null);
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [cacheKey, context, periodEnd, periodStart]);

  const allInsights = useMemo(() => data?.insights || data?.top_insights || [], [data?.insights, data?.top_insights]);
  const allActions = useMemo(() => data?.actions || [], [data?.actions]);

  const contextInsights = useMemo(
    () => allInsights.filter((insight) => (insight.context || "dashboard") === context),
    [allInsights, context]
  );
  const contextActions = useMemo(
    () => allActions.filter((action) => (action.context || "dashboard") === context),
    [allActions, context]
  );
  const severityOrder: Record<string, number> = {
    CRITICAL: 0,
    HIGH: 1,
    MEDIUM: 2,
    LOW: 3,
    INFO: 4,
  };
  const highestSeverity = useMemo(() => {
    if (!contextActions.length) return null;
    const sorted = [...contextActions].sort(
      (a, b) => (severityOrder[a.severity || "INFO"] ?? 10) - (severityOrder[b.severity || "INFO"] ?? 10)
    );
    return sorted[0]?.severity || null;
  }, [contextActions]);

  const healthSnippet = deriveHealthSnippet(data?.health_index?.score ?? null);
  const hasNewActions = Boolean(data?.has_new_actions);
  const newActionsCount = data?.new_actions_count ?? 0;

  const markContextSeen = useCallback(async () => {
    if (markSeenOnceRef.current) {
      return;
    }
    markSeenOnceRef.current = true;

    try {
      await markCompanionContextSeen(context);
      setError(null);
      setData((prev) => {
        const next = prev ? { ...prev, has_new_actions: false, new_actions_count: 0 } : prev;
        if (next) {
          const cached = cachedOverview[cacheKey];
          const updatedCache = cached
            ? { ...cached, data: next, error: null, fetchedAt: Date.now() }
            : { data: next, error: null, fetchedAt: Date.now() };
          cachedOverview[cacheKey] = updatedCache;
        }
        return next;
      });
    } catch (err) {
      markSeenOnceRef.current = false;
      const normalizedError = err instanceof Error ? err : new Error("Unable to update Companion state.");
      setError(normalizedError);
    }
  }, [cacheKey, context]);

  return {
    isLoading,
    error,
    healthSnippet,
    contextInsights,
    contextActions,
    contextAllClear: Boolean(data?.context_all_clear),
    contextNarrative: data?.llm_narrative?.context_summary || data?.llm_narrative?.summary || null,
    contextSummary: data?.llm_narrative?.context_summary || data?.llm_narrative?.summary || null,
    contextReasons: data?.context_reasons || [],
    contextSeverity: data?.context_severity || null,
    focusItems: data?.llm_narrative?.focus_items || data?.focus_items || [],
    highestSeverity,
    hasCriticalOrHigh: highestSeverity === "CRITICAL" || highestSeverity === "HIGH",
    hasNewActions,
    newActionsCount,
    markContextSeen,
  };
}

export function resetCompanionContextCacheForTests() {
  cachedOverview = {};
  inFlight = null;
}
