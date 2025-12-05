import React, { useEffect, useState } from "react";
import CompanionStrip from "./companion/CompanionStrip";

const BANK_GRADIENTS: Record<string, string> = {
  rbc: "from-indigo-500 to-indigo-700",
  td: "from-teal-500 to-teal-700",
  bmo: "from-sky-500 to-sky-700",
  scotia: "from-emerald-500 to-emerald-700",
  wise: "from-lime-500 to-lime-700",
  default: "from-slate-600 to-slate-800",
};

function getBankGradient(name: string) {
  const key = (name || "").toLowerCase();
  if (key.includes("rbc")) return BANK_GRADIENTS.rbc;
  if (key.includes("td")) return BANK_GRADIENTS.td;
  if (key.includes("bmo")) return BANK_GRADIENTS.bmo;
  if (key.includes("scotia")) return BANK_GRADIENTS.scotia;
  if (key.includes("wise")) return BANK_GRADIENTS.wise;
  return BANK_GRADIENTS.default;
}

function formatMoney(value: number | string, currency?: string) {
  const num = typeof value === "number" ? value : Number(value || 0);
  const sign = num < 0 ? "-" : "";
  const abs = Math.abs(num).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}$${abs}`;
}

function formatTimeSince(dateStr: string | null): string {
  if (!dateStr) return "Never synced";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? "" : "s"} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
  return date.toLocaleDateString();
}

type FeedStatus = "OK" | "ACTION_NEEDED" | "DISCONNECTED";

interface BankAccount {
  id: number;
  name: string;
  last4: string;
  bank: string;
  currency: string;
  ledgerLinked: boolean;
  ledgerBalance: string;
  feedStatus: FeedStatus;
  lastImportAt: string | null;
  newCount: number;
  createdCount: number;
  matchedCount: number;
  reviewUrl: string;
  importUrl: string;
}

interface OverviewSummary {
  new_to_review: number;
  created_from_feed: number;
  matched_to_invoices: number;
  reconciled_percent: number;
}

interface BankingAccountsAndFeedPageProps {
  overviewUrl: string;
  feedUrl: string;
  importUrl: string;
}

/* ──────────────────────────────────────────────────
   Circular Progress Ring Component
   ────────────────────────────────────────────────── */
const CircularProgress: React.FC<{ percent: number; size?: number }> = ({ percent, size = 120 }) => {
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#10b981"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{percent}%</span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wide">reconciled</span>
      </div>
    </div>
  );
};

/* ──────────────────────────────────────────────────
   Account Card Component (Redesigned)
   ────────────────────────────────────────────────── */
const AccountCard: React.FC<{ account: BankAccount }> = ({ account }) => {
  const gradient = getBankGradient(account.bank || account.name);
  const initial = (account.bank || account.name || "?").trim().charAt(0).toUpperCase();
  const isHealthy = account.feedStatus === "OK";
  const hasAction = account.feedStatus === "ACTION_NEEDED";

  return (
    <div
      className={`relative rounded-2xl border bg-white/80 backdrop-blur-sm p-4 shadow-lg transition-all duration-200 hover:shadow-xl ${isHealthy
          ? "border-emerald-100 ring-2 ring-emerald-50"
          : hasAction
            ? "border-amber-100 ring-2 ring-amber-50"
            : "border-slate-100"
        }`}
    >
      <div className="flex gap-4">
        {/* Bank Logo */}
        <div
          className={`flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${gradient} text-lg font-bold text-white shadow-md`}
        >
          {initial}
        </div>

        {/* Account Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-slate-900 truncate">{account.name}</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                ••••{account.last4 || "0000"}
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-lg font-bold text-slate-900">
                {formatMoney(account.ledgerBalance)}
              </p>
              <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                {account.currency || "CAD"}
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-3 flex items-center justify-between">
            <p className="text-[11px] text-slate-400">
              Last sync: {formatTimeSince(account.lastImportAt)}
            </p>
            <div className="flex gap-1.5">
              {account.newCount > 0 && (
                <span className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-100">
                  {account.newCount} New
                </span>
              )}
              {(account.createdCount + account.matchedCount) > 0 && (
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-100">
                  {account.createdCount + account.matchedCount} Posted
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-3 pt-3 border-t border-slate-100 flex gap-2">
        <a
          href={account.importUrl}
          className="flex-1 inline-flex items-center justify-center rounded-lg bg-slate-50 px-3 py-1.5 text-[11px] font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100 transition-colors"
        >
          Import CSV
        </a>
        <a
          href={account.reviewUrl}
          className="flex-1 inline-flex items-center justify-center rounded-lg bg-emerald-600 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
        >
          Review
        </a>
      </div>
    </div>
  );
};

/* ──────────────────────────────────────────────────
   Feed Overview Panel (Redesigned)
   ────────────────────────────────────────────────── */
const FeedOverviewPanel: React.FC<{ summary: OverviewSummary | null }> = ({ summary }) => {
  const reconciledPercent = summary?.reconciled_percent ?? 0;
  const newToReview = summary?.new_to_review ?? 0;
  const createdFromFeed = summary?.created_from_feed ?? 0;
  const matchedToInvoices = summary?.matched_to_invoices ?? 0;

  return (
    <section className="rounded-2xl bg-white/90 backdrop-blur-sm p-5 shadow-lg ring-1 ring-slate-100">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Feed Overview
        </h2>
      </div>

      {/* Progress Ring */}
      <div className="flex justify-center mb-4">
        <CircularProgress percent={reconciledPercent} />
      </div>

      <p className="text-center text-sm text-slate-600 mb-5">
        <span className="font-semibold text-slate-900">{newToReview}</span> items to review
      </p>

      {/* Stats */}
      <div className="space-y-3">
        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-100 text-sky-600">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-[11px] text-slate-500">Created from feed</p>
            <p className="text-sm font-semibold text-slate-900">{createdFromFeed}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-[11px] text-slate-500">Matched to invoices</p>
            <p className="text-sm font-semibold text-slate-900">{matchedToInvoices}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="flex-1">
            <p className="text-[11px] text-slate-500">Pending action</p>
            <p className="text-sm font-semibold text-slate-900">{newToReview}</p>
          </div>
        </div>
      </div>
    </section>
  );
};

/* ──────────────────────────────────────────────────
   Quick Actions Section (Redesigned)
   ────────────────────────────────────────────────── */
const QuickActionsSection: React.FC = () => {
  const steps = [
    {
      number: 1,
      title: "Import",
      description: "Drop CSV or connect bank",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
      ),
    },
    {
      number: 2,
      title: "Review",
      description: "Match deposits & categorize",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      ),
    },
    {
      number: 3,
      title: "Done",
      description: "P&L updates in real-time",
      icon: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {steps.map((step) => (
        <div
          key={step.number}
          className="rounded-2xl bg-white/90 backdrop-blur-sm p-4 shadow-sm ring-1 ring-slate-100 hover:ring-emerald-100 hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600 group-hover:bg-emerald-100 group-hover:text-emerald-700 transition-colors">
              {step.number}
            </div>
            <span className="text-slate-500 group-hover:text-emerald-600 transition-colors">
              {step.icon}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-slate-900">{step.title}</h3>
          <p className="text-[11px] text-slate-500 mt-0.5">{step.description}</p>
        </div>
      ))}
    </div>
  );
};

/* ──────────────────────────────────────────────────
   Main Page Component
   ────────────────────────────────────────────────── */
const BankingAccountsAndFeedPage: React.FC<BankingAccountsAndFeedPageProps> = ({
  overviewUrl,
  feedUrl,
  importUrl,
}) => {
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [summary, setSummary] = useState<OverviewSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        const res = await fetch(overviewUrl, { credentials: "same-origin" });
        if (!res.ok) {
          throw new Error("Unable to load banking overview.");
        }
        const json = await res.json();
        if (!isMounted) return;
        const normalized: BankAccount[] = (json.accounts || []).map((acc: any) => ({
          id: acc.id,
          name: acc.name,
          last4: acc.last4 || "",
          bank: acc.bank || "",
          currency: acc.currency || "",
          ledgerLinked: Boolean(acc.ledger_linked),
          ledgerBalance: acc.ledger_balance || "0",
          feedStatus: acc.feed_status || "OK",
          lastImportAt: acc.last_import_at || null,
          newCount: acc.new_count || 0,
          createdCount: acc.created_count || 0,
          matchedCount: acc.matched_count || 0,
          reviewUrl: acc.review_url || feedUrl,
          importUrl: acc.import_url || importUrl,
        }));
        setAccounts(normalized);
        setSummary(json.summary || null);
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load data.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [overviewUrl, feedUrl, importUrl]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 text-slate-900 font-sans">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin h-8 w-8 border-2 border-emerald-600 border-t-transparent rounded-full" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 text-slate-900 font-sans">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="rounded-2xl bg-rose-50 border border-rose-100 px-4 py-6 text-center">
            <p className="text-sm text-rose-600">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100/80 text-slate-900 font-sans">
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Header */}
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Banking
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Connect, sync & reconcile your accounts
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/bank-accounts/new/"
              className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-black transition-colors"
            >
              + Add account
            </a>
            <a
              href={accounts[0]?.importUrl || importUrl}
              className="inline-flex items-center rounded-full bg-white px-4 py-2 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 shadow-sm hover:bg-slate-50 transition-colors"
            >
              Import CSV
            </a>
            <a
              href={accounts[0]?.reviewUrl || feedUrl}
              className="inline-flex items-center rounded-full bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
            >
              Review feed
            </a>
          </div>
        </header>

        {/* Companion Strip */}
        <CompanionStrip context="bank" className="mb-6" />

        {/* Main Content Grid */}
        <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
          {/* Left Column - Accounts */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Connected Accounts
              </h2>
              <span className="text-xs text-slate-400">{accounts.length} active</span>
            </div>

            {accounts.length === 0 ? (
              <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white/50 px-6 py-12 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
                  <svg className="h-6 w-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-slate-700">No bank accounts yet</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                  Add your first account to start importing statements and reconciling transactions.
                </p>
                <a
                  href="/bank-accounts/new/"
                  className="mt-4 inline-flex items-center rounded-full bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700"
                >
                  + Add your first account
                </a>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {accounts.map((account) => (
                  <AccountCard key={account.id} account={account} />
                ))}
              </div>
            )}

            {/* Quick Actions */}
            <div className="mt-6">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
                How it works
              </h2>
              <QuickActionsSection />
            </div>
          </div>

          {/* Right Column - Feed Overview */}
          <div className="space-y-4">
            <FeedOverviewPanel summary={summary} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default BankingAccountsAndFeedPage;
