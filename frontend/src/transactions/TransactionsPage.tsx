import React, { useState, useMemo } from "react";
import {
    MemoryRouter,
    Routes,
    Route,
    useNavigate,
    useLocation,
} from "react-router-dom";
import { useTransactions, TransactionRow as ApiTransactionRow } from "./useTransactions";
import CompanionStrip from "../companion/CompanionStrip";
import {
    ArrowRight,
    ArrowUpRight,
    Calendar,
    Check,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    Download,
    Filter,
    MoreHorizontal,
    Plus,
    RefreshCw,
    Search,
    Sparkles,
    TrendingUp,
    AlertCircle,
    FileText,
    X,
    Clock,
    Send,
    CreditCard,
    Trash2,
    Archive,
    Printer,
    Copy,
    Mail
} from "lucide-react";

// -----------------------------------------------------------------------------
// Shared Utilities & Styles
// -----------------------------------------------------------------------------

function formatCurrency(amount: number, currency: string = "USD"): string {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
    }).format(amount);
}

function classNames(...classes: (string | false | null | undefined)[]) {
    return classes.filter(Boolean).join(" ");
}

function getCsrfToken(): string {
    const cookies = document.cookie.split(";").reduce((acc, cookie) => {
        const [key, value] = cookie.trim().split("=");
        acc[key] = value;
        return acc;
    }, {} as Record<string, string>);
    return cookies.csrftoken || "";
}

// -----------------------------------------------------------------------------
// Extended Types & Mock Data
// -----------------------------------------------------------------------------

type TransactionKind = "invoice" | "expense";

interface LineItem {
    id: string;
    description: string;
    qty: number;
    rate: number;
    total: number;
}

interface HistoryEvent {
    date: string;
    action: string;
    user: string;
}

interface TransactionRow {
    id: string;
    number: string;
    entity: string;
    email: string;
    date: string;
    dueDate: string;
    amount: number;
    status: string;
    lineItems: LineItem[];
    history: HistoryEvent[];
}

const MOCK_DATA: Record<TransactionKind, TransactionRow[]> = {
    invoice: [
        {
            id: "1", number: "INV-2025-001", entity: "Merryweather Corp", email: "billing@merryweather.com", date: "Dec 08, 2025", dueDate: "Dec 08, 2025", amount: 565.00, status: "Overdue",
            lineItems: [
                { id: "l1", description: "Consulting Services - Dec", qty: 2, rate: 200, total: 400 },
                { id: "l2", description: "SaaS Platform Fee", qty: 1, rate: 165, total: 165 }
            ],
            history: [
                { date: "Dec 08, 10:00 AM", action: "Invoice Created", user: "Mike" },
                { date: "Dec 08, 10:05 AM", action: "Sent to Client", user: "System" },
                { date: "Dec 09, 09:30 AM", action: "Viewed by Client", user: "Client" },
            ]
        },
        {
            id: "2", number: "INV-2025-002", entity: "Shopify Inc", email: "accounts@shopify.com", date: "Dec 07, 2025", dueDate: "Jan 07, 2026", amount: 11300.00, status: "Paid",
            lineItems: [
                { id: "l3", description: "Enterprise License Q4", qty: 1, rate: 10000, total: 10000 },
                { id: "l4", description: "Implementation Support", qty: 10, rate: 130, total: 1300 }
            ],
            history: [
                { date: "Dec 07, 02:00 PM", action: "Invoice Created", user: "Mike" },
                { date: "Dec 07, 02:15 PM", action: "Payment Received", user: "Stripe" },
            ]
        },
        { id: "3", number: "INV-2025-003", entity: "Acme Labs", email: "ap@acmelabs.org", date: "Dec 01, 2025", dueDate: "Dec 15, 2025", amount: 339.00, status: "Sent", lineItems: [], history: [] },
        { id: "4", number: "INV-2025-004", entity: "Globex Corp", email: "hank@globex.com", date: "Nov 28, 2025", dueDate: "Dec 28, 2025", amount: 2450.00, status: "Paid", lineItems: [], history: [] },
        { id: "5", number: "INV-2025-005", entity: "Soylent Corp", email: "finance@soylent.com", date: "Nov 25, 2025", dueDate: "Dec 25, 2025", amount: 1200.00, status: "Draft", lineItems: [], history: [] },
    ],
    expense: [
        {
            id: "e1", number: "BILL-9921", entity: "AWS Web Services", email: "no-reply@aws.amazon.com", date: "Dec 02, 2025", dueDate: "Dec 16, 2025", amount: 820.00, status: "Unpaid",
            lineItems: [
                { id: "el1", description: "EC2 Instances (us-east-1)", qty: 1, rate: 650, total: 650 },
                { id: "el2", description: "S3 Storage", qty: 1, rate: 170, total: 170 }
            ],
            history: [
                { date: "Dec 02, 08:00 AM", action: "Bill Received", user: "Auto-Ingest" },
            ]
        },
        { id: "e2", number: "BILL-9920", entity: "Figma, Inc.", email: "billing@figma.com", date: "Dec 01, 2025", dueDate: "Dec 15, 2025", amount: 120.00, status: "Paid", lineItems: [], history: [] },
        { id: "e3", number: "EXP-004", entity: "WeWork", email: "membership@wework.com", date: "Nov 30, 2025", dueDate: "Dec 01, 2025", amount: 4500.00, status: "Overdue", lineItems: [], history: [] },
    ]
};

