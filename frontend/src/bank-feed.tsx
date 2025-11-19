import React, { useCallback, useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

type BankAccount = {
  id: number;
  name: string;
  last4: string;
  ledgerBalance: number;
};

type LedgerLine = {
  account_name: string;
  account_code: string | null;
  debit: number;
  credit: number;
};

type JournalEntryPreview = {
  id: number;
  date: string;
  description: string;
  lines: LedgerLine[];
} | null;

type MatchCandidate = {
  id: number;
  description?: string;
  invoice_number?: string;
  customer?: string;
  date?: string;
  amount: number;
};

type BankTransaction = {
  id: number;
  date: string;
  description: string;
  amount: number;
  status: string;
  statusLabel: string;
  side: "IN" | "OUT";
  allocatedAmount: number;
  posted_journal_entry: JournalEntryPreview;
  expense_candidates: MatchCandidate[];
  invoice_candidates: MatchCandidate[];
};

type CategoryOption = {
  id: number;
  name: string;
};

type ContactOption = {
  id: number;
  name: string;
};

type ManualAllocationRow = {
  key: string;
  type: "DIRECT_INCOME" | "DIRECT_EXPENSE";
  accountId: string;
  amount: string;
};

const STATUS_STYLES: Record<string, string> = {
  NEW: "bg-sky-50 text-sky-700 ring-sky-100",
  PARTIAL: "bg-amber-50 text-amber-800 ring-amber-100",
  MATCHED_SINGLE: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  MATCHED_MULTI: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  EXCLUDED: "bg-slate-50 text-slate-500 ring-slate-100",
};

const STATUS_LABELS: Record<string, string> = {
  NEW: "New",
  PARTIAL: "Partial",
  MATCHED_SINGLE: "Matched",
  MATCHED_MULTI: "Matched (multi)",
  EXCLUDED: "Excluded",
};

function formatMoney(value: number | string | null | undefined) {
  const num = typeof value === "number" ? value : Number(value || 0);
  const sign = num < 0 ? "-" : "";
  const abs = Math.abs(num).toFixed(2);
  return `${sign}$${abs}`;
}

function getCookie(name: string) {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const trimmed = cookie.trim();
    if (trimmed.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmed.substring(name.length + 1));
    }
  }
  return null;
}

