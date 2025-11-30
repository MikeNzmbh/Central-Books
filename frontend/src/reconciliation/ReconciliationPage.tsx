import React, { useEffect, useState, useMemo } from "react";
import {
  AlertTriangle,
  Check,
  Filter,
  Info,
  RefreshCw,
  Search,
  Split,
  ChevronDown,
  ChevronRight,
  Plus,
  ArrowRight,
  Lock,
  Calendar
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "../components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "../components/ui/sheet";
import { ScrollArea } from "../components/ui/scroll-area";
import { Separator } from "../components/ui/separator";

import "../index.css";

// --- Types ---

export type RecoStatus = "NEW" | "SUGGESTED" | "MATCHED" | "MATCHED_SINGLE" | "MATCHED_MULTI" | "RECONCILED" | "PARTIAL" | "EXCLUDED" | "IGNORED";
export type RecoSessionStatus = "DRAFT" | "IN_PROGRESS" | "COMPLETED";

export interface BankAccountSummary {
  id: string;
  name: string; // e.g. "1000 · Cash (Main)"
  bankLabel?: string; // e.g. "RBC Business #1"
  currency: string;
  isDefault?: boolean;
}

export interface RecoPeriodOption {
  id: string;
  label: string; // e.g. "November 2025"
  startDate: string; // ISO date
  endDate: string; // ISO date
  isCurrent: boolean;
  isLocked: boolean;
}

export interface RecoSession {
  id: string;
  status: RecoSessionStatus;
  bankAccount: BankAccountSummary;
  period: RecoPeriodOption;
  beginningBalance: number; // statement opening balance
  endingBalance: number; // statement ending balance
  clearedBalance: number; // from matched/cleared txns
  difference: number; // endingBalance - clearedBalance
  reconciledPercent: number; // 0–100
  totalTransactions: number;
  unreconciledCount: number;
}

export interface BankTransaction {
  id: string;
  date: string; // ISO
  description: string;
  counterparty?: string;
  amount: number; // Numeric for calculation
  currency: string;
  status: RecoStatus;
  match_confidence?: number | null; // 0-1
  engine_reason?: string | null;
  match_type?: string | null;
  is_soft_locked?: boolean;

  // Frontend specific
  includedInSession: boolean; // whether this line is checked into current session
}

interface EngineInsights {
  state: "IDLE" | "MATCHING" | "IMPORTING";
  lastRunAt?: string;
  notes?: string;
}

interface ReconciliationPageState {
  bankAccounts: BankAccountSummary[];
  activeBankId: string | null;
  periods: RecoPeriodOption[];
  activePeriodId: string | null;
  canReconcile: boolean;
  emptyReason: string | null;
  session: RecoSession | null;
  transactions: BankTransaction[];
  engineInsights: EngineInsights | null;
  statusFilter: RecoStatus | "ALL";
  search: string;
  loading: boolean;
  error: string | null;
}

// --- Helper Functions ---

async function fetchJson<T = any>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include", // Ensure cookies are sent
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    let msg = `Request failed: ${res.status}`;
    try {
      const json = JSON.parse(text);
      if (json.error) msg = json.error;
      else if (json.detail) msg = json.detail;
    } catch (e) {
      // ignore
    }
    throw new Error(msg);
  }

  return res.json();
}

function getCsrfToken() {
  return document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value || "";
}

function formatAmount(amount: number, currency: string) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  }).format(amount);
}

// --- Components ---

function EmptyState({ canReconcile, reason }: { canReconcile: boolean; reason: string | null }) {
  return (
    <section className="mb-6 rounded-3xl border border-slate-200 bg-white shadow-sm p-6 flex flex-col items-center text-center gap-3">
      <div className="h-12 w-12 rounded-full bg-slate-50 flex items-center justify-center text-2xl">🏦</div>
      <h2 className="text-lg font-semibold text-slate-900">You don’t have any bank accounts yet</h2>
      <p className="max-w-lg text-sm text-slate-600">
        Add a bank account to start reconciling statements. We’ll bring you back here once it’s created.
      </p>
      <div className="flex items-center gap-2">
        <Button asChild>
          <a href="/bank-accounts/new/?returnTo=/reconciliation">+ Add a bank account</a>
        </Button>
      </div>
      {!canReconcile && reason && (
        <p className="text-xs text-slate-400">Reason: {reason}</p>
      )}
    </section>
  );
}

