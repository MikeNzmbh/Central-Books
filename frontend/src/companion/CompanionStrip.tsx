import React, { useEffect, useRef, useMemo } from "react";
import type { CompanionContext } from "./api";
import { useCompanionContext } from "./useCompanionContext";
import { useCompanionSummary, type CompanionSummary } from "./useCompanionSummary";
import { CompanionSuggestionBanner, type RiskLevel, type CompanionSuggestion, type FocusMode } from "./CompanionSuggestionBanner";

type CompanionStripProps = {
  context: CompanionContext;
  className?: string;
  userName?: string;
};

const friendlyLabels: Record<CompanionContext, string> = {
  bank: "banking",
  reconciliation: "reconciliation",
  invoices: "invoices",
  expenses: "expenses",
  reports: "reports",
  tax_fx: "tax & FX",
  dashboard: "workspace",
};

// Map context to radar axis
const CONTEXT_TO_RADAR_AXIS: Record<CompanionContext, keyof NonNullable<CompanionSummary["radar"]>> = {
  bank: "cash_reconciliation",
  reconciliation: "cash_reconciliation",
  invoices: "revenue_invoices",
  expenses: "expenses_receipts",
  reports: "tax_compliance",
  tax_fx: "tax_compliance",
  dashboard: "cash_reconciliation",
};

// Map context to coverage domain
const CONTEXT_TO_COVERAGE: Record<CompanionContext, keyof NonNullable<CompanionSummary["coverage"]>> = {
  bank: "banking",
  reconciliation: "banking",
  invoices: "invoices",
  expenses: "receipts",
  reports: "books",
  tax_fx: "books",
  dashboard: "banking",
};

/**
 * Get time-based greeting prefix
 */
function getGreetingPrefix(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 18) return "Good afternoon";
  return "Good evening";
}

/**
 * Build greeting with optional name
 */
function buildGreeting(userName?: string): string {
  const prefix = getGreetingPrefix();
  if (userName && userName.trim()) {
    return `${prefix}, ${userName.trim().split(" ")[0]}`;
  }
  return prefix;
}

/**
 * Determine focus mode from radar score
 */
function determineFocusMode(
  score: number | undefined,
  hasHighIssues: boolean
): FocusMode {
  if (score === undefined) return "watchlist";
  if (score >= 80 && !hasHighIssues) return "all_clear";
  if (score >= 50) return "watchlist";
  return "fire_drill";
}

/**
 * Get headline for surface based on focus mode
 */
function getHeadline(context: CompanionContext, focusMode: FocusMode): string {
  const headlines: Record<string, Record<FocusMode, string>> = {
    bank: {
      all_clear: "Your bank feeds look calm — cash and books are lining up well.",
      watchlist: "Some bank transactions still need review — your cash picture isn't fully locked in.",
      fire_drill: "Your cash view is fuzzy — unreconciled bank items are piling up.",
    },
    reconciliation: {
      all_clear: "Reconciliation is on track — everything is lining up nicely.",
      watchlist: "A few items need matching — worth a quick look before month-end.",
      fire_drill: "Several unmatched items need your attention to close this period.",
    },
    invoices: {
      all_clear: "Your invoices look steady — most of your billed revenue is on track.",
      watchlist: "You've got a few invoices to keep an eye on — some are drifting past due.",
      fire_drill: "There are invoices that need your attention — overdue items are building up.",
    },
    expenses: {
      all_clear: "Your recent receipts look tidy — nothing high-risk is showing up.",
      watchlist: "A few receipts need a second look — mostly about categories.",
      fire_drill: "Several receipts are blocking clean books — let's clear those next.",
    },
    reports: {
      all_clear: "Your books for this period look solid — nothing critical is standing out.",
      watchlist: "Your books are mostly fine, but there are a few items worth reviewing.",
      fire_drill: "There are issues in your books that could affect tax or reporting.",
    },
    tax_fx: {
      all_clear: "Tax and FX look healthy — no surprises here.",
      watchlist: "A few tax-related items need review before filing.",
      fire_drill: "Tax or FX issues need attention — let's sort these soon.",
    },
    dashboard: {
      all_clear: "Your workspace is looking great — all systems nominal.",
      watchlist: "A few items across your workspace need attention.",
      fire_drill: "Multiple areas need your focus to get back on track.",
    },
  };
  return headlines[context]?.[focusMode] || headlines.dashboard[focusMode];
}

/**
 * Get subtitle from LLM (primary) or coverage/playbook fallback
 * Returns both the subtitle text and whether it came from LLM
 */
