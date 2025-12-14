import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  ChevronDown,
  Download,
  Info,
  Sparkles,
  FileText,
  ShieldCheck,
  X,
  Check,
  ArrowRight,
  Search,
  MoreHorizontal,
  Database,
  Eye,
  EyeOff,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  CreditCard,
  Trash2,
  Pencil,
} from "lucide-react";
import { useTaxGuardian, type Severity, type Status, type TaxAnomaly, type PaymentStatus, type TaxPayment, type TaxPaymentKind } from "./useTaxGuardian";
import { useAuth } from "../contexts/AuthContext";

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

export function formatCurrency(amount: number | string | undefined | null, currency: string = "CAD"): string {
  const num = typeof amount === "string" ? parseFloat(amount) || 0 : amount || 0;
  if (isNaN(num)) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(0);
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(num);
}

function classNames(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

function paymentStatusLabel(status: PaymentStatus | null | undefined): string {
  switch (status) {
    case "PAID":
      return "Paid";
    case "PARTIALLY_PAID":
      return "Partially paid";
    case "UNPAID":
      return "Unpaid";
    case "OVERPAID":
      return "Overpaid";
    case "SETTLED_ZERO":
      return "Settled";
    case "NO_LIABILITY":
      return "No liability";
    case "REFUND_DUE":
      return "Refund due";
    case "REFUND_PARTIALLY_RECEIVED":
      return "Partial refund";
    case "REFUND_RECEIVED":
      return "Refund received";
    case "REFUND_OVERRECEIVED":
      return "Over-refunded";
    default:
      return "Settled";
  }
}

function paymentStatusClasses(status: PaymentStatus | null | undefined): string {
  switch (status) {
    case "PAID":
    case "REFUND_RECEIVED":
    case "SETTLED_ZERO":
    case "NO_LIABILITY":
      return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100";
    case "PARTIALLY_PAID":
    case "REFUND_PARTIALLY_RECEIVED":
      return "bg-amber-50 text-amber-700 ring-1 ring-amber-100";
    case "UNPAID":
    case "REFUND_DUE":
      return "bg-rose-50 text-rose-700 ring-1 ring-rose-100";
    case "OVERPAID":
    case "REFUND_OVERRECEIVED":
      return "bg-blue-50 text-blue-700 ring-1 ring-blue-100";
    default:
      return "bg-slate-100 text-slate-600 ring-1 ring-slate-200";
  }
}

function periodSortKey(periodKey: string): number {
  const m = periodKey.match(/^(\d{4})-(\d{2})$/);
  if (m) {
    const year = Number(m[1]);
    const month = Number(m[2]);
    return Date.UTC(year, month - 1, 1);
  }
  const q = periodKey.match(/^(\d{4})Q([1-4])$/);
  if (q) {
    const year = Number(q[1]);
    const quarter = Number(q[2]);
    const endMonth = quarter * 3;
    return Date.UTC(year, endMonth - 1, 1);
  }
  return 0;
}

function useQueryParams(): { period?: string; severity?: Severity | "all" } {
  const params = new URLSearchParams(window.location.search);
  return {
    period: params.get("period") || undefined,
    severity: (params.get("severity") as Severity | "all") || undefined,
  };
}

// -----------------------------------------------------------------------------
// Toast Component
// -----------------------------------------------------------------------------
const Toast: React.FC<{ message: string; type: "success" | "error" | "info"; onClose: () => void }> = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const styles = {
    success: "bg-emerald-600 text-white shadow-emerald-200",
    error: "bg-rose-600 text-white shadow-rose-200",
    info: "bg-slate-800 text-white shadow-slate-200",
  };

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-2xl px-5 py-3 shadow-xl ${styles[type]} transition-all`}>
      {type === "success" && <Check className="h-4 w-4" />}
      {type === "error" && <AlertTriangle className="h-4 w-4" />}
      {type === "info" && <Info className="h-4 w-4" />}
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
};

// -----------------------------------------------------------------------------
// Companion Panel
// -----------------------------------------------------------------------------
const DashboardCompanionPanel: React.FC<{
  summary?: string | null;
  isEnriching: boolean;
  onEnrich: () => void;
  userName?: string;
}> = ({ summary, isEnriching, onEnrich, userName }) => {
  return (
    <div className="relative overflow-hidden rounded-[2rem] border border-white/60 bg-gradient-to-br from-white via-slate-50 to-slate-100 p-8 shadow-sm ring-1 ring-black/5">
      {/* Glass decorative blob */}
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-blue-50/50 blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
        <div className="flex gap-5">
          {/* AI Avatar */}
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white shadow-md">
            <span className="text-xs font-bold tracking-wider">AI</span>
          </div>

          <div className="space-y-3 max-w-2xl">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">
                Tax Guardian Companion
              </h3>
            </div>

            {isEnriching ? (
              <div className="space-y-2">
                <h2 className="text-xl font-semibold text-slate-900 animate-pulse">
                  Analyzing your tax position...
                </h2>
                <div className="h-1.5 w-48 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full w-2/3 bg-gradient-to-r from-transparent via-blue-400 to-transparent animate-pulse" />
                </div>
              </div>
            ) : summary ? (
              <div className="space-y-2">
                <h2 className="text-xl font-semibold text-slate-900">
                  I've analyzed your current period.
                </h2>
                <p className="text-sm leading-relaxed text-slate-600">
                  {summary}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <h2 className="text-xl font-semibold text-slate-900">
                  Good day{userName ? `, ${userName}` : ""}. I'm ready to review.
                </h2>
                <p className="text-sm text-slate-600">
                  I can cross-check recent activity, anomalies, and jurisdiction coverage to bring you a clean tax summary.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Action Button Area */}
        <div className="flex flex-col items-end gap-3">
          <div className="flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-[10px] font-medium text-slate-500 shadow-sm ring-1 ring-slate-200 backdrop-blur-md">
            <Sparkles className="h-3 w-3 text-emerald-500" />
            <span>{isEnriching ? "Thinking..." : "Ready to analyze"}</span>
          </div>

          <button
            onClick={onEnrich}
            disabled={isEnriching}
            className="group relative inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-6 py-2.5 text-sm font-medium text-white shadow-lg shadow-slate-900/10 transition-all hover:bg-slate-800 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70"
          >
            {isEnriching ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <span>{summary ? "Refresh Analysis" : "Generate Analysis"}</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

// -----------------------------------------------------------------------------
// Helper Components
// -----------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  subtext,
  tone = "neutral",
  badge,
}: {
  label: string;
  value: string;
  subtext?: string;
  tone?: "neutral" | "positive" | "negative";
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100/50 transition-all hover:shadow-md">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{label}</span>
        {badge}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-3xl font-bold tracking-tight text-slate-900">{value}</span>
      </div>
      {subtext && (
        <div className={classNames("mt-2 text-xs font-medium",
          tone === "negative" ? "text-rose-600" : tone === "positive" ? "text-emerald-600" : "text-slate-500"
        )}>
          {subtext}
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main Page
// -----------------------------------------------------------------------------

const TaxGuardianPage: React.FC = () => {
  const queryParams = useQueryParams();
  const { auth } = useAuth();
  const userName = auth?.user?.firstName || auth?.user?.username || "there";
  const navigate = useNavigate();
  const location = useLocation();

  const {
    periods,
    snapshot,
    anomalies,
    bankAccounts,
    selectedPeriod,
    setSelectedPeriod,
    severityFilter,
    setSeverityFilter,
    loading,
    error,
    refresh,
    llmEnrich,
    resetPeriod,
    createPayment,
    updatePayment,
    deletePayment,
    updatePeriodStatus,
    updateAnomalyStatus,
  } = useTaxGuardian(queryParams.period, queryParams.severity);

  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
  const [statusFilter, setStatusFilter] = useState<Status | "all">("all");
  const [enriching, setEnriching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const [resetReason, setResetReason] = useState("");
  const [resetting, setResetting] = useState(false);
  const [paymentSaving, setPaymentSaving] = useState(false);
  const [paymentForm, setPaymentForm] = useState<{
    id: string | null;
    kind: TaxPaymentKind;
    bank_account_id: string;
    amount: string;
    payment_date: string;
    method: string;
    reference: string;
    notes: string;
  }>({
    id: null,
    kind: "PAYMENT",
    bank_account_id: "",
    amount: "",
    payment_date: new Date().toISOString().slice(0, 10),
    method: "EFT",
    reference: "",
    notes: "",
  });

  // Filtered anomalies
  const filteredAnomalies = useMemo(() => {
    return anomalies.filter((a: TaxAnomaly) => {
      if (severityFilter !== "all" && a.severity !== severityFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return a.code.toLowerCase().includes(q) || a.description.toLowerCase().includes(q);
      }
      return true;
    });
  }, [anomalies, severityFilter, statusFilter, searchQuery]);

  const showToast = (message: string, type: "success" | "error" | "info") => setToast({ message, type });

  useEffect(() => {
    if (!selectedPeriod) return;
    const params = new URLSearchParams(location.search);
    params.set("period", selectedPeriod);
    if (severityFilter !== "all") {
      params.set("severity", severityFilter);
    } else {
      params.delete("severity");
    }
    navigate(
      { pathname: location.pathname, search: params.toString() ? `?${params.toString()}` : "" },
      { replace: true }
    );
  }, [location.pathname, location.search, navigate, selectedPeriod, severityFilter]);

  const handleRefresh = async () => {
    if (!selectedPeriod) return;
    setRefreshing(true);
    try {
      await refresh(selectedPeriod);
      showToast("Tax data refreshed from ledger", "success");
    } catch (e: any) {
      showToast(e.message || "Refresh failed", "error");
    } finally {
      setRefreshing(false);
    }
  };

  const handleEnrich = async () => {
    if (!selectedPeriod) return;
    setEnriching(true);
    try {
      await llmEnrich(selectedPeriod);
      showToast("AI analysis generated", "success");
    } catch (e: any) {
      showToast(e.message || "AI analysis failed", "error");
    } finally {
      setEnriching(false);
    }
  };

  const handleStatusUpdate = async (nextStatus: string) => {
    if (!selectedPeriod) return;
    try {
      await updatePeriodStatus(selectedPeriod, nextStatus);
      showToast(`Period marked as ${nextStatus}`, "success");
    } catch (e: any) {
      showToast(e.message || "Status update failed", "error");
    }
  };

  const handleAnomalyResolve = async (anomalyId: string) => {
    if (!selectedPeriod) return;
    try {
      await updateAnomalyStatus(selectedPeriod, anomalyId, "RESOLVED", statusFilter);
      showToast("Anomaly marked as resolved", "success");
    } catch (e: any) {
      showToast(e.message || "Failed to update anomaly", "error");
    }
  };

  const handleResetPeriod = async () => {
    if (!selectedPeriod) return;
    setResetting(true);
    try {
      await resetPeriod(selectedPeriod, resetReason);
      setResetOpen(false);
      setResetReason("");
      showToast("Return reset to REVIEWED. Refresh is now enabled.", "success");
    } catch (e: any) {
      showToast(e.message || "Failed to reset period", "error");
    } finally {
      setResetting(false);
    }
  };

  const beginEditPayment = (p: TaxPayment) => {
    setPaymentForm({
      id: p.id,
      kind: p.kind || "PAYMENT",
      bank_account_id: p.bank_account_id ? String(p.bank_account_id) : (bankAccounts[0]?.id ?? ""),
      amount: String(p.amount ?? ""),
      payment_date: (p.payment_date || "").slice(0, 10) || new Date().toISOString().slice(0, 10),
      method: p.method || "EFT",
      reference: p.reference || "",
      notes: p.notes || "",
    });
  };

  const clearPaymentForm = () => {
    setPaymentForm({
      id: null,
      kind: netTax < 0 ? "REFUND" : "PAYMENT",
      bank_account_id: paymentForm.bank_account_id || (bankAccounts[0]?.id ?? ""),
      amount: "",
      payment_date: new Date().toISOString().slice(0, 10),
      method: "EFT",
      reference: "",
      notes: "",
    });
  };

  const savePayment = async () => {
    if (!selectedPeriod) return;
    setPaymentSaving(true);
    try {
      if (!paymentForm.amount.trim()) throw new Error("Amount is required.");
      if (!paymentForm.payment_date) throw new Error("Payment date is required.");
      if (!paymentForm.bank_account_id) throw new Error("Bank account is required.");
      const payload = {
        kind: paymentForm.kind,
        bank_account_id: paymentForm.bank_account_id,
        amount: paymentForm.amount,
        payment_date: paymentForm.payment_date,
        method: paymentForm.method,
        reference: paymentForm.reference,
        notes: paymentForm.notes,
      };
      if (paymentForm.id) {
        await updatePayment(selectedPeriod, paymentForm.id, payload);
        showToast("Payment updated", "success");
      } else {
        await createPayment(selectedPeriod, payload);
        showToast("Payment recorded", "success");
      }
      clearPaymentForm();
    } catch (e: any) {
      showToast(e.message || "Failed to save payment", "error");
    } finally {
      setPaymentSaving(false);
    }
  };

  const removePayment = async (paymentId: string) => {
    if (!selectedPeriod) return;
    if (!confirm("Delete this payment record?")) return;
    setPaymentSaving(true);
    try {
      await deletePayment(selectedPeriod, paymentId);
      showToast("Payment deleted", "success");
      if (paymentForm.id === paymentId) clearPaymentForm();
    } catch (e: any) {
      showToast(e.message || "Failed to delete payment", "error");
    } finally {
      setPaymentSaving(false);
    }
  };

  // Compute net tax from snapshot
  const netTax = useMemo(() => {
    if (!snapshot) return 0;
    if (snapshot.net_tax !== undefined && snapshot.net_tax !== null) return snapshot.net_tax;
    if (!snapshot.summary_by_jurisdiction) return 0;
    return Object.values(snapshot.summary_by_jurisdiction).reduce((sum: number, j: any) => sum + (j.net_tax || 0), 0);
  }, [snapshot]);

  useEffect(() => {
    if (paymentForm.id) return;
    const desired: TaxPaymentKind = netTax < 0 ? "REFUND" : "PAYMENT";
    if (paymentForm.kind !== desired) setPaymentForm((f) => ({ ...f, kind: desired }));
  }, [netTax, paymentForm.id, paymentForm.kind]);

  useEffect(() => {
    if (paymentForm.bank_account_id) return;
    if (!bankAccounts || bankAccounts.length === 0) return;
    setPaymentForm((f) => ({ ...f, bank_account_id: bankAccounts[0].id }));
  }, [bankAccounts, paymentForm.bank_account_id]);

  const currency = snapshot?.country === "US" ? "USD" : "CAD";
  const payments: TaxPayment[] = (snapshot?.payments as any) || [];
  const paymentsTotal = snapshot?.payments_total ?? snapshot?.payments_net_total ?? 0;
  const paymentsPaymentTotal = snapshot?.payments_payment_total ?? 0;
  const paymentsRefundTotal = snapshot?.payments_refund_total ?? 0;
  const paymentStatus: PaymentStatus | null = (snapshot?.payment_status as any) || null;
  const balance = snapshot?.balance ?? ((netTax || 0) - (paymentsTotal || 0));
  const remainingBalance = snapshot?.remaining_balance ?? balance;
  const dueBadge = useMemo(() => {
    if (snapshot?.is_overdue) return { text: `Overdue`, className: "text-rose-600" };
    if (snapshot?.is_due_soon) return { text: `Due soon`, className: "text-amber-600" };
    return { text: "On track", className: "text-emerald-600" };
  }, [snapshot]);

  // Format due date
  const dueDate = useMemo(() => {
    if (!snapshot?.due_date) return null;
    try {
      return new Date(snapshot.due_date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch {
      return snapshot.due_date;
    }
  }, [snapshot]);

  const trendPeriods = useMemo(() => {
    const sorted = [...periods].sort((a, b) => periodSortKey(a.period_key) - periodSortKey(b.period_key));
    return sorted.slice(Math.max(0, sorted.length - 12));
  }, [periods]);

  if (loading && !snapshot) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin text-slate-400 mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading Tax Guardian...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] p-8">
        <div className="max-w-xl mx-auto p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700">
          <AlertTriangle className="h-5 w-5 mb-2" />
          <p className="font-medium">Error loading Tax Guardian</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB] font-sans selection:bg-emerald-100 selection:text-emerald-900">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      {resetOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 p-4">
          <div className="w-full max-w-lg rounded-[2rem] bg-white p-6 shadow-xl ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Reset filed return?</h2>
                <p className="mt-1 text-xs text-slate-600">
                  This will reopen the period for changes. It does not delete transactions, but it clears the FILED lock.
                </p>
              </div>
              <button
                onClick={() => setResetOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Reason (optional)</label>
              <input
                value={resetReason}
                onChange={(e) => setResetReason(e.target.value)}
                placeholder="e.g., Filing was premature; adjusting rates"
                className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
              />
              {snapshot?.last_filed_at && (
                <p className="mt-2 text-[11px] text-slate-500">
                  Last filed at: {new Date(snapshot.last_filed_at).toLocaleString()}
                </p>
              )}
            </div>

            <div className="mt-6 flex items-center justify-end gap-2">
              <button
                onClick={() => setResetOpen(false)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleResetPeriod}
                disabled={resetting}
                className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 shadow-sm hover:bg-rose-100 disabled:opacity-50"
              >
                {resetting ? "Resetting..." : "Reset return"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mx-auto max-w-[1600px] px-6 py-8 md:px-10">

        {/* Header Section */}
        <header className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
              <Link to="/ai-companion" className="hover:text-slate-600">Overview</Link>
              <span className="text-slate-300">/</span>
              <span className="text-slate-600">Tax Guardian</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              {getGreeting()}, {userName}. <br className="hidden md:block" />
              <span className="text-slate-400">Your tax position is </span>
              <span className={classNames(
                "underline decoration-2 underline-offset-4",
                snapshot?.status === "FILED" ? "decoration-emerald-400 text-slate-900" : "decoration-amber-400 text-slate-900"
              )}>
                {snapshot?.status === "DRAFT" ? "in draft" : (snapshot?.status || "pending").toLowerCase()}.
              </span>
            </h1>
          </div>

          <div className="flex items-center gap-3">
            {selectedPeriod && snapshot && (
              <div className="relative group">
                <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50">
                  <Download className="h-3.5 w-3.5" />
                  Export
                  <ChevronDown className="h-3 w-3" />
                </button>
                <div className="absolute right-0 top-full mt-2 w-48 rounded-xl bg-white shadow-lg ring-1 ring-slate-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  <div className="p-2 space-y-1">
                    <a
                      href={`/api/tax/periods/${selectedPeriod}/export.json`}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-700 rounded-lg hover:bg-slate-50"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      Export JSON
                    </a>
                    <a
                      href={`/api/tax/periods/${selectedPeriod}/export.csv`}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-700 rounded-lg hover:bg-slate-50"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      Jurisdiction CSV
                    </a>
                    <a
                      href={`/api/tax/periods/${selectedPeriod}/export-ser.csv`}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-700 rounded-lg hover:bg-slate-50"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      US SER CSV
                    </a>
                    <div className="border-t border-slate-100 my-1" />
                    <a
                      href={`/api/tax/periods/${selectedPeriod}/anomalies/export.csv`}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-700 rounded-lg hover:bg-slate-50"
                    >
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Anomalies CSV
                    </a>
                  </div>
                </div>
              </div>
            )}
            <Link
              to="/tax/settings"
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-slate-900/10 transition-transform hover:scale-105 active:scale-95"
            >
              Tax Settings
            </Link>
            {auth?.isAdmin && (
              <Link
                to="/tax/catalog"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
              >
                <Database className="h-3.5 w-3.5" />
                Catalog
              </Link>
            )}
          </div>
        </header>

        {/* Dashboard Grid */}
        <div className="flex flex-col gap-8">

          {/* Top Row: Companion + Metrics */}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <DashboardCompanionPanel
                summary={snapshot?.llm_summary}
                isEnriching={enriching}
                onEnrich={handleEnrich}
                userName={userName}
              />
            </div>

            <div className="flex flex-col gap-4">
              <MetricCard
                label="Net tax"
                value={formatCurrency(netTax, currency)}
                subtext={
                  netTax < 0
                    ? `Refund received: ${formatCurrency(Math.max(0, -paymentsTotal), currency)} · Remaining: ${formatCurrency(remainingBalance, currency)}`
                    : `Paid: ${formatCurrency(Math.max(0, paymentsTotal), currency)} · Remaining: ${formatCurrency(remainingBalance, currency)}`
                }
                tone={
                  paymentStatus === "UNPAID" || paymentStatus === "REFUND_DUE"
                    ? "negative"
                    : paymentStatus === "PARTIALLY_PAID" || paymentStatus === "REFUND_PARTIALLY_RECEIVED"
                      ? "neutral"
                      : "positive"
                }
                badge={
                  <span className={classNames("rounded-full px-2 py-1 text-[10px] font-bold", paymentStatusClasses(paymentStatus))}>
                    {paymentStatusLabel(paymentStatus)}
                  </span>
                }
              />
              <div className="grid grid-cols-2 gap-4">
                <MetricCard
                  label="Status"
                  value={snapshot?.status || "—"}
                  tone="neutral"
                />
                <MetricCard
                  label="Due Date"
                  value={dueDate || "—"}
                  subtext={dueBadge.text}
                  tone={snapshot?.is_overdue ? "negative" : "positive"}
                />
              </div>
            </div>
          </div>

          {/* Trends */}
          <div className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-slate-400" />
                <h3 className="text-sm font-bold text-slate-900">Trends</h3>
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Last {trendPeriods.length}
              </span>
            </div>

            <div className="flex gap-3 overflow-x-auto pb-1">
              {trendPeriods.map((p, idx) => {
                const prev = idx > 0 ? trendPeriods[idx - 1] : null;
                const delta = prev ? (p.net_tax || 0) - (prev.net_tax || 0) : 0;
                const DeltaIcon = delta > 0.01 ? ArrowUpRight : delta < -0.01 ? ArrowDownRight : Minus;
                return (
                  <button
                    key={p.period_key}
                    onClick={() => setSelectedPeriod(p.period_key)}
                    className={classNames(
                      "min-w-[180px] rounded-[1.25rem] border px-4 py-3 text-left shadow-sm transition-colors hover:bg-slate-50",
                      selectedPeriod === p.period_key ? "border-slate-900 bg-slate-50" : "border-slate-100 bg-white"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700">{p.period_key}</span>
                      <DeltaIcon className="h-4 w-4 text-slate-400" />
                    </div>
                    <div className="mt-2 text-sm font-semibold text-slate-900 tabular-nums">
                      {formatCurrency(p.net_tax || 0, currency)}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {p.payment_status && (
                        <span className={classNames("rounded-full px-2 py-0.5 text-[10px] font-bold", paymentStatusClasses(p.payment_status))}>
                          {paymentStatusLabel(p.payment_status)}
                        </span>
                      )}
                      {(p.anomaly_counts?.high ?? 0) > 0 && (
                        <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 ring-1 ring-rose-100">
                          High {p.anomaly_counts.high}
                        </span>
                      )}
                      {p.is_overdue && (
                        <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 ring-1 ring-rose-100">
                          Overdue
                        </span>
                      )}
                      {(!p.is_overdue && p.is_due_soon) && (
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700 ring-1 ring-amber-100">
                          Due soon
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
              {trendPeriods.length === 0 && (
                <div className="text-sm text-slate-500 py-2">No periods yet.</div>
              )}
            </div>
          </div>

          {/* Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-[20px] bg-white p-2 pl-6 pr-2 shadow-sm ring-1 ring-slate-100">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Period</span>
                <div className="relative">
                  <select
                    className="appearance-none bg-transparent pr-6 text-sm font-semibold text-slate-900 outline-none cursor-pointer"
                    value={selectedPeriod || ""}
                    onChange={(e) => setSelectedPeriod(e.target.value)}
                  >
                    {periods.map(p => (
                      <option key={p.period_key} value={p.period_key}>
                        {p.period_key} {p.is_overdue ? "● overdue" : p.is_due_soon ? "● due soon" : ""}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-0 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              </div>

              <div className="h-4 w-px bg-slate-200" />

              <div className="flex items-center gap-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Severity</span>
                <div className="flex items-center gap-1">
                  {(["high", "medium", "low"] as Severity[]).map(sev => (
                    <button
                      key={sev}
                      onClick={() => setSeverityFilter(severityFilter === sev ? "all" : sev)}
                      className={classNames(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize transition-all",
                        severityFilter === sev
                          ? "bg-slate-900 text-white"
                          : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                      )}
                    >
                      {sev}
                    </button>
                  ))}
                </div>
              </div>

              <div className="h-4 w-px bg-slate-200" />

              <div className="flex items-center gap-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Status</span>
                <div className="flex items-center gap-1">
                  {(["OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED"] as Status[]).map(st => (
                    <button
                      key={st}
                      onClick={() => setStatusFilter(statusFilter === st ? "all" : st)}
                      className={classNames(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold transition-all",
                        statusFilter === st
                          ? "bg-slate-900 text-white"
                          : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                      )}
                    >
                      {st.charAt(0) + st.slice(1).toLowerCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search anomalies..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-9 w-64 rounded-xl border-none bg-slate-50 pl-9 pr-4 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-slate-200 focus:outline-none"
                />
              </div>
              <button
                onClick={handleRefresh}
                disabled={refreshing || !selectedPeriod || snapshot?.status === "FILED"}
                title={snapshot?.status === "FILED" ? "Filed periods cannot be recomputed. Reset the return to reopen." : "Refresh snapshot + anomalies"}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-50"
              >
                <RefreshCw className={classNames("h-3.5 w-3.5", refreshing && "animate-spin")} />
              </button>
              {snapshot?.status === "FILED" && (
                <button
                  onClick={() => setResetOpen(true)}
                  className="h-9 rounded-xl border border-rose-200 bg-rose-50 px-3 text-[11px] font-bold text-rose-700 hover:bg-rose-100"
                  title="Reset this filed return to reopen the period for changes."
                >
                  Reset return
                </button>
              )}
            </div>
          </div>

          {/* Main Content Area */}
          <div className="grid gap-6 lg:grid-cols-3">

            {/* Left: Detailed Tables */}
            <div className="space-y-6 lg:col-span-2">
              {/* Jurisdiction Table */}
              <div className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100">
                <div className="mb-6 flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900">Jurisdiction Breakdown</h3>
                  <Link to="/coa" className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 hover:text-emerald-700">View Full Ledger</Link>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      <tr className="border-b border-slate-100">
                        <th className="pb-3 pl-2">Region</th>
                        <th className="pb-3 text-right">Sales</th>
                        <th className="pb-3 text-right">Tax Collected</th>
                        <th className="pb-3 text-right pr-2">Net Tax</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {snapshot?.summary_by_jurisdiction && Object.entries(snapshot.summary_by_jurisdiction).map(([code, data]: [string, any]) => (
                        <tr key={code} className="group cursor-pointer hover:bg-slate-50">
                          <td className="py-3 pl-2 font-semibold text-slate-900">
                            <div className="flex items-center gap-2">
                              <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                              {code}
                            </div>
                          </td>
                          <td className="py-3 text-right text-slate-600 tabular-nums">{formatCurrency(data.taxable_sales, data.currency || currency)}</td>
                          <td className="py-3 text-right text-slate-600 tabular-nums">{formatCurrency(data.tax_collected, data.currency || currency)}</td>
                          <td className="py-3 pr-2 text-right font-bold text-slate-900 tabular-nums">{formatCurrency(data.net_tax, data.currency || currency)}</td>
                        </tr>
                      ))}
                      {(!snapshot?.summary_by_jurisdiction || Object.keys(snapshot.summary_by_jurisdiction).length === 0) && (
                        <tr>
                          <td colSpan={4} className="py-8 text-center text-slate-400">
                            No jurisdiction data available. Click refresh to compute.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Payments */}
              <div className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Payments</h3>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      Track payments and refunds for this period (bank account required for reconciliation).
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={classNames("rounded-full px-2 py-1 text-[10px] font-bold", paymentStatusClasses(paymentStatus))}>
                      {paymentStatusLabel(paymentStatus)}
                    </span>
                    {paymentsPaymentTotal > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700 ring-1 ring-emerald-200 tabular-nums">
                        <TrendingUp className="h-3 w-3" />
                        Paid {formatCurrency(paymentsPaymentTotal, currency)}
                      </span>
                    )}
                    {paymentsRefundTotal > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-700 ring-1 ring-blue-200 tabular-nums">
                        <ArrowDownRight className="h-3 w-3" />
                        Refunds {formatCurrency(paymentsRefundTotal, currency)}
                      </span>
                    )}
                    <span className={classNames(
                      "rounded-full px-2 py-1 text-[10px] font-bold ring-1 tabular-nums",
                      balance > 0.02 ? "bg-amber-50 text-amber-700 ring-amber-200" :
                        balance < -0.02 ? "bg-blue-50 text-blue-700 ring-blue-200" :
                          "bg-slate-100 text-slate-700 ring-slate-200"
                    )}>
                      {balance > 0.02 ? `Owing ${formatCurrency(balance, currency)}` :
                        balance < -0.02 ? `Credit ${formatCurrency(-balance, currency)}` :
                          "Settled"}
                    </span>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      <tr className="border-b border-slate-100">
                        <th className="pb-3 pl-2">Date</th>
                        <th className="pb-3">Type</th>
                        <th className="pb-3">Bank account</th>
                        <th className="pb-3 text-right">Amount</th>
                        <th className="pb-3">Method</th>
                        <th className="pb-3">Reference</th>
                        <th className="pb-3">Notes</th>
                        <th className="pb-3 pr-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {payments.map((p) => (
                        <tr key={p.id} className="group hover:bg-slate-50">
                          <td className="py-3 pl-2 font-semibold text-slate-900 tabular-nums">
                            {p.payment_date ? new Date(p.payment_date).toLocaleDateString() : "—"}
                          </td>
                          <td className="py-3">
                            <span className={classNames(
                              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                              p.kind === "REFUND"
                                ? "bg-blue-50 text-blue-700 ring-1 ring-blue-200"
                                : "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                            )}>
                              {p.kind === "REFUND" ? "Refund" : "Payment"}
                            </span>
                          </td>
                          <td className="py-3 text-slate-600 max-w-[220px] truncate" title={p.bank_account_label || ""}>
                            {p.bank_account_label || "—"}
                          </td>
                          <td className="py-3 text-right font-bold text-slate-900 tabular-nums">
                            {formatCurrency(p.amount, p.currency || currency)}
                          </td>
                          <td className="py-3 text-slate-600">{p.method || "—"}</td>
                          <td className="py-3 text-slate-600">{p.reference || "—"}</td>
                          <td className="py-3 text-slate-600 max-w-[280px] truncate" title={p.notes || ""}>
                            {p.notes || "—"}
                          </td>
                          <td className="py-3 pr-2 text-right">
                            <div className="inline-flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                              <button
                                onClick={() => beginEditPayment(p)}
                                className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-50 text-slate-600 hover:bg-slate-100"
                                title="Edit payment"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                              <button
                                onClick={() => removePayment(p.id)}
                                disabled={paymentSaving}
                                className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-50 text-rose-600 hover:bg-rose-100 disabled:opacity-50"
                                title="Delete payment"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {payments.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-10 text-center text-slate-400">
                            No payments recorded for this period.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="mt-6 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
                      <CreditCard className="h-4 w-4 text-slate-400" />
                      {paymentForm.id ? "Edit payment" : "Record new payment or refund"}
                    </div>
                    {paymentForm.id && (
                      <button
                        onClick={clearPaymentForm}
                        className="text-[11px] font-semibold text-slate-500 hover:text-slate-700"
                      >
                        Cancel edit
                      </button>
                    )}
                  </div>

                  {/* Type Toggle */}
                  <div className="mb-4 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setPaymentForm((f) => ({ ...f, kind: "PAYMENT" }))}
                      className={classNames(
                        "inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold transition-all",
                        paymentForm.kind === "PAYMENT"
                          ? "bg-emerald-600 text-white shadow-sm"
                          : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                      )}
                    >
                      <TrendingUp className="h-3.5 w-3.5" />
                      Payment to agency
                    </button>
                    <button
                      type="button"
                      onClick={() => setPaymentForm((f) => ({ ...f, kind: "REFUND" }))}
                      className={classNames(
                        "inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold transition-all",
                        paymentForm.kind === "REFUND"
                          ? "bg-blue-600 text-white shadow-sm"
                          : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
                      )}
                    >
                      <ArrowDownRight className="h-3.5 w-3.5" />
                      Refund from agency
                    </button>
                  </div>

                  <div className="grid gap-3 md:grid-cols-6">
                    <div className="md:col-span-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        {paymentForm.kind === "REFUND" ? "Refund amount" : "Amount"}
                      </label>
                      <input
                        value={paymentForm.amount}
                        onChange={(e) => setPaymentForm((f) => ({ ...f, amount: e.target.value }))}
                        placeholder="1000.00"
                        className="mt-1 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                      />
                    </div>
                    <div className="md:col-span-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Date</label>
                      <input
                        type="date"
                        value={paymentForm.payment_date}
                        onChange={(e) => setPaymentForm((f) => ({ ...f, payment_date: e.target.value }))}
                        className="mt-1 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                      />
                    </div>
                    <div className="md:col-span-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Bank account</label>
                      <select
                        value={paymentForm.bank_account_id}
                        onChange={(e) => setPaymentForm((f) => ({ ...f, bank_account_id: e.target.value }))}
                        disabled={bankAccounts.length === 0}
                        className="mt-1 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60"
                      >
                        <option value="" disabled>
                          {bankAccounts.length === 0 ? "No bank accounts" : "Select…"}
                        </option>
                        {bankAccounts.map((ba) => (
                          <option key={ba.id} value={ba.id}>
                            {ba.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="md:col-span-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Method</label>
                      <select
                        value={paymentForm.method}
                        onChange={(e) => setPaymentForm((f) => ({ ...f, method: e.target.value }))}
                        className="mt-1 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                      >
                        <option value="EFT">EFT</option>
                        <option value="Cheque">Cheque</option>
                        <option value="Card">Card</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>
                    <div className="md:col-span-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Reference</label>
                      <input
                        value={paymentForm.reference}
                        onChange={(e) => setPaymentForm((f) => ({ ...f, reference: e.target.value }))}
                        placeholder="CRA ref, bank ref..."
                        className="mt-1 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                      />
                    </div>
                    <div className="md:col-span-1">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Notes</label>
                      <input
                        value={paymentForm.notes}
                        onChange={(e) => setPaymentForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="Optional"
                        className="mt-1 h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-200"
                      />
                    </div>
                  </div>

                  <div className="mt-4 flex justify-end">
                    <button
                      onClick={savePayment}
                      disabled={paymentSaving || !selectedPeriod || !paymentForm.bank_account_id}
                      className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      {paymentSaving ? "Saving..." : paymentForm.id ? "Update payment" : "Add payment"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Filing Cards */}
              {snapshot?.line_mappings && Object.keys(snapshot.line_mappings).length > 0 && (
                <div className="grid gap-6 md:grid-cols-2">
                  {Object.entries(snapshot.line_mappings).map(([countryCode, lines]: [string, any]) => (
                    <div key={countryCode} className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100">
                      <div className="mb-4 flex items-center justify-between">
                        <span className="flex items-center gap-2 text-xs font-bold text-slate-900">
                          <div className="flex h-5 w-5 items-center justify-center rounded bg-slate-100 text-[10px] text-slate-700">
                            {countryCode === "CA" ? "🇨🇦" : countryCode === "US" ? "🇺🇸" : countryCode}
                          </div>
                          {countryCode === "CA" ? "GST/HST" : countryCode === "QC" ? "QST" : countryCode}
                        </span>
                        <span className={classNames(
                          "rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider",
                          snapshot.status === "FILED" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                        )}>
                          {snapshot.status || "Draft"}
                        </span>
                      </div>
                      <div className="space-y-3">
                        {Object.entries(lines).slice(0, 3).map(([lineCode, amount]: [string, any]) => (
                          <div key={lineCode} className="flex justify-between text-xs">
                            <span className="text-slate-500">{lineCode.replace(/_/g, " ")}</span>
                            <span className="font-medium text-slate-900">{formatCurrency(amount, currency)}</span>
                          </div>
                        ))}
                        {lines.net_tax !== undefined && (
                          <div className="mt-3 flex justify-between border-t border-slate-100 pt-3 text-xs font-bold">
                            <span className="text-slate-700">Net Payable</span>
                            <span className="text-slate-900">{formatCurrency(lines.net_tax, currency)}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Right: Anomalies List */}
            <div className="space-y-6">
              <div className="rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 h-full">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Anomalies</h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">Prioritize resolving high severity items</p>
                  </div>
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600">
                    {filteredAnomalies.length}
                  </span>
                </div>

                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {filteredAnomalies.map((a: TaxAnomaly) => (
                    <div key={a.id} className="group relative rounded-2xl border border-slate-100 bg-white p-4 transition-all hover:border-slate-200 hover:shadow-md">
                      <div className="mb-2 flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <span className={classNames(
                            "flex h-2 w-2 rounded-full",
                            a.severity === "high" ? "bg-rose-500" : a.severity === "medium" ? "bg-amber-500" : "bg-emerald-500"
                          )} />
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{a.code}</span>
                        </div>
                        <span className={classNames(
                          "text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded",
                          a.status === "RESOLVED" ? "bg-emerald-50 text-emerald-600" :
                            a.status === "ACKNOWLEDGED" ? "bg-blue-50 text-blue-600" :
                              a.status === "IGNORED" ? "bg-slate-50 text-slate-400" :
                                "bg-amber-50 text-amber-600"
                        )}>
                          {a.status}
                        </span>
                      </div>

                      <p className="text-xs font-medium text-slate-900 leading-relaxed mb-3">
                        {a.description}
                      </p>

                      <div className="flex items-center justify-between">
                        {a.jurisdiction_code && (
                          <span className="rounded-md bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500">
                            {a.jurisdiction_code}
                          </span>
                        )}

                        <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                          {a.linked_model && a.linked_id && (
                            <Link
                              to={`/${a.linked_model === "Invoice" ? "invoices" : "expenses"}/${a.linked_id}`}
                              className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-50 text-slate-600 hover:bg-slate-100"
                            >
                              <FileText className="h-3.5 w-3.5" />
                            </Link>
                          )}
                          {a.status === "OPEN" && (
                            <button
                              onClick={() => handleAnomalyResolve(a.id)}
                              className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {filteredAnomalies.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-500">
                        <CheckCircle2 className="h-6 w-6" />
                      </div>
                      <p className="text-sm font-medium text-slate-900">All Clear</p>
                      <p className="text-xs text-slate-500">No anomalies found for this period.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Card */}
              <div className="rounded-[2rem] bg-slate-900 p-6 text-white shadow-lg shadow-slate-900/10">
                <h3 className="text-sm font-bold">Ready to file?</h3>
                <p className="mt-1 text-xs text-slate-400">Once all anomalies are resolved, lock this period.</p>

                <div className="mt-4 flex gap-3">
                  <button
                    disabled={snapshot?.status !== "DRAFT"}
                    onClick={() => handleStatusUpdate("REVIEWED")}
                    className="flex-1 rounded-xl bg-white/10 py-2.5 text-xs font-semibold transition-colors hover:bg-white/20 disabled:opacity-50"
                  >
                    Review
                  </button>
                  <button
                    disabled={snapshot?.status === "FILED"}
                    onClick={() => handleStatusUpdate("FILED")}
                    className="flex-1 rounded-xl bg-white py-2.5 text-xs font-semibold text-slate-900 transition-colors hover:bg-slate-50 disabled:opacity-50"
                  >
                    File Return
                  </button>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};

// Helper for greeting
function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Morning";
  if (hour >= 12 && hour < 18) return "Afternoon";
  return "Evening";
}

export default TaxGuardianPage;
