import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    X,
    FileText,
    Mail,
    Printer,
    CreditCard,
    Calendar,
    User,
    DollarSign,
    ChevronRight,
    ExternalLink,
    Copy,
    Send,
    Clock,
    AlertTriangle,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
//    Types
// ─────────────────────────────────────────────────────────────────────────────

type InvoiceStatus = "DRAFT" | "SENT" | "PARTIAL" | "PAID" | "VOID";
type DrawerTab = "details" | "payments" | "actions";

interface Invoice {
    id: number;
    invoice_number: string;
    customer_id: number | null;
    customer_name: string | null;
    customer_email?: string | null;
    status: InvoiceStatus;
    issue_date: string | null;
    due_date: string | null;
    net_total: string;
    tax_total: string;
    grand_total: string;
    amount_paid: string;
    currency: string;
    memo?: string | null;
    terms?: string | null;
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

const statusColor: Record<InvoiceStatus, { bg: string; dot: string; label: string }> = {
    DRAFT: { bg: "bg-slate-50 text-slate-700 border border-slate-200", dot: "bg-slate-400", label: "Draft" },
    SENT: { bg: "bg-sky-50 text-sky-700 border border-sky-200", dot: "bg-sky-500", label: "Sent" },
    PARTIAL: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500", label: "Partial" },
    PAID: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500", label: "Paid" },
    VOID: { bg: "bg-rose-50 text-rose-700 border border-rose-200", dot: "bg-rose-500", label: "Void" },
};

const StatusBadge: React.FC<{ status: InvoiceStatus }> = ({ status }) => {
    const config = statusColor[status] || { bg: "bg-slate-50 text-slate-600 border border-slate-200", dot: "bg-slate-400", label: status };
    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${config.bg}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
            {config.label}
        </span>
    );
};

const formatDate = (iso: string | null) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "2-digit" });
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

const getDaysOverdue = (dueDate: string | null): number => {
    if (!dueDate) return 0;
    const diff = new Date().getTime() - new Date(dueDate).getTime();
    return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
};

const getBalanceDue = (invoice: Invoice): number => {
    const total = parseFloat(invoice.grand_total) || 0;
    const paid = parseFloat(invoice.amount_paid) || 0;
    return Math.max(0, total - paid);
};

const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(" ");

// ─────────────────────────────────────────────────────────────────────────────
//    Invoice Drawer Component
// ─────────────────────────────────────────────────────────────────────────────

interface InvoiceDrawerProps {
    invoice: Invoice;
    currency: string;
    onClose: () => void;
}

