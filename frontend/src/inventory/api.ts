import { ensureCsrfToken } from "../utils/csrf";

const BASE = "/api/inventory/";

export type InventoryItem = {
  id: number;
  workspace: number;
  name: string;
  sku: string;
  item_type: string;
  costing_method: string;
  default_uom: string;
  asset_account: number | null;
  cogs_account: number | null;
  revenue_account: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryLocation = {
  id: number;
  workspace: number;
  name: string;
  code: string;
  location_type: string;
  parent: number | null;
  created_at: string;
  updated_at: string;
};

export type InventoryBalance = {
  id: number;
  workspace: number;
  item: number;
  location: number;
  qty_on_hand: string;
  qty_committed: string;
  qty_on_order: string;
  qty_available: string;
  last_event: number | null;
  last_updated_at: string;
};

export type InventoryEvent = {
  id: number;
  workspace: number;
  item: number;
  location: number;
  event_type: string;
  quantity_delta: string;
  unit_cost: string | null;
  source_reference: string;
  purchase_document: number | null;
  batch_reference: string;
  metadata: Record<string, unknown>;
  actor_type: string;
  actor_id: string;
  created_by: number | null;
  created_at: string;
};

type ListResponse<T> = { results: T[] };

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    qs.set(key, String(value));
  }
  const query = qs.toString();
  return query ? `?${query}` : "";
}

async function parseError(res: Response): Promise<string> {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = await res.json().catch(() => ({}));
    const detail = (data && (data.detail || data.error || data.message)) as any;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return `Request failed (${res.status})`;
}

async function apiGet<T>(path: string, params: Record<string, any>): Promise<T> {
  const res = await fetch(`${BASE}${path}${buildQuery(params)}`, {
    method: "GET",
    credentials: "same-origin",
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return (await res.json()) as T;
}

async function apiPost<T>(path: string, body: Record<string, any>): Promise<T> {
  const csrf = await ensureCsrfToken();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRFToken": csrf } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return (await res.json()) as T;
}

export async function listInventoryItems(workspaceId: number): Promise<InventoryItem[]> {
  const data = await apiGet<ListResponse<InventoryItem>>("items/", { workspace_id: workspaceId });
  return data.results || [];
}

export async function listInventoryLocations(workspaceId: number): Promise<InventoryLocation[]> {
  const data = await apiGet<ListResponse<InventoryLocation>>("locations/", { workspace_id: workspaceId });
  return data.results || [];
}

export async function listInventoryBalances(
  workspaceId: number,
  opts: { itemId?: number; locationId?: number } = {},
): Promise<InventoryBalance[]> {
  const data = await apiGet<ListResponse<InventoryBalance>>("balances/", {
    workspace_id: workspaceId,
    item_id: opts.itemId,
    location_id: opts.locationId,
  });
  return data.results || [];
}

export async function listInventoryEvents(
  workspaceId: number,
  opts: { itemId?: number; locationId?: number; limit?: number } = {},
): Promise<InventoryEvent[]> {
  const data = await apiGet<ListResponse<InventoryEvent>>("events/", {
    workspace_id: workspaceId,
    item_id: opts.itemId,
    location_id: opts.locationId,
    limit: opts.limit,
  });
  return data.results || [];
}

export async function receiveInventory(payload: {
  workspace_id: number;
  item_id: number;
  location_id: number;
  quantity: string;
  unit_cost: string;
  po_reference?: string;
}): Promise<{ event_id: number; journal_entry_id: number }> {
  return apiPost("receive/", payload);
}

export async function shipInventory(payload: {
  workspace_id: number;
  item_id: number;
  location_id: number;
  quantity: string;
  so_reference?: string;
}): Promise<{ event_id: number; journal_entry_id: number }> {
  return apiPost("ship/", payload);
}

export async function adjustInventory(payload: {
  workspace_id: number;
  item_id: number;
  location_id: number;
  physical_qty: string;
  reason_code: string;
}): Promise<{ event_id: number; journal_entry_id: number } | { detail: string }> {
  return apiPost("adjust/", payload);
}

