import React, { useMemo } from "react";

// --- Type Definitions ---

export type PlPeriodPreset =
    | "this_month"
    | "last_month"
    | "this_quarter"
    | "last_quarter"
    | "this_year"
    | "last_year"
    | "last_30_days"
    | "custom";

export type PlComparePreset =
    | "previous_period"
    | "same_period_last_year"
    | "none";

export interface PlKpiSummary {
    income: number;
    cogs: number;
    grossProfit: number;
    expenses: number;
    netIncome: number;
    grossMarginPct: number | null;
    netMarginPct: number | null;
    changeIncomePct?: number | null;
    changeCogsPct?: number | null;
    changeGrossProfitPct?: number | null;
    changeExpensesPct?: number | null;
    changeNetIncomePct?: number | null;
}

export interface PlAccountRow {
    id: string;
    name: string;
    code?: string;
    group: "INCOME" | "COGS" | "EXPENSE";
    amount: number;
    compareAmount?: number | null;
}

export interface PlDiagnostics {
    hasActivity: boolean;
    reasons: string[];
}

export interface ProfitAndLossReportProps {
    businessName: string;
    currency: string;
    periodPreset: PlPeriodPreset;
    periodLabel: string;
    periodStart: string;
    periodEnd: string;
    comparePreset: PlComparePreset;
    compareLabel?: string;
    kpi: PlKpiSummary;
    rows: PlAccountRow[];
    diagnostics: PlDiagnostics;
    loading?: boolean;
    onBack?: () => void;
    onChangePeriod?: (period: PlPeriodPreset, custom?: { start: string; end: string }) => void;
    onChangeCompare?: (compare: PlComparePreset) => void;
    onExportPdf?: () => void;
    onExportCsv?: () => void;
    onPrint?: () => void;
}

// --- Helper Functions ---

const formatCurrency = (value: number, currency: string): string => {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: currency || "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value);
};

const formatCurrencyPrecise = (value: number, currency: string): string => {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: currency || "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
};

// --- Sub-Components ---

const TrendBadge: React.FC<{ value: number | null | undefined; inverse?: boolean }> = ({
    value,
    inverse = false,
}) => {
    if (value == null) return null;
    const isPositive = inverse ? value <= 0 : value >= 0;
    const textColor = isPositive ? "text-emerald-600" : "text-rose-500";
    const arrow = value >= 0 ? "↑" : "↓";
    return (
        <span className={`text-[11px] font-medium ${textColor}`}>
            {arrow} {Math.abs(value).toFixed(1)}%
        </span>
    );
};

const LoadingSpinner: React.FC = () => (
    <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-900 rounded-full animate-spin" />
    </div>
);

// --- Main Component ---

