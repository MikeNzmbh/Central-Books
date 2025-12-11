import React, { useCallback, useEffect, useMemo, useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
//    Types
// ─────────────────────────────────────────────────────────────────────────────

type InvoiceStatus = "DRAFT" | "SENT" | "PARTIAL" | "PAID" | "VOID";

interface Invoice {
    id: number;
    invoice_number: string;
    customer_id: number | null;
    customer_name: string | null;
    status: InvoiceStatus;
    issue_date: string | null;
    due_date: string | null;
    net_total: string;
    tax_total: string;
    grand_total: string;
    amount_paid: string;
    currency: string;
}

interface InvoiceStats {
    open_balance_total: string;
    revenue_ytd: string;
    total_invoices: number;
    avg_invoice_value: string;
}

interface StatusChoice {
    value: string;
    label: string;
}

interface ApiResponse {
    invoices: Invoice[];
    stats: InvoiceStats;
    status_filter: string;
    selected_invoice: Invoice | null;
    currency: string;
    status_choices: StatusChoice[];
    error?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
//    Helpers
// ─────────────────────────────────────────────────────────────────────────────

const statusColor: Record<InvoiceStatus, { bg: string; dot: string }> = {
    DRAFT: { bg: "bg-slate-50 text-slate-700 border border-slate-200", dot: "bg-slate-400" },
    SENT: { bg: "bg-sky-50 text-sky-700 border border-sky-200", dot: "bg-sky-500" },
    PARTIAL: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500" },
    PAID: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500" },
    VOID: { bg: "bg-rose-50 text-rose-700 border border-rose-200", dot: "bg-rose-500" },
};

const StatusBadge: React.FC<{ status: InvoiceStatus }> = ({ status }) => {
    const config = statusColor[status] || { bg: "bg-slate-50 text-slate-600 border border-slate-200", dot: "bg-slate-400" };
    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${config.bg}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
            {status}
        </span>
    );
};

const formatDate = (iso: string | null) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString();
};

const formatCurrency = (amount: string, currency: string) => {
    const num = parseFloat(amount);
    if (isNaN(num)) return amount;
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: currency || "USD",
        minimumFractionDigits: 2,
    }).format(num);
};

const isOverdue = (dueDate: string | null, status: InvoiceStatus): boolean => {
    if (!dueDate) return false;
    if (status === "PAID" || status === "VOID" || status === "DRAFT") return false;
    return new Date(dueDate) < new Date();
};

