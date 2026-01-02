import React, { useMemo, useState } from "react";

export type AccountType = "ASSET" | "LIABILITY" | "EQUITY" | "INCOME" | "EXPENSE";

export type AccountDTO = {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  detailType: string;
  isActive: boolean;
  balance: number;
  favorite?: boolean;
  detailUrl?: string;
};

export type ChartOfAccountsBootPayload = {
  accounts: AccountDTO[];
  currencyCode: string;
  totalsByType?: Partial<Record<AccountType, number>>;
};

interface ChartOfAccountsPageProps {
  payload: ChartOfAccountsBootPayload;
  newAccountUrl: string;
}

const ACCOUNT_TYPE_LABEL: Record<AccountType, string> = {
  ASSET: "Assets",
  LIABILITY: "Liabilities",
  EQUITY: "Equity",
  INCOME: "Income",
  EXPENSE: "Expenses",
};

function formatMoney(value: number, currencyCode: string) {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value).toFixed(2);
  return `${sign}$${abs} ${currencyCode}`;
}

function formatCountLabel(count: number, noun: string) {
  if (count === 0) return `No ${noun}s`;
  if (count === 1) return `1 ${noun}`;
  return `${count} ${noun}s`;
}

const ChartOfAccountsPage: React.FC<ChartOfAccountsPageProps> = ({ payload, newAccountUrl }) => {
  const accounts = payload.accounts || [];
  const currencyCode = payload.currencyCode || "USD";
  const totalsPreset = payload.totalsByType;
  const [typeFilter, setTypeFilter] = useState<AccountType | "ALL">("ALL");
  const [statusFilter, setStatusFilter] = useState<"ACTIVE" | "ARCHIVED" | "ALL">("ACTIVE");
  const [search, setSearch] = useState("");
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);

  const filteredAccounts = useMemo(
    () =>
      accounts.filter((acc) => {
        if (typeFilter !== "ALL" && acc.type !== typeFilter) return false;
        if (statusFilter === "ACTIVE" && !acc.isActive) return false;
        if (statusFilter === "ARCHIVED" && acc.isActive) return false;
        if (showFavoritesOnly && !acc.favorite) return false;

        if (search.trim()) {
          const q = search.toLowerCase();
          if (!(`${acc.code} ${acc.name} ${acc.detailType}`.toLowerCase().includes(q))) {
            return false;
          }
        }
        return true;
      }),
    [accounts, typeFilter, statusFilter, search, showFavoritesOnly]
  );

  const totalsByType = useMemo(() => {
    if (totalsPreset) {
      return totalsPreset;
    }
    const t: Partial<Record<AccountType, number>> = {};
    accounts.forEach((acc) => {
      t[acc.type] = (t[acc.type] || 0) + acc.balance;
    });
    return t;
  }, [accounts, totalsPreset]);

  const activeCount = accounts.filter((a) => a.isActive).length;
  const archivedCount = accounts.length - activeCount;

  const handleNewAccountClick = () => {
    if (newAccountUrl) {
      window.location.href = newAccountUrl;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="text-[11px] font-semibold tracking-[0.18em] text-slate-400 uppercase mb-2">
              REPORTS
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900 mb-1">
              Chart of Accounts
            </h1>
            <p className="text-sm text-slate-500 max-w-xl">
              Review, group, and maintain the accounts that power your ledger, Profit &amp; Loss, and balance sheet.
            </p>
          </div>

          <div className="flex flex-col items-stretch gap-3 sm:items-end">
            <div className="flex items-center gap-2">
              <button
                className="inline-flex items-center rounded-full bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-black"
                type="button"
                onClick={handleNewAccountClick}
              >
                + New account
              </button>
              <button className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50">
                Reorder codes
              </button>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-right text-xs text-slate-500 shadow-sm">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400 mb-1">Accounts overview</div>
              <div className="flex items-center justify-end gap-3 text-[11px]">
                <span className="text-slate-600 font-mono-soft">{formatCountLabel(activeCount, "active account")}</span>
                <span className="h-1 w-1 rounded-full bg-slate-300" />
                <span className="text-slate-400 font-mono-soft">{formatCountLabel(archivedCount, "archived")}</span>
              </div>
            </div>
          </div>
        </header>

        <div className="mb-5 grid gap-4 lg:grid-cols-[minmax(0,2.1fr)_minmax(0,2.4fr)]">
          <section className="rounded-3xl bg-white shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100 px-5 py-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h2 className="text-[13px] font-semibold text-slate-900">Balances by type</h2>
              <span className="text-[11px] text-slate-400">Ledger-backed preview</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-[11px]">
              {(["ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"] as AccountType[]).map((t) => {
                const total = totalsByType[t] || 0;
                const positive = t === "INCOME" ? total < 0 : total >= 0;
                const color = positive ? "text-emerald-600" : "text-rose-600";
                return (
                  <div key={t} className="rounded-2xl bg-slate-50 px-3 py-2 ring-1 ring-slate-100 flex flex-col gap-0.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-medium tracking-[0.16em] uppercase text-slate-400">
                        {ACCOUNT_TYPE_LABEL[t]}
                      </span>
                    </div>
                    <span className={`text-xs font-semibold font-mono-soft ${color}`}>{formatMoney(total, currencyCode)}</span>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded-3xl bg-white shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100 px-5 py-4 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-[13px] font-semibold text-slate-900">Refine this view</h2>
              <button
                type="button"
                className="text-[11px] font-medium text-sky-600 hover:text-sky-700"
                onClick={() => {
                  setTypeFilter("ALL");
                  setStatusFilter("ACTIVE");
                  setSearch("");
                  setShowFavoritesOnly(false);
                }}
              >
                Reset
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1 text-[11px] font-medium">
                {["ALL", "ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"].map((key) => {
                  const active = typeFilter === key || (key === "ALL" && typeFilter === "ALL");
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setTypeFilter(key as any)}
                      className={`rounded-full px-2.5 py-1 transition ${active ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                    >
                      {key === "ALL" ? "All types" : ACCOUNT_TYPE_LABEL[key as AccountType]}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1 text-[11px] font-medium">
                {["ACTIVE", "ARCHIVED", "ALL"].map((key) => {
                  const active = statusFilter === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setStatusFilter(key as any)}
                      className={`rounded-full px-2.5 py-1 transition ${active ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                    >
                      {key === "ACTIVE" ? "Active only" : key === "ARCHIVED" ? "Archived only" : "Show all"}
                    </button>
                  );
                })}
              </div>

              <label className="inline-flex items-center gap-2 text-[11px] text-slate-600">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                  checked={showFavoritesOnly}
                  onChange={(e) => setShowFavoritesOnly(e.target.checked)}
                />
                Show favorites only
              </label>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex-1">
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by name, code, or detail type"
                  className="h-8 w-full rounded-full border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                />
              </div>
            </div>
          </section>
        </div>

        <section className="rounded-3xl bg-white shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100 overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
            <div>
              <h2 className="text-[13px] font-semibold text-slate-900">Accounts</h2>
              <p className="text-[11px] text-slate-500">{formatCountLabel(filteredAccounts.length, "account")} shown with current filters.</p>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 ring-1 ring-slate-100">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Active
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 ring-1 ring-slate-100">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                Archived
              </span>
            </div>
          </div>

          {filteredAccounts.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-8 py-12 text-center text-xs text-slate-400">
              <p>No accounts match these filters.</p>
              <p className="mt-1">Try adjusting the type or status filters, or clear the search.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 text-xs">
                <thead className="bg-slate-50 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                  <tr>
                    <th className="px-5 py-2 text-left font-medium">Code</th>
                    <th className="px-3 py-2 text-left font-medium">Name</th>
                    <th className="px-3 py-2 text-left font-medium">Type</th>
                    <th className="px-3 py-2 text-left font-medium">Detail type</th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Balance</th>
                    <th className="px-4 py-2 text-right font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredAccounts.map((acc) => (
                    <tr key={acc.id} className="hover:bg-slate-50/70 transition">
                      <td className="whitespace-nowrap px-5 py-2 text-[11px] font-medium text-slate-500">{acc.code}</td>
                      <td className="max-w-[240px] px-3 py-2 align-middle">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${acc.favorite ? "text-amber-400" : "text-slate-300"
                              }`}
                            aria-hidden="true"
                          >
                            ★
                          </span>
                          <div className="min-w-0">
                            <div className="truncate text-[13px] font-semibold text-slate-900">{acc.name}</div>
                            <div className="truncate text-[11px] text-slate-500">{acc.detailType}</div>
                          </div>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-[11px] text-slate-600">{ACCOUNT_TYPE_LABEL[acc.type]}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-[11px] text-slate-500">{acc.detailType}</td>
                      <td className="whitespace-nowrap px-3 py-2">
                        {acc.isActive ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 ring-1 ring-emerald-100">Active</span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200">Archived</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right text-[11px] font-semibold text-slate-900 font-mono-soft">{formatMoney(acc.balance, currencyCode)}</td>
                      <td className="whitespace-nowrap px-4 py-2 text-right">
                        <a
                          href={acc.detailUrl || "#"}
                          className="text-[11px] font-medium text-sky-600 hover:text-sky-700"
                        >
                          View
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default ChartOfAccountsPage;
