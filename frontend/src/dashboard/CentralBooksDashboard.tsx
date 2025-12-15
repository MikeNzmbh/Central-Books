import React, { useMemo, useState } from "react";
import { DashboardCompanionPanel, CompanionBreakdown, CompanionInsight, CompanionTask } from "./DashboardCompanionPanel";
import { useAuth } from "../contexts/AuthContext";
import { AICommandStrip } from "./AICommandStrip";
import { SuppliersDonutCard } from "./SuppliersDonutCard";
import { PLSnapshotCard } from "./PLSnapshotCard";

type PLMonthOption = {
  value: string;
  label: string;
};

type DashboardMetrics = {
  cash_on_hand?: number;
  open_invoices_total?: number;
  open_invoices_count?: number;
  net_income_month?: number;
  revenue_30?: number;
  expenses_30?: number;
  overdue_total?: number;
  overdue_count?: number;
  unpaid_expenses_total?: number;
  revenue_month?: number;
  expenses_month?: number;
  pl_period_start?: string;
  pl_period_end?: string;
  pl_period_preset?: string;
  pl_selected_month?: string;
  pl_month_options?: PLMonthOption[];
  pl_period_label?: string;
  pl_compare_to?: string;
  pl_compare_label?: string;
  pl_compare_start?: string;
  pl_compare_end?: string;
  pl_prev_period_label?: string;
  pl_prev_income?: number | null;
  pl_prev_expenses?: number | null;
  pl_prev_net?: number | null;
  pl_diagnostics?: {
    has_ledger_activity?: boolean;
    has_bank_activity?: boolean;
    reason_code?: string;
    reason_message?: string;
  };
  pl_change_income_pct?: number | null;
  pl_change_expenses_pct?: number | null;
  pl_change_net_pct?: number | null;
  pl_debug?: {
    period_start?: string | null;
    period_end?: string | null;
    income_line_count?: number;
    expense_line_count?: number;
    last_income_entry_date?: string | null;
    last_expense_entry_date?: string | null;
    no_ledger_activity_for_period?: boolean;
  };
};

type InvoiceSummary = {
  number: string;
  customer: string;
  status: string;
  issue_date: string;
  amount: number;
  due_label: string;
  url?: string;
};

type BankFeedItem = {
  description: string;
  note?: string;
  amount: number;
  direction?: string;
  date?: string;
};

type ExpenseSummary = {
  name: string;
  total: number;
};

type SupplierSummary = {
  name: string;
  mtdSpend?: number;
  paymentCount?: number;
  category?: string;
};

type CashflowSeries = {
  labels?: string[];
  income?: number[];
  expenses?: number[];
};

export interface CentralBooksDashboardProps {
  username?: string;
  currency?: string;
  metrics?: DashboardMetrics;
  recentInvoices?: InvoiceSummary[];
  bankFeed?: BankFeedItem[];
  expenseSummary?: ExpenseSummary[];
  topSuppliers?: SupplierSummary[];
  cashflow?: CashflowSeries;
  urls?: {
    newInvoice?: string;
    invoices?: string;
    banking?: string;
    expenses?: string;
    suppliers?: string;
    profitAndLoss?: string;
    bankReview?: string;
    overdueInvoices?: string;
    unpaidExpenses?: string;
    startBooks?: string;
    bankImport?: string;
    cashflowReport?: string;
  };
  is_empty_workspace?: boolean;
}

