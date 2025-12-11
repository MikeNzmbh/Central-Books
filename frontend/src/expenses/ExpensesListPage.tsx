import React, { useCallback, useEffect, useMemo, useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
//    Types
// ─────────────────────────────────────────────────────────────────────────────

type ExpenseStatus = "UNPAID" | "PARTIAL" | "PAID";

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
    currency: string;
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

const statusColor: Record<ExpenseStatus, { bg: string; dot: string }> = {
    UNPAID: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500" },
    PARTIAL: { bg: "bg-sky-50 text-sky-700 border border-sky-200", dot: "bg-sky-500" },
    PAID: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500" },
};

const StatusBadge: React.FC<{ status: ExpenseStatus }> = ({ status }) => {
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
        setSelectedExpense(selectedExpense?.id === expense.id ? null : expense);
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
                                                className={`border-b border-slate-100 cursor-pointer transition-colors ${isSelected ? "bg-sky-50" : "hover:bg-slate-50"
                                                    }`}
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
                                                    <div className="flex items-center gap-2">
                                                        <a
                                                            href={`/expenses/${expense.id}/edit/`}
                                                            onClick={(e) => e.stopPropagation()}
                                                            className="text-xs font-medium text-sky-600 hover:text-sky-800"
                                                        >
                                                            Edit
                                                        </a>
                                                        <a
                                                            href={`/expenses/${expense.id}/pdf/`}
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

                {/* Selected Expense Detail Panel */}
                {selectedExpense && (
                    <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-slate-800">
                                    {selectedExpense.description || "Expense"}
                                </h3>
                                <p className="text-sm text-slate-500">
                                    {selectedExpense.supplier_name || "No supplier"} • {selectedExpense.category_name || "Uncategorized"}
                                </p>
                            </div>
                            <StatusBadge status={selectedExpense.status} />
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Date</div>
                                <div className="font-medium text-slate-800">{formatDate(selectedExpense.date)}</div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Amount</div>
                                <div className="font-semibold text-slate-900">
                                    {formatCurrency(selectedExpense.amount, selectedExpense.currency || currency)}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Supplier</div>
                                <div className="font-medium text-slate-800">{selectedExpense.supplier_name || "—"}</div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase">Category</div>
                                <div className="font-medium text-slate-800">{selectedExpense.category_name || "—"}</div>
                            </div>
                        </div>
                        <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                            <a
                                href={`/expenses/${selectedExpense.id}/edit/`}
                                className="px-4 py-2 text-sm font-medium text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
                            >
                                Edit Expense
                            </a>
                            <a
                                href={`/expenses/${selectedExpense.id}/pdf/`}
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
