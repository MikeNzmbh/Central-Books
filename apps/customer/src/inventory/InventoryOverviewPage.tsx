import React, { useMemo, useState } from "react";
import { Search, Plus, Package2, AlertTriangle, Warehouse, ArrowUpRight, Filter } from "lucide-react";

// NOTE:
// - TailwindCSS assumed to be available.
// - JetBrains Mono should be registered in your global CSS as `font-mono`.
// - Replace placeholder data + hooks with real API wiring when ready.

// -----------------------------
// Types
// -----------------------------

export type InventoryStatus = "in_stock" | "low_stock" | "out_of_stock" | "discontinued";

export interface InventoryItem {
  id: string;
  name: string;
  sku: string;
  category: string;
  status: InventoryStatus;
  onHand: number;
  committed: number;
  available: number;
  daysOfCover: number | null;
  locations: {
    name: string;
    onHand: number;
  }[];
  lastMovement: string; // e.g. "2025-12-20"
}

export interface InventoryOverviewStats {
  totalSkus: number;
  totalOnHandUnits: number;
  totalOnHandValue?: number; // optional until GL wiring is done
  lowStockCount: number;
  outOfStockCount: number;
  locationsCount: number;
}

interface InventoryOverviewData {
  stats: InventoryOverviewStats;
  items: InventoryItem[];
}

// -----------------------------
// Demo hook (replace with real API later)
// -----------------------------

function useInventoryOverviewDemo(): { data: InventoryOverviewData | null; isLoading: boolean } {
  const [isLoading] = useState(false);

  const data = useMemo<InventoryOverviewData>(() => {
    const items: InventoryItem[] = [
      {
        id: "1",
        name: "Blue Hoodie Premium",
        sku: "HD-BLUE-XS-2025",
        category: "Apparel",
        status: "in_stock",
        onHand: 128,
        committed: 34,
        available: 94,
        daysOfCover: 32,
        locations: [
          { name: "Main", onHand: 90 },
          { name: "Outlet", onHand: 38 },
        ],
        lastMovement: "2025-12-21",
      },
      {
        id: "2",
        name: "Black Hoodie Premium",
        sku: "HD-BLACK-M-2025",
        category: "Apparel",
        status: "low_stock",
        onHand: 22,
        committed: 18,
        available: 4,
        daysOfCover: 5,
        locations: [
          { name: "Main", onHand: 18 },
          { name: "Outlet", onHand: 4 },
        ],
        lastMovement: "2025-12-20",
      },
      {
        id: "3",
        name: "Everyday Notebook A5",
        sku: "NB-A5-GRID-001",
        category: "Stationery",
        status: "out_of_stock",
        onHand: 0,
        committed: 0,
        available: 0,
        daysOfCover: null,
        locations: [],
        lastMovement: "2025-12-12",
      },
      {
        id: "4",
        name: "Wireless Mouse Pro",
        sku: "MS-WL-PRO-2025",
        category: "Accessories",
        status: "in_stock",
        onHand: 64,
        committed: 9,
        available: 55,
        daysOfCover: 21,
        locations: [
          { name: "Main", onHand: 40 },
          { name: "Online", onHand: 24 },
        ],
        lastMovement: "2025-12-22",
      },
    ];

    const stats: InventoryOverviewStats = {
      totalSkus: items.length,
      totalOnHandUnits: items.reduce((acc, item) => acc + item.onHand, 0),
      totalOnHandValue: undefined,
      lowStockCount: items.filter((i) => i.status === "low_stock").length,
      outOfStockCount: items.filter((i) => i.status === "out_of_stock").length,
      locationsCount: new Set(items.flatMap((i) => i.locations.map((l) => l.name))).size,
    };

    return { stats, items };
  }, []);

  return { data, isLoading };
}

// -----------------------------
// Small UI helpers
// -----------------------------

