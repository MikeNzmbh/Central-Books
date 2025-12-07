import React, { useCallback, useEffect, useMemo, useState } from "react";

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

type ReceiptStatus = "PENDING" | "PROCESSED" | "POSTED" | "DISCARDED" | "ERROR";
type RiskLevel = "low" | "medium" | "high" | "unknown";

interface AuditFlag {
  code: string;
  severity?: string;
  message?: string;
}

interface UserHints {
  date_hint?: string | null;
  currency_hint?: string | null;
  vendor_hint?: string | null;
  category_hint?: string | null;
}

interface JournalLine {
  account_id?: number;
  debit?: string;
  credit?: string;
  description?: string;
}

interface ReceiptDoc {
  id: number;
  status: ReceiptStatus;
  storage_key: string;
  original_filename: string;
  extracted_payload: Record<string, any>;
  proposed_journal_payload: { date?: string; description?: string; lines?: JournalLine[] };
  audit_flags: AuditFlag[] | Record<string, any>;
  audit_score: string | number | null;
  audit_explanations?: string[];
  risk_level?: RiskLevel | null;
  posted_journal_entry_id: number | null;
  error_message?: string;
}

interface RankedDoc {
  document_id: number | string;
  priority: string;
  reason: string;
}

interface SuggestedClassification {
  document_id: number | string;
  suggested_account_code?: string | null;
  confidence?: number | null;
  reason?: string;
}

interface ReceiptRun {
  id: number;
  created_at: string;
  status: string;
  total_documents: number;
  success_count: number;
  warning_count: number;
  error_count: number;
  metrics?: Record<string, any>;
  trace_id?: string | null;
}

interface RunDetail extends ReceiptRun {
  documents: ReceiptDoc[];
  llm_explanations?: string[];
  llm_ranked_documents?: RankedDoc[];
  llm_suggested_classifications?: SuggestedClassification[];
  llm_suggested_followups?: string[];
}

interface UploadState {
  files: File[];
  defaultCurrency: string;
  defaultCategory: string;
  defaultVendor: string;
  defaultDate: string;
}

interface DraftEdits {
  date: string;
  amount: string;
  currency: string;
  vendor: string;
  category: string;
  description: string;
}

const statusColor: Record<ReceiptStatus, { bg: string; dot: string }> = {
  PENDING: { bg: "bg-slate-50 text-slate-700 border border-slate-200", dot: "bg-slate-400" },
  PROCESSED: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500" },
  POSTED: { bg: "bg-blue-50 text-blue-700 border border-blue-200", dot: "bg-blue-500" },
  DISCARDED: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500" },
  ERROR: { bg: "bg-rose-50 text-rose-700 border border-rose-200", dot: "bg-rose-500" },
};

const RISK_THRESHOLDS = { medium: 40, high: 60 };
const RUNS_PER_PAGE = 5;

const StatusBadge: React.FC<{ status: ReceiptStatus }> = ({ status }) => {
  const config = statusColor[status] || { bg: "bg-slate-50 text-slate-600 border border-slate-200", dot: "bg-slate-400" };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${config.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {status}
    </span>
  );
};

