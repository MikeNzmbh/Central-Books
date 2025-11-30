// frontend/src/reports/CashflowReportPrintPage.tsx
import React from "react";
import { CashflowReportPreview } from "./CashflowReportPreview";
import { CashflowReportProps } from "./CashflowReportPage";

/**
 * Print-friendly cashflow report page.
 * Receives data via props (from Django template) and renders CashflowReportPreview.
 * Users can use browser Print → "Save as PDF".
 */
export const CashflowReportPrintPage: React.FC<CashflowReportProps> = (props) => {
    const handlePrint = () => {
        window.print();
    };

    const formatCurrency = (value: number): string => {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: props.baseCurrency,
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

            <CashflowReportPreview
                workspaceName="CERN Books"
                currencyCode={props.baseCurrency}
                periodLabel={props.asOfLabel}
                generatedAt={new Date().toLocaleString()}
                netChange={formatCurrency(props.summary.netChange)}
                totalInflows={formatCurrency(props.summary.totalInflows)}
                totalOutflows={formatCurrency(props.summary.totalOutflows)}
                runwayLabel={props.summary.runwayLabel || undefined}
                trendData={props.trend.map((point) => ({
                    periodLabel: point.periodLabel,
                    inflows: formatCurrency(point.inflows),
                    outflows: formatCurrency(point.outflows),
                    net: formatCurrency(point.net),
                }))}
                topDrivers={props.topDrivers.map((driver) => ({
                    label: driver.label,
                    amount: formatCurrency(driver.amount),
                    type: driver.type,
                }))}
            />
        </div>
    );
};

export default CashflowReportPrintPage;
