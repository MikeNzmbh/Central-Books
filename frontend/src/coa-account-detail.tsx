import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";

type IconProps = React.SVGProps<SVGSVGElement>;
const stroke = {
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

const BanknoteIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <rect {...stroke} x="3" y="6" width="18" height="12" rx="2" />
    <circle {...stroke} cx="12" cy="12" r="3" />
    <path {...stroke} d="M6 12h.01M18 12h.01" />
  </svg>
);
const PencilIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M12 20h9M16.5 3.5l4 4L7 21H3v-4z" />
  </svg>
);
const PlusCircleIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <circle {...stroke} cx="12" cy="12" r="10" />
    <path {...stroke} d="M12 8v8M8 12h8" />
  </svg>
);
const TrashIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6" />
  </svg>
);
const FilterIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M4 6h16M7 12h10M10 18h4" />
  </svg>
);
const SortIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M11 5l-4 4 4 4M7 9h10M13 19l4-4-4-4M17 15H7" />
  </svg>
);
const InfoIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <circle {...stroke} cx="12" cy="12" r="10" />
    <path {...stroke} d="M12 16v-4M12 8h.01" />
  </svg>
);
const AlertIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="m10.3 3.1-8.5 14.9A1 1 0 0 0 3.6 20h16.8a1 1 0 0 0 .8-1.5L12.7 3.1a1 1 0 0 0-1.7 0z" />
    <path {...stroke} d="M12 9v4M12 17h.01" />
  </svg>
);
const SearchIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <circle {...stroke} cx="11" cy="11" r="7" />
    <line {...stroke} x1="16" y1="16" x2="21" y2="21" />
  </svg>
);
const StarIcon = ({ filled = true, ...props }: IconProps & { filled?: boolean }) => (
  <svg viewBox="0 0 24 24" {...props}>
    {filled ? (
      <path d="M12 17.3l-4.2 2.4 1-4.7-3.6-3.3 4.8-.4L12 7l2 4.3 4.8.4-3.6 3.3 1 4.7z" fill="currentColor" />
    ) : (
      <path {...stroke} fill="none" d="M12 17.3l-4.2 2.4 1-4.7-3.6-3.3 4.8-.4L12 7l2 4.3 4.8.4-3.6 3.3 1 4.7z" />
    )}
  </svg>
);
const ArrowDownRightIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M7 7l10 10M7 17V7h10" />
  </svg>
);
const ArrowUpRightIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M7 17L17 7M7 7h10v10" />
  </svg>
);
const LinkIcon = (props: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <path {...stroke} d="M10 13a5 5 0 0 0 7 7l2-2a5 5 0 0 0 0-7" />
    <path {...stroke} d="M14 11a5 5 0 0 0-7-7l-2 2a5 5 0 0 0 0 7" />
    <path {...stroke} d="M8.5 15.5l7-7" />
  </svg>
);

export type BankCoaViewProps = {
  accountId: number;
  name: string;
  code: string;
  type: string;
  detailType: string;
  currency: string;
  isFavorite: boolean;
  isBankAccount: boolean;
  bankLast4?: string | null;
  bankDisplayName?: string | null;
  balance: number;
  bankFeedBalance: number;
  periodDeposits: number;
  periodWithdrawals: number;
  periodCount: number;
  lastReconciledOn?: string | null;
  unreconciledCount?: number | null;
  editFormUrl: string;
  linkBankFeedUrl?: string;
  apiActivityUrl?: string;
  apiLedgerUrl?: string;
  apiToggleFavoriteUrl?: string;
  apiCreateManualTxUrl?: string;
  apiTransactionsUrl?: string;
};

type ActivityRow = {
  id: number | string;
  date: string;
  description: string;
  source: "Invoice" | "Expense" | "Manual" | "Other";
  amount: number;
  runningBalance: number;
};

type BankTransaction = {
  id: string;
  date: string;
  payee: string;
  type: "Deposit" | "Withdrawal";
  category: string;
  memo: string;
  statusCode: string;
  statusLabel: string;
  reconciliationStatus?: string | null;
  amount: number;
};