export default function ReconciliationPage({ bankAccountId }: { bankAccountId?: string }) {
  const [state, setState] = useState<ReconciliationPageState>({
    bankAccounts: [],
    activeBankId: bankAccountId || null,
    periods: [],
    activePeriodId: null,
    canReconcile: true,
    emptyReason: null,
    session: null,
    transactions: [],
    engineInsights: null,
    statusFilter: "ALL",
    search: "",
    loading: false,
    error: null,
  });

  // Initial Load
  useEffect(() => {
    loadConfig();
  }, []);

  // Load Session when Bank or Period changes
  useEffect(() => {
    if (state.activeBankId) {
      loadSession(state.activeBankId, state.activePeriodId);
    }
  }, [state.activeBankId, state.activePeriodId]);

  async function loadConfig() {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const raw = await fetchJson<any>("/api/reconciliation/config/");
      const accounts: BankAccountSummary[] = Array.isArray(raw) ? raw : (raw.accounts || []);
      const canReconcile = Array.isArray(raw) ? accounts.length > 0 : raw.can_reconcile !== false;
      const emptyReason = Array.isArray(raw) ? null : raw.reason || null;
      setState(prev => ({
        ...prev,
        bankAccounts: accounts,
        activeBankId: prev.activeBankId || (accounts.length > 0 ? accounts[0].id : null),
        canReconcile,
        emptyReason,
        loading: false
      }));
    } catch (e: any) {
      console.error(e);
      setState(prev => ({ ...prev, loading: false, error: e.message }));
    }
  }

  async function loadSession(bankId: string, periodId: string | null) {
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const url = `/api/reconciliation/session/?bank_account_id=${bankId}${periodId ? `&period_id=${periodId}` : ""}`;
      const sessionData = await fetchJson<any>(url);

      // Transform session data to match our types
      const session: RecoSession = {
        id: sessionData.id,
        status: sessionData.status,
        bankAccount: sessionData.bankAccount,
        period: sessionData.period,
        beginningBalance: sessionData.beginningBalance,
        endingBalance: sessionData.endingBalance,
        clearedBalance: sessionData.clearedBalance,
        difference: sessionData.difference,
        reconciledPercent: sessionData.reconciledPercent,
        totalTransactions: sessionData.totalTransactions,
        unreconciledCount: sessionData.unreconciledCount,
      };

      // Load transactions for this session
      // We use the existing endpoint but might need to filter client-side or update endpoint
      // For now, let's fetch transactions and map them
      const txData = await fetchJson<any[]>(`/api/bank-accounts/${bankId}/reconciliation/transactions/?status=ALL`);

      // Filter transactions relevant to this session (simple date filter for now + session check)
      // In a real app, the backend should do this filtering based on the session logic
      const startDate = new Date(session.period.startDate);
      const endDate = new Date(session.period.endDate);

      const mappedTxs: BankTransaction[] = txData.map((t: any) => ({
        id: String(t.id),
        date: t.date,
        description: t.description,
        counterparty: t.counterparty,
        amount: Number(t.amount),
        currency: t.currency,
        status: t.status,
        match_confidence: t.match_confidence,
        engine_reason: t.engine_reason,
        match_type: t.match_type,
        is_soft_locked: t.is_soft_locked,
        includedInSession: true, // Default to true if returned? Or logic based on date?
      })).filter(t => {
        // Simple client-side filter to mimic "in this period"
        // Ideally backend handles this
        const d = new Date(t.date);
        return d >= startDate && d <= endDate;
      });

      setState(prev => ({
        ...prev,
        periods: sessionData.periods,
        activePeriodId: session.period.id,
        session,
        transactions: mappedTxs,
        loading: false
      }));

    } catch (e: any) {
      console.error(e);
      setState(prev => ({ ...prev, loading: false, error: e.message }));
    }
  }

  const onSelectBank = (bankId: string) => {
    setState((prev) => ({ ...prev, activeBankId: bankId, activePeriodId: null, error: null }));
  };

  const onSelectPeriod = (periodId: string) => {
    setState((prev) => ({ ...prev, activePeriodId: periodId }));
  };

  const onChangeSessionField = async (field: "beginningBalance" | "endingBalance", value: number) => {
    // Optimistic update
    setState((prev) =>
      prev.session
        ? {
          ...prev,
          session: { ...prev.session, [field]: value },
        }
        : prev,
    );

    // Debounce/API call
    if (state.session) {
      try {
        await fetchJson("/api/reconciliation/session/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({
            session_id: state.session.id,
            [field]: value
          })
        });
        // Reload session to get updated difference/cleared balance
        loadSession(state.activeBankId!, state.activePeriodId);
      } catch (e) {
        console.error(e);
      }
    }
  };

  const onToggleInclude = async (txId: string) => {
    const tx = state.transactions.find(t => t.id === txId);
    if (!tx || !state.session) return;

    const newIncluded = !tx.includedInSession;

    // Optimistic
    setState((prev) => ({
      ...prev,
      transactions: prev.transactions.map((t) =>
        t.id === txId ? { ...t, includedInSession: newIncluded } : t,
      ),
    }));

    try {
      await fetchJson("/api/reconciliation/toggle-include/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          transaction_id: txId,
          session_id: state.session.id,
          included: newIncluded
        })
      });
      // Reload session stats
      loadSession(state.activeBankId!, state.activePeriodId);
    } catch (e) {
      console.error(e);
      // Revert?
    }
  };

  const onCompleteSession = async () => {
    if (!state.session) return;
    try {
      await fetchJson("/api/reconciliation/complete/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          session_id: state.session.id
        })
      });
      loadSession(state.activeBankId!, state.activePeriodId);
    } catch (e: any) {
      alert(e.message);
    }
  }

  const filteredTransactions = useMemo(() => {
    return state.transactions.filter((tx) => {
      const matchesStatus =
        state.statusFilter === "ALL" || tx.status === state.statusFilter;
      const matchesSearch = state.search
        ? (tx.description + " " + (tx.counterparty || "")).toLowerCase().includes(
          state.search.toLowerCase(),
        )
        : true;
      return matchesStatus && matchesSearch;
    });
  }, [state.transactions, state.statusFilter, state.search]);

  const disableComplete = !state.session || Math.abs(state.session.difference) > 0.01 || state.session.status === "COMPLETED";

  return (
    <div className="flex min-h-screen w-full flex-col bg-slate-50 text-slate-900">
      <PageHeader />

      <main className="flex-1 px-4 py-6 md:px-8">
        {state.error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-center gap-3 justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span>{state.error}</span>
            </div>
            <Button size="sm" onClick={loadConfig} className="rounded-full bg-red-600 hover:bg-red-700">
              Retry
            </Button>
          </div>
        )}

        {!state.loading && !state.error && state.bankAccounts.length === 0 && (
          <EmptyState canReconcile={state.canReconcile} reason={state.emptyReason} />
        )}

        <div className="flex flex-col gap-6">
          <SessionSetupBar
            state={state}
            onSelectBank={onSelectBank}
            onSelectPeriod={onSelectPeriod}
            onChangeSessionField={onChangeSessionField}
            onComplete={onCompleteSession}
            disableComplete={disableComplete}
          />

          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 xl:col-span-8 flex flex-col gap-6">
              <ProgressSummary session={state.session} />

              <section className="rounded-3xl border border-slate-200 bg-white shadow-sm flex flex-col min-h-[500px]">
                <div className="border-b border-slate-100 p-4 md:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-sm font-semibold tracking-wide text-slate-900">
                      Feed
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Transactions in this statement period
                    </p>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
                    <StatusFilter
                      active={state.statusFilter}
                      onChange={(status) => setState((prev) => ({ ...prev, statusFilter: status }))}
                    />

                    <div className="relative w-full sm:w-64">
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                      <input
                        type="search"
                        placeholder="Search..."
                        value={state.search}
                        onChange={(e) =>
                          setState((prev) => ({ ...prev, search: e.target.value }))
                        }
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900/5 focus:border-slate-300 transition-all"
                      />
                    </div>
                  </div>
                </div>

                <TransactionFeed
                  transactions={filteredTransactions}
                  onToggleInclude={onToggleInclude}
                  refresh={() => loadSession(state.activeBankId!, state.activePeriodId)}
                />
              </section>

              <AdjustmentsPanel session={state.session} onUpdate={() => loadSession(state.activeBankId!, state.activePeriodId)} />
            </div>

            <div className="col-span-12 xl:col-span-4 flex flex-col gap-6">
              <RightRail session={state.session} engineInsights={state.engineInsights} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function PageHeader() {
  return (
    <header className="sticky top-0 z-20 border-b bg-white/80 backdrop-blur-sm px-4 py-4 md:px-8">
      <div className="flex items-center gap-3">
        <div className="inline-flex items-center justify-center rounded-xl bg-emerald-100 p-2 text-emerald-700">
          <Check className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Reconciliation</h1>
          <p className="text-xs text-slate-500">Month-end check for your bank account</p>
        </div>
      </div>
    </header>
  );
}

