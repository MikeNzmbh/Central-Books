// frontend/src/reconciliation/ReconciliationReportPage.tsx
import React, { useEffect, useState } from "react";
import { ReconciliationReportPreview } from "./ReconciliationReportPreview";

interface ReconciliationReportPageProps {
    /** Session ID to load reconciliation data for */
    sessionId?: string;
}

interface ReconciliationSession {
    bank_account: {
        name: string;
        currency: string;
    };
    period: {
        label: string;
    };
    opening_balance: number;
    statement_ending_balance: number;
    ledger_ending_balance: number;
    difference: number;
    unreconciled_count: number;
    reconciled_count?: number;
    total_transactions?: number;
    feed: Array<{
        id: string;
        date: string;
        description: string;
        amount: number;
        status: "matched" | "new" | "excluded";
        reconciliation_status?: "reconciled" | "unreconciled";
    }>;
}

/**
 * Print-friendly reconciliation report page.
 * Loads data via API and renders ReconciliationReportPreview.
 * Users can use browser Print → "Save as PDF".
 */
export const ReconciliationReportPage: React.FC<ReconciliationReportPageProps> = ({
    sessionId,
}) => {
    const [session, setSession] = useState<ReconciliationSession | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!sessionId) {
            setError("No session ID provided");
            setLoading(false);
            return;
        }

        const fetchSession = async () => {
            try {
                const response = await fetch(`/api/reconciliation/session/${sessionId}/`);
                if (!response.ok) {
                    throw new Error("Failed to load reconciliation session");
                }
                const data = await response.json();
                setSession(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load data");
            } finally {
                setLoading(false);
            }
        };

        fetchSession();
    }, [sessionId]);

    const handlePrint = () => {
        window.print();
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-white flex items-center justify-center">
                <div className="text-slate-600">Loading report...</div>
            </div>
        );
    }

    if (error || !session) {
        return (
            <div className="min-h-screen bg-white flex items-center justify-center">
                <div className="text-rose-600">{error || "Session not found"}</div>
            </div>
        );
    }

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: session.bank_account.currency,
        }).format(value);
    };

    const differenceTone =
        Math.abs(session.difference) < 0.01
            ? "neutral"
            : session.difference > 0
                ? "positive"
                : "negative";

    return (
        <div className="min-h-screen bg-white print:bg-white">
            {/* Print button - hidden when printing */}
            <div className="fixed top-4 right-4 print:hidden">
                <button
                    onClick={handlePrint}
                    className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-lg hover:bg-slate-800"
                >
                    Print Report
                </button>
            </div>

            <ReconciliationReportPreview
                workspaceName="CERN Books"
                currencyCode={session.bank_account.currency}
                accountName={session.bank_account.name}
                periodLabel={session.period.label}
                generatedAt={new Date().toLocaleString()}
                openingBalance={formatCurrency(session.opening_balance)}
                statementClosingBalance={formatCurrency(session.statement_ending_balance)}
                ledgerClosingBalance={formatCurrency(session.ledger_ending_balance)}
                difference={formatCurrency(session.difference)}
                differenceTone={differenceTone}
                unreconciledCount={session.unreconciled_count}
                reconciledCount={session.reconciled_count}
                totalCount={session.total_transactions}
                feedRows={session.feed.map((item) => ({
                    date: item.date,
                    description: item.description,
                    reference: item.id,
                    amount: formatCurrency(item.amount),
                    status: item.reconciliation_status === "reconciled" ? "reconciled" : "unreconciled",
                }))}
            />
        </div>
    );
};

export default ReconciliationReportPage;
