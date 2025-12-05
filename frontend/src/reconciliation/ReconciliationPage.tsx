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
import { ReportExportButton } from "../reports/ReportExportButton";
import CompanionStrip from "../companion/CompanionStrip";

// --- Types ---

export type RecoStatus = "new" | "matched" | "partial" | "excluded";
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
  reconciledCount?: number;
  excludedCount?: number;
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
  uiStatus?: "NEW" | "MATCHED" | "PARTIAL" | "EXCLUDED";
  isCleared?: boolean;
  reconciliationStatus?: "reconciled" | "unreconciled";
  match_confidence?: number | null;
  engine_reason?: string | null;
  matchCandidates?: Array<{ journal_entry_id: number; confidence: number; reason?: string }>;
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
  statusFilter: RecoStatus | "all";
  search: string;
  loading: boolean;
  error: string | null;
  actionError: string | null;
  completionError: string | null;
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

  try {
    return await res.json();
  } catch {
    // Some endpoints may return empty body on success
    return {} as T;
  }
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
        <a
          href="/bank-accounts/new/?returnTo=/reconciliation"
          className="inline-flex items-center justify-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 transition-colors"
        >
          + Add a bank account
        </a>
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
    statusFilter: "all",
    search: "",
    loading: false,
    error: null,
    actionError: null,
    completionError: null,
  });

  const setActionError = (msg: string | null) => {
    setState(prev => ({ ...prev, actionError: msg }));
  };

  const activeBank = state.bankAccounts.find((b) => b.id === state.activeBankId) || null;
  const activePeriod = state.periods.find((p) => p.id === state.activePeriodId) || null;
  const isLocked = state.session?.status === "COMPLETED";

  // Initial Load
  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (state.activeBankId) {
      loadPeriods(state.activeBankId);
    }
  }, [state.activeBankId]);

  useEffect(() => {
    if (state.activeBankId && state.activePeriodId) {
      // Clear previous state and reload session when bank/period changes
      setState(prev => ({
        ...prev,
        session: null,
        transactions: [],
        loading: true,
        completionError: null,
      }));
      loadSession(state.activeBankId, state.activePeriodId);
    }
  }, [state.activeBankId, state.activePeriodId]);

  async function loadAccounts() {
    setState(prev => ({ ...prev, loading: true, error: null, completionError: null, actionError: null }));
    try {
      const accounts = await fetchJson<BankAccountSummary[]>("/api/reconciliation/accounts/");
      setState(prev => ({
        ...prev,
        bankAccounts: accounts,
        activeBankId: prev.activeBankId || (accounts[0]?.id ?? null),
        canReconcile: accounts.length > 0,
        emptyReason: accounts.length ? null : "no_bank_accounts",
        loading: false
      }));
    } catch (e: any) {
      console.error(e);
      setState(prev => ({
        ...prev,
        loading: false,
        error: e.message,
        bankAccounts: [],
        canReconcile: false,
        emptyReason: e.message
      }));
    }
  }

  const mapPeriod = (p: any): RecoPeriodOption => ({
    id: String(p.id),
    label: p.label || `${p.start_date || p.startDate}`,
    startDate: p.start_date || p.startDate || "",
    endDate: p.end_date || p.endDate || "",
    isCurrent: Boolean(p.is_current ?? p.isCurrent),
    isLocked: Boolean(p.is_locked ?? p.isLocked),
  });

  async function loadPeriods(bankId: string) {
    setState(prev => ({ ...prev, loading: true, error: null, actionError: null, completionError: null, periods: [], activePeriodId: null, session: null, transactions: [] }));
    try {
      const raw = await fetchJson<any>(`/api/reconciliation/accounts/${bankId}/periods/`);
      const source = Array.isArray(raw) ? raw : raw?.periods || [];
      const periods: RecoPeriodOption[] = source.map(mapPeriod);
      const nextPeriod = periods.length > 0 ? periods[0].id : null;
      setState(prev => ({
        ...prev,
        periods,
        activePeriodId: nextPeriod,
        loading: false,
      }));
    } catch (e: any) {
      console.error(e);
      setState(prev => ({ ...prev, loading: false, error: e.message, periods: [], activePeriodId: null }));
    }
  }

  async function loadSession(bankId: string, periodId: string | null) {
    if (!periodId) return;
    const period = state.periods.find(p => p.id === periodId);
    if (!period) return;
    setState(prev => ({ ...prev, loading: true, error: null, actionError: null, completionError: null }));
    try {
      const params = new URLSearchParams({
        account: bankId,
        start: period.startDate,
        end: period.endDate,
      });
      const data = await fetchJson<any>(`/api/reconciliation/session/?${params.toString()}`);
      const periods = (data.periods || state.periods || []).map(mapPeriod);
      const responsePeriod = data.period
        ? mapPeriod({
          id: data.period.id || period.id,
          label: data.period.label || period.label,
          start_date: data.period.start_date || data.period.startDate || period.startDate,
          end_date: data.period.end_date || data.period.endDate || period.endDate,
          is_current: data.period.is_current ?? data.period.isCurrent ?? period.isCurrent,
          is_locked: data.period.is_locked ?? data.period.isLocked ?? period.isLocked,
        })
        : null;
      const activePeriod = periods.find((p: RecoPeriodOption) => p.id === periodId) || responsePeriod || period;

      const feed = data.feed || {};
      const combined = ([] as any[]).concat(feed.new || [], feed.matched || [], feed.partial || [], feed.excluded || []);

      // Fetch match candidates for each transaction
      const transactions: BankTransaction[] = await Promise.all(
        combined.map(async (t: any) => {
          const recStatusRaw = t.reconciliation_status || "unreconciled";
          const recStatusLower = String(recStatusRaw).toLowerCase();
          const reconciliationStatus =
            recStatusLower === "reconciled" || recStatusLower === "reco_status_reconciled"
              ? "reconciled"
              : "unreconciled";
          const uiStatus = (t.ui_status || t.status || "NEW").toString().toUpperCase();
          const recoStatusLower = uiStatus.toLowerCase() as RecoStatus;

          // Fetch candidates only for unmatched, non-excluded transactions
          let matchCandidates: Array<{ journal_entry_id: number; confidence: number; reason?: string }> = [];
          if (reconciliationStatus === "unreconciled" && recoStatusLower !== "excluded" && recoStatusLower !== "matched") {
            try {
              const candidates = await fetchJson<any[]>(`/api/reconciliation/matches/?transaction_id=${t.id}`);
              matchCandidates = candidates.map((c: any) => ({
                journal_entry_id: c.journal_entry_id,
                confidence: c.confidence || 1.0,
                reason: c.reason,
              }));
            } catch (e) {
              console.warn(`Failed to fetch candidates for tx ${t.id}:`, e);
            }
          }

          return {
            id: String(t.id),
            date: t.date,
            description: t.description,
            counterparty: t.counterparty,
            amount: Number(t.amount),
            currency: t.currency || data.bank_account?.currency || "USD",
            status: recoStatusLower,
            uiStatus: uiStatus as BankTransaction["uiStatus"],
            isCleared: Boolean(t.is_cleared),
            reconciliationStatus,
            match_confidence: t.match_confidence,
            engine_reason: t.engine_reason,
            matchCandidates,
            includedInSession: t.includedInSession ?? uiStatus !== "EXCLUDED",
          };
        })
      );

      const sessionData = data.session || {};
      const clearedBalance = Number(
        sessionData.cleared_balance ??
        sessionData.clearedBalance ??
        sessionData.ledger_ending_balance ??
        0
      );

      // Use backend values for progress calculation
      const totalTransactions = Number(sessionData.total_transactions ?? transactions.length);
      const reconciledCount = Number(sessionData.reconciled_count ?? 0);
      const excludedCount = Number(sessionData.excluded_count ?? 0);
      const unreconciledCount = Number(sessionData.unreconciled_count ?? totalTransactions - reconciledCount);
      const reconciledPercent = Number(
        sessionData.reconciled_percent ??
        (totalTransactions ? ((reconciledCount + excludedCount) / totalTransactions) * 100 : 0)
      );

      const session: RecoSession = {
        id: String(sessionData.id || ""),
        status: (sessionData.status || "DRAFT") as RecoSessionStatus,
        bankAccount: {
          id: data.bank_account?.id ? String(data.bank_account.id) : bankId,
          name: data.bank_account?.name || "",
          currency: data.bank_account?.currency || "USD",
        },
        period: activePeriod,
        beginningBalance: Number(sessionData.opening_balance ?? 0),
        endingBalance: Number(sessionData.statement_ending_balance ?? 0),
        clearedBalance,
        difference: Number(sessionData.difference ?? 0),
        reconciledPercent: reconciledPercent,
        totalTransactions,
        reconciledCount,
        excludedCount,
        unreconciledCount,
      };

      setState((prev) => ({
        ...prev,
        periods,
        activePeriodId: activePeriod?.id || periodId,
        session,
        transactions,
        loading: false,
        actionError: null,
      }));
    } catch (e: any) {
      console.error(e);
      const msg = e?.message || "Failed to load session.";
      setState(prev => ({ ...prev, loading: false, error: msg, actionError: msg, transactions: [], session: null }));
    }
  }

  const onSelectBank = (bankId: string) => {
    setState((prev) => ({ ...prev, activeBankId: bankId, activePeriodId: null, error: null, actionError: null }));
  };

  const onSelectPeriod = (periodId: string) => {
    setState((prev) => ({ ...prev, activePeriodId: periodId, actionError: null }));
  };

  const onChangeSessionField = async (field: "beginningBalance" | "endingBalance", value: number) => {
    if (isLocked) return;
    if (Number.isNaN(value)) return;
    setState((prev) =>
      prev.session
        ? {
          ...prev,
          session: { ...prev.session, [field]: value },
        }
        : prev,
    );

    if (state.session) {
      try {
        const payload: any = {};
        if (field === "beginningBalance") payload.opening_balance = value;
        if (field === "endingBalance") payload.statement_ending_balance = value;
        await fetchJson(`/api/reconciliation/session/${state.session.id}/set_statement_balance/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify(payload)
        });
        if (state.activeBankId && state.activePeriodId) {
          loadSession(state.activeBankId, state.activePeriodId);
        }
      } catch (e) {
        console.error(e);
      }
    }
  };

  const onToggleInclude = async (txId: string) => {
    if (isLocked) return;
    const tx = state.transactions.find(t => t.id === txId);
    if (!tx || !state.session || !state.activeBankId || !state.activePeriodId) return;

    const shouldExclude = tx.includedInSession;
    await onExclude(txId, shouldExclude);
  };

  const onExclude = async (txId: string, shouldExclude: boolean) => {
    if (isLocked) return;
    if (!state.session || !state.activeBankId || !state.activePeriodId) return;
    try {
      setActionError(null);
      await fetchJson(`/api/reconciliation/session/${state.session.id}/exclude/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ transaction_id: txId, excluded: shouldExclude }),
      });

      // Refresh session and feed after exclude
      await loadSession(state.activeBankId, state.activePeriodId);
    } catch (e: any) {
      console.error(e);
      setActionError(e?.message || "Could not update transaction.");
    }
  };

  const onMatch = async (txId: string) => {
    if (isLocked) return;
    if (!state.session || !state.activeBankId || !state.activePeriodId) return;

    const tx = state.transactions.find(t => t.id === txId);
    if (!tx || !tx.matchCandidates || tx.matchCandidates.length === 0) {
      // No alert - inline warning is shown in the UI
      return;
    }

    try {
      setActionError(null);
      const chosen = tx.matchCandidates[0];
      await fetchJson(`/api/reconciliation/confirm-match/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          bank_transaction_id: txId,
          journal_entry_id: chosen.journal_entry_id,
          match_confidence: chosen.confidence || 1.0,
        }),
      });

      // Refresh session and feed after match
      await loadSession(state.activeBankId, state.activePeriodId);
    } catch (e: any) {
      console.error(e);
      setActionError(e?.message || "Could not match transaction.");
    }
  };

  const onAddAsNew = async (txId: string) => {
    if (isLocked) return;
    if (!state.session || !state.activeBankId || !state.activePeriodId) return;

    try {
      setActionError(null);
      // Call the backend to create a new transaction from this bank line
      // This will categorize it and mark as reconciled
      await fetchJson(`/api/reconciliation/add-as-new/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          bank_transaction_id: txId,
          session_id: state.session.id,
        }),
      });

      // Refresh session and feed after adding as new
      await loadSession(state.activeBankId, state.activePeriodId);
    } catch (e: any) {
      console.error(e);
      setActionError(e?.message || "Could not add transaction.");
    }
  };

  const onUnmatch = async (txId: string) => {
    if (isLocked) return;
    if (!state.session || !state.activeBankId || !state.activePeriodId) return;
    try {
      setActionError(null);
      await fetchJson(`/api/reconciliation/session/${state.session.id}/unmatch/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ transaction_id: txId }),
      });

      // Refresh session and feed after unmatch
      await loadSession(state.activeBankId, state.activePeriodId);
    } catch (e: any) {
      console.error(e);
      setActionError(e?.message || "Could not unmatch transaction.");
    }
  };

  const onCompleteSession = async () => {
    if (!state.session || !state.activeBankId || !state.activePeriodId || isLocked) return;
    try {
      setState(prev => ({ ...prev, completionError: null, actionError: null, loading: true }));
      await fetchJson(`/api/reconciliation/sessions/${state.session.id}/complete/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
      });
      await loadSession(state.activeBankId, state.activePeriodId);
    } catch (e: any) {
      const msg = e?.message || "Could not complete period, please try again.";
      setState(prev => ({ ...prev, completionError: msg, actionError: msg, loading: false }));
    }
  }

  const onReopenSession = async () => {
    if (!state.session || !state.activeBankId || !state.activePeriodId) return;
    const confirmed = window.confirm("Reopen this statement period for editing?");
    if (!confirmed) return;
    try {
      setState(prev => ({ ...prev, loading: true, actionError: null, completionError: null }));
      await fetchJson(`/api/reconciliation/sessions/${state.session.id}/reopen/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
      });
      await loadSession(state.activeBankId, state.activePeriodId);
    } catch (e: any) {
      console.error(e);
      setActionError(e?.message || "Could not reopen period.");
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  const filteredTransactions = useMemo(() => {
    return state.transactions.filter((tx) => {
      const txUiStatus = (tx.uiStatus || tx.status || "NEW").toLowerCase() as RecoStatus;
      const matchesStatus =
        state.statusFilter === "all" || txUiStatus === state.statusFilter;
      const matchesSearch = state.search
        ? (tx.description + " " + (tx.counterparty || "")).toLowerCase().includes(
          state.search.toLowerCase(),
        )
        : true;
      return matchesStatus && matchesSearch;
    });
  }, [state.transactions, state.statusFilter, state.search]);

  const differenceValue = Number(state.session?.difference ?? 0);
  const differenceNonZero = Math.abs(differenceValue) > 0.01;
  const hasUnreconciled = (state.session?.unreconciledCount ?? 0) > 0;
  const disableComplete = state.loading || !state.session || differenceNonZero || hasUnreconciled || isLocked;
  const completionDisabledReason = !state.session
    ? null
    : isLocked
      ? "This period is already completed."
      : differenceNonZero
        ? "Difference must be zero before completing this period."
        : hasUnreconciled
          ? "Reconcile or exclude all transactions before completing."
          : null;

  return (
    <div className="flex min-h-screen w-full flex-col bg-slate-50 text-slate-900">
      <PageHeader session={state.session} />
      <div className="px-4 md:px-8 mt-2 text-xs text-slate-500">
        <span className="font-semibold text-slate-700">Bank account:</span> {activeBank?.name || "—"} ·{" "}
        <span className="font-semibold text-slate-700">Statement period:</span>{" "}
        {activePeriod
          ? `${new Date(activePeriod.startDate).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })} – ${new Date(activePeriod.endDate).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}`
          : "—"}
        {state.session && (
          <span className="ml-3 inline-flex items-center rounded-full bg-slate-100 px-2 py-[2px] text-[11px] font-semibold uppercase tracking-wide text-slate-600">
            {state.session.status}
          </span>
        )}
      </div>

      <main className="flex-1 px-4 py-6 md:px-8">
        <CompanionStrip context="reconciliation" className="mb-6" />

        {state.error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-center gap-3 justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span>{state.error}</span>
            </div>
            <Button size="sm" onClick={loadAccounts} className="rounded-full bg-red-600 hover:bg-red-700">
              Retry
            </Button>
          </div>
        )}
        {state.actionError && !state.error && (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 flex items-center gap-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span>{state.actionError}</span>
            </div>
            <button
              type="button"
              className="ml-auto text-[11px] font-semibold text-amber-700 hover:text-amber-900"
              onClick={() => setActionError(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {!state.loading && !state.error && state.bankAccounts.length === 0 && (
          <EmptyState canReconcile={state.canReconcile} reason={state.emptyReason} />
        )}

        {!state.loading && !state.error && state.bankAccounts.length > 0 && state.periods.length === 0 && (
          <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
            No statement periods found for this bank account yet. Import a statement to start reconciling.
          </div>
        )}

        <div className="flex flex-col gap-6">
          <SessionSetupBar
            state={state}
            isLocked={isLocked}
            onSelectBank={onSelectBank}
            onSelectPeriod={onSelectPeriod}
            onChangeSessionField={onChangeSessionField}
            onComplete={onCompleteSession}
            onReopen={onReopenSession}
            disableComplete={disableComplete}
            completionError={state.completionError}
            completeDisabledReason={completionDisabledReason}
            activeBank={activeBank}
            activePeriod={activePeriod}
          />

          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 xl:col-span-8 flex flex-col gap-6">
              <ProgressSummary session={state.session} />

              <section className="rounded-3xl border border-slate-200 bg-white shadow-sm flex flex-col">
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

                <ScrollArea className="max-h-[600px]">
                  <TransactionFeed
                    transactions={filteredTransactions}
                    activeFilter={state.statusFilter}
                    onToggleInclude={onToggleInclude}
                    onMatch={onMatch}
                    onAddAsNew={onAddAsNew}
                    onUnmatch={onUnmatch}
                    isLocked={isLocked}
                    totalCount={state.session?.totalTransactions ?? state.transactions.length}
                  />
                </ScrollArea>
              </section>

              <AdjustmentsPanel session={state.session} isLocked={isLocked} onUpdate={() => loadSession(state.activeBankId!, state.activePeriodId)} onError={setActionError} />
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

function PageHeader({ session }: { session: RecoSession | null }) {
  const reportUrl = session ? `/reconciliation/${session.id}/report/` : undefined;

  return (
    <header className="sticky top-0 z-20 border-b bg-white/80 backdrop-blur-sm px-4 py-4 md:px-8">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="inline-flex items-center justify-center rounded-xl bg-emerald-100 p-2 text-emerald-700">
            <Check className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Reconciliation</h1>
            <p className="text-xs text-slate-500">Month-end check for your bank account</p>
          </div>
          {session && (
            <Badge variant="outline" className="rounded-full text-[10px] font-semibold uppercase tracking-wider">
              {session.status === "COMPLETED" ? "Completed" : session.status?.replace("_", " ")}
            </Badge>
          )}
        </div>

        {session && reportUrl && (
          <ReportExportButton to={reportUrl} />
        )}
      </div>
    </header>
  );
}

interface SessionSetupBarProps {
  state: ReconciliationPageState;
  isLocked: boolean;
  onSelectBank: (id: string) => void;
  onSelectPeriod: (id: string) => void;
  onChangeSessionField: (field: "beginningBalance" | "endingBalance", value: number) => void;
  onComplete: () => void;
  onReopen?: () => void;
  disableComplete: boolean;
  completionError?: string | null;
  completeDisabledReason?: string | null;
  activeBank: BankAccountSummary | null;
  activePeriod: RecoPeriodOption | null;
}

function SessionSetupBar({
  state,
  isLocked,
  onSelectBank,
  onSelectPeriod,
  onChangeSessionField,
  onComplete,
  onReopen,
  disableComplete,
  completionError,
  completeDisabledReason,
  activeBank,
  activePeriod,
}: SessionSetupBarProps) {
  const { bankAccounts, activeBankId, periods, activePeriodId, session } = state;

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
                  disabled={isLocked}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-medium outline-none focus:border-slate-400 focus:ring-0 disabled:opacity-70"
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
                  disabled={isLocked}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-medium outline-none focus:border-slate-400 focus:ring-0 disabled:opacity-70"
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
              <span className="text-[11px] text-slate-500">
                Difference = Statement ending – Cleared balance.
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-stretch gap-2 lg:w-48 pt-6">
          <Button
            onClick={onComplete}
            disabled={disableComplete}
            title={completeDisabledReason || undefined}
            className={`w-full rounded-xl h-11 font-semibold shadow-sm transition-all ${disableComplete
              ? "bg-slate-100 text-slate-400 hover:bg-slate-100"
              : "bg-slate-900 text-white hover:bg-slate-800 hover:shadow-md"
              }`}
          >
            {session?.status === "COMPLETED" ? "Period Completed" : "Complete period"}
          </Button>
          {session?.status === "COMPLETED" && (
            <Button
              variant="outline"
              onClick={onReopen}
              className="w-full rounded-xl border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-60"
            >
              Reopen period
            </Button>
          )}
          <Button
            variant="outline"
            disabled={isLocked}
            className="w-full rounded-xl border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-60"
          >
            Save draft
          </Button>
          {session?.status === "COMPLETED" && (
            <p className="text-[11px] text-slate-500 leading-snug">This period is locked. Reopen the period to make changes.</p>
          )}
          {completionError && (
            <p className="text-xs text-red-600 leading-snug">{completionError}</p>
          )}
          {!completionError && completeDisabledReason && disableComplete && (
            <p className="text-[11px] text-slate-500 leading-snug">{completeDisabledReason}</p>
          )}
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

  const differenceCalm = Math.abs(session.difference) <= 0.01;
  const differenceToneClass = differenceCalm
    ? "border-emerald-200 bg-emerald-50/50 text-emerald-700"
    : "border-amber-200 bg-amber-50/50 text-amber-700";
  const differenceHelper = differenceCalm
    ? "Balances align for this statement period."
    : "You still have unreconciled transactions in this period.";

  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm p-5">
      {/* Header with progress percentage */}
      <div className="flex items-baseline gap-2 mb-4">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Reconciliation Progress
        </span>
        <span className="text-2xl font-bold text-slate-900 ml-auto">
          {session.reconciledPercent.toFixed(0)}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${session.reconciledPercent}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="h-full bg-emerald-500"
          />
        </div>
      </div>

      {/* Main content - two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Financial Summary */}
        <div className="flex flex-col gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Financial Summary
          </h3>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">Cleared balance</span>
              <span className="font-mono font-semibold text-slate-900">
                {formatAmount(session.clearedBalance, session.bankAccount.currency)}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">Statement ending</span>
              <span className="font-mono font-semibold text-slate-900">
                {formatAmount(session.endingBalance, session.bankAccount.currency)}
              </span>
            </div>

            <Separator />

            <div className={`flex items-center justify-between rounded-xl border px-3 py-2.5 ${differenceToneClass}`}>
              <span className="text-sm font-medium">Difference</span>
              <span className="font-mono font-bold text-lg">
                {formatAmount(session.difference, session.bankAccount.currency)}
              </span>
            </div>
          </div>

          <p className="text-[11px] text-slate-500 leading-relaxed">
            {differenceHelper}
          </p>
        </div>

        {/* Right: Transaction Summary */}
        <div className="flex flex-col gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Transaction Summary
          </h3>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 px-3 py-3">
              <div className="text-[11px] font-medium text-emerald-700 uppercase tracking-wide mb-1">
                Reconciled
              </div>
              <div className="text-2xl font-bold text-emerald-900">
                {session.reconciledCount ?? 0}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="text-[11px] font-medium text-slate-600 uppercase tracking-wide mb-1">
                Excluded
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {session.excludedCount ?? 0}
              </div>
            </div>

            <div className="rounded-xl border border-amber-100 bg-amber-50/50 px-3 py-3">
              <div className="text-[11px] font-medium text-amber-700 uppercase tracking-wide mb-1">
                Unreconciled
              </div>
              <div className="text-2xl font-bold text-amber-900">
                {session.unreconciledCount}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="text-[11px] font-medium text-slate-600 uppercase tracking-wide mb-1">
                Total
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {session.totalTransactions}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

interface StatusFilterProps {
  active: RecoStatus | "all";
  onChange: (s: RecoStatus | "all") => void;
}

const STATUS_LABELS: Record<RecoStatus | "all", string> = {
  all: "All",
  new: "New",
  matched: "Matched",
  partial: "Partial",
  excluded: "Excluded",
};

function StatusFilter({ active, onChange }: StatusFilterProps) {
  const keys: Array<RecoStatus | "all"> = ["all", "new", "matched", "partial", "excluded"];
  return (
    <div className="inline-flex items-center rounded-xl border border-slate-200 bg-slate-50/50 p-1">
      {keys.map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          className={`rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all whitespace-nowrap ${active === key
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
  activeFilter: RecoStatus | "all";
  onToggleInclude: (id: string) => void;
  onMatch: (id: string) => void;
  onAddAsNew: (id: string) => void;
  onUnmatch: (id: string) => void;
  isLocked: boolean;
  totalCount: number;
}

function TransactionFeed({ transactions, onToggleInclude, onMatch, onAddAsNew, onUnmatch, isLocked, activeFilter, totalCount }: TransactionFeedProps) {
  if (totalCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="h-12 w-12 rounded-full bg-slate-50 flex items-center justify-center text-2xl">
          📄
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-slate-900">
            No bank transactions for this statement period yet.
          </p>
          <p className="text-xs text-slate-500 max-w-xs mx-auto">
            Import a statement or sync your bank feed to start reconciling this period.
          </p>
        </div>
      </div>
    );
  }

  if (!transactions.length) {
    const filterCopy: Record<RecoStatus | "all", string> = {
      all: "No transactions in this period.",
      new: "No new transactions in this period.",
      matched: "No matched transactions in this period.",
      partial: "No partial transactions in this period.",
      excluded: "No excluded transactions in this period.",
    };
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="h-12 w-12 rounded-full bg-slate-50 flex items-center justify-center text-2xl">
          ✨
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-slate-900">{filterCopy[activeFilter]}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col divide-y divide-slate-100">
      {transactions.map((tx) => (
        <TransactionRow
          key={tx.id}
          tx={tx}
          onToggleInclude={onToggleInclude}
          onMatch={onMatch}
          onAddAsNew={onAddAsNew}
          onUnmatch={onUnmatch}
          isLocked={isLocked}
        />
      ))}
    </div>
  );
}

