import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    X,
    FileText,
    Printer,
    CreditCard,
    Calendar,
    Tag,
    Building2,
    DollarSign,
    ChevronRight,
    ExternalLink,
    Receipt,
    Paperclip,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
//    Types
// ─────────────────────────────────────────────────────────────────────────────

type ExpenseStatus = "UNPAID" | "PARTIAL" | "PAID";
type DrawerTab = "details" | "payment" | "actions";

interface Expense {
    id: number;
    description: string;
    supplier_id: number | null;
    supplier_name: string | null;
    category_id: number | null;
    category_name: string | null;
    status: ExpenseStatus;
    date: string | null;
    amount: string;
    amount_paid?: string;
    currency: string;
    memo?: string | null;
    receipt_url?: string | null;
}

interface ExpenseStats {
    expenses_ytd: string;
    expenses_month: string;
    total_all: string;
    avg_expense: string;
    total_filtered: string;
}

interface Category {
    id: number;
    name: string;
}

interface StatusChoice {
    value: string;
    label: string;
}

interface ApiResponse {
    expenses: Expense[];
    stats: ExpenseStats;
    period: string;
    status_filter: string;
    category_filter: number | null;
    categories: Category[];
    selected_expense: Expense | null;
    currency: string;
    status_choices: StatusChoice[];
    error?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
//    Helpers
// ─────────────────────────────────────────────────────────────────────────────

const statusColor: Record<ExpenseStatus, { bg: string; dot: string; label: string }> = {
    UNPAID: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500", label: "Unpaid" },
    PARTIAL: { bg: "bg-sky-50 text-sky-700 border border-sky-200", dot: "bg-sky-500", label: "Partial" },
    PAID: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500", label: "Paid" },
};

const StatusBadge: React.FC<{ status: ExpenseStatus }> = ({ status }) => {
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

const getBalanceDue = (expense: Expense): number => {
    const total = parseFloat(expense.amount) || 0;
    const paid = parseFloat(expense.amount_paid || "0") || 0;
    return Math.max(0, total - paid);
};

const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(" ");

// ─────────────────────────────────────────────────────────────────────────────
//    Expense Drawer Component
// ─────────────────────────────────────────────────────────────────────────────

interface ExpenseDrawerProps {
    expense: Expense;
    currency: string;
    onClose: () => void;
}

const ExpenseDrawer: React.FC<ExpenseDrawerProps> = ({ expense, currency, onClose }) => {
    const [activeTab, setActiveTab] = useState<DrawerTab>("details");
    const balanceDue = getBalanceDue(expense);
    const amountPaid = parseFloat(expense.amount_paid || "0") || 0;
    const totalAmount = parseFloat(expense.amount) || 0;

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
                        <h2 className="text-lg font-bold text-slate-900 line-clamp-1">
                            {expense.description || "Expense"}
                        </h2>
                        <div className="flex items-center gap-3">
                            <StatusBadge status={expense.status} />
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
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Amount</div>
                            <div className="text-2xl font-bold text-slate-900 mt-0.5">
                                {formatCurrency(expense.amount, expense.currency || currency)}
                            </div>
                        </div>
                        {expense.status !== "PAID" && balanceDue > 0 && (
                            <div className="text-right">
                                <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-amber-600">Balance Due</div>
                                <div className="text-lg font-bold text-amber-600 mt-0.5">
                                    {formatCurrency(String(balanceDue), expense.currency || currency)}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Tabs */}
                <div className="border-b border-slate-100 px-6">
                    <div className="flex gap-1 -mb-px">
                        {(["details", "payment", "actions"] as DrawerTab[]).map((tab) => (
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
                            {/* Supplier */}
                            <div className="space-y-2">
                                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Supplier</h4>
                                <div className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100">
                                    <div className="h-9 w-9 rounded-full bg-slate-200 flex items-center justify-center">
                                        <Building2 className="h-4 w-4 text-slate-500" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="font-semibold text-slate-900 truncate">
                                            {expense.supplier_name || "No supplier"}
                                        </div>
                                        <div className="text-xs text-slate-500">Vendor</div>
                                    </div>
                                    {expense.supplier_id && (
                                        <a
                                            href={`/suppliers/${expense.supplier_id}/`}
                                            className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors"
                                        >
                                            <ExternalLink className="h-4 w-4 text-slate-400" />
                                        </a>
                                    )}
                                </div>
                            </div>

                            {/* Date & Category */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Date</h4>
                                    <div className="flex items-center gap-2 text-sm text-slate-900">
                                        <Calendar className="h-4 w-4 text-slate-400" />
                                        {formatDate(expense.date)}
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Category</h4>
                                    <div className="flex items-center gap-2 text-sm text-slate-900">
                                        <Tag className="h-4 w-4 text-slate-400" />
                                        {expense.category_name || "Uncategorized"}
                                    </div>
                                </div>
                            </div>

                            {/* Amount Details */}
                            <div className="space-y-2">
                                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Amount Details</h4>
                                <div className="rounded-xl border border-slate-100 divide-y divide-slate-100">
                                    <div className="flex items-center justify-between px-4 py-2.5">
                                        <span className="text-sm text-slate-600">Total Amount</span>
                                        <span className="text-sm font-bold text-slate-900">
                                            {formatCurrency(expense.amount, expense.currency || currency)}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between px-4 py-2.5">
                                        <span className="text-sm text-slate-600">Amount Paid</span>
                                        <span className="text-sm font-medium text-emerald-600">
                                            {formatCurrency(expense.amount_paid || "0", expense.currency || currency)}
                                        </span>
                                    </div>
                                    {balanceDue > 0 && (
                                        <div className="flex items-center justify-between px-4 py-2.5 bg-amber-50">
                                            <span className="text-sm font-medium text-amber-700">Balance Due</span>
                                            <span className="text-sm font-bold text-amber-700">
                                                {formatCurrency(String(balanceDue), expense.currency || currency)}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Receipt */}
                            {expense.receipt_url && (
                                <div className="space-y-2">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Attachment</h4>
                                    <a
                                        href={expense.receipt_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100 hover:bg-slate-100 transition-colors"
                                    >
                                        <Paperclip className="h-4 w-4 text-slate-500" />
                                        <span className="text-sm font-medium text-slate-700">View Receipt</span>
                                        <ExternalLink className="h-4 w-4 text-slate-400 ml-auto" />
                                    </a>
                                </div>
                            )}

                            {/* Notes */}
                            {expense.memo && (
                                <div className="space-y-2">
                                    <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Notes</h4>
                                    <p className="text-sm text-slate-600 bg-slate-50 rounded-xl p-3 border border-slate-100">
                                        {expense.memo}
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === "payment" && (
                        <div className="p-6 space-y-5">
                            {/* Payment Status */}
                            <div className="rounded-xl border border-slate-100 p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium text-slate-600">Total Amount</span>
                                    <span className="text-sm font-bold text-slate-900">
                                        {formatCurrency(expense.amount, expense.currency || currency)}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium text-slate-600">Amount Paid</span>
                                    <span className="text-sm font-bold text-emerald-600">
                                        {formatCurrency(expense.amount_paid || "0", expense.currency || currency)}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium text-slate-600">Balance Due</span>
                                    <span className={cn(
                                        "text-sm font-bold",
                                        balanceDue > 0 ? "text-amber-600" : "text-slate-400"
                                    )}>
                                        {formatCurrency(String(balanceDue), expense.currency || currency)}
                                    </span>
                                </div>
                                {/* Progress bar */}
                                {totalAmount > 0 && (
                                    <div className="space-y-1.5">
                                        <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                                            <div
                                                className="h-full bg-emerald-500 rounded-full transition-all"
                                                style={{
                                                    width: `${Math.min(100, (amountPaid / totalAmount) * 100)}%`
                                                }}
                                            />
                                        </div>
                                        <div className="text-[10px] text-slate-500 text-right">
                                            {Math.round((amountPaid / totalAmount) * 100) || 0}% paid
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Payment History Placeholder */}
                            <div className="space-y-2">
                                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Payment History</h4>
                                {amountPaid > 0 ? (
                                    <div className="rounded-xl border border-slate-100 p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="h-8 w-8 rounded-full bg-emerald-50 flex items-center justify-center">
                                                <CreditCard className="h-4 w-4 text-emerald-600" />
                                            </div>
                                            <div className="flex-1">
                                                <div className="text-sm font-medium text-slate-900">Payment made</div>
                                                <div className="text-xs text-slate-500">View details in ledger</div>
                                            </div>
                                            <div className="text-sm font-bold text-emerald-600">
                                                {formatCurrency(expense.amount_paid || "0", expense.currency || currency)}
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
                                    href={`/expenses/${expense.id}/pay/`}
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
                                href={`/expenses/${expense.id}/edit/`}
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors"
                            >
                                <FileText className="h-5 w-5 text-slate-500" />
                                <div className="flex-1 text-left">
                                    <div className="text-sm font-semibold text-slate-900">Edit Expense</div>
                                    <div className="text-xs text-slate-500">Modify details, category, or amount</div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                            </a>

                            <a
                                href={`/expenses/${expense.id}/pdf/`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors"
                            >
                                <Printer className="h-5 w-5 text-slate-500" />
                                <div className="flex-1 text-left">
                                    <div className="text-sm font-semibold text-slate-900">Download PDF</div>
                                    <div className="text-xs text-slate-500">Generate expense report</div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                            </a>

                            <a
                                href="/receipts/"
                                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors"
                            >
                                <Receipt className="h-5 w-5 text-slate-500" />
                                <div className="flex-1 text-left">
                                    <div className="text-sm font-semibold text-slate-900">Attach Receipt</div>
                                    <div className="text-xs text-slate-500">Upload supporting document</div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                            </a>

                            {balanceDue > 0 && (
                                <a
                                    href={`/expenses/${expense.id}/pay/`}
                                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                                >
                                    <DollarSign className="h-5 w-5 text-emerald-600" />
                                    <div className="flex-1 text-left">
                                        <div className="text-sm font-semibold text-emerald-900">Record Payment</div>
                                        <div className="text-xs text-emerald-600">
                                            {formatCurrency(String(balanceDue), expense.currency || currency)} remaining
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
                            href={`/expenses/${expense.id}/edit/`}
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

export default function ExpensesListPage({ defaultCurrency = "USD" }: { defaultCurrency?: string }) {
    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [stats, setStats] = useState<ExpenseStats | null>(null);
    const [period, setPeriod] = useState("this_month");
    const [statusFilter, setStatusFilter] = useState("all");
    const [categoryFilter, setCategoryFilter] = useState<number | null>(null);
    const [categories, setCategories] = useState<Category[]>([]);
    const [statusChoices, setStatusChoices] = useState<StatusChoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);
    const [currency, setCurrency] = useState(defaultCurrency);

    // Date range filters
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const loadExpenses = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            params.set("status", statusFilter);
            params.set("period", period);
            if (categoryFilter) params.set("category", String(categoryFilter));
            if (startDate) params.set("start", startDate);
            if (endDate) params.set("end", endDate);

            const res = await fetch(`/api/expenses/list/?${params.toString()}`);
            const json: ApiResponse = await res.json();

            if (!res.ok || json.error) {
                throw new Error(json.error || "Failed to load expenses");
            }

            setExpenses(json.expenses || []);
            setStats(json.stats || null);
            setCategories(json.categories || []);
            setStatusChoices(json.status_choices || []);
            setCurrency(json.currency || defaultCurrency);
        } catch (err: any) {
            setError(err.message || "Failed to load expenses");
        } finally {
            setLoading(false);
        }
    }, [statusFilter, period, categoryFilter, startDate, endDate, defaultCurrency]);

    useEffect(() => {
        loadExpenses();
    }, [loadExpenses]);

    const handleRowClick = (expense: Expense) => {
        setSelectedExpense(expense);
    };

    const handleCloseDrawer = () => {
        setSelectedExpense(null);
    };

    // Category breakdown for chart/summary
    const categoryBreakdown = useMemo(() => {
        const breakdown: Record<string, number> = {};
        expenses.forEach((exp) => {
            const cat = exp.category_name || "Uncategorized";
            breakdown[cat] = (breakdown[cat] || 0) + parseFloat(exp.amount || "0");
        });
        return Object.entries(breakdown)
            .map(([name, amount]) => ({ name, amount }))
            .sort((a, b) => b.amount - a.amount)
            .slice(0, 5);
    }, [expenses]);

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">Accounting</p>
                        <h1 className="text-2xl font-semibold">Expenses</h1>
                        <p className="text-sm text-slate-500">Track your business expenses and spending.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={loadExpenses}
                            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                        >
                            Refresh
                        </button>
                        <a
                            href="/expenses/new/"
                            className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
                        >
                            + New Expense
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
                            <div className="text-xs font-medium text-slate-500 uppercase">This Month</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.expenses_month, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Paid expenses</p>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Year to Date</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.expenses_ytd, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Paid expenses this year</p>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Avg Expense</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.avg_expense, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Average amount</p>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-4">
                            <div className="text-xs font-medium text-slate-500 uppercase">Filtered Total</div>
                            <div className="text-2xl font-semibold text-slate-900 mt-1">
                                {formatCurrency(stats.total_filtered, currency)}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">Current view</p>
                        </div>
                    </div>
                )}

                {/* Filters */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="flex flex-wrap items-center gap-4">
                        <div className="flex items-center gap-2">
                            <label className="text-sm font-medium text-slate-700">Period:</label>
                            <select
                                value={period}
                                onChange={(e) => setPeriod(e.target.value)}
                                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                            >
                                <option value="this_month">This Month</option>
                                <option value="this_year">This Year</option>
                                <option value="all">All Time</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-sm font-medium text-slate-700">Status:</label>
                            <select
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                            >
                                <option value="all">All</option>
                                <option value="paid">Paid</option>
                                <option value="unpaid">Unpaid</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-sm font-medium text-slate-700">Category:</label>
                            <select
                                value={categoryFilter || ""}
                                onChange={(e) => setCategoryFilter(e.target.value ? Number(e.target.value) : null)}
                                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                            >
                                <option value="">All Categories</option>
                                {categories.map((cat) => (
                                    <option key={cat.id} value={cat.id}>
                                        {cat.name}
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
                    </div>
                </div>

                {/* Top Categories Summary */}
                {categoryBreakdown.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-xl p-4">
                        <h3 className="text-sm font-semibold text-slate-800 mb-3">Top Categories</h3>
                        <div className="flex flex-wrap gap-3">
                            {categoryBreakdown.map((cat) => (
                                <div
                                    key={cat.name}
                                    className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100"
                                >
                                    <span className="text-sm font-medium text-slate-700">{cat.name}</span>
                                    <span className="text-sm text-slate-500">{formatCurrency(String(cat.amount), currency)}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Expenses Table */}
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                    {loading ? (
                        <div className="p-8 text-center text-slate-500">Loading expenses...</div>
                    ) : expenses.length === 0 ? (
                        <div className="p-8 text-center text-slate-500">
                            No expenses found. <a href="/expenses/new/" className="text-sky-600 hover:underline">Add your first expense</a>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-slate-50 border-b border-slate-200">
                                    <tr className="text-xs uppercase text-slate-500">
                                        <th className="px-4 py-3 font-medium">Date</th>
                                        <th className="px-4 py-3 font-medium">Description</th>
                                        <th className="px-4 py-3 font-medium">Supplier</th>
                                        <th className="px-4 py-3 font-medium">Category</th>
                                        <th className="px-4 py-3 font-medium text-right">Amount</th>
                                        <th className="px-4 py-3 font-medium">Status</th>
                                        <th className="px-4 py-3 font-medium"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {expenses.map((expense) => {
                                        const isSelected = selectedExpense?.id === expense.id;
                                        return (
                                            <tr
                                                key={expense.id}
                                                onClick={() => handleRowClick(expense)}
                                                className={cn(
                                                    "border-b border-slate-100 cursor-pointer transition-colors",
                                                    isSelected ? "bg-sky-50" : "hover:bg-slate-50"
                                                )}
                                            >
                                                <td className="px-4 py-3 text-slate-600">
                                                    {formatDate(expense.date)}
                                                </td>
                                                <td className="px-4 py-3 font-medium text-slate-800">
                                                    {expense.description || "—"}
                                                </td>
                                                <td className="px-4 py-3 text-slate-600">
                                                    {expense.supplier_name || "—"}
                                                </td>
                                                <td className="px-4 py-3 text-slate-600">
                                                    {expense.category_name || "—"}
                                                </td>
                                                <td className="px-4 py-3 text-right font-medium text-slate-800">
                                                    {formatCurrency(expense.amount, expense.currency || currency)}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <StatusBadge status={expense.status} />
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

            {/* Expense Drawer */}
            <AnimatePresence>
                {selectedExpense && (
                    <ExpenseDrawer
                        expense={selectedExpense}
                        currency={currency}
                        onClose={handleCloseDrawer}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}
