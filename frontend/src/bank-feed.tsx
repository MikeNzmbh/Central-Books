import React, { useState, useCallback, useEffect, useMemo } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { motion, AnimatePresence } from "framer-motion";
import {
  Landmark,
  CreditCard,
  Search,
  Filter,
  Download,
  Plus,
  Check,
  MoreHorizontal,
  RefreshCw,
  Settings,
  ChevronDown,
  Paperclip,
  CheckCircle2,
  Clock,
  AlertCircle,
  ShieldCheck,
  Sparkles
} from "lucide-react";

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

type TransactionStatus = "NEW" | "PARTIAL" | "MATCHED_SINGLE" | "MATCHED_MULTI" | "EXCLUDED";

interface Account {
  id: number;
  name: string;
  institution: string;
  type: "checking" | "credit";
  last4: string;
  currency: string;
  balance: number;
  lastSynced: string;
  unreconciledCount: number;
}

interface Transaction {
  id: number;
  date: string;
  payee: string;
  description: string;
  amount: number;
  type: "debit" | "credit";
  category?: string;
  status: TransactionStatus;
  matchSuggestion?: string;
  hasAttachment: boolean;
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

function formatMoney(value: number | string | null | undefined, currency: string = "USD") {
  const num = typeof value === "number" ? value : Number(value || 0);
  const sign = num < 0 ? "-" : "";
  const abs = Math.abs(num).toFixed(2);
  return `${sign}$${abs}`;
}

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return "Never";
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
}

// ---------------------------------------------------------------------------
// COMPONENTS
// ---------------------------------------------------------------------------

const StatusBadge = ({ status, suggestion }: { status: TransactionStatus, suggestion?: string }) => {
  if (status === "MATCHED_SINGLE" || status === "MATCHED_MULTI") {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-100 text-[10px] font-bold uppercase tracking-wide">
          <CheckCircle2 className="w-3 h-3" /> Match
        </span>
        {suggestion && <span className="text-xs text-slate-500 font-medium">{suggestion}</span>}
      </div>
    );
  }
  if (status === "PARTIAL") {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-100 text-[10px] font-bold uppercase tracking-wide">
          <Sparkles className="w-3 h-3" /> Partial
        </span>
        {suggestion && <span className="text-xs text-slate-500 font-medium truncate max-w-[100px]">{suggestion}</span>}
      </div>
    );
  }
  if (status === "EXCLUDED") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-500 border border-slate-200 text-[10px] font-bold uppercase tracking-wide">
        Excluded
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-100 text-[10px] font-bold uppercase tracking-wide">
      <AlertCircle className="w-3 h-3" /> Unreconciled
    </span>
  );
};

// ---------------------------------------------------------------------------
// MAIN COMPONENT
// ---------------------------------------------------------------------------

