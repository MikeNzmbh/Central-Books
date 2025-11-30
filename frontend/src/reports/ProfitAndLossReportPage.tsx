// frontend/src/reports/ProfitAndLossReportPage.tsx
import React from "react";
import { ProfitAndLossReportPreview } from "./ProfitAndLossReportPreview";

interface PLReportPageProps {
    periodLabel: string;
    currency: string;
    totalRevenue: number;
    totalExpenses: number;
    netIncome: number;
    revenueItems: Array<{
        category: string;
        amount: number;
    }>;
    expenseItems: Array<{
        category: string;
        amount: number;
    }>;
}

/**
 * Print-friendly P&L report page.
 * Receives data via props (from Django template) and renders ProfitAndLossReportPreview.
 * Users can use browser Print → "Save as PDF".
 */
export const ProfitAndLossReportPage: React.FC<PLReportPageProps> = (props) => {
    const handlePrint = () => {
        window.print();
    };

    const formatCurrency = (value: number): string => {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: props.currency,
        }).format(value);
    };

    return (
        <div className="min-h-screen bg-white print:bg-white">
            {/* Print button - hidden when printing */}
            <div className="fixed top-4 right-4 print:hidden z-50">
                <button
                    onClick={handlePrint}
                    className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-lg hover:bg-slate-800"
                >
                    Print Report
                </button>
            </div>

            <ProfitAndLossReportPreview
                workspaceName="CERN Books"
                currencyCode={props.currency}
                periodLabel={props.periodLabel}
                generatedAt={new Date().toLocaleString()}
                totalRevenue={formatCurrency(props.totalRevenue)}
                totalExpenses={formatCurrency(props.totalExpenses)}
                netIncome={formatCurrency(props.netIncome)}
                revenueItems={props.revenueItems.map((item) => ({
                    category: item.category,
                    amount: formatCurrency(item.amount),
                }))}
                expenseItems={props.expenseItems.map((item) => ({
                    category: item.category,
                    amount: formatCurrency(item.amount),
                }))}
            />
        </div>
    );
};

export default ProfitAndLossReportPage;