const CONFIG = {
    invoice: {
        title: "Invoices",
        label: "Receivables",
        createLabel: "New Invoice",
        metrics: [
            { label: "Open Balance", value: 904.00, subtext: "2 overdue invoices" },
            { label: "Revenue (YTD)", value: 145000.00, subtext: "Up 12% from last month", trend: "up" as const },
            { label: "Avg. Days to Pay", value: 14, subtext: "Industry avg: 30 days" },
        ]
    },
    expense: {
        title: "Expenses",
        label: "Payables",
        createLabel: "New Expense",
        metrics: [
            { label: "Outstanding", value: 5320.00, subtext: "1 overdue bill" },
            { label: "Expenses (YTD)", value: 42300.00, subtext: "Down 5% from last month", trend: "down" as const },
            { label: "Burn Rate", value: 3200.00, subtext: "Monthly average" },
        ]
    }
};

// -----------------------------------------------------------------------------
// Sub-Components
// -----------------------------------------------------------------------------

const StatusPill: React.FC<{ status: string }> = ({ status }) => {
    const styles: Record<string, string> = {
        draft: "bg-slate-100 text-slate-600 border-slate-200",
        sent: "bg-sky-50 text-sky-700 border-sky-200",
        partial: "bg-amber-50 text-amber-700 border-amber-200",
        paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
        overdue: "bg-rose-50 text-rose-700 border-rose-200",
        unpaid: "bg-slate-50 text-slate-700 border-slate-200",
    };

    const normalized = status.toLowerCase();

    return (
        <span
            className={classNames(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                styles[normalized] || styles.draft
            )}
        >
            <div className={classNames("h-1.5 w-1.5 rounded-full", normalized === 'paid' ? 'bg-emerald-500' : normalized === 'overdue' ? 'bg-rose-500' : 'bg-slate-400')} />
            {status}
        </span>
    );
};

// CompanionPanel removed - now using shared CompanionStrip component

interface PayBillFormState {
    isOpen: boolean;
    categoryId: string;
    accountId: string;
    taxAmount: string;
    paidDate: string;
    isSubmitting: boolean;
    error: string | null;
}

interface ExpenseDetail {
    id: number;
    description: string;
    supplier_name: string | null;
    category_id: number | null;
    category_name: string | null;
    account_id: number | null;
    account_label: string | null;
    status: string;
    date: string | null;
    due_date: string | null;
    amount: string;
    tax_amount: string;
    net_total: string;
    tax_total: string;
    grand_total: string;
    balance: string;
}

interface CategoryOption {
    id: number;
    name: string;
}

interface AccountOption {
    id: number;
    code: string;
    name: string;
}

