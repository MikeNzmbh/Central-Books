import React from "react";

export const cn = (...classes: (string | false | null | undefined)[]) =>
  classes.filter(Boolean).join(" ");

export const StatusPill: React.FC<{ tone?: "good" | "bad" | "warning" | "neutral"; label: string }> = ({
  tone = "neutral",
  label,
}) => {
  const map: Record<"good" | "bad" | "warning" | "neutral", string> = {
    good: "bg-emerald-50 text-emerald-700 border-emerald-200",
    bad: "bg-rose-50 text-rose-700 border-rose-200",
    warning: "bg-amber-50 text-amber-700 border-amber-200",
    neutral: "bg-slate-100 text-slate-700 border-slate-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide uppercase",
        map[tone]
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
};

export const Card: React.FC<{ title?: string; subtitle?: string; children?: React.ReactNode; footer?: React.ReactNode }> =
  ({ title, subtitle, children, footer }) => {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        {(title || subtitle) && (
          <header className="border-b border-slate-200 px-4 py-3 sm:px-5 sm:py-4 flex items-center justify-between gap-3">
            <div>
              {title && <h3 className="text-sm font-semibold text-slate-900">{title}</h3>}
              {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
            </div>
            {footer && <div className="text-xs text-slate-500 flex-shrink-0">{footer}</div>}
          </header>
        )}
        <div className="px-4 py-3 sm:px-5 sm:py-4 text-sm text-slate-700">{children}</div>
      </section>
    );
  };

interface SimpleTableProps {
  headers: string[];
  rows: React.ReactNode[][];
}

export const SimpleTable: React.FC<SimpleTableProps> = ({ headers, rows }) => {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-xs sm:text-sm border-separate border-spacing-y-2">
        <thead>
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, idx) => (
            <tr
              key={idx}
              className="rounded-xl bg-white shadow-[0_1px_3px_rgba(15,23,42,0.06)] ring-1 ring-slate-200/80 hover:bg-slate-50"
            >
              {cells.map((cell, i) => (
                <td key={i} className="px-3 py-2 align-middle text-slate-800">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
