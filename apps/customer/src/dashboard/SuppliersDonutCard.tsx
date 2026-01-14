import React, { useMemo } from "react";

interface SupplierData {
    name: string;
    mtdSpend?: number;
    paymentCount?: number;
    category?: string;
}

interface SuppliersCardProps {
    suppliers: SupplierData[];
    currency?: string;
    suppliersUrl?: string;
}

/**
 * Suppliers card with compact card grid layout.
 */
export const SuppliersDonutCard: React.FC<SuppliersCardProps> = ({
    suppliers,
    currency = "USD",
    suppliersUrl = "#",
}) => {
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

            {/* Supplier Cards Grid */}
            <div className="grid gap-3 sm:grid-cols-2">
                {suppliers.slice(0, 4).map((supplier, idx) => (
                    <div
                        key={`${supplier.name}-${idx}`}
                        className="rounded-2xl bg-slate-50/80 border border-slate-100 px-4 py-3 transition-all hover:bg-slate-50 hover:border-slate-200"
                    >
                        <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold text-slate-900 truncate">
                                    {supplier.name}
                                </p>
                                <p className="text-[11px] text-slate-500 truncate">
                                    {supplier.category || "Uncategorized"}
                                </p>
                            </div>
                            <div className="text-right shrink-0">
                                <p className="text-sm font-bold text-slate-900 font-mono-soft">
                                    {formatMoney(supplier.mtdSpend)}
                                </p>
                                <p className="text-[10px] text-slate-400">
                                    <span className="font-mono-soft">{supplier.paymentCount || 0}</span> payment{(supplier.paymentCount || 0) !== 1 ? "s" : ""}
                                </p>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Footer Summary */}
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-xs text-slate-500">
                    Total: <span className="font-semibold text-slate-700 font-mono-soft">{formatMoney(totalSpend)}</span>
                </span>
                <span className="text-xs text-slate-400">
                    <span className="font-mono-soft">{totalPayments}</span> payment{totalPayments !== 1 ? "s" : ""} this month
                </span>
            </div>
        </div>
    );
};

export default SuppliersDonutCard;
