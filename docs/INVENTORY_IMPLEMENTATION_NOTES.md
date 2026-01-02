# Inventory v1 – Implementation Notes

Inventory v1 is an event-sourced, ledger-based subsystem built around an append-only `InventoryEvent` stream (canonical) plus a denormalized `InventoryBalance` snapshot for fast reads. Costing is FIFO or weighted-average (AVCO). LIFO is intentionally not implemented.

## Data Model

- `inventory.InventoryItem`
  - Workspace-scoped catalog row (`workspace` → `core.Business`) with SKU uniqueness per workspace.
  - Item types: `inventory | non_inventory | service | bundle | assembly`
  - Costing method: `fifo | avco` (default `fifo`)
  - GL mappings:
    - `asset_account` (required for inventory/assembly)
    - `cogs_account` (required for inventory/assembly)
    - `revenue_account` (optional override)

- `inventory.InventoryLocation`
  - Workspace-scoped location tree (optional `parent`) supporting multiple warehouses/bins.
  - Types: `site | bin | in_transit`

- `inventory.InventoryEvent` (append-only)
  - Workspace + item + location scoped.
  - Event types:
    - `STOCK_RECEIVED`
    - `STOCK_SHIPPED`
    - `STOCK_COMMITTED`
    - `STOCK_UNCOMMITTED`
    - `STOCK_ADJUSTED`
    - `STOCK_TRANSFERRED` (stub)
    - `STOCK_LANDED_COST_ALLOCATED` (stub)
  - `quantity_delta` is the on-hand delta (signed).
  - `unit_cost` is required for `STOCK_RECEIVED` (DB constraint).
  - Commitment deltas are carried in `metadata.qty_committed_delta` and applied to the snapshot.

- `inventory.InventoryBalance` (snapshot)
  - Workspace + item + location unique row.
  - Tracks:
    - `qty_on_hand`
    - `qty_committed`
    - `qty_on_order`
    - `qty_available` (= on_hand − committed)
  - Updated transactionally whenever an `InventoryEvent` is appended.
  - DB constraints enforce non-negative `qty_on_hand`, `qty_committed`, and `qty_on_order`.

## System Accounts (COA)

Seeded via `core/accounting_defaults.py`:

- `1500` Inventory Asset (ASSET)
- `1510` Stock In Transit (ASSET, optional in v1)
- `2050` GRNI / Accrued Purchases (LIABILITY)
- `5020` Cost of Goods Sold (EXPENSE)
- `5030` Inventory Shrinkage / Adjustment (EXPENSE)
- `5040` Inventory Variance (EXPENSE, optional in v1)

## GL Posting Patterns (v1)

- Receive stock (`STOCK_RECEIVED`)
  - Debit: `item.asset_account`
  - Credit: GRNI (`2050`)
  - Amount: `quantity * unit_cost`

- Ship stock (`STOCK_SHIPPED`)
  - Debit: `item.cogs_account`
  - Credit: `item.asset_account`
  - Amount: computed COGS (FIFO/AVCO)

- Stocktake adjustment (`STOCK_ADJUSTED`)
  - Shrinkage (delta < 0):
    - Debit: Inventory Shrinkage (`5030`)
    - Credit: `item.asset_account`
  - Gain (delta > 0):
    - Debit: `item.asset_account`
    - Credit: Inventory Shrinkage (`5030`) (acts as “inventory gain” via credit)

- Vouchering (Phase 1 stub)
  - `inventory/services/vouchering.py:voucher_vendor_bill_against_grni`
  - Debit: GRNI (`2050`)
  - Credit: Accounts Payable (`2000`)
  - Optional: post differences to Inventory Variance (`5040`)

## v1.1 – GRNI Bill Matching

Implemented in `inventory/services/billing.py:post_vendor_bill_against_receipts`.

- Receipt-first flow (preferred):
  - Receipts post: Dr Inventory Asset / Cr GRNI.
  - Bill posting clears GRNI for the receipt value and posts AP for the bill amount.
- Purchase price variance (v1.1 simplification):
  - If **all linked receipt quantities are still on-hand**, the entire delta is applied as an **Inventory Asset revaluation**.
  - Otherwise, the entire delta is posted to **Inventory Variance** (`5040`).
- Receipts are linked to bills via `inventory.PurchaseDocumentReceiptLink` to keep the correlation durable for future PO/Bill modules.
- Bill-first flow (v1.1): explicitly disallowed by this service (requires `receipt_event_ids`).

## v1.1 – Inventory States (QOH / Committed / On Order)

Inventory snapshots track:

- `qty_on_hand`
- `qty_committed`
- `qty_on_order`
- `qty_available` (= on_hand − committed)

State transitions are driven by append-only events plus a projection update:

- PO events (`PO_CREATED`, `PO_UPDATED`, `PO_CANCELLED`) adjust `qty_on_order`.
- Receipts (`STOCK_RECEIVED`) increase on-hand and (when PO-linked) reduce on-order.
- Reservations (`STOCK_COMMITTED` / `STOCK_UNCOMMITTED`) adjust committed.
- Shipments (`STOCK_SHIPPED`) decrease on-hand and reduce committed (up to shipped quantity).

API additions (workspace-scoped) under `/api/inventory/`:

- `POST /api/inventory/reserve/`
- `POST /api/inventory/release/`

## v1.1 – Landed Cost (Skeleton)

Data model:

- `inventory.LandedCostBatch` (draft/applied/void)
- `inventory.LandedCostAllocation` (manual lines linking a batch to one or more `STOCK_RECEIVED` events)

Service:

- `inventory/services/landed_cost.py:create_landed_cost_batch` creates a draft batch + allocations.
- `inventory/services/landed_cost.py:apply_landed_cost` applies a batch:
  - Posts GL: Dr Inventory Asset / Cr Freight & Duties Clearing (`2060` by default, or batch `credit_account`).
  - Emits valuation-only inventory events: `STOCK_LANDED_COST_ALLOCATED` (quantity delta = 0).

This is intentionally a skeleton:

- Allocation is assumed to be manually provided and correct in v1.1.
- Costing engine does not yet incorporate landed-cost valuation events into FIFO/AVCO calculations.
- Future versions can:
  - allocate by value/weight/quantity
  - link landed cost to vendor bills directly
  - add Companion proposals for draft landed cost batches

## Costing Engine

Implemented in `inventory/costing.py`:

- FIFO: replays `InventoryEvent`s to build receipt layers and consumes them in order.
- AVCO: replays `InventoryEvent`s to compute on-hand value/qty and applies the rolling average.

## Negative Inventory Policy

- Canonical `qty_on_hand` is not allowed to go negative.
- `ship_stock` raises `DomainError("Insufficient stock to fulfill shipment.")` when on-hand is insufficient.
- No provisional/Shadow Ledger negative-inventory flows are implemented in v1.

## API (DRF) – Minimal v1

Workspace-scoped endpoints under `/api/inventory/`:

- `GET /api/inventory/items/?workspace_id=...`
- `POST /api/inventory/items/`
- `GET /api/inventory/balances/?workspace_id=...`
- `POST /api/inventory/receive/`
- `POST /api/inventory/ship/`
- `POST /api/inventory/adjust/`
