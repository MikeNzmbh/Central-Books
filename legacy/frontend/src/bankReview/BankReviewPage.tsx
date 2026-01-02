import React, { useCallback, useEffect, useState } from "react";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const trimmed = cookie.trim();
    if (trimmed.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmed.substring(name.length + 1));
    }
  }
  return null;
}

function getCsrfToken(): string {
  return (
    document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value ||
    getCookie("csrftoken") ||
    ""
  );
}

type RunStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
type RiskLevel = "low" | "medium" | "high" | "unknown";

interface AuditFlag {
  code: string;
  severity?: string;
  message?: string;
}

interface BankTransactionReview {
  id: number;
  status: string;
  raw_payload: Record<string, any>;
  matched_journal_ids: number[];
  audit_flags: AuditFlag[] | Record<string, any>;
  audit_score: string | number | null;
  audit_explanations?: string[];
  risk_level?: RiskLevel | null;
  error_message?: string;
}

interface RankedTransaction {
  transaction_id: number | string;
  priority: string;
  reason: string;
}

interface BankReviewRun {
  id: number;
  created_at: string;
  status: RunStatus;
  period_start?: string | null;
  period_end?: string | null;
  metrics?: Record<string, any>;
  overall_risk_score?: string | number | null;
  risk_level?: RiskLevel | null;
  trace_id?: string | null;
}

interface RunDetail extends BankReviewRun {
  transactions: BankTransactionReview[];
  llm_explanations?: string[];
  llm_ranked_transactions?: RankedTransaction[];
  llm_suggested_followups?: string[];
}

const RISK_THRESHOLDS = { medium: 40, high: 70 };

