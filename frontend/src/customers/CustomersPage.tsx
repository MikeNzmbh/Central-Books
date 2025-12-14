import React, { useMemo, useState, useEffect } from "react";
import CompanionStrip from "../companion/CompanionStrip";
import {
  Users,
  Plus,
  Search,
  Filter,
  CreditCard,
  Mail,
  Phone,
  Building2,
  ChevronRight,
  AlertTriangle,
  Sparkles,
  ChevronDown,
  CalendarDays,
  FileText,
} from "lucide-react";

// -----------------------------------------------------------------------------
// Customers Page – Apple-style Light UI with Companion Strip + Glow
// -----------------------------------------------------------------------------

export type CustomerAgingBucket = "current" | "30" | "60" | "90";

export type Customer = {
  id: number;
  name: string;
  company?: string;
  email?: string;
  phone?: string;
  status: "active" | "overdue" | "inactive";
  open_balance: string;
  ytd_revenue: string;
  mtd_revenue: string;
  currency: string;
  agingBucket: CustomerAgingBucket;
  last_invoice_date?: string;
  location?: string;
  tags?: string[];
  riskLevel?: "low" | "medium" | "high";
  is_active: boolean;
};

interface Stats {
  total_customers: number;
  total_ytd: string;
  total_mtd: string;
  total_open_balance: string;
}

interface CustomerData {
  customers: Customer[];
  stats: Stats;
  currency: string;
}

type ReversalsSummary = {
  open_ar: string;
  open_credits: string;
  deposit_balance: string;
  currency: string;
};

type CreditMemo = {
  id: number;
  credit_memo_number: string;
  posting_date: string | null;
  status: "DRAFT" | "POSTED" | "VOIDED";
  memo: string;
  net_total: string;
  tax_total: string;
  grand_total: string;
  available_amount: string;
  refunded_total: string;
  source_invoice_id: number | null;
  source_invoice_number: string | null;
  linked_invoices: Array<{ invoice_id: number; invoice_number: string; amount: string }>;
};

type CustomerDeposit = {
  id: number;
  posting_date: string | null;
  status: "DRAFT" | "POSTED" | "VOIDED";
  memo: string;
  amount: string;
  currency: string;
  available_amount: string;
  refunded_total: string;
  bank_account_id: number;
  bank_account_name: string;
  linked_invoices: Array<{ invoice_id: number; invoice_number: string; amount: string }>;
};

type CustomerRefund = {
  id: number;
  posting_date: string | null;
  status: "DRAFT" | "POSTED" | "VOIDED";
  memo: string;
  amount: string;
  currency: string;
  bank_account_id: number;
  bank_account_name: string;
  credit_memo_id: number | null;
  deposit_id: number | null;
};

type BankOverviewAccount = {
  id: number;
  name: string;
};

function formatCurrency(amount: number | string, currency = "CAD"): string {
  const num = typeof amount === "string" ? parseFloat(amount) || 0 : amount;
  try {
    return new Intl.NumberFormat("en-CA", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(num);
  } catch {
    return `${currency} ${num.toFixed(2)}`;
  }
}

function agingLabel(bucket: CustomerAgingBucket): string {
  switch (bucket) {
    case "current": return "Current";
    case "30": return "30 days";
    case "60": return "60 days";
    case "90": return "90+ days";
    default: return "";
  }
}

function agingBadgeClass(bucket: CustomerAgingBucket): string {
  switch (bucket) {
    case "current": return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
    case "30": return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
    case "60": return "bg-orange-50 text-orange-700 ring-1 ring-orange-200";
    case "90": return "bg-red-50 text-red-700 ring-1 ring-red-200";
    default: return "bg-slate-50 text-slate-600 ring-1 ring-slate-200";
  }
}

function statusBadgeClass(status: Customer["status"]): string {
  switch (status) {
    case "active": return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "overdue": return "bg-amber-50 text-amber-800 border border-amber-200";
    case "inactive": return "bg-slate-100 text-slate-500 border border-slate-200";
    default: return "bg-slate-50 text-slate-700 border border-slate-200";
  }
}

function riskChipClass(risk?: "low" | "medium" | "high"): string {
  switch (risk) {
    case "low": return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
    case "medium": return "bg-amber-50 text-amber-800 ring-1 ring-amber-200";
    case "high": return "bg-rose-50 text-rose-700 ring-1 ring-rose-200";
    default: return "bg-slate-50 text-slate-600 ring-1 ring-slate-200";
  }
}

const FILTER_TABS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "overdue", label: "Overdue" },
  { id: "inactive", label: "Inactive" },
] as const;

type FilterTabId = (typeof FILTER_TABS)[number]["id"];

// Derive aging bucket from open balance (mock logic)
function deriveAgingBucket(balance: string): CustomerAgingBucket {
  const num = parseFloat(balance) || 0;
  if (num <= 0) return "current";
  if (num < 1000) return "current";
  if (num < 5000) return "30";
  if (num < 10000) return "60";
  return "90";
}

// Derive status from balance
function deriveStatus(balance: string, isActive: boolean): Customer["status"] {
  if (!isActive) return "inactive";
  const num = parseFloat(balance) || 0;
  if (num > 5000) return "overdue";
  return "active";
}

// -----------------------------------------------------------------------------
// Main Customers Page
// -----------------------------------------------------------------------------

