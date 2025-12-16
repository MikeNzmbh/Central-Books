// frontend/src/reconciliation/ReconciliationReportPage.tsx
import React, { useEffect, useState } from "react";
import { ReconciliationReportPreview } from "./ReconciliationReportPreview";
import { ReportPeriodPicker, PeriodSelection } from "../components/reports/ReportPeriodPicker";

interface ReconciliationReportPageProps {
    /** Session ID to load reconciliation data for */
    sessionId?: string;
    periodStart?: string;
    periodEnd?: string;
    periodPreset?: string;
    compareTo?: string;
}

interface ReconciliationSession {
    bank_account: {
        name: string;
        currency: string;
    };
    period: {
        label: string;
        start?: string;
        end?: string;
        preset?: string;
    };
    comparison?: {
        label?: string | null;
        start?: string | null;
        end?: string | null;
        compare_to?: string | null;
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
    periodStart,
    periodEnd,
    periodPreset,
    compareTo,
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
                const params = new URLSearchParams();
                if (periodStart) params.set("start_date", periodStart);
                if (periodEnd) params.set("end_date", periodEnd);
                if (periodPreset) params.set("period_preset", periodPreset);
                if (compareTo) params.set("compare_to", compareTo);
                const query = params.toString();
                const response = await fetch(`/api/reconciliation/session/${sessionId}/${query ? `?${query}` : ""}`);
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
    }, [compareTo, periodEnd, periodPreset, periodStart, sessionId]);

    const handlePrint = () => {
        window.print();
    };

    const handlePeriodChange = (selection: PeriodSelection) => {
        const params = new URLSearchParams(window.location.search);
        params.set("period_preset", selection.preset || "custom");
        if (selection.preset === "custom") {
            if (selection.startDate) params.set("start_date", selection.startDate);
            if (selection.endDate) params.set("end_date", selection.endDate);
        } else {
            params.delete("start_date");
            params.delete("end_date");
        }
        params.set("compare_to", selection.compareTo || "none");
        window.location.search = params.toString();
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

            <div className="max-w-5xl mx-auto px-4 pt-6 print:hidden">
                <div className="grid grid-cols-1 md:grid-cols-[1.2fr_minmax(0,1fr)] gap-4">
                    <div>
                        <p className="text-sm text-slate-600">Showing {session.period.label}</p>
                        {session.comparison?.label && (
                            <p className="text-[12px] text-slate-500">Compared to {session.comparison.label}</p>
                        )}
                    </div>
                    <ReportPeriodPicker
                        preset={(session.period.preset as PeriodSelection["preset"]) || "custom"}
                        startDate={session.period.start}
                        endDate={session.period.end}
                        compareTo={(session.comparison?.compare_to as PeriodSelection["compareTo"]) || "none"}
                        onApply={handlePeriodChange}
                        onChange={(sel) => {
                            if (sel.preset !== "custom") handlePeriodChange(sel);
                        }}
                        className="justify-self-end"
                    />
                </div>
            </div>

            <ReconciliationReportPreview
                workspaceName="Clover Books"
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