function StatusPill({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] || "bg-slate-50 text-slate-500 ring-slate-100";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ring-1 ${cls}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function SidePill({ side }: { side: "IN" | "OUT" }) {
  const isIn = side === "IN";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${
        isIn
          ? "bg-emerald-50 text-emerald-700 ring-emerald-100"
          : "bg-rose-50 text-rose-700 ring-rose-100"
      }`}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      {isIn ? "Money in" : "Money out"}
    </span>
  );
}

function BankFeedPage() {
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [accountsError, setAccountsError] = useState<string | null>(null);

  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [transactionsError, setTransactionsError] = useState<string | null>(null);

  const [expenseCategories, setExpenseCategories] = useState<CategoryOption[]>([]);
  const [incomeCategories, setIncomeCategories] = useState<CategoryOption[]>([]);
  const [suppliers, setSuppliers] = useState<ContactOption[]>([]);
  const [customers, setCustomers] = useState<ContactOption[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(true);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [activeTab, setActiveTab] = useState<"ALLOCATE" | "CREATE" | "TRANSFER" | "EXCLUDE">(
    "ALLOCATE",
  );
  const [selectedTxId, setSelectedTxId] = useState<number | null>(null);

  const [createCategoryId, setCreateCategoryId] = useState<string>("");
  const [createContactId, setCreateContactId] = useState<string>("");
  const [createMemo, setCreateMemo] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [allocationSelections, setAllocationSelections] = useState<Record<number, string>>({});
  const [manualAllocations, setManualAllocations] = useState<ManualAllocationRow[]>([]);
  const [feeAccountId, setFeeAccountId] = useState("");
  const [feeAmount, setFeeAmount] = useState("");
  const [roundingAccountId, setRoundingAccountId] = useState("");
  const [roundingAmount, setRoundingAmount] = useState("");
  const [overpaymentAccountId, setOverpaymentAccountId] = useState("");
  const [overpaymentAmount, setOverpaymentAmount] = useState("");

  const csrfToken = useMemo(() => getCookie("csrftoken"), []);

  const fetchAccounts = useCallback(async () => {
    setAccountsLoading(true);
    setAccountsError(null);
    try {
      const res = await fetch("/api/banking/overview/", { credentials: "same-origin" });
      if (!res.ok) {
        throw new Error("Unable to load bank accounts.");
      }
      const data = await res.json();
      const normalized: BankAccount[] = (data.accounts || []).map((acc: any) => ({
        id: acc.id,
        name: acc.name,
        last4: acc.last4 || "",
        ledgerBalance: Number(acc.ledger_balance || 0),
      }));
      setAccounts(normalized);
      setSelectedAccountId((current) => {
        if (current && normalized.some((acc) => acc.id === current)) {
          return current;
        }
        return normalized[0]?.id ?? null;
      });
    } catch (err) {
      setAccountsError(err instanceof Error ? err.message : "Unable to load bank accounts.");
    } finally {
      setAccountsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  const fetchTransactions = useCallback(async () => {
    if (!selectedAccountId) {
      setTransactions([]);
      setStatusCounts({});
      setSelectedTxId(null);
      setTransactionsError(null);
      setTransactionsLoading(false);
      return;
    }
    setTransactionsLoading(true);
    setTransactionsError(null);
    const params = new URLSearchParams();
    params.set("account_id", String(selectedAccountId));
    params.set("status", statusFilter);
    try {
      const res = await fetch(`/api/banking/feed/transactions/?${params.toString()}`, {
        credentials: "same-origin",
      });
      if (!res.ok) {
        throw new Error("Unable to load transactions.");
      }
      const data = await res.json();
      const txs: BankTransaction[] = (data.transactions || []).map((tx: any) => ({
        id: tx.id,
        date: tx.date,
        description: tx.description,
        amount: Number(tx.amount || 0),
        status: tx.status,
        statusLabel: tx.status_label || tx.status,
        side: tx.side,
        allocatedAmount: Number(tx.allocated_amount || 0),
        posted_journal_entry: tx.posted_journal_entry || null,
        expense_candidates: tx.expense_candidates || [],
        invoice_candidates: tx.invoice_candidates || [],
      }));
      setTransactions(txs);
      setStatusCounts({
        NEW: 0,
        PARTIAL: 0,
        MATCHED_SINGLE: 0,
        MATCHED_MULTI: 0,
        EXCLUDED: 0,
        ...(data.status_counts || {}),
      });
      const latestBalance = Number(data.account?.ledger_balance ?? data.balance ?? 0);
      setAccounts((prev) =>
        prev.map((acc) =>
          acc.id === selectedAccountId ? { ...acc, ledgerBalance: latestBalance } : acc,
        ),
      );
      if (txs.length > 0) {
        setSelectedTxId((current) => current && txs.some((t) => t.id === current) ? current : txs[0].id);
      } else {
        setSelectedTxId(null);
      }
    } catch (err) {
      setTransactionsError(err instanceof Error ? err.message : "Unable to load transactions.");
    } finally {
      setTransactionsLoading(false);
    }
  }, [selectedAccountId, statusFilter]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  useEffect(() => {
    let isMounted = true;
    setMetadataLoading(true);
    setMetadataError(null);
    fetch("/api/banking/feed/metadata/", { credentials: "same-origin" })
      .then((res) => {
        if (!res.ok) {
          throw new Error("Unable to load categories.");
        }
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        setExpenseCategories(data.expense_categories || []);
        setIncomeCategories(data.income_categories || []);
        setSuppliers(data.suppliers || []);
        setCustomers(data.customers || []);
      })
      .catch((err: Error) => {
        if (isMounted) {
          setMetadataError(err.message);
        }
      })
      .finally(() => {
        if (isMounted) {
          setMetadataLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const postAction = useCallback(
    async (url: string, payload?: Record<string, unknown>) => {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
        body: JSON.stringify(payload || {}),
      });
      if (!res.ok) {
        let detail = "Unable to complete action.";
        try {
          const data = await res.json();
          detail = data?.detail || data?.error || detail;
        } catch {
          // ignore parse errors
        }
        throw new Error(detail);
      }
      try {
        return await res.json();
      } catch {
        return {};
      }
    },
    [csrfToken],
  );

  const filteredTransactions = useMemo(() => {
    if (statusFilter === "ALL") {
      return transactions;
    }
    return transactions.filter((tx) => tx.status === statusFilter);
  }, [transactions, statusFilter]);

  useEffect(() => {
    if (filteredTransactions.length === 0) {
      setSelectedTxId(null);
      return;
    }
    if (!selectedTxId) {
      setSelectedTxId(filteredTransactions[0].id);
      return;
    }
    if (!filteredTransactions.some((tx) => tx.id === selectedTxId)) {
      setSelectedTxId(filteredTransactions[0].id);
    }
  }, [filteredTransactions, selectedTxId]);

  const account = accounts.find((a) => a.id === selectedAccountId) || null;

  const selectedTx =
    filteredTransactions.find((t) => t.id === selectedTxId) ||
    filteredTransactions[0] ||
    null;

  useEffect(() => {
    if (!selectedTx) {
      setCreateCategoryId("");
      setCreateContactId("");
      return;
    }
    const categories =
      selectedTx.side === "OUT" ? expenseCategories : incomeCategories;
    if (categories.length > 0) {
      setCreateCategoryId((prev) => {
        if (prev && categories.some((cat) => String(cat.id) === prev)) {
          return prev;
        }
        return String(categories[0].id);
      });
    } else {
      setCreateCategoryId("");
    }
    setCreateContactId("");
    setAllocationSelections({});
    setManualAllocations([]);
    setFeeAccountId("");
    setFeeAmount("");
    setRoundingAccountId("");
    setRoundingAmount("");
    setOverpaymentAccountId("");
    setOverpaymentAmount("");
  }, [selectedTx?.id, expenseCategories, incomeCategories]);

  useEffect(() => {
    setCreateMemo("");
    setActionError(null);
    setActionSuccess(null);
  }, [selectedTx?.id]);

  const availableCategories =
    selectedTx && selectedTx.side === "OUT" ? expenseCategories : incomeCategories;
  const availableContacts =
    selectedTx && selectedTx.side === "OUT" ? suppliers : customers;
  const contactLabel = selectedTx && selectedTx.side === "OUT" ? "Supplier" : "Customer";
  const canCreateEntry = Boolean(selectedTx && createCategoryId);

  const totalStatusCount = useMemo(
    () =>
      Object.keys(statusCounts).reduce(
        (sum, key) => sum + Number(statusCounts[key] || 0),
        0,
      ),
    [statusCounts],
  );

  const statusFilters = [
    { key: "ALL", label: "All", count: totalStatusCount },
    { key: "NEW", label: "New", count: statusCounts.NEW ?? 0 },
    { key: "PARTIAL", label: "Partial", count: statusCounts.PARTIAL ?? 0 },
    { key: "MATCHED_SINGLE", label: "Matched", count: statusCounts.MATCHED_SINGLE ?? 0 },
    { key: "MATCHED_MULTI", label: "Matched (multi)", count: statusCounts.MATCHED_MULTI ?? 0 },
    { key: "EXCLUDED", label: "Excluded", count: statusCounts.EXCLUDED ?? 0 },
  ];

  const isDeposit = selectedTx?.side === "IN";
  const candidateList: MatchCandidate[] = selectedTx
    ? isDeposit
      ? selectedTx.invoice_candidates
      : selectedTx.expense_candidates
    : [];

  const toleranceCents = 2;
  const toleranceValue = toleranceCents / 100;

  const parseAmountInput = useCallback((value: string) => {
    if (typeof value !== "string") return 0;
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
  }, []);

  const handleCandidateToggle = useCallback(
    (candidate: MatchCandidate, enabled: boolean) => {
      setAllocationSelections((prev) => {
        const next = { ...prev };
        if (!enabled) {
          delete next[candidate.id];
        } else {
          next[candidate.id] = candidate.amount.toFixed(2);
        }
        return next;
      });
    },
    [],
  );

  const handleCandidateAmountChange = useCallback((candidateId: number, value: string) => {
    setAllocationSelections((prev) => ({ ...prev, [candidateId]: value }));
  }, []);

  const addManualAllocationRow = useCallback(() => {
    if (!selectedTx) return;
    const key = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const defaultType: ManualAllocationRow["type"] = selectedTx.side === "IN" ? "DIRECT_INCOME" : "DIRECT_EXPENSE";
    setManualAllocations((rows) => [
      ...rows,
      { key, type: defaultType, accountId: "", amount: "" },
    ]);
  }, [selectedTx]);

  const updateManualAllocationRow = useCallback(
    (key: string, patch: Partial<ManualAllocationRow>) => {
      setManualAllocations((rows) =>
        rows.map((row) => (row.key === key ? { ...row, ...patch } : row)),
      );
    },
    [],
  );

  const removeManualAllocationRow = useCallback((key: string) => {
    setManualAllocations((rows) => rows.filter((row) => row.key !== key));
  }, []);

  const allocationSummary = useMemo(() => {
    if (!selectedTx) {
      return {
        bankAmount: 0,
        totalAllocations: 0,
        candidateTotal: 0,
        manualTotal: 0,
        feeValue: 0,
        roundingValue: 0,
        overpaymentValue: 0,
        expectedBank: 0,
        remaining: 0,
        allocationCount: 0,
        isReady: false,
      };
    }
    const candidateTotal = Object.values(allocationSelections).reduce(
      (sum, value) => sum + parseAmountInput(value),
      0,
    );
    const manualTotal = manualAllocations.reduce(
      (sum, row) => sum + parseAmountInput(row.amount),
      0,
    );
    const totalAllocations = candidateTotal + manualTotal;
    const feeValue = parseAmountInput(feeAmount);
    const roundingRaw = Number(roundingAmount);
    const roundingValue = Number.isFinite(roundingRaw) ? roundingRaw : 0;
    const overpaymentValue = parseAmountInput(overpaymentAmount);
    const bankAmount = Math.abs(selectedTx.amount);

    const expectedBank = isDeposit
      ? totalAllocations + overpaymentValue - feeValue - roundingValue
      : totalAllocations + feeValue + roundingValue;
    const remaining = bankAmount - expectedBank;

    const allocationCount =
      Object.keys(allocationSelections).length +
      manualAllocations.filter((row) => parseAmountInput(row.amount) > 0 && row.accountId).length;

    const hasFee = feeValue > 0;
    const hasRounding = roundingValue !== 0;
    const hasOverpayment = overpaymentValue > 0;

    const isReady =
      totalAllocations > 0 &&
      Math.abs(remaining) <= toleranceValue &&
      (!hasFee || Boolean(feeAccountId)) &&
      (!hasRounding || Boolean(roundingAccountId)) &&
      (!hasOverpayment || (Boolean(overpaymentAccountId) && isDeposit));

    return {
      bankAmount,
      totalAllocations,
      candidateTotal,
      manualTotal,
      feeValue,
      roundingValue,
      overpaymentValue,
      expectedBank,
      remaining,
      allocationCount,
      isReady,
    };
  }, [
    allocationSelections,
    manualAllocations,
    feeAmount,
    roundingAmount,
    overpaymentAmount,
    feeAccountId,
    roundingAccountId,
    overpaymentAccountId,
    parseAmountInput,
    selectedTx,
    isDeposit,
    toleranceValue,
  ]);

  const handleCreateEntry = async () => {
    if (!selectedTx || !createCategoryId) {
      setActionError("Select a category before posting this entry.");
      return;
    }
    setActionSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    const payload: Record<string, unknown> = {
      category_id: Number(createCategoryId),
      memo: createMemo,
    };
    if (selectedTx.side === "OUT" && createContactId) {
      payload.supplier_id = Number(createContactId);
    }
    if (selectedTx.side === "IN" && createContactId) {
      payload.customer_id = Number(createContactId);
    }
    try {
      await postAction(`/api/banking/feed/transactions/${selectedTx.id}/create/`, payload);
      setActionSuccess("Entry posted to the ledger.");
      setCreateMemo("");
      setCreateContactId("");
      await Promise.all([fetchTransactions(), fetchAccounts()]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to post this entry.");
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleAllocate = async () => {
    if (!selectedTx) return;
    const isIncoming = selectedTx.side === "IN";

    const candidatePayload = Object.entries(allocationSelections)
      .map(([id, value]) => ({
        id: Number(id),
        amountValue: parseAmountInput(value),
      }))
      .filter((item) => item.amountValue > 0)
      .map((item) => ({
        type: isIncoming ? "INVOICE" : "BILL",
        id: item.id,
        amount: item.amountValue.toFixed(2),
      }));

    const manualPayload = manualAllocations
      .map((row) => ({
        type: row.type,
        account_id: row.accountId ? Number(row.accountId) : null,
        amountValue: parseAmountInput(row.amount),
      }))
      .filter((row) => row.account_id && row.amountValue > 0)
      .map((row) => ({
        type: row.type,
        account_id: row.account_id,
        amount: row.amountValue.toFixed(2),
      }));

    const allocationsPayload = [...candidatePayload, ...manualPayload];
    if (allocationsPayload.length === 0) {
      setActionError("Add at least one allocation amount.");
      return;
    }

    const body: Record<string, unknown> = {
      allocations: allocationsPayload,
      tolerance_cents: toleranceCents,
      operation_id: `banktx-${selectedTx.id}-${Date.now()}`,
    };

    const feeValue = parseAmountInput(feeAmount);
    if (feeAccountId && feeValue > 0) {
      body.fees = { account_id: Number(feeAccountId), amount: feeValue.toFixed(2) };
    }

    const roundingRaw = Number(roundingAmount);
    const roundingValue = Number.isFinite(roundingRaw) ? roundingRaw : 0;
    if (roundingAccountId && roundingValue !== 0) {
      body.rounding = {
        account_id: Number(roundingAccountId),
        amount: roundingValue.toFixed(2),
      };
    }

    const overpayValue = parseAmountInput(overpaymentAmount);
    if (isIncoming && overpaymentAccountId && overpayValue > 0) {
      body.overpayment = {
        account_id: Number(overpaymentAccountId),
        amount: overpayValue.toFixed(2),
      };
    }

    setActionSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const data = await postAction(
        `/api/banking/transactions/${selectedTx.id}/allocate/`,
        body,
      );
      if (!data?.ok) {
        throw new Error(data?.error || "Unable to allocate this transaction.");
      }
      setActionSuccess("Allocation posted to the ledger.");
      setAllocationSelections({});
      setManualAllocations([]);
      setFeeAccountId("");
      setFeeAmount("");
      setRoundingAccountId("");
      setRoundingAmount("");
      setOverpaymentAccountId("");
      setOverpaymentAmount("");
      await Promise.all([fetchTransactions(), fetchAccounts()]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to allocate this transaction.");
    } finally {
      setActionSubmitting(false);
    }
  };


  const handleExclude = async () => {
    if (!selectedTx) return;
    setActionSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await postAction(`/api/banking/feed/transactions/${selectedTx.id}/exclude/`);
      setActionSuccess("Transaction excluded from review.");
      await Promise.all([fetchTransactions(), fetchAccounts()]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to exclude this transaction.");
    } finally {
      setActionSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="text-[11px] font-semibold tracking-[0.18em] text-slate-400 uppercase mb-2">
              BANK FEED
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900 mb-1">
              Review bank transactions
            </h1>
            <p className="text-sm text-slate-500 max-w-xl">
              Match bank activity to invoices and expenses, or create new transactions directly from your feed.
            </p>
          </div>

          <div className="flex flex-col items-stretch gap-3 sm:items-end">
            <div className="flex items-center gap-2">
              <select
                className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 shadow-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                value={selectedAccountId ?? ""}
                onChange={(e) =>
                  setSelectedAccountId(e.target.value ? Number(e.target.value) : null)
                }
                disabled={accountsLoading || !accounts.length}
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {`${acc.name}${acc.last4 ? ` ••••${acc.last4}` : ""}`}
                  </option>
                ))}
              </select>
              <a
                href="/bank-feeds/new/"
                className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
              >
                Import CSV
              </a>
            </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-right text-xs text-slate-500 shadow-sm">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400 mb-1">
                  Current balance (ledger)
                </div>
                <div className="text-sm font-semibold text-slate-900">
                  {account ? formatMoney(account.ledgerBalance) : "—"}
                </div>
              </div>
            </div>
        </header>

        {accountsError && (
          <div className="mb-4 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs text-rose-600">
            {accountsError}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,3fr)]">
          <section className="rounded-3xl bg-white shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100 flex flex-col min-h-[420px]">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <div>
                <h2 className="text-[13px] font-semibold text-slate-900">Imported transactions</h2>
                <p className="text-[11px] text-slate-500">Review and assign each line to keep your books up to date.</p>
              </div>
              <div className="flex gap-1 rounded-full bg-slate-50 p-1">
                {statusFilters.map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setStatusFilter(f.key)}
                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition ${
                      statusFilter === f.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    <span>{f.label}</span>
                    <span className="ml-1 text-[10px] font-semibold text-slate-400">{f.count ?? 0}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="border-b border-slate-100 px-4 py-2">
              <input
                type="search"
                placeholder="Search description or amount"
                className="h-8 w-full rounded-full border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                disabled
              />
            </div>

            <div className="flex-1 overflow-y-auto">
              {transactionsError ? (
                <div className="flex h-full flex-col items-center justify-center px-8 py-10 text-center text-xs text-rose-500">
                  <p>{transactionsError}</p>
                </div>
              ) : transactionsLoading ? (
                <div className="flex h-full flex-col items-center justify-center px-8 py-10 text-center text-xs text-slate-400">
                  <p>Loading transactions…</p>
                </div>
              ) : filteredTransactions.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center px-8 py-10 text-center text-xs text-slate-400">
                  <p>No transactions for this filter yet.</p>
                  <p className="mt-1">Try switching the status filter or importing a new CSV.</p>
                </div>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {filteredTransactions.map((tx) => {
                    const isSelected = selectedTx && tx.id === selectedTx.id;
                    return (
                      <li
                        key={tx.id}
                        className={`cursor-pointer px-4 py-3 text-xs transition hover:bg-slate-50 ${
                          isSelected ? "bg-slate-50" : "bg-white"
                        }`}
                        onClick={() => setSelectedTxId(tx.id)}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-medium text-slate-500">{tx.date}</span>
                              <StatusPill status={tx.status} />
                            </div>
                            <p className="mt-1 truncate text-[13px] font-medium text-slate-900">{tx.description}</p>
                          </div>

                          <div className="flex flex-col items-end gap-1">
                            <SidePill side={tx.side} />
                            <div
                              className={`text-sm font-semibold ${
                                tx.amount >= 0 ? "text-emerald-600" : "text-rose-600"
                              }`}
                            >
                              {formatMoney(tx.amount)}
                            </div>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>

          <section className="rounded-3xl bg-white shadow-[0_18px_45px_rgba(15,23,42,0.06)] ring-1 ring-slate-100 min-h-[420px] flex flex-col">
            {selectedTx ? (
              <>
                <div className="border-b border-slate-100 px-6 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] font-semibold tracking-[0.16em] text-slate-400 uppercase">
                        {selectedTx.date}
                      </p>
                      <h2 className="mt-1 text-sm font-semibold text-slate-900">
                        {selectedTx.description}
                      </h2>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                        <SidePill side={selectedTx.side} />
                        <span className="inline-flex items-center rounded-full bg-slate-50 px-2 py-0.5 font-medium text-slate-500 ring-1 ring-slate-100">
                          Bank feed
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className={`text-lg font-semibold ${
                          selectedTx.amount >= 0 ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        {formatMoney(selectedTx.amount)}
                      </div>
                      <div className="mt-1 flex items-center justify-end gap-2 text-[11px] text-slate-500">
                        Status: <StatusPill status={selectedTx.status} />
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Allocated: {formatMoney(selectedTx.allocatedAmount)}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-b border-slate-100 px-6">
                  <nav className="flex gap-4 text-xs font-medium text-slate-500">
                    {[
                      { key: "ALLOCATE", label: "Allocate" },
                      { key: "CREATE", label: "Create" },
                      { key: "TRANSFER", label: "Transfer" },
                      { key: "EXCLUDE", label: "Exclude" },
                    ].map((tab) => (
                      <button
                        key={tab.key}
                        type="button"
                        onClick={() =>
                          setActiveTab(
                            tab.key as "ALLOCATE" | "CREATE" | "TRANSFER" | "EXCLUDE",
                          )
                        }
                        className={`relative py-3 transition ${
                          activeTab === tab.key
                            ? "text-slate-900"
                            : "text-slate-500 hover:text-slate-800"
                        }`}
                      >
                        {tab.label}
                        {activeTab === tab.key && (
                          <span className="absolute inset-x-0 -bottom-px block h-[2px] rounded-full bg-sky-500" />
                        )}
                      </button>
                    ))}
                  </nav>
                </div>

                <div className="flex-1 overflow-y-auto px-6 py-4 text-sm">
                  {actionError && (
                    <div className="mb-3 rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
                      {actionError}
                    </div>
                  )}
                  {actionSuccess && (
                    <div className="mb-3 rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-[11px] text-emerald-700">
                      {actionSuccess}
                    </div>
                  )}
                  {activeTab === "CREATE" && (
                    <div className="space-y-5 max-w-md">
                      <p className="text-xs text-slate-500">
                        Turn this bank line into a new expense or income entry. Mini-Books will post it to the right accounts in your ledger.
                      </p>

                      {metadataError && (
                        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
                          {metadataError}
                        </div>
                      )}

                      <div className="space-y-3">
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-600">
                            Transaction type
                          </label>
                          <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1 text-xs font-medium">
                            <button className="rounded-full bg-white px-3 py-1 shadow-sm text-slate-900">
                              {selectedTx.amount >= 0 ? "Income" : "Expense"}
                            </button>
                            <button className="rounded-full px-3 py-1 text-slate-400" disabled>
                              Transfer
                            </button>
                          </div>
                        </div>

                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-600">
                            Category
                          </label>
                          <select
                            className="h-9 w-full rounded-2xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                            value={createCategoryId}
                            onChange={(e) => setCreateCategoryId(e.target.value)}
                            disabled={
                              metadataLoading ||
                              availableCategories.length === 0 ||
                              actionSubmitting
                            }
                          >
                            {availableCategories.map((cat) => (
                              <option key={cat.id} value={cat.id}>
                                {cat.name}
                              </option>
                            ))}
                          </select>
                          {!metadataLoading && availableCategories.length === 0 && (
                            <p className="mt-1 text-[11px] text-rose-500">
                              Add {selectedTx.amount >= 0 ? "income" : "expense"} categories to
                              your chart of accounts to post directly from the feed.
                            </p>
                          )}
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <label className="mb-1 block text-xs font-medium text-slate-600">
                              {contactLabel} (optional)
                            </label>
                            <select
                              className="h-9 w-full rounded-2xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                              value={createContactId}
                              onChange={(e) => setCreateContactId(e.target.value)}
                              disabled={actionSubmitting || availableContacts.length === 0}
                            >
                              <option value="">
                                {selectedTx.side === "OUT" ? "No supplier" : "No customer"}
                              </option>
                              {availableContacts.map((contact) => (
                                <option key={contact.id} value={contact.id}>
                                  {contact.name}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="mb-1 block text-xs font-medium text-slate-600">
                              Memo
                            </label>
                            <input
                              className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                              placeholder="Internal note"
                              value={createMemo}
                              onChange={(e) => setCreateMemo(e.target.value)}
                              disabled={actionSubmitting}
                            />
                          </div>
                        </div>

                        <div className="pt-2">
                          <button
                            type="button"
                            onClick={handleCreateEntry}
                            disabled={!canCreateEntry || actionSubmitting || metadataLoading}
                            className={`inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold text-white shadow-sm ${
                              !canCreateEntry || actionSubmitting || metadataLoading
                                ? "cursor-not-allowed bg-emerald-400"
                                : "bg-emerald-600 hover:bg-emerald-700"
                            }`}
                          >
                            {actionSubmitting ? "Posting…" : "Create & post to ledger"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "ALLOCATE" && selectedTx && (
                    <div className="space-y-5">
                      {actionSuccess && (
                        <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-[11px] text-emerald-700">
                          {actionSuccess}
                        </div>
                      )}
                      {actionError && (
                        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
                          {actionError}
                        </div>
                      )}

                      <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4">
                        <div className="mb-3 flex items-center justify-between">
                          <div>
                            <p className="text-[11px] font-semibold text-slate-500 uppercase">
                              Suggested {isDeposit ? "invoices" : "bills"}
                            </p>
                            <p className="text-[11px] text-slate-500">
                              Select which documents this bank line belongs to.
                            </p>
                          </div>
                        </div>
                        <div className="space-y-3">
                          {candidateList.length ? (
                            candidateList.map((candidate) => {
                              const checked = Object.prototype.hasOwnProperty.call(
                                allocationSelections,
                                candidate.id,
                              );
                              const value = allocationSelections[candidate.id] || "";
                              return (
                                <div
                                  key={candidate.id}
                                  className="rounded-xl bg-white px-3 py-2 text-xs text-slate-700 shadow-sm"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-3">
                                    <label className="flex items-center gap-2">
                                      <input
                                        type="checkbox"
                                        className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                                        checked={checked}
                                        onChange={(e) => handleCandidateToggle(candidate, e.target.checked)}
                                      />
                                      <div>
                                        <div className="font-medium text-slate-900">
                                          {candidate.invoice_number
                                            ? `Invoice #${candidate.invoice_number}`
                                            : candidate.description || (isDeposit ? "Invoice" : "Bill")}
                                          {candidate.customer ? ` · ${candidate.customer}` : ""}
                                        </div>
                                        <div className="text-[11px] text-slate-500">
                                          {candidate.date} • {formatMoney(candidate.amount)}
                                        </div>
                                      </div>
                                    </label>
                                    <input
                                      type="number"
                                      step="0.01"
                                      min="0"
                                      className="h-9 w-32 rounded-full border border-slate-200 bg-white px-3 text-right text-xs text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
                                      value={value}
                                      disabled={!checked}
                                      onChange={(e) =>
                                        handleCandidateAmountChange(candidate.id, e.target.value)
                                      }
                                    />
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            <p className="text-[11px] text-slate-500">No suggestions yet.</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-100 bg-white px-4 py-4">
                        <div className="mb-3 flex items-center justify-between">
                          <div>
                            <p className="text-[11px] font-semibold text-slate-500 uppercase">
                              Additional splits
                            </p>
                            <p className="text-[11px] text-slate-500">
                              Send part of the amount directly to ledger accounts.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={addManualAllocationRow}
                            className="inline-flex items-center rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold text-white shadow-sm hover:bg-black"
                          >
                            + Add split
                          </button>
                        </div>
                        <div className="space-y-3 text-xs">
                          {manualAllocations.length === 0 && (
                            <p className="text-[11px] text-slate-500">No manual splits yet.</p>
                          )}
                          {manualAllocations.map((row) => {
                            const options =
                              selectedTx.side === "IN"
                                ? [{ value: "DIRECT_INCOME", label: "Direct income" }]
                                : [{ value: "DIRECT_EXPENSE", label: "Direct expense" }];
                            return (
                              <div
                                key={row.key}
                                className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <select
                                    value={row.type}
                                    onChange={(e) =>
                                      updateManualAllocationRow(row.key, {
                                        type: e.target.value as ManualAllocationRow["type"],
                                      })
                                    }
                                    className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                                    disabled={options.length === 1}
                                  >
                                    {options.map((opt) => (
                                      <option key={opt.value} value={opt.value}>
                                        {opt.label}
                                      </option>
                                    ))}
                                  </select>
                                  <input
                                    className="h-9 flex-1 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                                    placeholder="Account ID"
                                    value={row.accountId}
                                    onChange={(e) =>
                                      updateManualAllocationRow(row.key, { accountId: e.target.value })
                                    }
                                  />
                                  <input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    className="h-9 w-28 rounded-full border border-slate-200 bg-white px-3 text-right text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                                    placeholder="Amount"
                                    value={row.amount}
                                    onChange={(e) =>
                                      updateManualAllocationRow(row.key, { amount: e.target.value })
                                    }
                                  />
                                  <button
                                    type="button"
                                    onClick={() => removeManualAllocationRow(row.key)}
                                    className="text-[11px] font-medium text-rose-500 hover:text-rose-600"
                                  >
                                    Remove
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-100 bg-white px-4 py-4">
                        <p className="text-[11px] font-semibold text-slate-500 uppercase mb-3">
                          Adjustments
                        </p>
                        <div className="grid gap-3 text-xs md:grid-cols-2">
                          <div className="space-y-2">
                            <label className="text-[11px] font-medium text-slate-600">
                              Processor fee
                            </label>
                            <div className="flex gap-2">
                              <input
                                className="h-9 flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                placeholder="Account ID"
                                value={feeAccountId}
                                onChange={(e) => setFeeAccountId(e.target.value)}
                              />
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                className="h-9 w-28 rounded-full border border-slate-200 bg-slate-50 px-3 text-right text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                placeholder="0.00"
                                value={feeAmount}
                                onChange={(e) => setFeeAmount(e.target.value)}
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <label className="text-[11px] font-medium text-slate-600">
                              Rounding
                            </label>
                            <div className="flex gap-2">
                              <input
                                className="h-9 flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                placeholder="Account ID"
                                value={roundingAccountId}
                                onChange={(e) => setRoundingAccountId(e.target.value)}
                              />
                              <input
                                type="number"
                                step="0.01"
                                className="h-9 w-28 rounded-full border border-slate-200 bg-slate-50 px-3 text-right text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                placeholder="0.00"
                                value={roundingAmount}
                                onChange={(e) => setRoundingAmount(e.target.value)}
                              />
                            </div>
                          </div>
                          {isDeposit && (
                            <div className="space-y-2 md:col-span-2">
                              <label className="text-[11px] font-medium text-slate-600">
                                Overpayment → credit
                              </label>
                              <div className="flex flex-col gap-2 md:flex-row">
                                <input
                                  className="h-9 flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                  placeholder="Liability account ID"
                                  value={overpaymentAccountId}
                                  onChange={(e) => setOverpaymentAccountId(e.target.value)}
                                />
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  className="h-9 w-32 rounded-full border border-slate-200 bg-slate-50 px-3 text-right text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                  placeholder="0.00"
                                  value={overpaymentAmount}
                                  onChange={(e) => setOverpaymentAmount(e.target.value)}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-100 bg-white px-4 py-4">
                        <div className="grid gap-3 text-xs sm:grid-cols-3">
                          <div>
                            <p className="text-[11px] font-medium text-slate-500 uppercase">
                              Bank amount
                            </p>
                            <p className="text-sm font-semibold text-slate-900">
                              {formatMoney(allocationSummary.bankAmount)}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-medium text-slate-500 uppercase">
                              Allocated
                            </p>
                            <p className="text-sm font-semibold text-slate-900">
                              {formatMoney(allocationSummary.totalAllocations)}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-medium text-slate-500 uppercase">
                              Remaining
                            </p>
                            <p
                              className={`text-sm font-semibold ${
                                Math.abs(allocationSummary.remaining) <= toleranceValue
                                  ? "text-emerald-600"
                                  : "text-rose-600"
                              }`}
                            >
                              {formatMoney(allocationSummary.remaining)}
                            </p>
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] text-slate-500">
                          Must reconcile within ±${toleranceValue.toFixed(2)}.
                        </p>
                        <div className="pt-3">
                          <button
                            type="button"
                            onClick={handleAllocate}
                            disabled={!allocationSummary.isReady || actionSubmitting}
                            className={`inline-flex w-full items-center justify-center rounded-full px-4 py-2 text-xs font-semibold shadow-sm ${
                              !allocationSummary.isReady || actionSubmitting
                                ? "cursor-not-allowed bg-slate-100 text-slate-400"
                                : "bg-slate-900 text-white hover:bg-black"
                            }`}
                          >
                            {actionSubmitting ? "Posting…" : "Allocate"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "TRANSFER" && (
                    <div className="space-y-5 max-w-md">
                      <p className="text-xs text-slate-500">
                        Use a transfer when this movement is between your own accounts (for example, moving money from checking to savings).
                      </p>

                      <div className="space-y-3">
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-600">
                            From account
                          </label>
                          <input
                            className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                            defaultValue={account?.name || ""}
                            disabled
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-slate-600">
                            To account
                          </label>
                          <input
                            className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                            placeholder="e.g. Savings, Credit card"
                          />
                        </div>
                        <div className="pt-2">
                          <button className="inline-flex items-center rounded-full bg-sky-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-sky-700">
                            Record transfer
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "EXCLUDE" && (
                    <div className="space-y-4 max-w-md">
                      <p className="text-xs text-slate-500">
                        Exclude this line if it's a duplicate, personal transaction, or otherwise not relevant to your business books. It will remain in the feed but won't affect your reports.
                      </p>

                      <div className="rounded-2xl border border-rose-100 bg-rose-50 px-3 py-3 text-[11px] text-rose-700">
                        You can always undo this later from the bank feed if you exclude something by mistake.
                      </div>

                      <button
                        type="button"
                        onClick={handleExclude}
                        disabled={
                          !selectedTx ||
                          selectedTx.status !== "NEW" ||
                          actionSubmitting
                        }
                        className={`inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold ring-1 ${
                          !selectedTx || selectedTx.status !== "NEW" || actionSubmitting
                            ? "cursor-not-allowed bg-slate-100 text-slate-400 ring-slate-200"
                            : "bg-white text-rose-600 ring-rose-200 hover:bg-rose-50"
                        }`}
                      >
                        Exclude from books
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : transactionsLoading ? (
              <div className="flex flex-1 flex-col items-center justify-center px-8 py-10 text-center text-xs text-slate-400">
                <p>Loading transaction…</p>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center px-8 py-10 text-center text-xs text-slate-400">
                <p>Select a transaction on the left to review or create a posting.</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

const rootEl = document.getElementById("bank-feed-root");
if (rootEl) {
  const root = ReactDOM.createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <BankFeedPage />
    </React.StrictMode>,
  );
}

export default BankFeedPage;
