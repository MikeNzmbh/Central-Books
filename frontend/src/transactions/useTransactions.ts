import { useState, useEffect, useCallback } from "react";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

export type TransactionKind = "invoice" | "expense";

export interface TransactionRow {
    id: string;
    number: string;
    entity: string;
    email: string;
    date: string;
    dueDate: string;
    amount: number;
    status: string;
    currency: string;
}

export interface TransactionStats {
    openBalance: number;
    totalCount: number;
    overdueCount: number;
    revenueYtd?: number;
    expensesYtd?: number;
}

interface InvoiceApiItem {
    id: number;
    invoice_number: string;
    customer_name: string | null;
    status: string;
    issue_date: string | null;
    due_date: string | null;
    grand_total: string;
    currency: string;
}

interface ExpenseApiItem {
    id: number;
    description: string;
    supplier_name: string | null;
    status: string;
    date: string | null;
    amount: string;
    currency: string;
}

interface InvoiceApiResponse {
    invoices: InvoiceApiItem[];
    stats: {
        total_count: number;
        open_balance: number;
        revenue_ytd: number;
        overdue_count: number;
    };
    currency: string;
}

interface ExpenseApiResponse {
    expenses: ExpenseApiItem[];
    stats: {
        total_count: number;
        outstanding: number;
        expenses_ytd: number;
    };
    currency: string;
}

// -----------------------------------------------------------------------------
// Helper: Format date for display
// -----------------------------------------------------------------------------

function formatDate(isoDate: string | null): string {
    if (!isoDate) return "—";
    try {
        return new Date(isoDate).toLocaleDateString("en-US", {
            month: "short",
            day: "2-digit",
            year: "numeric",
        });
    } catch {
        return isoDate;
    }
}

// -----------------------------------------------------------------------------
// Hook
// -----------------------------------------------------------------------------

export function useTransactions(kind: TransactionKind) {
    const [rows, setRows] = useState<TransactionRow[]>([]);
    const [stats, setStats] = useState<TransactionStats>({
        openBalance: 0,
        totalCount: 0,
        overdueCount: 0,
    });
    const [currency, setCurrency] = useState("USD");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const endpoint = kind === "invoice"
                ? "/api/invoices/list/"
                : "/api/expenses/list/";

            const res = await fetch(endpoint, {
                credentials: "include",
                headers: { "Accept": "application/json" },
            });

            if (!res.ok) {
                throw new Error(`Failed to fetch ${kind}s`);
            }

            if (kind === "invoice") {
                const data: InvoiceApiResponse = await res.json();

                const transformed: TransactionRow[] = data.invoices.map((inv) => ({
                    id: String(inv.id),
                    number: inv.invoice_number || `INV-${inv.id}`,
                    entity: inv.customer_name || "Unknown Customer",
                    email: "", // Not provided by API
                    date: formatDate(inv.issue_date),
                    dueDate: formatDate(inv.due_date),
                    amount: parseFloat(inv.grand_total) || 0,
                    status: inv.status || "draft",
                    currency: inv.currency || data.currency,
                }));

                setRows(transformed);
                setStats({
                    openBalance: data.stats.open_balance || 0,
                    totalCount: data.stats.total_count || 0,
                    overdueCount: data.stats.overdue_count || 0,
                    revenueYtd: data.stats.revenue_ytd || 0,
                });
                setCurrency(data.currency);
            } else {
                const data: ExpenseApiResponse = await res.json();

                const transformed: TransactionRow[] = data.expenses.map((exp) => ({
                    id: String(exp.id),
                    number: `EXP-${exp.id}`,
                    entity: exp.supplier_name || exp.description || "Unknown",
                    email: "",
                    date: formatDate(exp.date),
                    dueDate: formatDate(exp.date), // Expenses don't have due_date
                    amount: parseFloat(exp.amount) || 0,
                    status: exp.status || "unpaid",
                    currency: exp.currency || data.currency,
                }));

                setRows(transformed);
                setStats({
                    openBalance: data.stats.outstanding || 0,
                    totalCount: data.stats.total_count || 0,
                    overdueCount: 0, // Not provided by expenses API
                    expensesYtd: data.stats.expenses_ytd || 0,
                });
                setCurrency(data.currency);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, [kind]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return {
        rows,
        stats,
        currency,
        loading,
        error,
        refresh: fetchData,
    };
}

export default useTransactions;