const fallbackTransactions: BankTransaction[] = [
  {
    id: "TX-10045",
    date: "2025-11-16",
    payee: "Stripe Payout",
    type: "Deposit",
    category: "Sales",
    memo: "Online sales batch",
    statusCode: "CLEARED",
    statusLabel: "Cleared",
    amount: 1289.45,
  },
  {
    id: "TX-10046",
    date: "2025-11-16",
    payee: "Uber",
    type: "Withdrawal",
    category: "Travel",
    memo: "Client meeting downtown",
    statusCode: "UNRECONCILED",
    statusLabel: "Unreconciled",
    amount: -24.9,
  },
  {
    id: "TX-10047",
    date: "2025-11-15",
    payee: "AWS",
    type: "Withdrawal",
    category: "Hosting",
    memo: "Central-Books infra",
    statusCode: "CLEARED",
    statusLabel: "Cleared",
    amount: -210,
  },
  {
    id: "TX-10048",
    date: "2025-11-14",
    payee: "Founders Coffee",
    type: "Withdrawal",
    category: "Meals",
    memo: "Sprint planning",
    statusCode: "UNRECONCILED",
    statusLabel: "Unreconciled",
    amount: -18.5,
  },
];

const randomTxId = () => `temp-${Math.random().toString(36).slice(2, 10)}`;

const normalizeApiTransaction = (raw: any): BankTransaction => {
  const amount = Number(raw?.amount ?? 0);
  const type: BankTransaction["type"] = amount >= 0 ? "Deposit" : "Withdrawal";
  const recoStatus = String(raw?.reconciliation_status || "").toLowerCase();
  const statusCode = recoStatus ? (recoStatus === "reconciled" ? "RECONCILED" : "UNRECONCILED") : String(raw?.status || "").toUpperCase();
  const statusLabel = recoStatus
    ? (recoStatus === "reconciled" ? "Reconciled" : "Unreconciled")
    : String(raw?.status_label || raw?.status || statusCode || "Status");
  const payee = String(raw?.counterparty || raw?.description || raw?.memo || type);
  return {
    id: String(raw?.id ?? raw?.external_id ?? randomTxId()),
    date: String(raw?.date || ""),
    payee,
    type,
    category: String(raw?.category || (type === "Deposit" ? "Income" : "Expense")),
    memo: String(raw?.memo || raw?.description || ""),
    statusCode,
    statusLabel,
    reconciliationStatus: recoStatus || null,
    amount,
  };
};

const formatMoney = (value: number, currency: string) =>
  new Intl.NumberFormat("en-CA", { style: "currency", currency }).format(value);

const isArchivedStatus = (statusCode: string) => {
  const normalized = (statusCode || "").toUpperCase();
  return normalized === "EXCLUDED" || normalized === "ARCHIVED";
};

const statusTone = (statusCode: string) => {
  const normalized = (statusCode || "").toUpperCase();
  if (normalized === "MATCHED_SINGLE" || normalized === "MATCHED_MULTI" || normalized === "CLEARED") {
    return "bg-emerald-50 text-emerald-700 ring-emerald-100";
  }
  if (normalized === "NEW" || normalized === "UNRECONCILED" || normalized === "PARTIAL") {
    return "bg-amber-50 text-amber-700 ring-amber-100";
  }
  if (normalized === "EXCLUDED" || normalized === "ARCHIVED") {
    return "bg-slate-100 text-slate-500 ring-slate-200";
  }
  return "bg-slate-50 text-slate-700 ring-slate-100";
};