const CentralBooksDashboard: React.FC<CentralBooksDashboardProps> = ({
  username,
  currency = "USD",
  metrics,
  recentInvoices = [],
  bankFeed = [],
  expenseSummary = [],
  topSuppliers = [],
  cashflow,
  urls,
}) => {
  const { logout } = useAuth();
  const greetingName = username && username.trim().length ? username : "there";
  const safeUrl = (value?: string) => value || "#";

  const formatter = useMemo(() => {
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currency || "USD",
      });
    } catch {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "USD",
      });
    }
  }, [currency]);

  const formatMoney = (value?: number) => formatter.format(value || 0);
  const pnlZero =
    (metrics?.revenue_month || 0) === 0 &&
    (metrics?.expenses_month || 0) === 0 &&
    (metrics?.net_income_month || 0) === 0;
  const plMessage =
    metrics?.net_income_month === 0 && metrics?.pl_diagnostics?.reason_message
      ? metrics.pl_diagnostics.reason_message
      : null;
  const noLedgerActivity = Boolean(metrics?.pl_debug?.no_ledger_activity_for_period);
  const showNoActivityMessage = pnlZero && (noLedgerActivity || Boolean(plMessage));
  const plPeriodLabel = metrics?.pl_period_label || "This month";
  const plPrevPeriodLabel = metrics?.pl_prev_period_label || "last month";

  const cashflowBars = useMemo(() => {
    const labels = cashflow?.labels || [];
    const income = cashflow?.income || [];
    const expenses = cashflow?.expenses || [];
    return labels.slice(-6).map((label, idx) => ({
      label,
      income: income[idx] || 0,
      expenses: expenses[idx] || 0,
    }));
  }, [cashflow]);

  const maxCashflowValue = useMemo(() => {
    if (!cashflowBars.length) return 1;
    return Math.max(
      ...cashflowBars.map((bar) => Math.max(bar.income || 0, bar.expenses || 0, 0)),
      1
    );
  }, [cashflowBars]);

  const tasks = useMemo(() => {
    const items: Array<{ title: string; body: string; color: string; cta: string; href: string }> = [];
    if ((metrics?.overdue_count || 0) > 0) {
      items.push({
        title: `${metrics?.overdue_count} invoice${metrics?.overdue_count === 1 ? "" : "s"} overdue`,
        body: `Customers owe ${formatMoney(metrics?.overdue_total)} `,
        color: "bg-amber-500",
        cta: "Review",
        href: safeUrl(urls?.overdueInvoices || urls?.invoices),
      });
    }
    if (bankFeed.length) {
      items.push({
        title: `${bankFeed.length} bank item${bankFeed.length === 1 ? "" : "s"} to review`,
        body: `Latest entry: ${bankFeed[0].description} `,
        color: "bg-sky-500",
        cta: "Open",
        href: safeUrl(urls?.bankReview || urls?.banking),
      });
    }
    if ((metrics?.unpaid_expenses_total || 0) > 0) {
      items.push({
        title: "Unpaid expenses",
        body: `${formatMoney(metrics?.unpaid_expenses_total)} awaiting payment`,
        color: "bg-rose-500",
        cta: "Inspect",
        href: safeUrl(urls?.unpaidExpenses || urls?.expenses),
      });
    }
    if (!items.length) {
      items.push({
        title: "Everything reconciled",
        body: "No outstanding tasks right now.",
        color: "bg-emerald-500",
        cta: "Nice",
        href: "#",
      });
    }
    return items.slice(0, 3);
  }, [metrics, bankFeed, formatMoney, urls]);

  // Companion Panel State
  const [companionTasks, setCompanionTasks] = useState<CompanionTask[]>([
    {
      id: "t1",
      title: "Uncategorized Transaction",
      subtitle: `Large outflow needs a category assignment.`,
      severity: "high",
      confidenceLabel: "Rent?",
      categoryLabel: "Ledger",
      ctaLabel: "Categorize",
    },
    {
      id: "t2",
      title: "Duplicate Invoice Detected",
      subtitle: "An invoice appears twice with identical amounts.",
      severity: "medium",
      categoryLabel: "Invoices",
      ctaLabel: "Review Duplicates",
    },
  ]);

  const companionInsights: CompanionInsight[] = useMemo(() => {
    const items: CompanionInsight[] = [];
    if ((metrics?.overdue_count || 0) > 0) {
      items.push({
        id: "overdue",
        title: "Customers have overdue invoices",
        message: `${metrics?.overdue_count} invoice${(metrics?.overdue_count || 0) > 1 ? 's' : ''} past due. Follow up to improve cash flow.`,
        severity: "info",
        categoryLabel: "Invoices",
      });
    }
    if (bankFeed.length > 5) {
      items.push({
        id: "bank",
        title: "Unreconciled transactions to clear",
        message: `${bankFeed.length} bank items need reconciliation.`,
        severity: "info",
        categoryLabel: "Banking",
      });
    }
    return items;
  }, [metrics, bankFeed]);

  const companionBreakdown: CompanionBreakdown = useMemo(() => {
    const today = new Date();
    const dateLabel = today.toISOString().split('T')[0];
    return {
      dateLabel,
      reconciliation: bankFeed.length === 0 ? 100 : Math.max(0, 100 - bankFeed.length * 5),
      ledgerIntegrity: 95,
      invoices: (metrics?.overdue_count || 0) > 0 ? 85 : 96,
      expenses: 100,
      taxFx: 100,
      bank: bankFeed.length === 0 ? 100 : Math.max(4, 100 - bankFeed.length * 10),
    };
  }, [bankFeed, metrics]);

  const handleCompanionTaskPrimary = (id: string) => {
    // Navigate to appropriate page based on task
    const task = companionTasks.find(t => t.id === id);
    if (task?.categoryLabel === "Ledger") {
      window.location.href = urls?.banking || "/banking/";
    } else if (task?.categoryLabel === "Invoices") {
      window.location.href = urls?.invoices || "/invoices/";
    }
  };

  const handleCompanionTaskSecondary = (id: string) => {
    setCompanionTasks((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <div className="min-h-screen w-full bg-slate-50 text-slate-900 px-4 py-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">Overview</p>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-900">
              Morning, {greetingName}. Your books are in good shape.
            </h1>
            <p className="text-sm text-slate-500">
              Live snapshot across cash, invoices, expenses, suppliers, and profit &amp; loss.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <a
              href={safeUrl(urls?.banking)}
              className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Go to banking
            </a>
            <a
              href={safeUrl(urls?.profitAndLoss)}
              className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              View P&amp;L
            </a>
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              Logout
            </button>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-[1.15fr,1.1fr]">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-3xl border border-slate-100 bg-white/90 px-4 py-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">Cash on hand</p>
              <p className="mt-2 text-xl font-semibold text-slate-900">{formatMoney(metrics?.cash_on_hand)}</p>
              <div className="mt-1 flex items-center gap-1.5 text-[11px] text-emerald-600">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <span>Updated live from ledger balances</span>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-100 bg-white/90 px-4 py-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">Open invoices</p>
              <p className="mt-2 text-xl font-semibold text-slate-900">{formatMoney(metrics?.open_invoices_total)}</p>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-600">
                <span>{metrics?.open_invoices_count || 0} awaiting payment</span>
                <span className="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                  {metrics?.overdue_count || 0} overdue
                </span>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-100 bg-white/90 px-4 py-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">Profit &amp; loss</p>
              <p className="mt-0.5 text-[11px] text-slate-500">{plPeriodLabel}</p>
              {showNoActivityMessage ? (
                <div className="mt-2 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-[12px] text-slate-600">
                  No income or expenses have been posted to your ledger for this period. Try last month or another date
                  range.
                </div>
              ) : (
                <>
                  <p className="mt-2 text-xl font-semibold text-slate-900">{formatMoney(metrics?.net_income_month)}</p>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-600">
                    <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-700">
                      Revenue {formatMoney(metrics?.revenue_month)}
                    </span>
                    <span>Expenses {formatMoney(metrics?.expenses_month)}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-600">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">
                      vs {plPrevPeriodLabel}
                    </span>
                    <span>
                      Revenue {formatMoney(metrics?.pl_prev_income ?? 0)} · Expenses {formatMoney(metrics?.pl_prev_expenses ?? 0)}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white/90 p-4 sm:p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Cashflow — last 6 periods</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">
                  Smooth and trending {cashflowBars.length ? "with your real numbers" : "— add data to populate."}
                </p>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-slate-500">
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700 whitespace-nowrap">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Inflows
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 font-medium text-rose-700 whitespace-nowrap">
                  <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                  Outflows
                </span>
              </div>
            </div>

            <div className="relative mt-1 h-32 rounded-2xl bg-slate-50/80 overflow-hidden">
              <div className="absolute inset-x-4 bottom-4 top-5 flex items-end gap-2 h-full">
                {cashflowBars.length ? (
                  cashflowBars.map((bar, idx) => {
                    const incomeHeight = Math.max(6, (bar.income / maxCashflowValue) * 90);
                    const expenseHeight = Math.max(4, (bar.expenses / maxCashflowValue) * 60);
                    return (
                      <div key={`${bar.label} -${idx} `} className="flex-1 flex flex-col justify-end gap-1 h-full">
                        <div
                          className="rounded-full bg-emerald-200 transition-all duration-200"
                          style={{ height: `${incomeHeight}% ` }}
                        />
                        <div
                          className="rounded-full bg-rose-200 transition-all duration-200"
                          style={{ height: `${expenseHeight}% ` }}
                        />
                      </div>
                    );
                  })
                ) : (
                  <div className="text-sm text-slate-500 px-4">Add invoices and expenses to populate this view.</div>
                )}
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-white/40 to-transparent" />
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>
                {cashflowBars.length
                  ? `${cashflowBars[0].label} → ${cashflowBars[cashflowBars.length - 1].label} `
                  : "Waiting for activity"}
              </span>
              <a
                href={safeUrl(urls?.cashflowReport)}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium hover:bg-slate-50"
              >
                View cashflow report
              </a>
            </div>
          </div>
        </section>

        {/* Companion Health Index - above invoices/banking */}
        <section>
          <DashboardCompanionPanel
            greetingName={greetingName}
            breakdown={companionBreakdown}
            insights={companionInsights}
            tasks={companionTasks}
            onTaskPrimary={handleCompanionTaskPrimary}
            onTaskSecondary={handleCompanionTaskSecondary}
            onOpenFullCompanion={() => window.location.href = "/companion/"}
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.1fr,1.05fr]">
          <div className="rounded-3xl border border-slate-100 bg-white/90 p-4 sm:p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500">Invoices</p>
                <p className="mt-1 text-sm text-slate-500">
                  Snapshot of what&apos;s open, overdue, and collected.
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <a
                  href={safeUrl(urls?.newInvoice)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-slate-700 hover:bg-white"
                >
                  New invoice
                </a>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl bg-slate-50/80 border border-slate-100 px-3 py-3">
                <p className="text-[11px] text-slate-500">Open</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{formatMoney(metrics?.open_invoices_total)}</p>
                <p className="mt-0.5 text-[11px] text-slate-500">{metrics?.open_invoices_count || 0} invoices</p>
              </div>
              <div className="rounded-2xl bg-slate-50/80 border border-slate-100 px-3 py-3">
                <p className="text-[11px] text-slate-500">Overdue</p>
                <p className="mt-1 text-lg font-semibold text-amber-700">{formatMoney(metrics?.overdue_total)}</p>
                <p className="mt-0.5 text-[11px] text-amber-700">{metrics?.overdue_count || 0} clients</p>
              </div>
              <div className="rounded-2xl bg-slate-50/80 border border-slate-100 px-3 py-3">
                <p className="text-[11px] text-slate-500">Collected (30d)</p>
                <p className="mt-1 text-lg font-semibold text-emerald-700">{formatMoney(metrics?.revenue_30)}</p>
                <p className="mt-0.5 text-[11px] text-emerald-700">vs expenses {formatMoney(metrics?.expenses_30)}</p>
              </div>
            </div>

            <div className="mt-1 rounded-2xl border border-slate-100 bg-slate-50/80 p-3">
              <div className="flex items-center justify-between text-[11px] text-slate-600 mb-2">
                <span>Recent invoices</span>
                <span>Date · Client · Status · Total</span>
              </div>
              <div className="space-y-1.5 text-xs">
                {recentInvoices.length ? (
                  recentInvoices.slice(0, 3).map((inv) => (
                    <a
                      key={inv.number}
                      href={safeUrl(inv.url || urls?.invoices)}
                      className="flex items-center justify-between rounded-xl bg-white px-3 py-2 hover:bg-slate-50 transition"
                    >
                      <span className="flex-1 truncate">#{inv.number} · {inv.customer}</span>
                      <span className="w-24 text-right text-slate-500">{inv.due_label}</span>
                      <span className="w-20 text-right font-medium text-slate-900">{formatMoney(inv.amount)}</span>
                    </a>
                  ))
                ) : (
                  <div className="text-slate-500 text-sm px-2 py-3">No invoices yet.</div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-3xl border border-slate-100 bg-white/90 p-4 sm:p-5 shadow-sm flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500">Bank feed</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {bankFeed.length
                      ? `${bankFeed.length} item${bankFeed.length === 1 ? "" : "s"} need review.`
                      : "Connect a bank feed to see activity here."}
                  </p>
                </div>
                <a
                  href={safeUrl(urls?.banking)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-white"
                >
                  Go to banking
                </a>
              </div>

              <div className="space-y-1.5 text-xs">
                {bankFeed.length ? (
                  bankFeed.map((item, idx) => (
                    <div key={`${item.description} -${idx} `} className="flex items-center justify-between rounded-2xl bg-slate-50 px-3 py-2">
                      <div className="flex flex-col">
                        <span className="font-medium text-slate-900">{item.description}</span>
                        <span className="text-[11px] text-slate-500">{item.note}</span>
                      </div>
                      <span className={`font - semibold ${item.amount >= 0 ? "text-emerald-700" : "text-rose-600"} `}>
                        {item.amount >= 0 ? "+" : "-"}{formatMoney(Math.abs(item.amount))}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-500 text-sm px-2 py-3">No transactions yet.</div>
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-100 bg-white/90 p-4 sm:p-5 shadow-sm flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500">Expenses</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Where your money is going this month.
                  </p>
                </div>
                <a
                  href={safeUrl(urls?.expenses)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-white"
                >
                  View expenses
                </a>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 text-xs">
                <div className="rounded-2xl bg-slate-50/80 border border-slate-100 px-3 py-3">
                  <p className="text-[11px] text-slate-500">This month</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatMoney(metrics?.expenses_month)}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">vs revenue {formatMoney(metrics?.revenue_month)}</p>
                </div>
                {expenseSummary.slice(0, 2).map((entry) => (
                  <div key={entry.name} className="rounded-2xl bg-slate-50/80 border border-slate-100 px-3 py-3">
                    <p className="text-[11px] text-slate-500">Top category</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{entry.name}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">{formatMoney(entry.total)}</p>
                  </div>
                ))}
                {expenseSummary.length === 0 && (
                  <div className="rounded-2xl bg-slate-50/80 border border-slate-100 px-3 py-3">
                    <p className="text-[11px] text-slate-500">No expenses yet</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">Log your first expense.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Bottom Section: AI Strip + Suppliers + P&L (Redesigned) */}
        <section className="space-y-4">
          {/* Full-width AI Command Strip */}
          <AICommandStrip tasks={tasks} />

          {/* Two-column layout: Suppliers + P&L */}
          <div className="grid gap-4 lg:grid-cols-2">
            <SuppliersDonutCard
              suppliers={topSuppliers}
              currency={currency}
              suppliersUrl={safeUrl(urls?.suppliers)}
            />
            <PLSnapshotCard
              revenue={metrics?.revenue_month}
              expenses={metrics?.expenses_month}
              netProfit={metrics?.net_income_month}
              currency={currency}
              periodLabel={plPeriodLabel}
              selectedMonth={metrics?.pl_selected_month}
              monthOptions={metrics?.pl_month_options}
              prevRevenue={metrics?.pl_prev_income}
              prevExpenses={metrics?.pl_prev_expenses}
              prevNet={metrics?.pl_prev_net}
              profitAndLossUrl={safeUrl(urls?.profitAndLoss)}
              showNoActivity={showNoActivityMessage}
              noActivityMessage={plMessage || undefined}
            />
          </div>
        </section>
      </div>
    </div>
  );
};

export default CentralBooksDashboard;