const ProfitAndLossReportPage: React.FC<ProfitAndLossReportProps> = ({
    businessName,
    currency,
    periodPreset,
    periodLabel,
    periodStart,
    periodEnd,
    comparePreset,
    compareLabel,
    kpi,
    rows,
    diagnostics,
    loading = false,
    onBack,
    onChangePeriod,
    onChangeCompare,
    onExportPdf,
    onExportCsv,
    onPrint,
}) => {
    const incomeRows = useMemo(() => rows.filter((r) => r.group === "INCOME"), [rows]);
    const cogsRows = useMemo(() => rows.filter((r) => r.group === "COGS"), [rows]);
    const expenseRows = useMemo(() => rows.filter((r) => r.group === "EXPENSE"), [rows]);

    const hasComparison = comparePreset !== "none" && compareLabel;

    // Group totals for comparison
    const compareIncome = hasComparison ? incomeRows.reduce((sum, r) => sum + (r.compareAmount || 0), 0) : null;
    const compareCogs = hasComparison ? cogsRows.reduce((sum, r) => sum + (r.compareAmount || 0), 0) : null;
    const compareExpenses = hasComparison ? expenseRows.reduce((sum, r) => sum + (r.compareAmount || 0), 0) : null;
    const compareGrossProfit = compareIncome !== null && compareCogs !== null ? compareIncome - compareCogs : null;
    const compareNetIncome = compareGrossProfit !== null && compareExpenses !== null ? compareGrossProfit - compareExpenses : null;

    return (
        <div className="min-h-screen w-full bg-slate-50 text-slate-900">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
                {/* Header - matching Cashflow style */}
                <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="space-y-1">
                        <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">
                            Reports · Profit & Loss
                        </p>
                        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
                            {businessName}
                        </h1>
                        <p className="text-sm text-slate-500 max-w-xl">
                            Revenue, costs, and profitability for the period. Track margins, monitor expenses, and understand your bottom line.
                        </p>
                        <p className="text-xs text-slate-400">
                            Showing {periodLabel} · {periodStart} – {periodEnd}
                        </p>
                        {hasComparison && (
                            <p className="text-[11px] text-slate-500">Compared to {compareLabel}</p>
                        )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        {onExportPdf && (
                            <button
                                onClick={onExportPdf}
                                className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-100"
                            >
                                Download PDF
                            </button>
                        )}
                    </div>
                </header>

                {/* Period Picker Row */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span className="font-medium">PERIOD</span>
                        <select
                            value={periodPreset}
                            onChange={(e) => onChangePeriod?.(e.target.value as PlPeriodPreset)}
                            className="px-2 py-1 rounded border border-slate-200 bg-white text-slate-700"
                        >
                            <option value="this_month">This Month</option>
                            <option value="last_month">Last Month</option>
                            <option value="this_quarter">This Quarter</option>
                            <option value="last_quarter">Last Quarter</option>
                            <option value="this_year">This Year</option>
                            <option value="last_year">Last Year</option>
                            <option value="last_30_days">Last 30 Days</option>
                        </select>

                        <span className="font-medium ml-4">COMPARE</span>
                        <select
                            value={comparePreset}
                            onChange={(e) => onChangeCompare?.(e.target.value as PlComparePreset)}
                            className="px-2 py-1 rounded border border-slate-200 bg-white text-slate-700"
                        >
                            <option value="previous_period">Previous period</option>
                            <option value="same_period_last_year">Same period last year</option>
                            <option value="none">No comparison</option>
                        </select>
                    </div>
                </div>

                {loading ? (
                    <LoadingSpinner />
                ) : (
                    <>
                        {/* KPI Cards - matching Cashflow style exactly */}
                        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                            {/* Net Income */}
                            <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 py-4 flex flex-col gap-2">
                                <p className="text-[11px] font-medium text-slate-500 uppercase">Net Income</p>
                                <p className={`text-xl font-semibold tracking-tight ${kpi.netIncome >= 0 ? '' : 'text-rose-500'}`}>
                                    {formatCurrency(kpi.netIncome, currency)}
                                </p>
                                <p className="text-[11px] text-slate-500">
                                    {kpi.netIncome >= 0 ? "Profit after all expenses" : "Operating at a loss"}
                                </p>
                            </div>

                            {/* Total Revenue */}
                            <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 py-4 flex flex-col gap-2">
                                <p className="text-[11px] font-medium text-slate-500 uppercase">Total Revenue</p>
                                <p className="text-xl font-semibold tracking-tight">
                                    {formatCurrency(kpi.income, currency)}
                                </p>
                                <p className="text-[11px] text-slate-500">Income from sales and services.</p>
                            </div>

                            {/* Total Expenses */}
                            <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 py-4 flex flex-col gap-2">
                                <p className="text-[11px] font-medium text-slate-500 uppercase">Total Expenses</p>
                                <p className="text-xl font-semibold tracking-tight">
                                    {formatCurrency(kpi.expenses + kpi.cogs, currency)}
                                </p>
                                <p className="text-[11px] text-slate-500">COGS and operating expenses combined.</p>
                            </div>

                            {/* Gross Margin - Dark card like Cash Runway */}
                            <div className="rounded-3xl bg-slate-900 text-slate-50 px-4 py-4 flex flex-col gap-2">
                                <p className="text-[11px] font-medium text-slate-300 uppercase">Gross Margin</p>
                                <p className="text-xl font-semibold tracking-tight">
                                    {kpi.grossMarginPct != null ? `${kpi.grossMarginPct.toFixed(1)}%` : "—"}
                                </p>
                                <p className="text-[11px] text-slate-300">
                                    Profit after cost of goods sold.
                                </p>
                            </div>
                        </section>

                        {/* Two Column Layout - matching Cashflow */}
                        <section className="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)] gap-4">
                            {/* Income vs Expenses Breakdown */}
                            <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 sm:px-6 py-4 sm:py-5 flex flex-col gap-4">
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <p className="text-sm font-medium text-slate-900">Profit breakdown</p>
                                        <p className="text-[11px] text-slate-500">
                                            Revenue minus costs equals your profit.
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-4 text-[11px] text-slate-500">
                                        <span className="inline-flex items-center gap-1">
                                            <span className="h-2 w-2 rounded-full bg-emerald-500" />
                                            Revenue
                                        </span>
                                        <span className="inline-flex items-center gap-1">
                                            <span className="h-2 w-2 rounded-full bg-rose-400" />
                                            Costs
                                        </span>
                                    </div>
                                </div>

                                {/* Bar Chart */}
                                <div className="mt-2 h-52 sm:h-60 flex items-end gap-4 border-t border-slate-100 pt-4">
                                    {/* Revenue Bar */}
                                    <div className="flex-1 flex flex-col items-center h-full">
                                        <div className="relative w-full flex flex-col justify-end" style={{ height: "100%" }}>
                                            <div
                                                className="w-full rounded-t-lg bg-emerald-200 transition-all duration-200"
                                                style={{ height: `${Math.min(100, (kpi.income / Math.max(kpi.income, kpi.expenses + kpi.cogs, 1)) * 100)}%` }}
                                            />
                                        </div>
                                        <p className="text-[11px] font-medium mt-2 text-emerald-600">
                                            {formatCurrency(kpi.income, currency)}
                                        </p>
                                        <p className="text-[11px] text-slate-500">Revenue</p>
                                    </div>

                                    {/* COGS Bar */}
                                    {kpi.cogs > 0 && (
                                        <div className="flex-1 flex flex-col items-center h-full">
                                            <div className="relative w-full flex flex-col justify-end" style={{ height: "100%" }}>
                                                <div
                                                    className="w-full rounded-t-lg bg-amber-200 transition-all duration-200"
                                                    style={{ height: `${Math.min(100, (kpi.cogs / Math.max(kpi.income, kpi.expenses + kpi.cogs, 1)) * 100)}%` }}
                                                />
                                            </div>
                                            <p className="text-[11px] font-medium mt-2 text-amber-600">
                                                {formatCurrency(kpi.cogs, currency)}
                                            </p>
                                            <p className="text-[11px] text-slate-500">COGS</p>
                                        </div>
                                    )}

                                    {/* Expenses Bar */}
                                    <div className="flex-1 flex flex-col items-center h-full">
                                        <div className="relative w-full flex flex-col justify-end" style={{ height: "100%" }}>
                                            <div
                                                className="w-full rounded-t-lg bg-rose-200 transition-all duration-200"
                                                style={{ height: `${Math.min(100, (kpi.expenses / Math.max(kpi.income, kpi.expenses + kpi.cogs, 1)) * 100)}%` }}
                                            />
                                        </div>
                                        <p className="text-[11px] font-medium mt-2 text-rose-500">
                                            {formatCurrency(kpi.expenses, currency)}
                                        </p>
                                        <p className="text-[11px] text-slate-500">Expenses</p>
                                    </div>

                                    {/* Net Income Bar */}
                                    <div className="flex-1 flex flex-col items-center h-full">
                                        <div className="relative w-full flex flex-col justify-end" style={{ height: "100%" }}>
                                            <div
                                                className={`w-full rounded-t-lg transition-all duration-200 ${kpi.netIncome >= 0 ? 'bg-emerald-400' : 'bg-rose-400'}`}
                                                style={{ height: `${Math.min(100, (Math.abs(kpi.netIncome) / Math.max(kpi.income, kpi.expenses + kpi.cogs, 1)) * 100)}%` }}
                                            />
                                        </div>
                                        <p className={`text-[11px] font-medium mt-2 ${kpi.netIncome >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                                            {formatCurrency(kpi.netIncome, currency)}
                                        </p>
                                        <p className="text-[11px] text-slate-500">Net</p>
                                    </div>
                                </div>
                            </div>

                            {/* Margin Metrics */}
                            <div className="rounded-3xl bg-white shadow-sm border border-slate-100 px-4 sm:px-6 py-4 sm:py-5 flex flex-col gap-4">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-slate-900">Margins</p>
                                        <p className="text-[11px] text-slate-500">Profitability metrics.</p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4 text-center text-xs">
                                    {/* Gross Margin */}
                                    <div className="flex flex-col items-center gap-2 p-4 rounded-2xl bg-slate-50">
                                        <p className="text-[11px] text-slate-500 uppercase">Gross</p>
                                        <p className="text-lg font-semibold text-slate-900">
                                            {kpi.grossMarginPct != null ? `${kpi.grossMarginPct.toFixed(1)}%` : "—"}
                                        </p>
                                        {kpi.changeGrossProfitPct != null && (
                                            <TrendBadge value={kpi.changeGrossProfitPct} />
                                        )}
                                    </div>

                                    {/* Net Margin */}
                                    <div className="flex flex-col items-center gap-2 p-4 rounded-2xl bg-slate-50">
                                        <p className="text-[11px] text-slate-500 uppercase">Net</p>
                                        <p className={`text-lg font-semibold ${kpi.netMarginPct != null && kpi.netMarginPct >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                                            {kpi.netMarginPct != null ? `${kpi.netMarginPct.toFixed(1)}%` : "—"}
                                        </p>
                                        {kpi.changeNetIncomePct != null && (
                                            <TrendBadge value={kpi.changeNetIncomePct} />
                                        )}
                                    </div>
                                </div>

                                {/* Top expenses mini list */}
                                <div className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2.5 mt-auto">
                                    <div className="flex items-center justify-between">
                                        <p className="text-[11px] font-medium text-slate-700">Top expense categories</p>
                                    </div>
                                    <div className="mt-2 space-y-1.5">
                                        {expenseRows.slice(0, 3).map((row) => (
                                            <div key={row.id} className="flex items-center justify-between text-[11px]">
                                                <span className="text-slate-500 truncate mr-2">{row.name}</span>
                                                <span className="text-rose-500 font-medium">
                                                    {formatCurrency(row.amount, currency)}
                                                </span>
                                            </div>
                                        ))}
                                        {expenseRows.length === 0 && (
                                            <p className="text-slate-500 text-xs">No expenses yet.</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </section>

                        {/* Detailed Breakdown Table */}
                        <section className="rounded-3xl bg-white shadow-sm border border-slate-100 overflow-hidden">
                            <div className="px-4 sm:px-6 py-3 flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-slate-900">Detailed breakdown</p>
                                    <p className="text-[11px] text-slate-500">
                                        Account-level view of revenue, costs, and expenses.
                                    </p>
                                </div>
                            </div>

                            <div className="border-t border-slate-100 overflow-x-auto">
                                <table className="min-w-full text-left text-xs">
                                    <thead className="bg-slate-50/80">
                                        <tr>
                                            <th className="px-4 sm:px-6 py-2 font-medium text-slate-500">Account</th>
                                            <th className="px-4 sm:px-6 py-2 font-medium text-slate-500 text-right">{periodLabel}</th>
                                            {hasComparison && (
                                                <>
                                                    <th className="px-4 sm:px-6 py-2 font-medium text-slate-500 text-right">{compareLabel}</th>
                                                    <th className="px-4 sm:px-6 py-2 font-medium text-slate-500 text-right">Change</th>
                                                </>
                                            )}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {/* Revenue Header */}
                                        <tr className="bg-slate-50">
                                            <td colSpan={hasComparison ? 4 : 2} className="px-4 sm:px-6 py-2 text-[11px] font-semibold text-slate-700 uppercase">
                                                Revenue
                                            </td>
                                        </tr>
                                        {incomeRows.map((row, idx) => (
                                            <tr key={row.id} className={idx % 2 === 0 ? "bg-white" : "bg-slate-50/60"}>
                                                <td className="px-4 sm:px-6 py-2.5">
                                                    <span className="text-slate-700 text-xs">{row.name}</span>
                                                    {row.code && <span className="text-slate-400 text-[10px] ml-2">{row.code}</span>}
                                                </td>
                                                <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-700">
                                                    {formatCurrencyPrecise(row.amount, currency)}
                                                </td>
                                                {hasComparison && (
                                                    <>
                                                        <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-500">
                                                            {formatCurrencyPrecise(row.compareAmount || 0, currency)}
                                                        </td>
                                                        <td className="px-4 sm:px-6 py-2.5 text-right">
                                                            {row.compareAmount != null && row.compareAmount !== 0 && (
                                                                <TrendBadge value={((row.amount - row.compareAmount) / Math.abs(row.compareAmount)) * 100} />
                                                            )}
                                                        </td>
                                                    </>
                                                )}
                                            </tr>
                                        ))}
                                        {incomeRows.length === 0 && (
                                            <tr><td colSpan={hasComparison ? 4 : 2} className="px-4 sm:px-6 py-2.5 text-xs text-slate-400 italic">No revenue recorded</td></tr>
                                        )}
                                        {/* Total Revenue */}
                                        <tr className="bg-slate-100 font-medium">
                                            <td className="px-4 sm:px-6 py-2.5 text-xs text-slate-700">Total Revenue</td>
                                            <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-emerald-600 font-semibold">
                                                {formatCurrencyPrecise(kpi.income, currency)}
                                            </td>
                                            {hasComparison && (
                                                <>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-500">
                                                        {formatCurrencyPrecise(compareIncome || 0, currency)}
                                                    </td>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right">
                                                        <TrendBadge value={kpi.changeIncomePct} />
                                                    </td>
                                                </>
                                            )}
                                        </tr>

                                        {/* COGS Section */}
                                        {cogsRows.length > 0 && (
                                            <>
                                                <tr className="bg-slate-50">
                                                    <td colSpan={hasComparison ? 4 : 2} className="px-4 sm:px-6 py-2 text-[11px] font-semibold text-slate-700 uppercase">
                                                        Cost of Goods Sold
                                                    </td>
                                                </tr>
                                                {cogsRows.map((row, idx) => (
                                                    <tr key={row.id} className={idx % 2 === 0 ? "bg-white" : "bg-slate-50/60"}>
                                                        <td className="px-4 sm:px-6 py-2.5">
                                                            <span className="text-slate-700 text-xs">{row.name}</span>
                                                            {row.code && <span className="text-slate-400 text-[10px] ml-2">{row.code}</span>}
                                                        </td>
                                                        <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-700">
                                                            {formatCurrencyPrecise(row.amount, currency)}
                                                        </td>
                                                        {hasComparison && (
                                                            <>
                                                                <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-500">
                                                                    {formatCurrencyPrecise(row.compareAmount || 0, currency)}
                                                                </td>
                                                                <td className="px-4 sm:px-6 py-2.5 text-right">
                                                                    {row.compareAmount != null && row.compareAmount !== 0 && (
                                                                        <TrendBadge value={((row.amount - row.compareAmount) / Math.abs(row.compareAmount)) * 100} inverse />
                                                                    )}
                                                                </td>
                                                            </>
                                                        )}
                                                    </tr>
                                                ))}
                                                <tr className="bg-slate-100 font-medium">
                                                    <td className="px-4 sm:px-6 py-2.5 text-xs text-slate-700">Total COGS</td>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-700 font-semibold">
                                                        {formatCurrencyPrecise(kpi.cogs, currency)}
                                                    </td>
                                                    {hasComparison && (
                                                        <>
                                                            <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-500">
                                                                {formatCurrencyPrecise(compareCogs || 0, currency)}
                                                            </td>
                                                            <td className="px-4 sm:px-6 py-2.5 text-right">
                                                                <TrendBadge value={kpi.changeCogsPct} inverse />
                                                            </td>
                                                        </>
                                                    )}
                                                </tr>
                                            </>
                                        )}

                                        {/* Gross Profit */}
                                        <tr className="bg-slate-200/60 font-semibold">
                                            <td className="px-4 sm:px-6 py-2.5 text-xs text-slate-900">Gross Profit</td>
                                            <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-900">
                                                {formatCurrencyPrecise(kpi.grossProfit, currency)}
                                            </td>
                                            {hasComparison && (
                                                <>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-600">
                                                        {formatCurrencyPrecise(compareGrossProfit || 0, currency)}
                                                    </td>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right">
                                                        <TrendBadge value={kpi.changeGrossProfitPct} />
                                                    </td>
                                                </>
                                            )}
                                        </tr>

                                        {/* Operating Expenses */}
                                        <tr className="bg-slate-50">
                                            <td colSpan={hasComparison ? 4 : 2} className="px-4 sm:px-6 py-2 text-[11px] font-semibold text-slate-700 uppercase">
                                                Operating Expenses
                                            </td>
                                        </tr>
                                        {expenseRows.map((row, idx) => (
                                            <tr key={row.id} className={idx % 2 === 0 ? "bg-white" : "bg-slate-50/60"}>
                                                <td className="px-4 sm:px-6 py-2.5">
                                                    <span className="text-slate-700 text-xs">{row.name}</span>
                                                    {row.code && <span className="text-slate-400 text-[10px] ml-2">{row.code}</span>}
                                                </td>
                                                <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-700">
                                                    {formatCurrencyPrecise(row.amount, currency)}
                                                </td>
                                                {hasComparison && (
                                                    <>
                                                        <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-500">
                                                            {formatCurrencyPrecise(row.compareAmount || 0, currency)}
                                                        </td>
                                                        <td className="px-4 sm:px-6 py-2.5 text-right">
                                                            {row.compareAmount != null && row.compareAmount !== 0 && (
                                                                <TrendBadge value={((row.amount - row.compareAmount) / Math.abs(row.compareAmount)) * 100} inverse />
                                                            )}
                                                        </td>
                                                    </>
                                                )}
                                            </tr>
                                        ))}
                                        {expenseRows.length === 0 && (
                                            <tr><td colSpan={hasComparison ? 4 : 2} className="px-4 sm:px-6 py-2.5 text-xs text-slate-400 italic">No expenses recorded</td></tr>
                                        )}
                                        <tr className="bg-slate-100 font-medium">
                                            <td className="px-4 sm:px-6 py-2.5 text-xs text-slate-700">Total Expenses</td>
                                            <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-rose-500 font-semibold">
                                                {formatCurrencyPrecise(kpi.expenses, currency)}
                                            </td>
                                            {hasComparison && (
                                                <>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right text-xs text-slate-500">
                                                        {formatCurrencyPrecise(compareExpenses || 0, currency)}
                                                    </td>
                                                    <td className="px-4 sm:px-6 py-2.5 text-right">
                                                        <TrendBadge value={kpi.changeExpensesPct} inverse />
                                                    </td>
                                                </>
                                            )}
                                        </tr>

                                        {/* Net Income */}
                                        <tr className="bg-slate-900 font-bold text-white">
                                            <td className="px-4 sm:px-6 py-3 text-xs">Net Income</td>
                                            <td className={`px-4 sm:px-6 py-3 text-right text-xs ${kpi.netIncome >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                {formatCurrencyPrecise(kpi.netIncome, currency)}
                                            </td>
                                            {hasComparison && (
                                                <>
                                                    <td className="px-4 sm:px-6 py-3 text-right text-xs text-slate-300">
                                                        {formatCurrencyPrecise(compareNetIncome || 0, currency)}
                                                    </td>
                                                    <td className="px-4 sm:px-6 py-3 text-right">
                                                        {kpi.changeNetIncomePct != null && (
                                                            <span className={`text-[11px] font-medium ${kpi.changeNetIncomePct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                                {kpi.changeNetIncomePct >= 0 ? '↑' : '↓'} {Math.abs(kpi.changeNetIncomePct).toFixed(1)}%
                                                            </span>
                                                        )}
                                                    </td>
                                                </>
                                            )}
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    </>
                )}
            </div>
        </div>
    );
};

export default ProfitAndLossReportPage;
