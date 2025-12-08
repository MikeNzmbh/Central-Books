import React, { useState, useMemo, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Landmark,
  CreditCard,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ExternalLink,
  Sparkles,
  RefreshCw,
  Wallet,
  ShieldCheck,
  ShieldAlert,
  Search,
  Info,
  Loader2
} from "lucide-react";

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

type RiskLevel = "low" | "medium" | "high";

interface BankSummary {
  id: string;
  name: string;
  last4: string;
  currency: string;
  status: RiskLevel;
  unreconciledCount: number;
  unreconciledAmount: string;
  totalTransactions: number;
  balance: string;
  lastSynced: string;
}

interface BankInsight {
  id: string;
  type: "match" | "anomaly" | "optimization";
  title: string;
  description: string;
}

interface FlaggedTransaction {
  id: string;
  date: string;
  description: string;
  amount: string;
  status: "unmatched" | "partial" | "duplicate" | "suspicious" | "matched" | "excluded";
  suggestion: string;
  confidence: number;
}

interface PreviousAudit {
  date: string;
  status: string;
  color: string;
}

interface BankAuditSummaryResponse {
  banks: BankSummary[];
  insights: Record<string, BankInsight[]>;
  flaggedTransactions: Record<string, FlaggedTransaction[]>;
  previousAudits: PreviousAudit[];
  companionEnabled: boolean;
}

// ---------------------------------------------------------------------------
// HELPERS
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// SUB-COMPONENTS
// ---------------------------------------------------------------------------

const Card = ({ children, className = "", noPadding = false }: { children: React.ReactNode, className?: string, noPadding?: boolean }) => (
  <div className={`bg-white border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] rounded-xl overflow-hidden ${className}`}>
    {noPadding ? children : <div className="p-5">{children}</div>}
  </div>
);

const RiskBadge = ({ status }: { status: RiskLevel }) => {
  if (status === "low") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100 ring-1 ring-emerald-500/10">
        <CheckCircle2 className="w-3 h-3" /> Reconciled
      </span>
    );
  }
  if (status === "medium") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full bg-amber-50 text-amber-700 border border-amber-100 ring-1 ring-amber-500/10">
        <AlertTriangle className="w-3 h-3" /> Review
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full bg-rose-50 text-rose-700 border border-rose-100 ring-1 ring-rose-500/10">
      <ShieldAlert className="w-3 h-3" /> Attention
    </span>
  );
};

const FlagStatusPill = ({ status }: { status: FlaggedTransaction["status"] }) => {
  const styles: Record<string, string> = {
    unmatched: "bg-slate-100 text-slate-600 border-slate-200",
    partial: "bg-blue-50 text-blue-700 border-blue-200",
    duplicate: "bg-amber-50 text-amber-700 border-amber-200",
    suspicious: "bg-rose-50 text-rose-700 border-rose-200",
    matched: "bg-emerald-50 text-emerald-700 border-emerald-200",
    excluded: "bg-slate-50 text-slate-400 border-slate-200",
  };

  return (
    <span className={`inline-flex px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide border ${styles[status] || styles.unmatched}`}>
      {status}
    </span>
  );
};

const LoadingState = () => (
  <div className="min-h-screen bg-slate-50/50 flex items-center justify-center">
    <div className="flex flex-col items-center gap-3">
      <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
      <p className="text-sm text-slate-500">Loading bank audit data...</p>
    </div>
  </div>
);

const ErrorState = ({ error, onRetry }: { error: string; onRetry: () => void }) => (
  <div className="min-h-screen bg-slate-50/50 flex items-center justify-center">
    <div className="flex flex-col items-center gap-4 max-w-md text-center px-4">
      <div className="w-12 h-12 rounded-full bg-rose-100 flex items-center justify-center">
        <AlertTriangle className="w-6 h-6 text-rose-600" />
      </div>
      <h2 className="text-lg font-semibold text-slate-900">Unable to load data</h2>
      <p className="text-sm text-slate-500">{error}</p>
      <button
        onClick={onRetry}
        className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
      >
        Try Again
      </button>
    </div>
  </div>
);

