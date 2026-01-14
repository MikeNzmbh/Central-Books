// frontend/src/reports/ProfitAndLossReportPreview.tsx
import React from "react";
import { ReportShell } from "./ReportShell";
import { ReportSection, ReportKpi } from "./reportTypes";

interface PLReportPreviewProps {
    workspaceName: string;
    currencyCode: string;
    periodLabel: string;
    generatedAt: string;
    totalRevenue: string;
    totalExpenses: string;
    netIncome: string;
    revenueItems: Array<{
        category: string;
        amount: string;
    }>;
    expenseItems: Array<{
        category: string;
        amount: string;
    }>;
}

/**
 * Profit & Loss report preview component using ReportShell.
 * Displays revenue, expenses, and net income with detailed breakdowns.
 */
export const ProfitAndLossReportPreview: React.FC<PLReportPreviewProps> = (props) => {
    const kpis: ReportKpi[] = [
        {
            id: "revenue",
            label: "Total revenue",
            value: props.totalRevenue,
            tone: "positive",
        },
        {
            id: "expenses",
            label: "Total expenses",
            value: props.totalExpenses,
            tone: "negative",
        },
        {
            id: "net-income",
            label: "Net income",
            value: props.netIncome,
            tone: "neutral",
            sublabel: "Revenue minus expenses",
        },
    ];

    const revenueSection: ReportSection = {
        id: "revenue",
        title: "Revenue breakdown",
        description: "All income categories for this period.",
        variant: "table",
        table: {
            columns: [
                { key: "category", label: "Category", width: "70%" },
                { key: "amount", label: "Amount", align: "right", width: "30%" },
            ],
            rows: props.revenueItems.map((item) => ({
                category: item.category,
                amount: item.amount,
            })),
            totalsRow: {
                category: "Total Revenue",
                amount: props.totalRevenue,
            },
        },
    };

    const expensesSection: ReportSection = {
        id: "expenses",
        title: "Expenses breakdown",
        description: "All expense categories for this period.",
        variant: "table",
        table: {
            columns: [
                { key: "category", label: "Category", width: "70%" },
                { key: "amount", label: "Amount", align: "right", width: "30%" },
            ],
            rows: props.expenseItems.map((item) => ({
                category: item.category,
                amount: item.amount,
            })),
            totalsRow: {
                category: "Total Expenses",
                amount: props.totalExpenses,
            },
        },
    };

    const summarySection: ReportSection = {
        id: "summary",
        title: "Profit & Loss summary",
        variant: "text",
        body: (
            <p>
                This report shows your revenue, expenses, and net income for the selected period.
                Use it to understand profitability and track your business performance over time.
                For tax reporting, please consult with a qualified accountant.
            </p>
        ),
    };

    return (
        <ReportShell
            title="Profit & Loss Report"
            subtitle="Summary of revenue, expenses, and net income for the period."
            context={{
                workspaceName: props.workspaceName,
                periodLabel: props.periodLabel,
                generatedAt: props.generatedAt,
                currencyCode: props.currencyCode,
            }}
            kpis={kpis}
            sections={[summarySection, revenueSection, expensesSection]}
        />
    );
};
