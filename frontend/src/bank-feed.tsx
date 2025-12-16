import React, { useState, useCallback, useEffect, useMemo } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { motion, AnimatePresence } from "framer-motion";
import {
  Banknote,
  RefreshCw,
  Filter,
  Search,
  ChevronRight,
  ArrowDownToLine,
  ArrowUpToLine,
  Settings2,
  CheckCircle2,
  XCircle,
  Shuffle,
  Sparkles,
  Wallet,
  Receipt,
  CreditCard,
  Download,
  Plus,
  Clock,
  AlertCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

type FeedStatus = "for_review" | "categorized" | "excluded" | "all";
type TransactionStatus = "NEW" | "PARTIAL" | "MATCHED_SINGLE" | "MATCHED_MULTI" | "EXCLUDED";

interface BankAccountSummary {
  id: number;
  name: string;
  institution: string;
  currency: string;
  last4: string;
  balance: number;
  clearedBalance: number;
  lastSync: string;
  status: "ok" | "warning" | "error";
  unreconciledCount: number;
}

interface MatchCandidate {
  id: string;
  type: "invoice" | "expense" | "transfer";
  label: string;
  reference: string;
  date: string;
  amount: number;
  confidence: number;
}

interface BankFeedTransaction {
  id: number;
  date: string;
  description: string;
  payee: string;
  direction: "in" | "out";
  amount: number;
  currency: string;
  status: FeedStatus;
  rawStatus: TransactionStatus;
  category?: string;
  importRuleHint?: string;
  hasAnomaly?: boolean;
  suggestedMatches?: MatchCandidate[];
}

interface DrawerFormState {
  mode: "match" | "categorize" | "tax";
  selectedMatchId?: string;
  category?: string;
  taxCode?: string;
  memo?: string;
}

// ---------------------------------------------------------------------------
// HELPERS
// ---------------------------------------------------------------------------

function formatCurrency(amount: number, currency = "CAD") {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatRelativeTime(isoString: string | null): string {
  if (!isoString) return "Never";
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return "Yesterday";
  return `${diffDays}d ago`;
}

function mapApiStatus(rawStatus: TransactionStatus): FeedStatus {
  switch (rawStatus) {
    case "NEW":
    case "PARTIAL":
      return "for_review";
    case "MATCHED_SINGLE":
    case "MATCHED_MULTI":
      return "categorized";
    case "EXCLUDED":
      return "excluded";
    default:
      return "for_review";
  }
}

const expenseCategories = [
  "Software & SaaS",
  "Advertising & Marketing",
  "Meals & Entertainment",
  "Rent & Utilities",
  "Travel",
  "Owner Draw",
];

const incomeCategories = [
  "Sales",
  "Subscription Revenue",
  "Consulting Income",
  "Interest Income",
];

const taxCodes = [
  { id: "GST_ONLY", label: "GST only" },
  { id: "HST_ONLY", label: "HST only" },
  { id: "GST_HST", label: "Combined GST/HST" },
  { id: "EXEMPT", label: "Tax exempt" },
  { id: "OUT_OF_SCOPE", label: "Out of scope" },
];

// ---------------------------------------------------------------------------
// HELPER FUNCTIONS
// ---------------------------------------------------------------------------

const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(" ");

// ---------------------------------------------------------------------------
// MAIN COMPONENT
// ---------------------------------------------------------------------------

export default function BankFeedPage() {
  const [accounts, setAccounts] = useState<BankAccountSummary[]>([]);
  const [transactions, setTransactions] = useState<BankFeedTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<FeedStatus>("for_review");
  const [search, setSearch] = useState("");
  const [selectedTxId, setSelectedTxId] = useState<number | null>(null);
  const [drawerForm, setDrawerForm] = useState<DrawerFormState>({ mode: "match" });

  // Fetch accounts
  const fetchAccounts = useCallback(async () => {
    const res = await fetch("/api/banking/overview/", { credentials: "same-origin" });
    if (!res.ok) throw new Error("Unable to load bank accounts.");
    const data = await res.json();

    const normalized: BankAccountSummary[] = (data.accounts || []).map((acc: any) => ({
      id: acc.id,
      name: acc.name,
      institution: acc.bank || "Bank",
      currency: acc.currency || "CAD",
      last4: acc.last4 || "••••",
      balance: Number(acc.ledger_balance || 0),
      clearedBalance: Number(acc.cleared_balance || acc.ledger_balance || 0),
      lastSync: formatRelativeTime(acc.last_import_at),
      status: acc.new_count > 5 ? "warning" : "ok",
      unreconciledCount: acc.new_count || 0,
    }));

    setAccounts(normalized);

    if (!selectedAccountId && normalized.length > 0) {
      setSelectedAccountId(normalized[0].id);
    }
  }, [selectedAccountId]);

  // Fetch transactions
  const fetchTransactions = useCallback(async () => {
    if (!selectedAccountId) {
      setTransactions([]);
      return;
    }

    const params = new URLSearchParams();
    params.set("account_id", String(selectedAccountId));
    params.set("status", "ALL");

    const res = await fetch(`/api/banking/feed/transactions/?${params.toString()}`, {
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Unable to load transactions.");

    const data = await res.json();
    const txs: BankFeedTransaction[] = (data.transactions || []).map((tx: any) => {
      const rawStatus = tx.status as TransactionStatus;
      const amount = Math.abs(Number(tx.amount || 0));
      return {
        id: tx.id,
        date: tx.date,
        payee: tx.description?.split(" ")[0] || "Unknown",
        description: tx.description || "",
        direction: Number(tx.amount || 0) >= 0 ? "in" : "out",
        amount,
        currency: "CAD",
        status: mapApiStatus(rawStatus),
        rawStatus,
        category: tx.category_name || undefined,
        importRuleHint: tx.match_suggestion || undefined,
        hasAnomaly: rawStatus === "PARTIAL",
      };
    });

    setTransactions(txs);
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
      fetchTransactions().catch(console.error);
    }
  }, [selectedAccountId, fetchTransactions]);

  // Refresh
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([fetchAccounts(), fetchTransactions()]);
    } finally {
      setRefreshing(false);
    }
  }, [fetchAccounts, fetchTransactions]);

  // Derived
  const activeAccount = useMemo(
    () => accounts.find((a) => a.id === selectedAccountId) ?? accounts[0] ?? null,
    [accounts, selectedAccountId]
  );

  const filteredTransactions = useMemo(() => {
    let list = transactions;
    if (statusFilter !== "all") {
      list = list.filter((tx) => tx.status === statusFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (tx) =>
          tx.description.toLowerCase().includes(q) ||
          tx.payee.toLowerCase().includes(q) ||
          (tx.category ?? "").toLowerCase().includes(q)
      );
    }
    return list;
  }, [transactions, statusFilter, search]);

  const selectedTx = useMemo(
    () => transactions.find((t) => t.id === selectedTxId) ?? null,
    [transactions, selectedTxId]
  );

  const totals = useMemo(() => {
    const moneyIn = transactions.filter((tx) => tx.direction === "in").reduce((sum, tx) => sum + tx.amount, 0);
    const moneyOut = transactions.filter((tx) => tx.direction === "out").reduce((sum, tx) => sum + tx.amount, 0);
    const toReview = transactions.filter((tx) => tx.status === "for_review").length;
    const categorized = transactions.filter((tx) => tx.status === "categorized").length;
    return { moneyIn, moneyOut, toReview, categorized };
  }, [transactions]);

  const handleOpenDrawer = (tx: BankFeedTransaction) => {
    setSelectedTxId(tx.id);
    setDrawerForm({
      mode: tx.suggestedMatches && tx.suggestedMatches.length > 0 ? "match" : tx.direction === "out" ? "categorize" : "tax",
      selectedMatchId: tx.suggestedMatches?.[0]?.id,
      category: tx.category,
    });
  };

  const handleApply = () => {
    setSelectedTxId(null);
    // TODO: POST to API to save categorization/match
  };

  const statusLabel = (status: FeedStatus) => {
    switch (status) {
      case "for_review": return "For review";
      case "categorized": return "Categorized";
      case "excluded": return "Excluded";
      default: return "All";
    }
  };

  // Loading
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50/80 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-900 border-t-transparent" />
          <p className="text-sm text-slate-500">Loading banking data...</p>
        </div>
      </div>
    );
  }

  // Error
  if (error) {
    return (
      <div className="min-h-screen bg-slate-50/80 flex items-center justify-center">
        <div className="rounded-2xl border border-red-100 bg-red-50 p-6 text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-rose-400 mx-auto mb-3" />
          <p className="text-sm font-medium text-red-700">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-xs font-medium text-white hover:bg-red-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/80 px-6 py-6 font-sans">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between gap-6">
          <div className="space-y-1">
            <h1 className="text-[26px] font-bold tracking-tight text-slate-900">Banking</h1>
            <p className="text-sm text-slate-500">
              Live bank feeds, smart matching, and tax-aware categorization for all your accounts.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="/bank/import/"
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-all"
            >
              <Download className="h-4 w-4" />
              Import statements
            </a>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 transition-all disabled:opacity-50"
            >
              <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
              Fetch bank feed
            </button>
          </div>
        </div>

        {/* Account Cards Carousel */}
        <div className="w-full overflow-x-auto rounded-2xl border border-slate-200 bg-white/90 p-3 shadow-sm">
          <div className="flex min-w-max gap-3">
            {accounts.map((account) => {
              const isActive = account.id === selectedAccountId;
              return (
                <button
                  key={account.id}
                  onClick={() => setSelectedAccountId(account.id)}
                  className={cn(
                    "flex min-w-[260px] flex-col justify-between rounded-2xl border px-4 py-3 text-left transition-all",
                    "hover:-translate-y-[1px] hover:shadow-md",
                    isActive
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50/80 text-slate-900"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">Account</div>
                      <div className="text-sm font-bold tracking-tight">{account.name}</div>
                      <div className={cn("text-[11px] tracking-wide", isActive ? "text-slate-100/80" : "text-slate-500")}>
                        {account.institution} · ··{account.last4}
                      </div>
                    </div>
                    <Banknote className={cn("h-5 w-5", isActive ? "text-emerald-300" : "text-emerald-500")} />
                  </div>

                  <div className="mt-4 flex items-end justify-between">
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.16em] opacity-70">Current balance</div>
                      <div className="text-lg font-bold tracking-tight">
                        {formatCurrency(account.balance, account.currency)}
                      </div>
                      <div className={cn("mt-1 text-[11px] tracking-wide", isActive ? "text-slate-100/80" : "text-slate-500")}>
                        Cleared {formatCurrency(account.clearedBalance, account.currency)}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide border",
                          account.status === "ok" && (isActive ? "border-emerald-300 text-emerald-100" : "border-emerald-500 text-emerald-600"),
                          account.status === "warning" && "border-amber-500 bg-amber-50 text-amber-700"
                        )}
                      >
                        {account.status === "ok" && "In sync"}
                        {account.status === "warning" && "Needs review"}
                      </span>
                      <div className={cn("text-[11px] tracking-wide", isActive ? "text-slate-100/80" : "text-slate-500")}>
                        {account.lastSync}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}

            {accounts.length === 0 && (
              <div className="flex min-w-[260px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center">
                <CreditCard className="h-8 w-8 text-slate-300 mb-2" />
                <p className="text-sm font-medium text-slate-600">No accounts connected</p>
                <a href="/bank/setup/" className="mt-2 text-xs text-blue-600 hover:underline">
                  Connect your first bank
                </a>
              </div>
            )}
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2.1fr)_minmax(0,1.3fr)]">
          {/* Bank Feed Card */}
          <div className="rounded-[1.5rem] border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-row items-center justify-between gap-4 p-5 pb-3 border-b border-slate-100">
              <div className="space-y-1">
                <h3 className="text-base font-bold tracking-tight text-slate-900">Bank feed</h3>
                <p className="text-xs text-slate-500">
                  Match, categorize, and add tax before posting to your books.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative w-56">
                  <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search description, payee..."
                    className="h-9 w-full rounded-full border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs focus:outline-none focus:ring-2 focus:ring-slate-200"
                  />
                </div>
                <button className="h-9 w-9 rounded-full border border-slate-200 flex items-center justify-center hover:bg-slate-50">
                  <Filter className="h-4 w-4 text-slate-500" />
                </button>
              </div>
            </div>

            <div className="p-5 space-y-4">
              {/* Status Tabs */}
              <div className="flex items-center justify-between gap-4">
                <div className="grid h-9 w-full max-w-md grid-cols-4 rounded-full bg-slate-100 p-1">
                  {(["for_review", "categorized", "excluded", "all"] as FeedStatus[]).map((status) => (
                    <button
                      key={status}
                      onClick={() => setStatusFilter(status)}
                      className={cn(
                        "rounded-full text-xs font-semibold tracking-wide transition-all",
                        statusFilter === status
                          ? "bg-white text-slate-900 shadow-sm"
                          : "text-slate-500 hover:text-slate-700"
                      )}
                    >
                      {statusLabel(status)}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-4 text-[11px] tracking-wide text-slate-500">
                  <div className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    <span>{totals.categorized} categorized</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                    <span>{totals.toReview} to review</span>
                  </div>
                </div>
              </div>

              {/* Separator */}
              <div className="h-px w-full bg-slate-100" />

              {/* Transaction Table */}
              <div className="rounded-2xl border border-slate-100 bg-slate-50/60 overflow-hidden">
                <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,0.9fr)_minmax(0,0.6fr)_minmax(0,0.6fr)_80px] gap-4 px-4 pt-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                  <div>Date & description</div>
                  <div>Payee</div>
                  <div>Category</div>
                  <div className="text-right">Amount</div>
                  <div className="text-right">Status</div>
                </div>
                <div className="h-px w-full bg-slate-100" />

                <div className="max-h-[400px] overflow-auto divide-y divide-slate-100 bg-white">
                  {filteredTransactions.map((tx) => (
                    <button
                      key={tx.id}
                      onClick={() => handleOpenDrawer(tx)}
                      className={cn(
                        "grid w-full grid-cols-[minmax(0,1.4fr)_minmax(0,0.9fr)_minmax(0,0.6fr)_minmax(0,0.6fr)_80px] gap-4 px-4 py-3 text-left",
                        "hover:bg-slate-50/80 transition-colors",
                        selectedTxId === tx.id && "bg-slate-50"
                      )}
                    >
                      {/* Date & Description */}
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold tracking-tight text-slate-900">
                            {new Date(tx.date).toLocaleDateString("en-CA", { month: "short", day: "2-digit" })}
                          </span>
                          {tx.hasAnomaly && (
                            <span className="h-5 rounded-full bg-red-50 px-2 text-[10px] font-bold text-rose-700 border border-rose-100 flex items-center">
                              Review
                            </span>
                          )}
                        </div>
                        <div className="line-clamp-1 text-[13px] font-bold tracking-tight text-slate-900">
                          {tx.description}
                        </div>
                        {tx.importRuleHint && (
                          <div className="text-[11px] text-slate-500">{tx.importRuleHint}</div>
                        )}
                      </div>

                      {/* Payee */}
                      <div className="flex flex-col justify-center gap-0.5">
                        <div className="text-[13px] font-semibold tracking-tight text-slate-900">{tx.payee}</div>
                        <div className="text-[11px] text-slate-500">Imported</div>
                      </div>

                      {/* Category */}
                      <div className="flex flex-col justify-center gap-0.5">
                        <div className="text-[13px] tracking-tight text-slate-900">
                          {tx.category || "Uncategorized"}
                        </div>
                        <div className="text-[11px] text-slate-500">Click to edit</div>
                      </div>

                      {/* Amount */}
                      <div className="flex flex-col items-end justify-center">
                        <div
                          className={cn(
                            "text-[13px] font-bold tracking-tight",
                            tx.direction === "in" ? "text-emerald-600" : "text-rose-600"
                          )}
                        >
                          {tx.direction === "in" ? "+" : "-"}
                          {formatCurrency(tx.amount, tx.currency)}
                        </div>
                        <div className="text-[11px] text-slate-500">{tx.currency}</div>
                      </div>

                      {/* Status */}
                      <div className="flex items-center justify-end gap-1">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide border",
                            tx.status === "for_review" && "border-amber-400 text-amber-700 bg-amber-50",
                            tx.status === "categorized" && "border-emerald-500 bg-emerald-50 text-emerald-700",
                            tx.status === "excluded" && "border-slate-300 bg-slate-50 text-slate-600"
                          )}
                        >
                          {statusLabel(tx.status)}
                        </span>
                        <ChevronRight className="h-4 w-4 text-slate-400" />
                      </div>
                    </button>
                  ))}

                  {filteredTransactions.length === 0 && (
                    <div className="px-6 py-12 text-center text-sm text-slate-500">
                      No transactions match this filter.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right Sidebar */}
          <div className="flex flex-col gap-6">
            {/* Bank Guardian Companion */}
            <div className="relative rounded-[1.5rem] border border-slate-100 bg-white/50 p-5 shadow-sm backdrop-blur-md shadow-[0_0_40px_-10px_rgba(99,102,241,0.12)]">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                    Bank Guardian
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-emerald-500" />
                    <p className="text-xs text-slate-600">
                      {totals.toReview === 0
                        ? "Everything reconciled for this account. Keep up the streak."
                        : `${totals.toReview} transaction${totals.toReview > 1 ? "s" : ""} waiting to be matched or categorized.`}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col items-end text-right">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Money in / out</div>
                  <div className="mt-1 flex items-center gap-3 text-xs">
                    <div className="flex items-center gap-1 text-emerald-600">
                      <ArrowDownToLine className="h-3.5 w-3.5" />
                      <span>{formatCurrency(totals.moneyIn, activeAccount?.currency || "CAD")}</span>
                    </div>
                    <div className="flex items-center gap-1 text-rose-600">
                      <ArrowUpToLine className="h-3.5 w-3.5" />
                      <span>{formatCurrency(totals.moneyOut, activeAccount?.currency || "CAD")}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="h-px w-full bg-slate-100 my-4" />

              <div className="grid grid-cols-2 gap-4 text-[11px] text-slate-600">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Wallet className="h-3.5 w-3.5 text-slate-500" />
                    <span className="uppercase tracking-[0.18em] text-slate-500">Account</span>
                  </div>
                  <div className="text-[13px] font-bold text-slate-900">
                    {activeAccount?.name || "None selected"}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {activeAccount?.institution} · ··{activeAccount?.last4}
                  </div>
                </div>
                <div className="space-y-1.5 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Settings2 className="h-3.5 w-3.5 text-slate-500" />
                    <span className="uppercase tracking-[0.18em] text-slate-500">Reconciliation</span>
                  </div>
                  <div className="flex items-center justify-end gap-2 text-[13px]">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                      {totals.categorized} ready
                    </span>
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                      {totals.toReview} to review
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500">Sync {activeAccount?.lastSync}</div>
                </div>
              </div>
            </div>

            {/* Account Activity Card */}
            <div className="rounded-[1.5rem] border border-slate-200 bg-white shadow-sm p-5">
              <div className="flex items-center justify-between gap-2 mb-4">
                <div>
                  <h4 className="text-sm font-bold text-slate-900">Account activity</h4>
                  <p className="text-xs text-slate-500">Snapshot for the last 7 days on this account.</p>
                </div>
                <button className="h-8 w-8 rounded-full hover:bg-slate-50 flex items-center justify-center">
                  <Shuffle className="h-4 w-4 text-slate-500" />
                </button>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 mb-4">
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-3 py-3">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <div className="text-[10px] uppercase tracking-[0.16em] text-emerald-700">Money in</div>
                      <div className="text-[16px] font-bold text-emerald-900">
                        {formatCurrency(totals.moneyIn, activeAccount?.currency || "CAD")}
                      </div>
                    </div>
                    <ArrowDownToLine className="h-5 w-5 text-emerald-600" />
                  </div>
                </div>
                <div className="rounded-2xl border border-rose-100 bg-rose-50/80 px-3 py-3">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <div className="text-[10px] uppercase tracking-[0.16em] text-rose-700">Money out</div>
                      <div className="text-[16px] font-bold text-rose-900">
                        {formatCurrency(totals.moneyOut, activeAccount?.currency || "CAD")}
                      </div>
                    </div>
                    <ArrowUpToLine className="h-5 w-5 text-rose-600" />
                  </div>
                </div>
              </div>

              <div className="h-px w-full bg-slate-100 mb-4" />

              <div className="grid gap-3 text-[11px] text-slate-600">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Receipt className="h-3.5 w-3.5 text-slate-500" />
                    <span>Transactions to review</span>
                  </div>
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                    {totals.toReview} items
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CreditCard className="h-3.5 w-3.5 text-slate-500" />
                    <span>Ready to post to ledger</span>
                  </div>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                    {totals.categorized} items
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Slide-out Drawer */}
        <AnimatePresence>
          {selectedTx && (
            <motion.div
              className="fixed inset-0 z-40 flex justify-end bg-slate-900/20 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedTxId(null)}
            >
              <motion.div
                className="h-full w-full max-w-md bg-white shadow-2xl"
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring", damping: 30, stiffness: 300 }}
                onClick={(e) => e.stopPropagation()}
              >
                {/* Drawer Header */}
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                  <div className="space-y-1">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Transaction</div>
                    <div className="text-sm font-bold text-slate-900 line-clamp-1">
                      {selectedTx.description}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {new Date(selectedTx.date).toLocaleDateString("en-CA", {
                        year: "numeric",
                        month: "short",
                        day: "2-digit",
                      })}{" "}
                      · {selectedTx.payee}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div
                      className={cn(
                        "text-[15px] font-bold",
                        selectedTx.direction === "in" ? "text-emerald-600" : "text-rose-600"
                      )}
                    >
                      {selectedTx.direction === "in" ? "+" : "-"}
                      {formatCurrency(selectedTx.amount, selectedTx.currency)}
                    </div>
                    <button
                      className="h-8 w-8 rounded-full border border-slate-200 flex items-center justify-center hover:bg-slate-50"
                      onClick={() => setSelectedTxId(null)}
                    >
                      <XCircle className="h-4 w-4 text-slate-500" />
                    </button>
                  </div>
                </div>

                {/* Drawer Content */}
                <div className="px-5 py-4 space-y-4">
                  {/* Mode Tabs */}
                  <div className="grid h-9 w-full grid-cols-3 rounded-full bg-slate-100 p-1">
                    {(["match", "categorize", "tax"] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setDrawerForm((prev) => ({ ...prev, mode }))}
                        className={cn(
                          "rounded-full text-xs font-semibold capitalize transition-all",
                          drawerForm.mode === mode
                            ? "bg-white text-slate-900 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                        )}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>

                  {/* Match Tab */}
                  {drawerForm.mode === "match" && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                          Suggested matches
                        </span>
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                          {selectedTx.suggestedMatches?.length ? "Auto-match ready" : "No suggestions"}
                        </span>
                      </div>
                      {(!selectedTx.suggestedMatches || selectedTx.suggestedMatches.length === 0) && (
                        <div className="rounded-2xl border border-dashed border-slate-200 px-3 py-4 text-center text-[11px] text-slate-500">
                          No suggested matches. You can still categorize this transaction manually.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Categorize Tab */}
                  {drawerForm.mode === "categorize" && (
                    <div className="space-y-4">
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <label className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                            Category
                          </label>
                          <a href="/categories/" className="text-[11px] text-slate-400 hover:underline">
                            Manage
                          </a>
                        </div>
                        <select
                          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-slate-900"
                          value={drawerForm.category ?? ""}
                          onChange={(e) => setDrawerForm((prev) => ({ ...prev, category: e.target.value }))}
                        >
                          <option value="">Select category</option>
                          {(selectedTx.direction === "out" ? expenseCategories : incomeCategories).map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                          Memo
                        </label>
                        <textarea
                          rows={3}
                          className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-slate-900"
                          value={drawerForm.memo ?? ""}
                          onChange={(e) => setDrawerForm((prev) => ({ ...prev, memo: e.target.value }))}
                          placeholder="Add context for future you or your accountant."
                        />
                      </div>
                    </div>
                  )}

                  {/* Tax Tab */}
                  {drawerForm.mode === "tax" && (
                    <div className="space-y-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                          Tax treatment
                        </label>
                        <select
                          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-slate-900"
                          value={drawerForm.taxCode ?? ""}
                          onChange={(e) => setDrawerForm((prev) => ({ ...prev, taxCode: e.target.value }))}
                        >
                          <option value="">Select tax code</option>
                          {taxCodes.map((code) => (
                            <option key={code.id} value={code.id}>{code.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="rounded-2xl bg-slate-50 px-3 py-3 text-[11px] text-slate-600">
                        This transaction will be sent to the Tax Engine with the selected tax code.
                        Tax-exempt or out-of-scope items will not affect GST/HST line 101.
                      </div>
                    </div>
                  )}
                </div>

                {/* Drawer Footer */}
                <div className="absolute bottom-0 left-0 right-0 border-t border-slate-100 bg-white px-5 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <button
                      className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                      onClick={() => setSelectedTxId(null)}
                    >
                      Cancel
                    </button>
                    <div className="flex items-center gap-2">
                      <button className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                        Exclude from books
                      </button>
                      <button
                        className="rounded-full bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800"
                        onClick={handleApply}
                      >
                        {drawerForm.mode === "match" ? "Match & save" : "Save to books"}
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
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