export default function BankFeedPage() {
  // State
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "review" | "matched">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch accounts from API (Option B)
  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch("/api/banking/overview/", { credentials: "same-origin" });
      if (!res.ok) throw new Error("Unable to load bank accounts.");
      const data = await res.json();

      const normalized: Account[] = (data.accounts || []).map((acc: any) => ({
        id: acc.id,
        name: acc.name,
        institution: acc.bank || "Bank",
        type: acc.ledger_balance < 0 ? "credit" : "checking",
        last4: acc.last4 || "••••",
        currency: acc.currency || "USD",
        balance: Number(acc.ledger_balance || 0),
        lastSynced: formatRelativeTime(acc.last_import_at),
        unreconciledCount: acc.new_count || 0,
      }));

      setAccounts(normalized);

      // Auto-select first account if none selected
      if (!selectedAccountId && normalized.length > 0) {
        setSelectedAccountId(normalized[0].id);
      }
    } catch (err) {
      throw err;
    }
  }, [selectedAccountId]);

  // Fetch transactions for selected account (Option B)
  const fetchTransactions = useCallback(async () => {
    if (!selectedAccountId) {
      setTransactions([]);
      return;
    }

    try {
      const params = new URLSearchParams();
      params.set("account_id", String(selectedAccountId));
      params.set("status", "ALL");

      const res = await fetch(`/api/banking/feed/transactions/?${params.toString()}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("Unable to load transactions.");

      const data = await res.json();
      const txs: Transaction[] = (data.transactions || []).map((tx: any) => ({
        id: tx.id,
        date: tx.date,
        payee: tx.description?.split(" ")[0] || "Unknown",
        description: tx.description || "",
        amount: Math.abs(Number(tx.amount || 0)),
        type: Number(tx.amount || 0) < 0 ? "debit" : "credit",
        category: tx.category_name || undefined,
        status: tx.status as TransactionStatus,
        matchSuggestion: tx.match_suggestion || undefined,
        hasAttachment: Boolean(tx.has_attachment),
      }));

      setTransactions(txs);
    } catch (err) {
      throw err;
    }
  }, [selectedAccountId]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        await fetchAccounts();
      } catch (err: any) {
        setError(err.message || "Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // Fetch transactions when account changes
  useEffect(() => {
    if (selectedAccountId) {
      fetchTransactions().catch(err => {
        console.error("Failed to load transactions:", err);
      });
    }
  }, [selectedAccountId, fetchTransactions]);

  // Refresh handler
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([fetchAccounts(), fetchTransactions()]);
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setRefreshing(false);
    }
  }, [fetchAccounts, fetchTransactions]);

  // Derived state
  const selectedAccount = useMemo(() =>
    accounts.find(a => a.id === selectedAccountId) || accounts[0] || null,
    [accounts, selectedAccountId]
  );

  const filteredTransactions = useMemo(() => {
    let txs = transactions;

    // Filter by tab
    if (activeTab === "review") {
      txs = txs.filter(tx => tx.status === "NEW" || tx.status === "PARTIAL");
    } else if (activeTab === "matched") {
      txs = txs.filter(tx => tx.status === "MATCHED_SINGLE" || tx.status === "MATCHED_MULTI");
    }

    // Filter by search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      txs = txs.filter(tx =>
        tx.payee.toLowerCase().includes(q) ||
        tx.description.toLowerCase().includes(q) ||
        String(tx.amount).includes(q)
      );
    }

    return txs;
  }, [transactions, activeTab, searchQuery]);

  const reviewCount = useMemo(() =>
    transactions.filter(tx => tx.status === "NEW" || tx.status === "PARTIAL").length,
    [transactions]
  );

  const matchedCount = useMemo(() =>
    transactions.filter(tx => tx.status === "MATCHED_SINGLE" || tx.status === "MATCHED_MULTI").length,
    [transactions]
  );

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
          <p className="text-sm text-slate-500">Loading banking data...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 max-w-md text-center px-4">
          <AlertCircle className="w-12 h-12 text-rose-400" />
          <h2 className="text-lg font-semibold text-slate-900">Unable to load data</h2>
          <p className="text-sm text-slate-500">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 pb-12 flex flex-col">

      {/* --- Global Header (Workspace Style) --- */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="bg-blue-950 p-1.5 rounded-lg shadow-sm">
              <Landmark className="w-4 h-4 text-white" />
            </div>
            <span className="text-xs font-bold tracking-widest text-blue-950 uppercase">Banking Workspace</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 rounded-lg transition-colors border border-transparent hover:border-slate-200">
            <Settings className="w-4 h-4" />
            <span>Rules</span>
          </button>
          <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 rounded-lg transition-colors border border-transparent hover:border-slate-200">
            <Download className="w-4 h-4" />
            <span>Export</span>
          </button>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-blue-950 text-white rounded-lg shadow-sm hover:bg-blue-900 transition-colors text-xs font-bold">
            <Plus className="w-3.5 h-3.5" />
            <span>Add Transaction</span>
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* --- LEFT SIDEBAR: Accounts Vault --- */}
        <aside className="w-80 bg-slate-50 border-r border-slate-200 flex flex-col overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4 px-2">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Accounts</h3>
              <a href="/bank/setup/" className="text-slate-400 hover:text-blue-900 transition-colors">
                <Plus className="w-4 h-4" />
              </a>
            </div>

            <div className="space-y-3">
              {accounts.length === 0 ? (
                <div className="text-center py-8">
                  <CreditCard className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No accounts yet</p>
                  <a href="/bank/setup/" className="text-xs text-blue-600 hover:underline">Add your first bank</a>
                </div>
              ) : accounts.map((acc) => (
                <div
                  key={acc.id}
                  onClick={() => setSelectedAccountId(acc.id)}
                  className={`relative p-4 rounded-xl border cursor-pointer transition-all duration-200 group ${selectedAccountId === acc.id
                      ? "bg-white border-blue-500 shadow-md ring-1 ring-blue-500/20 z-10"
                      : "bg-white border-slate-200 hover:border-blue-300 hover:shadow-sm"
                    }`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center border ${selectedAccountId === acc.id ? "bg-blue-50 border-blue-100 text-blue-700" : "bg-slate-50 border-slate-100 text-slate-500"
                        }`}>
                        <CreditCard className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-900">{acc.name}</h4>
                        <p className="text-xs text-slate-500 font-mono">•••• {acc.last4}</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">Balance</p>
                      <p className="text-sm font-mono font-semibold text-slate-900">
                        {acc.currency} {acc.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    {acc.unreconciledCount > 0 && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100 text-[10px] font-bold">
                        {acc.unreconciledCount}
                      </span>
                    )}
                  </div>

                  {/* Active Indicator */}
                  {selectedAccountId === acc.id && (
                    <div className="absolute left-0 top-4 bottom-4 w-1 bg-blue-500 rounded-r-full" />
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="mt-auto p-4 border-t border-slate-200">
            <div className="bg-blue-50/50 rounded-lg p-3 border border-blue-100">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-1 bg-blue-100 rounded-md">
                  <ShieldCheck className="w-3 h-3 text-blue-700" />
                </div>
                <span className="text-xs font-bold text-blue-900">Audit Status</span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-600 mb-2">
                <span>Last Scan: Today</span>
                <span className="text-emerald-600 font-medium">Healthy</span>
              </div>
              <a
                href="/bank-review/"
                className="block w-full py-1.5 bg-white border border-blue-200 rounded-md text-[10px] font-bold text-blue-700 hover:bg-blue-50 transition-colors shadow-sm text-center"
              >
                Run Health Check
              </a>
            </div>
          </div>
        </aside>

        {/* --- MAIN CONTENT: Financial Feed --- */}
        <main className="flex-1 bg-white flex flex-col min-w-0">

          {/* Toolbar */}
          {selectedAccount && (
            <div className="px-6 py-4 border-b border-slate-100 flex flex-col gap-4">
              {/* Account Summary Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                    {selectedAccount.name}
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200 uppercase">
                      {selectedAccount.type}
                    </span>
                  </h2>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Updated {selectedAccount.lastSynced}
                    </span>
                    <span>•</span>
                    <span>{selectedAccount.currency} Account</span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">Current Balance</p>
                  <p className="text-2xl font-mono font-bold text-slate-900 tracking-tight">
                    ${selectedAccount.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </p>
                </div>
              </div>

              {/* Controls */}
              <div className="flex flex-wrap items-center justify-between gap-4 mt-2">
                <div className="flex items-center gap-2 bg-slate-100/50 p-1 rounded-lg border border-slate-200/50">
                  {[
                    { key: 'all', label: 'All Transactions' },
                    { key: 'review', label: `For Review (${reviewCount})` },
                    { key: 'matched', label: `Matched (${matchedCount})` },
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key as any)}
                      className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === tab.key
                          ? 'bg-white text-blue-950 shadow-sm ring-1 ring-slate-200'
                          : 'text-slate-500 hover:text-slate-700'
                        }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1.5 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search description, amount..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 pr-4 py-1.5 text-xs font-medium border border-slate-200 rounded-lg w-64 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all"
                    />
                  </div>
                  <button
                    onClick={handleRefresh}
                    disabled={refreshing}
                    className="p-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-500 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Transaction Table */}
          <div className="flex-1 overflow-auto">
            {filteredTransactions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-12">
                <CheckCircle2 className="w-12 h-12 text-emerald-200 mb-3" />
                <p className="text-sm font-medium text-slate-900">No transactions to show</p>
                <p className="text-xs text-slate-500">
                  {activeTab === 'review' ? 'All transactions have been reviewed.' : 'Import transactions to get started.'}
                </p>
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead className="bg-slate-50 sticky top-0 z-20 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 w-10">
                      <input type="checkbox" className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
                    </th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-24">Date</th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Description & Payee</th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Category</th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider text-right w-32">Spent</th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider text-right w-32">Received</th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-40">Status</th>
                    <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-16">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTransactions.map((tx) => (
                    <tr key={tx.id} className="group hover:bg-blue-50/20 transition-colors">
                      <td className="px-4 py-3">
                        <input type="checkbox" className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
                      </td>
                      <td className="px-4 py-3 text-xs font-medium text-slate-500">{tx.date}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col">
                          <span className="text-xs font-bold text-slate-900">{tx.payee}</span>
                          <span className="text-[10px] text-slate-500 font-mono truncate max-w-[300px]">{tx.description}</span>
                          {tx.hasAttachment && (
                            <div className="flex items-center gap-1 mt-0.5 text-[10px] text-blue-600">
                              <Paperclip className="w-3 h-3" />
                              <span>Receipt attached</span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {tx.category ? (
                          <span className="inline-flex px-2 py-0.5 rounded border border-slate-200 bg-slate-50 text-[10px] font-medium text-slate-600">
                            {tx.category}
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-600 font-medium italic flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" /> Select Category
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {tx.type === 'debit' && (
                          <span className="text-xs font-mono font-medium text-slate-900">
                            {tx.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {tx.type === 'credit' && (
                          <span className="text-xs font-mono font-medium text-emerald-600">
                            {tx.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={tx.status} suggestion={tx.matchSuggestion} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          {tx.status === 'MATCHED_SINGLE' || tx.status === 'MATCHED_MULTI' ? (
                            <button className="p-1.5 bg-emerald-50 text-emerald-600 rounded hover:bg-emerald-100 transition-colors" title="Confirm Match">
                              <Check className="w-3.5 h-3.5" />
                            </button>
                          ) : (
                            <button className="p-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors" title="Find Match">
                              <Search className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button className="p-1.5 hover:bg-slate-100 text-slate-400 rounded transition-colors">
                            <MoreHorizontal className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* Empty State / Pagination Spacer */}
            <div className="h-20" />
          </div>

          {/* Footer / Batch Actions */}
          <div className="bg-white border-t border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm z-20">
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span>Showing {filteredTransactions.length} of {transactions.length} transactions</span>
              <span className="w-px h-4 bg-slate-200" />
              <span>Last updated just now</span>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-bold hover:bg-slate-50 transition-colors">
                Previous
              </button>
              <button className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-bold hover:bg-slate-50 transition-colors">
                Next
              </button>
            </div>
          </div>

        </main>
      </div>
    </div>
  );
}

// Mount the app
const rootEl = document.getElementById("bank-feed-root");
if (rootEl) {
  const root = ReactDOM.createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <BankFeedPage />
    </React.StrictMode>,
  );
}
