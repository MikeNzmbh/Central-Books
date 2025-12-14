import React, { useState, useMemo } from "react";

interface SupplierData {
    name: string;
    mtdSpend?: number;
    paymentCount?: number;
    category?: string;
}

interface SuppliersDonutCardProps {
    suppliers: SupplierData[];
    currency?: string;
    suppliersUrl?: string;
}

const COLORS = [
    { bg: "bg-indigo-500", text: "text-indigo-600", light: "bg-indigo-100" },
    { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-100" },
    { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-100" },
    { bg: "bg-rose-500", text: "text-rose-600", light: "bg-rose-100" },
    { bg: "bg-sky-500", text: "text-sky-600", light: "bg-sky-100" },
];

/**
 * Suppliers card with interactive donut chart visualization.
 * Hover over donut segments or list items to highlight.
 */
export const SuppliersDonutCard: React.FC<SuppliersDonutCardProps> = ({
    suppliers,
    currency = "USD",
    suppliersUrl = "#",
}) => {
    const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

    const formatter = useMemo(() => {
        try {
            return new Intl.NumberFormat(undefined, { style: "currency", currency });
        } catch {
            return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" });
        }
    }, [currency]);

    const formatMoney = (value?: number) => formatter.format(value || 0);

    const totalSpend = useMemo(
        () => suppliers.reduce((sum, s) => sum + (s.mtdSpend || 0), 0),
        [suppliers]
    );

    const totalPayments = useMemo(
        () => suppliers.reduce((sum, s) => sum + (s.paymentCount || 0), 0),
        [suppliers]
    );

    // Generate donut segments
    const segments = useMemo(() => {
        if (!suppliers.length || totalSpend === 0) return [];

        let cumulativePercent = 0;
        return suppliers.slice(0, 5).map((supplier, idx) => {
            const percent = totalSpend > 0 ? ((supplier.mtdSpend || 0) / totalSpend) * 100 : 0;
            const startPercent = cumulativePercent;
            cumulativePercent += percent;

            return {
                ...supplier,
                percent,
                startPercent,
                endPercent: cumulativePercent,
                color: COLORS[idx % COLORS.length],
            };
        });
    }, [suppliers, totalSpend]);

    // SVG donut chart
    const radius = 40;
    const circumference = 2 * Math.PI * radius;

    if (!suppliers.length) {
        return (
            <div className="rounded-3xl border border-slate-100 bg-white/90 p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <p className="text-xs font-medium text-slate-500">Suppliers</p>
                        <p className="text-sm text-slate-400">This Month</p>
                    </div>
                    <a
                        href={suppliersUrl}
                        className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-white"
                    >
                        Manage →
                    </a>
                </div>
                <div className="flex items-center justify-center py-8 text-sm text-slate-400">
                    No supplier activity this month
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-3xl border border-slate-100 bg-white/90 p-5 shadow-sm">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <p className="text-xs font-medium text-slate-500">Suppliers</p>
                    <p className="text-sm text-slate-400">This Month</p>
                </div>
                <a
                    href={suppliersUrl}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-white transition-colors"
                >
                    Manage →
                </a>
            </div>

            <div className="flex gap-6">
                {/* Donut Chart */}
                <div className="relative flex-shrink-0">
                    <svg width="100" height="100" viewBox="0 0 100 100" className="transform -rotate-90">
                        {/* Background circle */}
                        <circle
                            cx="50"
                            cy="50"
                            r={radius}
                            fill="none"
                            stroke="#f1f5f9"
                            strokeWidth="12"
                        />
                        {/* Segments */}
                        {segments.map((segment, idx) => {
                            const offset = circumference * (segment.startPercent / 100);
                            const length = circumference * (segment.percent / 100);
                            const isHovered = hoveredIndex === idx;

                            return (
                                <circle
                                    key={segment.name}
                                    cx="50"
                                    cy="50"
                                    r={radius}
                                    fill="none"
                                    stroke={isHovered ? "#1e293b" : `url(#gradient-${idx})`}
                                    strokeWidth={isHovered ? "14" : "12"}
                                    strokeDasharray={`${length} ${circumference - length}`}
                                    strokeDashoffset={-offset}
                                    strokeLinecap="round"
                                    className="transition-all duration-200 cursor-pointer"
                                    onMouseEnter={() => setHoveredIndex(idx)}
                                    onMouseLeave={() => setHoveredIndex(null)}
                                />
                            );
                        })}
                        {/* Gradient definitions */}
                        <defs>
                            {segments.map((_, idx) => (
                                <linearGradient key={idx} id={`gradient-${idx}`}>
                                    <stop offset="0%" stopColor={
                                        idx === 0 ? "#6366f1" :
                                            idx === 1 ? "#10b981" :
                                                idx === 2 ? "#f59e0b" :
                                                    idx === 3 ? "#f43f5e" : "#0ea5e9"
                                    } />
                                    <stop offset="100%" stopColor={
                                        idx === 0 ? "#818cf8" :
                                            idx === 1 ? "#34d399" :
                                                idx === 2 ? "#fbbf24" :
                                                    idx === 3 ? "#fb7185" : "#38bdf8"
                                    } />
                                </linearGradient>
                            ))}
                        </defs>
                    </svg>

                    {/* Center text */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-lg font-bold text-slate-900">
                            {hoveredIndex !== null
                                ? `${Math.round(segments[hoveredIndex]?.percent || 0)}%`
                                : totalPayments
                            }
                        </span>
                        <span className="text-[10px] text-slate-500">
                            {hoveredIndex !== null ? "of total" : "payments"}
                        </span>
                    </div>
                </div>

                {/* Supplier List */}
                <div className="flex-1 space-y-1.5">
                    {segments.map((segment, idx) => {
                        const isHovered = hoveredIndex === idx;
                        const barWidth = segment.percent;

                        return (
                            <div
                                key={segment.name}
                                className={`flex items-center justify-between rounded-xl px-2.5 py-1.5 transition-all cursor-pointer ${isHovered ? "bg-slate-100 scale-[1.02]" : "hover:bg-slate-50"
                                    }`}
                                onMouseEnter={() => setHoveredIndex(idx)}
                                onMouseLeave={() => setHoveredIndex(null)}
                            >
                                <div className="flex items-center gap-2 min-w-0 flex-1">
                                    <div className={`h-2 w-2 rounded-full ${segment.color.bg}`} />
                                    <div className="min-w-0 flex-1">
                                        <p className="text-xs font-medium text-slate-900 truncate">{segment.name}</p>
                                        <div className="mt-0.5 h-1 w-full rounded-full bg-slate-100 overflow-hidden">
                                            <div
                                                className={`h-full rounded-full transition-all duration-300 ${segment.color.bg}`}
                                                style={{ width: `${barWidth}%` }}
                                            />
                                        </div>
                                    </div>
                                </div>
                                <span className="ml-2 text-xs font-semibold text-slate-700 tabular-nums">
                                    {formatMoney(segment.mtdSpend)}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Footer */}
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-xs text-slate-500">
                    Total: <span className="font-medium text-slate-700">{formatMoney(totalSpend)}</span> across {totalPayments} payment{totalPayments !== 1 ? "s" : ""}
                </span>
            </div>
        </div>
    );
};

export default SuppliersDonutCard;