const TransactionDrawer: React.FC<{
    transaction: TransactionRow | null;
    kind: TransactionKind;
    onClose: () => void;
    onPaymentComplete?: () => void;
}> = ({ transaction, kind, onClose, onPaymentComplete }) => {
    const [payBillForm, setPayBillForm] = useState<PayBillFormState>({
        isOpen: false,
        categoryId: "",
        accountId: "",
        taxAmount: "",
        paidDate: new Date().toISOString().split("T")[0],
        isSubmitting: false,
        error: null,
    });
    const [expenseDetail, setExpenseDetail] = useState<ExpenseDetail | null>(null);
    const [categories, setCategories] = useState<CategoryOption[]>([]);
    const [accounts, setAccounts] = useState<AccountOption[]>([]);
    const [loadingDetail, setLoadingDetail] = useState(false);

    // Load expense detail when Pay Bill is clicked
    const loadExpenseDetail = async () => {
        if (!transaction) return;
        setLoadingDetail(true);
        try {
            const resp = await fetch(`/api/expenses/${transaction.id}/`);
            if (!resp.ok) throw new Error("Failed to load expense");
            const data = await resp.json();
            setExpenseDetail(data.expense);
            setCategories(data.categories || []);
            setAccounts(data.accounts || []);
            setPayBillForm((prev) => ({
                ...prev,
                isOpen: true,
                categoryId: data.expense.category_id?.toString() || "",
                taxAmount: data.expense.tax_amount || "0.00",
            }));
        } catch (err) {
            setPayBillForm((prev) => ({
                ...prev,
                error: err instanceof Error ? err.message : "Failed to load expense",
            }));
        } finally {
            setLoadingDetail(false);
        }
    };

    const handlePayBill = async () => {
        if (!transaction) return;
        setPayBillForm((prev) => ({ ...prev, isSubmitting: true, error: null }));
        try {
            const resp = await fetch(`/api/expenses/${transaction.id}/pay/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({
                    category_id: payBillForm.categoryId || null,
                    tax_amount: payBillForm.taxAmount || null,
                    paid_date: payBillForm.paidDate || null,
                }),
            });
            if (!resp.ok) {
                const data = await resp.json();
                throw new Error(data.error || "Failed to pay bill");
            }
            // Success - close drawer and refresh
            setPayBillForm((prev) => ({ ...prev, isSubmitting: false, isOpen: false }));
            onPaymentComplete?.();
            onClose();
        } catch (err) {
            setPayBillForm((prev) => ({
                ...prev,
                isSubmitting: false,
                error: err instanceof Error ? err.message : "Payment failed",
            }));
        }
    };

    if (!transaction) return null;

    const isPaid = transaction.status.toLowerCase() === "paid";

    return (
        <>
            <div className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm transition-opacity" onClick={onClose} />
            <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md transform bg-white shadow-2xl transition-transform duration-300 ease-in-out">
                <div className="flex h-full flex-col">
                    {/* Drawer Header */}
                    <div className="flex items-start justify-between border-b border-slate-100 p-6">
                        <div className="space-y-1">
                            <div className="flex items-center gap-2">
                                <span className="text-lg font-bold text-slate-900">{transaction.number}</span>
                                <StatusPill status={transaction.status} />
                            </div>
                            <p className="text-sm text-slate-500">{transaction.entity}</p>
                        </div>
                        <button onClick={onClose} className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                            <X className="h-5 w-5" />
                        </button>
                    </div>

                    {/* Drawer Content */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {/* Quick Stats */}
                        <div className="grid grid-cols-2 gap-4 mb-8">
                            <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Amount</p>
                                <p className="mt-1 text-lg font-bold text-slate-900">{formatCurrency(transaction.amount)}</p>
                            </div>
                            <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Due Date</p>
                                <p className={classNames("mt-1 text-lg font-medium", transaction.status === "Overdue" ? "text-rose-600" : "text-slate-900")}>
                                    {transaction.dueDate}
                                </p>
                            </div>
                        </div>

                        {/* Pay Bill Form */}
                        {payBillForm.isOpen && kind === "expense" && (
                            <div className="mb-8 rounded-xl border-2 border-indigo-200 bg-indigo-50/50 p-4 space-y-4">
                                <h4 className="text-xs font-bold uppercase tracking-widest text-indigo-600">Pay This Bill</h4>

                                {payBillForm.error && (
                                    <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
                                        {payBillForm.error}
                                    </div>
                                )}

                                {/* Category Selection */}
                                <div>
                                    <label className="block text-xs font-medium text-slate-600 mb-1">Category</label>
                                    <select
                                        value={payBillForm.categoryId}
                                        onChange={(e) => setPayBillForm((prev) => ({ ...prev, categoryId: e.target.value }))}
                                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                    >
                                        <option value="">Select category...</option>
                                        {categories.map((cat) => (
                                            <option key={cat.id} value={cat.id}>{cat.name}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* COA Account Selection */}
                                <div>
                                    <label className="block text-xs font-medium text-slate-600 mb-1">COA Account</label>
                                    <select
                                        value={payBillForm.accountId}
                                        onChange={(e) => setPayBillForm((prev) => ({ ...prev, accountId: e.target.value }))}
                                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                    >
                                        <option value="">Select account...</option>
                                        {accounts.map((acc) => (
                                            <option key={acc.id} value={acc.id}>{acc.code} • {acc.name}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Tax Amount */}
                                <div>
                                    <label className="block text-xs font-medium text-slate-600 mb-1">Tax Amount</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={payBillForm.taxAmount}
                                        onChange={(e) => setPayBillForm((prev) => ({ ...prev, taxAmount: e.target.value }))}
                                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                        placeholder="0.00"
                                    />
                                </div>

                                {/* Payment Date */}
                                <div>
                                    <label className="block text-xs font-medium text-slate-600 mb-1">Payment Date</label>
                                    <input
                                        type="date"
                                        value={payBillForm.paidDate}
                                        onChange={(e) => setPayBillForm((prev) => ({ ...prev, paidDate: e.target.value }))}
                                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                                    />
                                </div>

                                {/* Form Actions */}
                                <div className="flex gap-2 pt-2">
                                    <button
                                        onClick={() => setPayBillForm((prev) => ({ ...prev, isOpen: false }))}
                                        className="flex-1 rounded-lg border border-slate-200 bg-white py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        onClick={handlePayBill}
                                        disabled={payBillForm.isSubmitting}
                                        className="flex-1 rounded-lg bg-indigo-600 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                                    >
                                        {payBillForm.isSubmitting ? "Processing..." : "Confirm Payment"}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Line Items */}
                        <div className="mb-8 space-y-4">
                            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400">Line Items</h4>
                            {transaction.lineItems && transaction.lineItems.length > 0 ? (
                                <div className="rounded-xl border border-slate-100 overflow-hidden">
                                    <table className="w-full text-left text-xs">
                                        <thead className="bg-slate-50 font-medium text-slate-500">
                                            <tr>
                                                <th className="px-4 py-2">Description</th>
                                                <th className="px-4 py-2 text-right">Qty</th>
                                                <th className="px-4 py-2 text-right">Amount</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {transaction.lineItems.map(item => (
                                                <tr key={item.id}>
                                                    <td className="px-4 py-3 text-slate-900">{item.description}</td>
                                                    <td className="px-4 py-3 text-right text-slate-500">{item.qty}</td>
                                                    <td className="px-4 py-3 text-right font-medium text-slate-900">{formatCurrency(item.total)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400">
                                    No line item details available
                                </div>
                            )}
                        </div>

                        {/* Timeline */}
                        <div className="space-y-4">
                            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400">Activity History</h4>
                            <div className="relative border-l-2 border-slate-100 ml-2 space-y-6 pl-6 pb-2">
                                {transaction.history && transaction.history.length > 0 ? (
                                    transaction.history.map((event, idx) => (
                                        <div key={idx} className="relative">
                                            <div className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-white bg-slate-300 ring-1 ring-slate-100" />
                                            <p className="text-xs font-medium text-slate-900">{event.action}</p>
                                            <p className="text-[10px] text-slate-500">{event.date} • {event.user}</p>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-xs text-slate-400 italic">No history recorded</p>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Drawer Footer Actions */}
                    <div className="border-t border-slate-100 bg-slate-50 p-6">
                        <div className="grid grid-cols-2 gap-3">
                            <button className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100">
                                <FileText className="h-3.5 w-3.5" />
                                Download PDF
                            </button>
                            {kind === "invoice" ? (
                                <button className="flex items-center justify-center gap-2 rounded-xl bg-slate-900 py-2.5 text-xs font-semibold text-white hover:bg-slate-800">
                                    <Send className="h-3.5 w-3.5" /> Resend Invoice
                                </button>
                            ) : (
                                <button
                                    onClick={loadExpenseDetail}
                                    disabled={isPaid || loadingDetail || payBillForm.isOpen}
                                    className={classNames(
                                        "flex items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-semibold",
                                        isPaid
                                            ? "bg-emerald-100 text-emerald-700 cursor-not-allowed"
                                            : payBillForm.isOpen
                                                ? "bg-indigo-100 text-indigo-700"
                                                : "bg-slate-900 text-white hover:bg-slate-800"
                                    )}
                                >
                                    {loadingDetail ? (
                                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                                    ) : isPaid ? (
                                        <>
                                            <Check className="h-3.5 w-3.5" /> Paid
                                        </>
                                    ) : payBillForm.isOpen ? (
                                        <>
                                            <CreditCard className="h-3.5 w-3.5" /> Filling...
                                        </>
                                    ) : (
                                        <>
                                            <CreditCard className="h-3.5 w-3.5" /> Pay Bill
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};


const BulkActionBar: React.FC<{ count: number; onClear: () => void }> = ({ count, onClear }) => {
    if (count === 0) return null;

    return (
        <div className="fixed bottom-8 left-1/2 z-40 flex -translate-x-1/2 items-center gap-4 rounded-2xl border border-slate-800 bg-slate-900 px-6 py-3 text-white shadow-2xl animate-in slide-in-from-bottom-10 fade-in duration-300">
            <div className="flex items-center gap-3 border-r border-slate-700 pr-4">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-indigo-500 text-[10px] font-bold">
                    {count}
                </span>
                <span className="text-xs font-medium">Selected</span>
            </div>
            <div className="flex items-center gap-2">
                <button className="rounded-lg p-2 hover:bg-slate-800" title="Archive">
                    <Archive className="h-4 w-4 text-slate-300" />
                </button>
                <button className="rounded-lg p-2 hover:bg-slate-800" title="Print">
                    <Printer className="h-4 w-4 text-slate-300" />
                </button>
                <button className="rounded-lg p-2 hover:bg-slate-800" title="Delete">
                    <Trash2 className="h-4 w-4 text-rose-400" />
                </button>
            </div>
            <div className="border-l border-slate-700 pl-4">
                <button onClick={onClear} className="text-xs font-medium text-slate-400 hover:text-white">
                    Cancel
                </button>
            </div>
        </div>
    );
};

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export const TransactionsPageContent: React.FC<{ kind: TransactionKind }> = ({ kind }) => {
    const navigate = useNavigate();
    const config = CONFIG[kind];

    // Fetch real data from API
    const { rows: apiRows, stats, currency, loading, error, refresh } = useTransactions(kind);

    // State
    const [filter, setFilter] = useState("all");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [selectedTransaction, setSelectedTransaction] = useState<TransactionRow | null>(null);

    // Convert API rows to internal format with empty lineItems/history for drawer
    const rows: TransactionRow[] = useMemo(() =>
        apiRows.map(r => ({
            ...r,
            lineItems: [],
            history: [],
        })),
        [apiRows]);

    // Filtering Logic
    const filteredRows = useMemo(() => {
        let result = rows;
        if (filter !== "all") {
            result = result.filter(r => r.status.toLowerCase() === filter);
        }
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            result = result.filter(r =>
                r.number.toLowerCase().includes(q) ||
                r.entity.toLowerCase().includes(q)
            );
        }
        return result;
    }, [rows, filter, searchQuery]);

    // Selection Logic
    const toggleSelection = (id: string) => {
        const next = new Set(selectedIds);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        setSelectedIds(next);
    };

    const toggleAll = () => {
        if (selectedIds.size === filteredRows.length) setSelectedIds(new Set());
        else setSelectedIds(new Set(filteredRows.map(r => r.id)));
    };

    // Loading state
    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-[#F9FAFB]">
                <div className="flex flex-col items-center gap-4">
                    <RefreshCw className="h-8 w-8 animate-spin text-slate-400" />
                    <p className="text-sm text-slate-500">Loading {kind}s...</p>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-[#F9FAFB]">
                <div className="flex flex-col items-center gap-4 text-center">
                    <AlertCircle className="h-12 w-12 text-rose-400" />
                    <p className="text-sm text-slate-700">Failed to load {kind}s</p>
                    <p className="text-xs text-slate-500">{error}</p>
                    <button onClick={refresh} className="mt-2 rounded-full bg-slate-900 px-4 py-2 text-xs text-white hover:bg-slate-800">
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#F9FAFB] font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">

            {/* Detail Drawer */}
            <TransactionDrawer
                transaction={selectedTransaction}
                kind={kind}
                onClose={() => setSelectedTransaction(null)}
            />

            {/* Floating Bulk Actions */}
            <BulkActionBar count={selectedIds.size} onClear={() => setSelectedIds(new Set())} />

            <div className="mx-auto max-w-[1600px] px-6 py-8 md:px-10">

                {/* Header */}
                <header className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
                    <div className="space-y-2">
                        <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                            <span>Overview</span>
                            <span className="text-slate-300">/</span>
                            <span className="text-slate-600">{config.label}</span>
                        </div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                            {config.title}
                        </h1>
                    </div>

                    <div className="flex items-center gap-3">
                        <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50">
                            <Download className="h-3.5 w-3.5" />
                            Export CSV
                        </button>
                        <button className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-slate-900/10 transition-transform hover:scale-105 active:scale-95">
                            <Plus className="h-3.5 w-3.5" />
                            {config.createLabel}
                        </button>
                    </div>
                </header>

                <div className="flex flex-col gap-8">

                    {/* Top Section: Companion + Metrics */}
                    <div className="grid gap-6 lg:grid-cols-3">
                        <div className="lg:col-span-2">
                            <CompanionStrip context={kind === "invoice" ? "invoices" : "expenses"} />
                        </div>
                        <div className="flex flex-col justify-between gap-4">
                            {/* Metrics */}
                            <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 transition-all hover:shadow-md">
                                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
                                    {kind === "invoice" ? "Open Balance" : "Outstanding"}
                                </span>
                                <span className="mt-3 text-3xl font-bold tracking-tight text-slate-900">
                                    {formatCurrency(stats.openBalance, currency)}
                                </span>
                                <span className="mt-2 text-xs font-medium text-slate-500">
                                    {stats.overdueCount > 0 ? `${stats.overdueCount} overdue` : "All current"}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 transition-all hover:shadow-md min-w-0">
                                    <div className="flex justify-between">
                                        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
                                            {kind === "invoice" ? "Revenue YTD" : "Expenses YTD"}
                                        </span>
                                    </div>
                                    <span className="mt-3 text-xl font-bold tracking-tight text-slate-900 truncate" title={formatCurrency(
                                        kind === "invoice" ? (stats.revenueYtd || 0) : (stats.expensesYtd || 0),
                                        currency
                                    )}>
                                        {formatCurrency(
                                            kind === "invoice" ? (stats.revenueYtd || 0) : (stats.expensesYtd || 0),
                                            currency
                                        )}
                                    </span>
                                </div>
                                <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 transition-all hover:shadow-md">
                                    <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Volume</span>
                                    <span className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{stats.totalCount}</span>
                                    <span className="mt-1 text-[10px] text-slate-400">{kind}s</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Main Table Card */}
                    <div className="min-h-[600px] rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100">

                        {/* Toolbar */}
                        <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                            {/* Tabs */}
                            <div className="flex overflow-hidden rounded-xl border border-slate-100 bg-slate-50/50 p-1">
                                {["All", "Paid", "Overdue", "Draft"].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setFilter(tab.toLowerCase())}
                                        className={classNames(
                                            "rounded-lg px-4 py-1.5 text-xs font-semibold transition-all",
                                            filter === tab.toLowerCase()
                                                ? "bg-white text-slate-900 shadow-sm ring-1 ring-black/5"
                                                : "text-slate-500 hover:text-slate-700"
                                        )}
                                    >
                                        {tab}
                                    </button>
                                ))}
                            </div>

                            {/* Search */}
                            <div className="flex items-center gap-2">
                                <div className="relative">
                                    <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                                    <input
                                        type="text"
                                        placeholder={`Search ${kind}s...`}
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="h-9 w-64 rounded-xl border-none bg-slate-50 pl-9 pr-4 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-slate-200 transition-all"
                                    />
                                </div>
                                <button className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors">
                                    <Filter className="h-3.5 w-3.5" />
                                </button>
                            </div>
                        </div>

                        {/* Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs">
                                <thead className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                    <tr className="border-b border-slate-100">
                                        <th className="pb-4 pl-4 w-10">
                                            <input
                                                type="checkbox"
                                                className="rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                                                checked={selectedIds.size === filteredRows.length && filteredRows.length > 0}
                                                onChange={toggleAll}
                                            />
                                        </th>
                                        <th className="pb-4 pl-2">Number</th>
                                        <th className="pb-4">{kind === "invoice" ? "Customer" : "Supplier"}</th>
                                        <th className="pb-4">Date</th>
                                        <th className="pb-4">Due Date</th>
                                        <th className="pb-4 text-right">Amount</th>
                                        <th className="pb-4 pl-4">Status</th>
                                        <th className="pb-4 text-right pr-4">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {filteredRows.map((row) => (
                                        <tr
                                            key={row.id}
                                            onClick={(e) => {
                                                // Don't open drawer if clicking checkbox or actions
                                                if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).closest('button')) return;
                                                setSelectedTransaction(row);
                                            }}
                                            className={classNames(
                                                "group cursor-pointer transition-colors",
                                                selectedIds.has(row.id) ? "bg-slate-50" : "hover:bg-slate-50"
                                            )}
                                        >
                                            <td className="py-4 pl-4">
                                                <input
                                                    type="checkbox"
                                                    className="rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                                                    checked={selectedIds.has(row.id)}
                                                    onChange={() => toggleSelection(row.id)}
                                                />
                                            </td>
                                            <td className="py-4 pl-2 font-mono font-medium text-slate-600 group-hover:text-indigo-600 transition-colors">
                                                {row.number}
                                            </td>
                                            <td className="py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500">
                                                        {row.entity.charAt(0)}
                                                    </div>
                                                    <div className="flex flex-col">
                                                        <span className="font-semibold text-slate-900">{row.entity}</span>
                                                        <span className="text-[10px] text-slate-400">{row.email}</span>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="py-4 text-slate-500">{row.date}</td>
                                            <td className="py-4 text-slate-500">
                                                {row.status === "Overdue" ? (
                                                    <span className="flex items-center gap-1.5 font-medium text-rose-600">
                                                        <AlertCircle className="h-3.5 w-3.5" />
                                                        {row.dueDate}
                                                    </span>
                                                ) : (
                                                    row.dueDate
                                                )}
                                            </td>
                                            <td className="py-4 text-right font-bold text-slate-900 tabular-nums text-sm">
                                                {formatCurrency(row.amount)}
                                            </td>
                                            <td className="py-4 pl-4">
                                                <StatusPill status={row.status} />
                                            </td>
                                            <td className="py-4 pr-4 text-right">
                                                <div className="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                                                    <button
                                                        className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-slate-400 shadow-sm ring-1 ring-slate-200 hover:text-slate-900 transition-all hover:scale-105"
                                                        title="View Details"
                                                        onClick={() => setSelectedTransaction(row)}
                                                    >
                                                        <FileText className="h-4 w-4" />
                                                    </button>
                                                    <button className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-slate-400 shadow-sm ring-1 ring-slate-200 hover:text-slate-900 transition-all hover:scale-105">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination Footer */}
                        <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-6">
                            <span className="text-xs text-slate-500">
                                Showing <span className="font-semibold text-slate-900">{filteredRows.length}</span> of <span className="font-semibold text-slate-900">{rows.length}</span> transactions
                            </span>
                            <div className="flex items-center gap-2">
                                <button className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400 hover:bg-slate-50 hover:text-slate-600 disabled:opacity-50">
                                    <ChevronLeft className="h-4 w-4" />
                                </button>
                                <span className="text-xs font-medium text-slate-600">Page 1 of 1</span>
                                <button className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400 hover:bg-slate-50 hover:text-slate-600 disabled:opacity-50">
                                    <ChevronRight className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
};

// -----------------------------------------------------------------------------
// Root App & Routing
// -----------------------------------------------------------------------------

export const TransactionsPage: React.FC = () => {
    return (
        <MemoryRouter>
            <Routes>
                <Route path="/" element={<TransactionsPageContent kind="invoice" />} />
                <Route path="/invoices" element={<TransactionsPageContent kind="invoice" />} />
                <Route path="/expenses" element={<TransactionsPageContent kind="expense" />} />
            </Routes>

            {/* Demo Switcher */}
            <div className="fixed bottom-6 left-6 z-50 flex items-center gap-1 rounded-full bg-white/90 p-1.5 shadow-xl ring-1 ring-slate-200 backdrop-blur-md">
                <NavButton to="/invoices" label="Invoices" />
                <NavButton to="/expenses" label="Expenses" />
            </div>
        </MemoryRouter>
    );
};

// Helper for the demo switcher
const NavButton: React.FC<{ to: string; label: string }> = ({ to, label }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const isActive = location.pathname === to || (to === "/invoices" && location.pathname === "/");

    return (
        <button
            onClick={() => navigate(to)}
            className={classNames(
                "rounded-full px-4 py-1.5 text-xs font-bold transition-all",
                isActive ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
            )}
        >
            {label}
        </button>
    )
}

export default TransactionsPage;
