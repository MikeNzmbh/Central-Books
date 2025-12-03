import React, { useEffect, useRef } from "react";
import type { CompanionContext } from "./api";
import { useCompanionContext } from "./useCompanionContext";

type CompanionStripProps = {
  context: CompanionContext;
  className?: string;
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

const combine = (items: string[]) => items.filter(Boolean).slice(0, 3);

// Health score color mapping
function getHealthBorderColor(score: number | null): string {
  if (score === null) return "border-slate-200";
  if (score >= 80) return "border-emerald-300";
  if (score >= 60) return "border-amber-300";
  if (score >= 40) return "border-orange-300";
  return "border-rose-300";
}

function getHealthRingColor(score: number | null): string {
  if (score === null) return "ring-slate-100";
  if (score >= 80) return "ring-emerald-100";
  if (score >= 60) return "ring-amber-100";
  if (score >= 40) return "ring-orange-100";
  return "ring-rose-100";
}

const CompanionStrip: React.FC<CompanionStripProps> = ({ context, className }) => {
  const {
    isLoading,
    error,
    healthSnippet,
    contextInsights,
    contextActions,
    contextAllClear,
    contextNarrative,
    hasNewActions,
    markContextSeen,
  } = useCompanionContext(context);
  const items = combine([
    ...contextInsights.map((i) => i.title || i.body),
    ...contextActions.map((a) => a.summary || a.action_type),
  ]);
  const hasSignals = items.length > 0;
  const label = friendlyLabels[context] || "workspace";
  const didMarkSeenRef = useRef(false);
  const showNewBadge = hasNewActions && !contextAllClear && hasSignals;

  const healthScore = healthSnippet?.score ?? null;
  const borderColor = getHealthBorderColor(healthScore);
  const ringColor = getHealthRingColor(healthScore);

  useEffect(() => {
    if (didMarkSeenRef.current) return;
    if (!isLoading && !error) {
      didMarkSeenRef.current = true;
      markContextSeen().catch(() => {
        didMarkSeenRef.current = false;
      });
    }
  }, [isLoading, error, markContextSeen]);

  if (isLoading) {
    return (
      <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
        <div className={`companion-glow-inner relative overflow-hidden p-3 shadow-sm border ${borderColor}`}>
          <div className="h-2 w-24 animate-pulse rounded-full bg-slate-100" />
          <div className="mt-2 h-2 w-full animate-pulse rounded-full bg-slate-100" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
        <div className={`companion-glow-inner border ${borderColor} bg-white/90 px-3 py-2 text-[12px] text-slate-600 shadow-sm`}>
          <div className="flex items-center gap-2">
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[11px]">⚠</span>
            <span>Companion temporarily unavailable</span>
          </div>
        </div>
      </div>
    );
  }

  if (contextAllClear || !hasSignals) {
    return (
      <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
        <div
          className={`companion-glow-inner flex flex-col gap-1 border ${borderColor} bg-white/90 px-3 py-2 text-[13px] text-slate-600 shadow-sm`}
        >
          <div className="flex items-center gap-2">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-[12px] text-emerald-700">✓</span>
            <span className="font-semibold text-slate-700">Everything looks good here.</span>
          </div>
          <span className="text-[12px] text-slate-500">
            Companion checked this {label} area and found nothing urgent.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={`companion-glow ${className || ""}`} data-testid="companion-strip-glow">
      <div
        className={`companion-glow-inner flex flex-col gap-1 border ${borderColor} bg-sky-50/90 px-3 py-2 shadow-sm`}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-[12px] font-semibold text-slate-700">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-sky-600 text-[11px] font-bold text-white">
              AI
            </span>
            <span className="flex items-center gap-2">
              <span>Companion suggests…</span>
              {showNewBadge ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-[2px] text-[10px] font-semibold text-sky-700 ring-1 ring-sky-200">
                  New
                </span>
              ) : null}
            </span>
            {healthSnippet && (
              <span className="text-[11px] font-medium text-slate-500">
                {healthSnippet.statusText}
              </span>
            )}
          </div>
          <a
            className="text-[11px] font-semibold text-sky-700 underline decoration-sky-300 decoration-dotted hover:text-sky-800"
            href="/dashboard/"
          >
            View more
          </a>
        </div>
        <ul className="ml-1 list-disc space-y-1 pl-4 text-[13px] text-slate-700">
          {items.slice(0, 2).map((text, idx) => (
            <li key={idx}>{text}</li>
          ))}
        </ul>
        {contextNarrative ? (
          <p className="text-[12px] text-slate-600">{contextNarrative}</p>
        ) : null}
      </div>
    </div>
  );
};

export default CompanionStrip;
