import React, { useMemo } from "react";
import { ReportExportButton } from "./ReportExportButton";
import { ReportPeriodPicker, PeriodSelection } from "../components/reports/ReportPeriodPicker";

export interface CashflowPeriodPoint {
  periodLabel: string;
  inflows: number;
  outflows: number;
  net: number;
}

export interface CashflowActivityBreakdown {
  operating: number;
  investing: number;
  financing: number;
}

export interface CashDriver {
  id: string;
  label: string;
  amount: number;
  type: "inflow" | "outflow";
}

export interface CashflowReportProps {
  username: string;
  asOfLabel: string;
  baseCurrency: string;
  period?: {
    start?: string;
    end?: string;
    preset?: string;
    label?: string | null;
  };
  comparison?: {
    label?: string | null;
    start?: string | null;
    end?: string | null;
    compare_to?: string | null;
  };
  summary: {
    netChange: number;
    totalInflows: number;
    totalOutflows: number;
    runwayLabel?: string | null;
  };
  trend: CashflowPeriodPoint[];
  activities: CashflowActivityBreakdown;
  topDrivers: CashDriver[];
  bankingUrl?: string;
  invoicesUrl?: string;
  expensesUrl?: string;
}

const CashflowReportPage: React.FC<CashflowReportProps> = ({
  username,
  asOfLabel,
  baseCurrency,
  summary,
  trend,
  activities,
  topDrivers,
  bankingUrl,
  invoicesUrl,
  expensesUrl,
  period,
  comparison,
}) => {
  const currencyCode =
    baseCurrency?.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase() || "USD";

  const formatter = useMemo(
    () =>
      new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currencyCode,
        maximumFractionDigits: 0,
      }),
    [currencyCode]
  );

  const formatCurrency = (value: number): string => formatter.format(value || 0);

  const totalInflows = summary.totalInflows || 0;
  const totalOutflows = summary.totalOutflows || 0;
  const netCash = summary.netChange || totalInflows - totalOutflows;

  const maxPeriodTotal =
    trend.length > 0
      ? Math.max(
        ...trend.map((p) => Math.max(p.inflows + p.outflows, Math.abs(p.net))),
        1
      )
      : 1;

  const activitiesArray = [
    { label: "Operating", value: activities.operating || 0 },
    { label: "Investing", value: activities.investing || 0 },
    { label: "Financing", value: activities.financing || 0 },
  ];

  const maxActivity = Math.max(
    ...activitiesArray.map((item) => Math.abs(item.value)),
    1
  );

  const handlePeriodChange = (selection: PeriodSelection) => {
    const params = new URLSearchParams(window.location.search);
    params.set("period_preset", selection.preset || "last_6_months");
    if (selection.preset === "custom") {
      if (selection.startDate) params.set("start_date", selection.startDate);
      if (selection.endDate) params.set("end_date", selection.endDate);
    } else {
      params.delete("start_date");
      params.delete("end_date");
    }
    params.set("compare_to", selection.compareTo || "none");
    window.location.search = params.toString();
  };

  const hasTrend = trend.length > 0;
  const safeTrend = hasTrend ? trend : [];

  return (
    <div className="min-h-screen w-full bg-slate-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="space-y-1">
            <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">
              Reports · Cashflow
            </p>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
              Morning, {username.split(" ")[0] || "there"}.<br className="hidden md:block" />
              <span className="text-slate-400">Your cashflow is </span>
              <span className="mb-accent-underline">{netCash >= 0 ? "healthy." : "under pressure."}</span>
            </h1>
            <p className="text-sm text-slate-500 max-w-xl">
              Cash moving in and out of your business. Trends, drivers, activities—everything you
              need to keep runway calm and predictable.
            </p>
            <p className="text-xs text-slate-400">
              {period?.label ? `Showing ${period.label}` : asOfLabel}
            </p>
            {comparison?.label && (
              <p className="text-[11px] text-slate-500">Compared to {comparison.label}</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {bankingUrl && (
              <a
                href={bankingUrl}
                className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-100"
              >
                Go to banking
              </a>
            )}
            <ReportExportButton to="/reports/cashflow/print/" />
          </div>
        </header>

        <div className="flex flex-col md:flex-row md:items-center md:justify-end">
          <ReportPeriodPicker
            preset={(period?.preset as PeriodSelection["preset"]) || "last_6_months"}
            startDate={period?.start}
            endDate={period?.end}
            compareTo={(comparison?.compare_to as PeriodSelection["compareTo"]) || "previous_period"}
            onApply={handlePeriodChange}
            onChange={(sel) => {
              if (sel.preset !== "custom") handlePeriodChange(sel);
            }}
            className="md:max-w-xl w-full"
          />
        </div>

        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 py-4 flex flex-col gap-2">
            <p className="text-[11px] font-medium text-slate-500 uppercase">Net cash change</p>
            <p className="text-xl font-semibold tracking-tight font-mono-soft">{formatCurrency(netCash)}</p>
            <p className="text-[11px] text-slate-500">
              {netCash >= 0 ? "More coming in than going out" : "Outflows are ahead of inflows"}
            </p>
          </div>
          <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 py-4 flex flex-col gap-2">
            <p className="text-[11px] font-medium text-slate-500 uppercase">Total inflows</p>
            <p className="text-xl font-semibold tracking-tight font-mono-soft">{formatCurrency(totalInflows)}</p>
            <p className="text-[11px] text-slate-500">Customer payments, deposits, and receipts.</p>
          </div>
          <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 py-4 flex flex-col gap-2">
            <p className="text-[11px] font-medium text-slate-500 uppercase">Total outflows</p>
            <p className="text-xl font-semibold tracking-tight font-mono-soft">{formatCurrency(totalOutflows)}</p>
            <p className="text-[11px] text-slate-500">Bills, payroll, subscriptions, and other spend.</p>
          </div>
          <div className="rounded-3xl bg-slate-900 text-slate-50 px-4 py-4 flex flex-col gap-2">
            <p className="text-[11px] font-medium text-slate-300 uppercase">Cash runway</p>
            <p className="text-xl font-semibold tracking-tight font-mono-soft">
              {summary.runwayLabel || "—"}
            </p>
            <p className="text-[11px] text-slate-300">
              Simple signal based on current cash and monthly net activity.
            </p>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)] gap-4">
          <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 sm:px-6 py-4 sm:py-5 flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-slate-900">Cashflow trend</p>
                <p className="text-[11px] text-slate-500">
                  Bars show inflows vs. outflows per month. The line tracks net cash.
                </p>
              </div>
              <div className="flex items-center gap-4 text-[11px] text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  Inflows
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-rose-400" />
                  Outflows
                </span>
              </div>
            </div>
            {hasTrend ? (
              <div className="mt-2 h-52 sm:h-60 flex items-end gap-2 sm:gap-3 border-t border-slate-100 pt-4">
                {safeTrend.map((period) => {
                  const inflowHeight = Math.max(
                    6,
                    (Math.abs(period.inflows) / maxPeriodTotal) * 100
                  );
                  const outflowHeight = Math.max(
                    4,
                    (Math.abs(period.outflows) / maxPeriodTotal) * 100
                  );
                  const net = period.net || 0;
                  return (
                    <div key={period.periodLabel} className="flex-1 flex flex-col items-center h-full">
                      <div
                        className="relative w-full flex flex-col justify-end gap-1"
                        style={{ height: "100%" }}
                      >
                        <div
                          className="w-full rounded-full bg-emerald-200 transition-all duration-200"
                          style={{ height: `${inflowHeight}%` }}
                        />
                        <div
                          className="w-full rounded-full bg-rose-200 transition-all duration-200 -mt-1"
                          style={{ height: `${outflowHeight}%` }}
                        />
                      </div>
                      <p
                        className={
                          "text-[11px] font-medium mt-2 font-mono-soft " +
                          (net >= 0 ? "text-emerald-600" : "text-rose-500")
                        }
                      >
                        {formatCurrency(net)}
                      </p>
                      <p className="text-[11px] text-slate-500">{period.periodLabel}</p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="h-52 flex items-center justify-center text-sm text-slate-500 border border-dashed border-slate-200 rounded-2xl">
                No cash movements yet. Connect a bank account or import CSV.
              </div>
            )}
          </div>

          <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 sm:px-6 py-4 sm:py-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-900">Activities</p>
                <p className="text-[11px] text-slate-500">Operating, investing, financing.</p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center text-xs">
              {activitiesArray.map((activity) => {
                const height = Math.max(
                  10,
                  (Math.abs(activity.value) / maxActivity) * 100
                );
                const positive = activity.value >= 0;
                return (
                  <div key={activity.label} className="flex flex-col items-center gap-2 h-40">
                    <div className="flex-1 flex items-end w-full justify-center">
                      <div
                        className={
                          "w-8 rounded-full " +
                          (positive ? "bg-emerald-200" : "bg-rose-200")
                        }
                        style={{ height: `${height}%` }}
                      />
                    </div>
                    <div>
                      <p className="text-[11px] text-slate-500 uppercase">{activity.label}</p>
                      <p
                        className={
                          "text-[11px] font-semibold font-mono-soft " +
                          (positive ? "text-emerald-600" : "text-rose-500")
                        }
                      >
                        {formatCurrency(activity.value)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2.5">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-medium text-slate-700">Top cash drivers</p>
                {invoicesUrl && (
                  <a
                    href={invoicesUrl}
                    className="text-[11px] font-medium text-slate-500 hover:text-slate-900"
                  >
                    View all
                  </a>
                )}
              </div>
              <div className="mt-2 space-y-1.5">
                {topDrivers.length ? (
                  topDrivers.map((driver) => (
                    <div key={driver.id} className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-500 truncate mr-2">{driver.label}</span>
                      <span
                        className={
                          "font-mono-soft " + (driver.amount >= 0 ? "text-emerald-600 font-medium" : "text-rose-500 font-medium")
                        }
                      >
                        {formatCurrency(driver.amount)}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-slate-500 text-xs">No drivers yet.</p>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-3xl bg-white shadow-sm border border-slate-100 overflow-hidden">
          <div className="px-4 sm:px-6 py-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">Period breakdown</p>
              <p className="text-[11px] text-slate-500">
                Detailed view of inflows, outflows, and net cash per period.
              </p>
            </div>
            {expensesUrl && (
              <a
                href={expensesUrl}
                className="text-[11px] font-medium text-slate-500 hover:text-slate-900"
              >
                Go to expenses
              </a>
            )}
          </div>
          <div className="border-t border-slate-100 overflow-x-auto">
            {hasTrend ? (
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50/80">
                  <tr>
                    <th className="px-4 sm:px-6 py-2 font-medium text-slate-500">Period</th>
                    <th className="px-4 sm:px-6 py-2 font-medium text-slate-500">Inflows</th>
                    <th className="px-4 sm:px-6 py-2 font-medium text-slate-500">Outflows</th>
                    <th className="px-4 sm:px-6 py-2 font-medium text-slate-500">Net cash</th>
                  </tr>
                </thead>
                <tbody>
                  {safeTrend.map((point, idx) => {
                    const net = point.net || point.inflows - point.outflows;
                    return (
                      <tr
                        key={point.periodLabel}
                        className={idx % 2 === 0 ? "bg-white" : "bg-slate-50/60"}
                      >
                        <td className="px-4 sm:px-6 py-2.5 text-slate-700 text-xs">
                          {point.periodLabel}
                        </td>
                        <td className="px-4 sm:px-6 py-2.5 text-slate-700 text-xs font-mono-soft">
                          {formatCurrency(point.inflows)}
                        </td>
                        <td className="px-4 sm:px-6 py-2.5 text-slate-700 text-xs font-mono-soft">
                          {formatCurrency(point.outflows)}
                        </td>
                        <td
                          className={
                            "px-4 sm:px-6 py-2.5 text-xs font-medium font-mono-soft " +
                            (net >= 0 ? "text-emerald-600" : "text-rose-500")
                          }
                        >
                          {formatCurrency(net)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="py-8 text-center text-sm text-slate-500">
                No cashflow periods yet. Once transactions post, this table will populate.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default CashflowReportPage;