interface TransactionRowProps {
  tx: BankTransaction;
  onToggleInclude: (id: string) => void;
  onMatch: (id: string) => void;
  onAddAsNew: (id: string) => void;
  onUnmatch: (id: string) => void;
  isLocked: boolean;
}

function TransactionRow({ tx, onToggleInclude, onMatch, onAddAsNew, onUnmatch, isLocked }: TransactionRowProps) {
  const uiStatus = (tx.uiStatus || tx.status || "NEW").toUpperCase();
  const isExcluded = uiStatus === "EXCLUDED";
  const isMatched = uiStatus === "MATCHED";
  const isPartial = uiStatus === "PARTIAL";
  const isCleared = Boolean(tx.isCleared);
  const isReconciled = uiStatus === "MATCHED" || uiStatus === "PARTIAL" || isExcluded;
  const hasCandidate = tx.matchCandidates && tx.matchCandidates.length > 0;
  const actionsDisabled = isLocked;
  const isPositive = tx.amount >= 0;

  // Status colors for left border
  const statusBorderColor = isMatched
    ? "border-l-emerald-500"
    : isPartial
      ? "border-l-amber-500"
      : isExcluded
        ? "border-l-slate-300"
        : "border-l-slate-200";

  return (
    <article
      className={`
        group flex items-center gap-4 px-4 py-3 border-l-4 ${statusBorderColor}
        transition-colors hover:bg-slate-50/80
        ${!tx.includedInSession ? "opacity-50" : ""}
      `}
    >
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={tx.includedInSession}
        onChange={() => onToggleInclude(tx.id)}
        disabled={actionsDisabled}
        className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 shrink-0"
      />

      {/* Date */}
      <div className="w-16 shrink-0">
        <span className="text-xs font-medium text-slate-500">
          {new Date(tx.date).toLocaleDateString(undefined, {
            month: "short",
            day: "2-digit",
          })}
        </span>
      </div>

      {/* Description & Counterparty */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-900 truncate">
          {tx.description}
        </p>
        {tx.counterparty && (
          <p className="text-xs text-slate-500 truncate">{tx.counterparty}</p>
        )}
      </div>

      {/* Amount */}
      <div className="w-28 shrink-0 text-right">
        <span className={`text-sm font-bold font-mono ${isPositive ? "text-emerald-600" : "text-slate-900"}`}>
          {formatAmount(tx.amount, tx.currency)}
        </span>
      </div>

      {/* Status Badge */}
      <div className="w-24 shrink-0 flex justify-center">
        {isMatched ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-700 ring-1 ring-emerald-200">
            <Check className="h-3 w-3" />
            Matched
          </span>
        ) : isPartial ? (
          <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold uppercase text-amber-700 ring-1 ring-amber-200">
            Partial
          </span>
        ) : isExcluded ? (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase text-slate-500">
            Excluded
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full bg-sky-50 px-2.5 py-1 text-[10px] font-bold uppercase text-sky-700 ring-1 ring-sky-200">
            New
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="w-24 shrink-0 flex justify-end gap-2">
        {!isMatched && !isExcluded && uiStatus !== "MATCHED" && uiStatus !== "PARTIAL" ? (
          hasCandidate ? (
            <Button
              size="sm"
              onClick={() => onMatch(tx.id)}
              disabled={actionsDisabled}
              className="h-7 rounded-full bg-slate-900 px-3 text-[11px] font-medium text-white hover:bg-slate-800"
            >
              Match
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onAddAsNew(tx.id)}
              disabled={actionsDisabled}
              className="h-7 rounded-full border-slate-200 px-3 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              Add new
            </Button>
          )
        ) : null}
        {isMatched && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onUnmatch(tx.id)}
            disabled={actionsDisabled}
            className="h-7 rounded-full border-slate-200 px-3 text-[11px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            Undo
          </Button>
        )}
      </div>
    </article>
  );
}