const BankCoaViewPage: React.FC<BankCoaViewProps> = (props) => {
  const [typeFilter, setTypeFilter] = useState("All movement");
  const [statusFilter, setStatusFilter] = useState("Active only");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"transactions" | "reconciliation" | "activity">("transactions");
  const [isFavorite, setIsFavorite] = useState(props.isFavorite);
  const [isCreatingTx, setIsCreatingTx] = useState(false);
  const [activityRows, setActivityRows] = useState<ActivityRow[]>([]);
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(false);

  useEffect(() => {
    if (!props.apiTransactionsUrl) {
      // No bank connection - show empty state
      setTransactions([]);
      setIsLoadingTransactions(false);
      return;
    }
    let aborted = false;
    setIsLoadingTransactions(true);
    fetch(props.apiTransactionsUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to load transactions");
        }
        return res.json();
      })
      .then((data) => {
        if (aborted) return;
        const rows = Array.isArray(data?.transactions)
          ? data.transactions.map((row: any) => normalizeApiTransaction(row))
          : [];
        // Always use real data only - no fallback to demo transactions
        setTransactions(rows);
      })
      .catch((error) => {
        console.error("Failed to load bank transactions:", error);
        if (!aborted) {
          // On error, show empty state rather than demo data
          setTransactions([]);
        }
      })
      .finally(() => {
        if (!aborted) {
          setIsLoadingTransactions(false);
        }
      });
    return () => {
      aborted = true;
    };
  }, [props.apiTransactionsUrl]);

  useEffect(() => {
    if (!props.apiActivityUrl) {
      const fallbackSource = transactions.length ? transactions : fallbackTransactions;
      setActivityRows(
        fallbackSource.map((tx, index) => ({
          id: tx.id,
          date: tx.date,
          description: tx.memo || tx.payee,
          source: tx.type === "Deposit" ? "Invoice" : "Expense",
          amount: tx.amount,
          runningBalance: props.balance - index * 10,
        }))
      );
      return;
    }

    setIsLoadingActivity(true);
    fetch(props.apiActivityUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data.rows)) {
          setActivityRows(
            data.rows.map((row: any, idx: number) => ({
              id: row.id ?? idx,
              date: String(row.date ?? ""),
              description: String(row.description ?? ""),
              source: (row.source as ActivityRow["source"]) || "Other",
              amount: Number(row.amount ?? 0),
              runningBalance: Number(row.running_balance ?? props.balance),
            }))
          );
        }
      })
      .catch(() => setActivityRows([]))
      .finally(() => setIsLoadingActivity(false));
  }, [props.apiActivityUrl, props.balance, transactions.length]);

  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      if (typeFilter === "Deposits" && tx.type !== "Deposit") return false;
      if (typeFilter === "Withdrawals" && tx.type !== "Withdrawal") return false;
      if (search) {
        const q = search.toLowerCase();
        const haystack = `${tx.payee} ${tx.memo} ${tx.category}`.toLowerCase();
        if (!haystack.includes(q)) {
          return false;
        }
      }
      if (statusFilter === "Active only" && isArchivedStatus(tx.statusCode)) return false;
      if (statusFilter === "Archived only" && !isArchivedStatus(tx.statusCode)) return false;
      return true;
    });
  }, [transactions, typeFilter, search, statusFilter]);

  const handleToggleFavorite = () => {
    const next = !isFavorite;
    setIsFavorite(next);
    if (!props.apiToggleFavoriteUrl) return;
    fetch(props.apiToggleFavoriteUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ account_id: props.accountId, favorite: next }),
    }).catch(() => setIsFavorite((prev) => !prev));
  };

  const resetFilters = () => {
    setTypeFilter("All movement");
    setStatusFilter("Active only");
    setSearch("");
  };

  const activityFallbackSource = transactions.length ? transactions : fallbackTransactions;
  const activityForDisplay = activityRows.length
    ? activityRows
    : activityFallbackSource.map((tx, index) => ({
      id: tx.id,
      date: tx.date,
      description: tx.memo || tx.payee,
      source: tx.type === "Deposit" ? "Invoice" : "Expense",
      amount: tx.amount,
      runningBalance: props.balance - index * 10,
    }));

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-slate-50 to-slate-100 text-slate-900">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:px-8 lg:py-8">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-slate-500 shadow-sm ring-1 ring-slate-200">
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-white">
                <BanknoteIcon className="h-3.5 w-3.5" />
              </span>
              <span>Chart of Accounts · Bank account</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{props.name || "Bank account"}</h1>
            <p className="max-w-xl text-sm text-slate-500">
              View this bank account in context of your Chart of Accounts. Edit the account properties and work with every transaction flowing through it without leaving the COA.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50">
              <InfoIcon className="h-4 w-4" />
              Reconciliation rules
            </button>
            <button
              onClick={() => setIsCreatingTx(true)}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800"
            >
              <PlusCircleIcon className="h-4 w-4" />
              New transaction
            </button>
          </div>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,2fr)]">
          <div className="space-y-4">
            <div className="rounded-3xl border border-slate-200 bg-white/90 shadow-sm">
              <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-5 py-4">
                <div>
                  <div className="flex items-center gap-2 text-base font-semibold">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-white">
                      <BanknoteIcon className="h-4 w-4" />
                    </span>
                    {props.name || "Bank account"}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Code <span className="font-mono">{props.code || "—"}</span> · Type {props.type || "Bank"} · Status: Active
                  </div>
                </div>
                <div className="inline-flex items-center gap-2">
                  <button
                    onClick={handleToggleFavorite}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  >
                    <StarIcon className={`h-4 w-4 ${isFavorite ? "text-amber-400" : "text-slate-300"}`} filled={isFavorite} />
                  </button>
                  {props.editFormUrl ? (
                    <a
                      href={props.editFormUrl}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                    >
                      <PencilIcon className="h-4 w-4" />
                    </a>
                  ) : null}
                </div>
              </div>
              <div className="space-y-4 px-5 py-4 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Ledger balance</div>
                    <div className="mt-1 text-lg font-semibold text-slate-900 font-mono-soft">{formatMoney(props.balance, props.currency)}</div>
                    <div className="mt-1 flex items-center gap-1 text-[11px] text-emerald-600">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      In sync with last close
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Bank feed balance</div>
                    <div className="mt-1 text-lg font-semibold text-slate-900 font-mono-soft">{formatMoney(props.bankFeedBalance, props.currency)}</div>
                    {(() => {
                      const difference = Math.abs(props.balance - props.bankFeedBalance);
                      const unreconciledText = props.unreconciledCount
                        ? `${props.unreconciledCount} item${props.unreconciledCount > 1 ? 's' : ''} to reconcile`
                        : 'No items to reconcile';
                      if (difference < 0.01) {
                        return (
                          <div className="mt-1 flex items-center gap-1 text-[11px] text-emerald-600">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            In sync with ledger
                          </div>
                        );
                      }
                      return (
                        <div className="mt-1 flex items-center gap-1 text-[11px] text-amber-600">
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                          Off by <span className="font-mono-soft">{formatMoney(difference, props.currency)}</span> · {unreconciledText}
                        </div>
                      );
                    })()}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-600">Bank connection</span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 ring-1 ring-emerald-100">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Connected
                      </span>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                      <div className="font-mono text-[11px] text-slate-500">**** {props.bankLast4 || "0000"}</div>
                      <div className="mt-0.5 text-[11px] text-slate-500">
                        {props.bankDisplayName || props.name || "Linked account"}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <span className="text-slate-600">Default posting rules</span>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
                      <div>Deposits → 4000 · Sales</div>
                      <div>Fees → 6100 · Bank Fees</div>
                      <div>Transfers → 1999 · Clearing</div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-b-3xl border-t border-slate-200 bg-slate-50 px-4 py-3 text-[11px] text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <AlertIcon className="h-3.5 w-3.5 text-amber-500" />
                  <span className="font-mono-soft">{props.unreconciledCount || 0}</span> unreconciled items since last close.
                </span>
                <button className="rounded-full border border-slate-300 bg-white px-3 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50">
                  Open reconciliation
                </button>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white/90 shadow-sm">
              <div className="border-b border-slate-200 px-5 py-4">
                <div className="text-sm font-semibold">Account metadata</div>
                <div className="mt-1 text-xs text-slate-500">
                  Change how this bank account appears in your COA. All edits are tracked in the audit log.
                </div>
              </div>
              <div className="space-y-3 px-5 py-4 text-xs">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-medium text-slate-700">Account name</label>
                  <input className="h-8 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-slate-900" defaultValue={props.name} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-medium text-slate-700">Code</label>
                    <input className="h-8 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 font-mono" defaultValue={props.code} />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-medium text-slate-700">Display group</label>
                    <input className="h-8 w-full rounded-xl border border-slate-200 bg-slate-50 px-3" defaultValue="Operating accounts" />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-medium text-slate-700">Description</label>
                  <input className="h-8 w-full rounded-xl border border-slate-200 bg-slate-50 px-3" defaultValue="Main CAD operating account connected to CentralBank feed." />
                </div>
              </div>
              <div className="flex items-center justify-between rounded-b-3xl border-t border-slate-200 bg-slate-50 px-4 py-3 text-[11px]">
                <button className="inline-flex items-center gap-1 text-rose-500 hover:text-rose-600">
                  <TrashIcon className="h-3.5 w-3.5" />
                  Archive account
                </button>
                <button className="rounded-full bg-slate-900 px-3 py-1 text-white">Save changes</button>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-slate-200 bg-white/90 shadow-sm">
              <div className="border-b border-slate-200 px-5 py-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-semibold">Transactions</div>
                    <div className="text-xs text-slate-500">Create, edit, or delete entries that hit this bank account directly from the COA.</div>
                  </div>
                  <div className="hidden items-center gap-2 rounded-full bg-slate-50 px-3 py-1 text-[11px] text-slate-500 ring-1 ring-slate-200 md:inline-flex">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Live ledger link active
                  </div>
                </div>
              </div>
              <div className="space-y-3 px-5 py-4">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div className="flex flex-1 items-center gap-2">
                    <div className="relative flex-1">
                      <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                      <input
                        className="h-8 w-full rounded-full border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-900"
                        placeholder="Search payee, memo, category"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </div>
                    <button className="hidden h-8 items-center gap-1 rounded-full border border-slate-200 bg-white px-3 text-[11px] text-slate-700 hover:bg-slate-50 md:inline-flex">
                      <FilterIcon className="h-3.5 w-3.5" />
                      Filters
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 hover:bg-slate-50">
                      <SortIcon className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setIsCreatingTx(true)}
                      className="inline-flex h-8 items-center gap-1 rounded-full bg-slate-900 px-3 text-[11px] font-semibold text-white hover:bg-slate-800"
                    >
                      <PlusCircleIcon className="h-3.5 w-3.5" />
                      New transaction
                    </button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-[11px] text-slate-600">
                  <div className="flex flex-wrap gap-1 rounded-full bg-slate-50 p-1">
                    {["All movement", "Deposits", "Withdrawals"].map((label) => (
                      <button
                        key={label}
                        onClick={() => setTypeFilter(label)}
                        className={`rounded-full px-2.5 py-1 font-medium ${typeFilter === label ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                          }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1 rounded-full bg-slate-50 p-1">
                    {["Active only", "Archived only", "Show all"].map((label) => (
                      <button
                        key={label}
                        onClick={() => setStatusFilter(label)}
                        className={`rounded-full px-2.5 py-1 font-medium ${statusFilter === label ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                          }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <button onClick={resetFilters} className="rounded-full border border-slate-200 px-3 py-1 text-[11px] text-slate-600 hover:bg-slate-50">Reset</button>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50">
                  <table className="min-w-full text-xs">
                    <thead className="bg-slate-50/90">
                      <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                        <th className="px-3 py-2">Date</th>
                        <th className="px-3 py-2">Payee / Source</th>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2">Category</th>
                        <th className="px-3 py-2">Memo</th>
                        <th className="px-3 py-2 text-right">Amount</th>
                        <th className="px-3 py-2 text-right">Status</th>
                        <th className="px-3 py-2 text-right" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {isLoadingTransactions && (
                        <tr>
                          <td colSpan={8} className="px-4 py-6 text-center text-[11px] text-slate-500">
                            Loading transactions…
                          </td>
                        </tr>
                      )}
                      {!isLoadingTransactions && filteredTransactions.length === 0 && transactions.length === 0 && (
                        <tr>
                          <td colSpan={8} className="px-4 py-8 text-center">
                            <div className="mx-auto max-w-sm">
                              <div className="text-sm font-medium text-slate-900">No transactions yet</div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                When payments start hitting this account, they'll appear here.
                                {props.isBankAccount && (
                                  <span> Import a CSV from your bank or connect a bank feed to get started.</span>
                                )}
                              </div>
                              {props.linkBankFeedUrl && (
                                <div className="mt-3">
                                  <a
                                    href={props.linkBankFeedUrl}
                                    className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-slate-800"
                                  >
                                    <LinkIcon className="h-3.5 w-3.5" />
                                    Open bank feed
                                  </a>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                      {!isLoadingTransactions && filteredTransactions.length === 0 && transactions.length > 0 && (
                        <tr>
                          <td colSpan={8} className="px-4 py-6 text-center text-[11px] text-slate-500">
                            No transactions match your filters.
                          </td>
                        </tr>
                      )}
                      {!isLoadingTransactions &&
                        filteredTransactions.map((tx) => (
                          <tr key={tx.id} className="hover:bg-white">
                            <td className="px-3 py-2 font-mono text-[11px] text-slate-600">{tx.date}</td>
                            <td className="px-3 py-2 text-[11px] text-slate-900">
                              <div>{tx.payee}</div>
                              <div className="mt-0.5 font-mono text-[10px] text-slate-400">{tx.id}</div>
                            </td>
                            <td className="px-3 py-2 text-[11px] text-slate-700">{tx.type}</td>
                            <td className="px-3 py-2 text-[11px] text-slate-700">
                              <span className="inline-flex rounded-full bg-white px-2 py-0.5 text-[10px] ring-1 ring-slate-200">
                                {tx.category || "—"}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-[11px] text-slate-600">{tx.memo || "—"}</td>
                            <td className="px-3 py-2 text-right font-mono text-[11px]">
                              <span className={tx.amount < 0 ? "text-rose-500" : "text-emerald-600"}>{formatMoney(tx.amount, props.currency)}</span>
                            </td>
                            <td className="px-3 py-2 text-right">
                              <span className={`inline-flex items-center justify-end gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${statusTone(tx.statusCode)}`}>
                                {tx.statusLabel || tx.statusCode || "Status"}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right">
                              <div className="inline-flex items-center gap-1">
                                <button className="h-6 w-6 rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-700">
                                  <PencilIcon className="h-3.5 w-3.5" />
                                </button>
                                <button className="h-6 w-6 rounded-full text-rose-400 hover:bg-rose-50 hover:text-rose-600">
                                  <TrashIcon className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                  <div className="border-t border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
                    Showing <span className="font-mono-soft">{filteredTransactions.length}</span> of <span className="font-mono-soft">{transactions.length}</span> transactions.
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
                  <div className="font-medium text-slate-900">Recent changes & audit trail</div>
                  <div className="mt-2 space-y-2">
                    <div className="flex items-start gap-2 rounded-xl bg-white px-3 py-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      <div>
                        <div className="text-[11px]">You renamed this account from “CentralBank-1” to “{props.name}”.</div>
                        <div className="text-[10px] text-slate-400">Today · 14:22 · by you</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-2 rounded-xl bg-white px-3 py-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-sky-500" />
                      <div>
                        <div className="text-[11px]">AI suggested category “Travel” for Uber expense. You accepted.</div>
                        <div className="text-[10px] text-slate-400">Yesterday · Central-Books AI</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {tab !== "transactions" && (
              <div className={`rounded-3xl border ${tab === "reconciliation" ? "border-dashed" : "border-solid"} border-slate-200 bg-white/80 p-6 text-xs text-slate-500`}>
                {tab === "reconciliation" ? (
                  <p>This tab will hook into the reconciliation workspace. Provide matches and status here later.</p>
                ) : (
                  <div className="space-y-2">
                    <p>Ledger lines for this account will appear here.</p>
                    {props.apiLedgerUrl && (
                      <p className="text-[11px] text-slate-400">Endpoint wired: <code>{props.apiLedgerUrl}</code></p>
                    )}
                    {isLoadingActivity ? (
                      <p className="text-[11px] text-slate-400">Loading activity…</p>
                    ) : (
                      <div className="space-y-1">
                        {activityForDisplay.slice(0, 5).map((row) => (
                          <div key={row.id} className="rounded-xl bg-slate-50 px-3 py-2">
                            <div className="text-[11px] text-slate-500">{row.date}</div>
                            <div className="text-[11px] text-slate-900">{row.description || "Ledger entry"}</div>
                            <div className="text-[10px] text-slate-500">
                              {row.source} · <span className="font-mono-soft">{formatMoney(row.amount, props.currency)}</span> · Running <span className="font-mono-soft">{formatMoney(row.runningBalance, props.currency)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {isCreatingTx && (
          <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/40">
            <div className="flex h-full w-full max-w-md flex-col bg-white shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">New transaction</div>
                  <div className="text-sm font-semibold text-slate-900">Post a manual entry on this account</div>
                </div>
                <button
                  onClick={() => setIsCreatingTx(false)}
                  className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-50"
                >
                  Close
                </button>
              </div>
              <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-xs text-slate-700">
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Type</div>
                  <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1">
                    <button className="rounded-full bg-white px-3 py-1 text-[11px] font-medium text-slate-900 shadow-sm">Deposit</button>
                    <button className="rounded-full px-3 py-1 text-[11px] font-medium text-slate-500">Withdrawal</button>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <div className="mb-1 text-[11px] font-medium text-slate-500">Date</div>
                    <input type="date" className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800" />
                  </div>
                  <div>
                    <div className="mb-1 text-[11px] font-medium text-slate-500">Amount</div>
                    <div className="flex items-center gap-1">
                      <span className="rounded-2xl bg-slate-50 px-2 py-1 text-[11px] text-slate-500">{props.currency}</span>
                      <input type="number" className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800" placeholder="0.00" />
                    </div>
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Description</div>
                  <input type="text" className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800" placeholder="What is this transaction for?" />
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Memo (optional)</div>
                  <textarea className="min-h-[70px] w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800" placeholder="Internal note that only you will see" />
                </div>
                {props.apiCreateManualTxUrl && (
                  <div className="text-[11px] text-slate-400">Will POST to <code>{props.apiCreateManualTxUrl}</code> once wired.</div>
                )}
              </div>
              <div className="border-t border-slate-100 px-5 py-3 text-right">
                <button
                  onClick={() => setIsCreatingTx(false)}
                  className="mr-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-4 py-1.5 text-[11px] font-semibold text-white shadow-sm hover:bg-black">
                  Save transaction
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BankCoaViewPage;
export const BankCoaViewPageGlass = BankCoaViewPage;
export const BankCoaViewPageCompact = BankCoaViewPage;

function bootstrap() {
  const el = document.getElementById("coa-account-root");
  if (!el) return;
  const d = el.dataset || {};
  const props: BankCoaViewProps = {
    accountId: Number(d.accountId || "0"),
    name: d.name || "",
    code: d.code || "",
    type: d.type || "Assets",
    detailType: d.detailType || "Operating bank account",
    currency: d.currency || "USD",
    isFavorite: d.isFavorite === "true",
    isBankAccount: d.isBankAccount === "true",
    bankLast4: d.bankLast4 || null,
    bankDisplayName: d.bankDisplayName || null,
    balance: Number(d.balance || "0"),
    bankFeedBalance: Number(d.bankFeedBalance || "0"),
    periodDeposits: Number(d.periodDeposits || "0"),
    periodWithdrawals: Number(d.periodWithdrawals || "0"),
    periodCount: Number(d.periodCount || "0"),
    lastReconciledOn: d.lastReconciledOn || null,
    unreconciledCount: d.unreconciledCount ? Number(d.unreconciledCount) : null,
    editFormUrl: d.editFormUrl || "",
    linkBankFeedUrl: d.linkBankFeedUrl || undefined,
    apiActivityUrl: d.apiActivityUrl || undefined,
    apiLedgerUrl: d.apiLedgerUrl || undefined,
    apiToggleFavoriteUrl: d.apiToggleFavoriteUrl || undefined,
    apiCreateManualTxUrl: d.apiCreateManualTxUrl || undefined,
    apiTransactionsUrl: d.apiTransactionsUrl || undefined,
  };

  const root = createRoot(el);
  root.render(
    <React.StrictMode>
      <BankCoaViewPage {...props} />
    </React.StrictMode>
  );
}

bootstrap();
