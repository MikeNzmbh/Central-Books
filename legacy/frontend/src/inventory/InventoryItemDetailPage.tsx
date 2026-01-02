import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, PackagePlus, Send, SlidersHorizontal } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, Button } from "../components/ui";
import { usePermissions } from "../hooks/usePermissions";
import {
  listInventoryBalances,
  listInventoryEvents,
  listInventoryItems,
  listInventoryLocations,
  type InventoryBalance,
  type InventoryEvent,
  type InventoryItem,
  type InventoryLocation,
} from "./api";
import { AdjustStockSheet, ReceiveStockSheet, ShipStockSheet } from "./InventoryMovementSheets";

const parseNum = (value: any): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
};

const fmtQty = (value: number): string => {
  if (!Number.isFinite(value)) return "0.0000";
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
};

const fmtDateTime = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
};

function eventLabel(eventType: string): string {
  const t = (eventType || "").toUpperCase();
  if (t === "STOCK_RECEIVED") return "Received";
  if (t === "STOCK_SHIPPED") return "Shipped";
  if (t === "STOCK_ADJUSTED") return "Adjusted";
  if (t === "STOCK_COMMITTED") return "Reserved";
  if (t === "STOCK_UNCOMMITTED") return "Released";
  if (t === "PO_CREATED") return "PO created";
  if (t === "PO_UPDATED") return "PO updated";
  if (t === "PO_CANCELLED") return "PO cancelled";
  if (t === "STOCK_LANDED_COST_ALLOCATED") return "Landed cost (stub)";
  if (t === "VENDOR_BILL_POSTED") return "Vendor bill posted";
  return eventType;
}

type Totals = {
  onHand: number;
  committed: number;
  onOrder: number;
  available: number;
};

