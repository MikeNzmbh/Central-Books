import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  FileText,
  Calendar,
  Hash,
  Link as LinkIcon,
  ChevronRight,
  ExternalLink,
  Eye,
  EyeOff,
  Search,
  BookOpen,
  Receipt,
  CreditCard,
  Landmark,
  RefreshCw,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
//    Types
// ─────────────────────────────────────────────────────────────────────────────

interface JournalLine {
  id: number;
  account_id: number;
  account_name: string;
  account_code: string;
  debit: string;
  credit: string;
  description: string;
}

interface JournalEntry {
  id: number;
  date: string;
  description: string;
  is_void: boolean;
  source_type: string | null;
  source_label: string | null;
  source_object_id: number | null;
  total_debit: string;
  total_credit: string;
  lines: JournalLine[];
  created_at: string | null;
}

interface Stats {
  total_entries: number;
  ytd_entries: number;
  mtd_entries: number;
}

interface SourceChoice {
  value: string;
  label: string;
}

interface JournalData {
  entries: JournalEntry[];
  stats: Stats;
  source_choices: SourceChoice[];
  currency: string;
}

// ─────────────────────────────────────────────────────────────────────────────
//    Helpers
// ─────────────────────────────────────────────────────────────────────────────

const formatCurrency = (value: string, currency: string): string => {
  const num = parseFloat(value) || 0;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    minimumFractionDigits: 2,
  }).format(num);
};

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const getSourceIcon = (sourceType: string | null) => {
  switch (sourceType) {
    case "invoice": return <Receipt className="h-4 w-4" />;
    case "expense": return <CreditCard className="h-4 w-4" />;
    case "banktransaction": return <Landmark className="h-4 w-4" />;
    case "receipt": return <FileText className="h-4 w-4" />;
    default: return <BookOpen className="h-4 w-4" />;
  }
};

const getSourceUrl = (sourceType: string | null, sourceId: number | null): string | null => {
  if (!sourceType || !sourceId) return null;
  switch (sourceType) {
    case "invoice": return `/invoices/${sourceId}/edit/`;
    case "expense": return `/expenses/${sourceId}/edit/`;
    case "banktransaction": return `/banking/transactions/${sourceId}/`;
    case "receipt": return `/receipts/`;
    default: return null;
  }
};

const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(" ");

// ─────────────────────────────────────────────────────────────────────────────
//    Journal Entry Drawer
// ─────────────────────────────────────────────────────────────────────────────

interface JournalEntryDrawerProps {
  entry: JournalEntry;
  currency: string;
  onClose: () => void;
}