interface StatusPillProps {
  status: RecoStatus;
  label?: string;
}

function StatusPill({ status, label }: StatusPillProps) {
  const base = "inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide";
  switch (status) {
    case "new":
      return <span className={`${base} bg-slate-100 text-slate-600`}>{label || "New"}</span>;
    case "matched":
      return <span className={`${base} bg-sky-50 text-sky-700 ring-1 ring-sky-100`}>{label || "Matched"}</span>;
    case "partial":
      return <span className={`${base} bg-amber-50 text-amber-700 ring-1 ring-amber-100`}>{label || "Partial"}</span>;
    case "excluded":
      return <span className={`${base} bg-slate-50 text-slate-400`}>{label || "Excluded"}</span>;
    default:
      return null;
  }
}

interface AdjustmentsPanelProps {
  session: RecoSession | null;
  isLocked: boolean;
  onUpdate: () => void;
  onError: (msg: string | null) => void;
}

function AdjustmentsPanel({ session, isLocked, onUpdate, onError }: AdjustmentsPanelProps) {
  const [type, setType] = useState("Bank fee");
  const [amount, setAmount] = useState("");
  const [account, setAccount] = useState("Service charges");
  const [loading, setLoading] = useState(false);

  const sanitizeAmount = (value: string) => {
    const cleaned = value.replace(/[^0-9.-]/g, "");
    const negative = cleaned.startsWith("-");
    const unsigned = cleaned.replace(/-/g, "");
    const parts = unsigned.split(".");
    const head = parts.shift() || "";
    const decimal = parts.length ? parts.join("") : "";
    const combined = decimal ? `${head || "0"}.${decimal}` : head;
    if (!combined && negative) return "-";
    return negative ? `-${combined}` : combined;
  };

  const handleAmountChange = (val: string) => {
    setAmount(sanitizeAmount(val));
  };

  const handleAmountBlur = () => {
    if (!amount) return;
    const parsed = Number(amount);
    if (Number.isNaN(parsed)) {
      setAmount("");
      return;
    }
    setAmount(parsed.toFixed(2));
  };

  if (!session) return null;

  const handleAdd = async () => {
    if (isLocked) return;
    const cleanedAmount = sanitizeAmount(amount);
    if (!cleanedAmount || cleanedAmount === ".") return;
    setLoading(true);
    try {
      onError(null);
      await fetchJson("/api/reconciliation/create-adjustment/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          session_id: session.id,
          type,
          amount: cleanedAmount,
          account_name: account
        })
      });
      setAmount("");
      onUpdate();
    } catch (e) {
      console.error(e);
      onError(e instanceof Error ? e.message : "Failed to add adjustment");
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
          <Select value={type} onValueChange={setType} disabled={isLocked}>
            <SelectTrigger className="h-10 rounded-xl border-slate-200 bg-slate-50 text-sm disabled:opacity-60">
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
              type="text"
              inputMode="decimal"
              value={amount}
              onChange={e => handleAmountChange(e.target.value)}
              onBlur={handleAmountBlur}
              disabled={isLocked}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-medium outline-none focus:border-slate-400 focus:ring-0 disabled:opacity-60"
              placeholder="0.00"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium">
              {session.bankAccount.currency}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Account</label>
          <Select value={account} onValueChange={setAccount} disabled={isLocked}>
            <SelectTrigger className="h-10 rounded-xl border-slate-200 bg-slate-50 text-sm disabled:opacity-60">
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
          disabled={loading || !amount || isLocked}
          className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {loading ? "Adding..." : "Add adjustment"}
        </Button>
      </div>
      {isLocked && (
        <p className="text-[11px] text-slate-500">
          This period is completed and adjustments are locked.
        </p>
      )}
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