export const InventoryItemDetailPage: React.FC = () => {
  const { itemId } = useParams();
  const { workspace, can } = usePermissions();
  const workspaceId = workspace?.businessId ?? null;
  // TODO: Re-enable when permissions are fully set up
  // const canView = can("inventory.view", "view");
  // const canManage = can("inventory.manage", "edit");
  const canView = true;
  const canManage = true;

  const parsedItemId = Number(itemId);
  const [item, setItem] = useState<InventoryItem | null>(null);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [events, setEvents] = useState<InventoryEvent[]>([]);
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [receiveOpen, setReceiveOpen] = useState(false);
  const [shipOpen, setShipOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);

  const load = async () => {
    if (!workspaceId || !Number.isFinite(parsedItemId)) return;
    setLoading(true);
    setError(null);
    try {
      const [itemsRes, balancesRes, eventsRes, locationsRes] = await Promise.all([
        listInventoryItems(workspaceId),
        listInventoryBalances(workspaceId, { itemId: parsedItemId }),
        listInventoryEvents(workspaceId, { itemId: parsedItemId, limit: 150 }),
        listInventoryLocations(workspaceId),
      ]);
      setItem(itemsRes.find((it) => it.id === parsedItemId) || null);
      setBalances(balancesRes);
      setEvents(eventsRes);
      setLocations(locationsRes);
    } catch (e: any) {
      setError(e?.message || "Failed to load item");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, parsedItemId]);

  const totals: Totals = useMemo(() => {
    const out = { onHand: 0, committed: 0, onOrder: 0, available: 0 };
    for (const b of balances) {
      out.onHand += parseNum(b.qty_on_hand);
      out.committed += parseNum(b.qty_committed);
      out.onOrder += parseNum(b.qty_on_order);
      out.available += parseNum(b.qty_available);
    }
    return out;
  }, [balances]);

  const locationNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const l of locations) {
      map.set(l.id, l.code ? `${l.code} · ${l.name}` : l.name);
    }
    return map;
  }, [locations]);

  const defaultLocationId = balances[0]?.location ?? locations[0]?.id ?? null;

  if (!workspaceId) {
    return (
      <Card className="border-none bg-white/90 shadow-sm">
        <CardHeader>
          <CardTitle>No workspace</CardTitle>
          <CardDescription>Select a workspace to view inventory.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!canView) {
    return (
      <Card className="border-none bg-white/90 shadow-sm">
        <CardHeader>
          <CardTitle>Not authorized</CardTitle>
          <CardDescription>You don’t have permission to view inventory in this workspace.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!Number.isFinite(parsedItemId)) {
    return (
      <Card className="border-none bg-white/90 shadow-sm">
        <CardHeader>
          <CardTitle>Invalid item</CardTitle>
          <CardDescription>Item id is missing or invalid.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="min-h-screen w-full bg-slate-50/80 px-4 pb-12 pt-6 sm:px-6 lg:px-8 font-sans">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Link to="/" className="inline-flex items-center gap-2 hover:text-slate-900">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Link>
              <span className="text-slate-300">/</span>
              <span className="text-slate-500">Item detail</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              {item?.name || (loading ? "Loading…" : "Item not found")}
            </h1>
            <p className="text-sm text-slate-500">
              {item?.sku ? (
                <>
                  SKU <span className="font-mono text-xs text-slate-700">{item.sku}</span>
                  <span className="text-slate-300"> · </span>
                </>
              ) : null}
              Costing: <span className="font-medium text-slate-700">{(item?.costing_method || "—").toUpperCase()}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={load} disabled={loading}>
              Refresh
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Button>
            {canManage && (
              <>
                <Button onClick={() => setReceiveOpen(true)}>
                  <PackagePlus className="mr-2 h-4 w-4" />
                  Receive
                </Button>
                <Button variant="secondary" onClick={() => setShipOpen(true)}>
                  <Send className="mr-2 h-4 w-4" />
                  Ship
                </Button>
                <Button variant="outline" onClick={() => setAdjustOpen(true)}>
                  <SlidersHorizontal className="mr-2 h-4 w-4" />
                  Adjust
                </Button>
              </>
            )}
          </div>
        </header>

        {error && (
          <Card className="border border-rose-100 bg-rose-50 shadow-sm">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm text-rose-700 font-medium">{error}</div>
                <button
                  className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-medium text-white hover:bg-rose-700"
                  onClick={load}
                >
                  Retry
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="border border-slate-200 bg-white/90 shadow-sm">
            <CardHeader className="pb-2">
              <CardDescription>On hand</CardDescription>
              <CardTitle className="text-2xl">{fmtQty(totals.onHand)}</CardTitle>
            </CardHeader>
          </Card>
          <Card className="border border-slate-200 bg-white/90 shadow-sm">
            <CardHeader className="pb-2">
              <CardDescription>Available</CardDescription>
              <CardTitle className="text-2xl">{fmtQty(totals.available)}</CardTitle>
            </CardHeader>
          </Card>
          <Card className="border border-slate-200 bg-white/90 shadow-sm">
            <CardHeader className="pb-2">
              <CardDescription>Committed</CardDescription>
              <CardTitle className="text-2xl">{fmtQty(totals.committed)}</CardTitle>
            </CardHeader>
          </Card>
          <Card className="border border-slate-200 bg-white/90 shadow-sm">
            <CardHeader className="pb-2">
              <CardDescription>On order</CardDescription>
              <CardTitle className="text-2xl">{fmtQty(totals.onOrder)}</CardTitle>
            </CardHeader>
          </Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <Card className="border border-slate-200 bg-white/90 shadow-sm">
            <CardHeader>
              <CardTitle>Balances</CardTitle>
              <CardDescription>Per location snapshot (projection).</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-slate-500 border-b border-slate-200">
                      <th className="py-3 text-left font-semibold">Location</th>
                      <th className="py-3 text-right font-semibold">On hand</th>
                      <th className="py-3 text-right font-semibold">Available</th>
                      <th className="py-3 text-right font-semibold">Committed</th>
                      <th className="py-3 text-right font-semibold">On order</th>
                    </tr>
                  </thead>
                  <tbody>
                    {balances.map((b) => (
                      <tr key={b.id} className="border-b border-slate-100">
                        <td className="py-3 pr-3 text-slate-900 font-medium">
                          {locationNameById.get(b.location) || `Location #${b.location}`}
                        </td>
                        <td className="py-3 text-right font-mono-soft text-slate-900">{fmtQty(parseNum(b.qty_on_hand))}</td>
                        <td className="py-3 text-right font-mono-soft text-slate-900">{fmtQty(parseNum(b.qty_available))}</td>
                        <td className="py-3 text-right font-mono-soft text-slate-700">{fmtQty(parseNum(b.qty_committed))}</td>
                        <td className="py-3 text-right font-mono-soft text-slate-700">{fmtQty(parseNum(b.qty_on_order))}</td>
                      </tr>
                    ))}
                    {!loading && balances.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-10 text-center text-sm text-slate-500">
                          No balances yet. Receive stock to create the first event.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-slate-200 bg-white/90 shadow-sm">
            <CardHeader>
              <CardTitle>Recent events</CardTitle>
              <CardDescription>Append-only event stream (most recent first).</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-2">
                {events.map((e) => {
                  const qty = parseNum(e.quantity_delta);
                  const qtyTone = qty >= 0 ? "text-emerald-700" : "text-rose-700";
                  const ref = (e.source_reference || "").trim();
                  const reason = (e.metadata || {})["reason_code"];
                  return (
                    <div key={e.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-slate-900 truncate">{eventLabel(e.event_type)}</div>
                          <div className="text-xs text-slate-500 mt-0.5">
                            {fmtDateTime(e.created_at)}
                            {ref ? (
                              <>
                                <span className="text-slate-300"> · </span>
                                <span className="font-mono">{ref}</span>
                              </>
                            ) : null}
                            {reason ? (
                              <>
                                <span className="text-slate-300"> · </span>
                                <span className="font-mono">{String(reason)}</span>
                              </>
                            ) : null}
                          </div>
                        </div>
                        <div className={`shrink-0 font-mono-soft font-semibold ${qtyTone}`}>{qty >= 0 ? "+" : ""}{fmtQty(qty)}</div>
                      </div>
                    </div>
                  );
                })}
                {!loading && events.length === 0 && (
                  <div className="py-10 text-center text-sm text-slate-500">No events yet.</div>
                )}
              </div>
            </CardContent>
          </Card>
        </section>

        {canManage && (
          <>
            <ReceiveStockSheet
              open={receiveOpen}
              onOpenChange={setReceiveOpen}
              workspaceId={workspaceId}
              itemId={parsedItemId}
              locations={locations}
              defaultLocationId={defaultLocationId}
              onCompleted={load}
            />
            <ShipStockSheet
              open={shipOpen}
              onOpenChange={setShipOpen}
              workspaceId={workspaceId}
              itemId={parsedItemId}
              locations={locations}
              defaultLocationId={defaultLocationId}
              onCompleted={load}
            />
            <AdjustStockSheet
              open={adjustOpen}
              onOpenChange={setAdjustOpen}
              workspaceId={workspaceId}
              itemId={parsedItemId}
              locations={locations}
              defaultLocationId={defaultLocationId}
              onCompleted={load}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default InventoryItemDetailPage;