const JournalEntryDrawer: React.FC<JournalEntryDrawerProps> = ({ entry, currency, onClose }) => {
  const sourceUrl = getSourceUrl(entry.source_type, entry.source_object_id);
  const isBalanced = entry.total_debit === entry.total_credit;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex justify-end"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <motion.div
        className="relative h-full w-full max-w-lg bg-white shadow-2xl flex flex-col"
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 30, stiffness: 300 }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">
                Entry #{entry.id}
              </h2>
              {entry.is_void && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-100 text-rose-700 border border-rose-200">
                  Void
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-500">
              <Calendar className="h-4 w-4" />
              {formatDate(entry.date)}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-100 transition-colors"
          >
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* Totals Summary */}
        <div className="border-b border-slate-100 px-6 py-4 bg-slate-50/50">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Total Debit</div>
              <div className="text-xl font-bold text-emerald-600 mt-0.5">
                {formatCurrency(entry.total_debit, currency)}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Total Credit</div>
              <div className="text-xl font-bold text-rose-600 mt-0.5">
                {formatCurrency(entry.total_credit, currency)}
              </div>
            </div>
          </div>
          {!isBalanced && (
            <div className="mt-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs font-medium">
              ⚠️ Entry is not balanced
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6 space-y-5">
            {/* Description */}
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Description</h4>
              <p className="text-sm text-slate-900 font-medium">
                {entry.description || "No description"}
              </p>
            </div>

            {/* Source */}
            {entry.source_type && (
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Source</h4>
                <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="h-9 w-9 rounded-full bg-slate-200 flex items-center justify-center text-slate-500">
                    {getSourceIcon(entry.source_type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-900 truncate capitalize">
                      {entry.source_type?.replace("banktransaction", "Bank Transaction")}
                    </div>
                    <div className="text-xs text-slate-500">{entry.source_label || `ID: ${entry.source_object_id}`}</div>
                  </div>
                  {sourceUrl && (
                    <a
                      href={sourceUrl}
                      className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors"
                    >
                      <ExternalLink className="h-4 w-4 text-slate-400" />
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* Status */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Status</h4>
                <div className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold",
                  entry.is_void
                    ? "bg-rose-50 text-rose-700 border border-rose-200"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                )}>
                  <span className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    entry.is_void ? "bg-rose-500" : "bg-emerald-500"
                  )} />
                  {entry.is_void ? "Void" : "Active"}
                </div>
              </div>
              <div className="space-y-1.5">
                <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Lines</h4>
                <div className="flex items-center gap-2 text-sm text-slate-900">
                  <Hash className="h-4 w-4 text-slate-400" />
                  {entry.lines.length} lines
                </div>
              </div>
            </div>

            {/* Journal Lines */}
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Journal Lines</h4>
              <div className="rounded-xl border border-slate-100 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b border-slate-100">
                    <tr className="text-[10px] uppercase text-slate-500 font-bold">
                      <th className="px-3 py-2 text-left">Account</th>
                      <th className="px-3 py-2 text-right">Debit</th>
                      <th className="px-3 py-2 text-right">Credit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {entry.lines.map((line) => (
                      <tr key={line.id} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2.5">
                          <div className="space-y-0.5">
                            <div className="font-mono text-[10px] text-slate-400">{line.account_code}</div>
                            <div className="font-medium text-slate-900 text-xs">{line.account_name}</div>
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-right font-medium text-emerald-600 text-xs">
                          {parseFloat(line.debit) > 0 ? formatCurrency(line.debit, currency) : "—"}
                        </td>
                        <td className="px-3 py-2.5 text-right font-medium text-rose-600 text-xs">
                          {parseFloat(line.credit) > 0 ? formatCurrency(line.credit, currency) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-100 border-t border-slate-200">
                    <tr className="font-bold text-xs">
                      <td className="px-3 py-2.5 text-slate-700">Total</td>
                      <td className="px-3 py-2.5 text-right text-emerald-700">
                        {formatCurrency(entry.total_debit, currency)}
                      </td>
                      <td className="px-3 py-2.5 text-right text-rose-700">
                        {formatCurrency(entry.total_credit, currency)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 px-6 py-4 bg-slate-50/50">
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:bg-white transition-colors"
            >
              Close
            </button>
            {sourceUrl && (
              <a
                href={sourceUrl}
                className="px-4 py-2 rounded-lg bg-slate-900 text-sm font-semibold text-white hover:bg-slate-800 transition-colors"
              >
                View Source
              </a>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//    Main Component
// ─────────────────────────────────────────────────────────────────────────────

export const JournalEntriesPage: React.FC = () => {
  const [data, setData] = useState<JournalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [showVoid, setShowVoid] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.set("q", searchQuery);
      if (sourceFilter !== "all") params.set("source", sourceFilter);
      if (showVoid) params.set("show_void", "true");

      const response = await fetch(`/api/journal/list/?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch journal entries");
      const json = await response.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [sourceFilter, showVoid]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchData();
    }, 300);
    return () => clearTimeout(debounce);
  }, [searchQuery]);

  const handleRowClick = (entry: JournalEntry) => {
    setSelectedEntry(entry);
  };

  const handleCloseDrawer = () => {
    setSelectedEntry(null);
  };

  const currency = data?.currency || "USD";
  const stats = data?.stats;
  const entries = data?.entries || [];
  const sourceChoices = data?.source_choices || [];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">Accounting</p>
            <h1 className="text-2xl font-semibold">Journal Entries</h1>
            <p className="text-sm text-slate-500">View and manage your general ledger entries.</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <a
              href="/journal/new/"
              className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors"
            >
              + New Entry
            </a>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3">
            {error}
          </div>
        )}

        {/* KPI Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">Total Entries</div>
              <div className="text-2xl font-semibold text-slate-900 mt-1">{stats.total_entries}</div>
              <p className="text-xs text-slate-500 mt-1">All time</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">Year to Date</div>
              <div className="text-2xl font-semibold text-slate-900 mt-1">{stats.ytd_entries}</div>
              <p className="text-xs text-slate-500 mt-1">Entries this year</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs font-medium text-slate-500 uppercase">This Month</div>
              <div className="text-2xl font-semibold text-slate-900 mt-1">{stats.mtd_entries}</div>
              <p className="text-xs text-slate-500 mt-1">Entries this month</p>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 max-w-xs relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-slate-700">Source:</label>
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              >
                <option value="all">All Sources</option>
                {sourceChoices.map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={showVoid}
                onChange={(e) => setShowVoid(e.target.checked)}
                className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
              />
              {showVoid ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              Show Void
            </label>
          </div>
        </div>

        {/* Entries Table */}
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          {loading && !data ? (
            <div className="p-8 text-center text-slate-500">Loading journal entries...</div>
          ) : entries.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              No journal entries found. <a href="/journal/new/" className="text-sky-600 hover:underline">Create your first entry</a>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr className="text-xs uppercase text-slate-500">
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Description</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                    <th className="px-4 py-3 font-medium text-right">Debit</th>
                    <th className="px-4 py-3 font-medium text-right">Credit</th>
                    <th className="px-4 py-3 font-medium text-center">Lines</th>
                    <th className="px-4 py-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => {
                    const isSelected = selectedEntry?.id === entry.id;
                    return (
                      <tr
                        key={entry.id}
                        onClick={() => handleRowClick(entry)}
                        className={cn(
                          "border-b border-slate-100 cursor-pointer transition-colors",
                          isSelected ? "bg-sky-50" : "hover:bg-slate-50",
                          entry.is_void && "opacity-50"
                        )}
                      >
                        <td className="px-4 py-3 font-medium text-slate-800 whitespace-nowrap">
                          {formatDate(entry.date)}
                        </td>
                        <td className="px-4 py-3 text-slate-600 max-w-xs truncate">
                          {entry.description || "—"}
                          {entry.is_void && (
                            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-rose-100 text-rose-700">
                              Void
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {entry.source_type && (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600">
                              {getSourceIcon(entry.source_type)}
                              <span className="capitalize">{entry.source_label || entry.source_type}</span>
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-emerald-600">
                          {formatCurrency(entry.total_debit, currency)}
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-rose-600">
                          {formatCurrency(entry.total_credit, currency)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-slate-100 text-xs font-medium text-slate-600">
                            {entry.lines.length}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <ChevronRight className="h-4 w-4 text-slate-400" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Journal Entry Drawer */}
      <AnimatePresence>
        {selectedEntry && (
          <JournalEntryDrawer
            entry={selectedEntry}
            currency={currency}
            onClose={handleCloseDrawer}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default JournalEntriesPage;
