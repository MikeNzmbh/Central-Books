import React, { useState, useEffect, useMemo } from "react";
import { Plus, Filter, Search, Tag, Package, Wrench, Archive, Sparkles, ArrowUpRight, Check } from "lucide-react";

// Shared types
export type ItemKind = "product" | "service";
export type ItemStatus = "active" | "archived";

export interface ProductServiceItem {
  id: number;
  name: string;
  code: string;
  sku: string;
  kind: ItemKind;
  status: ItemStatus;
  type: string;
  category?: string;
  unitLabel?: string;
  price: number;
  currency: string;
  incomeAccountLabel?: string;
  expenseAccountLabel?: string;
  lastSoldOn?: string;
  usageCount?: number;
  isRecurring?: boolean;
  description?: string;
}

interface Stats {
  activeCount: number;
  productCount: number;
  serviceCount: number;
  avgPrice: number;
}

function formatMoney(value: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-CA", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}

function kindIcon(kind: ItemKind) {
  if (kind === "product") return <Package className="h-3.5 w-3.5" />;
  return <Wrench className="h-3.5 w-3.5" />;
}

export default function ProductsPage() {
  const [items, setItems] = useState<ProductServiceItem[]>([]);
  const [stats, setStats] = useState<Stats>({ activeCount: 0, productCount: 0, serviceCount: 0, avgPrice: 0 });
  const [currency, setCurrency] = useState("CAD");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeKind, setActiveKind] = useState<ItemKind | "all">("all");
  const [statusFilter, setStatusFilter] = useState<ItemStatus | "all">("active");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeKind !== "all") params.set("kind", activeKind);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (search) params.set("q", search);

      const response = await fetch(`/api/products/list/?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch products");

      const json = await response.json();

      // Map API response to our interface
      const mappedItems: ProductServiceItem[] = (json.items || []).map((item: any) => ({
        id: item.id,
        name: item.name,
        code: item.code || item.sku || `ITEM-${item.id}`,
        sku: item.sku || "",
        kind: item.kind || (item.type === "PRODUCT" ? "product" : "service"),
        status: item.status || (item.is_archived ? "archived" : "active"),
        type: item.type,
        category: item.income_category_name || undefined,
        price: parseFloat(item.price) || 0,
        currency: json.currency || "CAD",
        incomeAccountLabel: item.income_account_label || undefined,
        expenseAccountLabel: item.expense_account_label || undefined,
        lastSoldOn: item.last_sold_on || undefined,
        usageCount: item.usage_count || 0,
        description: item.description || "",
      }));

      setItems(mappedItems);
      setStats({
        activeCount: json.stats?.active_count || 0,
        productCount: json.stats?.product_count || 0,
        serviceCount: json.stats?.service_count || 0,
        avgPrice: parseFloat(json.stats?.avg_price) || 0,
      });
      setCurrency(json.currency || "CAD");

      // Auto-select first item if none selected
      if (mappedItems.length > 0 && !selectedId) {
        setSelectedId(mappedItems[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeKind, statusFilter]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchData();
    }, 300);
    return () => clearTimeout(debounce);
  }, [search]);

  const selected = useMemo(
    () => items.find((it) => it.id === selectedId) ?? items[0] ?? null,
    [items, selectedId]
  );

  if (loading && items.length === 0) {
    return (
      <div className="min-h-screen w-full bg-slate-50/80 px-4 pb-12 pt-20 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-900 border-t-transparent" />
          <p className="text-sm text-slate-500">Loading products &amp; services...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full bg-slate-50/80 px-4 pb-12 pt-20 flex items-center justify-center">
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
    <div className="min-h-screen w-full bg-slate-50/80 px-4 pb-12 pt-6 sm:px-6 lg:px-8 font-sans">
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
              Catalog
            </div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">Products &amp; Services</h1>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white shadow-sm">
                <Sparkles className="h-2.5 w-2.5" />
                Live
              </span>
            </div>
            <p className="text-sm text-slate-500 max-w-xl leading-relaxed">
              Central place to manage what you sell, how you price it, and how it flows into your
              ledger and tax engine.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <a
              href="/items/new/?type=service"
              className="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-5 py-2.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <Wrench className="mr-2 h-3.5 w-3.5" />
              New Service
            </a>
            <a
              href="/items/new/?type=product"
              className="inline-flex items-center justify-center rounded-full bg-slate-900 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-slate-900/10 hover:bg-slate-800 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              <Plus className="mr-2 h-3.5 w-3.5" />
              New Product
            </a>
          </div>
        </header>

        {/* Metrics Cards */}
        <section className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-2 rounded-[1.5rem] border border-slate-100 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
              Active Items
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-slate-900 font-mono-soft tracking-tight">
                {stats.activeCount}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              {stats.productCount} products · {stats.serviceCount} services
            </p>
          </div>
          <div className="flex flex-col gap-2 rounded-[1.5rem] border border-slate-100 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
              Avg. Price
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-slate-900 font-mono-soft tracking-tight">
                {formatMoney(stats.avgPrice, currency)}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">Across all active items</p>
          </div>
          <div className="flex flex-col gap-2 rounded-[1.5rem] border border-slate-100 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
              Services
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-slate-900 font-mono-soft tracking-tight">
                {stats.serviceCount}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">Subscriptions or retainers</p>
          </div>
          <div className="flex flex-col gap-2 rounded-[1.5rem] border border-slate-100 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
              Catalog Health
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-100" />
              <span className="text-sm font-semibold text-emerald-700">Ready for invoicing</span>
            </div>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Accounts &amp; pricing set.
            </p>
          </div>
        </section>

        {/* Main Content */}
        <section className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)] xl:grid-cols-[minmax(0,2.5fr)_minmax(0,1.2fr)]">
          {/* Items List */}
          <div className="flex flex-col gap-5 rounded-[2rem] border border-slate-100 bg-white p-6 shadow-sm">
            {/* Filters */}
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2 rounded-xl bg-slate-50/50 p-1.5 ring-1 ring-slate-100">
                {(["all", "product", "service"] as const).map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    onClick={() => setActiveKind(kind)}
                    className={`rounded-lg px-4 py-1.5 text-xs font-semibold capitalize transition-all ${activeKind === kind
                      ? "bg-white text-slate-900 shadow-sm ring-1 ring-black/5"
                      : "text-slate-500 hover:text-slate-700 hover:bg-slate-100/50"
                      }`}
                  >
                    {kind === "all" ? "All Items" : `${kind}s`}
                  </button>
                ))}
              </div>

              <div className="flex flex-1 items-center justify-end gap-3">
                <div className="flex items-center rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600 shadow-sm">
                  <Filter className="mr-2 h-3.5 w-3.5 text-slate-400" />
                  <div className="flex gap-1">
                    {(["active", "archived"] as const).map((s) => (
                      <button
                        key={s}
                        onClick={() => setStatusFilter(s === statusFilter ? "all" : s)}
                        className={`rounded-lg px-2.5 py-1 capitalize transition-colors ${statusFilter === s
                          ? "bg-slate-100 text-slate-900 font-medium"
                          : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                          }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="relative w-full max-w-[260px]">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                    <Search className="h-4 w-4 text-slate-400" />
                  </div>
                  <input
                    type="text"
                    className="block w-full rounded-xl border border-slate-200 bg-white py-2 pl-10 pr-3 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-100 transition-shadow"
                    placeholder="Search name, SKU, category..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-hidden rounded-2xl border border-slate-100">
              <div className="hidden grid-cols-[minmax(0,2.5fr)_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.8fr)] bg-slate-50/80 px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 md:grid border-b border-slate-100">
                <div>Item Details</div>
                <div>Ledger Account</div>
                <div className="text-right">Price</div>
                <div className="text-right pr-2">Usage</div>
              </div>
              <div className="divide-y divide-slate-100 bg-white">
                {items.length === 0 ? (
                  <div className="px-6 py-16 text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-400">
                      <Search className="h-6 w-6" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-900">No items found</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      Try adjusting your filters or search query to find what you're looking for.
                    </p>
                    <a
                      href="/items/new/"
                      className="mt-4 inline-flex items-center rounded-lg bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800"
                    >
                      <Plus className="mr-1.5 h-3.5 w-3.5" />
                      Add your first item
                    </a>
                  </div>
                ) : null}
                {items.map((item) => {
                  const isSelected = selected?.id === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={`flex w-full flex-col gap-4 px-6 py-5 text-left transition-all md:grid md:grid-cols-[minmax(0,2.5fr)_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.8fr)] md:items-center md:gap-6 ${isSelected
                        ? "bg-slate-50 relative z-10 ring-1 ring-inset ring-slate-200"
                        : "hover:bg-slate-50/60"
                        }`}
                    >
                      {/* Item Details */}
                      <div className="flex items-start gap-4">
                        <div className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border text-slate-500 shadow-sm transition-colors ${isSelected ? "bg-white border-slate-200" : "bg-slate-50 border-slate-100"
                          }`}>
                          {kindIcon(item.kind)}
                        </div>
                        <div className="min-w-0 space-y-1.5">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-bold text-slate-900 leading-none">
                              {item.name}
                            </span>
                            {item.status === "archived" && (
                              <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-slate-500 border border-slate-200">
                                Archived
                              </span>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium text-slate-500">
                            <span className="flex items-center gap-1 rounded-md bg-slate-100/80 px-2 py-0.5 font-mono text-slate-600 border border-slate-200/50">
                              {item.code}
                            </span>
                            {item.category && (
                              <span className="flex items-center gap-1 text-slate-400">
                                <span className="h-0.5 w-0.5 rounded-full bg-slate-300" />
                                {item.category}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Ledger Account */}
                      <div className="flex flex-col gap-1.5">
                        <div className="text-[11px] font-medium text-slate-600 truncate flex items-center gap-1.5" title={item.incomeAccountLabel}>
                          <div className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                          {item.incomeAccountLabel || <span className="text-slate-400 italic">No account map</span>}
                        </div>
                      </div>

                      {/* Price */}
                      <div className="flex items-center justify-end md:block md:text-right">
                        <div className="text-sm font-bold text-slate-900 font-mono-soft">
                          {formatMoney(item.price, currency)}
                        </div>
                        {item.unitLabel && (
                          <div className="text-[10px] font-medium text-slate-400">
                            per {item.unitLabel}
                          </div>
                        )}
                      </div>

                      {/* Usage */}
                      <div className="flex items-center justify-end pr-2 md:block md:text-right">
                        <span className="text-xs font-semibold text-slate-700 font-mono-soft">
                          {item.usageCount || 0}
                        </span>
                        <div className="text-[10px] font-medium text-slate-400">uses</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Sidebar */}
          <aside className="flex flex-col gap-6">
            {/* Companion Panel */}
            <div className="relative rounded-[2rem] bg-white p-1.5 ring-1 ring-slate-200 shadow-[0_0_60px_-15px_rgba(99,102,241,0.15)]">
              <div className="relative z-10 flex flex-col gap-5 rounded-[1.7rem] border border-white/60 bg-white p-6">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-[10px] font-bold tracking-[0.2em] text-slate-400 uppercase">
                      Catalog Companion
                    </div>
                    <p className="mt-1 text-xs font-medium text-slate-600">
                      Pricing &amp; account signals.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900 transition-colors"
                  >
                    <ArrowUpRight className="h-4 w-4" />
                  </button>
                </div>

                {selected ? (
                  <div className="flex flex-col gap-5 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
                    <div className="flex items-start gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-sm font-bold text-white shadow-md">
                        {selected.name.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <h3 className="truncate text-sm font-bold text-slate-900">
                            {selected.name}
                          </h3>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] font-medium text-slate-500">
                          <span className="capitalize">{selected.kind}</span>
                          <span className="h-0.5 w-0.5 rounded-full bg-slate-300" />
                          <span>{selected.code}</span>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 py-4 border-y border-slate-50">
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Pricing</div>
                        <div className="mt-1 text-base font-bold text-slate-900 font-mono-soft">
                          {formatMoney(selected.price, currency)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Uses</div>
                        <div className="mt-1 text-sm font-medium text-slate-600">
                          {selected.usageCount || 0} invoices
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                          <span>Ledger Account</span>
                        </div>
                        <div className="text-xs font-medium text-slate-700 bg-slate-50 px-3 py-2 rounded-xl border border-slate-100 truncate flex items-center gap-2">
                          <div className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                          {selected.incomeAccountLabel || "Unmapped"}
                        </div>
                      </div>
                      {selected.expenseAccountLabel && (
                        <div>
                          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                            <span>Expense Account</span>
                          </div>
                          <div className="text-xs font-medium text-slate-700 bg-slate-50 px-3 py-2 rounded-xl border border-slate-100 truncate flex items-center gap-2">
                            <div className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                            {selected.expenseAccountLabel}
                          </div>
                        </div>
                      )}
                      {selected.category && (
                        <div>
                          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                            <span>Category</span>
                          </div>
                          <div className="inline-flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 border border-emerald-100 w-full">
                            <Check className="h-3.5 w-3.5" />
                            {selected.category}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="pt-2">
                      <a
                        href={`/items/${selected.id}/edit/`}
                        className="block w-full rounded-xl bg-slate-900 py-3 text-center text-xs font-bold text-white hover:bg-slate-800 transition-colors shadow-lg shadow-slate-900/10"
                      >
                        Edit Item Details
                      </a>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
                    <Tag className="mb-3 h-6 w-6 text-slate-300" />
                    <p className="text-xs font-medium text-slate-500">
                      Select an item to see details.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Tips */}
            <div className="rounded-[2rem] border border-slate-100 bg-white p-6 text-[11px] text-slate-600 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <span className="font-bold uppercase tracking-[0.15em] text-slate-400 text-[10px]">
                  Quick Tips
                </span>
                <Sparkles className="h-4 w-4 text-amber-400" />
              </div>
              <ul className="space-y-3">
                <li className="flex gap-3 items-start">
                  <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                  <span className="leading-relaxed">Link each item to an <strong>income account</strong> for accurate P&L tracking.</span>
                </li>
                <li className="flex gap-3 items-start">
                  <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                  <span className="leading-relaxed">Use clear SKUs to align invoices with inventory.</span>
                </li>
                <li className="flex gap-3 items-start">
                  <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                  <span className="leading-relaxed">Archive old items instead of deleting to preserve historical data.</span>
                </li>
              </ul>
            </div>
          </aside>
        </section>
      </div>
    </div>
  );
}
