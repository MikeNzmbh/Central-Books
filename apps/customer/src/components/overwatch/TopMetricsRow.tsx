import React from "react";
import { Link } from "react-router-dom";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Minus,
  ShieldCheck,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useFinancialPulseMetrics, type FinancialPulseMetrics } from "./useFinancialPulseMetrics";

const cn = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(" ");

function formatMoney(amount: number, currency: string, opts?: { maximumFractionDigits?: number }): string {
  if (!Number.isFinite(amount)) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: opts?.maximumFractionDigits ?? 0,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString(undefined, { maximumFractionDigits: opts?.maximumFractionDigits ?? 0 })} ${currency || ""}`.trim();
  }
}

function formatSignedMoney(amount: number, currency: string): string {
  if (!Number.isFinite(amount)) return "—";
  const minus = "−";
  const sign = amount >= 0 ? "+" : minus;
  return `${sign}${formatMoney(Math.abs(amount), currency)}`;
}

function parseISODateToLocal(iso: string): Date | null {
  const core = iso.split("T")[0];
  const parts = core.split("-");
  if (parts.length !== 3) return null;
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  const day = Number(parts[2]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  const d = new Date(year, month - 1, day);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDateShort(iso: string): string {
  const d = parseISODateToLocal(iso);
  if (!d) return "—";
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getMonth()];
  return `${month} ${d.getDate()}`;
}

function daysUntil(iso: string): number | null {
  const d = parseISODateToLocal(iso);
  if (!d) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  return Math.round((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function SkeletonLine({ className }: { className: string }) {
  return <div className={cn("animate-pulse rounded-md bg-slate-200/70", className)} />;
}

function MetricCardShell({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-3xl border border-slate-100/70 bg-slate-50/80",
        "shadow-[0_18px_60px_rgba(15,23,42,0.06)]",
        "transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_22px_70px_rgba(15,23,42,0.08)]"
      )}
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 opacity-60">
        <div className="absolute -top-16 -right-16 h-40 w-40 rounded-full bg-gradient-to-br from-slate-100 via-slate-50 to-slate-200 blur-2xl" />
        <div className="absolute -bottom-20 -left-10 h-40 w-40 rounded-full bg-gradient-to-tr from-white via-slate-50 to-slate-200 blur-2xl" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-slate-200/70 to-transparent" />
      </div>

      <div className="relative p-5 md:p-6 flex flex-col gap-3 min-h-[168px]">
        {children}
      </div>
    </div>
  );
}

function CardHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-medium text-rose-700">{message}</div>
      <button
        type="button"
        onClick={onRetry}
        className="self-start inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
      >
        Try again <ArrowRight className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function CashOnHandCard({
  metrics,
  isLoading,
  onRetry,
}: {
  metrics: FinancialPulseMetrics | null;
  isLoading: boolean;
  onRetry: () => void;
}) {
  if (isLoading) {
    return (
      <MetricCardShell>
        <CardHeader title="Cash on hand" />
        <SkeletonLine className="h-9 w-44" />
        <SkeletonLine className="h-4 w-56" />
        <div className="mt-auto flex justify-end">
          <SkeletonLine className="h-6 w-40 rounded-full" />
        </div>
      </MetricCardShell>
    );
  }

  const amount = metrics?.cashOnHand?.amount;
  if (!metrics || !Number.isFinite(amount)) {
    return (
      <MetricCardShell>
        <CardHeader title="Cash on hand" />
        <InlineError message="Unable to load cash balances" onRetry={onRetry} />
      </MetricCardShell>
    );
  }

  const { currency, trendDelta, trendLast30d } = metrics.cashOnHand;
  const showTrend = Number.isFinite(trendDelta) && !!trendLast30d;
  const trendTone =
    trendLast30d === "up"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200/70"
      : trendLast30d === "down"
        ? "bg-rose-50 text-rose-700 border-rose-200/70"
        : "bg-slate-100 text-slate-700 border-slate-200/70";
  const TrendIcon =
    trendLast30d === "up" ? ArrowUpRight : trendLast30d === "down" ? ArrowDownRight : Minus;

  return (
    <MetricCardShell>
      <CardHeader title="Cash on hand" />
      <div className="text-3xl md:text-4xl font-semibold tracking-tight text-slate-900 font-mono-soft">
        {formatMoney(amount as number, currency)}
      </div>
      <div className="text-xs text-slate-500">Updated live from ledger balances.</div>

      <div className="mt-auto flex items-end justify-between gap-3">
        <div />
        {showTrend ? (
          <div className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold", trendTone)}>
            <TrendIcon className="h-3.5 w-3.5" />
            <span className="whitespace-nowrap">Last 30 days: <span className="font-mono-soft">{trendDelta! >= 0 ? "+" : ""}{trendDelta!.toFixed(1)}%</span></span>
          </div>
        ) : null}
      </div>
    </MetricCardShell>
  );
}

function RunwayCard({
  metrics,
  isLoading,
  onRetry,
}: {
  metrics: FinancialPulseMetrics | null;
  isLoading: boolean;
  onRetry: () => void;
}) {
  if (isLoading) {
    return (
      <MetricCardShell>
        <CardHeader title="Runway & Burn" />
        <SkeletonLine className="h-9 w-32" />
        <SkeletonLine className="h-4 w-44" />
        <SkeletonLine className="h-4 w-48" />
      </MetricCardShell>
    );
  }

  const runwayMonths = metrics?.runway?.months;
  const burn = metrics?.runway?.burnRateMonthly;
  if (!metrics || !Number.isFinite(runwayMonths) || !Number.isFinite(burn)) {
    return (
      <MetricCardShell>
        <CardHeader title="Runway & Burn" />
        <InlineError message="Unable to load runway metrics" onRetry={onRetry} />
      </MetricCardShell>
    );
  }

  const currency = metrics.runway.currency;
  const months = runwayMonths as number;
  const burnRateMonthly = burn as number;

  const runwayDisplay = months >= 24 ? "24+ months" : `${months.toFixed(1)} months`;
  const runwayTag =
    months >= 24
      ? { label: "On track", className: "bg-emerald-50 text-emerald-700 border-emerald-200/70" }
      : months >= 12
        ? { label: "Comfortable", className: "bg-slate-100 text-slate-700 border-slate-200/70" }
        : months < 6
          ? { label: "Low runway", className: "bg-amber-50 text-amber-700 border-amber-200/70" }
          : { label: "Watch", className: "bg-amber-50/60 text-amber-700 border-amber-200/60" };

  const burnLabel = burnRateMonthly < 0 ? "Burn" : "Surplus";
  const burnColor =
    metrics.runway.burnDirection === "decreasing"
      ? "text-emerald-700"
      : metrics.runway.burnDirection === "increasing"
        ? "text-rose-700"
        : "text-slate-700";
  const BurnIcon =
    metrics.runway.burnDirection === "decreasing"
      ? TrendingDown
      : metrics.runway.burnDirection === "increasing"
        ? TrendingUp
        : Minus;

  return (
    <MetricCardShell>
      <CardHeader
        title="Runway & Burn"
        right={
          <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold", runwayTag.className)}>
            {runwayTag.label}
          </span>
        }
      />

      <div className="flex items-baseline gap-2">
        <div className="text-3xl md:text-4xl font-semibold tracking-tight text-slate-900 font-mono-soft">
          {runwayDisplay}
        </div>
      </div>

      <div className={cn("flex items-center gap-2 text-sm font-semibold", burnColor)}>
        <BurnIcon className="h-4 w-4" />
        <span className="font-mono-soft">
          {burnLabel} {formatSignedMoney(burnRateMonthly, currency)} / month
        </span>
      </div>

      <div className="text-xs text-slate-500">Based on last 3 months average.</div>
    </MetricCardShell>
  );
}

function Next30DaysCard({
  metrics,
  isLoading,
  onRetry,
}: {
  metrics: FinancialPulseMetrics | null;
  isLoading: boolean;
  onRetry: () => void;
}) {
  if (isLoading) {
    return (
      <MetricCardShell>
        <CardHeader title="Next 30 Days — In vs Out" />
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <SkeletonLine className="h-3 w-16" />
            <SkeletonLine className="h-7 w-28" />
          </div>
          <div className="space-y-2">
            <SkeletonLine className="h-3 w-16" />
            <SkeletonLine className="h-7 w-28" />
          </div>
        </div>
        <SkeletonLine className="h-8 w-full rounded-xl" />
      </MetricCardShell>
    );
  }

  const incoming = metrics?.next30Days?.incomingAR;
  const outgoing = metrics?.next30Days?.outgoingAP;
  const net = metrics?.next30Days?.netCash;
  if (!metrics || !Number.isFinite(incoming) || !Number.isFinite(outgoing) || !Number.isFinite(net)) {
    return (
      <MetricCardShell>
        <CardHeader title="Next 30 Days — In vs Out" />
        <InlineError message="Unable to load cashflow outlook" onRetry={onRetry} />
      </MetricCardShell>
    );
  }

  const currency = metrics.next30Days.currency;
  const incomingAR = incoming as number;
  const outgoingAP = outgoing as number;
  const netCash = net as number;
  const allQuiet = incomingAR === 0 && outgoingAP === 0;
  const netTone =
    netCash >= 0
      ? "bg-emerald-50 text-emerald-700 border-emerald-200/70"
      : "bg-rose-50 text-rose-700 border-rose-200/70";

  const max = Math.max(incomingAR, outgoingAP, 1);
  const incomingPct = Math.round((incomingAR / max) * 100);
  const outgoingPct = Math.round((outgoingAP / max) * 100);

  return (
    <MetricCardShell>
      <CardHeader title="Next 30 Days — In vs Out" />

      {allQuiet ? (
        <div className="mt-2 rounded-2xl border border-slate-200/70 bg-white/60 px-4 py-3">
          <div className="text-sm font-semibold text-slate-800">All quiet</div>
          <div className="text-xs text-slate-500 mt-0.5">No expected inflows or outflows detected.</div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Incoming</div>
              <div className="text-xl font-semibold text-slate-900 font-mono-soft">
                {formatMoney(incomingAR, currency)}
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Outgoing</div>
              <div className="text-xl font-semibold text-slate-900 font-mono-soft">
                {formatMoney(outgoingAP, currency)}
              </div>
            </div>
          </div>

          <div className="mt-1 rounded-2xl border border-slate-200/70 bg-white/60 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-slate-600">Net</div>
              <div className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold font-mono-soft", netTone)}>
                {formatSignedMoney(netCash, currency)}
              </div>
            </div>
            <div className="mt-2 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>In</span>
                <span className="font-mono-soft">{incomingPct}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full rounded-full bg-emerald-400/70" style={{ width: `${incomingPct}%` }} />
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Out</span>
                <span className="font-mono-soft">{outgoingPct}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div className="h-full rounded-full bg-rose-400/70" style={{ width: `${outgoingPct}%` }} />
              </div>
            </div>
          </div>
        </>
      )}
    </MetricCardShell>
  );
}

function TaxGuardianCard({
  metrics,
  isLoading,
  onRetry,
}: {
  metrics: FinancialPulseMetrics | null;
  isLoading: boolean;
  onRetry: () => void;
}) {
  if (isLoading) {
    return (
      <MetricCardShell>
        <CardHeader title="Tax & Compliance" />
        <SkeletonLine className="h-9 w-40" />
        <SkeletonLine className="h-4 w-44" />
        <div className="flex gap-2">
          <SkeletonLine className="h-6 w-24 rounded-full" />
          <SkeletonLine className="h-6 w-28 rounded-full" />
        </div>
        <div className="mt-auto flex justify-end">
          <SkeletonLine className="h-8 w-40 rounded-lg" />
        </div>
      </MetricCardShell>
    );
  }

  const due = metrics?.taxGuardian?.dueDate;
  const amount = metrics?.taxGuardian?.netTaxDue;
  if (!metrics || !Number.isFinite(amount)) {
    return (
      <MetricCardShell>
        <CardHeader title="Tax & Compliance" />
        <InlineError message="Unable to load tax status" onRetry={onRetry} />
      </MetricCardShell>
    );
  }

  const status = metrics.taxGuardian.status;
  const statusTone =
    status === "all_clear"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200/70"
      : status === "attention"
        ? "bg-amber-50 text-amber-700 border-amber-200/70"
        : "bg-rose-50 text-rose-700 border-rose-200/70";
  const StatusIcon = status === "all_clear" ? ShieldCheck : ShieldAlert;

  const days = due ? daysUntil(due) : null;
  const dueRisk = days === null ? "Unknown" : days <= 7 ? "At risk" : "On track";
  const dueTone =
    days === null
      ? "bg-slate-100 text-slate-700 border-slate-200/70"
      : days <= 7
        ? "bg-amber-50 text-amber-700 border-amber-200/70"
        : "bg-slate-100 text-slate-700 border-slate-200/70";

  const taxHref = `/tax${metrics.taxGuardian.periodLabel ? `?period=${encodeURIComponent(metrics.taxGuardian.periodLabel)}` : ""}`;

  return (
    <MetricCardShell>
      <CardHeader title="Tax & Compliance" />

      <div className="space-y-1">
        <div className="text-xs font-semibold text-slate-500">Net tax this period</div>
        <div className="text-3xl md:text-4xl font-semibold tracking-tight text-slate-900 font-mono-soft">
          {formatMoney(amount as number, metrics.taxGuardian.currency)}
        </div>
        <div className="text-xs text-slate-500">Period: {metrics.taxGuardian.periodLabel || "—"}</div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold", statusTone)}>
          <StatusIcon className="h-3.5 w-3.5" />
          {status === "all_clear" ? "All clear" : status === "attention" ? "Attention" : "High risk"}
        </span>
        <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold", dueTone)}>
          <span>Due:</span>
          <span className="font-mono-soft">{due ? formatDateShort(due) : "—"}</span>
          <span className="text-slate-400">·</span>
          <span>{dueRisk}</span>
        </span>
      </div>

      {metrics.taxGuardian.openAnomalies > 0 ? (
        <div className="flex items-center gap-2 text-xs text-amber-700">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
          <span>{metrics.taxGuardian.openAnomalies} anomalies need review</span>
        </div>
      ) : null}

      <div className="mt-auto flex justify-end">
        <Link
          to={taxHref}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
        >
          View Tax Guardian <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </MetricCardShell>
  );
}

export default function TopMetricsRow({ className }: { className?: string }) {
  const { data, isLoading, refetch } = useFinancialPulseMetrics();

  return (
    <section className={cn("w-full", className)} aria-label="Top metrics">
      <div
        className={cn(
          "grid gap-4 md:gap-5 xl:gap-6",
          "grid-cols-1 md:grid-cols-2 xl:grid-cols-4"
        )}
      >
        <CashOnHandCard metrics={data} isLoading={isLoading} onRetry={refetch} />
        <RunwayCard metrics={data} isLoading={isLoading} onRetry={refetch} />
        <Next30DaysCard metrics={data} isLoading={isLoading} onRetry={refetch} />
        <TaxGuardianCard metrics={data} isLoading={isLoading} onRetry={refetch} />
      </div>
    </section>
  );
}
