import { useCallback, useEffect, useMemo, useState } from "react";

export interface FinancialPulseMetrics {
  cashOnHand: {
    amount: number;
    currency: string;
    updatedAt: string;
    trendLast30d?: "up" | "down" | "flat";
    trendDelta?: number;
  };

  runway: {
    months: number;
    burnRateMonthly: number;
    currency: string;
    burnDirection: "increasing" | "decreasing" | "stable";
  };

  next30Days: {
    incomingAR: number;
    outgoingAP: number;
    netCash: number;
    currency: string;
  };

  taxGuardian: {
    periodLabel: string;
    netTaxDue: number;
    currency: string;
    status: "all_clear" | "attention" | "high_risk";
    dueDate: string;
    openAnomalies: number;
  };
}

type DashboardPayload = {
  currency?: string;
  metrics?: {
    cash_on_hand?: number;
    open_invoices_total?: number;
    unpaid_expenses_total?: number;
    revenue_30?: number;
    expenses_30?: number;
  };
};

type CompanionSummaryPayload = {
  finance_snapshot?: {
    cash_health?: {
      ending_cash?: number;
      monthly_burn?: number;
      runway_months?: number | null;
    };
    revenue_expense?: {
      months?: string[];
      revenue?: number[];
      expense?: number[];
    };
  };
  tax?: {
    period_key: string;
    net_tax: number | null;
    jurisdictions?: Array<{ currency?: string | null }>;
    anomaly_counts?: { low?: number; medium?: number; high?: number };
  };
  tax_guardian?: {
    issues?: unknown[];
  };
};

type TaxPeriodsResponse = {
  periods?: Array<{
    period_key: string;
    net_tax?: number;
    anomaly_counts?: { low?: number; medium?: number; high?: number };
    due_date?: string;
    is_due_soon?: boolean;
    is_overdue?: boolean;
  }>;
};

type InvoiceListResponse = {
  currency?: string;
  invoices?: Array<{
    status?: string;
    due_date?: string | null;
    grand_total?: string | number | null;
    amount_paid?: string | number | null;
  }>;
};

function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : Number.NaN;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  }
  return Number.NaN;
}

function sumAnomalies(counts?: { low?: number; medium?: number; high?: number }): number {
  const low = counts?.low ?? 0;
  const medium = counts?.medium ?? 0;
  const high = counts?.high ?? 0;
  return low + medium + high;
}