const parseRiskScore = (score: string | number | null | undefined): number | null => {
  if (typeof score === "number") return Number.isFinite(score) ? score : null;
  if (typeof score === "string") {
    const parsed = parseFloat(score);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const deriveRiskLevel = (score: string | number | null | undefined): RiskLevel => {
  const parsed = parseRiskScore(score);
  if (parsed === null) return "unknown";
  if (parsed >= RISK_THRESHOLDS.high) return "high";
  if (parsed >= RISK_THRESHOLDS.medium) return "medium";
  return "low";
};

const riskColors: Record<RiskLevel, string> = {
  high: "bg-rose-100 text-rose-700 border border-rose-200",
  medium: "bg-amber-100 text-amber-800 border border-amber-200",
  low: "bg-emerald-100 text-emerald-700 border border-emerald-200",
  unknown: "bg-slate-100 text-slate-600 border border-slate-200",
};

const RiskBadge: React.FC<{ score: string | number | null | undefined }> = ({ score }) => {
  const level = deriveRiskLevel(score);
  const parsed = parseRiskScore(score);
  const label =
    level === "high" ? "High risk" : level === "medium" ? "Medium risk" : level === "low" ? "Low risk" : "Unknown risk";
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold inline-flex items-center gap-1 ${riskColors[level]}`}>
      {label}
      {parsed !== null ? ` · ${parsed.toFixed(0)}` : ""}
    </span>
  );
};

const formatDateTime = (iso: string) => new Date(iso).toLocaleString();

const BankReviewPage: React.FC = () => {
  const [runs, setRuns] = useState<BankReviewRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [periodStart, setPeriodStart] = useState<string>("");
  const [periodEnd, setPeriodEnd] = useState<string>("");
  const [linesJson, setLinesJson] = useState<string>('[{"date":"2025-01-01","description":"Bank deposit","amount":100}]');
  const [highlightedTxId, setHighlightedTxId] = useState<number | null>(null);

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const res = await fetch("/api/agentic/bank-review/runs");
      const json = await res.json();
      setRuns(json.runs || []);
    } catch (err) {
      setError("Unable to load bank review runs");
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  const loadRunDetail = useCallback(async (runId: number) => {
    try {
      const res = await fetch(`/api/agentic/bank-review/run/${runId}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to load run");
      setSelectedRun(json);
    } catch (err) {
      setError("Unable to load run details");
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const runReview = async () => {
    setRunning(true);
    setError(null);
    setInfo(null);
    const normalizeDate = (value: string | null) => {
      if (!value) return "";
      if (/^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10);
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return "";
      return parsed.toISOString().slice(0, 10);
    };
    const form = new FormData();
    const startIso = normalizeDate(periodStart);
    const endIso = normalizeDate(periodEnd);
    if (periodStart && !startIso) {
      setError("Invalid period start. Use YYYY-MM-DD.");
      setRunning(false);
      return;
    }
    if (periodEnd && !endIso) {
      setError("Invalid period end. Use YYYY-MM-DD.");
      setRunning(false);
      return;
    }
    if (startIso) form.append("period_start", startIso);
    if (endIso) form.append("period_end", endIso);
    form.append("lines", linesJson);
    try {
      const res = await fetch("/api/agentic/bank-review/run", {
        method: "POST",
        body: form,
        headers: { "X-CSRFToken": getCsrfToken() },
        credentials: "same-origin",
      });
      const text = await res.text();
      let json: any;
      try {
        json = JSON.parse(text);
      } catch {
        // Server returned HTML instead of JSON (likely a CSRF or server error page)
        console.error("Server returned non-JSON response:", text.slice(0, 200));
        throw new Error("Server returned an unexpected response. Please try again or check logs.");
      }
      if (!res.ok) throw new Error(json.error || "Review failed");
      setInfo(`Review ${json.run_id} completed`);
      await loadRuns();
      if (json.run_id) {
        await loadRunDetail(json.run_id);
      }
    } catch (err: any) {
      setError(err?.message || "Review failed");
    } finally {
      setRunning(false);
    }
  };

  const normalizeFlags = (flags: BankTransactionReview["audit_flags"]): AuditFlag[] => {
    if (Array.isArray(flags)) return flags;
    if (flags && typeof flags === "object") return Object.values(flags) as AuditFlag[];
    return [];
  };

  const llmExplanations = selectedRun?.llm_explanations || [];
  const llmRanked = selectedRun?.llm_ranked_transactions || [];
  const llmFollowups = selectedRun?.llm_suggested_followups || [];
  const hasLlmInsights = llmExplanations.length > 0 || llmRanked.length > 0 || llmFollowups.length > 0;

  const focusTransaction = (txId: number | string | null | undefined) => {
    if (txId === null || txId === undefined) return;
    const parsed = Number(txId);
    if (!Number.isFinite(parsed)) return;
    setHighlightedTxId(parsed);
    const el = document.getElementById(`tx-${parsed}`);
    if (el && typeof (el as any).scrollIntoView === "function") {
      (el as any).scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  useEffect(() => {
    if (highlightedTxId === null) return;
    const timer = setTimeout(() => setHighlightedTxId(null), 2000);
    return () => clearTimeout(timer);
  }, [highlightedTxId]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium text-slate-500 uppercase">Bank Companion</p>
            <h1 className="text-2xl font-semibold">Bank Review</h1>
            <p className="text-sm text-slate-500">Review bank transactions against the ledger.</p>
          </div>
        </div>

        {error && <div className="rounded-lg bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3">{error}</div>}
        {info && <div className="rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3">{info}</div>}

        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Run a bank review</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="block">
              <span className="text-xs text-slate-600">Period start</span>
              <input
                type="date"
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1 text-sm"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Period end</span>
              <input
                type="date"
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1 text-sm"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
              />
            </label>
            <div className="flex items-end justify-end">
              <button
                onClick={runReview}
                disabled={running}
                className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800 disabled:opacity-50"
              >
                {running ? "Running…" : "Run bank review"}
              </button>
            </div>
          </div>
          <div>
            <span className="text-xs text-slate-600">Bank lines (JSON)</span>
            <textarea
              className="w-full mt-1 border border-slate-200 rounded px-2 py-1 text-sm min-h-[100px]"
              value={linesJson}
              onChange={(e) => setLinesJson(e.target.value)}
            />
            <div className="text-[11px] text-slate-500 mt-1">{"Provide an array of {date, description, amount, external_id?}."}</div>
          </div>
        </section>

        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Previous runs</h2>
            <button
              onClick={loadRuns}
              className="text-xs font-semibold text-slate-600 border border-slate-200 rounded px-2 py-1"
            >
              Refresh
            </button>
          </div>
          {loadingRuns ? (
            <div className="text-sm text-slate-500">Loading…</div>
          ) : runs.length === 0 ? (
            <div className="text-sm text-slate-500">No bank reviews yet.</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-xs uppercase text-slate-500">
                    <th className="py-2">Run</th>
                    <th>Period</th>
                    <th>Status</th>
                    <th>Risk</th>
                    <th>Unreconciled</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-t border-slate-100">
                      <td className="py-2 font-semibold text-slate-800">#{run.id}</td>
                      <td className="text-slate-600">
                        {run.period_start || "—"} – {run.period_end || "—"}
                      </td>
                      <td className="text-slate-600">{run.status}</td>
                      <td>
                        <RiskBadge score={run.overall_risk_score} />
                      </td>
                      <td className="text-slate-600">{run.metrics?.transactions_unreconciled ?? "—"}</td>
                      <td>
                        <button
                          className="text-xs font-semibold text-sky-700 hover:text-sky-900"
                          onClick={() => loadRunDetail(run.id)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {selectedRun && (
          <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">Run #{selectedRun.id}</h3>
                <p className="text-xs text-slate-500">
                  {selectedRun.period_start || "—"} – {selectedRun.period_end || "—"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {selectedRun.trace_id && (
                  <a
                    href={`/agentic/console?trace=${encodeURIComponent(selectedRun.trace_id)}`}
                    className="text-xs font-semibold text-sky-700 hover:text-sky-900 underline"
                  >
                    View in console
                  </a>
                )}
                <RiskBadge score={selectedRun.overall_risk_score} />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className="border border-slate-100 rounded-lg p-3">
                <div className="text-[11px] uppercase text-slate-500">Status</div>
                <div className="font-semibold text-slate-800">{selectedRun.status}</div>
              </div>
              <div className="border border-slate-100 rounded-lg p-3">
                <div className="text-[11px] uppercase text-slate-500">Transactions</div>
                <div className="font-semibold text-slate-800">
                  {selectedRun.metrics?.transactions_total ?? "—"} total ·{" "}
                  {selectedRun.metrics?.transactions_unreconciled ?? "0"} unreconciled
                </div>
              </div>
              <div className="border border-slate-100 rounded-lg p-3">
                <div className="text-[11px] uppercase text-slate-500">High risk</div>
                <div className="font-semibold text-slate-800">{selectedRun.metrics?.transactions_high_risk ?? "—"}</div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-[11px] uppercase text-slate-500">AI Companion insights – suggestions only, your data remains unchanged.</div>
              <div className="border border-slate-200 rounded-lg p-3 bg-slate-50">
                {hasLlmInsights ? (
                  <div className="space-y-3">
                    {llmExplanations.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-slate-700">Narrative</div>
                        <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                          {llmExplanations.map((line, idx) => (
                            <li key={`llm-expl-${idx}`}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {llmRanked.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-slate-700">Top transactions to review</div>
                        <div className="space-y-1">
                          {llmRanked.map((item, idx) => (
                            <button
                              key={`llm-ranked-${idx}`}
                              onClick={() => focusTransaction(item.transaction_id)}
                              className="w-full text-left border border-slate-200 rounded px-2 py-2 bg-white hover:border-sky-300"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">Transaction {item.transaction_id}</span>
                                <span className="text-[11px] uppercase bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                                  {item.priority}
                                </span>
                              </div>
                              <div className="text-sm text-slate-700">{item.reason}</div>
                              <div className="text-[11px] text-slate-500">Click to jump to the transaction below.</div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {llmFollowups.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-slate-700">Suggested follow-ups</div>
                        <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                          {llmFollowups.map((line, idx) => (
                            <li key={`followup-${idx}`}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-slate-500">
                    AI insights unavailable for this run. Turn on AI Companion in Account settings to enable suggestions.
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-[11px] uppercase text-slate-500">Transactions</div>
              {selectedRun.transactions.length === 0 ? (
                <div className="text-sm text-slate-500">No transactions in this run.</div>
              ) : (
                <div className="space-y-2">
                  {selectedRun.transactions.map((tx) => {
                    const flags = normalizeFlags(tx.audit_flags);
                    const severityClass =
                      tx.risk_level === "high" || tx.status === "UNMATCHED"
                        ? "border-rose-200 bg-rose-50/60"
                        : tx.risk_level === "medium"
                          ? "border-amber-200 bg-amber-50/60"
                          : "border-slate-100 bg-white";
                    const highlightClass = highlightedTxId === tx.id ? "ring-2 ring-sky-500" : "";
                    return (
                      <div
                        key={tx.id}
                        id={`tx-${tx.id}`}
                        className={`border rounded-lg p-3 ${severityClass} ${highlightClass}`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="font-semibold text-slate-800">
                            {tx.raw_payload.date || ""} · {tx.raw_payload.description || ""}
                          </div>
                          <RiskBadge score={tx.audit_score} />
                        </div>
                        <div className="text-xs text-slate-600">Amount {tx.raw_payload.amount}</div>
                        <div className="text-xs text-slate-600">Status {tx.status}</div>
                        {tx.error_message && <div className="text-xs text-rose-600 mt-1">{tx.error_message}</div>}
                        {flags.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {flags.map((f, idx) => (
                              <div
                                key={`${f.code}-${idx}`}
                                className="text-xs border border-slate-200 rounded px-2 py-1 bg-white flex items-start gap-2"
                              >
                                <span className="font-semibold text-slate-800">{f.code}</span>
                                <span className="text-slate-600">{f.message || ""}</span>
                                {f.severity && (
                                  <span className="ml-auto text-[10px] uppercase bg-slate-100 text-slate-600 px-1 rounded">{f.severity}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                        {tx.matched_journal_ids && tx.matched_journal_ids.length > 0 && (
                          <div className="text-[11px] text-slate-600 mt-1">
                            Matched journals: {tx.matched_journal_ids.join(", ")}
                          </div>
                        )}
                        {tx.audit_explanations && tx.audit_explanations.length > 0 && (
                          <div className="text-[11px] text-slate-600 mt-1">{tx.audit_explanations.join(" ")}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default BankReviewPage;