const InvoiceDrawer: React.FC<InvoiceDrawerProps> = ({ invoice, currency, onClose }) => {
    const [activeTab, setActiveTab] = useState<DrawerTab>("details");
    const overdue = isOverdue(invoice.due_date, invoice.status);
    const daysOverdue = getDaysOverdue(invoice.due_date);
    const balanceDue = getBalanceDue(invoice);

    const handleCopyInvoiceNumber = () => {
        navigator.clipboard.writeText(invoice.invoice_number || `INV-${invoice.id}`);
    };

    return (
        <motion.div
            className="fixed inset-0 z-50 flex justify-end"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
        >
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Drawer */}
            <motion.div
                className="relative h-full w-full max-w-md bg-white shadow-2xl flex flex-col"
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", damping: 30, stiffness: 300 }}
            >
                {/* Header */}
                <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
                    <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                            <h2 className="text-lg font-bold text-slate-900">
                                {invoice.invoice_number || `INV-${invoice.id}`}
                            </h2>
                            <button
                                onClick={handleCopyInvoiceNumber}
                                className="p-1 rounded hover:bg-slate-100 transition-colors"
                                title="Copy invoice number"
                            >
                                <Copy className="h-3.5 w-3.5 text-slate-400" />
                            </button>
                        </div>
                        <div className="flex items-center gap-3">
                            <StatusBadge status={invoice.status} />
                            {overdue && (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-600">
                                    <AlertTriangle className="h-3 w-3" />
                                    {daysOverdue}d overdue
                                </span>
                            )}
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-full hover:bg-slate-100 transition-colors"
                    >
                        <X className="h-5 w-5 text-slate-500" />
                    </button>
                </div>

                {/* Amount Summary */}
                <div className="border-b border-slate-100 px-6 py-4 bg-slate-50/50">
                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Total</div>
                            <div className="text-[15px] font-bold text-slate-900 mt-0.5">
                                {formatCurrency(invoice.grand_total, invoice.currency || currency)}
                            </div>
                        </div>
                        <div>
                            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Paid</div>
                            <div className="text-[15px] font-bold text-emerald-600 mt-0.5">
                                {formatCurrency(invoice.amount_paid, invoice.currency || currency)}
                            </div>
                        </div>
                        <div>
                            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Balance</div>
                            <div className={cn(
                                "text-[15px] font-bold mt-0.5",
                                balanceDue > 0 ? (overdue ? "text-rose-600" : "text-amber-600") : "text-slate-400"
                            )}>
                                {formatCurrency(String(balanceDue), invoice.currency || currency)}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div className="border-b border-slate-100 px-6">
                    <div className="flex gap-1 -mb-px">
                        {(["details", "payments", "actions"] as DrawerTab[]).map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={cn(
                                    "px-4 py-3 text-xs font-semibold capitalize border-b-2 transition-colors",
                                    activeTab === tab
                                        ? "border-slate-900 text-slate-900"
                                        : "border-transparent text-slate-500 hover:text-slate-700"
                                )}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Tab Content */}
                <div className="flex-1 overflow-y-auto">
                    {activeTab === "details" && (
                        <div className="p-6 space-y-5">
                            {/* Customer */}
                            <div className="space-y-2">
                                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Customer</h4>
                                <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100">
                                    <div className="h-9 w-9 rounded-full bg-slate-200 flex items-center justify-center">
                                        <User className="h-4 w-4 text-slate-500" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="font-semibold text-slate-900 truncate">
                                            {invoice.customer_name || "Walk-in Customer"}
                                        </div>
                                        {invoice.customer_email && (
                                            <div className="text-xs text-slate-500 truncate">{invoice.customer_email}</div>
                                        )}
                                    </div>
                                    {invoice.customer_id && (
                                        <a
                                            href={`/customers/${invoice.customer_id}/`}
                                            className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors"
                                        >
                                            <ExternalLink className="h-4 w-4 text-slate-400" />
                                        </a>
                                    )}
                                </div>
                            </div>

                            {/* Dates */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Issue Date</h4>
                                    <div className="flex items-center gap-2 text-sm text-slate-900">
                                        <Calendar className="h-4 w-4 text-slate-400" />
                                        {formatDate(invoice.issue_date)}
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Due Date</h4>
                                    <div className={cn(
                                        "flex items-center gap-2 text-sm",
                                        overdue ? "text-rose-600 font-medium" : "text-slate-900"
                                    )}>
                                        <Clock className="h-4 w-4" />
                                        {formatDate(invoice.due_date)}
                                    </div>
                                </div>
                            </div>

                            {/* Amounts Breakdown */}
                            <div className="space-y-2">
                                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Amount Breakdown</h4>
                                <div className="rounded-xl border border-slate-100 divide-y divide-slate-100">
                                    <div className="flex items-center justify-between px-4 py-2.5">
                                        <span className="text-sm text-slate-600">Subtotal</span>
                                        <span className="text-sm font-medium text-slate-900">
                                            {formatCurrency(invoice.net_total, invoice.currency || currency)}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between px-4 py-2.5">
                                        <span className="text-sm text-slate-600">Tax</span>
                                        <span className="text-sm font-medium text-slate-900">
                                            {formatCurrency(invoice.tax_total, invoice.currency || currency)}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50">
                                        <span className="text-sm font-semibold text-slate-900">Total</span>
                                        <span className="text-sm font-bold text-slate-900">
                                            {formatCurrency(invoice.grand_total, invoice.currency || currency)}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Notes */}
                            {invoice.memo && (
                                <div className="space-y-2">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Notes</h4>
                                    <p className="text-sm text-slate-600 bg-slate-50 rounded-xl p-3 border border-slate-100">
                                        {invoice.memo}
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === "payments" && (
                        <div className="p-6 space-y-5">
                            {/* Payment Status */}
                            <div className="rounded-xl border border-slate-100 p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium text-slate-600">Amount Paid</span>
                                    <span className="text-sm font-bold text-emerald-600">
                                        {formatCurrency(invoice.amount_paid, invoice.currency || currency)}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium text-slate-600">Balance Due</span>
                                    <span className={cn(
                                        "text-sm font-bold",
                                        balanceDue > 0 ? "text-amber-600" : "text-slate-400"
                                    )}>
                                        {formatCurrency(String(balanceDue), invoice.currency || currency)}
                                    </span>
                                </div>
                                {/* Progress bar */}
                                <div className="space-y-1.5">
                                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                                        <div
                                            className="h-full bg-emerald-500 rounded-full transition-all"
                                            style={{
                                                width: `${Math.min(100, (parseFloat(invoice.amount_paid) / parseFloat(invoice.grand_total)) * 100)}%`
                                            }}
                                        />
                                    </div>
                                    <div className="text-[10px] text-slate-500 text-right">
                                        {Math.round((parseFloat(invoice.amount_paid) / parseFloat(invoice.grand_total)) * 100) || 0}% paid
                                    </div>
                                </div>
                            </div>

                            {/* Payment History Placeholder */}
                            <div className="space-y-2">
                                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Payment History</h4>
                                {parseFloat(invoice.amount_paid) > 0 ? (
                                    <div className="rounded-xl border border-slate-100 p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="h-8 w-8 rounded-full bg-emerald-50 flex items-center justify-center">
                                                <CreditCard className="h-4 w-4 text-emerald-600" />
                                            </div>
                                            <div className="flex-1">
                                                <div className="text-sm font-medium text-slate-900">Payment received</div>
                                                <div className="text-xs text-slate-500">View full details in customer ledger</div>
                                            </div>
                                            <div className="text-sm font-bold text-emerald-600">
                                                {formatCurrency(invoice.amount_paid, invoice.currency || currency)}
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center">
                                        <div className="text-sm text-slate-500">No payments recorded yet</div>
                                    </div>
                                )}
                            </div>

                            {/* Record Payment CTA */}
                            {balanceDue > 0 && (
                                <a
                                    href={`/invoices/${invoice.id}/receive-payment/`}
                                    className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl bg-emerald-600 text-white font-semibold text-sm hover:bg-emerald-700 transition-colors"
                                >
                                    <DollarSign className="h-4 w-4" />
                                    Record Payment
                                </a>
                            )}
                        </div>
                    )}

                    {activeTab === "actions" && (
                        <div className="p-6 space-y-3">
                            <a
                                href={`/invoices/${invoice.id}/edit/`}
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors"
                            >
                                <FileText className="h-5 w-5 text-slate-500" />
                                <div className="flex-1 text-left">
                                    <div className="text-sm font-semibold text-slate-900">Edit Invoice</div>
                                    <div className="text-xs text-slate-500">Modify line items, dates, or terms</div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                            </a>

                            <a
                                href={`/invoices/${invoice.id}/pdf/`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors"
                            >
                                <Printer className="h-5 w-5 text-slate-500" />
                                <div className="flex-1 text-left">
                                    <div className="text-sm font-semibold text-slate-900">Download PDF</div>
                                    <div className="text-xs text-slate-500">Print or save invoice</div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                            </a>

                            {invoice.customer_email && (
                                <button
                                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors"
                                    onClick={() => window.open(`mailto:${invoice.customer_email}?subject=Invoice ${invoice.invoice_number}`)}
                                >
                                    <Mail className="h-5 w-5 text-slate-500" />
                                    <div className="flex-1 text-left">
                                        <div className="text-sm font-semibold text-slate-900">Email Customer</div>
                                        <div className="text-xs text-slate-500">{invoice.customer_email}</div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-slate-400" />
                                </button>
                            )}

                            {invoice.status === "DRAFT" && (
                                <a
                                    href={`/invoices/${invoice.id}/send/`}
                                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-sky-50 border border-sky-200 hover:bg-sky-100 transition-colors"
                                >
                                    <Send className="h-5 w-5 text-sky-600" />
                                    <div className="flex-1 text-left">
                                        <div className="text-sm font-semibold text-sky-900">Mark as Sent</div>
                                        <div className="text-xs text-sky-600">Move from draft to sent status</div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-sky-400" />
                                </a>
                            )}

                            {balanceDue > 0 && invoice.status !== "DRAFT" && (
                                <a
                                    href={`/invoices/${invoice.id}/receive-payment/`}
                                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                                >
                                    <DollarSign className="h-5 w-5 text-emerald-600" />
                                    <div className="flex-1 text-left">
                                        <div className="text-sm font-semibold text-emerald-900">Record Payment</div>
                                        <div className="text-xs text-emerald-600">
                                            {formatCurrency(String(balanceDue), invoice.currency || currency)} remaining
                                        </div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-emerald-400" />
                                </a>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="border-t border-slate-100 px-6 py-4 bg-slate-50/50">
                    <div className="flex items-center justify-between gap-3">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:bg-white transition-colors"
                        >
                            Close
                        </button>
                        <a
                            href={`/invoices/${invoice.id}/edit/`}
                            className="px-4 py-2 rounded-lg bg-slate-900 text-sm font-semibold text-white hover:bg-slate-800 transition-colors"
                        >
                            Open Full View
                        </a>
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
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
        setSelectedInvoice(invoice);
    };

    const handleCloseDrawer = () => {
        setSelectedInvoice(null);
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
                                                className={cn(
                                                    "border-b border-slate-100 cursor-pointer transition-colors",
                                                    isSelected ? "bg-sky-50" : "hover:bg-slate-50",
                                                    overdue && !isSelected && "bg-rose-50/50"
                                                )}
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
                                                    <ChevronRight className="h-4 w-4 text-slate-400" />
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>

            {/* Invoice Drawer */}
            <AnimatePresence>
                {selectedInvoice && (
                    <InvoiceDrawer
                        invoice={selectedInvoice}
                        currency={currency}
                        onClose={handleCloseDrawer}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}
