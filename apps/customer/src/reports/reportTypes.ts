// frontend/src/reports/reportTypes.ts
import { ReactNode } from "react";

export type ReportKpiTone = "positive" | "negative" | "neutral";

export interface ReportKpi {
  id: string;
  label: string;
  value: string;
  sublabel?: string;
  tone?: ReportKpiTone;
}

export type ReportTableAlign = "left" | "right" | "center";

export interface ReportTableColumn {
  key: string;
  label: string;
  align?: ReportTableAlign;
  width?: string; // optional, e.g. "20%", "120px"
}

export type ReportTableRow = Record<string, ReactNode>;

export interface ReportTableConfig {
  columns: ReportTableColumn[];
  rows: ReportTableRow[];
  totalsRow?: ReportTableRow | null;
}

export type ReportSectionVariant = "table" | "text";

export interface ReportSection {
  id: string;
  title: string;
  description?: string;
  variant: ReportSectionVariant;
  table?: ReportTableConfig;
  body?: ReactNode;
}

export interface ReportContextMeta {
  workspaceName: string;
  periodLabel?: string;
  generatedAt: string; // preformatted label e.g. "Nov 30, 2025 · 09:45"
  accountName?: string;
  currencyCode?: string;
}

export interface ReportShellProps {
  title: string; // "Reconciliation Report"
  subtitle?: string; // optional extra line
  context: ReportContextMeta;
  kpis: ReportKpi[];
  sections: ReportSection[];
  footerNote?: string;
  className?: string; // optional extra classes for outer container
}
