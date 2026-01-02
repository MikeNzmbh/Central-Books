import React, { useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink, FileText, ShieldCheck } from "lucide-react";
import { useExpenseTaxDrilldown, useInvoiceTaxDrilldown } from "../companion/useTaxDocuments";

const severityBadge = (sev: string) => {
  const map: Record<string, string> = {
    high: "bg-rose-50 text-rose-700 border border-rose-200",
    medium: "bg-amber-50 text-amber-700 border border-amber-200",
    low: "bg-slate-100 text-slate-700 border border-slate-200",
  };
  return map[sev] || map.low;
};

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    OPEN: "bg-blue-50 text-blue-700 border border-blue-200",
    ACKNOWLEDGED: "bg-amber-50 text-amber-700 border border-amber-200",
    RESOLVED: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    IGNORED: "bg-slate-100 text-slate-600 border border-slate-200",
  };
  return map[status] || map.OPEN;
};

const toNumber = (value: string | number | null | undefined) => {
  if (value === null || value === undefined) return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : 0;
};

const formatMoney = (value: string | number | null | undefined, currency: string) => {
  const num = toNumber(value);
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num);
  } catch {
    return `$${num.toFixed(2)}`;
  }
};

export default function TaxDocumentDrilldownCard(props: { documentType: "invoice" | "expense"; documentId: string | number }) {
  const { data, isLoading, error } =
    props.documentType === "invoice" ? useInvoiceTaxDrilldown(props.documentId) : useExpenseTaxDrilldown(props.documentId);

  const [expanded, setExpanded] = useState(false);

  const jurisdictions = useMemo(() => {
    const rows = data?.breakdown?.by_jurisdiction || [];
    return rows
      .map((r) => r.jurisdiction_code)
      .filter(Boolean)
      .sort();
  }, [data]);

  return (
    <div className="border border-slate-200 rounded-2xl bg-white shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-lg bg-slate-900 flex items-center justify-center shadow-sm">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">Tax breakdown</div>
              <div className="text-xs text-slate-500">
                {data?.period_key ? `Period ${data.period_key}` : "Tax Engine v1"}
                {jurisdictions.length > 0 && (
                  <span className="ml-2 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                    Jurisdictions: {jurisdictions.join(", ")}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
        {data?.tax_guardian_link && (
          <a
            href={data.tax_guardian_link}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
          >
            Tax Guardian
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>

      <div className="p-4 space-y-3">
        {isLoading && <div className="text-sm text-slate-600">Loading tax breakdown…</div>}
        {error && (
          <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">
            Couldn’t load tax breakdown. This does not affect your saved document.
          </div>
        )}

        {data && (
          <>
            {!data.line_level_available && data.breakdown_note && (
              <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg p-3">
                {data.breakdown_note}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="border border-slate-200 rounded-xl p-3 bg-white">
                <div className="text-[11px] uppercase font-semibold text-slate-500">Net</div>
                <div className="text-lg font-bold text-slate-900 font-mono-soft">{formatMoney(data.totals.net_total, data.currency)}</div>
              </div>
              <div className="border border-slate-200 rounded-xl p-3 bg-white">
                <div className="text-[11px] uppercase font-semibold text-slate-500">Tax</div>
                <div className="text-lg font-bold text-slate-900 font-mono-soft">{formatMoney(data.totals.tax_total, data.currency)}</div>
              </div>
              <div className="border border-slate-200 rounded-xl p-3 bg-white">
                <div className="text-[11px] uppercase font-semibold text-slate-500">Gross</div>
                <div className="text-lg font-bold text-slate-900 font-mono-soft">{formatMoney(data.totals.gross_total, data.currency)}</div>
              </div>
            </div>

            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <div className="px-3 py-2 bg-slate-50 text-xs font-semibold text-slate-600">By jurisdiction</div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-white text-slate-600">
                    <tr className="border-b border-slate-100">
                      <th className="px-3 py-2 text-left">Jurisdiction</th>
                      <th className="px-3 py-2 text-right">Taxable base</th>
                      <th className="px-3 py-2 text-right">Tax</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.breakdown.by_jurisdiction || []).map((row) => (
                      <tr key={row.jurisdiction_code} className="border-b border-slate-50">
                        <td className="px-3 py-2 font-semibold text-slate-800">{row.jurisdiction_code || "—"}</td>
                        <td className="px-3 py-2 text-right font-mono-soft text-slate-700">{formatMoney(row.taxable_base, data.currency)}</td>
                        <td className="px-3 py-2 text-right font-mono-soft text-slate-700">{formatMoney(row.tax_total, data.currency)}</td>
                      </tr>
                    ))}
                    {(data.breakdown.by_jurisdiction || []).length === 0 && (
                      <tr>
                        <td colSpan={3} className="px-3 py-6 text-center text-sm text-slate-500">
                          No jurisdiction breakdown available.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <button
              onClick={() => setExpanded((v) => !v)}
              className="w-full inline-flex items-center justify-between px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50"
            >
              <span>Line-level components</span>
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {expanded && (
              <div className="border border-slate-200 rounded-xl p-3 bg-white space-y-3">
                {(data.lines || []).map((line) => (
                  <div key={line.line_id} className="border border-slate-100 rounded-lg p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{line.description}</div>
                        {line.tax_group && (
                          <div className="text-xs text-slate-500 mt-0.5">
                            Tax group: <span className="font-semibold text-slate-700">{line.tax_group}</span>
                          </div>
                        )}
                      </div>
                      <div className="text-sm font-semibold text-slate-900 font-mono-soft">{formatMoney(line.net_amount, data.currency)}</div>
                    </div>

                    <div className="mt-3 overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="text-slate-600">
                          <tr className="border-b border-slate-100">
                            <th className="py-1 text-left">Component</th>
                            <th className="py-1 text-left">Jurisdiction</th>
                            <th className="py-1 text-right">Rate</th>
                            <th className="py-1 text-right">Tax</th>
                            <th className="py-1 text-right">Recoverable</th>
                          </tr>
                        </thead>
                        <tbody>
                          {line.tax_details.map((td, idx) => (
                            <tr key={`${line.line_id}-${idx}`} className="border-b border-slate-50">
                              <td className="py-1 text-slate-800">{td.tax_component_name || "—"}</td>
                              <td className="py-1 text-slate-700">{td.jurisdiction_code || "—"}</td>
                              <td className="py-1 text-right font-mono-soft text-slate-600">{td.rate ?? "—"}</td>
                              <td className="py-1 text-right font-mono-soft text-slate-700">{formatMoney(td.tax_amount, data.currency)}</td>
                              <td className="py-1 text-right">
                                <span
                                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${td.is_recoverable ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-700 border-slate-200"
                                    }`}
                                >
                                  {td.is_recoverable ? "Yes" : "No"}
                                </span>
                              </td>
                            </tr>
                          ))}
                          {line.tax_details.length === 0 && (
                            <tr>
                              <td colSpan={5} className="py-3 text-center text-sm text-slate-500">
                                No line-level tax details.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="border border-slate-200 rounded-xl p-3 bg-white">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                {data.anomalies.length === 0 ? (
                  <>
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    No tax anomalies detected for this document
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    Possible tax issues ({data.anomalies.length})
                  </>
                )}
              </div>

              {data.anomalies.length > 0 && (
                <div className="mt-3 space-y-2">
                  {data.anomalies.map((a) => (
                    <div key={a.id} className="flex items-start justify-between gap-3 border border-slate-100 rounded-lg p-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded-full text-[11px] font-semibold border ${severityBadge(a.severity)}`}>
                            {a.severity.toUpperCase()}
                          </span>
                          <span className={`px-2 py-1 rounded-full text-[11px] font-semibold border ${statusBadge(a.status)}`}>
                            {a.status}
                          </span>
                          <span className="text-xs font-semibold text-slate-700">{a.code}</span>
                        </div>
                        <div className="text-sm text-slate-700 mt-1 truncate" title={a.description}>
                          {a.description}
                        </div>
                      </div>
                      <a
                        href={data.tax_guardian_link}
                        className="shrink-0 inline-flex items-center gap-1 text-sm font-semibold text-sky-700 hover:text-sky-900"
                      >
                        View in Tax Guardian <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  ))}
                </div>
              )}

              {data.anomalies.length === 0 && (
                <div className="mt-2 text-xs text-slate-500">
                  Tax amounts remain deterministic; this section surfaces only what’s already computed.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
