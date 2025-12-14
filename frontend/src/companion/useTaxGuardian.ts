import { useEffect, useState, useCallback } from "react";
import { parseCookies } from "../utils/cookies";

export type Severity = "high" | "medium" | "low";
export type Status = "OPEN" | "ACKNOWLEDGED" | "RESOLVED" | "IGNORED";
export type PaymentStatus =
  | "PAID"
  | "PARTIALLY_PAID"
  | "UNPAID"
  | "OVERPAID"
  | "SETTLED_ZERO"
  | "NO_LIABILITY"
  | "REFUND_DUE"
  | "REFUND_PARTIALLY_RECEIVED"
  | "REFUND_RECEIVED"
  | "REFUND_OVERRECEIVED";

export type TaxPaymentKind = "PAYMENT" | "REFUND";

export type TaxPayment = {
  id: string;
  kind: TaxPaymentKind;
  amount: number;
  currency: string;
  payment_date: string;
  bank_account_id?: string | null;
  bank_account_label?: string;
  method?: string;
  reference?: string;
  notes?: string;
  created_at?: string;
};

export type BankAccountOption = {
  id: string;
  name: string;
  currency: string;
};

export interface TaxPeriod {
  period_key: string;
  status: string;
  net_tax: number;
  payments_payment_total?: number;
  payments_refund_total?: number;
  payments_net_total?: number;
  payments_total?: number;
  balance?: number;
  remaining_balance?: number;
  payment_status?: PaymentStatus | null;
  anomaly_counts: { low: number; medium: number; high: number };
  due_date?: string;
  is_due_soon?: boolean;
  is_overdue?: boolean;
}

export interface TaxSnapshot {
  period_key: string;
  country: string;
  status: string;
  due_date?: string;
  is_due_soon?: boolean;
  is_overdue?: boolean;
  filed_at?: string | null;
  last_filed_at?: string | null;
  last_reset_at?: string | null;
  last_reset_reason?: string;
  llm_summary?: string;
  llm_notes?: string;
  summary_by_jurisdiction: Record<string, any>;
  line_mappings: Record<string, any>;
  net_tax?: number;
  payments?: TaxPayment[];
  payments_payment_total?: number;
  payments_refund_total?: number;
  payments_net_total?: number;
  payments_total?: number;
  balance?: number;
  remaining_balance?: number;
  payment_status?: PaymentStatus | null;
  anomaly_counts: { low: number; medium: number; high: number };
  has_high_severity_blockers: boolean;
}

export interface TaxAnomaly {
  id: string;
  code: string;
  severity: string;
  status: string;
  description: string;
  task_code: string;
  created_at?: string;
  resolved_at?: string;
  linked_model?: string | null;
  linked_id?: number | null;
  jurisdiction_code?: string | null;
  linked_model_friendly?: string | null;
  ledger_path?: string | null;
  expected_tax_amount?: number;
  actual_tax_amount?: number;
  difference?: number;
}

