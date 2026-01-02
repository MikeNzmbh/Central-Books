import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

type InvoiceStatus = "PENDING" | "PROCESSED" | "POSTED" | "DISCARDED" | "ERROR";
type RiskLevel = "low" | "medium" | "high" | "unknown";

interface AuditFlag {
  code: string;
  severity?: string;
  message?: string;
}

interface JournalLine {
  account_id?: number;
  account_name?: string;
  debit: string;
  credit: string;
  description?: string;
}

interface InvoiceDoc {
  id: number;
  status: InvoiceStatus;
  storage_key: string;
  original_filename: string;
  extracted_payload: Record<string, any>;
  proposed_journal_payload: Record<string, any>;
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

interface InvoiceRun {
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

interface RunDetail extends InvoiceRun {
  documents: InvoiceDoc[];
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
  defaultIssueDate: string;
  defaultDueDate: string;
}

interface DraftEdits {
  vendor: string;
  invoice_number: string;
  issue_date: string;
  due_date: string;
  amount: string;
  tax: string;
  currency: string;
  category: string;
  description: string;
}

const statusColor: Record<InvoiceStatus, { bg: string; dot: string }> = {
  PENDING: { bg: "bg-slate-50 text-slate-700 border border-slate-200", dot: "bg-slate-400" },
  PROCESSED: { bg: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500" },
  POSTED: { bg: "bg-blue-50 text-blue-700 border border-blue-200", dot: "bg-blue-500" },
  DISCARDED: { bg: "bg-amber-50 text-amber-700 border border-amber-200", dot: "bg-amber-500" },
  ERROR: { bg: "bg-rose-50 text-rose-700 border border-rose-200", dot: "bg-rose-500" },
};

const RISK_THRESHOLDS = { medium: 40, high: 60 };
const RUNS_PER_PAGE = 5;

const StatusBadge: React.FC<{ status: InvoiceStatus }> = ({ status }) => {
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

const normalizeAuditFlags = (flags: InvoiceDoc["audit_flags"]): AuditFlag[] => {
  if (Array.isArray(flags)) return flags;
  if (flags && typeof flags === "object") {
    return Object.values(flags) as AuditFlag[];
  }
  return [];
};

const deriveRiskLevel = (doc: InvoiceDoc): RiskLevel => {
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
      {config.label}<span className="font-mono-soft">{suffix}</span>
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
    return <div className="text-xs text-slate-500">No journal lines</div>;
  }
  return (
    <div className="space-y-2">
      {date && <div className="text-xs text-slate-500">Date: {date}</div>}
      {description && <div className="text-xs text-slate-600 italic">{description}</div>}
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] uppercase text-slate-500 border-b border-slate-100">
            <th className="text-left py-1">Account</th>
            <th className="text-right py-1">Debit</th>
            <th className="text-right py-1">Credit</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, idx) => (
            <tr key={idx} className="border-b border-slate-50">
              <td className="py-1 text-slate-700">{line.account_name || `Account #${line.account_id}`}</td>
              <td className="py-1 text-right text-slate-700 font-mono-soft">{parseFloat(line.debit) > 0 ? line.debit : "—"}</td>
              <td className="py-1 text-right text-slate-700 font-mono-soft">{parseFloat(line.credit) > 0 ? line.credit : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="text-[10px] text-slate-400">Lines will be recomputed on approve with your edits</div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────────────────
   Invoice Document Card Component (Design B)
───────────────────────────────────────────────────────────────────────────── */
const InvoiceDocumentCard: React.FC<{
  doc: InvoiceDoc;
  isHighlighted: boolean;
  onApprove: (id: number, overrides: DraftEdits) => Promise<void>;
  onDiscard: (id: number) => void;
}> = ({ doc, isHighlighted, onApprove, onDiscard }) => {
  const extracted = doc.extracted_payload || {};
  const proposed = doc.proposed_journal_payload || {};
  const auditFlags = normalizeAuditFlags(doc.audit_flags);
  const riskLevel = deriveRiskLevel(doc);
  const auditScore = parseAuditScore(doc.audit_score);
  const userHints = extracted.user_hints || {};

  const [edits, setEdits] = useState<DraftEdits>({
    vendor: extracted.vendor || "",
    invoice_number: extracted.invoice_number || "",
    issue_date: extracted.issue_date || "",
    due_date: extracted.due_date || "",
    amount: extracted.total || "0",
    tax: extracted.tax || "",
    currency: extracted.currency || "",
    category: extracted.category_hint || "",
    description: `Invoice ${extracted.invoice_number || ""} from ${extracted.vendor || ""}`,
  });

  const [showRaw, setShowRaw] = useState(false);
  const [approving, setApproving] = useState(false);

  const resetToAI = () => {
    setEdits({
      vendor: extracted.vendor || "",
      invoice_number: extracted.invoice_number || "",
      issue_date: extracted.issue_date || "",
      due_date: extracted.due_date || "",
      amount: extracted.total || "0",
      tax: extracted.tax || "",
      currency: extracted.currency || "",
      category: extracted.category_hint || "",
      description: `Invoice ${extracted.invoice_number || ""} from ${extracted.vendor || ""}`,
    });
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await onApprove(doc.id, edits);
    } finally {
      setApproving(false);
    }
  };

  const highlightClass = isHighlighted ? "ring-2 ring-sky-500" : "";
  const borderClass =
    riskLevel === "high" || doc.status === "ERROR"
      ? "border-rose-200 bg-rose-50/60"
      : riskLevel === "medium"
        ? "border-amber-200 bg-amber-50/60"
        : "border-slate-200 bg-white";

  // Check for hint mismatches
  const hintMismatches: { field: string; hint: string; ai: string }[] = [];
  if (userHints.vendor_hint && userHints.vendor_hint !== extracted.vendor) {
    hintMismatches.push({ field: "Vendor", hint: userHints.vendor_hint, ai: extracted.vendor || "" });
  }
  if (userHints.amount_hint && userHints.amount_hint !== extracted.total) {
    hintMismatches.push({ field: "Amount", hint: userHints.amount_hint, ai: extracted.total || "" });
  }
  if (userHints.currency_hint && userHints.currency_hint !== extracted.currency) {
    hintMismatches.push({ field: "Currency", hint: userHints.currency_hint, ai: extracted.currency || "" });
  }

  return (
    <div
      id={`invoice-${doc.id}`}
      className={`border rounded-xl p-4 space-y-4 ${highlightClass} ${borderClass}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="font-semibold text-slate-800">{doc.original_filename || doc.storage_key}</div>
          <div className="text-xs text-slate-500">{doc.storage_key}</div>
          {extracted.ocr_status && (
            <div className="text-[10px] text-slate-400 mt-1">
              OCR: {extracted.ocr_used ? "Used" : extracted.ocr_status}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <RiskBadge level={riskLevel} score={auditScore} />
          <StatusBadge status={doc.status} />
        </div>
      </div>

      {doc.error_message && <div className="text-xs text-rose-600">{doc.error_message}</div>}

      {/* Hint mismatch warnings */}
      {hintMismatches.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 space-y-1">
          <div className="text-[10px] uppercase font-semibold text-amber-700">Hint vs AI mismatch</div>
          {hintMismatches.map((m, idx) => (
            <div key={idx} className="text-xs text-amber-800">
              {m.field}: Your hint "{m.hint}" vs AI "{m.ai}"
            </div>
          ))}
        </div>
      )}

      {/* Main content: Invoice Details + Journal Preview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Invoice Details Form */}
        <div className="space-y-3">
          <div className="text-[11px] uppercase text-slate-500 font-semibold">Invoice Details</div>
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="text-[10px] text-slate-500">Vendor</span>
              <input
                type="text"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.vendor}
                onChange={(e) => setEdits((p) => ({ ...p, vendor: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Invoice #</span>
              <input
                type="text"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.invoice_number}
                onChange={(e) => setEdits((p) => ({ ...p, invoice_number: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Issue Date</span>
              <input
                type="date"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.issue_date}
                onChange={(e) => setEdits((p) => ({ ...p, issue_date: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Due Date</span>
              <input
                type="date"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.due_date}
                onChange={(e) => setEdits((p) => ({ ...p, due_date: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Amount</span>
              <input
                type="text"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.amount}
                onChange={(e) => setEdits((p) => ({ ...p, amount: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Tax</span>
              <input
                type="text"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.tax}
                onChange={(e) => setEdits((p) => ({ ...p, tax: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Currency</span>
              <input
                type="text"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.currency}
                onChange={(e) => setEdits((p) => ({ ...p, currency: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
            <label className="block">
              <span className="text-[10px] text-slate-500">Category</span>
              <input
                type="text"
                className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={edits.category}
                onChange={(e) => setEdits((p) => ({ ...p, category: e.target.value }))}
                disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
              />
            </label>
          </div>
          <label className="block">
            <span className="text-[10px] text-slate-500">Description</span>
            <input
              type="text"
              className="w-full mt-0.5 border border-slate-200 rounded px-2 py-1 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
              value={edits.description}
              onChange={(e) => setEdits((p) => ({ ...p, description: e.target.value }))}
              disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
            />
          </label>
        </div>

        {/* Right: Journal Preview */}
        <div className="space-y-3">
          <div className="text-[11px] uppercase text-slate-500 font-semibold">Journal Preview</div>
          <div className="bg-slate-50 rounded-lg p-3">
            <JournalLinesPreview
              lines={proposed.lines}
              date={proposed.date}
              description={proposed.description}
            />
          </div>
        </div>
      </div>

      {/* Audit & Risk Panel */}
      <div className="space-y-2">
        <div className="text-[11px] uppercase text-slate-500 font-semibold">Audit & Risk</div>
        {auditFlags.length === 0 ? (
          <div className="text-xs text-emerald-600">No audit flags</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {auditFlags.map((flag, idx) => (
              <div
                key={`${flag.code}-${idx}`}
                className="text-xs rounded border border-slate-200 bg-white px-2 py-1"
              >
                <span className="font-semibold text-slate-800">{formatFlagLabel(flag.code)}</span>
                {flag.message && <span className="text-slate-600 ml-1">{flag.message}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleApprove}
            disabled={approving || doc.status === "POSTED" || doc.status === "DISCARDED" || doc.status === "ERROR"}
            className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50"
          >
            {approving ? "Approving…" : doc.status === "POSTED" ? "Posted" : "Approve & Post"}
          </button>
          <button
            onClick={() => onDiscard(doc.id)}
            disabled={doc.status === "DISCARDED" || doc.status === "POSTED"}
            className="px-3 py-1.5 rounded-lg bg-amber-100 text-amber-700 text-xs font-semibold hover:bg-amber-200 disabled:opacity-50"
          >
            Discard
          </button>
          <button
            onClick={resetToAI}
            disabled={doc.status === "POSTED" || doc.status === "DISCARDED"}
            className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold hover:bg-slate-200 disabled:opacity-50"
          >
            Reset to AI
          </button>
        </div>
        {doc.posted_journal_entry_id && (
          <div className="text-xs text-slate-600">Posted JE #<span className="font-mono-soft">{doc.posted_journal_entry_id}</span></div>
        )}
      </div>

      {/* Collapsible Raw JSON */}
      <div>
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="text-xs text-slate-500 hover:text-slate-700"
        >
          {showRaw ? "▾ Hide raw JSON" : "▸ Show raw JSON"}
        </button>
        {showRaw && (
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div className="text-[10px] uppercase text-slate-500 mb-1">Extracted</div>
              <pre className="bg-slate-100 rounded p-2 text-[10px] overflow-auto max-h-40">
                {JSON.stringify(extracted, null, 2)}
              </pre>
            </div>
            <div>
              <div className="text-[10px] uppercase text-slate-500 mb-1">Proposed Journal</div>
              <pre className="bg-slate-100 rounded p-2 text-[10px] overflow-auto max-h-40">
                {JSON.stringify(proposed, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────────────────
   Main Component
───────────────────────────────────────────────────────────────────────────── */
const InvoicesPage: React.FC<{ defaultCurrency: string }> = ({ defaultCurrency }) => {
  const [upload, setUpload] = useState<UploadState>({
    files: [],
    defaultCurrency,
    defaultCategory: "",
    defaultVendor: "",
    defaultIssueDate: "",
    defaultDueDate: "",
  });
  const [runs, setRuns] = useState<InvoiceRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [highlightedDocId, setHighlightedDocId] = useState<number | null>(null);
  const [runsPage, setRunsPage] = useState(0);

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const res = await fetch("/api/agentic/invoices/runs");
      const json = await res.json();
      setRuns(json.runs || []);
    } catch (err) {
      setError("Unable to load runs");
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  const loadRunDetail = useCallback(async (runId: number) => {
    try {
      const res = await fetch(`/api/agentic/invoices/run/${runId}`);
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
    if (upload.defaultIssueDate) form.append("default_issue_date", upload.defaultIssueDate);
    if (upload.defaultDueDate) form.append("default_due_date", upload.defaultDueDate);
    try {
      const res = await fetch("/api/agentic/invoices/run", { method: "POST", body: form });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Upload failed");
      setInfo(`Run ${json.run_id} queued`);
      setUpload((prev) => ({ ...prev, files: [] }));
      await loadRuns();
      if (json.run_id) {
        await loadRunDetail(json.run_id);
      }
    } catch (err: any) {
      setError(err?.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const approveInvoice = async (id: number, overrides: DraftEdits) => {
    try {
      const res = await fetch(`/api/agentic/invoices/${id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(overrides),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Approve failed");
      setInfo("Approved and posted");
      if (selectedRun) loadRunDetail(selectedRun.id);
    } catch (err: any) {
      setError(err?.message || "Approve failed");
    }
  };

  const discardInvoice = async (id: number) => {
    try {
      const res = await fetch(`/api/agentic/invoices/${id}/discard`, { method: "POST" });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Discard failed");
      setInfo("Invoice discarded");
      if (selectedRun) loadRunDetail(selectedRun.id);
    } catch (err: any) {
      setError(err?.message || "Discard failed");
    }
  };

  const llmExplanations = selectedRun?.llm_explanations || [];
  const llmRankedDocs = selectedRun?.llm_ranked_documents || [];
  const llmFollowups = selectedRun?.llm_suggested_followups || [];
  const hasLlmInsights = llmExplanations.length > 0 || llmRankedDocs.length > 0 || llmFollowups.length > 0;

  const focusDoc = (docId: number | string | null | undefined) => {
    if (docId === null || docId === undefined) return;
    const parsed = Number(docId);
    if (!Number.isFinite(parsed)) return;
    setHighlightedDocId(parsed);
    const el = document.getElementById(`invoice-${parsed}`);
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

  // Pagination
  const sortedRuns = useMemo(() => [...runs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()), [runs]);
  const totalPages = Math.ceil(sortedRuns.length / RUNS_PER_PAGE);
  const pagedRuns = sortedRuns.slice(runsPage * RUNS_PER_PAGE, (runsPage + 1) * RUNS_PER_PAGE);
  const showPagination = sortedRuns.length > RUNS_PER_PAGE;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium text-slate-500 uppercase">Documents</p>
            <h1 className="text-2xl font-semibold">Invoices (AI)</h1>
            <p className="text-sm text-slate-500">Upload vendor invoices, review & edit, and approve for posting.</p>
          </div>
        </div>

        {error && <div className="rounded-lg bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3">{error}</div>}
        {info && <div className="rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3">{info}</div>}

        {/* Upload Section */}
        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Upload invoices</h2>
              <p className="text-xs text-slate-500">PDF, JPG, PNG, HEIC supported</p>
            </div>
            <div className="text-xs text-slate-500">
              Total size: <span className="font-mono-soft">{prettyBytes(totalUploadSize)}</span> · Files: <span className="font-mono-soft">{upload.files.length}</span>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <label className="block">
              <span className="text-xs text-slate-600">Default currency</span>
              <input
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={upload.defaultCurrency}
                onChange={(e) => setUpload((p) => ({ ...p, defaultCurrency: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Issue date</span>
              <input
                type="date"
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={upload.defaultIssueDate}
                onChange={(e) => setUpload((p) => ({ ...p, defaultIssueDate: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Due date</span>
              <input
                type="date"
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={upload.defaultDueDate}
                onChange={(e) => setUpload((p) => ({ ...p, defaultDueDate: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Category hint</span>
              <input
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={upload.defaultCategory}
                onChange={(e) => setUpload((p) => ({ ...p, defaultCategory: e.target.value }))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-600">Vendor hint</span>
              <input
                className="w-full mt-1 border border-slate-200 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-sky-300 focus:border-sky-300"
                value={upload.defaultVendor}
                onChange={(e) => setUpload((p) => ({ ...p, defaultVendor: e.target.value }))}
              />
            </label>
          </div>
          <div className="border border-dashed border-slate-300 rounded-xl p-4 bg-slate-50">
            <input
              type="file"
              multiple
              onChange={(e) => handleFilesChange(e.target.files)}
              className="text-sm"
              aria-label="invoice-files-input"
            />
            <div className="text-xs text-slate-500 mt-2">Drag and drop or click to select files</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {upload.files.map((file) => (
                <span key={file.name} className="px-2 py-1 bg-white border border-slate-200 rounded text-xs flex items-center gap-1">
                  <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  {file.name} · <span className="font-mono-soft">{prettyBytes(file.size)}</span>
                </span>
              ))}
              {upload.files.length === 0 && <span className="text-xs text-slate-400">No files selected yet</span>}
            </div>
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800 disabled:opacity-50"
            >
              {uploading ? "Uploading…" : "Upload & Process"}
            </button>
          </div>
        </section>

        {/* Recent Runs with Pagination */}
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
            <div className="text-sm text-slate-500">No runs yet. Upload invoices to get started.</div>
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
                    {pagedRuns.map((run) => (
                      <tr key={run.id} className="border-t border-slate-100">
                        <td className="py-2 font-semibold text-slate-800 font-mono-soft">#{run.id}</td>
                        <td className="text-slate-600">{formatDateTime(run.created_at)}</td>
                        <td className="text-slate-600 font-mono-soft">{run.total_documents}</td>
                        <td className="text-slate-600">{run.status}</td>
                        <td className="text-slate-600 font-mono-soft">{run.error_count}</td>
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
              {showPagination && (
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <button
                    onClick={() => setRunsPage((p) => Math.max(0, p - 1))}
                    disabled={runsPage === 0}
                    className="text-xs font-semibold text-slate-600 border border-slate-200 rounded px-2 py-1 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-slate-500">
                    Page {runsPage + 1} of {totalPages}
                  </span>
                  <button
                    onClick={() => setRunsPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={runsPage >= totalPages - 1}
                    className="text-xs font-semibold text-slate-600 border border-slate-200 rounded px-2 py-1 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </section>

        {/* Run Detail */}
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
                  <Link
                    to={`/agentic/console?trace=${encodeURIComponent(selectedRun.trace_id)}`}
                    className="text-xs font-semibold text-sky-700 hover:text-sky-900 underline"
                  >
                    View in console
                  </Link>
                )}
                <StatusBadge status={selectedRun.status as InvoiceStatus} />
              </div>
            </div>

            {/* AI Insights */}
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

            {/* Document Cards */}
            <div className="space-y-4">
              {selectedRun.documents.map((doc) => (
                <InvoiceDocumentCard
                  key={doc.id}
                  doc={doc}
                  isHighlighted={highlightedDocId === doc.id}
                  onApprove={approveInvoice}
                  onDiscard={discardInvoice}
                />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default InvoicesPage;
