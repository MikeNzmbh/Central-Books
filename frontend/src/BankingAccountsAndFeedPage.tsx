import React, { useEffect, useState } from "react";

const BANK_GRADIENTS: Record<string, string> = {
  rbc: "from-indigo-500 to-indigo-700",
  td: "from-green-500 to-green-700",
  bmo: "from-sky-500 to-sky-700",
  scotia: "from-red-500 to-red-700",
  wise: "from-emerald-500 to-emerald-700",
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

function formatMoney(value: number | string) {
  const num = typeof value === "number" ? value : Number(value || 0);
  const sign = num < 0 ? "-" : "";
  const abs = Math.abs(num).toFixed(2);
  return `${sign}$${abs}`;
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

function statusBadge(status: FeedStatus) {
  switch (status) {
    case "OK":
      return (
        <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-emerald-100">
          <span className="mr-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Feed healthy
        </span>
      );
    case "ACTION_NEEDED":
      return (
        <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-medium text-amber-800 ring-1 ring-amber-100 whitespace-nowrap">
          <span className="mr-1 h-1.5 w-1.5 rounded-full bg-amber-500" />
          <span>Review&nbsp;</span>
          <span className="underline decoration-dotted">new items</span>
        </span>
      );
    case "DISCONNECTED":
      return (
        <span className="inline-flex items-center rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-medium text-rose-700 ring-1 ring-rose-100">
          <span className="mr-1 h-1.5 w-1.5 rounded-full bg-rose-500" />
          Connection paused
        </span>
      );
    default:
      return null;
  }
}

interface BankingAccountsAndFeedPageProps {
  overviewUrl: string;
  feedUrl: string;
  importUrl: string;
}

const AccountRow: React.FC<{ account: BankAccount }> = ({ account }) => {
  const lastImportText = account.lastImportAt
    ? new Date(account.lastImportAt).toLocaleString()
    : "No imports yet";
  const gradient = getBankGradient(account.bank || account.name);
  const initial = (account.name || "?").trim().charAt(0).toUpperCase();
  return (
    <div className="flex gap-3 rounded-2xl border border-slate-100 bg-white p-3 shadow-sm transition hover:border-sky-100 hover:shadow-md">
      <div
        className={`relative flex h-24 w-40 flex-col justify-between rounded-3xl bg-gradient-to-br ${gradient} px-3 py-2 text-[11px] text-slate-50`}
      >
        <div className="flex items-center justify-between">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15 text-xs font-semibold">
            {initial}
          </div>
          <span className="rounded-full bg-black/20 px-2.5 py-0.5 text-[10px] font-semibold">
            {account.currency || "USD"}
          </span>
        </div>
        <div className="space-y-0.5 mt-1">
          <div className="text-[10px] tracking-[0.28em] uppercase text-slate-100/80">
            {(account.bank || "Scotia").toUpperCase()}
          </div>
          <div className="text-[11px] font-semibold leading-tight max-w-[150px] truncate">{account.name}</div>
          <div className="text-[10px] tracking-[0.16em] text-slate-100/85">•••• {account.last4 || "0000"}</div>
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold text-slate-900">{account.name}</p>
            {statusBadge(account.feedStatus)}
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500">
            <span>
              <span className="font-medium text-slate-600">Last import:</span> {lastImportText}
            </span>
            <span className="hidden sm:inline" aria-hidden="true">
              •
            </span>
            <span>
              <span className="font-medium text-slate-600">Feed items:</span> {account.newCount} New ·{" "}
              {account.createdCount} Created · {account.matchedCount} Matched
            </span>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href={account.importUrl}
            className="inline-flex items-center rounded-full bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-700 ring-1 ring-slate-200 shadow-sm hover:bg-slate-50"
          >
            Import CSV
          </a>
          <a
            href={account.reviewUrl}
            className="inline-flex items-center rounded-full bg-sky-600 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm hover:bg-sky-700"
          >
            Review transactions
          </a>
        </div>
      </div>
      <div className="flex flex-col items-end justify-between text-right">
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Ledger balance</div>
        <div className="text-sm font-semibold text-slate-900">
          {formatMoney(account.ledgerBalance)} {account.currency}
        </div>
      </div>
    </div>
  );
};

const SnapshotCard: React.FC<{ summary: OverviewSummary | null }> = ({ summary }) => {
  const newToReview = summary?.new_to_review ?? 0;
  const createdFromFeed = summary?.created_from_feed ?? 0;
  const matchedToInvoices = summary?.matched_to_invoices ?? 0;
  const reconciledPercent = summary?.reconciled_percent ?? 0;

  return (
    <section className="rounded-3xl bg-white px-6 py-5 text-sm text-slate-700 shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Bank feed snapshot
          </h2>
          <p className="text-xs leading-relaxed text-slate-600">
            All connected bank accounts are kept in sync with your ledger. Once you import statements and review transactions, CERN Books keeps your cash, Profit &amp; Loss, and tax summaries aligned automatically.
          </p>
        </div>
        <div className="flex items-center">
          <div className="flex h-24 w-24 flex-col items-center justify-center rounded-2xl bg-emerald-50 text-[11px] font-medium text-emerald-700 ring-1 ring-emerald-100 text-center leading-snug">
            <div className="text-sm font-semibold">{reconciledPercent}%</div>
            <div>of items</div>
            <div>reconciled</div>
          </div>
        </div>
      </div>
      <div className="mt-4 grid gap-3 text-[11px] sm:grid-cols-3">
        <div className="rounded-2xl bg-slate-50 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-400 whitespace-nowrap">New to review</div>
          <div className="mt-1 text-lg font-semibold text-slate-900">{newToReview}</div>
          <p className="mt-0.5 text-[11px] text-slate-500">Spread across your connected accounts.</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-400 whitespace-nowrap">Created from feed</div>
          <div className="mt-1 text-lg font-semibold text-slate-900">{createdFromFeed}</div>
          <p className="mt-0.5 text-[11px] text-slate-500">Expenses &amp; income posted this week.</p>
        </div>
        <div className="rounded-2xl bg-slate-50 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-400 whitespace-nowrap">Matched to invoices</div>
          <div className="mt-1 text-lg font-semibold text-slate-900">{matchedToInvoices}</div>
          <p className="mt-0.5 text-[11px] text-slate-500">Payments matched to open invoices.</p>
        </div>
      </div>
    </section>
  );
};

const ComingSoonCard: React.FC = () => {
  return (
    <section className="rounded-3xl bg-white px-6 py-5 text-sm text-slate-700 shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Coming soon</h2>
      <p className="text-xs leading-relaxed text-slate-600">
        Future updates will add live bank connections, reconciliation checklists, and smart alerts for unmatched items so you can keep every dollar in sync without manual uploads.
      </p>
      <div className="mt-3 rounded-2xl bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
        You get the same bank feed engine as the big tools, but with a calmer, CERN Books-first workflow.
      </div>
    </section>
  );
};

const QuickActionsCard: React.FC = () => {
  return (
    <section className="rounded-3xl bg-white px-6 py-5 text-sm text-slate-700 shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Quick actions</h2>
      <p className="mb-3 text-xs text-slate-600">
        Clear your feed in a couple of focused passes. CERN Books keeps it fun and lightweight.
      </p>
      <div className="grid gap-3 text-[11px] sm:grid-cols-3">
        <button className="rounded-2xl bg-slate-50 px-3 py-2 text-left font-medium text-slate-800 hover:bg-slate-100">
          <div className="mb-1 text-[11px] uppercase tracking-[0.14em] text-slate-400">1. Import</div>
          <div>Drop in your latest CSV statements.</div>
        </button>
        <button className="rounded-2xl bg-slate-50 px-3 py-2 text-left font-medium text-slate-800 hover:bg-slate-100">
          <div className="mb-1 text-[11px] uppercase tracking-[0.14em] text-slate-400">2. Review</div>
          <div>Match deposits &amp; withdrawals in one place.</div>
        </button>
        <button className="rounded-2xl bg-slate-50 px-3 py-2 text-left font-medium text-slate-800 hover:bg-slate-100">
          <div className="mb-1 text-[11px] uppercase tracking-[0.14em] text-slate-400">3. Done</div>
          <div>See Profit &amp; Loss update instantly.</div>
        </button>
      </div>
    </section>
  );
};

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
      <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <p className="text-sm text-slate-500">Loading banking overview…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <p className="text-sm text-rose-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              BANKING
            </div>
            <h1 className="mb-1 text-2xl font-semibold tracking-tight text-slate-900">
              Bank accounts &amp; feed
            </h1>
            <p className="max-w-xl text-sm text-slate-500">
              Connect accounts, import statements, and keep your bank feed tidy. Once reconciled, your ledger, Profit &amp; Loss, and tax reports stay perfectly in sync.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/bank-accounts/new/"
              className="inline-flex items-center rounded-full bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-black"
            >
              + Add bank account
            </a>
            <a
              href={accounts[0]?.importUrl || importUrl}
              className="inline-flex items-center rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 shadow-sm hover:bg-slate-50"
            >
              Import CSV
            </a>
            <a
              href={accounts[0]?.reviewUrl || feedUrl}
              className="inline-flex items-center rounded-full bg-sky-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-sky-700"
            >
              Review transactions
            </a>
          </div>
        </header>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,2.3fr)_minmax(0,2fr)]">
          <section className="space-y-3">
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-semibold uppercase tracking-[0.16em] text-slate-400">
                Connected accounts
              </span>
              <span>{accounts.length} active</span>
            </div>
            {accounts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">
                No bank accounts yet. Add your first account to start reconciling.
              </div>
            ) : (
              accounts.map((account) => <AccountRow key={account.id} account={account} />)
            )}
          </section>

          <section className="space-y-4">
            <SnapshotCard summary={summary} />
            <QuickActionsCard />
            <ComingSoonCard />
          </section>
        </div>
      </div>
    </div>
  );
};

export default BankingAccountsAndFeedPage;