const EmptyState = () => (
  <div className="min-h-screen bg-slate-50/50 font-sans text-slate-900 pb-12">
    <div className="relative z-10 max-w-[1400px] mx-auto px-6 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Bank Audit & Health Check
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          AI-powered diagnostic of your reconciliation status.
        </p>
      </header>

      <Card className="max-w-xl mx-auto text-center py-12">
        <Wallet className="w-12 h-12 text-slate-300 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-slate-900 mb-2">No Bank Accounts Found</h2>
        <p className="text-sm text-slate-500 mb-6">
          Set up your bank accounts and import transactions to start auditing.
        </p>
        <a
          href="/bank/setup/"
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          Set Up Banks
          <ArrowRight className="w-4 h-4" />
        </a>
      </Card>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// MAIN COMPONENT
// ---------------------------------------------------------------------------

export default function BankAuditHealthCheckPage() {
  const [data, setData] = useState<BankAuditSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBankId, setSelectedBankId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [filterText, setFilterText] = useState("");

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const res = await fetch("/api/agentic/bank-audit/summary", {
        credentials: "same-origin",
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to load data (${res.status})`);
      }

      const json: BankAuditSummaryResponse = await res.json();
      setData(json);

      // Auto-select first bank if none selected
      if (!selectedBankId && json.banks.length > 0) {
        setSelectedBankId(json.banks[0].id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load bank audit data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedBankId]);

  useEffect(() => {
    fetchData();
  }, []);

  const selectedBank = useMemo(() => {
    if (!data || !selectedBankId) return null;
    return data.banks.find(b => b.id === selectedBankId) || data.banks[0] || null;
  }, [data, selectedBankId]);

  const insights = useMemo(() => {
    if (!data || !selectedBankId) return [];
    return data.insights[selectedBankId] || [];
  }, [data, selectedBankId]);

  const flaggedTransactions = useMemo(() => {
    if (!data || !selectedBankId) return [];
    let txs = data.flaggedTransactions[selectedBankId] || [];

    // Apply filter
    if (filterText.trim()) {
      const search = filterText.toLowerCase();
      txs = txs.filter(tx =>
        tx.description.toLowerCase().includes(search) ||
        tx.amount.toLowerCase().includes(search) ||
        tx.status.toLowerCase().includes(search)
      );
    }

    return txs;
  }, [data, selectedBankId, filterText]);

  const totalUnreconciled = useMemo(() => {
    if (!data) return 0;
    return data.banks.reduce((acc, curr) => acc + curr.unreconciledCount, 0);
  }, [data]);

  const banksWithIssues = useMemo(() => {
    if (!data) return 0;
    return data.banks.filter(b => b.status === "high").length;
  }, [data]);

  // Loading state
  if (loading) {
    return <LoadingState />;
  }

  // Error state
  if (error) {
    return <ErrorState error={error} onRetry={() => fetchData()} />;
  }

  // Empty state - no banks
  if (!data || data.banks.length === 0) {
    return <EmptyState />;
  }

  const containerAnimation = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemAnimation = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4 } }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 font-sans text-slate-900 pb-12">

      {/* Background Ambience */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-30">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-b from-blue-100/40 to-transparent rounded-bl-full" />
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 py-8">

        {/* --- HEADER --- */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8"
        >
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              Bank Audit & Health Check
            </h1>
            <p className="text-slate-500 mt-1 text-sm max-w-2xl">
              AI-powered diagnostic of your reconciliation status. Review findings here, then fix them in the Banking workspace.
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Summary Stats */}
            <div className="hidden md:flex items-center gap-4 bg-white px-5 py-2.5 rounded-xl border border-slate-200 shadow-sm">
              <div className="text-right">
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Open Items</p>
                <p className="text-xl font-bold text-slate-900 leading-none">
                  {totalUnreconciled}
                </p>
              </div>
              <div className="h-8 w-px bg-slate-100" />
              <div className="text-right">
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Critical</p>
                <p className={`text-xl font-bold leading-none ${banksWithIssues > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                  {banksWithIssues}
                </p>
              </div>
            </div>

            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="h-12 w-12 rounded-xl bg-blue-950 text-white shadow-lg shadow-blue-900/20 hover:bg-blue-900 transition-all flex items-center justify-center disabled:opacity-50"
            >
              <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </motion.header>

        {/* --- MAIN CONTENT GRID --- */}
        <motion.div
          variants={containerAnimation}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-12 gap-8"
        >

          {/* --- LEFT COLUMN: BANK LIST (The Vault) --- */}
          <div className="lg:col-span-4 space-y-6">
            <motion.div variants={itemAnimation}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Wallet className="w-4 h-4 text-slate-400" />
                  Banks Scanned
                </h3>
              </div>

              <div className="space-y-3">
                {data.banks.map((bank) => (
                  <div
                    key={bank.id}
                    onClick={() => setSelectedBankId(bank.id)}
                    className={`group relative p-5 rounded-2xl border transition-all duration-300 cursor-pointer overflow-hidden ${selectedBankId === bank.id
                      ? 'bg-blue-950 border-blue-900 shadow-xl shadow-blue-900/20 ring-1 ring-blue-800'
                      : 'bg-white border-slate-200 hover:border-blue-300 hover:shadow-md'
                      }`}
                  >
                    {/* Active State Background FX */}
                    {selectedBankId === bank.id && (
                      <div className="absolute inset-0 z-0">
                        <div className="absolute top-0 right-0 w-40 h-40 bg-blue-500/10 rounded-full blur-3xl transform translate-x-10 -translate-y-10" />
                      </div>
                    )}

                    <div className="relative z-10 flex justify-between items-start mb-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-sm transition-colors ${selectedBankId === bank.id ? 'bg-white/10 text-white' : 'bg-slate-50 text-slate-600'
                          }`}>
                          <CreditCard className="w-5 h-5" />
                        </div>
                        <div>
                          <h4 className={`text-sm font-bold ${selectedBankId === bank.id ? 'text-white' : 'text-slate-900'}`}>
                            {bank.name}
                          </h4>
                          <p className={`text-xs font-mono mt-0.5 ${selectedBankId === bank.id ? 'text-blue-200' : 'text-slate-400'}`}>
                            •••• {bank.last4}
                          </p>
                        </div>
                      </div>
                      {/* Only show badge on inactive cards to reduce noise on active card */}
                      {selectedBankId !== bank.id && <RiskBadge status={bank.status} />}
                    </div>

                    <div className="relative z-10 grid grid-cols-2 gap-4">
                      <div>
                        <p className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${selectedBankId === bank.id ? 'text-blue-300' : 'text-slate-400'
                          }`}>Last Sync</p>
                        <p className={`text-xs font-medium ${selectedBankId === bank.id ? 'text-blue-100' : 'text-slate-700'
                          }`}>{bank.lastSynced}</p>
                      </div>
                      <div className="text-right">
                        <p className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${selectedBankId === bank.id ? 'text-blue-300' : 'text-slate-400'
                          }`}>Open Items</p>
                        <p className={`text-xl font-bold font-mono leading-none ${bank.unreconciledCount > 0
                          ? (selectedBankId === bank.id ? 'text-rose-300' : 'text-rose-600')
                          : (selectedBankId === bank.id ? 'text-emerald-300' : 'text-emerald-600')
                          }`}>{bank.unreconciledCount}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* History Section */}
            {data.previousAudits.length > 0 && (
              <motion.div variants={itemAnimation} className="pt-4 border-t border-slate-200/60">
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Previous Audits</h4>
                <div className="space-y-2">
                  {data.previousAudits.map((hist, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-2 bg-white rounded-lg border border-slate-100 text-xs">
                      <span className="text-slate-700 font-medium">{hist.date}</span>
                      <span className={`font-semibold ${hist.color}`}>{hist.status}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </div>

          {/* --- RIGHT COLUMN: DIAGNOSTIC PANEL --- */}
          <div className="lg:col-span-8 space-y-6">
            {selectedBank && (
              <motion.div variants={itemAnimation}>
                <Card noPadding className="border-blue-100/50 shadow-md min-h-[600px] flex flex-col">

                  {/* 1. Diagnostic Header */}
                  <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-blue-900 shadow-sm">
                        <Landmark className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h2 className="text-lg font-bold text-slate-900">{selectedBank.name}</h2>
                          <RiskBadge status={selectedBank.status} />
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {selectedBank.currency} Account · {selectedBank.totalTransactions} transactions scanned
                        </p>
                      </div>
                    </div>

                    {/* Primary Action - Drills down to Workspace */}
                    <a
                      href="/banking/"
                      className="group flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 text-xs font-bold rounded-lg hover:border-blue-300 hover:text-blue-700 shadow-sm transition-all"
                    >
                      <span>Open in Banking Workspace</span>
                      <ExternalLink className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                    </a>
                  </div>

                  {/* 2. AI Companion Insights (The "Brain") */}
                  <div className="p-6 bg-gradient-to-b from-white to-blue-50/30 relative overflow-hidden">

                    <div className="flex items-center justify-between mb-4 relative z-10">
                      <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-blue-100 rounded-md">
                          <Sparkles className="w-3.5 h-3.5 text-blue-700" />
                        </div>
                        <h3 className="text-sm font-bold text-slate-900">Neural Diagnostics</h3>
                      </div>
                      <span className="text-[10px] font-medium text-slate-400 flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3" />
                        {data.companionEnabled ? "Suggestions only. No auto-posting." : "Enable AI Companion for insights."}
                      </span>
                    </div>

                    {insights.length > 0 ? (
                      <div className="grid gap-3 relative z-10">
                        {insights.map((insight) => (
                          <div key={insight.id} className="flex gap-4 p-4 bg-white border border-slate-200 rounded-lg shadow-sm hover:border-blue-300 transition-colors group">
                            <div className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 ${insight.type === 'anomaly' ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]' :
                              insight.type === 'optimization' ? 'bg-amber-500' : 'bg-blue-500'
                              }`} />
                            <div className="flex-1">
                              <h4 className="text-xs font-bold text-slate-900 mb-1">{insight.title}</h4>
                              <p className="text-xs font-medium text-slate-600 leading-relaxed">
                                {insight.description}
                              </p>
                            </div>
                            <div className="self-center">
                              <button className="text-xs font-semibold text-blue-600 hover:text-blue-800 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                                Investigate <ArrowRight className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-slate-200 rounded-lg bg-slate-50/50 relative z-10">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
                        <p className="text-sm font-medium text-slate-900">No Anomalies Detected</p>
                        <p className="text-xs text-slate-500">
                          {data.companionEnabled
                            ? "Pattern matching algorithms found no issues with this account."
                            : "Run a bank audit to generate AI insights."}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* 3. Flagged Transactions Table (The "Evidence") */}
                  <div className="flex-1 border-t border-slate-200 bg-white">
                    <div className="px-6 py-4 flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                          Flagged Transactions
                          <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-bold">
                            {flaggedTransactions.length}
                          </span>
                        </h3>
                        <p className="text-xs text-slate-500 mt-1">
                          Items requiring manual review in the Banking workspace.
                        </p>
                      </div>

                      {(data.flaggedTransactions[selectedBankId!]?.length || 0) > 0 && (
                        <div className="relative">
                          <Search className="absolute left-2.5 top-1.5 w-3.5 h-3.5 text-slate-400" />
                          <input
                            type="text"
                            placeholder="Filter..."
                            value={filterText}
                            onChange={(e) => setFilterText(e.target.value)}
                            className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-md bg-slate-50 focus:ring-1 focus:ring-blue-500 outline-none w-40"
                          />
                        </div>
                      )}
                    </div>

                    {flaggedTransactions.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                          <thead>
                            <tr className="bg-slate-50 border-y border-slate-100">
                              <th className="pl-6 pr-4 py-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider w-24">Date</th>
                              <th className="px-4 py-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Description</th>
                              <th className="px-4 py-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-right w-24">Amount</th>
                              <th className="px-4 py-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider w-32">Status</th>
                              <th className="px-4 py-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider">AI Suggestion</th>
                              <th className="pr-6 py-3 w-16"></th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {flaggedTransactions.map((tx) => (
                              <tr key={tx.id} className="group hover:bg-blue-50/30 transition-colors">
                                <td className="pl-6 pr-4 py-3 text-xs font-mono text-slate-500">{tx.date}</td>
                                <td className="px-4 py-3 text-xs font-semibold text-slate-900">{tx.description}</td>
                                <td className={`px-4 py-3 text-xs font-mono font-medium text-right ${tx.amount.startsWith('-') ? 'text-slate-900' : 'text-emerald-600'}`}>
                                  {tx.amount}
                                </td>
                                <td className="px-4 py-3">
                                  <FlagStatusPill status={tx.status} />
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-1.5 text-xs text-slate-600">
                                    <Sparkles className="w-3 h-3 text-blue-400 flex-shrink-0" />
                                    <span className="truncate max-w-[200px]">{tx.suggestion}</span>
                                    <span className="text-[10px] text-slate-400 bg-slate-100 px-1 rounded ml-1">
                                      {tx.confidence}%
                                    </span>
                                  </div>
                                </td>
                                <td className="pr-6 py-3 text-right">
                                  <a
                                    href="/banking/"
                                    className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-all inline-block"
                                    title="View in Reconciliation"
                                  >
                                    <ExternalLink className="w-3.5 h-3.5" />
                                  </a>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 bg-slate-50/30">
                        <CheckCircle2 className="w-10 h-10 text-emerald-200 mb-3" />
                        <p className="text-sm font-medium text-slate-900">All Transactions Cleared</p>
                        <p className="text-xs text-slate-500">No flags requiring attention.</p>
                      </div>
                    )}

                    {flaggedTransactions.length > 0 && (
                      <div className="p-3 bg-slate-50/50 border-t border-slate-100 flex items-center justify-center gap-1 text-xs text-slate-500">
                        <Info className="w-3.5 h-3.5" />
                        <span>To match or edit transactions, switch to the</span>
                        <a href="/banking/" className="font-bold text-blue-700 hover:underline">Banking Workspace</a>
                      </div>
                    )}
                  </div>
                </Card>
              </motion.div>
            )}
          </div>

        </motion.div>

      </div>
    </div>
  );
}
