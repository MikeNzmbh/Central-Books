import React, { useMemo } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface PLMonthOption {
    value: string;
    label: string;
}

interface PLSnapshotCardProps {
    revenue?: number;
    expenses?: number;
    netProfit?: number;
    currency?: string;
    periodLabel?: string;
    selectedMonth?: string;
    monthOptions?: PLMonthOption[];
    prevRevenue?: number | null;
    prevExpenses?: number | null;
    prevNet?: number | null;
    revenueHistory?: number[];
    expensesHistory?: number[];
    profitAndLossUrl?: string;
    showNoActivity?: boolean;
    noActivityMessage?: string;
}

/**
 * P&L Snapshot card with sparkline trends and margin indicator.
 */
export const PLSnapshotCard: React.FC<PLSnapshotCardProps> = ({
    revenue = 0,
    expenses = 0,
    netProfit = 0,
    currency = "USD",
    periodLabel = "This Month",
    selectedMonth = "",
    monthOptions = [],
    prevRevenue = null,
    prevExpenses = null,
    prevNet = null,
    revenueHistory = [],
    expensesHistory = [],
    profitAndLossUrl = "#",
    showNoActivity = false,
    noActivityMessage,
}) => {
    const formatter = useMemo(() => {
        try {
            return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 });
        } catch {
            return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
        }
    }, [currency]);

    const formatMoney = (value: number) => formatter.format(value);

    // Calculate margin percentage
    const margin = revenue > 0 ? ((revenue - expenses) / revenue) * 100 : 0;
    const marginCapped = Math.min(100, Math.max(0, margin));

    // Calculate trend vs previous period
    const revenueTrend = prevRevenue !== null && prevRevenue > 0
        ? ((revenue - prevRevenue) / prevRevenue) * 100
        : null;
    const expensesTrend = prevExpenses !== null && prevExpenses > 0
        ? ((expenses - prevExpenses) / prevExpenses) * 100
        : null;

    // Generate sparkline path
    const generateSparkline = (data: number[], height: number = 20, width: number = 60): string => {
        if (data.length < 2) return "";

        const max = Math.max(...data, 1);
        const min = Math.min(...data, 0);
        const range = max - min || 1;

        const points = data.map((value, idx) => {
            const x = (idx / (data.length - 1)) * width;
            const y = height - ((value - min) / range) * height;
            return `${x},${y}`;
        });

        return `M${points.join(" L")}`;
    };

    const revenueSparkline = generateSparkline(revenueHistory.length > 1 ? revenueHistory : [0, revenue]);
    const expensesSparkline = generateSparkline(expensesHistory.length > 1 ? expensesHistory : [0, expenses]);

    if (showNoActivity) {
        return (
            <div className="rounded-3xl border border-slate-100 bg-white/90 p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <p className="text-xs font-medium text-slate-500">Profit & Loss</p>
                        <p className="text-sm text-slate-400">{periodLabel}</p>
                    </div>
                    <a
                        href={profitAndLossUrl}
                        className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-white"
                    >
                        Open P&L →
                    </a>
                </div>
                <div className="rounded-2xl bg-slate-50 border border-slate-100 px-4 py-6 text-center">
                    <p className="text-sm text-slate-500">
                        {noActivityMessage || "No income or expenses recorded for this period"}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                        Create entries or categorize bank transactions to see P&L data.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-3xl border border-slate-100 bg-white/90 p-5 shadow-sm">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <p className="text-xs font-medium text-slate-500">Profit & Loss</p>
                </div>
                <a
                    href={profitAndLossUrl}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-white transition-colors"
                >
                    Open P&L →
                </a>
            </div>

            {/* Period Selector */}
            {monthOptions.length > 0 && (
                <div className="mb-4">
                    <select
                        value={selectedMonth}
                        onChange={(e) => {
                            window.location.href = `/dashboard/?pl_month=${e.target.value}`;
                        }}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300 transition-colors hover:bg-white"
                    >
                        {monthOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </div>
            )}

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-3 mb-4">
                {/* Revenue */}
                <div className="rounded-2xl bg-emerald-50/50 border border-emerald-100 p-3">
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-[10px] font-medium text-emerald-600 uppercase tracking-wider">Revenue</p>
                            <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(revenue)}</p>
                        </div>
                        <svg width="40" height="20" className="mt-1">
                            <path
                                d={revenueSparkline}
                                fill="none"
                                stroke="#10b981"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                    </div>
                    {revenueTrend !== null && (
                        <div className={`mt-1 flex items-center gap-1 text-[10px] font-medium ${revenueTrend >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                            {revenueTrend >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                            <span>{revenueTrend >= 0 ? "+" : ""}{revenueTrend.toFixed(0)}% vs prior</span>
                        </div>
                    )}
                </div>

                {/* Expenses */}
                <div className="rounded-2xl bg-rose-50/50 border border-rose-100 p-3">
                    <div className="flex items-start justify-between">
                        <div>
                            <p className="text-[10px] font-medium text-rose-600 uppercase tracking-wider">Expenses</p>
                            <p className="mt-1 text-lg font-bold text-slate-900">{formatMoney(expenses)}</p>
                        </div>
                        <svg width="40" height="20" className="mt-1">
                            <path
                                d={expensesSparkline}
                                fill="none"
                                stroke="#f43f5e"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            />
                        </svg>
                    </div>
                    {expensesTrend !== null && (
                        <div className={`mt-1 flex items-center gap-1 text-[10px] font-medium ${expensesTrend <= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                            {expensesTrend <= 0 ? <TrendingDown className="h-3 w-3" /> : <TrendingUp className="h-3 w-3" />}
                            <span>{expensesTrend >= 0 ? "+" : ""}{expensesTrend.toFixed(0)}% vs prior</span>
                        </div>
                    )}
                </div>

                {/* Net Profit */}
                <div className={`rounded-2xl p-3 ${netProfit >= 0 ? "bg-indigo-50/50 border border-indigo-100" : "bg-amber-50/50 border border-amber-100"}`}>
                    <p className={`text-[10px] font-medium uppercase tracking-wider ${netProfit >= 0 ? "text-indigo-600" : "text-amber-600"}`}>
                        Net Profit
                    </p>
                    <p className={`mt-1 text-lg font-bold ${netProfit >= 0 ? "text-slate-900" : "text-amber-700"}`}>
                        {formatMoney(netProfit)}
                    </p>
                    <p className="mt-1 text-[10px] font-medium text-slate-500">
                        {margin.toFixed(0)}% margin
                    </p>
                </div>
            </div>

            {/* Margin Progress Bar */}
            <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[10px]">
                    <span className="text-slate-500">Profit Margin</span>
                    <span className="font-semibold text-slate-700">{margin.toFixed(1)}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                        className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-500"
                        style={{ width: `${marginCapped}%` }}
                    />
                </div>
                <div className="flex justify-between text-[9px] text-slate-400">
                    <span>0%</span>
                    <span>50%</span>
                    <span>100%</span>
                </div>
            </div>
        </div>
    );
};

export default PLSnapshotCard;
