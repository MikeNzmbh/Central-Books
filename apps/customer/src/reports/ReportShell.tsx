// frontend/src/reports/ReportShell.tsx
import React from "react";
import {
  ReportShellProps,
  ReportKpi,
  ReportSection,
  ReportTableConfig,
  ReportTableColumn,
} from "./reportTypes";

const cn = (...classes: Array<string | false | undefined | null>) =>
  classes.filter(Boolean).join(" ");

const toneClasses: Record<NonNullable<ReportKpi["tone"]>, string> = {
  positive: "border-emerald-300 bg-emerald-50",
  negative: "border-rose-300 bg-rose-50",
  neutral: "border-slate-200 bg-slate-50",
};

function KpiCard({ kpi }: { kpi: ReportKpi }) {
  const tone = kpi.tone ?? "neutral";
  return (
    <div
      className={cn(
        "rounded-xl border p-3 md:p-4 flex flex-col gap-1 min-w-[130px] avoid-break",
        "text-wrap",
        toneClasses[tone]
      )}
    >
      <div className="text-xs uppercase tracking-wide text-slate-500">
        {kpi.label}
      </div>
      <div className="text-lg md:text-xl font-semibold text-slate-900">
        {kpi.value}
      </div>
      {kpi.sublabel && (
        <div className="text-xs text-slate-500">{kpi.sublabel}</div>
      )}
    </div>
  );
}

function renderTable(table: ReportTableConfig) {
  const colAlign = (col: ReportTableColumn): string => {
    switch (col.align) {
      case "right":
        return "text-right";
      case "center":
        return "text-center";
      default:
        return "text-left";
    }
  };

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full border-collapse text-[11px] md:text-xs">
        <thead className="bg-slate-50">
          <tr>
            {table.columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-3 py-2 font-medium text-slate-600",
                  colAlign(col),
                  "text-wrap"
                )}
                style={col.width ? { width: col.width } : undefined}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, idx) => (
            <tr
              key={idx}
              className={idx % 2 === 0 ? "bg-white" : "bg-slate-50/50"}
            >
              {table.columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    "px-3 py-1.5 align-top text-slate-800",
                    colAlign(col)
                  )}
                >
                  {row[col.key]}
                </td>
              ))}
            </tr>
          ))}
          {table.totalsRow && (
            <tr className="bg-slate-900/5 border-t border-slate-300">
              {table.columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    "px-3 py-1.5 font-semibold text-slate-900",
                    colAlign(col)
                  )}
                >
                  {table.totalsRow![col.key]}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ReportSectionBlock({ section }: { section: ReportSection }) {
  return (
    <section className="flex flex-col gap-2">
      <div>
        <h2 className="text-sm md:text-base font-semibold text-slate-900 heading-responsive">
          {section.title}
        </h2>
        {section.description && (
          <p className="mt-1 text-[11px] md:text-xs text-slate-600 text-wrap">
            {section.description}
          </p>
        )}
      </div>

      {section.variant === "table" && section.table && renderTable(section.table)}

      {section.variant === "text" && section.body && (
        <div className="text-[11px] md:text-xs leading-relaxed text-slate-800 text-wrap">
          {section.body}
        </div>
      )}
    </section>
  );
}

export const ReportShell: React.FC<ReportShellProps> = ({
  title,
  subtitle,
  context,
  kpis,
  sections,
  footerNote,
  className,
}) => {
  return (
    <div
      className={cn(
        "bg-white text-slate-900 report-shell",
        "p-4 md:p-6 lg:p-8",
        "flex flex-col gap-4 md:gap-6",
        "text-wrap",
        className
      )}
    >
      {/* Header strip */}
      <header className="flex flex-col gap-2 border-b border-slate-200 pb-3 md:pb-4">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-2">
          <div className="flex flex-col gap-1">
            <div className="inline-flex items-center gap-2">
              <span className="rounded-full bg-slate-900 text-white px-2.5 py-0.5 text-[10px] uppercase tracking-wide">
                Clover Books
              </span>
              {context.currencyCode && (
                <span className="rounded-full bg-slate-100 text-slate-700 px-2 py-0.5 text-[10px]">
                  {context.currencyCode}
                </span>
              )}
            </div>
            <h1 className="text-base md:text-lg font-semibold heading-responsive">
              {title}
            </h1>
            {subtitle && (
              <p className="text-[11px] md:text-xs text-slate-600 text-balance">
                {subtitle}
              </p>
            )}
          </div>

          <div className="text-[10px] md:text-xs text-right text-slate-500 space-y-0.5">
            <div>{context.workspaceName}</div>
            {context.accountName && <div>Account: {context.accountName}</div>}
            {context.periodLabel && <div>Period: {context.periodLabel}</div>}
            <div>Generated: {context.generatedAt}</div>
          </div>
        </div>
      </header>

      {/* KPI row */}
      {kpis.length > 0 && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.id} kpi={kpi} />
          ))}
        </section>
      )}

      {/* Sections */}
      <main className="flex flex-col gap-4 md:gap-5">
        {sections.map((section) => (
          <ReportSectionBlock key={section.id} section={section} />
        ))}
      </main>

      {/* Footer */}
      <footer className="pt-3 mt-2 border-t border-dashed border-slate-200">
        <p className="text-[9px] leading-snug text-slate-500 text-balance">
          {footerNote ??
            "This report is for internal use only and is not tax, legal, or investment advice. Please consult a qualified professional before making decisions based on this data."}
        </p>
      </footer>
    </div>
  );
};