// ─────────────────────────────────────────────────────────────────────────────
//    Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function InvoicesListPage({ defaultCurrency = "USD" }: { defaultCurrency?: string }) {
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [stats, setStats] = useState<InvoiceStats | null>(null);
    const [statusFilter, setStatusFilter] = useState("all");
    const [statusChoices, setStatusChoices] = useState<StatusChoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
    const [currency, setCurrency] = useState(defaultCurrency);

    // Date range filters
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const loadInvoices = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            params.set("status", statusFilter);
            if (startDate) params.set("start", startDate);
            if (endDate) params.set("end", endDate);

            const res = await fetch(`/api/invoices/list/?${params.toString()}`);
            const json: ApiResponse = await res.json();

            if (!res.ok || json.error) {
                throw new Error(json.error || "Failed to load invoices");
            }

            setInvoices(json.invoices || []);
            setStats(json.stats || null);
            setStatusChoices(json.status_choices || []);
            setCurrency(json.currency || defaultCurrency);
        } catch (err: any) {
            setError(err.message || "Failed to load invoices");
        } finally {
            setLoading(false);
        }
    }, [statusFilter, startDate, endDate, defaultCurrency]);

    useEffect(() => {
        loadInvoices();
    }, [loadInvoices]);

    const handleStatusChange = (newStatus: string) => {
        setStatusFilter(newStatus);
    };

    const handleRowClick = (invoice: Invoice) => {
        setSelectedInvoice(selectedInvoice?.id === invoice.id ? null : invoice);
    };

    // Compute summary stats
    const overdueCount = useMemo(() => {
        return invoices.filter(inv => isOverdue(inv.due_date, inv.status)).length;
    }, [invoices]);

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">Accounting</p>
                        <h1 className="text-2xl font-semibold">Invoices</h1>
                        <p className="text-sm text-slate-500">Track what you've billed and what's still unpaid.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={loadInvoices}
                            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                        >
                            Refresh
                        </button>
                        <a
                            href="/invoices/new/"
                            className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
                        >
                            + New Invoice
                        </a>
                    </div>
                </div>

                {/* Error Banner */}
                {error && (
                    <div className="rounded-lg bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3">
                        {error}
                    </div>
                )}

                {/* KPI Cards */}
                {stats && (
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Open Balance</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.open_balance_total, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Unpaid invoices</p>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Revenue (YTD)</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.revenue_ytd, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Paid invoices this year</p>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Total Invoices</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">{stats.total_invoices}</div>
                            <p className="text-xs text-slate-500 mt-1">All time</p>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Avg Invoice</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.avg_invoice_value, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Average value</p>
                        </div>
                    </div>
                )}

                {/* Filters */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="flex flex-wrap items-center gap-4">
                        <div className="flex items-center gap-2">
                            <label className="text-sm font-medium text-slate-700">Status:</label>
                            <select
                                value={statusFilter}
                                onChange={(e) => handleStatusChange(e.target.value)}
                                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                            >
                                <option value="all">All</option>
                                <option value="overdue">Overdue</option>
                                {statusChoices.map((choice) => (
                                    <option key={choice.value} value={choice.value.toLowerCase()}>
                                        {choice.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-sm font-medium text-slate-700">From:</label>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-sm font-medium text-slate-700">To:</label>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                            />
                        </div>
                        {overdueCount > 0 && (
                            <div className="ml-auto">
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                                    {overdueCount} overdue
                                </span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Invoices Table */}
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                    {loading ? (
                        <div className="p-8 text-center text-slate-500">Loading invoices...</div>
                    ) : invoices.length === 0 ? (
                        <div className="p-8 text-center text-slate-500">
                            No invoices found. <a href="/invoices/new/" className="text-sky-600 hover:underline">Create your first invoice</a>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-slate-50 border-b border-slate-200">
                                    <tr className="text-xs uppercase text-slate-500">
                                        <th className="px-4 py-3 font-medium">Invoice #</th>
                                        <th className="px-4 py-3 font-medium">Customer</th>
                                        <th className="px-4 py-3 font-medium">Issue Date</th>
                                        <th className="px-4 py-3 font-medium">Due Date</th>
                                        <th className="px-4 py-3 font-medium text-right">Amount</th>
                                        <th className="px-4 py-3 font-medium">Status</th>
                                        <th className="px-4 py-3 font-medium"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {invoices.map((invoice) => {
                                        const overdue = isOverdue(invoice.due_date, invoice.status);
                                        const isSelected = selectedInvoice?.id === invoice.id;
                                        return (
                                            <tr
                                                key={invoice.id}
                                                onClick={() => handleRowClick(invoice)}
                                                className={`border-b border-slate-100 cursor-pointer transition-colors ${isSelected ? "bg-sky-50" : "hover:bg-slate-50"
                                                    } ${overdue ? "bg-rose-50/50" : ""}`}
                                            >
                                                <td className="px-4 py-3 font-semibold text-slate-800">
                                                    {invoice.invoice_number || `#${invoice.id}`}
                                                </td>
                                                <td className="px-4 py-3 text-slate-600">
                                                    {invoice.customer_name || "—"}
                                                </td>
                                                <td className="px-4 py-3 text-slate-600">
                                                    {formatDate(invoice.issue_date)}
                                                </td>
                                                <td className={`px-4 py-3 ${overdue ? "text-rose-600 font-medium" : "text-slate-600"}`}>
                                                    {formatDate(invoice.due_date)}
                                                    {overdue && <span className="ml-1 text-xs">⚠️</span>}
                                                </td>
                                                <td className="px-4 py-3 text-right font-medium text-slate-800">
                                                    {formatCurrency(invoice.grand_total, invoice.currency || currency)}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <StatusBadge status={invoice.status} />
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center gap-2">
                                                        <a
                                                            href={`/invoices/${invoice.id}/edit/`}
                                                            onClick={(e) => e.stopPropagation()}
                                                            className="text-xs font-medium text-sky-600 hover:text-sky-800"
                                                        >
                                                            Edit
                                                        </a>
                                                        <a
                                                            href={`/invoices/${invoice.id}/pdf/`}
                                                            onClick={(e) => e.stopPropagation()}
                                                            className="text-xs font-medium text-slate-500 hover:text-slate-700"
                                                        >
                                                            PDF
                                                        </a>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Selected Invoice Detail Panel */}
                {selectedInvoice && (
                    <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-slate-800">
                                    Invoice {selectedInvoice.invoice_number || `#${selectedInvoice.id}`}
                                </h3>
                                <p className="text-sm text-slate-500">
                                    {selectedInvoice.customer_name || "No customer"}
                                </p>
                            </div>
                            <StatusBadge status={selectedInvoice.status} />
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Issue Date</div>
                                <div className="font-medium text-slate-800">{formatDate(selectedInvoice.issue_date)}</div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Due Date</div>
                                <div className={`font-medium ${isOverdue(selectedInvoice.due_date, selectedInvoice.status) ? "text-rose-600" : "text-slate-800"}`}>
                                    {formatDate(selectedInvoice.due_date)}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Net Total</div>
                                <div className="font-medium text-slate-800">
                                    {formatCurrency(selectedInvoice.net_total, selectedInvoice.currency || currency)}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Grand Total</div>
                                <div className="font-semibold text-slate-900">
                                    {formatCurrency(selectedInvoice.grand_total, selectedInvoice.currency || currency)}
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                            <a
                                href={`/invoices/${selectedInvoice.id}/edit/`}
                                className="px-4 py-2 text-sm font-medium text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
                            >
                                Edit Invoice
                            </a>
                            <a
                                href={`/invoices/${selectedInvoice.id}/pdf/`}
                                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                            >
                                Download PDF
                            </a>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