function classNames(...values: (string | false | null | undefined)[]) {
  return values.filter(Boolean).join(" ");
}

function statusLabel(status: InventoryStatus): string {
  switch (status) {
    case "in_stock":
      return "In stock";
    case "low_stock":
      return "Low stock";
    case "out_of_stock":
      return "Out of stock";
    case "discontinued":
      return "Discontinued";
    default:
      return status;
  }
}

function statusToneClasses(status: InventoryStatus): string {
  switch (status) {
    case "in_stock":
      return "bg-emerald-50 text-emerald-700 border-emerald-100";
    case "low_stock":
      return "bg-amber-50 text-amber-700 border-amber-100";
    case "out_of_stock":
      return "bg-rose-50 text-rose-700 border-rose-100";
    case "discontinued":
      return "bg-slate-100 text-slate-600 border-slate-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

// -----------------------------
// Metric cards (top strip)
// -----------------------------

interface MetricCardProps {
  label: string;
  value: string;
  helper?: string;
  icon?: React.ReactNode;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, helper, icon }) => {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-slate-100 bg-slate-50/80 shadow-[0_16px_60px_rgba(15,23,42,0.06)]">
      {/* liquid metal background */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 opacity-70">
        <div className="absolute -top-16 -right-10 h-40 w-40 rounded-full bg-gradient-to-br from-slate-50 via-white to-slate-200 blur-2xl" />
        <div className="absolute -bottom-14 -left-20 h-40 w-40 rounded-full bg-gradient-to-tr from-white via-slate-50 to-slate-200 blur-2xl" />
      </div>

      <div className="relative flex h-full flex-col gap-2 p-5 md:p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
            {label}
          </p>
          {icon && (
            <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-white/70 shadow-[0_0_0_1px_rgba(148,163,184,0.25)]">
              {icon}
            </div>
          )}
        </div>

        <div className="mt-1 flex items-baseline justify-between gap-4">
          <p className="font-mono-soft text-2xl md:text-[28px] font-semibold tracking-tight text-slate-900">
            {value}
          </p>
        </div>

        {helper && (
          <p className="mt-1 text-xs text-slate-500">{helper}</p>
        )}
      </div>
    </div>
  );
};

// -----------------------------
// Main Page Component
// -----------------------------

const InventoryPage: React.FC = () => {
  const { data, isLoading } = useInventoryOverviewDemo();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<InventoryStatus | "all">("all");

  const selectedItem = useMemo(
    () => data?.items.find((i) => i.id === selectedId) ?? data?.items[0] ?? null,
    [data, selectedId]
  );

  const filteredItems = useMemo(() => {
    if (!data) return [];

    return data.items.filter((item) => {
      const matchesStatus =
        statusFilter === "all" ? true : item.status === statusFilter;
      const term = search.trim().toLowerCase();
      const matchesSearch =
        term.length === 0 ||
        item.name.toLowerCase().includes(term) ||
        item.sku.toLowerCase().includes(term) ||
        item.category.toLowerCase().includes(term);
      return matchesStatus && matchesSearch;
    });
  }, [data, search, statusFilter]);

  return (
    <div className="min-h-screen bg-[#f5f7fb] px-4 pb-10 pt-6 md:px-8 lg:px-12">
      {/* Page header */}
      <header className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
            Inventory
          </p>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
            Your stock is under control.
          </h1>
          <p className="text-sm text-slate-500">
            Live view of items, locations, and availability across your workspace.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50">
            <Filter className="h-3.5 w-3.5" />
            Saved views
          </button>
          <button className="inline-flex items-center gap-2 rounded-full border border-slate-900/90 bg-slate-900 px-4 py-2 text-xs font-medium text-slate-50 shadow-[0_14px_40px_rgba(15,23,42,0.45)] hover:bg-black">
            <Plus className="h-3.5 w-3.5" />
            Receive stock
          </button>
        </div>
      </header>

      {/* Top metrics row */}
      <section className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4 md:gap-5 xl:gap-6">
        <MetricCard
          label="Total SKUs"
          value={isLoading || !data ? "—" : data.stats.totalSkus.toString()}
          helper="Tracked inventory items in this workspace."
          icon={<Package2 className="h-4 w-4 text-slate-600" />}
        />
        <MetricCard
          label="On-hand units"
          value={
            isLoading || !data
              ? "—"
              : data.stats.totalOnHandUnits.toLocaleString()
          }
          helper="Physical units currently available across locations."
          icon={<Warehouse className="h-4 w-4 text-slate-600" />}
        />
        <MetricCard
          label="Low & out of stock"
          value={
            isLoading || !data
              ? "—"
              : `${data.stats.lowStockCount} low • ${data.stats.outOfStockCount} out`
          }
          helper="Items that may need reordering soon."
          icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
        />
        <MetricCard
          label="Locations"
          value={
            isLoading || !data
              ? "—"
              : data.stats.locationsCount.toString()
          }
          helper="Warehouses, stores, and virtual locations."
          icon={<ArrowUpRight className="h-4 w-4 text-slate-600" />}
        />
      </section>

      {/* Filters + layout */}
      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
        {/* Left: table */}
        <div className="rounded-3xl border border-slate-100 bg-white/80 shadow-[0_18px_55px_rgba(15,23,42,0.05)]">
          <div className="flex flex-col gap-4 border-b border-slate-100 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-slate-900 text-xs font-semibold text-slate-50">
                INV
              </div>
              <div>
                <p className="text-sm font-medium text-slate-900">Inventory items</p>
                <p className="text-xs text-slate-500">
                  Search, filter, and inspect items across all locations.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 rounded-full bg-slate-50 px-2 py-1 text-[11px] text-slate-500">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Live from ledger
              </div>
            </div>
          </div>

          {/* Controls */}
          <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-5">
            <div className="flex flex-1 items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
              <Search className="h-4 w-4 flex-none text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name, SKU, or category"
                className="w-full bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              {([
                ["all", "All"],
                ["in_stock", "In stock"],
                ["low_stock", "Low"],
                ["out_of_stock", "Out"],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setStatusFilter(value as InventoryStatus | "all")}
                  className={classNames(
                    "rounded-full border px-3 py-1 transition",
                    statusFilter === value
                      ? "border-slate-900 bg-slate-900 text-slate-50 shadow-[0_10px_26px_rgba(15,23,42,0.25)]"
                      : "border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full border-separate border-spacing-y-1 px-2 py-3 text-xs md:px-4">
              <thead>
                <tr className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                  <th className="px-3 py-2 text-left font-medium">Item</th>
                  <th className="px-3 py-2 text-left font-medium">SKU</th>
                  <th className="px-3 py-2 text-left font-medium">Category</th>
                  <th className="px-3 py-2 text-right font-medium">On hand</th>
                  <th className="px-3 py-2 text-right font-medium">Committed</th>
                  <th className="px-3 py-2 text-right font-medium">Available</th>
                  <th className="px-3 py-2 text-right font-medium">Days cover</th>
                  <th className="px-3 py-2 text-right font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {isLoading || !data ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-10 text-center text-xs text-slate-400">
                      Loading inventory…
                    </td>
                  </tr>
                ) : filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-10 text-center text-xs text-slate-400">
                      No items match this view.
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((item) => (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedId(item.id)}
                      className={classNames(
                        "cursor-pointer rounded-2xl bg-white align-middle shadow-[0_6px_20px_rgba(15,23,42,0.03)] transition",
                        "hover:-translate-y-0.5 hover:shadow-[0_10px_32px_rgba(15,23,42,0.10)]",
                        selectedItem?.id === item.id &&
                        "ring-1 ring-slate-900/5 ring-offset-1 ring-offset-slate-100"
                      )}
                    >
                      <td className="px-3 py-3 text-left">
                        <div className="flex flex-col">
                          <span className="text-[13px] font-medium text-slate-900">
                            {item.name}
                          </span>
                          <span className="mt-0.5 text-[11px] text-slate-400">
                            Last movement · {item.lastMovement}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-left">
                        <span className="font-mono text-[11px] text-slate-500">
                          {item.sku}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-left">
                        <span className="text-[11px] text-slate-500">{item.category}</span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-mono-soft text-xs text-slate-900">
                          {item.onHand.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-mono-soft text-xs text-slate-500">
                          {item.committed.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-mono-soft text-xs text-slate-900">
                          {item.available.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-mono-soft text-xs text-slate-500">
                          {item.daysOfCover ?? "—"}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span
                          className={classNames(
                            "inline-flex items-center justify-end gap-1 rounded-full border px-2.5 py-1 text-[11px]",
                            statusToneClasses(item.status)
                          )}
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-current/80" />
                          {statusLabel(item.status)}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: detail panel */}
        <aside className="flex flex-col gap-4 rounded-3xl border border-slate-100 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
                Snapshot
              </p>
              <h2 className="mt-1 text-sm font-semibold text-slate-900">
                {selectedItem ? selectedItem.name : "Select an item"}
              </h2>
              {selectedItem && (
                <p className="mt-1 text-[11px] text-slate-500">
                  {selectedItem.category} · SKU
                  <span className="font-mono"> {selectedItem.sku}</span>
                </p>
              )}
            </div>

            {selectedItem && (
              <span
                className={classNames(
                  "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px]",
                  statusToneClasses(selectedItem.status)
                )}
              >
                {statusLabel(selectedItem.status)}
              </span>
            )}
          </div>

          {selectedItem ? (
            <>
              <div className="grid grid-cols-3 gap-3 rounded-2xl bg-slate-50 p-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-400">
                    On hand
                  </p>
                  <p className="mt-1 font-mono-soft text-sm font-semibold text-slate-900">
                    {selectedItem.onHand.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-400">
                    Available
                  </p>
                  <p className="mt-1 font-mono-soft text-sm font-semibold text-slate-900">
                    {selectedItem.available.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-400">
                    Days cover
                  </p>
                  <p className="mt-1 font-mono-soft text-sm font-semibold text-slate-900">
                    {selectedItem.daysOfCover ?? "—"}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-[11px] font-medium text-slate-500">Location split</p>
                {selectedItem.locations.length === 0 ? (
                  <p className="text-[11px] text-slate-400">No active locations for this item.</p>
                ) : (
                  <div className="space-y-2">
                    {selectedItem.locations.map((loc) => {
                      const ratio = selectedItem.onHand
                        ? loc.onHand / selectedItem.onHand
                        : 0;
                      return (
                        <div key={loc.name} className="space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-slate-500">
                            <span>{loc.name}</span>
                            <span className="font-mono-soft text-slate-700">
                              {loc.onHand.toLocaleString()}
                            </span>
                          </div>
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full bg-slate-900/80"
                              style={{ width: `${Math.max(8, ratio * 100)}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="mt-1 space-y-1 text-[11px] text-slate-400">
                <p>Last movement · {selectedItem.lastMovement}</p>
                <p>Inventory v1 · Event-sourced, GL-linked.</p>
              </div>

              <div className="mt-2 flex flex-wrap gap-2">
                <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50">
                  <Plus className="h-3 w-3" /> Receive
                </button>
                <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50">
                  Adjust
                </button>
                <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50">
                  Movement log
                </button>
              </div>
            </>
          ) : (
            <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 p-5 text-center">
              <p className="text-sm font-medium text-slate-700">
                Select an item to see its inventory story.
              </p>
              <p className="mt-1 text-xs text-slate-400">
                You&apos;ll see locations, days of cover, and movement history here.
              </p>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
};

export default InventoryPage;
