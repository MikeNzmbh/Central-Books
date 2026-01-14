// frontend/src/reconciliation/ReconciliationReportPreview.tsx
import React from "react";
import { ReportShell } from "../reports/ReportShell";
import { ReportSection, ReportKpi } from "../reports/reportTypes";

interface ReconciliationReportPreviewProps {
  workspaceName: string;
  currencyCode: string;
  accountName: string;
  periodLabel: string;
  generatedAt: string;
  openingBalance: string; // formatted, e.g. "$1,200.00"
  statementClosingBalance: string;
  ledgerClosingBalance: string;
  difference: string; // e.g. "$35.00"
  differenceTone: "positive" | "negative" | "neutral";
  unreconciledCount: number;
  reconciledCount?: number;
  totalCount?: number;
  feedRows: {
    date: string;
    description: string;
    reference: string;
    amount: string;
    status: "reconciled" | "unreconciled";
  }[];
}

export const ReconciliationReportPreview: React.FC<
  ReconciliationReportPreviewProps
> = (props) => {
  const kpis: ReportKpi[] = [
    {
      id: "opening",
      label: "Opening balance",
      value: props.openingBalance,
      tone: "neutral",
    },
    {
      id: "statement",
      label: "Statement closing",
      value: props.statementClosingBalance,
      tone: "neutral",
    },
    {
      id: "ledger",
      label: "Ledger closing",
      value: props.ledgerClosingBalance,
      tone: "neutral",
    },
    {
      id: "difference",
      label: "Difference",
      value: props.difference,
      sublabel:
        props.unreconciledCount > 0
          ? `${props.unreconciledCount} unreconciled items`
          : "Fully reconciled",
      tone: props.differenceTone,
    },
    {
      id: "reco-ratio",
      label: "Reconciliation progress",
      value: props.totalCount
        ? `${props.reconciledCount ?? 0} / ${props.totalCount}`
        : `${props.reconciledCount ?? 0} reconciled`,
      sublabel:
        props.totalCount && props.totalCount > 0
          ? `${Math.round(((props.reconciledCount ?? 0) / props.totalCount) * 100)}% reconciled`
          : undefined,
      tone: "neutral",
    },
  ];

  const feedSection: ReportSection = {
    id: "feed",
    title: "Bank feed summary",
    description:
      "This table shows the reconciled and unreconciled transactions for the selected statement period.",
    variant: "table",
    table: {
      columns: [
        { key: "date", label: "Date", width: "14%" },
        { key: "description", label: "Description", width: "42%" },
        { key: "reference", label: "Ref.", width: "14%" },
        { key: "amount", label: "Amount", align: "right", width: "15%" },
        { key: "status", label: "Status", align: "right", width: "15%" },
      ],
      rows: props.feedRows.map((r) => ({
        date: r.date,
        description: r.description,
        reference: r.reference,
        amount: r.amount,
        status: r.status === "reconciled" ? "Reconciled" : "Unreconciled",
      })),
      totalsRow: null,
    },
  };

  const narrativeSection: ReportSection = {
    id: "summary",
    title: "Reconciliation summary",
    variant: "text",
    body: (
      <p>
        For this period, the bank statement and the ledger are{" "}
        <strong>
          {props.differenceTone === "neutral" ? "fully aligned" : "not aligned"}
        </strong>
        . The difference reflects items that are still pending review or
        allocation. Use this report as an internal record of your reconciliation
        work and keep it alongside your statement PDFs.
      </p>
    ),
  };

  return (
    <ReportShell
      title="Reconciliation Report"
      subtitle="Summary of bank statements and ledger balances for the selected period."
      context={{
        workspaceName: props.workspaceName,
        periodLabel: props.periodLabel,
        generatedAt: props.generatedAt,
        accountName: props.accountName,
        currencyCode: props.currencyCode,
      }}
      kpis={kpis}
      sections={[narrativeSection, feedSection]}
    />
  );
};
