// frontend/src/reports/CashflowReportPreview.tsx
import React from "react";
import { ReportShell } from "./ReportShell";
import { ReportSection, ReportKpi } from "./reportTypes";

interface CashflowReportPreviewProps {
    workspaceName: string;
    currencyCode: string;
    periodLabel: string;
    generatedAt: string;
    netChange: string;
    totalInflows: string;
    totalOutflows: string;
    runwayLabel?: string;
    trendData: Array<{
        periodLabel: string;
        inflows: string;
        outflows: string;
        net: string;
    }>;
    topDrivers: Array<{
        label: string;
        amount: string;
        type: "inflow" | "outflow";
    }>;
}

/**
 * Cashflow report preview component using ReportShell.
 * Maps cashflow data to KPIs, tables, and narrative sections.
 */
export const CashflowReportPreview: React.FC<CashflowReportPreviewProps> = (props) => {
    const kpis: ReportKpi[] = [
        {
            id: "net-change",
            label: "Net cash change",
            value: props.netChange,
            tone: "neutral",
            sublabel: props.runwayLabel || undefined,
        },
        {
            id: "inflows",
            label: "Total inflows",
            value: props.totalInflows,
            tone: "positive",
        },
        {
            id: "outflows",
            label: "Total outflows",
            value: props.totalOutflows,
            tone: "negative",
        },
    ];

    const trendSection: ReportSection = {
        id: "trend",
        title: "Cash movement trend",
        description: "Period-over-period cash inflows, outflows, and net change.",
        variant: "table",
        table: {
            columns: [
                { key: "period", label: "Period", width: "25%" },
                { key: "inflows", label: "Cash In", align: "right", width: "25%" },
                { key: "outflows", label: "Cash Out", align: "right", width: "25%" },
                { key: "net", label: "Net Change", align: "right", width: "25%" },
            ],
            rows: props.trendData.map((row) => ({
                period: row.periodLabel,
                inflows: row.inflows,
                outflows: row.outflows,
                net: row.net,
            })),
            totalsRow: null,
        },
    };

    const driversSection: ReportSection = {
        id: "drivers",
        title: "Top cash drivers",
        description: "Largest sources of cash in and cash out during this period.",
        variant: "table",
        table: {
            columns: [
                { key: "category", label: "Category", width: "50%" },
                { key: "type", label: "Type", width: "25%" },
                { key: "amount", label: "Amount", align: "right", width: "25%" },
            ],
            rows: props.topDrivers.map((driver) => ({
                category: driver.label,
                type: driver.type === "inflow" ? "Cash In" : "Cash Out",
                amount: driver.amount,
            })),
            totalsRow: null,
        },
    };

    const narrativeSection: ReportSection = {
        id: "summary",
        title: "Cashflow summary",
        variant: "text",
        body: (
            <p>
                This report shows the movement of cash for the selected period. Use it to
                understand where your money is coming from and where it's going. For detailed
                transaction-level analysis, review your bank feed and reconciliation reports.
            </p>
        ),
    };

    return (
        <ReportShell
            title="Cashflow Report"
            subtitle="Summary of cash inflows, outflows, and net cash movement."
            context={{
                workspaceName: props.workspaceName,
                periodLabel: props.periodLabel,
                generatedAt: props.generatedAt,
                currencyCode: props.currencyCode,
            }}
            kpis={kpis}
            sections={[narrativeSection, trendSection, driversSection]}
        />
    );
};