const parseAuditScore = (score: string | number | null | undefined): number | null => {
  if (typeof score === "number") return Number.isFinite(score) ? score : null;
  if (typeof score === "string") {
    const parsed = parseFloat(score);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const normalizeAuditFlags = (flags: ReceiptDoc["audit_flags"]): AuditFlag[] => {
  if (Array.isArray(flags)) return flags;
  if (flags && typeof flags === "object") {
    return Object.values(flags) as AuditFlag[];
  }
  return [];
};

const deriveRiskLevel = (doc: ReceiptDoc): RiskLevel => {
  if (doc.status === "ERROR") return "high";
  const flags = normalizeAuditFlags(doc.audit_flags);
  if (doc.risk_level && doc.risk_level !== "unknown") return doc.risk_level;
  if (flags.some((f) => (f.severity || "").toLowerCase() === "high")) return "high";
  const score = parseAuditScore(doc.audit_score);
  if (score === null) return "unknown";
  if (score >= RISK_THRESHOLDS.high) return "high";
  if (score >= RISK_THRESHOLDS.medium) return "medium";
  return "low";
};

const riskConfig: Record<RiskLevel, { bg: string; dot: string; label: string }> = {
  high: { bg: "bg-rose-50 text-rose-700 border border-rose-200", dot: "bg-rose-500", label: "High risk" },
  medium: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500", label: "Medium risk" },
  low: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500", label: "Low risk" },
  unknown: { bg: "bg-slate-50 text-slate-600 border border-slate-200", dot: "bg-slate-400", label: "Unknown" },
};

const RiskBadge: React.FC<{ level: RiskLevel; score: number | null }> = ({ level, score }) => {
  const config = riskConfig[level];
  const suffix = score !== null ? ` · ${score.toFixed(0)}` : "";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${config.bg}`}>
      <span className={`w-2 h-2 rounded-full ${config.dot}`} />
      {config.label}{suffix}
    </span>
  );
};

const formatFlagLabel = (code?: string) => {
  if (!code) return "Audit flag";
  return code.replace(/_/g, " ").toLowerCase().replace(/(^|\s)\w/g, (s) => s.toUpperCase());
};

const formatDateTime = (iso: string) => new Date(iso).toLocaleString();

const prettyBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

/* ─────────────────────────────────────────────────────────────────────────────
   Journal Lines Preview Component
───────────────────────────────────────────────────────────────────────────── */
const JournalLinesPreview: React.FC<{ lines?: JournalLine[]; date?: string; description?: string }> = ({
  lines,
  date,
  description,
}) => {
  if (!lines || lines.length === 0) {
    return <div className="text-xs text-slate-500">No journal lines proposed</div>;
  }
  return (
    <div className="space-y-2">
      <div className="text-xs text-slate-600">
        {date && <span className="mr-2">Date: {date}</span>}
        {description && <span>{description}</span>}
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-200">
            <th className="py-1 pr-2">Account</th>
            <th className="py-1 pr-2 text-right">Debit</th>
            <th className="py-1 pr-2 text-right">Credit</th>
            <th className="py-1">Desc</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, idx) => (
            <tr key={idx} className="border-b border-slate-100">
              <td className="py-1 pr-2 text-slate-700">{line.account_id || "—"}</td>
              <td className="py-1 pr-2 text-right text-slate-700">{line.debit && line.debit !== "0" ? `$${line.debit}` : "—"}</td>
              <td className="py-1 pr-2 text-right text-slate-700">{line.credit && line.credit !== "0" ? `$${line.credit}` : "—"}</td>
              <td className="py-1 text-slate-600">{line.description || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────────────────
   Main Component
───────────────────────────────────────────────────────────────────────────── */
const ReceiptsPage: React.FC<{ defaultCurrency: string }> = ({ defaultCurrency }) => {
  const [upload, setUpload] = useState<UploadState>({
    files: [],
    defaultCurrency,
    defaultCategory: "",
    defaultVendor: "",
    defaultDate: "",
  });
  const [runs, setRuns] = useState<ReceiptRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [highlightedDocId, setHighlightedDocId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<Record<number, DraftEdits>>({});
  const [draftRunId, setDraftRunId] = useState<number | null>(null);
  const [postingId, setPostingId] = useState<number | null>(null);
  const [discardingId, setDiscardingId] = useState<number | null>(null);

  // Pagination state
  const [runsPage, setRunsPage] = useState(1);

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const res = await fetch("/api/agentic/receipts/runs");
      const json = await res.json();
      setRuns(json.runs || []);
      setRunsPage(1); // Reset to first page on reload
    } catch (err) {
      setError("Unable to load runs");
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  const loadRunDetail = useCallback(async (runId: number) => {
    try {
      const res = await fetch(`/api/agentic/receipts/run/${runId}`);
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

  useEffect(() => {
    if (!selectedRun) return;
    setDrafts((prev) => {
      const reset = draftRunId !== selectedRun.id;
      const base = reset ? {} : { ...prev };
      const next = { ...base };
      selectedRun.documents.forEach((doc) => {
        if (!next[doc.id]) {
          const extracted = doc.extracted_payload || {};
          const proposed = doc.proposed_journal_payload || {};
          next[doc.id] = {
            date: extracted.date || "",
            amount: extracted.total || "",
            currency: extracted.currency || upload.defaultCurrency || "",
            vendor: extracted.vendor || doc.original_filename || "",
            category: extracted.category_hint || "",
            description: proposed.description || `Receipt - ${extracted.vendor || doc.original_filename}`,
          };
        }
      });
      return next;
    });
    setDraftRunId(selectedRun.id);
  }, [selectedRun, upload.defaultCurrency, draftRunId]);

  const handleFilesChange = (files: FileList | null) => {
    if (!files) return;
    setUpload((prev) => ({ ...prev, files: Array.from(files) }));
  };

  const handleUpload = async () => {
    if (!upload.files.length) {
      setError("Please select at least one file");
      return;
    }
    setUploading(true);
    setError(null);
    setInfo(null);
    const form = new FormData();
    upload.files.forEach((f) => form.append("files", f));
    if (upload.defaultCurrency) form.append("default_currency", upload.defaultCurrency);
    if (upload.defaultCategory) form.append("default_category", upload.defaultCategory);
    if (upload.defaultVendor) form.append("default_vendor", upload.defaultVendor);
    if (upload.defaultDate) form.append("default_date", upload.defaultDate);
    try {
      const res = await fetch("/api/agentic/receipts/run", {
        method: "POST",
        body: form,
        headers: { "X-CSRFToken": getCsrfToken() },
      });
      const json = await res.json();
      if (!res.ok) {
        if (json.errors && typeof json.errors === "object") {
          const fieldMessages = Object.entries(json.errors)
            .map(([field, msgs]) => {
              const fieldLabel = field.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
              const messages = Array.isArray(msgs) ? msgs.join(" ") : String(msgs);
              return `${fieldLabel}: ${messages}`;
            })
            .join(" | ");
          throw new Error(fieldMessages || json.error || "Validation failed");
        }
        throw new Error(json.error || "Upload failed");
      }
      setInfo(`Run ${json.run_id} queued`);
      setUpload((prev) => ({ ...prev, files: [] }));
      await loadRuns();
      if (json.run_id) {
        await loadRunDetail(json.run_id);
      }
    } catch (err: any) {
      console.error("Upload error:", err);
      setError(err?.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const approveReceipt = async (id: number) => {
    const draft = drafts[id];
    setPostingId(id);
    try {
      const res = await fetch(`/api/agentic/receipts/${id}/approve`, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken(), "Content-Type": "application/json" },
        body: draft ? JSON.stringify({ overrides: draft }) : "{}",
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Approve failed");
      setInfo("Approved and posted");
      if (selectedRun) loadRunDetail(selectedRun.id);
    } catch (err: any) {
      setError(err?.message || "Approve failed");
    } finally {
      setPostingId(null);
    }
  };

  const discardReceipt = async (id: number) => {
    setDiscardingId(id);
    try {
      const res = await fetch(`/api/agentic/receipts/${id}/discard`, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Discard failed");
      setInfo("Receipt discarded");
      if (selectedRun) loadRunDetail(selectedRun.id);
    } catch (err: any) {
      setError(err?.message || "Discard failed");
    } finally {
      setDiscardingId(null);
    }
  };

  const updateDraft = (id: number, field: keyof DraftEdits, value: string) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: {
        date: prev[id]?.date || "",
        amount: prev[id]?.amount || "",
        currency: prev[id]?.currency || "",
        vendor: prev[id]?.vendor || "",
        category: prev[id]?.category || "",
        description: prev[id]?.description || "",
        [field]: value,
      },
    }));
  };

  const resetDraftToAI = (doc: ReceiptDoc) => {
    const extracted = doc.extracted_payload || {};
    const proposed = doc.proposed_journal_payload || {};
    setDrafts((prev) => ({
      ...prev,
      [doc.id]: {
        date: extracted.date || "",
        amount: extracted.total || "",
        currency: extracted.currency || "",
        vendor: extracted.vendor || doc.original_filename || "",
        category: extracted.category_hint || "",
        description: proposed.description || "",
      },
    }));
  };

  // LLM Insights
  const llmExplanations = selectedRun?.llm_explanations || [];
  const llmRankedDocs = selectedRun?.llm_ranked_documents || [];
  const llmFollowups = selectedRun?.llm_suggested_followups || [];
  const llmSuggestions = selectedRun?.llm_suggested_classifications || [];
  const hasLlmInsights = llmExplanations.length > 0 || llmRankedDocs.length > 0 || llmFollowups.length > 0 || llmSuggestions.length > 0;
  const suggestionByDoc = useMemo(() => {
    const map = new Map<number, SuggestedClassification>();
    llmSuggestions.forEach((s) => {
      const parsed = Number(s.document_id);
      if (Number.isFinite(parsed) && !map.has(parsed)) {
        map.set(parsed, s);
      }
    });
    return map;
  }, [llmSuggestions]);

  const focusDoc = (docId: number | string | null | undefined) => {
    if (docId === null || docId === undefined) return;
    const parsed = Number(docId);
    if (!Number.isFinite(parsed)) return;
    setHighlightedDocId(parsed);
    const el = document.getElementById(`receipt-${parsed}`);
    if (el && typeof (el as any).scrollIntoView === "function") {
      (el as any).scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  useEffect(() => {
    if (highlightedDocId === null) return;
    const timer = setTimeout(() => setHighlightedDocId(null), 2000);
    return () => clearTimeout(timer);
  }, [highlightedDocId]);

  const totalUploadSize = useMemo(
    () => upload.files.reduce((sum, f) => sum + f.size, 0),
    [upload.files]
  );

  // Pagination logic
  const totalPages = Math.ceil(runs.length / RUNS_PER_PAGE);
  const paginatedRuns = useMemo(() => {
    const start = (runsPage - 1) * RUNS_PER_PAGE;
    return runs.slice(start, start + RUNS_PER_PAGE);
  }, [runs, runsPage]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium text-slate-500 uppercase">Documents</p>
            <h1 className="text-2xl font-semibold">Receipts</h1>
            <p className="text-sm text-slate-500">Upload receipts, review AI-extracted data, and post to your ledger.</p>
          </div>
        </div>

        {error && <div className="rounded-lg bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3">{error}</div>}
        {info && <div className="rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3">{info}</div>}

        {/* Upload Section */}
        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-800">Upload receipts</h2>
              <p className="text-xs text-slate-500 mt-0.5">AI-powered extraction of vendor, date, and amount</p>
            </div>
            <div className="text-xs text-slate-500 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
              {upload.files.length} files · {prettyBytes(totalUploadSize)}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Default currency</span>
              <input
                className="w-full mt-1.5 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-400 transition-all"
                value={upload.defaultCurrency}
                onChange={(e) => setUpload((p) => ({ ...p, defaultCurrency: e.target.value }))}
                placeholder="e.g., CAD"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Date hint</span>
              <input
                type="text"
                className="w-full mt-1.5 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-400 transition-all"
                value={upload.defaultDate}
                onChange={(e) => setUpload((p) => ({ ...p, defaultDate: e.target.value }))}
                placeholder="YYYY-MM-DD"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Category hint</span>
              <input
                className="w-full mt-1.5 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-400 transition-all"
                value={upload.defaultCategory}
                onChange={(e) => setUpload((p) => ({ ...p, defaultCategory: e.target.value }))}
                placeholder="Office Supplies"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Vendor hint</span>
              <input
                className="w-full mt-1.5 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-400 transition-all"
                value={upload.defaultVendor}
                onChange={(e) => setUpload((p) => ({ ...p, defaultVendor: e.target.value }))}
                placeholder="Vendor name"
              />
            </label>
          </div>
          <div className="border-2 border-dashed border-slate-200 rounded-xl p-5 bg-slate-50/50 hover:border-slate-300 hover:bg-slate-50 transition-all">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center text-slate-400 border border-slate-200">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div className="flex-1">
                <input
                  type="file"
                  multiple
                  onChange={(e) => handleFilesChange(e.target.files)}
                  className="text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200 file:cursor-pointer file:transition-colors"
                  aria-label="receipt-files-input"
                />
                <p className="text-xs text-slate-400 mt-1">PDF, JPG, PNG, HEIC up to 10MB each</p>
              </div>
            </div>
            {upload.files.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-200 flex flex-wrap gap-2">
                {upload.files.map((file) => (
                  <span key={file.name} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-600 shadow-sm">
                    <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {file.name}
                    <span className="text-slate-400">·</span>
                    <span className="text-slate-500">{prettyBytes(file.size)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleUpload}
              disabled={uploading || upload.files.length === 0}
              className="px-5 py-2.5 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              {uploading ? "Uploading…" : "Upload & Process"}
            </button>
          </div>
        </section>

        {/* Recent Runs Section with Pagination */}
        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent runs</h2>
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
            <div className="text-sm text-slate-500">No runs yet. Upload receipts to get started.</div>
          ) : (
            <>
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-xs uppercase text-slate-500">
                      <th className="py-2">Run</th>
                      <th>Created</th>
                      <th>Docs</th>
                      <th>Status</th>
                      <th>Errors</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedRuns.map((run) => (
                      <tr key={run.id} className="border-t border-slate-100">
                        <td className="py-2 font-semibold text-slate-800">#{run.id}</td>
                        <td className="text-slate-600">{formatDateTime(run.created_at)}</td>
                        <td className="text-slate-600">{run.total_documents}</td>
                        <td className="text-slate-600">{run.status}</td>
                        <td className="text-slate-600">{run.error_count}</td>
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
              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <div className="text-xs text-slate-500">
                    Page {runsPage} of {totalPages} · {runs.length} total runs
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setRunsPage((p) => Math.max(1, p - 1))}
                      disabled={runsPage <= 1}
                      className="px-3 py-1 text-xs font-semibold border border-slate-200 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setRunsPage((p) => Math.min(totalPages, p + 1))}
                      disabled={runsPage >= totalPages}
                      className="px-3 py-1 text-xs font-semibold border border-slate-200 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </section>

        {/* Run Detail Section */}
        {selectedRun && (
          <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">Run #{selectedRun.id}</h3>
                <p className="text-xs text-slate-500">
                  {selectedRun.total_documents} docs · {selectedRun.success_count} success · {selectedRun.error_count} errors
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
                <StatusBadge status={selectedRun.status as ReceiptStatus} />
              </div>
            </div>

            {/* AI Companion Insights */}
            <div className="space-y-2">
              <div className="text-[11px] uppercase text-slate-500">
                AI Companion insights – suggestions only, your data remains unchanged.
              </div>
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
                    {llmRankedDocs.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-slate-700">Top documents to review</div>
                        <div className="space-y-1">
                          {llmRankedDocs.map((item, idx) => (
                            <button
                              key={`llm-rank-${idx}`}
                              onClick={() => focusDoc(item.document_id)}
                              className="w-full text-left border border-slate-200 rounded px-2 py-2 bg-white hover:border-sky-300"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">Document {item.document_id}</span>
                                <span className="text-[11px] uppercase bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                                  {item.priority}
                                </span>
                              </div>
                              <div className="text-sm text-slate-700">{item.reason}</div>
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
                  <div className="text-sm text-slate-500">AI insights unavailable for this run.</div>
                )}
              </div>
            </div>

            {/* Receipt Documents */}
            <div className="space-y-4">
              {selectedRun.documents.map((doc) => {
                const riskLevel = deriveRiskLevel(doc);
                const auditScore = parseAuditScore(doc.audit_score);
                const auditFlags = normalizeAuditFlags(doc.audit_flags);
                const suggestion = suggestionByDoc.get(doc.id);
                const userHints = (doc.extracted_payload?.user_hints || {}) as Record<string, any>;
                const highlightClass = highlightedDocId === doc.id ? "ring-2 ring-sky-500" : "";
                const isPosting = postingId === doc.id;
                const isDiscarding = discardingId === doc.id;
                const isPosted = doc.status === "POSTED";
                const isDiscarded = doc.status === "DISCARDED";
                const canApprove = doc.status === "PROCESSED" && !isPosting;
                const canDiscard = doc.status !== "DISCARDED" && !isDiscarding;

                return (
                  <div
                    key={doc.id}
                    id={`receipt-${doc.id}`}
                    className={`border rounded-xl overflow-hidden ${highlightClass} ${riskLevel === "high" || doc.status === "ERROR"
                      ? "border-rose-200 bg-rose-50/60"
                      : riskLevel === "medium"
                        ? "border-amber-200 bg-amber-50/60"
                        : "border-slate-200 bg-white"
                      }`}
                  >
                    {/* Card Header */}
                    <div className="flex items-center justify-between gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-slate-200 rounded flex items-center justify-center text-slate-500 text-xs">
                          📄
                        </div>
                        <div>
                          <div className="font-semibold text-slate-800">{doc.original_filename || "Untitled"}</div>
                          <div className="text-[11px] text-slate-500">{doc.storage_key}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <RiskBadge level={riskLevel} score={auditScore} />
                        <StatusBadge status={doc.status} />
                      </div>
                    </div>

                    {doc.error_message && (
                      <div className="px-4 py-2 bg-rose-100 text-rose-700 text-xs">{doc.error_message}</div>
                    )}
                    {doc.status === "ERROR" && (
                      <div className="px-4 py-2 bg-rose-100 text-rose-700 text-xs">
                        Cannot be auto-processed. Please enter manually or re-upload.
                      </div>
                    )}

                    <div className="p-4">
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        {/* Left: Editable Form */}
                        <div className="lg:col-span-2 space-y-4">
                          <div className="text-xs font-semibold text-slate-700 uppercase">Receipt Details</div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <label className="block space-y-1">
                              <span className="text-xs text-slate-600">Vendor</span>
                              <input
                                className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
                                value={drafts[doc.id]?.vendor || ""}
                                onChange={(e) => updateDraft(doc.id, "vendor", e.target.value)}
                                disabled={isPosted}
                              />
                              {userHints.vendor_hint && userHints.vendor_hint !== drafts[doc.id]?.vendor && (
                                <div className="text-[10px] text-slate-500">Hint: {userHints.vendor_hint}</div>
                              )}
                            </label>
                            <label className="block space-y-1">
                              <span className="text-xs text-slate-600">Date</span>
                              <input
                                className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
                                value={drafts[doc.id]?.date || ""}
                                onChange={(e) => updateDraft(doc.id, "date", e.target.value)}
                                placeholder="YYYY-MM-DD"
                                disabled={isPosted}
                              />
                              {userHints.date_hint && userHints.date_hint !== drafts[doc.id]?.date && (
                                <div className="text-[10px] text-slate-500">Hint: {userHints.date_hint}</div>
                              )}
                            </label>
                            <label className="block space-y-1">
                              <span className="text-xs text-slate-600">Amount</span>
                              <input
                                type="text"
                                className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
                                value={drafts[doc.id]?.amount || ""}
                                onChange={(e) => updateDraft(doc.id, "amount", e.target.value)}
                                disabled={isPosted}
                              />
                            </label>
                            <label className="block space-y-1">
                              <span className="text-xs text-slate-600">Currency</span>
                              <input
                                className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
                                value={drafts[doc.id]?.currency || ""}
                                onChange={(e) => updateDraft(doc.id, "currency", e.target.value)}
                                placeholder="CAD"
                                disabled={isPosted}
                              />
                              {userHints.currency_hint && userHints.currency_hint !== drafts[doc.id]?.currency && (
                                <div className="text-[10px] text-slate-500">Hint: {userHints.currency_hint}</div>
                              )}
                            </label>
                            <label className="block space-y-1 md:col-span-2">
                              <span className="text-xs text-slate-600">Category / Account</span>
                              <input
                                className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
                                value={drafts[doc.id]?.category || ""}
                                onChange={(e) => updateDraft(doc.id, "category", e.target.value)}
                                placeholder="e.g., Office Supplies"
                                disabled={isPosted}
                              />
                            </label>
                            <label className="block space-y-1 md:col-span-2">
                              <span className="text-xs text-slate-600">Description</span>
                              <input
                                className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
                                value={drafts[doc.id]?.description || ""}
                                onChange={(e) => updateDraft(doc.id, "description", e.target.value)}
                                disabled={isPosted}
                              />
                            </label>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex flex-wrap gap-2 items-center pt-2">
                            <button
                              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold disabled:opacity-50 hover:bg-emerald-700 transition-colors"
                              onClick={() => approveReceipt(doc.id)}
                              disabled={!canApprove || isPosted}
                            >
                              {isPosting ? "Posting…" : isPosted ? "✓ Posted" : "Approve & Post"}
                            </button>
                            <button
                              className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-semibold disabled:opacity-50 hover:bg-slate-50 transition-colors"
                              onClick={() => discardReceipt(doc.id)}
                              disabled={!canDiscard || isDiscarded}
                            >
                              {isDiscarding ? "Discarding…" : isDiscarded ? "Discarded" : "Discard"}
                            </button>
                            {!isPosted && !isDiscarded && (
                              <button
                                className="px-3 py-2 text-xs text-slate-600 hover:text-slate-800"
                                onClick={() => resetDraftToAI(doc)}
                              >
                                Reset to AI values
                              </button>
                            )}
                            {doc.posted_journal_entry_id && (
                              <span className="text-xs text-slate-600 ml-auto">
                                Posted JE #{doc.posted_journal_entry_id}
                              </span>
                            )}
                          </div>

                          {/* Collapsible Raw JSON */}
                          <details className="mt-2">
                            <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">
                              Show raw JSON
                            </summary>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                              <div>
                                <div className="text-[10px] uppercase text-slate-500 mb-1">Extracted</div>
                                <pre className="bg-slate-50 rounded p-2 text-[10px] overflow-auto border border-slate-200 max-h-40">
                                  {JSON.stringify(doc.extracted_payload, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <div className="text-[10px] uppercase text-slate-500 mb-1">Proposed Journal</div>
                                <pre className="bg-slate-50 rounded p-2 text-[10px] overflow-auto border border-slate-200 max-h-40">
                                  {JSON.stringify(doc.proposed_journal_payload, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </details>
                        </div>

                        {/* Right: Journal Preview + Audit */}
                        <div className="space-y-4">
                          {/* Journal Lines Preview */}
                          <div>
                            <div className="text-xs font-semibold text-slate-700 uppercase mb-2">Journal Preview</div>
                            <div className="border border-slate-200 rounded-lg p-3 bg-white">
                              <JournalLinesPreview
                                lines={doc.proposed_journal_payload?.lines}
                                date={doc.proposed_journal_payload?.date}
                                description={doc.proposed_journal_payload?.description}
                              />
                              <div className="text-[10px] text-slate-500 mt-2 italic">
                                Lines will be recomputed on approve with your edits.
                              </div>
                            </div>
                          </div>

                          {/* Audit & Risk */}
                          <div>
                            <div className="text-xs font-semibold text-slate-700 uppercase mb-2">Audit & Risk</div>
                            <div className="space-y-2">
                              {auditFlags.length === 0 ? (
                                <div className="text-xs text-slate-500">No audit flags</div>
                              ) : (
                                auditFlags.map((flag, idx) => (
                                  <div
                                    key={`${flag.code}-${idx}`}
                                    className="flex items-start gap-2 text-xs rounded border border-slate-200 bg-white px-2 py-1.5"
                                  >
                                    <span className="font-semibold text-slate-800">{formatFlagLabel(flag.code)}</span>
                                    <span className="text-slate-600 flex-1">{flag.message || "Needs review"}</span>
                                    {flag.severity && (
                                      <span className="px-1.5 rounded bg-slate-100 text-slate-600 uppercase text-[10px]">
                                        {flag.severity}
                                      </span>
                                    )}
                                  </div>
                                ))
                              )}
                              {doc.audit_explanations && doc.audit_explanations.length > 0 && (
                                <div className="text-[11px] text-slate-600 italic">
                                  {doc.audit_explanations.join(" ")}
                                </div>
                              )}
                              {suggestion && (
                                <div className="border border-slate-200 rounded px-2 py-1.5 bg-white">
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-semibold text-slate-800">AI suggestion</span>
                                    {suggestion.confidence !== undefined && suggestion.confidence !== null && (
                                      <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                                        {(Number(suggestion.confidence) * 100).toFixed(0)}% confidence
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-xs text-slate-700">
                                    Account {suggestion.suggested_account_code || "—"} ·{" "}
                                    {suggestion.reason || "Review suggested classification."}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default ReceiptsPage;
