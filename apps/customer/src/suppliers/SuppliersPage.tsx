import React, { useState, useEffect, useMemo } from 'react';
import {
  Plus,
  Search,
  Filter,
  Mail,
  Phone,
  Download,
  TrendingUp,
  CreditCard,
  CalendarDays,
  FileText,
  AlertTriangle,
} from "lucide-react";

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface Supplier {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  total_spend: string;
  ytd_spend: string;
  expense_count: number;
  is_active?: boolean;
  last_expense_date?: string;
}

interface Stats {
  total_suppliers: number;
  total_spend: string;
  ytd_spend: string;
}

interface SupplierData {
  suppliers: Supplier[];
  stats: Stats;
  currency: string;
}

interface SupplierExpense {
  id: number;
  expense_number?: string;
  issue_date?: string;
  status?: string;
  total?: string;
  net_total?: string;
}

// -----------------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------------

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

function classNames(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

function statusBadgeClass(isActive: boolean): string {
  return isActive
    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
    : "bg-slate-100 text-slate-500 border border-slate-200";
}

type FilterTab = "all" | "active" | "inactive";
type DetailTab = "overview" | "expenses" | "credits" | "activity" | "notes";

const FILTER_TABS = [
  { id: "all" as FilterTab, label: "All" },
  { id: "active" as FilterTab, label: "Active" },
  { id: "inactive" as FilterTab, label: "Inactive" },
];

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export const SuppliersPage: React.FC = () => {
  const [data, setData] = useState<SupplierData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterTab, setFilterTab] = useState<FilterTab>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");

  // Expenses for selected supplier
  const [supplierExpenses, setSupplierExpenses] = useState<SupplierExpense[]>([]);
  const [loadingExpenses, setLoadingExpenses] = useState(false);

  // Notes
  const [noteText, setNoteText] = useState("");
  const [supplierNotes, setSupplierNotes] = useState<Array<{ id: number; text: string; created_at: string }>>([]);

  const fetchData = async () => {
    try {
      const response = await fetch(`/api/suppliers/list/`);
      if (!response.ok) throw new Error("Failed to fetch suppliers");
      const json = await response.json();
      setData(json);
      if (json.suppliers?.length > 0 && !selectedId) {
        setSelectedId(json.suppliers[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Fetch expenses when supplier changes
  useEffect(() => {
    if (!selectedId) return;
    setLoadingExpenses(true);
    fetch(`/api/expenses/list/?supplier=${selectedId}`)
      .then(res => res.json())
      .then(json => setSupplierExpenses(json.expenses || []))
      .catch(() => setSupplierExpenses([]))
      .finally(() => setLoadingExpenses(false));
  }, [selectedId]);

  const suppliers = data?.suppliers || [];
  const currency = data?.currency || "CAD";
  const stats = data?.stats;

  const filteredSuppliers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return suppliers.filter((s) => {
      if (filterTab === "active" && s.is_active === false) return false;
      if (filterTab === "inactive" && s.is_active !== false) return false;
      if (!q) return true;
      return s.name.toLowerCase().includes(q) || (s.email && s.email.toLowerCase().includes(q));
    });
  }, [suppliers, search, filterTab]);

  const selectedSupplier = useMemo(
    () => suppliers.find((s) => s.id === selectedId) ?? filteredSuppliers[0] ?? null,
    [suppliers, selectedId, filteredSuppliers]
  );

  const summary = useMemo(() => {
    const totalOpen = suppliers.reduce((sum, s) => sum + (parseFloat(s.ytd_spend) || 0), 0);
    const activeCount = suppliers.filter((s) => s.is_active !== false).length;
    const inactiveCount = suppliers.filter((s) => s.is_active === false).length;
    return { totalOpen, activeCount, inactiveCount, total: suppliers.length };
  }, [suppliers]);

  const handleAddNote = () => {
    if (!selectedSupplier || !noteText.trim()) return;
    const newNote = { id: Date.now(), text: noteText, created_at: new Date().toISOString() };
    setSupplierNotes([newNote, ...supplierNotes]);
    setNoteText("");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-slate-900 border-t-transparent mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading suppliers...</p>
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
        {/* Header */}
        <header className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
              <span>Directory</span>
              <span className="text-slate-300">/</span>
              <span className="text-slate-600">Suppliers</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              Suppliers
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50">
              <Download className="h-3.5 w-3.5" />
              Export
            </button>
            <a
              href="/suppliers/new/"
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-slate-900/10 transition-transform hover:scale-105 active:scale-95"
            >
              <Plus className="h-3.5 w-3.5" />
              New Supplier
            </a>
          </div>
        </header>

        <div className="flex flex-col gap-8">
          {/* Top Section: Metrics */}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 transition-all hover:shadow-md">
              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
                Open Payables
              </span>
              <span className="mt-3 text-3xl font-bold tracking-tight text-slate-900 font-mono-soft">
                {formatCurrency(stats?.ytd_spend || 0, currency)}
              </span>
              <span className="mt-2 text-xs font-medium text-emerald-600 flex items-center gap-1">
                <TrendingUp className="h-3 w-3" /> Live from ledger
              </span>
            </div>
            <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 transition-all hover:shadow-md">
              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Spend</span>
              <span className="mt-3 text-xl font-bold tracking-tight text-slate-900 font-mono-soft">
                {formatCurrency(stats?.total_spend || 0, currency).split('.')[0]}
              </span>
              <span className="mt-1 text-[10px] text-slate-400">YTD Volume</span>
            </div>
            <div className="flex flex-col rounded-[2rem] bg-white p-6 shadow-sm ring-1 ring-slate-100 transition-all hover:shadow-md">
              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Active</span>
              <span className="mt-3 text-2xl font-bold tracking-tight text-slate-900 font-mono-soft">{summary.activeCount}</span>
              <span className="mt-1 text-[10px] text-slate-400">Relationships</span>
            </div>
          </div>

          {/* Main content: list + detail */}
          <section className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)]">
            {/* Left: Suppliers list */}
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="px-4 py-4 border-b border-slate-100">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">Supplier directory</h3>
                    <p className="text-xs text-slate-500">Search, filter, and select a supplier.</p>
                  </div>
                </div>

                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <div className="relative flex-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search by name or email"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="w-full h-9 border border-slate-200 bg-slate-50 rounded-lg pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-500"
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
                      className={classNames(
                        "inline-flex items-center rounded-full px-3 py-1 transition-all",
                        filterTab === tab.id
                          ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200 mb-accent-underline"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      )}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="h-[420px] overflow-y-auto">
                <div className="divide-y divide-slate-100">
                  {filteredSuppliers.length === 0 && (
                    <div className="flex flex-col items-center justify-center gap-2 px-5 py-10 text-center text-xs text-slate-400">
                      <p>No suppliers match your filters.</p>
                      <a href="/suppliers/new/" className="text-slate-900 hover:underline">Create a new supplier</a>
                    </div>
                  )}

                  {filteredSuppliers.map((supplier) => {
                    const isSelected = selectedSupplier?.id === supplier.id;
                    const isActive = supplier.is_active !== false;
                    return (
                      <button
                        key={supplier.id}
                        onClick={() => setSelectedId(supplier.id)}
                        className={classNames(
                          "w-full flex items-start gap-3 px-4 py-3 text-left transition-colors",
                          isSelected ? "bg-slate-50" : "hover:bg-slate-50/50"
                        )}
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-700 to-slate-900 text-sm font-semibold text-white shadow-sm">
                          {supplier.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0 overflow-hidden">
                          <div className="text-sm font-semibold text-slate-900 truncate">{supplier.name}</div>
                          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                            {supplier.email && (
                              <span className="inline-flex items-center gap-1">
                                <Mail className="h-3 w-3" />
                                <span className="truncate max-w-[150px]">{supplier.email}</span>
                              </span>
                            )}
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-2">
                            <span className={classNames(
                              "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px]",
                              statusBadgeClass(isActive)
                            )}>
                              <span className={classNames(
                                "mr-1.5 h-1.5 w-1.5 rounded-full",
                                isActive ? "bg-emerald-500" : "bg-slate-400"
                              )} />
                              {isActive ? "Active" : "Inactive"}
                            </span>
                          </div>
                        </div>
                        <div className="flex flex-col items-end justify-between gap-1 text-right text-[11px]">
                          <div className="text-[12px] font-semibold text-slate-900">
                            {formatCurrency(supplier.ytd_spend, currency)}
                          </div>
                          <div className="text-[11px] text-slate-400">
                            {supplier.expense_count} expenses
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Right: Supplier details */}
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="px-4 py-4 border-b border-slate-100">
                {selectedSupplier ? (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-700 to-slate-900 text-sm font-semibold text-white shadow-sm">
                          {selectedSupplier.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-slate-900 sm:text-base">
                            {selectedSupplier.name}
                          </h3>
                          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                            {selectedSupplier.email && (
                              <span className="inline-flex items-center gap-1">
                                <Mail className="h-3 w-3" />
                                {selectedSupplier.email}
                              </span>
                            )}
                            {selectedSupplier.phone && (
                              <span className="inline-flex items-center gap-1">
                                <Phone className="h-3 w-3" />
                                {selectedSupplier.phone}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                        <span className={classNames(
                          "inline-flex items-center rounded-full px-2.5 py-0.5",
                          statusBadgeClass(selectedSupplier.is_active !== false)
                        )}>
                          <span className={classNames(
                            "mr-1.5 h-1.5 w-1.5 rounded-full",
                            selectedSupplier.is_active !== false ? "bg-emerald-500" : "bg-slate-400"
                          )} />
                          {selectedSupplier.is_active !== false ? "Active" : "Inactive"}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-2">
                      <div className="text-right text-xs text-slate-500">Total spend</div>
                      <div className="text-lg font-semibold tracking-tight text-slate-900">
                        {formatCurrency(selectedSupplier.total_spend, currency)}
                      </div>
                      <div className="flex gap-1.5">
                        <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-700 hover:bg-slate-100 transition-colors">
                          <CreditCard className="h-3.5 w-3.5" />
                          Record payment
                        </button>
                        <a
                          href={`/expenses/new/?supplier=${selectedSupplier.id}`}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          Create expense
                        </a>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="py-6 text-center text-xs text-slate-400">
                    Select a supplier to see details.
                  </div>
                )}
              </div>

              {/* Tabs content */}
              {selectedSupplier && (
                <div className="p-4">
                  <div className="mb-4 flex gap-1 rounded-2xl bg-slate-100 p-1 text-xs">
                    {(["overview", "expenses", "credits", "activity", "notes"] as DetailTab[]).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={classNames(
                          "flex-1 rounded-xl px-3 py-2 font-medium capitalize transition-all",
                          activeTab === tab
                            ? "bg-white text-slate-900 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                        )}
                      >
                        {tab}
                      </button>
                    ))}
                  </div>

                  {/* Tab: OVERVIEW */}
                  {activeTab === "overview" && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-semibold text-slate-900">Supplier Overview</h4>
                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Total Spend</div>
                          <div className="mt-1 text-lg font-semibold text-slate-900">
                            {formatCurrency(selectedSupplier.total_spend, currency)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">YTD Spend</div>
                          <div className="mt-1 text-lg font-semibold text-slate-900">
                            {formatCurrency(selectedSupplier.ytd_spend, currency)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Total Expenses</div>
                          <div className="mt-1 text-lg font-semibold text-slate-900">
                            {selectedSupplier.expense_count}
                          </div>
                        </div>
                      </div>
                      {selectedSupplier.address && (
                        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Address</div>
                          <div className="mt-1 text-sm text-slate-900">{selectedSupplier.address}</div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab: EXPENSES */}
                  {activeTab === "expenses" && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-semibold text-slate-900">Expenses</h4>
                        <a
                          href={`/expenses/new/?supplier=${selectedSupplier.id}`}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          New expense
                        </a>
                      </div>

                      {loadingExpenses ? (
                        <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200 text-center">
                          <div className="animate-spin rounded-full h-6 w-6 border-2 border-slate-500 border-t-transparent mx-auto" />
                          <p className="text-xs text-slate-500 mt-2">Loading expenses...</p>
                        </div>
                      ) : supplierExpenses.length === 0 ? (
                        <div className="rounded-2xl bg-slate-50 p-8 ring-1 ring-slate-200 text-center">
                          <FileText className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                          <p className="text-sm text-slate-500">No expenses yet</p>
                          <p className="text-xs text-slate-400 mt-1">Create the first expense for {selectedSupplier.name}</p>
                        </div>
                      ) : (
                        <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200 space-y-2">
                          {supplierExpenses.slice(0, 10).map((exp) => (
                            <a
                              key={exp.id}
                              href={`/expenses/${exp.id}/`}
                              className="flex items-center justify-between p-3 rounded-xl bg-white ring-1 ring-slate-100 hover:ring-slate-200 transition-colors"
                            >
                              <div>
                                <div className="text-xs font-semibold text-slate-900">
                                  {exp.expense_number || `EXP-${exp.id}`}
                                </div>
                                <div className="text-[11px] text-slate-500">
                                  {exp.issue_date ? new Date(exp.issue_date).toLocaleDateString() : "—"} • {exp.status || "Draft"}
                                </div>
                              </div>
                              <div className="text-right">
                                <div className="text-sm font-bold text-slate-900 font-mono-soft">
                                  {formatCurrency(exp.total || exp.net_total || 0, currency)}
                                </div>
                              </div>
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab: CREDITS */}
                  {activeTab === "credits" && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-semibold text-slate-900">Credits & Prepayments</h4>
                        <div className="flex flex-wrap gap-2">
                          <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 text-[11px] font-medium text-white hover:bg-slate-800 transition-colors">
                            <Plus className="h-3.5 w-3.5" />
                            Issue debit memo
                          </button>
                          <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-700 hover:bg-slate-50 transition-colors">
                            <CreditCard className="h-3.5 w-3.5" />
                            Record prepayment
                          </button>
                        </div>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Open A/P (after credits)</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">
                            {formatCurrency(0, currency)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Open credits</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">
                            {formatCurrency(0, currency)}
                          </div>
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                          <div className="text-[11px] text-slate-500">Prepayments</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900">
                            {formatCurrency(0, currency)}
                          </div>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <h5 className="text-xs font-semibold text-slate-900">Debit memos</h5>
                        <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200">
                          <div className="text-center py-4 text-xs text-slate-500">No debit memos yet.</div>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <h5 className="text-xs font-semibold text-slate-900">Prepayments</h5>
                        <div className="rounded-2xl bg-slate-50 p-2 ring-1 ring-slate-200">
                          <div className="text-center py-4 text-xs text-slate-500">No prepayments recorded yet.</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Tab: ACTIVITY */}
                  {activeTab === "activity" && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-semibold text-slate-900">Activity Timeline</h4>
                      <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                        {supplierExpenses.length === 0 ? (
                          <div className="text-center py-4 text-xs text-slate-500">
                            No activity yet for this supplier.
                          </div>
                        ) : (
                          <div className="space-y-4">
                            {supplierExpenses.slice(0, 8).map((exp) => (
                              <div key={exp.id} className="flex gap-3">
                                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                                  <FileText className="h-4 w-4" />
                                </div>
                                <div>
                                  <p className="text-xs font-medium text-slate-900">
                                    Expense {exp.status === "PAID" ? "paid" : "created"}
                                  </p>
                                  <p className="text-[11px] text-slate-500">
                                    {exp.expense_number || `EXP-${exp.id}`} • {formatCurrency(exp.total || exp.net_total || 0, currency)}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Tab: NOTES */}
                  {activeTab === "notes" && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-semibold text-slate-900">Supplier Notes</h4>
                      <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                        <textarea
                          value={noteText}
                          onChange={(e) => setNoteText(e.target.value)}
                          placeholder="Add a note about this supplier..."
                          className="w-full h-20 px-3 py-2 text-xs bg-white border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-slate-200"
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

                      <div className="space-y-2">
                        {supplierNotes.length === 0 ? (
                          <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200 text-center">
                            <p className="text-xs text-slate-500">No notes yet. Add one above!</p>
                          </div>
                        ) : (
                          supplierNotes.map((note) => (
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
      </div>
    </div>
  );
};

export default SuppliersPage;
