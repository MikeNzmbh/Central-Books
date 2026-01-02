import React, { useEffect, useMemo, useState } from "react";
import {
  Button,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../components/ui";
import type { InventoryLocation } from "./api";
import { adjustInventory, receiveInventory, shipInventory } from "./api";

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaceId: number;
  itemId: number;
  locations: InventoryLocation[];
  defaultLocationId?: number | null;
  onCompleted: () => void;
};

const parsePositive = (value: string): number => {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return n;
};

const LocationSelect: React.FC<{
  locations: InventoryLocation[];
  value: string;
  onChange: (value: string) => void;
}> = ({ locations, value, onChange }) => {
  const options = useMemo(() => {
    return locations.map((l) => ({
      id: String(l.id),
      label: l.code ? `${l.code} · ${l.name}` : l.name,
    }));
  }, [locations]);

  return (
    <Select value={value} onValueChange={onChange} disabled={locations.length === 0}>
      <SelectTrigger>
        <SelectValue placeholder={locations.length ? "Select a location" : "No locations available"} />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.id} value={opt.id}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export const ReceiveStockSheet: React.FC<SheetProps> = ({
  open,
  onOpenChange,
  workspaceId,
  itemId,
  locations,
  defaultLocationId,
  onCompleted,
}) => {
  const [locationId, setLocationId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [unitCost, setUnitCost] = useState<string>("");
  const [poReference, setPoReference] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setQuantity("");
    setUnitCost("");
    setPoReference("");
    const preferred = defaultLocationId ? String(defaultLocationId) : locations[0]?.id ? String(locations[0].id) : "";
    setLocationId(preferred);
  }, [open, defaultLocationId, locations]);

  const canSubmit =
    !!locationId && parsePositive(quantity) > 0 && parsePositive(unitCost) > 0 && locations.length > 0 && !saving;

  const onSubmit = async () => {
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      await receiveInventory({
        workspace_id: workspaceId,
        item_id: itemId,
        location_id: Number(locationId),
        quantity,
        unit_cost: unitCost,
        po_reference: poReference || undefined,
      });
      onOpenChange(false);
      onCompleted();
    } catch (e: any) {
      setError(e?.message || "Failed to receive stock");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Receive stock</SheetTitle>
          <SheetDescription>Add inventory into a warehouse location and post to GRNI.</SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Location</div>
            <LocationSelect locations={locations} value={locationId} onChange={setLocationId} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Quantity</div>
            <Input inputMode="decimal" placeholder="e.g. 10" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Unit cost</div>
            <Input inputMode="decimal" placeholder="e.g. 2.50" value={unitCost} onChange={(e) => setUnitCost(e.target.value)} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">PO reference (optional)</div>
            <Input placeholder="e.g. PO-123" value={poReference} onChange={(e) => setPoReference(e.target.value)} />
          </div>

          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-md p-2">{error}</div>}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={onSubmit} disabled={!canSubmit}>
              {saving ? "Receiving…" : "Receive"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export const ShipStockSheet: React.FC<SheetProps> = ({
  open,
  onOpenChange,
  workspaceId,
  itemId,
  locations,
  defaultLocationId,
  onCompleted,
}) => {
  const [locationId, setLocationId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const [soReference, setSoReference] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setQuantity("");
    setSoReference("");
    const preferred = defaultLocationId ? String(defaultLocationId) : locations[0]?.id ? String(locations[0].id) : "";
    setLocationId(preferred);
  }, [open, defaultLocationId, locations]);

  const canSubmit = !!locationId && parsePositive(quantity) > 0 && locations.length > 0 && !saving;

  const onSubmit = async () => {
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      await shipInventory({
        workspace_id: workspaceId,
        item_id: itemId,
        location_id: Number(locationId),
        quantity,
        so_reference: soReference || undefined,
      });
      onOpenChange(false);
      onCompleted();
    } catch (e: any) {
      setError(e?.message || "Failed to ship stock");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Ship stock</SheetTitle>
          <SheetDescription>Reduce on-hand inventory and post COGS.</SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Location</div>
            <LocationSelect locations={locations} value={locationId} onChange={setLocationId} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Quantity</div>
            <Input inputMode="decimal" placeholder="e.g. 5" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">SO reference (optional)</div>
            <Input placeholder="e.g. SO-123" value={soReference} onChange={(e) => setSoReference(e.target.value)} />
          </div>

          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-md p-2">{error}</div>}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={onSubmit} disabled={!canSubmit}>
              {saving ? "Shipping…" : "Ship"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export const AdjustStockSheet: React.FC<SheetProps> = ({
  open,
  onOpenChange,
  workspaceId,
  itemId,
  locations,
  defaultLocationId,
  onCompleted,
}) => {
  const [locationId, setLocationId] = useState<string>("");
  const [physicalQty, setPhysicalQty] = useState<string>("");
  const [reasonCode, setReasonCode] = useState<string>("COUNT");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setPhysicalQty("");
    setReasonCode("COUNT");
    const preferred = defaultLocationId ? String(defaultLocationId) : locations[0]?.id ? String(locations[0].id) : "";
    setLocationId(preferred);
  }, [open, defaultLocationId, locations]);

  const canSubmit =
    !!locationId && parsePositive(physicalQty) >= 0 && reasonCode.trim().length > 0 && locations.length > 0 && !saving;

  const onSubmit = async () => {
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      await adjustInventory({
        workspace_id: workspaceId,
        item_id: itemId,
        location_id: Number(locationId),
        physical_qty: physicalQty,
        reason_code: reasonCode.trim(),
      });
      onOpenChange(false);
      onCompleted();
    } catch (e: any) {
      setError(e?.message || "Failed to adjust stock");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Adjust stock</SheetTitle>
          <SheetDescription>Set on-hand quantity to a physical count and post shrinkage/gain.</SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Location</div>
            <LocationSelect locations={locations} value={locationId} onChange={setLocationId} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Physical on-hand</div>
            <Input inputMode="decimal" placeholder="e.g. 42" value={physicalQty} onChange={(e) => setPhysicalQty(e.target.value)} />
          </div>

          <div>
            <div className="text-xs font-medium text-slate-700 mb-1">Reason code</div>
            <Input placeholder="e.g. COUNT" value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} />
          </div>

          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-md p-2">{error}</div>}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={onSubmit} disabled={!canSubmit}>
              {saving ? "Adjusting…" : "Adjust"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};

