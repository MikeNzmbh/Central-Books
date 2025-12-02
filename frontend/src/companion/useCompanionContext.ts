import { useEffect, useMemo, useState } from "react";

import type { CompanionAction, CompanionContext, CompanionInsight, CompanionOverview } from "./api";
import { fetchCompanionOverview } from "./api";

const CACHE_TTL_MS = 60_000;

type CacheEntry = {
  data: CompanionOverview | null;
  error: Error | null;
  fetchedAt: number;
};

let cachedOverview: CacheEntry | null = null;
let inFlight: Promise<CompanionOverview> | null = null;

export type UseCompanionContextResult = {
  isLoading: boolean;
  error: Error | null;
  healthSnippet: {
    score: number | null;
    statusText: string;
  } | null;
  contextInsights: CompanionInsight[];
  contextActions: CompanionAction[];
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
  const [data, setData] = useState<CompanionOverview | null>(cachedOverview?.data ?? null);
  const [isLoading, setIsLoading] = useState(!isCacheFresh(cachedOverview));
  const [error, setError] = useState<Error | null>(cachedOverview?.error ?? null);

  useEffect(() => {
    let mounted = true;
    if (isCacheFresh(cachedOverview)) {
      setIsLoading(false);
      setError(cachedOverview?.error ?? null);
      setData(cachedOverview?.data ?? null);
      return () => {
        mounted = false;
      };
    }

    setIsLoading(true);
    if (!inFlight) {
      inFlight = fetchCompanionOverview()
        .then((payload) => {
          cachedOverview = { data: payload, error: null, fetchedAt: Date.now() };
          return payload;
        })
        .catch((err) => {
          const normalizedError = err instanceof Error ? err : new Error("Unable to load Companion data.");
          cachedOverview = { data: null, error: normalizedError, fetchedAt: Date.now() };
          throw normalizedError;
        })
        .finally(() => {
          inFlight = null;
        });
    }

    inFlight
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setError(null);
      })
      .catch((err: Error) => {
        if (!mounted) return;
        setError(err);
        setData(cachedOverview?.data ?? null);
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

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

  const healthSnippet = deriveHealthSnippet(data?.health_index?.score ?? null);

  return {
    isLoading,
    error,
    healthSnippet,
    contextInsights,
    contextActions,
  };
}

export function resetCompanionContextCacheForTests() {
  cachedOverview = null;
  inFlight = null;
}
