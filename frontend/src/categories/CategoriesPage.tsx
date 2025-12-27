import React, { useMemo, useState, useEffect } from "react";

// Types
interface Category {
  id: number;
  name: string;
  code: string;
  type: "INCOME" | "EXPENSE";
  description: string;
  isArchived: boolean;
  accountLabel?: string;
  accountId?: number;
  transactionCount: number;
  currentMonthTotal: number;
  ytdTotal: number;
  lastUsedAt?: string;
}

interface Stats {
  activeCount: number;
  incomeCategories: number;
  expenseCategories: number;
  uncategorizedCount: number;
  uncategorizedYtd: number;
}

const typeLabel: Record<string, string> = {
  INCOME: "Income",
  EXPENSE: "Expense",
};

const typePillClasses: Record<string, string> = {
  INCOME: "bg-emerald-50 text-emerald-700 border-emerald-100",
  EXPENSE: "bg-rose-50 text-rose-700 border-rose-100",
};

const formatCurrency = (amount: number, currency = "CAD"): string => {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
};

const formatDate = (date?: string | null): string => {
  if (!date) return "—";
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
};

const CategoriesPage: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [stats, setStats] = useState<Stats>({
    activeCount: 0,
    incomeCategories: 0,
    expenseCategories: 0,
    uncategorizedCount: 0,
    uncategorizedYtd: 0,
  });
  const [currency, setCurrency] = useState("CAD");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "INCOME" | "EXPENSE">("all");
  const [statusFilter, setStatusFilter] = useState<"active" | "archived" | "all">("active");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (typeFilter !== "all") params.set("type", typeFilter.toLowerCase());
      if (statusFilter === "archived") params.set("archived", "true");
      if (search) params.set("q", search);

      const response = await fetch(`/api/categories/list/?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch categories");

      const json = await response.json();

      // Map API response
      const mapped: Category[] = (json.categories || []).map((cat: any) => ({
        id: cat.id,
        name: cat.name,
        code: cat.code || `CAT-${cat.id}`,
        type: cat.type,
        description: cat.description || "",
        isArchived: cat.is_archived,
        accountLabel: cat.account_label || undefined,
        accountId: cat.account_id || undefined,
        transactionCount: cat.transaction_count || 0,
        currentMonthTotal: parseFloat(cat.current_month_total) || 0,
        ytdTotal: parseFloat(cat.ytd_total) || 0,
        lastUsedAt: cat.last_used_at || undefined,
      }));

      setCategories(mapped);
      setStats({
        activeCount: json.stats?.active_count || 0,
        incomeCategories: json.stats?.income_categories || 0,
        expenseCategories: json.stats?.expense_categories || 0,
        uncategorizedCount: json.stats?.uncategorized_count || 0,
        uncategorizedYtd: parseFloat(json.stats?.uncategorized_ytd) || 0,
      });
      setCurrency(json.currency || "CAD");

      if (mapped.length > 0 && !selectedId) {
        setSelectedId(mapped[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [typeFilter, statusFilter]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchData();
    }, 300);
    return () => clearTimeout(debounce);
  }, [search]);

  const filteredCategories = useMemo(() => {
    if (statusFilter === "all") return categories;
    if (statusFilter === "archived") return categories.filter((c) => c.isArchived);
    return categories.filter((c) => !c.isArchived);
  }, [categories, statusFilter]);

  const selectedCategory = useMemo(
    () => filteredCategories.find((c) => c.id === selectedId) ?? filteredCategories[0] ?? null,
    [filteredCategories, selectedId]
  );

  if (loading && categories.length === 0) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-900 border-t-transparent" />
          <p className="text-sm text-slate-500">Loading categories...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="rounded-2xl border border-red-100 bg-red-50 p-6 text-center max-w-md">
          <p className="text-sm font-medium text-red-700">{error}</p>
          <button
            onClick={() => { setError(null); fetchData(); }}
            className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-xs font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-6">
        {/* Header */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Categories
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Organize how money flows in and out of your books. Categories drive your
              P&L, dashboards, and tax engine.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50 transition-colors">
              Bulk actions
            </button>
            <a
              href="/categories/new/"
              className="rounded-full bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 transition-colors"
            >
              + New category
            </a>
          </div>
        </header>

        {/* KPI Cards */}
        <section className="grid gap-4 md:grid-cols-4">
          <div className="flex flex-col justify-between rounded-[1.25rem] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                Active categories
              </p>
              <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                Chart of accounts
              </span>
            </div>
            <p className="mt-3 text-2xl font-bold tracking-tight text-slate-900">
              {stats.activeCount}
            </p>
            <p className="mt-1 text-xs text-slate-500 font-medium">Across all types</p>
          </div>

          <div className="rounded-[1.25rem] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Income vs Expenses
            </p>
            <div className="mt-3 flex items-end justify-between">
              <div>
                <p className="text-sm font-medium text-emerald-700">{stats.incomeCategories} income</p>
                <p className="text-sm font-medium text-rose-700">{stats.expenseCategories} expense</p>
              </div>
              <div className="flex w-32 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-2 bg-emerald-400"
                  style={{ width: `${(stats.incomeCategories / Math.max(stats.incomeCategories + stats.expenseCategories, 1)) * 100}%` }}
                />
                <div
                  className="h-2 bg-rose-400"
                  style={{ width: `${(stats.expenseCategories / Math.max(stats.incomeCategories + stats.expenseCategories, 1)) * 100}%` }}
                />
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-500 font-medium">You can rebalance at any time.</p>
          </div>

          <div className="rounded-[1.25rem] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              Total categories
            </p>
            <p className="mt-3 text-2xl font-bold tracking-tight text-slate-900">
              {categories.length}
            </p>
            <p className="mt-1 text-xs text-slate-500 font-medium">
              Active + archived categories in system.
            </p>
          </div>

          <div className="rounded-[1.25rem] border border-amber-200 bg-amber-50/60 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-bold uppercase tracking-widest text-amber-700">
                Uncategorized watch
              </p>
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                Assistant
              </span>
            </div>
            <p className="mt-3 text-sm font-bold text-amber-900">
              {stats.uncategorizedCount} transactions uncategorized
            </p>
            <p className="mt-1 text-xs text-amber-800 font-medium">
              {stats.uncategorizedYtd > 0
                ? `${formatCurrency(stats.uncategorizedYtd, currency)} YTD sitting in Uncategorized.`
                : "You're fully categorized for the year."}
            </p>
            <a
              href="/transactions/?status=uncategorized"
              className="mt-3 inline-flex items-center text-xs font-bold text-amber-900 underline-offset-2 hover:underline"
            >
              Review uncategorized activity
            </a>
          </div>
        </section>

        {/* Main Content */}
        <section className="flex flex-col gap-4 rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-1 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5">
              <span className="text-xs text-slate-400">Search</span>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Name, code, or description"
                className="h-6 flex-1 border-none bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-0 font-medium"
              />
            </div>

            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-1 py-1 text-xs font-medium text-slate-600">
              {(["all", "INCOME", "EXPENSE"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`rounded-full px-3 py-1 transition-all ${typeFilter === t
                    ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200 mb-accent-underline"
                    : "text-slate-600 hover:bg-white"
                    }`}
                >
                  {t === "all" ? "All types" : typeLabel[t]}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-1 py-1 text-xs font-medium text-slate-600">
              {(["active", "archived", "all"] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`rounded-full px-3 py-1 capitalize transition-all ${statusFilter === status
                    ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200 mb-accent-underline"
                    : "text-slate-600 hover:bg-white"
                    }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>

          {/* Two Column Grid */}
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.4fr)]">
            {/* Categories Table */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50/60 overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 bg-white/50 backdrop-blur-sm">
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  Category list
                </p>
                <p className="text-[10px] font-medium text-slate-400">
                  {filteredCategories.length} shown
                </p>
              </div>

              <div className="max-h-[460px] overflow-auto">
                <table className="min-w-full text-left text-sm text-slate-700">
                  <thead className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50/95 text-[10px] uppercase tracking-wider font-bold text-slate-400 backdrop-blur">
                    <tr>
                      <th className="px-5 py-2.5">Name</th>
                      <th className="px-5 py-2.5">Type</th>
                      <th className="px-5 py-2.5">Code</th>
                      <th className="px-5 py-2.5 text-right">This month</th>
                      <th className="px-5 py-2.5 text-right">YTD</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCategories.map((cat) => {
                      const isSelected = selectedCategory?.id === cat.id;
                      return (
                        <tr
                          key={cat.id}
                          onClick={() => setSelectedId(cat.id)}
                          className={`group cursor-pointer border-b border-slate-100 text-xs transition last:border-b-0 ${isSelected ? "bg-white relative z-10" : "hover:bg-white"
                            }`}
                        >
                          <td className="px-5 py-3">
                            <div className="flex flex-col">
                              <span className="text-[13px] font-bold text-slate-900">
                                {cat.name}
                              </span>
                              <span className="mt-0.5 text-[11px] text-slate-500 font-medium line-clamp-1">
                                {cat.description || "No description"}
                              </span>
                            </div>
                          </td>
                          <td className="px-5 py-3">
                            <span
                              className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${typePillClasses[cat.type] || "bg-slate-50 text-slate-600 border-slate-200"
                                }`}
                            >
                              {typeLabel[cat.type] || cat.type}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-[12px] font-mono text-slate-600">{cat.code}</td>
                          <td className="px-5 py-3 text-right text-[12px] font-semibold text-slate-700 font-mono-soft">
                            {formatCurrency(cat.currentMonthTotal, currency)}
                          </td>
                          <td className="px-5 py-3 text-right text-[12px] text-slate-500 font-medium font-mono-soft">
                            {formatCurrency(cat.ytdTotal, currency)}
                          </td>
                        </tr>
                      );
                    })}
                    {filteredCategories.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-5 py-12 text-center text-xs text-slate-400 font-medium"
                        >
                          No categories match your filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right Panel */}
            <div className="flex flex-col gap-4">
              {/* Companion */}
              <div className="relative rounded-2xl border border-slate-100 bg-white/50 p-5 shadow-sm backdrop-blur-md shadow-[0_0_40px_-10px_rgba(99,102,241,0.12)]">
                <p className="text-[10px] font-bold tracking-[0.2em] text-slate-400 uppercase">
                  COMPANION
                </p>
                <p className="mt-1.5 text-xs text-slate-600 leading-relaxed font-medium">
                  Categories help drive your dashboards, P&L views, and tax mappings.
                  Keep system categories intact and archive unused ones instead of
                  deleting.
                </p>
                <div className="mt-4 grid grid-cols-2 gap-3 text-[11px] text-slate-600">
                  <div className="rounded-xl bg-white px-3 py-2.5 shadow-sm border border-slate-100">
                    <p className="font-bold text-slate-900">Health check</p>
                    <p className="mt-1 text-[10px] text-slate-500 font-medium">
                      {stats.uncategorizedCount === 0
                        ? "All transactions are categorized."
                        : `${stats.uncategorizedCount} uncategorized transactions need attention.`}
                    </p>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2.5 shadow-sm border border-slate-100">
                    <p className="font-bold text-slate-900">Suggestions</p>
                    <p className="mt-1 text-[10px] text-slate-500 font-medium">
                      Consider merging duplicate expense categories next.
                    </p>
                  </div>
                </div>
              </div>

              {/* Category Details */}
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-5">
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                  Category details
                </p>

                {selectedCategory ? (
                  <div className="mt-4 space-y-5 text-xs text-slate-600">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-base font-bold text-slate-900">
                          {selectedCategory.name}
                        </p>
                        <p className="mt-1 text-[11px] text-slate-500 font-medium">
                          {selectedCategory.description || "No description provided yet."}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1.5">
                        <span
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${typePillClasses[selectedCategory.type] || "bg-slate-50 text-slate-600 border-slate-200"
                            }`}
                        >
                          {typeLabel[selectedCategory.type] || selectedCategory.type}
                        </span>
                        <span
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${selectedCategory.isArchived
                            ? "bg-slate-50 text-slate-500 border-slate-200"
                            : "bg-emerald-50 text-emerald-700 border-emerald-100"
                            }`}
                        >
                          {selectedCategory.isArchived ? "Archived" : "Active"}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Code
                        </p>
                        <p className="mt-0.5 text-sm font-bold text-slate-900 font-mono">
                          {selectedCategory.code}
                        </p>
                        <p className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Ledger Account
                        </p>
                        <p className="mt-0.5 text-sm font-medium text-slate-700">
                          {selectedCategory.accountLabel || "Not mapped"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Activity this month
                        </p>
                        <p className="mt-0.5 text-sm font-bold text-slate-900 font-mono-soft">
                          {formatCurrency(selectedCategory.currentMonthTotal, currency)}
                        </p>
                        <p className="mt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          YTD total
                        </p>
                        <p className="mt-0.5 text-sm font-medium text-slate-800 font-mono-soft">
                          {formatCurrency(selectedCategory.ytdTotal, currency)}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Usage
                        </p>
                        <p className="mt-1 text-sm font-bold text-slate-900">
                          {selectedCategory.transactionCount} transactions
                        </p>
                        <p className="mt-1 text-[10px] font-medium text-slate-500">
                          Last used {formatDate(selectedCategory.lastUsedAt)}
                        </p>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm flex flex-col justify-between">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Controls
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          <a
                            href={`/categories/${selectedCategory.id}/edit/`}
                            className="rounded-lg bg-white px-2 py-1 text-[10px] font-bold text-slate-700 shadow-sm border border-slate-200 hover:bg-slate-50"
                          >
                            Edit
                          </a>
                          <button className="rounded-lg bg-white px-2 py-1 text-[10px] font-bold text-slate-700 shadow-sm border border-slate-200 hover:bg-slate-50">
                            Map Tax
                          </button>
                          <button className="rounded-lg bg-rose-50 px-2 py-1 text-[10px] font-bold text-rose-700 hover:bg-rose-100 border border-rose-100">
                            Archive
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 text-xs font-medium text-slate-400 italic">
                    Select a category on the left to see details, mappings, and controls.
                  </p>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default CategoriesPage;