function getSubtitle(
  context: CompanionContext,
  summary: CompanionSummary | null,
  focusMode: FocusMode
): { text: string; isLlm: boolean } {
  if (!summary) {
    return { text: "Companion will be back shortly with suggestions.", isLlm: false };
  }

  // Map context to llm_subtitles key
  const llmSubtitleMap: Record<CompanionContext, keyof NonNullable<CompanionSummary["llm_subtitles"]>> = {
    bank: "bank",
    reconciliation: "bank",
    invoices: "invoices",
    expenses: "receipts",
    reports: "books",
    tax_fx: "books",
    dashboard: "bank",
  };

  // PRIMARY: Use DeepSeek-generated subtitle if available
  const llmKey = llmSubtitleMap[context];
  const llmSubtitle = summary.llm_subtitles?.[llmKey];
  if (llmSubtitle && llmSubtitle.trim()) {
    return { text: llmSubtitle, isLlm: true };
  }

  // FALLBACK: Deterministic subtitle (only when LLM failed)
  // Check for playbook step for this context
  const surfaceMap: Record<CompanionContext, string> = {
    bank: "bank",
    reconciliation: "bank",
    invoices: "invoices",
    expenses: "receipts",
    reports: "books",
    tax_fx: "books",
    dashboard: "bank",
  };
  const targetSurface = surfaceMap[context];

  const playbookStep = summary.playbook?.find(s => s.surface === targetSurface);
  if (playbookStep && (playbookStep.severity === "high" || playbookStep.severity === "medium")) {
    return { text: `Top next step: ${playbookStep.label}`, isLlm: false };
  }

  // Fall back to coverage
  const coverageKey = CONTEXT_TO_COVERAGE[context];
  const coverage = summary.coverage?.[coverageKey];
  if (coverage) {
    const pct = Math.round(coverage.coverage_percent);
    if (pct >= 90) return { text: `You've covered about ${pct}% of this area right now.`, isLlm: false };
    if (pct >= 60) return { text: `You're about ${pct}% of the way through — a bit more attention here will close the loop.`, isLlm: false };
    return { text: `Coverage is still light here (~${pct}%). Spending a few minutes will make this much more reliable.`, isLlm: false };
  }

  return { text: `Everything looks healthy in your ${friendlyLabels[context]} workspace.`, isLlm: false };
}

/**
 * Map focus mode to risk level for backward compatibility
 */
function focusModeToRiskLevel(focusMode: FocusMode): RiskLevel {
  if (focusMode === "all_clear") return "low";
  if (focusMode === "watchlist") return "medium";
  return "high";
}

const CompanionStrip: React.FC<CompanionStripProps> = ({ context, className, userName }) => {
  const {
    isLoading: contextLoading,
    error: contextError,
    contextActions,
    markContextSeen,
  } = useCompanionContext(context);

  const { summary, isLoading: summaryLoading, error: summaryError } = useCompanionSummary();

  const didMarkSeenRef = useRef(false);
  const label = friendlyLabels[context] || "workspace";
  const isLoading = contextLoading || summaryLoading;
  const hasError = !!contextError || !!summaryError;

  useEffect(() => {
    if (didMarkSeenRef.current) return;
    if (!isLoading && !hasError) {
      didMarkSeenRef.current = true;
      markContextSeen().catch(() => {
        didMarkSeenRef.current = false;
      });
    }
  }, [isLoading, hasError, markContextSeen]);

  // Build view model from summary data
  const viewModel = useMemo(() => {
    const greeting = buildGreeting(userName);

    if (hasError || !summary) {
      return {
        greeting,
        headline: "Here's what your Companion will suggest as soon as it's back online.",
        subtitle: "Companion is temporarily unavailable for this area.",
        isLlmSubtitle: false,
        focusMode: "watchlist" as FocusMode,
        riskLevel: "low" as RiskLevel,
        statusLabel: "Companion temporarily unavailable",
      };
    }

    // Get radar data for this context
    const radarKey = CONTEXT_TO_RADAR_AXIS[context];
    const axisData = summary.radar?.[radarKey];
    const score = axisData?.score;
    const hasHighIssues = (summary.global?.open_issues_by_severity?.high || 0) > 0;

    const focusMode = determineFocusMode(score, hasHighIssues);
    const headline = getHeadline(context, focusMode);
    const subtitleResult = getSubtitle(context, summary, focusMode);
    const riskLevel = focusModeToRiskLevel(focusMode);

    const statusLabels: Record<FocusMode, string> = {
      all_clear: "On track",
      watchlist: "Needs attention",
      fire_drill: "Action required",
    };

    return {
      greeting,
      headline,
      subtitle: subtitleResult.text,
      isLlmSubtitle: subtitleResult.isLlm,
      focusMode,
      riskLevel,
      statusLabel: statusLabels[focusMode],
    };
  }, [userName, hasError, summary, context]);

  // Build suggestions from actions
  const suggestions: CompanionSuggestion[] = contextActions.slice(0, 3).map((action, idx) => ({
    id: `action-${idx}`,
    label: action.summary || action.short_title || action.action_type || "Take action",
  }));

  return (
    <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
      <CompanionSuggestionBanner
        userName={userName}
        riskLevel={viewModel.riskLevel}
        sentimentLabel={viewModel.statusLabel}
        toneSubtitle={viewModel.subtitle}
        isLlmSubtitle={viewModel.isLlmSubtitle}
        suggestions={viewModel.focusMode === "all_clear" ? [] : suggestions}
        onViewMore={() => (window.location.href = "/dashboard/")}
        isLoading={isLoading}
        greeting={viewModel.greeting}
        focusMode={viewModel.focusMode}
        primaryCTA={null}
      />
    </div>
  );
};

export default CompanionStrip;