interface SessionSetupBarProps {
  state: ReconciliationPageState;
  onSelectBank: (id: string) => void;
  onSelectPeriod: (id: string) => void;
  onChangeSessionField: (field: "beginningBalance" | "endingBalance", value: number) => void;
  onComplete: () => void;
  disableComplete: boolean;
}

function SessionSetupBar({
  state,
  onSelectBank,
  onSelectPeriod,
  onChangeSessionField,
  onComplete,
  disableComplete,
}: SessionSetupBarProps) {
  const { bankAccounts, activeBankId, periods, activePeriodId, session } = state;

  const activeBank = bankAccounts.find((b) => b.id === activeBankId) || null;
  const activePeriod = periods.find((p) => p.id === activePeriodId) || null;

  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm p-5 flex flex-col gap-5">
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
        <div className="flex flex-col gap-5 flex-1">
          <div className="flex flex-col md:flex-row gap-4 md:items-center">
            <div className="flex flex-col gap-1.5 flex-1 min-w-[200px]">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Bank account
              </label>
              <Select
                value={activeBankId || ""}
                onValueChange={onSelectBank}
                disabled={bankAccounts.length === 0}
              >
                <SelectTrigger className="h-10 rounded-xl border-slate-200 bg-slate-50 text-sm font-medium">
                  <SelectValue placeholder="Select account" />
                </SelectTrigger>
                <SelectContent>
                  {bankAccounts.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5 flex-1 min-w-[200px]">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Statement period
              </label>
              <Select
                value={activePeriodId || ""}
                onValueChange={onSelectPeriod}
                disabled={!activeBankId || periods.length === 0}
              >
                <SelectTrigger className="h-10 rounded-xl border-slate-200 bg-slate-50 text-sm font-medium">
                  <SelectValue placeholder="Select period" />
                </SelectTrigger>
                <SelectContent>
                  {periods.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      <span className="flex items-center gap-2">
                        {p.label}
                        {p.isLocked && <Lock className="h-3 w-3 text-slate-400" />}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Opening balance
              </span>
              <div className="relative">
                <input
                  type="number"
                  value={session?.beginningBalance ?? ""}
                  onChange={(e) => onChangeSessionField("beginningBalance", parseFloat(e.target.value))}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-medium outline-none focus:border-slate-400 focus:ring-0"
                  placeholder="0.00"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium">
                  {activeBank?.currency}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Statement ending balance
              </span>
              <div className="relative">
                <input
                  type="number"
                  value={session?.endingBalance ?? ""}
                  onChange={(e) => onChangeSessionField("endingBalance", parseFloat(e.target.value))}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-medium outline-none focus:border-slate-400 focus:ring-0"
                  placeholder="0.00"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium">
                  {activeBank?.currency}
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Difference
              </span>
              <div className={`relative flex items-center justify-between rounded-xl border px-3 py-2.5 ${!session || session.difference === 0
                  ? "border-emerald-200 bg-emerald-50/50 text-emerald-700"
                  : "border-amber-200 bg-amber-50/50 text-amber-700"
                }`}>
                <span className="text-sm font-bold">
                  {session ? session.difference.toFixed(2) : "—"}
                </span>
                <span className="text-xs font-medium opacity-70">{activeBank?.currency}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-stretch gap-2 lg:w-48 pt-6">
          <Button
            onClick={onComplete}
            disabled={disableComplete}
            className={`w-full rounded-xl h-11 font-semibold shadow-sm transition-all ${disableComplete
                ? "bg-slate-100 text-slate-400 hover:bg-slate-100"
                : "bg-slate-900 text-white hover:bg-slate-800 hover:shadow-md"
              }`}
          >
            {session?.status === "COMPLETED" ? "Period Completed" : "Complete period"}
          </Button>
          <Button
            variant="outline"
            className="w-full rounded-xl border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900"
          >
            Save draft
          </Button>
        </div>
      </div>
    </section>
  );
}

interface ProgressSummaryProps {
  session: RecoSession | null;
}

function ProgressSummary({ session }: ProgressSummaryProps) {
  if (!session) return null;

  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm p-5 flex flex-col gap-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Reconciliation Progress
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {session.reconciledPercent.toFixed(0)}%
            </span>
            <span className="text-sm text-slate-500">
              of {session.totalTransactions} transactions
            </span>
          </div>
        </div>

        <div className="flex-1 md:max-w-md flex flex-col justify-center">
          <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${session.reconciledPercent}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="h-full bg-emerald-500"
            />
          </div>
        </div>

        <div className="flex flex-col items-start md:items-end gap-1 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Cleared balance:</span>
            <span className="font-mono font-medium text-slate-900">
              {formatAmount(session.clearedBalance, session.bankAccount.currency)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Statement ending:</span>
            <span className="font-mono font-medium text-slate-900">
              {formatAmount(session.endingBalance, session.bankAccount.currency)}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

interface StatusFilterProps {
  active: RecoStatus | "ALL";
  onChange: (s: RecoStatus | "ALL") => void;
}

const STATUS_LABELS: Record<RecoStatus | "ALL", string> = {
  ALL: "All",
  NEW: "New",
  SUGGESTED: "Suggested",
  MATCHED: "Matched",
  MATCHED_SINGLE: "Matched",
  MATCHED_MULTI: "Matched",
  RECONCILED: "Reconciled",
  PARTIAL: "Partial",
  EXCLUDED: "Excluded",
  IGNORED: "Ignored",
};

function StatusFilter({ active, onChange }: StatusFilterProps) {
  const keys: Array<RecoStatus | "ALL"> = ["ALL", "NEW", "SUGGESTED", "MATCHED", "PARTIAL", "EXCLUDED"];
  return (
    <div className="inline-flex items-center rounded-xl border border-slate-200 bg-slate-50/50 p-1">
      {keys.map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${active === key
              ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
              : "text-slate-500 hover:text-slate-700 hover:bg-slate-100/50"
            }`}
        >
          {STATUS_LABELS[key]}
        </button>
      ))}
    </div>
  );
}

interface TransactionFeedProps {
  transactions: BankTransaction[];
  onToggleInclude: (id: string) => void;
  refresh: () => void;
}

function TransactionFeed({ transactions, onToggleInclude, refresh }: TransactionFeedProps) {
  if (!transactions.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="h-12 w-12 rounded-full bg-slate-50 flex items-center justify-center text-2xl">
          ✨
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-slate-900">
            Everything in this period is reconciled
          </p>
          <p className="text-xs text-slate-500 max-w-xs mx-auto">
            Great job! New imports and matches will appear here automatically.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col divide-y divide-slate-100">
      {transactions.map((tx) => (
        <TransactionRow key={tx.id} tx={tx} onToggleInclude={onToggleInclude} refresh={refresh} />
      ))}
    </div>
  );
}

interface TransactionRowProps {
  tx: BankTransaction;
  onToggleInclude: (id: string) => void;
  refresh: () => void;
}

function TransactionRow({ tx, onToggleInclude, refresh }: TransactionRowProps) {
  const hasSuggestion = (tx.status === "SUGGESTED" || tx.status === "NEW") && tx.match_confidence != null;
  const isReconciled = tx.status === "RECONCILED" || tx.status === "MATCHED" || tx.status === "MATCHED_SINGLE";

  const handleConfirm = async () => {
    try {
      // Confirm the suggestion
      // We need to fetch matches first to get the candidate? 
      // Or just assume the first one?
      // For simplicity, let's open the match drawer or call confirm if we have data.
      // The current API requires journal_entry_id.
      // Let's just trigger a refresh for now or implement full match logic.
      // Actually, let's use the existing confirm endpoint if we can.
      // But we don't have the candidate ID here.
      // So "Confirm" should probably fetch matches and confirm the top one.

      const matches = await fetchJson<any[]>(`/api/reconciliation/matches/?transaction_id=${tx.id}`);
      if (matches.length > 0) {
        const top = matches[0];
        await fetchJson(`/api/reconciliation/confirm-match/`, {
          method: "POST",
          body: JSON.stringify({
            bank_transaction_id: tx.id,
            journal_entry_id: top.journal_entry_id,
            match_confidence: top.confidence,
          }),
        });
        refresh();
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <article className={`group flex flex-col gap-3 p-4 transition-colors hover:bg-slate-50/50 ${!tx.includedInSession ? "opacity-60" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="pt-1">
            <input
              type="checkbox"
              checked={tx.includedInSession}
              onChange={() => onToggleInclude(tx.id)}
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20 cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500 w-12">
                {new Date(tx.date).toLocaleDateString(undefined, {
                  month: "short",
                  day: "2-digit",
                })}
              </span>
              <p className="text-sm font-medium text-slate-900 line-clamp-1">
                {tx.description}
              </p>
            </div>

            <div className="pl-14">
              {tx.counterparty && (
                <p className="text-xs text-slate-500 mb-1">{tx.counterparty}</p>
              )}

              {hasSuggestion && !isReconciled && (
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 border border-emerald-100">
                    <Check className="h-3 w-3" />
                    Suggested match · {(tx.match_confidence! * 100).toFixed(0)}%
                  </span>
                  {tx.match_type === "RULE" && (
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                      Rule
                    </span>
                  )}
                  {tx.engine_reason && (
                    <span className="text-[11px] text-slate-400 italic">
                      {tx.engine_reason}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 min-w-[140px]">
          <span className="text-sm font-bold text-slate-900 font-mono">
            {formatAmount(tx.amount, tx.currency)}
          </span>
          <StatusPill status={tx.status} />

          <div className="flex gap-2 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {hasSuggestion && !isReconciled ? (
              <>
                <Button
                  size="sm"
                  onClick={handleConfirm}
                  className="h-7 rounded-full bg-slate-900 px-3 text-[11px] font-medium text-white hover:bg-slate-800"
                >
                  Confirm
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 rounded-full border-slate-200 px-3 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                >
                  Review
                </Button>
              </>
            ) : !isReconciled ? (
              <>
                <Button
                  size="sm"
                  className="h-7 rounded-full bg-slate-900 px-3 text-[11px] font-medium text-white hover:bg-slate-800"
                >
                  Categorize
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 rounded-full border-slate-200 px-3 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                >
                  Match
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

interface StatusPillProps {
  status: RecoStatus;
}

function StatusPill({ status }: StatusPillProps) {
  const base = "inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide";
  switch (status) {
    case "NEW":
      return <span className={`${base} bg-slate-100 text-slate-600`}>New</span>;
    case "SUGGESTED":
      return <span className={`${base} bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100`}>Suggested</span>;
    case "MATCHED":
    case "MATCHED_SINGLE":
    case "MATCHED_MULTI":
    case "RECONCILED":
      return <span className={`${base} bg-sky-50 text-sky-700 ring-1 ring-sky-100`}>Matched</span>;
    case "PARTIAL":
      return <span className={`${base} bg-amber-50 text-amber-700 ring-1 ring-amber-100`}>Partial</span>;
    case "EXCLUDED":
      return <span className={`${base} bg-slate-50 text-slate-400`}>Excluded</span>;
    default:
      return null;
  }
}

interface AdjustmentsPanelProps {
  session: RecoSession | null;
  onUpdate: () => void;
}

function AdjustmentsPanel({ session, onUpdate }: AdjustmentsPanelProps) {
  const [type, setType] = useState("Bank fee");
  const [amount, setAmount] = useState("");
  const [account, setAccount] = useState("Service charges");
  const [loading, setLoading] = useState(false);

  if (!session) return null;

  const handleAdd = async () => {
    if (!amount) return;
    setLoading(true);
    try {
      await fetchJson("/api/reconciliation/create-adjustment/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          session_id: session.id,
          type,
          amount,
          account_name: account
        })
      });
      setAmount("");
      onUpdate();
    } catch (e) {
      console.error(e);
      alert("Failed to add adjustment");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm p-5 flex flex-col gap-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-slate-900">
            Adjustments
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Record bank fees, interest and small final adjustments.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Type</label>
          <Select value={type} onValueChange={setType}>
            <SelectTrigger className="h-10 rounded-xl border-slate-200 bg-slate-50 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Bank fee">Bank fee</SelectItem>
              <SelectItem value="Interest income">Interest income</SelectItem>
              <SelectItem value="Other adjustment">Other adjustment</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Amount</label>
          <div className="relative">
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-medium outline-none focus:border-slate-400 focus:ring-0"
              placeholder="0.00"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium">
              {session.bankAccount.currency}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Account</label>
          <Select value={account} onValueChange={setAccount}>
            <SelectTrigger className="h-10 rounded-xl border-slate-200 bg-slate-50 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Service charges">Service charges</SelectItem>
              <SelectItem value="Interest income">Interest income</SelectItem>
              <SelectItem value="Suspense">Suspense</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex justify-between items-center mt-2 pt-4 border-t border-slate-100">
        <p className="text-[11px] text-slate-500">
          Adjustments will be posted to your ledger and included in the cleared balance.
        </p>
        <Button
          onClick={handleAdd}
          disabled={loading || !amount}
          className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800"
        >
          {loading ? "Adding..." : "Add adjustment"}
        </Button>
      </div>
    </section>
  );
}

interface RightRailProps {
  session: RecoSession | null;
  engineInsights: EngineInsights | null;
}

function RightRail({ session, engineInsights }: RightRailProps) {
  return (
    <aside className="flex flex-col gap-6">
      <div className="rounded-3xl border border-slate-200 bg-white shadow-sm p-5 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-slate-900">
          <Info className="h-4 w-4 text-emerald-500" />
          <h3 className="text-sm font-semibold">Session health</h3>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          Keep this tab open while you reconcile. Matches and splits save automatically.
          The engine runs in the background to find new suggestions.
        </p>

        <div className="mt-2 rounded-xl bg-slate-50 p-3 text-xs text-slate-600 space-y-1.5">
          <div className="flex justify-between">
            <span>Engine status:</span>
            <span className="font-medium text-emerald-700">Active</span>
          </div>
          <div className="flex justify-between">
            <span>Last sync:</span>
            <span>Just now</span>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white shadow-sm p-5 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-slate-900">
          <Calendar className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-semibold">Timeline</h3>
        </div>
        {session ? (
          <ul className="mt-1 text-xs text-slate-600 space-y-3">
            <li className="flex justify-between items-center">
              <span>Period</span>
              <span className="font-medium text-slate-900">{session.period.label}</span>
            </li>
            <li className="flex justify-between items-center">
              <span>Total transactions</span>
              <span className="font-medium text-slate-900">{session.totalTransactions}</span>
            </li>
            <li className="flex justify-between items-center">
              <span>Unreconciled</span>
              <span className="font-medium text-slate-900">{session.unreconciledCount}</span>
            </li>
            <li className="flex justify-between items-center">
              <span>Status</span>
              <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider">
                {session.status.replace("_", " ")}
              </Badge>
            </li>
          </ul>
        ) : (
          <p className="text-xs text-slate-500">Select a bank and period to see details.</p>
        )}
      </div>

      <div className="rounded-3xl border border-slate-200 bg-slate-50 shadow-sm p-5 flex flex-col gap-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Audit ready
        </h3>
        <p className="text-xs text-slate-600 leading-relaxed">
          Every match, split and adjustment is stored in the history for this period. Use the
          transaction drawer to see the audit trail for any line.
        </p>
      </div>
    </aside>
  );
}