const CustomersPage: React.FC = () => {
  const [data, setData] = useState<CustomerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [filterTab, setFilterTab] = useState<FilterTabId>("all");

  // Tab state
  const [activeTab, setActiveTab] = useState<'overview' | 'invoices' | 'credits' | 'activity' | 'notes'>('overview');

  // Payment modal state
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [paymentMethod, setPaymentMethod] = useState('EFT');
  const [paymentReference, setPaymentReference] = useState('');
  const [paymentNotes, setPaymentNotes] = useState('');
  const [paymentTaxRateId, setPaymentTaxRateId] = useState<string>('');
  const [paymentTaxAmount, setPaymentTaxAmount] = useState<number>(0);

  // Notes state
  const [noteText, setNoteText] = useState('');
  const [customerNotes, setCustomerNotes] = useState<Array<{ id: number; text: string; created_at: string }>>([]);

  // Live data state
  const [customerInvoices, setCustomerInvoices] = useState<any[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [taxRates, setTaxRates] = useState<Array<{ id: number; name: string; code: string; percentage: string }>>([]);

  // Reversals state (credits / deposits / refunds)
  const [reversalsSummary, setReversalsSummary] = useState<ReversalsSummary | null>(null);
  const [creditMemos, setCreditMemos] = useState<CreditMemo[]>([]);
  const [deposits, setDeposits] = useState<CustomerDeposit[]>([]);
  const [refunds, setRefunds] = useState<CustomerRefund[]>([]);
  const [loadingReversals, setLoadingReversals] = useState(false);

  // Bank accounts (for deposits/refunds)
  const [bankAccounts, setBankAccounts] = useState<BankOverviewAccount[]>([]);

  // Credit memo modal
  const [creditMemoModalOpen, setCreditMemoModalOpen] = useState(false);
  const [creditMemoSourceInvoiceId, setCreditMemoSourceInvoiceId] = useState<string>("");
  const [creditMemoNetTotal, setCreditMemoNetTotal] = useState("");
  const [creditMemoPostingDate, setCreditMemoPostingDate] = useState(new Date().toISOString().split("T")[0]);
  const [creditMemoMemo, setCreditMemoMemo] = useState("");

  // Apply credit memo modal
  const [applyCreditModalOpen, setApplyCreditModalOpen] = useState(false);
  const [applyCreditMemoId, setApplyCreditMemoId] = useState<number | null>(null);
  const [applyCreditInvoiceId, setApplyCreditInvoiceId] = useState<string>("");
  const [applyCreditAmount, setApplyCreditAmount] = useState("");

  // Deposit modal
  const [depositModalOpen, setDepositModalOpen] = useState(false);
  const [depositBankAccountId, setDepositBankAccountId] = useState<string>("");
  const [depositAmount, setDepositAmount] = useState("");
  const [depositPostingDate, setDepositPostingDate] = useState(new Date().toISOString().split("T")[0]);
  const [depositMemo, setDepositMemo] = useState("");

  // Apply deposit modal
  const [applyDepositModalOpen, setApplyDepositModalOpen] = useState(false);
  const [applyDepositId, setApplyDepositId] = useState<number | null>(null);
  const [applyDepositInvoiceId, setApplyDepositInvoiceId] = useState<string>("");
  const [applyDepositAmount, setApplyDepositAmount] = useState("");

  // Refund modal
  const [refundModalOpen, setRefundModalOpen] = useState(false);
  const [refundBankAccountId, setRefundBankAccountId] = useState<string>("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundPostingDate, setRefundPostingDate] = useState(new Date().toISOString().split("T")[0]);
  const [refundMemo, setRefundMemo] = useState("");
  const [refundSourceType, setRefundSourceType] = useState<"credit_memo" | "deposit" | "none">("credit_memo");
  const [refundSourceId, setRefundSourceId] = useState<string>("");

  // Fetch customers from API
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch("/api/customers/list/");
        if (!response.ok) throw new Error("Failed to fetch customers");
        const json = await response.json();
        setData(json);
        // Select first customer by default
        if (json.customers?.length > 0 && !selectedId) {
          setSelectedId(json.customers[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Fetch tax rates on mount
  useEffect(() => {
    fetch("/api/taxes/rates/?active=1")
      .then(res => res.json())
      .then(json => setTaxRates(json.tax_rates || []))
      .catch(() => { });
  }, []);

  // Fetch bank accounts for deposit/refund pickers
  useEffect(() => {
    fetch("/api/banking/overview/")
      .then((res) => res.json())
      .then((json) => {
        const accounts = (json?.accounts || []) as Array<{ id: number; name: string }>;
        setBankAccounts(accounts.map((a) => ({ id: a.id, name: a.name })));
        if (!depositBankAccountId && accounts.length) setDepositBankAccountId(String(accounts[0].id));
        if (!refundBankAccountId && accounts.length) setRefundBankAccountId(String(accounts[0].id));
      })
      .catch(() => { });
  }, []);

  const refreshReversals = async (customerId: number) => {
    setLoadingReversals(true);
    try {
      const [summaryRes, memosRes, depositsRes, refundsRes] = await Promise.all([
        fetch(`/api/reversals/customers/${customerId}/summary/`),
        fetch(`/api/reversals/customers/${customerId}/credit-memos/`),
        fetch(`/api/reversals/customers/${customerId}/deposits/`),
        fetch(`/api/reversals/customers/${customerId}/refunds/`),
      ]);
      const summaryJson = summaryRes.ok ? await summaryRes.json() : null;
      const memosJson = memosRes.ok ? await memosRes.json() : null;
      const depositsJson = depositsRes.ok ? await depositsRes.json() : null;
      const refundsJson = refundsRes.ok ? await refundsRes.json() : null;

      setReversalsSummary(summaryJson);
      setCreditMemos((memosJson?.credit_memos || []) as CreditMemo[]);
      setDeposits((depositsJson?.deposits || []) as CustomerDeposit[]);
      setRefunds((refundsJson?.refunds || []) as CustomerRefund[]);
    } catch {
      // Keep UI resilient; surface nothing for now.
    } finally {
      setLoadingReversals(false);
    }
  };

  // Fetch invoices when customer changes
  useEffect(() => {
    if (!selectedId) return;
    setCreditMemoSourceInvoiceId("");
    setApplyCreditInvoiceId("");
    setApplyDepositInvoiceId("");
    setRefundSourceId("");
    setLoadingInvoices(true);
    fetch(`/api/invoices/list/?customer=${selectedId}`)
      .then(res => res.json())
      .then(json => {
        const invs = json.invoices || [];
        setCustomerInvoices(invs);
        if (invs.length) {
          setCreditMemoSourceInvoiceId(String(invs[0].id));
          setApplyCreditInvoiceId(String(invs[0].id));
          setApplyDepositInvoiceId(String(invs[0].id));
        }
      })
      .catch(() => setCustomerInvoices([]))
      .finally(() => setLoadingInvoices(false));
  }, [selectedId]);

  // Fetch reversals when customer changes
  useEffect(() => {
    if (!selectedId) return;
    refreshReversals(selectedId);
  }, [selectedId]);

  // Transform API customers to include derived fields
  const customers: Customer[] = useMemo(() => {
    if (!data?.customers) return [];
    return data.customers.map((c: any) => ({
      ...c,
      status: deriveStatus(c.open_balance, c.is_active !== false),
      agingBucket: deriveAgingBucket(c.open_balance),
      currency: data.currency || "CAD",
      riskLevel: parseFloat(c.open_balance) > 10000 ? "high" : parseFloat(c.open_balance) > 5000 ? "medium" : "low",
    }));
  }, [data]);

  const filteredCustomers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return customers.filter((c) => {
      if (filterTab !== "all" && c.status !== filterTab) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        (c.email && c.email.toLowerCase().includes(q)) ||
        (c.phone && c.phone.toLowerCase().includes(q))
      );
    });
  }, [customers, search, filterTab]);

  const selectedCustomer = useMemo(
    () => customers.find((c) => c.id === selectedId) ?? filteredCustomers[0] ?? null,
    [customers, selectedId, filteredCustomers]
  );

  const summary = useMemo(() => {
    const totalOpen = customers.reduce((sum, c) => sum + (parseFloat(c.open_balance) || 0), 0);
    const overdueCount = customers.filter((c) => c.status === "overdue").length;
    const inactiveCount = customers.filter((c) => c.status === "inactive").length;
    return { totalOpen, overdueCount, inactiveCount, total: customers.length };
  }, [customers]);

  const currency = data?.currency || "CAD";

  // Handler functions
  const handleRecordPayment = () => {
    if (!selectedCustomer) return;
    setPaymentAmount(selectedCustomer.open_balance);
    setPaymentTaxRateId('');
    setPaymentTaxAmount(0);
    setPaymentModalOpen(true);
  };

  // Calculate tax based on selected rate and amount
  const calculateTax = (amount: string, taxRateId: string) => {
    if (!taxRateId || !amount.trim()) {
      setPaymentTaxAmount(0);
      return;
    }
    const selectedRate = taxRates.find(r => String(r.id) === taxRateId);
    if (selectedRate) {
      const numAmount = parseFloat(amount) || 0;
      const percentage = parseFloat(selectedRate.percentage) || 0;
      const tax = numAmount * (percentage / 100);
      setPaymentTaxAmount(Math.round(tax * 100) / 100);
    }
  };

  const handleAmountChange = (value: string) => {
    setPaymentAmount(value);
    calculateTax(value, paymentTaxRateId);
  };

  const handleTaxRateChange = (rateId: string) => {
    setPaymentTaxRateId(rateId);
    calculateTax(paymentAmount, rateId);
  };

  const handleSavePayment = async () => {
    if (!selectedCustomer || !paymentAmount.trim()) {
      alert("Please enter a payment amount");
      return;
    }

    const totalWithTax = (parseFloat(paymentAmount) || 0) + paymentTaxAmount;

    // TODO: Wire to actual API endpoint POST /api/payments/
    console.log("Recording payment:", {
      customer_id: selectedCustomer.id,
      amount: paymentAmount,
      tax_rate_id: paymentTaxRateId || null,
      tax_amount: paymentTaxAmount,
      total: totalWithTax,
      payment_date: paymentDate,
      method: paymentMethod,
      reference: paymentReference,
      notes: paymentNotes,
    });

    alert(`Payment of ${formatCurrency(totalWithTax, currency)} (incl. tax) recorded for ${selectedCustomer.name}`);
    setPaymentModalOpen(false);

    // Reset form
    setPaymentAmount('');
    setPaymentReference('');
    setPaymentNotes('');
    setPaymentTaxRateId('');
    setPaymentTaxAmount(0);
  };

  const handleAddNote = () => {
    if (!selectedCustomer || !noteText.trim()) return;

    const newNote = {
      id: Date.now(),
      text: noteText,
      created_at: new Date().toISOString(),
    };

    setCustomerNotes([newNote, ...customerNotes]);
    setNoteText('');

    // TODO: POST to /api/customers/{id}/notes/
    console.log("Adding note:", newNote);
  };

  const handleOpenCreditMemoModal = () => {
    if (!selectedCustomer) return;
    setCreditMemoNetTotal("");
    setCreditMemoMemo("");
    setCreditMemoPostingDate(new Date().toISOString().split("T")[0]);
    setCreditMemoModalOpen(true);
  };

  const handleCreateAndPostCreditMemo = async () => {
    if (!selectedCustomer) return;
    if (!creditMemoNetTotal.trim()) {
      alert("Enter a credit memo amount");
      return;
    }

    const payload: any = {
      customer_id: selectedCustomer.id,
      net_total: creditMemoNetTotal,
      posting_date: creditMemoPostingDate,
      memo: creditMemoMemo,
    };
    if (creditMemoSourceInvoiceId) payload.source_invoice_id = Number(creditMemoSourceInvoiceId);

    const createRes = await fetch("/api/reversals/customer-credit-memos/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const createJson = await createRes.json();
    if (!createRes.ok) {
      alert(createJson?.error || "Failed to create credit memo");
      return;
    }

    const creditMemoId = createJson?.credit_memo?.id;
    if (!creditMemoId) {
      alert("Credit memo created but response was missing an id");
      return;
    }

    const postRes = await fetch(`/api/reversals/customer-credit-memos/${creditMemoId}/post/`, { method: "POST" });
    const postJson = await postRes.json();
    if (!postRes.ok) {
      alert(postJson?.error || "Failed to post credit memo");
      return;
    }

    setCreditMemoModalOpen(false);
    await refreshReversals(selectedCustomer.id);
  };

  const handleOpenApplyCreditModal = (memo: CreditMemo) => {
    setApplyCreditMemoId(memo.id);
    setApplyCreditAmount(memo.available_amount);
    if (memo.source_invoice_id) setApplyCreditInvoiceId(String(memo.source_invoice_id));
    setApplyCreditModalOpen(true);
  };

  const handleApplyCreditMemo = async () => {
    if (!selectedCustomer || !applyCreditMemoId) return;
    if (!applyCreditInvoiceId || !applyCreditAmount.trim()) {
      alert("Select an invoice and amount");
      return;
    }
    const res = await fetch(`/api/reversals/customer-credit-memos/${applyCreditMemoId}/allocate/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        allocations: [{ invoice_id: Number(applyCreditInvoiceId), amount: applyCreditAmount }],
      }),
    });
    const json = await res.json();
    if (!res.ok) {
      alert(json?.error || "Failed to apply credit memo");
      return;
    }
    setApplyCreditModalOpen(false);
    await refreshReversals(selectedCustomer.id);
  };

  const handleOpenDepositModal = () => {
    if (!selectedCustomer) return;
    setDepositAmount("");
    setDepositMemo("");
    setDepositPostingDate(new Date().toISOString().split("T")[0]);
    setDepositModalOpen(true);
  };

  const handleCreateDeposit = async () => {
    if (!selectedCustomer) return;
    if (!depositBankAccountId) {
      alert("Select a bank account");
      return;
    }
    if (!depositAmount.trim()) {
      alert("Enter a deposit amount");
      return;
    }
    const res = await fetch("/api/reversals/customer-deposits/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_id: selectedCustomer.id,
        bank_account_id: Number(depositBankAccountId),
        amount: depositAmount,
        currency,
        posting_date: depositPostingDate,
        memo: depositMemo,
      }),
    });
    const json = await res.json();
    if (!res.ok) {
      alert(json?.error || "Failed to record deposit");
      return;
    }
    setDepositModalOpen(false);
    await refreshReversals(selectedCustomer.id);
  };

  const handleOpenApplyDepositModal = (deposit: CustomerDeposit) => {
    setApplyDepositId(deposit.id);
    setApplyDepositAmount(deposit.available_amount);
    setApplyDepositModalOpen(true);
  };

  const handleApplyDeposit = async () => {
    if (!selectedCustomer || !applyDepositId) return;
    if (!applyDepositInvoiceId || !applyDepositAmount.trim()) {
      alert("Select an invoice and amount");
      return;
    }
    const res = await fetch(`/api/reversals/customer-deposits/${applyDepositId}/apply/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        allocations: [{ invoice_id: Number(applyDepositInvoiceId), amount: applyDepositAmount }],
      }),
    });
    const json = await res.json();
    if (!res.ok) {
      alert(json?.error || "Failed to apply deposit");
      return;
    }
    setApplyDepositModalOpen(false);
    await refreshReversals(selectedCustomer.id);
  };

  const handleOpenRefundModal = () => {
    if (!selectedCustomer) return;
    setRefundAmount("");
    setRefundMemo("");
    setRefundPostingDate(new Date().toISOString().split("T")[0]);
    setRefundModalOpen(true);
  };

  const handleCreateRefund = async () => {
    if (!selectedCustomer) return;
    if (!refundBankAccountId) {
      alert("Select a bank account");
      return;
    }
    if (!refundAmount.trim()) {
      alert("Enter a refund amount");
      return;
    }

    const payload: any = {
      customer_id: selectedCustomer.id,
      bank_account_id: Number(refundBankAccountId),
      amount: refundAmount,
      currency,
      posting_date: refundPostingDate,
      memo: refundMemo,
    };
    if (refundSourceType === "credit_memo" && refundSourceId) payload.credit_memo_id = Number(refundSourceId);
    if (refundSourceType === "deposit" && refundSourceId) payload.deposit_id = Number(refundSourceId);

    const res = await fetch("/api/reversals/customer-refunds/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (!res.ok) {
      alert(json?.error || "Failed to record refund");
      return;
    }
    setRefundModalOpen(false);
    await refreshReversals(selectedCustomer.id);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-emerald-500 border-t-transparent mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading customers...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-8">
        <div className="p-4 text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/80 px-4 py-6 sm:px-6 lg:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-5">

        {/* Page header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200 shadow-sm">
              <Users className="h-3.5 w-3.5 text-emerald-500" />
              <span>Customers &amp; Receivables</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
              Customers
            </h1>
            <p className="max-w-xl text-sm text-slate-500">
              A clean, Apple-grade home for your customers, invoices, and receivables. Designed
              to work hand-in-hand with Companion and Tax Guardian.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-medium shadow-sm hover:bg-slate-50 transition-colors">
              <Filter className="h-4 w-4" />
              Saved views
            </button>
            <a
              href="/customers/new/"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 text-white text-sm font-medium shadow-lg shadow-emerald-500/25 hover:bg-emerald-600 transition-colors"
            >
              <Plus className="h-4 w-4" />
              New customer
            </a>
          </div>
        </header>

        {/* Shared Companion Strip with glow */}
        <div className="mb-2">
          <CompanionStrip context="invoices" />
        </div>

        {/* Main content: list + detail */}
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)]">

          {/* Left: Customers list */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="px-4 py-4 border-b border-slate-100">
              <div className="flex items-center justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Customer directory</h3>
                  <p className="text-xs text-slate-500">Search, filter, and select a customer.</p>
                </div>
                <button className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-600 hover:bg-slate-100 transition-colors">
                  <CalendarDays className="h-3.5 w-3.5" />
                  Aging view
                </button>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search by name, company, or email"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full h-9 border border-slate-200 bg-slate-50 rounded-lg pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  />
                </div>
                <button className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-600 hover:bg-slate-100 transition-colors">
                  <Filter className="h-3.5 w-3.5" />
                  Filters
                </button>
              </div>

              <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1 text-xs">
                {FILTER_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setFilterTab(tab.id)}
                    className={`inline-flex items-center rounded-full px-3 py-1 transition-all ${filterTab === tab.id
                      ? "bg-slate-900 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-[420px] overflow-y-auto">
              <div className="divide-y divide-slate-100">
                {filteredCustomers.length === 0 && (
                  <div className="flex flex-col items-center justify-center gap-2 px-5 py-10 text-center text-xs text-slate-400">
                    <p>No customers match your filters.</p>
                    <a href="/customers/new/" className="text-emerald-600 hover:underline">Create a new customer</a>
                  </div>
                )}

                {filteredCustomers.map((customer) => {
                  const isSelected = selectedCustomer?.id === customer.id;
                  return (
                    <button
                      key={customer.id}
                      onClick={() => setSelectedId(customer.id)}
                      className={`flex w-full items-stretch gap-3 px-4 py-3 text-left text-xs transition-all ${isSelected
                        ? "bg-emerald-50/50 border-l-2 border-l-emerald-500"
                        : "hover:bg-slate-50"
                        }`}
                    >
                      <div className="flex flex-1 flex-col gap-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-[13px] font-medium text-slate-900">
                            {customer.name}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          {customer.email && (
                            <span className="inline-flex items-center gap-1">
                              <Mail className="h-3 w-3" />
                              <span className="truncate max-w-[150px]">{customer.email}</span>
                            </span>
                          )}
                          {customer.phone && (
                            <span className="inline-flex items-center gap-1">
                              <Phone className="h-3 w-3" />
                              <span>{customer.phone}</span>
                            </span>
                          )}
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] ${statusBadgeClass(customer.status)}`}>
                            <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${customer.status === "active" ? "bg-emerald-500" :
                              customer.status === "overdue" ? "bg-amber-500" : "bg-slate-400"
                              }`} />
                            {customer.status === "active" ? "Active" : customer.status === "overdue" ? "Overdue" : "Inactive"}
                          </span>
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] ${agingBadgeClass(customer.agingBucket)}`}>
                            {agingLabel(customer.agingBucket)}
                          </span>
                          {customer.riskLevel && customer.riskLevel !== "low" && (
                            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${riskChipClass(customer.riskLevel)}`}>
                              <AlertTriangle className="h-3 w-3" />
                              {customer.riskLevel === "medium" ? "Medium risk" : "High risk"}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col items-end justify-between gap-1 text-right text-[11px]">
                        <div className="text-[12px] font-semibold text-slate-900">
                          {formatCurrency(customer.open_balance, customer.currency)}
                        </div>
                        {customer.last_invoice_date && (
                          <div className="flex items-center gap-1 text-[11px] text-slate-400">
                            <CalendarDays className="h-3 w-3" />
                            <span>Last {customer.last_invoice_date}</span>
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right: Customer details */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="px-4 py-4 border-b border-slate-100">
              {selectedCustomer ? (
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-sm font-semibold text-white shadow-sm">
                        {selectedCustomer.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900 sm:text-base">
                          {selectedCustomer.name}
                        </h3>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          {selectedCustomer.email && (
                            <span className="inline-flex items-center gap-1">
                              <Mail className="h-3 w-3" />
                              {selectedCustomer.email}
                            </span>
                          )}
                          {selectedCustomer.phone && (
                            <span className="inline-flex items-center gap-1">
                              <Phone className="h-3 w-3" />
                              {selectedCustomer.phone}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 ${statusBadgeClass(selectedCustomer.status)}`}>
                        <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${selectedCustomer.status === "active" ? "bg-emerald-500" :
                          selectedCustomer.status === "overdue" ? "bg-amber-500" : "bg-slate-400"
                          }`} />
                        {selectedCustomer.status === "active" ? "Active" : selectedCustomer.status === "overdue" ? "Overdue" : "Inactive"}
                      </span>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 ${agingBadgeClass(selectedCustomer.agingBucket)}`}>
                        {agingLabel(selectedCustomer.agingBucket)}
                      </span>
                      {selectedCustomer.riskLevel && (
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${riskChipClass(selectedCustomer.riskLevel)}`}>
                          <AlertTriangle className="h-3 w-3" />
                          {selectedCustomer.riskLevel === "low" ? "Low risk" : selectedCustomer.riskLevel === "medium" ? "Medium risk" : "High risk"}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    <div className="text-right text-xs text-slate-500">Open balance</div>
                    <div className="text-lg font-semibold tracking-tight text-slate-900">
                      {formatCurrency(selectedCustomer.open_balance, selectedCustomer.currency)}
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        onClick={handleRecordPayment}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-700 hover:bg-slate-100 transition-colors"
                      >
                        <CreditCard className="h-3.5 w-3.5" />
                        Record payment
                      </button>
                      <a
                        href={`/invoices/new/?customer=${selectedCustomer.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        Create invoice
                      </a>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-slate-400">
                  Select a customer to see details.
                </div>
              )}
            </div>

            {/* Tabs content */}
            {selectedCustomer && (
              <div className="p-4">
                <div className="mb-4 flex gap-1 rounded-2xl bg-slate-100 p-1 text-xs">
                  <button
                    onClick={() => setActiveTab('overview')}
                    className={`flex-1 rounded-xl px-3 py-2 font-medium transition-all ${activeTab === 'overview'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    Overview
                  </button>
                  <button
                    onClick={() => setActiveTab('invoices')}
                    className={`flex-1 rounded-xl px-3 py-2 font-medium transition-all ${activeTab === 'invoices'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    Invoices
                  </button>
                  <button
                    onClick={() => setActiveTab('credits')}
                    className={`flex-1 rounded-xl px-3 py-2 font-medium transition-all ${activeTab === 'credits'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    Credits
                  </button>
                  <button
                    onClick={() => setActiveTab('activity')}
                    className={`flex-1 rounded-xl px-3 py-2 font-medium transition-all ${activeTab === 'activity'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    Activity
                  </button>
                  <button
                    onClick={() => setActiveTab('notes')}
                    className={`flex-1 rounded-xl px-3 py-2 font-medium transition-all ${activeTab === 'notes'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    Notes
                  </button>
                </div>

                {/* Tab Content: OVERVIEW */}
                {activeTab === 'overview' && (
                  <>
                    {/* Metrics row */}
                    <div className="grid gap-3 md:grid-cols-3 mb-4">
                      <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Open balance</span>
                          <ChevronRight className="h-3 w-3" />
                        </div>
                        <div className="mt-1 text-sm font-semibold text-slate-900">
                          {formatCurrency(selectedCustomer.open_balance, selectedCustomer.currency)}
                        </div>
                        <p className="mt-0.5 text-[11px] text-slate-400">All unpaid invoices.</p>
                      </div>
                      <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Aging bucket</span>
                          <CalendarDays className="h-3 w-3" />
                        </div>
                        <div className="mt-1 inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                          <span>{agingLabel(selectedCustomer.agingBucket)}</span>
                          <span className={`rounded-full px-2 py-0.5 text-[11px] ${agingBadgeClass(selectedCustomer.agingBucket)}`}>
                            {selectedCustomer.agingBucket === "current" ? "On time" : "Late"}
                          </span>
                        </div>
                        <p className="mt-0.5 text-[11px] text-slate-400">Prioritize collections.</p>
                      </div>
                      <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Risk level</span>
                          <Sparkles className="h-3 w-3 text-emerald-500" />
                        </div>
                        <div className="mt-1 text-sm font-semibold text-slate-900">
                          {selectedCustomer.riskLevel === "low" ? "Low risk" : selectedCustomer.riskLevel === "medium" ? "Medium risk" : "High risk"}
                        </div>
                        <p className="mt-0.5 text-[11px] text-slate-400">Based on payment patterns.</p>
                      </div>
                    </div>

                    {/* Quick actions */}
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                        <div className="mb-2 flex items-center justify-between text-[11px] text-slate-500">
                          <span>Quick actions</span>
                          <ChevronDown className="h-3 w-3" />
                        </div>
                        <div className="grid gap-2 sm:grid-cols-3">
                          <a href={`/invoices/new/?customer=${selectedCustomer.id}`} className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-700 hover:bg-slate-100 transition-colors">
                            <FileText className="h-3.5 w-3.5" />
                            New invoice
                          </a>
                          <button
                            onClick={handleRecordPayment}
                            className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-700 hover:bg-slate-100 transition-colors"
                          >
                            <CreditCard className="h-3.5 w-3.5" />
                            Record payment
                          </button>
                          <a
                            href={`/coa/customer-${selectedCustomer.id}`}
                            className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-700 hover:bg-slate-100 transition-colors"
                          >
                            <Building2 className="h-3.5 w-3.5" />
                            View ledger
                          </a>
                        </div>
                      </div>

                      <div className="rounded-2xl bg-emerald-50/50 p-3 ring-1 ring-emerald-200">
                        <div className="mb-2 flex items-center justify-between text-[11px] text-emerald-700">
                          <span>Companion notes</span>
                          <Sparkles className="h-3 w-3" />
                        </div>
                        <p className="rounded-xl bg-white px-3 py-2 text-[11px] text-slate-600 ring-1 ring-emerald-100">
                          "{selectedCustomer.name} typically pays within 7 days. Consider a follow-up if balance exceeds 30 days."
                        </p>
                      </div>
                    </div>
                  </>
                )}

                {/* Tab Content: INVOICES */}
                {activeTab === 'invoices' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-900">
                        Customer Invoices {customerInvoices.length > 0 && `(${customerInvoices.length})`}
                      </h4>
                      <a
                        href={`/invoices/new/?customer=${selectedCustomer.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        New Invoice
                      </a>
                    </div>

                    {loadingInvoices ? (
                      <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200 text-center">
                        <div className="animate-spin rounded-full h-6 w-6 border-2 border-emerald-500 border-t-transparent mx-auto" />
                        <p className="text-xs text-slate-500 mt-2">Loading invoices...</p>
                      </div>
                    ) : customerInvoices.length === 0 ? (
                      <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                        <div className="text-center py-4">
                          <FileText className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                          <p className="text-sm text-slate-500">No invoices yet</p>
                          <p className="text-xs text-slate-400 mt-1">Create the first invoice for {selectedCustomer.name}</p>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200 space-y-2">
                        {customerInvoices.slice(0, 10).map((inv: any) => (
                          <a
                            key={inv.id}
                            href={`/invoices/?invoice=${inv.id}`}
                            className="flex items-center justify-between p-3 rounded-xl bg-white ring-1 ring-slate-100 hover:ring-slate-200 transition-colors"
                          >
                            <div>
                              <div className="text-xs font-semibold text-slate-900">
                                {inv.invoice_number || `INV-${inv.id}`}
                              </div>
                              <div className="text-[11px] text-slate-500">
                                {inv.issue_date ? new Date(inv.issue_date).toLocaleDateString() : '—'} • {inv.status || 'Draft'}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-sm font-bold text-slate-900 tabular-nums">
                                {formatCurrency(inv.grand_total || inv.net_total || 0, currency)}
                              </div>
                              <div className={`text-[10px] font-medium ${inv.status === 'PAID' ? 'text-emerald-600' :
                                  inv.status === 'OVERDUE' ? 'text-rose-600' :
                                    inv.status === 'SENT' ? 'text-amber-600' : 'text-slate-400'
                                }`}>
                                {inv.status === 'PAID' ? '✓ Paid' :
                                  inv.status === 'OVERDUE' ? '! Overdue' :
                                    inv.status === 'SENT' ? '○ Sent' : '○ Draft'}
                              </div>
                            </div>
                          </a>
                        ))}
                        {customerInvoices.length > 10 && (
                          <a
                            href={`/invoices/?customer=${selectedCustomer.id}`}
                            className="block text-center py-2 text-[11px] font-medium text-slate-500 hover:text-slate-700"
                          >
                            View all {customerInvoices.length} invoices →
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Tab Content: CREDITS */}
                {activeTab === 'credits' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-slate-900">Credits &amp; Refunds</h4>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={handleOpenCreditMemoModal}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Issue credit memo
                        </button>
                        <button
                          onClick={handleOpenDepositModal}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                        >
                          <CreditCard className="h-3.5 w-3.5" />
                          Record deposit
                        </button>
                        <button
                          onClick={handleOpenRefundModal}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                        >
                          <CreditCard className="h-3.5 w-3.5" />
                          Record refund
                        </button>
                      </div>
                    </div>

                    {loadingReversals ? (
                      <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200 text-center">
                        <div className="animate-spin rounded-full h-6 w-6 border-2 border-emerald-500 border-t-transparent mx-auto" />
                        <p className="text-xs text-slate-500 mt-2">Loading credits...</p>
                      </div>
                    ) : (
                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Open A/R (after credits)</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">
                            {formatCurrency(reversalsSummary?.open_ar || "0.00", currency)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Open credits</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">
                            {formatCurrency(reversalsSummary?.open_credits || "0.00", currency)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Deposits</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">
                            {formatCurrency(reversalsSummary?.deposit_balance || "0.00", currency)}
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h5 className="text-xs font-semibold text-slate-900">Credit memos</h5>
                      </div>
                      <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200 space-y-2">
                        {creditMemos.length === 0 ? (
                          <div className="text-center py-4 text-xs text-slate-500">No credit memos yet.</div>
                        ) : (
                          creditMemos.map((m) => {
                            const canApply = m.status === "POSTED" && (parseFloat(m.available_amount) || 0) > 0;
                            return (
                              <div
                                key={m.id}
                                className="flex items-center justify-between gap-3 p-3 rounded-xl bg-white ring-1 ring-slate-100"
                              >
                                <div className="min-w-0">
                                  <div className="text-xs font-semibold text-slate-900 truncate">
                                    {m.credit_memo_number || `CM-${m.id}`}
                                  </div>
                                  <div className="text-[11px] text-slate-500 truncate">
                                    {m.posting_date || "—"}
                                    {m.source_invoice_number ? ` • Invoice ${m.source_invoice_number}` : ""}
                                  </div>
                                  <div className="text-[11px] text-slate-400 truncate">
                                    Status: {m.status}
                                  </div>
                                </div>
                                <div className="text-right shrink-0">
                                  <div className="text-sm font-bold text-slate-900 tabular-nums">
                                    {formatCurrency(m.grand_total, currency)}
                                  </div>
                                  <div className="text-[11px] text-slate-500 tabular-nums">
                                    Available {formatCurrency(m.available_amount, currency)}
                                  </div>
                                </div>
                                {canApply && (
                                  <button
                                    onClick={() => handleOpenApplyCreditModal(m)}
                                    className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-[11px] font-medium text-white hover:bg-emerald-700 transition-colors"
                                  >
                                    Apply
                                  </button>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h5 className="text-xs font-semibold text-slate-900">Deposits</h5>
                      <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200 space-y-2">
                        {deposits.length === 0 ? (
                          <div className="text-center py-4 text-xs text-slate-500">No deposits recorded yet.</div>
                        ) : (
                          deposits.map((d) => {
                            const canApply = d.status === "POSTED" && (parseFloat(d.available_amount) || 0) > 0;
                            return (
                              <div
                                key={d.id}
                                className="flex items-center justify-between gap-3 p-3 rounded-xl bg-white ring-1 ring-slate-100"
                              >
                                <div className="min-w-0">
                                  <div className="text-xs font-semibold text-slate-900 truncate">DEP-{d.id}</div>
                                  <div className="text-[11px] text-slate-500 truncate">
                                    {d.posting_date || "—"} • {d.bank_account_name}
                                  </div>
                                  <div className="text-[11px] text-slate-400 truncate">Status: {d.status}</div>
                                </div>
                                <div className="text-right shrink-0">
                                  <div className="text-sm font-bold text-slate-900 tabular-nums">
                                    {formatCurrency(d.amount, currency)}
                                  </div>
                                  <div className="text-[11px] text-slate-500 tabular-nums">
                                    Available {formatCurrency(d.available_amount, currency)}
                                  </div>
                                </div>
                                {canApply && (
                                  <button
                                    onClick={() => handleOpenApplyDepositModal(d)}
                                    className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-[11px] font-medium text-white hover:bg-emerald-700 transition-colors"
                                  >
                                    Apply
                                  </button>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <h5 className="text-xs font-semibold text-slate-900">Refunds</h5>
                      <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200 space-y-2">
                        {refunds.length === 0 ? (
                          <div className="text-center py-4 text-xs text-slate-500">No refunds recorded yet.</div>
                        ) : (
                          refunds.map((r) => (
                            <div
                              key={r.id}
                              className="flex items-center justify-between gap-3 p-3 rounded-xl bg-white ring-1 ring-slate-100"
                            >
                              <div className="min-w-0">
                                <div className="text-xs font-semibold text-slate-900 truncate">REF-{r.id}</div>
                                <div className="text-[11px] text-slate-500 truncate">
                                  {r.posting_date || "—"} • {r.bank_account_name}
                                </div>
                                <div className="text-[11px] text-slate-400 truncate">Status: {r.status}</div>
                              </div>
                              <div className="text-right shrink-0">
                                <div className="text-sm font-bold text-slate-900 tabular-nums">
                                  {formatCurrency(r.amount, currency)}
                                </div>
                                <div className="text-[11px] text-slate-500">
                                  {r.credit_memo_id ? `From CM-${r.credit_memo_id}` : r.deposit_id ? `From DEP-${r.deposit_id}` : "Refund"}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab Content: ACTIVITY */}
                {activeTab === 'activity' && (
                  <div className="space-y-4">
                    <h4 className="text-sm font-semibold text-slate-900">Activity Timeline</h4>

                    <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                      <div className="space-y-4">
                        {customerInvoices.length === 0 ? (
                          <div className="text-center py-4 text-xs text-slate-500">
                            No activity yet for this customer.
                          </div>
                        ) : (
                          customerInvoices.slice(0, 8).map((inv: any) => (
                            <div key={inv.id} className="flex gap-3">
                              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${inv.status === 'PAID' ? 'bg-emerald-100 text-emerald-600' :
                                  inv.status === 'SENT' ? 'bg-blue-100 text-blue-600' :
                                    'bg-slate-100 text-slate-600'
                                }`}>
                                {inv.status === 'PAID' ? <CreditCard className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                              </div>
                              <div>
                                <p className="text-xs font-medium text-slate-900">
                                  {inv.status === 'PAID' ? 'Invoice paid' :
                                    inv.status === 'SENT' ? 'Invoice sent' : 'Invoice created'}
                                </p>
                                <p className="text-[11px] text-slate-500">
                                  {inv.invoice_number || `INV-${inv.id}`} • {formatCurrency(inv.grand_total || inv.net_total || 0, currency)} • {
                                    inv.issue_date ? new Date(inv.issue_date).toLocaleDateString() : 'Recently'
                                  }
                                </p>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab Content: NOTES */}
                {activeTab === 'notes' && (
                  <div className="space-y-4">
                    <h4 className="text-sm font-semibold text-slate-900">Customer Notes</h4>

                    {/* Add note form */}
                    <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                      <textarea
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        placeholder="Add a note about this customer..."
                        className="w-full h-20 px-3 py-2 text-xs bg-white border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-emerald-200"
                      />
                      <div className="mt-2 flex justify-end">
                        <button
                          onClick={handleAddNote}
                          disabled={!noteText.trim()}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Add Note
                        </button>
                      </div>
                    </div>

                    {/* Notes list */}
                    <div className="space-y-2">
                      {customerNotes.length === 0 ? (
                        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200 text-center">
                          <p className="text-xs text-slate-500">No notes yet. Add one above!</p>
                        </div>
                      ) : (
                        customerNotes.map((note) => (
                          <div key={note.id} className="rounded-2xl bg-white p-3 ring-1 ring-slate-200">
                            <p className="text-xs text-slate-900">{note.text}</p>
                            <p className="mt-1 text-[10px] text-slate-400">
                              {new Date(note.created_at).toLocaleString()}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Payment Modal */}
      {paymentModalOpen && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">Record Payment</h3>
              <button
                onClick={() => setPaymentModalOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500"
              >
                ×
              </button>
            </div>

            <p className="text-xs text-slate-500 mb-4">
              Recording payment for <span className="font-medium text-slate-700">{selectedCustomer.name}</span>
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Amount</label>
                <input
                  type="text"
                  value={paymentAmount}
                  onChange={(e) => handleAmountChange(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="0.00"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Tax Rate (optional)</label>
                <select
                  value={paymentTaxRateId}
                  onChange={(e) => handleTaxRateChange(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  <option value="">No tax</option>
                  {taxRates.map(rate => (
                    <option key={rate.id} value={String(rate.id)}>
                      {rate.name} ({rate.code}) - {rate.percentage}%
                    </option>
                  ))}
                </select>
                {paymentTaxAmount > 0 && (
                  <div className="mt-1 text-[11px] text-emerald-600 font-medium">
                    Tax: {formatCurrency(paymentTaxAmount, currency)} • Total: {formatCurrency((parseFloat(paymentAmount) || 0) + paymentTaxAmount, currency)}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Payment Date</label>
                <input
                  type="date"
                  value={paymentDate}
                  onChange={(e) => setPaymentDate(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Payment Method</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  <option value="EFT">EFT / Bank Transfer</option>
                  <option value="Check">Check</option>
                  <option value="Cash">Cash</option>
                  <option value="Credit Card">Credit Card</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Reference (optional)</label>
                <input
                  type="text"
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="Transaction ID, check number, etc."
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Notes (optional)</label>
                <textarea
                  value={paymentNotes}
                  onChange={(e) => setPaymentNotes(e.target.value)}
                  className="w-full h-16 px-3 py-2 text-sm border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="Any additional notes..."
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setPaymentModalOpen(false)}
                className="flex-1 h-10 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSavePayment}
                className="flex-1 h-10 rounded-xl bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                Record Payment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Credit Memo Modal */}
      {creditMemoModalOpen && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">Issue Credit Memo</h3>
              <button
                onClick={() => setCreditMemoModalOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500"
              >
                ×
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Source invoice (optional)</label>
                <select
                  value={creditMemoSourceInvoiceId}
                  onChange={(e) => setCreditMemoSourceInvoiceId(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  {customerInvoices.map((inv: any) => {
                    const label = inv.invoice_number || `INV-${inv.id}`;
                    const total = inv.grand_total || inv.net_total || 0;
                    return (
                      <option key={inv.id} value={String(inv.id)}>
                        {label} • {formatCurrency(total, currency)}
                      </option>
                    );
                  })}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Net amount</label>
                <input
                  type="number"
                  step="0.01"
                  value={creditMemoNetTotal}
                  onChange={(e) => setCreditMemoNetTotal(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="0.00"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Posting date</label>
                <input
                  type="date"
                  value={creditMemoPostingDate}
                  onChange={(e) => setCreditMemoPostingDate(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Memo (optional)</label>
                <textarea
                  value={creditMemoMemo}
                  onChange={(e) => setCreditMemoMemo(e.target.value)}
                  className="w-full h-16 px-3 py-2 text-sm border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="Reason / details..."
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setCreditMemoModalOpen(false)}
                className="flex-1 h-10 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateAndPostCreditMemo}
                className="flex-1 h-10 rounded-xl bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                Post Credit Memo
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Apply Credit Memo Modal */}
      {applyCreditModalOpen && selectedCustomer && applyCreditMemoId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">Apply Credit Memo</h3>
              <button
                onClick={() => setApplyCreditModalOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500"
              >
                ×
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Invoice</label>
                <select
                  value={applyCreditInvoiceId}
                  onChange={(e) => setApplyCreditInvoiceId(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  {customerInvoices.map((inv: any) => {
                    const label = inv.invoice_number || `INV-${inv.id}`;
                    const total = inv.grand_total || inv.net_total || 0;
                    return (
                      <option key={inv.id} value={String(inv.id)}>
                        {label} • {formatCurrency(total, currency)}
                      </option>
                    );
                  })}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Amount to apply</label>
                <input
                  type="number"
                  step="0.01"
                  value={applyCreditAmount}
                  onChange={(e) => setApplyCreditAmount(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setApplyCreditModalOpen(false)}
                className="flex-1 h-10 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyCreditMemo}
                className="flex-1 h-10 rounded-xl bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deposit Modal */}
      {depositModalOpen && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">Record Deposit</h3>
              <button
                onClick={() => setDepositModalOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500"
              >
                ×
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Bank account</label>
                <select
                  value={depositBankAccountId}
                  onChange={(e) => setDepositBankAccountId(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  {bankAccounts.map((a) => (
                    <option key={a.id} value={String(a.id)}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Amount</label>
                <input
                  type="number"
                  step="0.01"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Posting date</label>
                <input
                  type="date"
                  value={depositPostingDate}
                  onChange={(e) => setDepositPostingDate(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Memo (optional)</label>
                <textarea
                  value={depositMemo}
                  onChange={(e) => setDepositMemo(e.target.value)}
                  className="w-full h-16 px-3 py-2 text-sm border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="Retainer / overpayment..."
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setDepositModalOpen(false)}
                className="flex-1 h-10 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateDeposit}
                className="flex-1 h-10 rounded-xl bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                Record Deposit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Apply Deposit Modal */}
      {applyDepositModalOpen && selectedCustomer && applyDepositId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">Apply Deposit</h3>
              <button
                onClick={() => setApplyDepositModalOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500"
              >
                ×
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Invoice</label>
                <select
                  value={applyDepositInvoiceId}
                  onChange={(e) => setApplyDepositInvoiceId(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  {customerInvoices.map((inv: any) => {
                    const label = inv.invoice_number || `INV-${inv.id}`;
                    const total = inv.grand_total || inv.net_total || 0;
                    return (
                      <option key={inv.id} value={String(inv.id)}>
                        {label} • {formatCurrency(total, currency)}
                      </option>
                    );
                  })}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Amount to apply</label>
                <input
                  type="number"
                  step="0.01"
                  value={applyDepositAmount}
                  onChange={(e) => setApplyDepositAmount(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setApplyDepositModalOpen(false)}
                className="flex-1 h-10 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyDeposit}
                className="flex-1 h-10 rounded-xl bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Refund Modal */}
      {refundModalOpen && selectedCustomer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">Record Refund</h3>
              <button
                onClick={() => setRefundModalOpen(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500"
              >
                ×
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Bank account</label>
                <select
                  value={refundBankAccountId}
                  onChange={(e) => setRefundBankAccountId(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  {bankAccounts.map((a) => (
                    <option key={a.id} value={String(a.id)}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Refund source</label>
                <select
                  value={refundSourceType}
                  onChange={(e) => {
                    const v = e.target.value as "credit_memo" | "deposit" | "none";
                    setRefundSourceType(v);
                    setRefundSourceId("");
                  }}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                >
                  <option value="credit_memo">Credit memo</option>
                  <option value="deposit">Deposit</option>
                  <option value="none">Other / A/R</option>
                </select>
              </div>

              {refundSourceType !== "none" && (
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 mb-1">Source</label>
                  <select
                    value={refundSourceId}
                    onChange={(e) => setRefundSourceId(e.target.value)}
                    className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  >
                    <option value="">Select…</option>
                    {refundSourceType === "credit_memo" &&
                      creditMemos
                        .filter((m) => m.status === "POSTED" && (parseFloat(m.available_amount) || 0) > 0)
                        .map((m) => (
                          <option key={m.id} value={String(m.id)}>
                            {m.credit_memo_number || `CM-${m.id}`} • {formatCurrency(m.available_amount, currency)} available
                          </option>
                        ))}
                    {refundSourceType === "deposit" &&
                      deposits
                        .filter((d) => d.status === "POSTED" && (parseFloat(d.available_amount) || 0) > 0)
                        .map((d) => (
                          <option key={d.id} value={String(d.id)}>
                            DEP-{d.id} • {formatCurrency(d.available_amount, currency)} available
                          </option>
                        ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Amount</label>
                <input
                  type="number"
                  step="0.01"
                  value={refundAmount}
                  onChange={(e) => setRefundAmount(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="0.00"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Posting date</label>
                <input
                  type="date"
                  value={refundPostingDate}
                  onChange={(e) => setRefundPostingDate(e.target.value)}
                  className="w-full h-10 px-3 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-200"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">Memo (optional)</label>
                <textarea
                  value={refundMemo}
                  onChange={(e) => setRefundMemo(e.target.value)}
                  className="w-full h-16 px-3 py-2 text-sm border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-emerald-200"
                  placeholder="Refund details..."
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setRefundModalOpen(false)}
                className="flex-1 h-10 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateRefund}
                className="flex-1 h-10 rounded-xl bg-emerald-600 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                Record Refund
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomersPage;