function computeBurnDirection(expenseSeries?: number[]): "increasing" | "decreasing" | "stable" {
  if (!expenseSeries || expenseSeries.length < 2) return "stable";
  const last = expenseSeries[expenseSeries.length - 1];
  const prev = expenseSeries[expenseSeries.length - 2];
  if (!Number.isFinite(last) || !Number.isFinite(prev) || prev === 0) return "stable";
  const ratio = last / prev;
  if (ratio >= 1.03) return "increasing";
  if (ratio <= 0.97) return "decreasing";
  return "stable";
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

function taxStatusFromCounts(counts?: { low?: number; medium?: number; high?: number }, due?: { is_overdue?: boolean }): FinancialPulseMetrics["taxGuardian"]["status"] {
  if (due?.is_overdue) return "high_risk";
  const high = counts?.high ?? 0;
  const medium = counts?.medium ?? 0;
  const low = counts?.low ?? 0;
  if (high > 0) return "high_risk";
  if (medium > 0 || low > 0) return "attention";
  return "all_clear";
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Request failed (${res.status}) ${text}`.trim());
  }
  return (await res.json()) as T;
}

export function useFinancialPulseMetrics(): {
  data: FinancialPulseMetrics | null;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
} {
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [data, setData] = useState<FinancialPulseMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const refetch = useCallback(() => {
    setRefreshIndex((i) => i + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      setError(null);

      const [dashboardResult, summaryResult, taxPeriodsResult, invoicesResult] = await Promise.allSettled([
        fetchJson<DashboardPayload>("/api/dashboard/"),
        fetchJson<CompanionSummaryPayload>("/api/agentic/companion/summary"),
        fetchJson<TaxPeriodsResponse>("/api/tax/periods/"),
        fetchJson<InvoiceListResponse>("/api/invoices/list/?status=all"),
      ]);

      if (cancelled) return;

      const failures = [dashboardResult, summaryResult, taxPeriodsResult, invoicesResult]
        .filter((r) => r.status === "rejected")
        .map((r) => (r as PromiseRejectedResult).reason);
      setError(failures.length ? failures : null);

      const dashboard = dashboardResult.status === "fulfilled" ? dashboardResult.value : null;
      const summary = summaryResult.status === "fulfilled" ? summaryResult.value : null;
      const taxPeriods = taxPeriodsResult.status === "fulfilled" ? taxPeriodsResult.value : null;
      const invoices = invoicesResult.status === "fulfilled" ? invoicesResult.value : null;

      const currency =
        dashboard?.currency ||
        invoices?.currency ||
        summary?.tax?.jurisdictions?.find((j) => Boolean(j.currency))?.currency ||
        "USD";

      const nowIso = new Date().toISOString();

      const dashboardCash = toNumber(dashboard?.metrics?.cash_on_hand);
      const snapshotCash = toNumber(summary?.finance_snapshot?.cash_health?.ending_cash);
      const cashOnHandAmount = Number.isFinite(dashboardCash) ? dashboardCash : snapshotCash;

      const snapshotRunway = toNumber(summary?.finance_snapshot?.cash_health?.runway_months);
      const snapshotMonthlyBurn = toNumber(summary?.finance_snapshot?.cash_health?.monthly_burn);
      const burnRateMonthly = Number.isFinite(snapshotMonthlyBurn) ? -snapshotMonthlyBurn : Number.NaN;
      const runwayMonths = Number.isFinite(snapshotRunway)
        ? snapshotRunway
        : Number.isFinite(burnRateMonthly) && burnRateMonthly >= 0 && Number.isFinite(cashOnHandAmount) && cashOnHandAmount > 0
          ? 24
          : Number.NaN;
      const burnDirection = computeBurnDirection(summary?.finance_snapshot?.revenue_expense?.expense);

      const invoiceWindowStart = new Date();
      invoiceWindowStart.setHours(0, 0, 0, 0);
      const invoiceWindowEnd = new Date(invoiceWindowStart);
      invoiceWindowEnd.setDate(invoiceWindowEnd.getDate() + 30);
      const incomingFromInvoices = (() => {
        const list = invoices?.invoices || [];
        if (list.length === 0) return Number.NaN;
        let total = 0;
        let counted = 0;
        for (const inv of list) {
          if (!inv?.due_date) continue;
          const status = String(inv.status || "").toUpperCase();
          if (status !== "SENT" && status !== "PARTIAL") continue;
          const due = parseISODateToLocal(inv.due_date);
          if (!due) continue;
          if (due < invoiceWindowStart || due > invoiceWindowEnd) continue;

          const grandTotal = toNumber(inv.grand_total);
          const amountPaid = toNumber(inv.amount_paid);
          const balance = (Number.isFinite(grandTotal) ? grandTotal : 0) - (Number.isFinite(amountPaid) ? amountPaid : 0);
          if (!Number.isFinite(balance) || balance <= 0) continue;
          total += balance;
          counted += 1;
        }
        return counted > 0 ? total : 0;
      })();
      const fallbackIncoming = toNumber(dashboard?.metrics?.open_invoices_total);
      const incomingAR = Number.isFinite(incomingFromInvoices)
        ? incomingFromInvoices
        : Number.isFinite(fallbackIncoming)
          ? fallbackIncoming
          : Number.NaN;

      const unpaidExpenses = toNumber(dashboard?.metrics?.unpaid_expenses_total);

      const periodKey =
        summary?.tax?.period_key ||
        taxPeriods?.periods?.[0]?.period_key ||
        "";
      const periodFromList = taxPeriods?.periods?.find((p) => p.period_key === periodKey);
      const dueDate = periodFromList?.due_date || "";
      const dueMeta = periodFromList ? { is_overdue: periodFromList.is_overdue, is_due_soon: periodFromList.is_due_soon } : undefined;

      const netTaxDueFromSummary = summary?.tax?.net_tax;
      const netTaxDueFromPeriods = toNumber(periodFromList?.net_tax);
      const netTaxDue = netTaxDueFromSummary !== null && netTaxDueFromSummary !== undefined
        ? Number(netTaxDueFromSummary)
        : netTaxDueFromPeriods;

      const taxCounts =
        summary?.tax?.anomaly_counts || periodFromList?.anomaly_counts || undefined;
      const openAnomalies = sumAnomalies(taxCounts);
      const taxGuardianStatus = taxStatusFromCounts(taxCounts, dueMeta);

      const taxOutflow = (() => {
        if (!Number.isFinite(netTaxDue) || netTaxDue <= 0) return 0;
        if (!dueDate) return 0;
        const due = parseISODateToLocal(dueDate);
        if (!due) return 0;
        if (due <= invoiceWindowEnd) return netTaxDue;
        return 0;
      })();

      const outgoingAP = Number.isFinite(unpaidExpenses)
        ? unpaidExpenses + taxOutflow
        : Number.NaN;

      const netCash = Number.isFinite(incomingAR) && Number.isFinite(outgoingAP)
        ? incomingAR - outgoingAP
        : Number.NaN;

      setData({
        cashOnHand: {
          amount: cashOnHandAmount,
          currency,
          updatedAt: nowIso,
        },
        runway: {
          months: runwayMonths,
          burnRateMonthly,
          currency,
          burnDirection,
        },
        next30Days: {
          incomingAR,
          outgoingAP,
          netCash,
          currency,
        },
        taxGuardian: {
          periodLabel: periodKey,
          netTaxDue,
          currency,
          status: taxGuardianStatus,
          dueDate,
          openAnomalies,
        },
      });
      setIsLoading(false);
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [refreshIndex]);

  return useMemo(() => ({ data, isLoading, error, refetch }), [data, isLoading, error, refetch]);
}
