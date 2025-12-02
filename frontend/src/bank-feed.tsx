import React, { useCallback, useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

type BankAccount = {
  id: number;
  name: string;
  last4: string;
  ledgerBalance: number;
  ledgerAccountId?: number | null;
  currency?: string;
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

type LedgerAccountOption = {
  id: number;
  name: string;
  code?: string | null;
};

type TaxRateOption = {
  id: number;
  name: string;
  code?: string | null;
  percentage: number;
};

type TaxTreatment = "NONE" | "INCLUDED" | "ON_TOP";

type ManualAllocationRow = {
  key: string;
  type: "DIRECT_INCOME" | "DIRECT_EXPENSE";
  accountId: string;
  amount: string;
  taxTreatment: TaxTreatment;
  taxRateId: string;
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
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${isIn
        ? "bg-emerald-50 text-emerald-700 ring-emerald-100"
        : "bg-rose-50 text-rose-700 ring-rose-100"
        }`}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      {isIn ? "Money in" : "Money out"}
    </span>
  );
}

function computeTaxParts(amount: string, treatment: TaxTreatment, ratePct: number) {
  const amt = Number(amount || 0);
  const rate = Number(ratePct || 0) / 100;
  const round = (val: number) => Math.round(val * 100) / 100;
  if (!Number.isFinite(amt)) return { net: 0, tax: 0, gross: 0 };
  if (treatment === "INCLUDED") {
    const gross = amt;
    const divisor = 1 + rate;
    const net = divisor === 0 ? gross : gross / divisor;
    const tax = gross - net;
    return { net: round(net), tax: round(tax), gross: round(gross) };
  }
  if (treatment === "ON_TOP") {
    const net = amt;
    const tax = net * rate;
    const gross = net + tax;
    return { net: round(net), tax: round(tax), gross: round(gross) };
  }
  return { net: round(amt), tax: 0, gross: round(amt) };
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
  const [expenseAccounts, setExpenseAccounts] = useState<LedgerAccountOption[]>([]);
  const [incomeAccounts, setIncomeAccounts] = useState<LedgerAccountOption[]>([]);
  const [equityAccounts, setEquityAccounts] = useState<LedgerAccountOption[]>([]);
  const [taxRates, setTaxRates] = useState<TaxRateOption[]>([]);
  const [suppliers, setSuppliers] = useState<ContactOption[]>([]);
  const [customers, setCustomers] = useState<ContactOption[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(true);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [activeTab, setActiveTab] = useState<"ALLOCATE" | "CREATE" | "ADD" | "TRANSFER" | "EXCLUDE">("ALLOCATE");
  const [selectedTxId, setSelectedTxId] = useState<number | null>(null);

  const [createCategoryId, setCreateCategoryId] = useState<string>("");
  const [createContactId, setCreateContactId] = useState<string>("");
  const [createMemo, setCreateMemo] = useState("");
  const [createTaxTreatment, setCreateTaxTreatment] = useState<TaxTreatment>("NONE");
  const [createTaxRateId, setCreateTaxRateId] = useState("");
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
  const [addDirection, setAddDirection] = useState<"IN" | "OUT">("IN");
  const [addAccountId, setAddAccountId] = useState("");
  const [addAmount, setAddAmount] = useState("");
  const [addTaxTreatment, setAddTaxTreatment] = useState<TaxTreatment>("NONE");
  const [addTaxRateId, setAddTaxRateId] = useState("");
  const [addMemo, setAddMemo] = useState("");
  const [addContactId, setAddContactId] = useState("");
  const [createMenuOpen, setCreateMenuOpen] = useState(false);
  const [categoryDrawerOpen, setCategoryDrawerOpen] = useState(false);
  const [categoryDraft, setCategoryDraft] = useState<{
    name: string;
    type: "EXPENSE" | "INCOME";
    code: string;
    description: string;
    accountId: string;
  }>({
    name: "",
    type: "EXPENSE",
    code: "",
    description: "",
    accountId: "",
  });
  const [categoryDrawerError, setCategoryDrawerError] = useState<string | null>(null);
  const [categoryDrawerSaving, setCategoryDrawerSaving] = useState(false);
  const [txDrawerOpen, setTxDrawerOpen] = useState(false);
  const [txSide, setTxSide] = useState<"IN" | "OUT">("IN");
  const [txDate, setTxDate] = useState("");
  const [txAmount, setTxAmount] = useState("");
  const [txDescription, setTxDescription] = useState("");
  const [txMemo, setTxMemo] = useState("");
  const [txDrawerError, setTxDrawerError] = useState<string | null>(null);
  const [txDrawerSaving, setTxDrawerSaving] = useState(false);

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
        ledgerAccountId: acc.ledger_account_id ?? acc.account_id ?? null,
        currency: acc.currency || "USD",
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
      const accountMeta = data.account || {};
      const latestBalance = Number(accountMeta.ledger_balance ?? data.balance ?? 0);
      setAccounts((prev) =>
        prev.map((acc) =>
          acc.id === selectedAccountId
            ? {
              ...acc,
              ledgerBalance: latestBalance,
              ledgerAccountId: accountMeta.ledger_account_id ?? acc.ledgerAccountId ?? null,
              currency: accountMeta.currency || acc.currency,
            }
            : acc,
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
    setCreateMenuOpen(false);
  }, [selectedAccountId]);

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
  const accountCurrency = account?.currency || "USD";

  const loadMetadata = useCallback(async () => {
    setMetadataLoading(true);
    setMetadataError(null);
    try {
      const res = await fetch("/api/banking/feed/metadata/", { credentials: "same-origin" });
      if (!res.ok) {
        throw new Error("Unable to load categories.");
      }
      const data = await res.json();
      setExpenseCategories(data.expense_categories || []);
      setIncomeCategories(data.income_categories || []);
      setSuppliers(data.suppliers || []);
      setCustomers(data.customers || []);
      setExpenseAccounts(data.expense_accounts || []);
      setIncomeAccounts(data.income_accounts || []);
      setEquityAccounts(data.equity_accounts || []);
      setTaxRates(
        (data.tax_rates || []).map((tr: any) => ({
          id: tr.id,
          name: tr.name,
          code: tr.code,
          percentage: Number(tr.percentage || 0),
        })),
      );
    } catch (err) {
      setMetadataError(err instanceof Error ? err.message : "Unable to load categories.");
    } finally {
      setMetadataLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetadata();
  }, [loadMetadata]);

  useEffect(() => {
    const options =
      addDirection === "IN" ? incomeAccounts : [...expenseAccounts, ...equityAccounts];
    if (options.length === 0) return;
    if (!options.some((opt) => String(opt.id) === addAccountId)) {
      setAddAccountId(String(options[0].id));
    }
  }, [addDirection, incomeAccounts, expenseAccounts, equityAccounts, addAccountId]);

  const selectedTx =
    filteredTransactions.find((t) => t.id === selectedTxId) ||
    filteredTransactions[0] ||
    null;

  useEffect(() => {
    if (!selectedTx) {
      setCreateCategoryId("");
      setCreateContactId("");
      setAddAccountId("");
      setAddAmount("");
      setAddContactId("");
      setCreateTaxTreatment("NONE");
      setCreateTaxRateId("");
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
    setCreateTaxTreatment("NONE");
    setCreateTaxRateId(taxRates[0]?.id ? String(taxRates[0].id) : "");
    const defaultDirection: "IN" | "OUT" = selectedTx.side === "IN" ? "IN" : "OUT";
    setAddDirection(defaultDirection);
    const defaultAccounts =
      defaultDirection === "IN" ? incomeAccounts : [...expenseAccounts, ...equityAccounts];
    setAddAccountId(defaultAccounts[0]?.id ? String(defaultAccounts[0].id) : "");
    setAddAmount(Math.abs(selectedTx.amount || 0).toFixed(2));
    setAddTaxTreatment("NONE");
    setAddTaxRateId(taxRates[0]?.id ? String(taxRates[0].id) : "");
    setAddMemo(selectedTx.description || "");
    setAddContactId("");
  }, [selectedTx?.id, expenseCategories, incomeCategories, equityAccounts, taxRates]);

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
  const createRatePct =
    taxRates.find((tr) => String(tr.id) === createTaxRateId)?.percentage || 0;
  const createBaseAmountStr =
    selectedTx && createTaxTreatment === "ON_TOP" && createRatePct > 0
      ? (Math.abs(selectedTx.amount || 0) / (1 + createRatePct / 100)).toFixed(2)
      : selectedTx
        ? Math.abs(selectedTx.amount || 0).toFixed(2)
        : "0";
  const createTaxParts = computeTaxParts(createBaseAmountStr, createTaxTreatment, createRatePct);
  const createAmountMatches = selectedTx
    ? Math.abs(createTaxParts.gross - Math.abs(selectedTx.amount || 0)) <= 0.02
    : false;
  const addAccountOptions = useMemo(
    () =>
      addDirection === "IN"
        ? incomeAccounts
        : [...expenseAccounts, ...equityAccounts],
    [addDirection, expenseAccounts, incomeAccounts, equityAccounts],
  );
  const addRatePct =
    taxRates.find((tr) => String(tr.id) === addTaxRateId)?.percentage || 0;
  const addTaxParts = computeTaxParts(addAmount || "0", addTaxTreatment, addRatePct);
  const bankAmountAbs = selectedTx ? Math.abs(selectedTx.amount || 0) : 0;
  const addAmountMatches = Math.abs(addTaxParts.gross - bankAmountAbs) <= 0.02;
  const canAddEntry =
    Boolean(selectedTx && addAccountId) && addAmountMatches && !actionSubmitting;

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

  const openCategoryDrawer = useCallback(() => {
    const defaultType: "EXPENSE" | "INCOME" = selectedTx?.side === "OUT" ? "EXPENSE" : "INCOME";
    const accountOptions = defaultType === "EXPENSE" ? expenseAccounts : incomeAccounts;
    setCategoryDraft({
      name: "",
      type: defaultType,
      code: "",
      description: "",
      accountId: accountOptions[0]?.id ? String(accountOptions[0].id) : "",
    });
    setCategoryDrawerError(null);
    setCategoryDrawerOpen(true);
    setCreateMenuOpen(false);
  }, [expenseAccounts, incomeAccounts, selectedTx?.side]);

  const handleSaveCategory = useCallback(async () => {
    setCategoryDrawerSaving(true);
    setCategoryDrawerError(null);
    const payload: Record<string, unknown> = {
      name: categoryDraft.name,
      type: categoryDraft.type,
      code: categoryDraft.code,
      description: categoryDraft.description,
      account_id: categoryDraft.accountId ? Number(categoryDraft.accountId) : null,
    };
    try {
      const data = await postAction("/api/categories/", payload);
      const created = data?.category;
      await loadMetadata();
      if (created && selectedTx) {
        const sideType = selectedTx.side === "OUT" ? "EXPENSE" : "INCOME";
        if (created.type === sideType) {
          setCreateCategoryId(String(created.id));
        }
      }
      setCategoryDrawerOpen(false);
      setActionError(null);
      setActionSuccess("Category created and ready to use.");
    } catch (err) {
      setCategoryDrawerError(err instanceof Error ? err.message : "Unable to create category.");
    } finally {
      setCategoryDrawerSaving(false);
    }
  }, [
    categoryDraft.accountId,
    categoryDraft.code,
    categoryDraft.description,
    categoryDraft.name,
    categoryDraft.type,
    loadMetadata,
    postAction,
    selectedTx,
  ]);

  const openTxDrawer = useCallback(() => {
    const defaultSide: "IN" | "OUT" = selectedTx?.side || "IN";
    setTxSide(defaultSide);
    setTxDate(selectedTx?.date || new Date().toISOString().slice(0, 10));
    setTxAmount("");
    setTxDescription("");
    setTxMemo("");
    setTxDrawerError(null);
    setTxDrawerOpen(true);
    setCreateMenuOpen(false);
  }, [selectedTx]);

  const handleCreateManualTx = useCallback(async () => {
    if (!account || !account.ledgerAccountId) {
      setTxDrawerError("Link this bank account to a ledger account before creating a transaction.");
      return;
    }
    const amountNumber = Number(txAmount);
    if (!txAmount || !Number.isFinite(amountNumber) || amountNumber === 0) {
      setTxDrawerError("Enter a non-zero amount.");
      return;
    }
    if (!txDescription.trim()) {
      setTxDrawerError("Add a description before saving.");
      return;
    }
    setTxDrawerSaving(true);
    setTxDrawerError(null);
    const payload: Record<string, unknown> = {
      date: txDate,
      amount: Math.abs(amountNumber),
      description: txDescription.trim(),
      memo: txMemo.trim(),
      side: txSide,
    };
    try {
      await postAction(`/api/accounts/${account.ledgerAccountId}/manual-transaction/`, payload);
      setActionError(null);
      setActionSuccess("Transaction added to your feed.");
      setTxDrawerOpen(false);
      setTxAmount("");
      setTxDescription("");
      setTxMemo("");
      await Promise.all([fetchTransactions(), fetchAccounts()]);
    } catch (err) {
      setTxDrawerError(err instanceof Error ? err.message : "Unable to create transaction.");
    } finally {
      setTxDrawerSaving(false);
    }
  }, [
    account,
    fetchAccounts,
    fetchTransactions,
    postAction,
    txAmount,
    txDate,
    txDescription,
    txMemo,
    txSide,
  ]);

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
    const defaultAccountOptions =
      defaultType === "DIRECT_INCOME" ? incomeAccounts : [...expenseAccounts, ...equityAccounts];
    setManualAllocations((rows) => [
      ...rows,
      {
        key,
        type: defaultType,
        accountId: defaultAccountOptions[0]?.id ? String(defaultAccountOptions[0].id) : "",
        amount: "",
        taxTreatment: "NONE",
        taxRateId: taxRates[0]?.id ? String(taxRates[0].id) : "",
      },
    ]);
  }, [selectedTx, expenseAccounts, incomeAccounts, equityAccounts, taxRates]);

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
    const getRatePct = (row: { taxRateId?: string }) => {
      if (!row.taxRateId) return 0;
      const rate = taxRates.find((tr) => String(tr.id) === row.taxRateId);
      return rate ? rate.percentage : 0;
    };
    const candidateTotal = Object.values(allocationSelections).reduce(
      (sum, value) => sum + parseAmountInput(value),
      0,
    );
    const manualTotal = manualAllocations.reduce((sum, row) => {
      const parts = computeTaxParts(
        row.amount,
        row.taxTreatment || "NONE",
        getRatePct(row),
      );
      return sum + parts.gross;
    }, 0);
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

    const hasAllocations = totalAllocations > 0 && allocationCount > 0;
    const hasRequiredAccounts =
      (!hasFee || Boolean(feeAccountId)) &&
      (!hasRounding || Boolean(roundingAccountId)) &&
      (!hasOverpayment || (Boolean(overpaymentAccountId) && isDeposit));
    const isReady = hasAllocations && hasRequiredAccounts;

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
      hasAllocations,
      hasRequiredAccounts,
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
  ]);

  const handleCreateEntry = async () => {
    if (!selectedTx || !createCategoryId) {
      setActionError("Select a category before posting this entry.");
      return;
    }
    if (!createAmountMatches) {
      setActionError("Tax selection must match the bank amount.");
      return;
    }
    if (createTaxTreatment !== "NONE" && !createTaxRateId) {
      setActionError("Select a tax code for this tax treatment.");
      return;
    }
    setActionSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    const payload: Record<string, unknown> = {
      category_id: Number(createCategoryId),
      memo: createMemo,
      tax_treatment: createTaxTreatment,
      amount: createBaseAmountStr,
    };
    if (createTaxTreatment !== "NONE" && createTaxRateId) {
      payload.tax_rate_id = Number(createTaxRateId);
    }
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
        tax_treatment: row.taxTreatment || "NONE",
        tax_rate_id: row.taxRateId ? Number(row.taxRateId) : null,
      }))
      .filter((row) => row.account_id && row.amountValue > 0)
      .map((row) => ({
        type: row.type,
        account_id: row.account_id,
        amount: row.amountValue.toFixed(2),
        tax_treatment: row.tax_treatment,
        tax_rate_id: row.tax_rate_id || undefined,
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

  const handleAddToLedger = async () => {
    if (!selectedTx || !addAccountId) return;
    const amountValue = parseAmountInput(addAmount);
    if (amountValue <= 0) {
      setActionError("Enter an amount greater than zero.");
      return;
    }
    if (addTaxTreatment !== "NONE" && !addTaxRateId) {
      setActionError("Select a tax code for this tax treatment.");
      return;
    }
    setActionSubmitting(true);
    setActionError(null);
    setActionSuccess(null);
    const payload: Record<string, unknown> = {
      account_id: Number(addAccountId),
      direction: addDirection,
      amount: amountValue.toFixed(2),
      tax_treatment: addTaxTreatment,
      memo: addMemo.trim(),
    };
    if (addTaxTreatment !== "NONE" && addTaxRateId) {
      payload.tax_rate_id = Number(addTaxRateId);
    }
    if (addContactId) {
      if (addDirection === "IN") {
        payload.customer_id = Number(addContactId);
      } else {
        payload.supplier_id = Number(addContactId);
      }
    }
    try {
      const data = await postAction(
        `/api/banking/feed/transactions/${selectedTx.id}/add/`,
        payload,
      );
      if (!data?.success) {
        throw new Error(data?.detail || data?.error || "Unable to post entry.");
      }
      setActionSuccess("Posted to the ledger and reconciled.");
      await Promise.all([fetchTransactions(), fetchAccounts()]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to post this entry.");
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
    <>
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
              <div className="flex flex-wrap items-center gap-2 sm:justify-end">
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
                <div className="relative" onMouseLeave={() => setCreateMenuOpen(false)}>
                  <button
                    type="button"
                    onClick={() => setCreateMenuOpen((open) => !open)}
                    className="inline-flex items-center rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-black"
                  >
                    + Create
                  </button>
                  {createMenuOpen && (
                    <div className="absolute right-0 z-20 mt-1 w-48 rounded-2xl border border-slate-200 bg-white p-1 text-left shadow-lg">
                      <button
                        type="button"
                        onClick={openCategoryDrawer}
                        className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <span>New category</span>
                        <span className="text-slate-400">⌘C</span>
                      </button>
                      <button
                        type="button"
                        onClick={openTxDrawer}
                        disabled={!account?.ledgerAccountId}
                        className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-[11px] font-medium ${account?.ledgerAccountId ? "text-slate-700 hover:bg-slate-50" : "cursor-not-allowed text-slate-300"}`}
                      >
                        <span>New transaction</span>
                        <span className="text-slate-400">⌘T</span>
                      </button>
                      {!account?.ledgerAccountId && (
                        <p className="px-3 pb-2 text-[10px] text-slate-400">
                          Link this bank to a ledger account to post manual transactions.
                        </p>
                      )}
                    </div>
                  )}
                </div>
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
              <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                <div className="min-w-0 flex-shrink-0">
                  <h2 className="text-[13px] font-semibold text-slate-900">Imported transactions</h2>
                  <p className="text-[11px] text-slate-500">Review and assign each line to keep your books up to date.</p>
                </div>
                <div className="w-full flex-1 sm:w-auto">
                  <div className="flex max-w-full flex-wrap items-center gap-1 overflow-x-auto rounded-2xl bg-slate-50 p-2 sm:flex-nowrap sm:justify-end sm:rounded-full sm:p-1 sm:pl-2">
                    {statusFilters.map((f) => (
                      <button
                        key={f.key}
                        type="button"
                        onClick={() => setStatusFilter(f.key)}
                        className={`flex-shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium transition ${statusFilter === f.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                          }`}
                      >
                        <span>{f.label}</span>
                        <span className="ml-1 text-[10px] font-semibold text-slate-400">{f.count ?? 0}</span>
                      </button>
                    ))}
                  </div>
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
                          className={`cursor-pointer px-4 py-3 text-xs transition hover:bg-slate-50 ${isSelected ? "bg-slate-50" : "bg-white"
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
                                className={`text-sm font-semibold ${tx.amount >= 0 ? "text-emerald-600" : "text-rose-600"
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
                          className={`text-lg font-semibold ${selectedTx.amount >= 0 ? "text-emerald-600" : "text-rose-600"
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
                        { key: "ADD", label: "Add to bank account" },
                        { key: "TRANSFER", label: "Transfer" },
                        { key: "EXCLUDE", label: "Exclude" },
                      ].map((tab) => (
                        <button
                          key={tab.key}
                          type="button"
                          onClick={() =>
                            setActiveTab(
                              tab.key as "ALLOCATE" | "CREATE" | "ADD" | "TRANSFER" | "EXCLUDE",
                            )
                          }
                          className={`relative py-3 transition ${activeTab === tab.key
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
                          Turn this bank line into a new expense or income entry. CERN Books will post it to the right accounts in your ledger.
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
                            <div className="mb-1 flex items-center justify-between">
                              <label className="text-xs font-medium text-slate-600">
                                Category
                              </label>
                              <button
                                type="button"
                                onClick={openCategoryDrawer}
                                className="text-[11px] font-semibold text-sky-600 hover:text-sky-700"
                                disabled={metadataLoading}
                              >
                                Create
                              </button>
                            </div>
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

                          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <select
                                value={createTaxTreatment}
                                onChange={(e) => setCreateTaxTreatment(e.target.value as TaxTreatment)}
                                className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100 disabled:text-slate-400"
                                disabled={taxRates.length === 0}
                              >
                                <option value="NONE">No tax</option>
                                <option value="INCLUDED">Tax included</option>
                                <option value="ON_TOP">Tax on top</option>
                              </select>
                              <select
                                value={createTaxRateId}
                                onChange={(e) => setCreateTaxRateId(e.target.value)}
                                disabled={createTaxTreatment === "NONE" || taxRates.length === 0}
                                className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
                              >
                                {taxRates.length === 0 ? (
                                  <option value="">No tax codes</option>
                                ) : (
                                  taxRates.map((tr) => (
                                    <option key={tr.id} value={tr.id}>
                                      {tr.name} ({tr.percentage}%)
                                    </option>
                                  ))
                                )}
                              </select>
                              <span className="text-[11px] text-slate-600">
                                Net {formatMoney(createTaxParts.net)} · Tax {formatMoney(createTaxParts.tax)} · Gross{" "}
                                {formatMoney(createTaxParts.gross)}
                              </span>
                            </div>
                            {taxRates.length === 0 && (
                              <p className="mt-1 text-[11px] text-slate-500">
                                No tax rates configured. Tax selection is disabled.
                              </p>
                            )}
                            {!createAmountMatches && (
                              <p className="mt-1 text-[11px] text-rose-600">
                                Gross must match the bank amount ({formatMoney(Math.abs(selectedTx.amount || 0))}).
                              </p>
                            )}
                          </div>

                          <div className="pt-2">
                            <button
                              type="button"
                              onClick={handleCreateEntry}
                              disabled={!canCreateEntry || actionSubmitting || metadataLoading || !createAmountMatches}
                              className={`inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold text-white shadow-sm ${!canCreateEntry || actionSubmitting || metadataLoading || !createAmountMatches
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
                              const rate = taxRates.find((tr) => String(tr.id) === row.taxRateId)?.percentage || 0;
                              const parts = computeTaxParts(row.amount, row.taxTreatment || "NONE", rate);
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
                                    <select
                                      value={row.taxTreatment || "NONE"}
                                      onChange={(e) =>
                                        updateManualAllocationRow(row.key, {
                                          taxTreatment: e.target.value as TaxTreatment,
                                        })
                                      }
                                      className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100 disabled:text-slate-400"
                                      disabled={taxRates.length === 0}
                                    >
                                      <option value="NONE">No tax</option>
                                      <option value="INCLUDED">Tax included</option>
                                      <option value="ON_TOP">Tax on top</option>
                                    </select>
                                    <select
                                      value={row.taxRateId}
                                      onChange={(e) =>
                                        updateManualAllocationRow(row.key, { taxRateId: e.target.value })
                                      }
                                      disabled={(row.taxTreatment || "NONE") === "NONE" || taxRates.length === 0}
                                      className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
                                    >
                                      {taxRates.length === 0 ? (
                                        <option value="">No tax codes</option>
                                      ) : (
                                        taxRates.map((tr) => (
                                          <option key={tr.id} value={tr.id}>
                                            {tr.name} ({tr.percentage}%)
                                          </option>
                                        ))
                                      )}
                                    </select>
                                    <button
                                      type="button"
                                      onClick={() => removeManualAllocationRow(row.key)}
                                      className="text-[11px] font-medium text-rose-500 hover:text-rose-600"
                                    >
                                      Remove
                                    </button>
                                  </div>
                                  <div className="mt-1 text-[11px] text-slate-600">
                                    Net {formatMoney(parts.net)} · Tax {formatMoney(parts.tax)} · Gross{" "}
                                    {formatMoney(parts.gross)}
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
                              <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
                                <input
                                  className="h-9 min-w-[150px] flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                  placeholder="Account ID"
                                  value={feeAccountId}
                                  onChange={(e) => setFeeAccountId(e.target.value)}
                                />
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  className="h-9 w-32 flex-shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 text-right text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
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
                              <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
                                <input
                                  className="h-9 min-w-[150px] flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                  placeholder="Account ID"
                                  value={roundingAccountId}
                                  onChange={(e) => setRoundingAccountId(e.target.value)}
                                />
                                <input
                                  type="number"
                                  step="0.01"
                                  className="h-9 w-32 flex-shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 text-right text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
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
                                <div className="flex flex-col flex-wrap gap-2 sm:flex-row sm:items-center">
                                  <input
                                    className="h-9 min-w-[180px] flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                    placeholder="Liability account ID"
                                    value={overpaymentAccountId}
                                    onChange={(e) => setOverpaymentAccountId(e.target.value)}
                                  />
                                  <input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    className="h-9 w-32 flex-shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 text-right text-xs outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
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
                                className={`text-sm font-semibold ${Math.abs(allocationSummary.remaining) <= toleranceValue
                                  ? "text-emerald-600"
                                  : "text-rose-600"
                                  }`}
                              >
                                {formatMoney(allocationSummary.remaining)}
                              </p>
                            </div>
                          </div>
                          <p className="mt-2 text-[11px] text-slate-500">
                            {Math.abs(allocationSummary.remaining) <= toleranceValue
                              ? `✓ Within tolerance (±$${toleranceValue.toFixed(2)})`
                              : `⚠️ Remaining amount of ${formatMoney(allocationSummary.remaining)} will be posted automatically as a rounding adjustment (use a rounding account to override the default).`}
                          </p>
                          <div className="pt-3">
                            <button
                              type="button"
                              onClick={handleAllocate}
                              disabled={!allocationSummary.isReady || actionSubmitting}
                              className={`inline-flex w-full items-center justify-center rounded-full px-4 py-2 text-xs font-semibold shadow-sm ${!allocationSummary.isReady || actionSubmitting
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

                    {activeTab === "ADD" && selectedTx && (
                      <div className="space-y-4 max-w-md">
                        <p className="text-xs text-slate-500">
                          Post this bank line directly to a single ledger account with optional tax. No splits required.
                        </p>
                        <div className="space-y-3">
                          <div>
                            <label className="mb-1 block text-xs font-medium text-slate-600">
                              Direction
                            </label>
                            <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1 text-xs font-medium">
                              <button
                                type="button"
                                onClick={() => setAddDirection("IN")}
                                className={`rounded-full px-3 py-1 ${addDirection === "IN" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
                              >
                                Money in
                              </button>
                              <button
                                type="button"
                                onClick={() => setAddDirection("OUT")}
                                className={`rounded-full px-3 py-1 ${addDirection === "OUT" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
                              >
                                Money out
                              </button>
                            </div>
                          </div>

                          <div>
                            <div className="mb-1 flex items-center justify-between">
                              <label className="text-xs font-medium text-slate-600">Category (ledger)</label>
                            </div>
                            <select
                              className="h-9 w-full rounded-2xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                              value={addAccountId}
                              onChange={(e) => setAddAccountId(e.target.value)}
                              disabled={addAccountOptions.length === 0 || actionSubmitting}
                            >
                              {addAccountOptions.map((acc) => (
                                <option key={acc.id} value={acc.id}>
                                  {`${acc.code ? `${acc.code} · ` : ""}${acc.name}`}
                                </option>
                              ))}
                            </select>
                            {addAccountOptions.length === 0 && (
                              <p className="mt-1 text-[11px] text-rose-500">
                                Add {addDirection === "IN" ? "income" : "expense/equity"} accounts to post this entry.
                              </p>
                            )}
                          </div>

                          <div className="grid gap-3 sm:grid-cols-2">
                            <div>
                              <label className="mb-1 block text-xs font-medium text-slate-600">
                                {addDirection === "IN" ? "Customer" : "Supplier"} (optional)
                              </label>
                              <select
                                className="h-9 w-full rounded-2xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                                value={addContactId}
                                onChange={(e) => setAddContactId(e.target.value)}
                                disabled={actionSubmitting || (addDirection === "IN" ? customers.length === 0 : suppliers.length === 0)}
                              >
                                <option value="">
                                  {addDirection === "IN" ? "No customer" : "No supplier"}
                                </option>
                                {(addDirection === "IN" ? customers : suppliers).map((contact) => (
                                  <option key={contact.id} value={contact.id}>
                                    {contact.name}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="mb-1 block text-xs font-medium text-slate-600">
                                Category amount
                              </label>
                              <input
                                className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                                type="number"
                                step="0.01"
                                value={addAmount}
                                onChange={(e) => setAddAmount(e.target.value)}
                                disabled={actionSubmitting}
                              />
                              <p className="mt-1 text-[11px] text-slate-500">
                                Bank amount: {formatMoney(bankAmountAbs)}
                              </p>
                            </div>
                          </div>

                          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                              <span className="text-[11px] font-semibold text-slate-600">Tax</span>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <select
                                value={addTaxTreatment}
                                onChange={(e) => setAddTaxTreatment(e.target.value as TaxTreatment)}
                                className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                              >
                                <option value="NONE">No tax</option>
                                <option value="INCLUDED">Tax included</option>
                                <option value="ON_TOP">Tax on top</option>
                              </select>
                              <select
                                value={addTaxRateId}
                                onChange={(e) => setAddTaxRateId(e.target.value)}
                                disabled={addTaxTreatment === "NONE" || taxRates.length === 0}
                                className="h-9 rounded-full border border-slate-200 bg-white px-3 text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
                              >
                                {taxRates.length === 0 ? (
                                  <option value="">No tax codes</option>
                                ) : (
                                  taxRates.map((tr) => (
                                    <option key={tr.id} value={tr.id}>
                                      {tr.name} ({tr.percentage}%)
                                    </option>
                                  ))
                                )}
                              </select>
                            </div>
                            <p className="mt-2 text-[11px] text-slate-600">
                              Net {formatMoney(addTaxParts.net)} · Tax {formatMoney(addTaxParts.tax)} · Gross{" "}
                              {formatMoney(addTaxParts.gross)}
                            </p>
                            {taxRates.length === 0 && (
                              <p className="mt-1 text-[11px] text-slate-500">
                                No tax rates configured. Tax selection is disabled.
                              </p>
                            )}
                            {!addAmountMatches && (
                              <p className="mt-1 text-[11px] text-rose-600">
                                Gross must match the bank amount ({formatMoney(bankAmountAbs)}). Adjust the base amount or tax.
                              </p>
                            )}
                          </div>

                          <div>
                            <label className="mb-1 block text-xs font-medium text-slate-600">
                              Memo (optional)
                            </label>
                            <input
                              className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                              placeholder="Internal note"
                              value={addMemo}
                              onChange={(e) => setAddMemo(e.target.value)}
                              disabled={actionSubmitting}
                            />
                          </div>

                          <div className="pt-2">
                            <button
                              type="button"
                              onClick={handleAddToLedger}
                              disabled={!canAddEntry}
                              className={`inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold text-white shadow-sm ${!canAddEntry
                                ? "cursor-not-allowed bg-emerald-300"
                                : "bg-emerald-600 hover:bg-emerald-700"
                                }`}
                            >
                              {actionSubmitting ? "Posting…" : "Add to bank account"}
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
                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
                          Tax not applicable for pure transfers.
                        </div>

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
                          className={`inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold ring-1 ${!selectedTx || selectedTx.status !== "NEW" || actionSubmitting
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
      {categoryDrawerOpen && (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/40">
          <div className="flex h-full w-full max-w-lg flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Create category</div>
                <div className="text-sm font-semibold text-slate-900">Add a new category without leaving this review.</div>
              </div>
              <button
                type="button"
                onClick={() => setCategoryDrawerOpen(false)}
                className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-50"
              >
                Close
              </button>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-xs text-slate-700">
              {categoryDrawerError && (
                <div className="rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
                  {categoryDrawerError}
                </div>
              )}
              <div>
                <div className="mb-1 text-[11px] font-medium text-slate-500">Type</div>
                <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1 text-[11px] font-medium">
                  <button
                    type="button"
                    onClick={() => {
                      const opts = expenseAccounts;
                      setCategoryDraft((prev) => ({
                        ...prev,
                        type: "EXPENSE",
                        accountId: opts[0]?.id ? String(opts[0].id) : "",
                      }));
                    }}
                    className={`rounded-full px-3 py-1 ${categoryDraft.type === "EXPENSE" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
                  >
                    Expense
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const opts = incomeAccounts;
                      setCategoryDraft((prev) => ({
                        ...prev,
                        type: "INCOME",
                        accountId: opts[0]?.id ? String(opts[0].id) : "",
                      }));
                    }}
                    className={`rounded-full px-3 py-1 ${categoryDraft.type === "INCOME" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
                  >
                    Income
                  </button>
                </div>
              </div>
              <div>
                <div className="mb-1 text-[11px] font-medium text-slate-500">Name</div>
                <input
                  className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                  placeholder={categoryDraft.type === "EXPENSE" ? "e.g. Subscriptions" : "e.g. Sales"}
                  value={categoryDraft.name}
                  onChange={(e) => setCategoryDraft((prev) => ({ ...prev, name: e.target.value }))}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Code</div>
                  <input
                    className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                    placeholder="Optional"
                    value={categoryDraft.code}
                    onChange={(e) => setCategoryDraft((prev) => ({ ...prev, code: e.target.value }))}
                  />
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Account (optional)</div>
                  <select
                    className="h-9 w-full rounded-2xl border border-slate-200 bg-white px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                    value={categoryDraft.accountId}
                    onChange={(e) => setCategoryDraft((prev) => ({ ...prev, accountId: e.target.value }))}
                  >
                    <option value="">No linked account</option>
                    {(categoryDraft.type === "EXPENSE" ? expenseAccounts : incomeAccounts).map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {`${acc.code ? `${acc.code} · ` : ""}${acc.name}`}
                      </option>
                    ))}
                  </select>
                  {(categoryDraft.type === "EXPENSE" ? expenseAccounts : incomeAccounts).length === 0 && (
                    <p className="mt-1 text-[10px] text-slate-400">
                      Add {categoryDraft.type === "EXPENSE" ? "expense" : "income"} accounts in your COA to link this category.
                    </p>
                  )}
                </div>
              </div>
              <div>
                <div className="mb-1 text-[11px] font-medium text-slate-500">Description</div>
                <textarea
                  className="min-h-[70px] w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                  placeholder="What does this category cover?"
                  value={categoryDraft.description}
                  onChange={(e) => setCategoryDraft((prev) => ({ ...prev, description: e.target.value }))}
                />
              </div>
            </div>
            <div className="border-t border-slate-100 px-5 py-3 text-right">
              <button
                type="button"
                onClick={() => setCategoryDrawerOpen(false)}
                className="mr-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveCategory}
                disabled={categoryDrawerSaving}
                className={`inline-flex items-center rounded-full px-4 py-1.5 text-[11px] font-semibold text-white shadow-sm ${categoryDrawerSaving ? "cursor-not-allowed bg-slate-400" : "bg-emerald-600 hover:bg-emerald-700"}`}
              >
                {categoryDrawerSaving ? "Saving…" : "Save category"}
              </button>
            </div>
          </div>
        </div>
      )}
      {txDrawerOpen && (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/40">
          <div className="flex h-full w-full max-w-md flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">New transaction</div>
                <div className="text-sm font-semibold text-slate-900">Post a manual bank line for review</div>
              </div>
              <button
                type="button"
                onClick={() => setTxDrawerOpen(false)}
                className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-50"
              >
                Close
              </button>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-xs text-slate-700">
              {txDrawerError && (
                <div className="rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
                  {txDrawerError}
                </div>
              )}
              {!account?.ledgerAccountId && (
                <div className="rounded-2xl border border-amber-100 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                  Link this bank account to a ledger account before creating manual transactions.
                </div>
              )}
              <div>
                <div className="mb-1 text-[11px] font-medium text-slate-500">Type</div>
                <div className="inline-flex gap-1 rounded-full bg-slate-50 p-1">
                  <button
                    type="button"
                    onClick={() => setTxSide("IN")}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium ${txSide === "IN" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
                  >
                    Money in
                  </button>
                  <button
                    type="button"
                    onClick={() => setTxSide("OUT")}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium ${txSide === "OUT" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}
                  >
                    Money out
                  </button>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Date</div>
                  <input
                    type="date"
                    className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                    value={txDate}
                    onChange={(e) => setTxDate(e.target.value)}
                  />
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-medium text-slate-500">Amount</div>
                  <div className="flex items-center gap-1">
                    <span className="rounded-2xl bg-slate-50 px-2 py-1 text-[11px] text-slate-500">{accountCurrency}</span>
                    <input
                      type="number"
                      className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                      placeholder="0.00"
                      value={txAmount}
                      onChange={(e) => setTxAmount(e.target.value)}
                    />
                  </div>
                </div>
              </div>
              <div>
                <div className="mb-1 text-[11px] font-medium text-slate-500">Description</div>
                <input
                  className="h-9 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                  placeholder="What is this transaction for?"
                  value={txDescription}
                  onChange={(e) => setTxDescription(e.target.value)}
                />
              </div>
              <div>
                <div className="mb-1 text-[11px] font-medium text-slate-500">Memo (optional)</div>
                <textarea
                  className="min-h-[70px] w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none focus:border-sky-400 focus:bg-white focus:ring-2 focus:ring-sky-100"
                  placeholder="Internal note"
                  value={txMemo}
                  onChange={(e) => setTxMemo(e.target.value)}
                />
              </div>
            </div>
            <div className="border-t border-slate-100 px-5 py-3 text-right">
              <button
                type="button"
                onClick={() => setTxDrawerOpen(false)}
                className="mr-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreateManualTx}
                disabled={txDrawerSaving || !account?.ledgerAccountId}
                className={`inline-flex items-center rounded-full px-4 py-1.5 text-[11px] font-semibold text-white shadow-sm ${txDrawerSaving || !account?.ledgerAccountId ? "cursor-not-allowed bg-slate-400" : "bg-slate-900 hover:bg-black"}`}
              >
                {txDrawerSaving ? "Saving…" : "Save transaction"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
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