export function useTaxGuardian(initialPeriodKey?: string, initialSeverity?: Severity | "all") {
  const [periods, setPeriods] = useState<TaxPeriod[]>([]);
  const [snapshot, setSnapshot] = useState<TaxSnapshot | null>(null);
  const [anomalies, setAnomalies] = useState<TaxAnomaly[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccountOption[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string | undefined>(initialPeriodKey);
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">(initialSeverity || "all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getCsrfToken = useCallback((): string | undefined => {
    const cookies = parseCookies(document.cookie || "");
    return cookies.csrftoken;
  }, []);

  const apiFetch = useCallback(
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const method = (init.method || "GET").toUpperCase();
      const headers: Record<string, string> = {
        Accept: "application/json",
        ...(init.headers as Record<string, string> | undefined),
      };
      if (method !== "GET") {
        const csrf = getCsrfToken();
        if (csrf) headers["X-CSRFToken"] = csrf;
        if (init.body !== undefined && !headers["Content-Type"]) {
          headers["Content-Type"] = "application/json";
        }
      }
      const res = await fetch(input, {
        credentials: "same-origin",
        ...init,
        headers,
      });
      return res;
    },
    [getCsrfToken]
  );

  const fetchPeriods = useCallback(async () => {
    const res = await apiFetch("/api/tax/periods/");
    if (!res.ok) throw new Error("Failed to load tax periods");
    const data = await res.json();
    setPeriods(data.periods || []);
    if (!selectedPeriod && data.periods && data.periods.length > 0) {
      setSelectedPeriod(data.periods[0].period_key);
    }
  }, [apiFetch, selectedPeriod]);

  const fetchSnapshot = useCallback(
    async (period: string) => {
      const res = await apiFetch(`/api/tax/periods/${period}/`);
      if (!res.ok) throw new Error("Failed to load tax snapshot");
      const data = await res.json();
      setSnapshot(data);
    },
    [apiFetch]
  );

  const fetchAnomalies = useCallback(
    async (period: string, severity?: Severity | "all", status?: Status | "all") => {
      const params = new URLSearchParams();
      if (severity && severity !== "all") params.append("severity", severity);
      if (status && status !== "all") params.append("status", status);
      const res = await apiFetch(`/api/tax/periods/${period}/anomalies/?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to load tax anomalies");
      const data = await res.json();
      setAnomalies(data.anomalies || []);
    },
    [apiFetch]
  );

  const fetchBankAccounts = useCallback(async () => {
    const res = await apiFetch("/api/reconciliation/accounts/");
    if (!res.ok) throw new Error("Failed to load bank accounts");
    const data = await res.json();
    const source = Array.isArray(data) ? data : data?.accounts || [];
    const normalized: BankAccountOption[] = source.map((acc: any) => ({
      id: String(acc.id),
      name: String(acc.name || ""),
      currency: String(acc.currency || "USD"),
    }));
    setBankAccounts(normalized);
  }, [apiFetch]);

  const refresh = useCallback(
    async (period: string) => {
      const res = await apiFetch(`/api/tax/periods/${period}/refresh/`, { method: "POST" });
      if (!res.ok) throw new Error("Refresh failed");
      await fetchSnapshot(period);
      await fetchAnomalies(period);
    },
    [apiFetch, fetchAnomalies, fetchSnapshot]
  );

  const updatePeriodStatus = useCallback(
    async (period: string, status: string) => {
      const res = await apiFetch(`/api/tax/periods/${period}/status/`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("Failed to update status");
      await fetchSnapshot(period);
    },
    [apiFetch, fetchSnapshot]
  );

  const updateAnomalyStatus = useCallback(
    async (period: string, anomalyId: string, status: Status, statusFilter?: Status | "all") => {
      const res = await apiFetch(`/api/tax/periods/${period}/anomalies/${anomalyId}/`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("Failed to update anomaly");
      await fetchAnomalies(period, severityFilter, statusFilter);
    },
    [apiFetch, fetchAnomalies, severityFilter]
  );

  const llmEnrich = useCallback(
    async (period: string) => {
      const res = await apiFetch(`/api/tax/periods/${period}/llm-enrich/`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const message = (data as any)?.detail || (data as any)?.error || "LLM enrichment failed";
        throw new Error(message);
      }
      await fetchSnapshot(period);
    },
    [apiFetch, fetchSnapshot]
  );

  const resetPeriod = useCallback(
    async (period: string, reason?: string) => {
      const res = await apiFetch(`/api/tax/periods/${period}/reset/`, {
        method: "POST",
        body: JSON.stringify({ confirm_reset: true, reason: reason || "" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.error || (data as any)?.detail || "Reset failed");
      await fetchSnapshot(period);
      await fetchAnomalies(period);
    },
    [apiFetch, fetchAnomalies, fetchSnapshot]
  );

  const createPayment = useCallback(
    async (
      period: string,
      payload: {
        kind?: TaxPaymentKind;
        bank_account_id?: string;
        amount: number | string;
        payment_date: string;
        method?: string;
        reference?: string;
        notes?: string;
      }
    ) => {
      const res = await apiFetch(`/api/tax/periods/${period}/payments/`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.error || JSON.stringify((data as any)?.errors || data));
      await Promise.all([fetchSnapshot(period), fetchPeriods()]);
    },
    [apiFetch, fetchPeriods, fetchSnapshot]
  );

  const updatePayment = useCallback(
    async (
      period: string,
      paymentId: string,
      payload: Partial<{
        kind: TaxPaymentKind;
        bank_account_id: string;
        amount: number | string;
        payment_date: string;
        method: string;
        reference: string;
        notes: string;
      }>
    ) => {
      const res = await apiFetch(`/api/tax/periods/${period}/payments/${paymentId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.error || JSON.stringify((data as any)?.errors || data));
      await Promise.all([fetchSnapshot(period), fetchPeriods()]);
    },
    [apiFetch, fetchPeriods, fetchSnapshot]
  );

  const deletePayment = useCallback(
    async (period: string, paymentId: string) => {
      const res = await apiFetch(`/api/tax/periods/${period}/payments/${paymentId}/`, { method: "DELETE" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((data as any)?.error || "Failed to delete payment");
      await Promise.all([fetchSnapshot(period), fetchPeriods()]);
    },
    [apiFetch, fetchPeriods, fetchSnapshot]
  );

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([fetchPeriods(), fetchBankAccounts()])
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [fetchBankAccounts, fetchPeriods]);

  useEffect(() => {
    if (!selectedPeriod) return;
    setLoading(true);
    Promise.all([fetchSnapshot(selectedPeriod), fetchAnomalies(selectedPeriod)])
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedPeriod, fetchAnomalies, fetchSnapshot]);

  return {
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
    refetch: async () => {
      if (!selectedPeriod) return;
      await fetchSnapshot(selectedPeriod);
      await fetchAnomalies(selectedPeriod);
    },
  };
}
