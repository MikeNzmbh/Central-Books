import React, { useEffect, useRef } from "react";
import type { CompanionContext } from "./api";
import { useCompanionContext } from "./useCompanionContext";
import { CompanionSuggestionBanner, type RiskLevel, type CompanionSuggestion } from "./CompanionSuggestionBanner";

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

/**
 * Maps context severity to RiskLevel for the new banner design.
 */
function mapSeverityToRiskLevel(severity: string | null | undefined): RiskLevel {
  const sev = (severity || "").toLowerCase();
  if (sev === "critical") return "critical";
  if (sev === "high") return "high";
  if (sev === "medium") return "medium";
  return "low";
}

/**
 * Get a user-friendly sentiment label based on risk level.
 */
function getSentimentLabel(riskLevel: RiskLevel, allClear: boolean): string {
  if (allClear) return "All systems nominal";
  switch (riskLevel) {
    case "critical":
      return "Immediate Action Required";
    case "high":
      return "High risk";
    case "medium":
      return "Needs attention";
    default:
      return "All good";
  }
}

/**
 * Get a tone subtitle based on context and risk level.
 */
function getToneSubtitle(riskLevel: RiskLevel, context: string, allClear: boolean): string {
  if (allClear) {
    return `Your ${context} area is in great shape.`;
  }
  switch (riskLevel) {
    case "critical":
      return "Multiple issues require your immediate attention.";
    case "high":
      return "There are urgent items that need to be addressed soon.";
    case "medium":
      return "Steady, just keep an eye on a few items.";
    default:
      return `Everything looks healthy in your ${context} workspace.`;
  }
}

const CompanionStrip: React.FC<CompanionStripProps> = ({ context, className, userName }) => {
  const {
    isLoading,
    error,
    contextInsights,
    contextActions,
    contextAllClear,
    contextSeverity,
    markContextSeen,
  } = useCompanionContext(context);

  const didMarkSeenRef = useRef(false);
  const label = friendlyLabels[context] || "workspace";

  useEffect(() => {
    if (didMarkSeenRef.current) return;
    if (!isLoading && !error) {
      didMarkSeenRef.current = true;
      markContextSeen().catch(() => {
        didMarkSeenRef.current = false;
      });
    }
  }, [isLoading, error, markContextSeen]);

  // Calculate risk level and suggestions
  const riskLevel = mapSeverityToRiskLevel(contextSeverity);
  const hasSignals = contextInsights.length > 0 || contextActions.length > 0;
  const allClear = contextAllClear || !hasSignals;

  // Build suggestions from insights and actions
  const suggestions: CompanionSuggestion[] = [
    ...contextInsights.slice(0, 2).map((insight, idx) => ({
      id: `insight-${idx}`,
      label: insight.title || insight.body || "Review insight",
    })),
    ...contextActions.slice(0, 2).map((action, idx) => ({
      id: `action-${idx}`,
      label: action.summary || action.short_title || action.action_type || "Take action",
    })),
  ].slice(0, 4); // Max 4 suggestions

  const sentimentLabel = getSentimentLabel(riskLevel, allClear);
  const toneSubtitle = getToneSubtitle(riskLevel, label, allClear);

  // Error state
  if (error) {
    return (
      <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
        <CompanionSuggestionBanner
          riskLevel="low"
          sentimentLabel="Temporarily unavailable"
          toneSubtitle="Companion will be back shortly."
          suggestions={[]}
          onViewMore={() => (window.location.href = "/dashboard/")}
        />
      </div>
    );
  }

  return (
    <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
      <CompanionSuggestionBanner
        userName={userName}
        riskLevel={allClear ? "low" : riskLevel}
        sentimentLabel={sentimentLabel}
        toneSubtitle={toneSubtitle}
        suggestions={allClear ? [] : suggestions}
        onViewMore={() => (window.location.href = "/dashboard/")}
        isLoading={isLoading}
      />
    </div>
  );
};

export default CompanionStrip;
