import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.accounting_defaults import ensure_default_accounts
from core.models import Account, Business, JournalEntry
from inventory.accounts import (
    COGS_CODE,
    GRNI_CODE,
    INVENTORY_ASSET_CODE,
    INVENTORY_VARIANCE_CODE,
    LANDED_COST_CLEARING_CODE,
)
from inventory.models import InventoryBalance, InventoryEvent, InventoryItem, InventoryLocation, LandedCostBatch, PurchaseDocumentReceiptLink
from inventory.services.billing import post_vendor_bill_against_receipts
from inventory.services.purchasing import record_po_created
from inventory.services.receiving import receive_stock
from inventory.services.shipping import ship_stock


User = get_user_model()


class InventoryV11Tests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="invuser11",
            email="inv11@example.com",
            password="testpass123",
        )
        self.workspace = Business.objects.create(
            name="Inventory v1.1 Co",
            owner_user=self.user,
            currency="USD",
        )
        self.user.current_business = self.workspace
        self.user.save()
        self.client.login(username="invuser11", password="testpass123")

        ensure_default_accounts(self.workspace)
        self.asset_account = Account.objects.get(business=self.workspace, code=INVENTORY_ASSET_CODE)
        self.cogs_account = Account.objects.get(business=self.workspace, code=COGS_CODE)
        self.grni_account = Account.objects.get(business=self.workspace, code=GRNI_CODE)
        self.variance_account = Account.objects.get(business=self.workspace, code=INVENTORY_VARIANCE_CODE)
        self.landed_clearing = Account.objects.get(business=self.workspace, code=LANDED_COST_CLEARING_CODE)

        self.location = InventoryLocation.objects.create(
            workspace=self.workspace,
            name="Main Warehouse",
            code="MAIN",
            location_type=InventoryLocation.LocationType.SITE,
        )
        self.item = InventoryItem.objects.create(
            workspace=self.workspace,
            name="Widget",
            sku="W-001",
            item_type=InventoryItem.ItemType.INVENTORY,
            costing_method=InventoryItem.CostingMethod.FIFO,
            asset_account=self.asset_account,
            cogs_account=self.cogs_account,
        )

    def test_grni_bill_post_all_on_hand_adjusts_inventory_asset(self):
        receipt_event, _receipt_je = receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-1",
            created_by=self.user,
        )

        bill_doc, bill_je = post_vendor_bill_against_receipts(
            workspace=self.workspace,
            bill_reference="BILL-1",
            receipt_event_ids=[receipt_event.id],
            bill_total=Decimal("25.0000"),
            created_by=self.user,
        )

        self.assertEqual(bill_doc.document_type, "BILL")
        self.assertTrue(PurchaseDocumentReceiptLink.objects.filter(bill=bill_doc, receipt_event=receipt_event).exists())

        lines = list(bill_je.lines.select_related("account").order_by("id"))
        self.assertEqual(len(lines), 3)
        # Dr GRNI 20
        self.assertEqual(lines[0].account_id, self.grni_account.id)
        self.assertEqual(lines[0].debit, Decimal("20.0000"))
        # Dr Inventory Asset 5 (revaluation)
        self.assertEqual(lines[1].account_id, self.asset_account.id)
        self.assertEqual(lines[1].debit, Decimal("5.0000"))
        # Cr AP 25
        self.assertEqual(lines[2].account.code, "2000")
        self.assertEqual(lines[2].credit, Decimal("25.0000"))

    def test_grni_bill_post_some_consumed_books_variance(self):
        receipt_event, _ = receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-2",
            created_by=self.user,
        )
        ship_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("5.0000"),
            so_reference="SO-1",
            created_by=self.user,
        )

        _bill_doc, bill_je = post_vendor_bill_against_receipts(
            workspace=self.workspace,
            bill_reference="BILL-2",
            receipt_event_ids=[receipt_event.id],
            bill_total=Decimal("25.0000"),
            created_by=self.user,
        )

        lines = list(bill_je.lines.select_related("account").order_by("id"))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].account_id, self.grni_account.id)
        self.assertEqual(lines[0].debit, Decimal("20.0000"))
        self.assertEqual(lines[1].account_id, self.variance_account.id)
        self.assertEqual(lines[1].debit, Decimal("5.0000"))
        self.assertEqual(lines[2].account.code, "2000")
        self.assertEqual(lines[2].credit, Decimal("25.0000"))

    def test_po_created_increases_on_order_and_receipt_decreases(self):
        record_po_created(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            po_reference="PO-ONORDER",
            created_by=self.user,
        )
        bal = InventoryBalance.objects.get(workspace=self.workspace, item=self.item, location=self.location)
        self.assertEqual(bal.qty_on_order, Decimal("10.0000"))
        self.assertEqual(bal.qty_on_hand, Decimal("0.0000"))

        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("6.0000"),
            unit_cost=Decimal("1.0000"),
            po_reference="PO-ONORDER",
            created_by=self.user,
        )
        bal.refresh_from_db()
        self.assertEqual(bal.qty_on_order, Decimal("4.0000"))
        self.assertEqual(bal.qty_on_hand, Decimal("6.0000"))
        self.assertEqual(bal.qty_available, Decimal("6.0000"))

    def test_reserve_and_release_endpoints_update_committed(self):
        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("5.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-R",
            created_by=self.user,
        )

        reserve_res = self.client.post(
            reverse("inventory:reserve"),
            data={
                "workspace_id": self.workspace.id,
                "item_id": self.item.id,
                "location_id": self.location.id,
                "quantity": "3.0000",
                "reference": "SO-123",
            },
        )
        self.assertEqual(reserve_res.status_code, 201)
        bal = InventoryBalance.objects.get(workspace=self.workspace, item=self.item, location=self.location)
        self.assertEqual(bal.qty_committed, Decimal("3.0000"))
        self.assertEqual(bal.qty_available, Decimal("2.0000"))

        release_res = self.client.post(
            reverse("inventory:release"),
            data={
                "workspace_id": self.workspace.id,
                "item_id": self.item.id,
                "location_id": self.location.id,
                "quantity": "2.0000",
                "reference": "SO-123",
            },
        )
        self.assertEqual(release_res.status_code, 201)
        bal.refresh_from_db()
        self.assertEqual(bal.qty_committed, Decimal("1.0000"))
        self.assertEqual(bal.qty_available, Decimal("4.0000"))

        reserve_fail = self.client.post(
            reverse("inventory:reserve"),
            data={
                "workspace_id": self.workspace.id,
                "item_id": self.item.id,
                "location_id": self.location.id,
                "quantity": "10.0000",
                "reference": "SO-999",
            },
        )
        self.assertEqual(reserve_fail.status_code, 400)

    def test_landed_cost_skeleton_api_create_and_apply(self):
        receipt_event, _ = receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-LC",
            created_by=self.user,
        )

        payload = {
            "workspace_id": self.workspace.id,
            "description": "Freight for PO-LC",
            "allocation_method": "manual",
            "total_extra_cost": "5.0000",
            "allocations": [
                {"receipt_event_id": receipt_event.id, "allocated_amount": "5.0000"},
            ],
        }
        create_res = self.client.post(
            reverse("inventory:landed_cost_batches"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(create_res.status_code, 201)
        batch_id = create_res.json()["id"]
        batch = LandedCostBatch.objects.get(id=batch_id, workspace=self.workspace)
        self.assertEqual(batch.status, LandedCostBatch.Status.DRAFT)

        apply_res = self.client.post(
            reverse("inventory:landed_cost_apply", kwargs={"pk": batch.id}),
            data=json.dumps({"workspace_id": self.workspace.id}),
            content_type="application/json",
        )
        self.assertEqual(apply_res.status_code, 201)
        journal_entry_id = apply_res.json()["journal_entry_id"]
        je = JournalEntry.objects.get(id=journal_entry_id, business=self.workspace)
        lines = list(je.lines.select_related("account").order_by("id"))
        self.assertEqual(lines[0].account_id, self.asset_account.id)
        self.assertEqual(lines[0].debit, Decimal("5.0000"))
        self.assertEqual(lines[1].account_id, self.landed_clearing.id)
        self.assertEqual(lines[1].credit, Decimal("5.0000"))

        self.assertTrue(
            InventoryEvent.objects.filter(
                workspace=self.workspace,
                event_type=InventoryEvent.EventType.STOCK_LANDED_COST_ALLOCATED,
                metadata__landed_cost_batch_id=batch.id,
            ).exists()
        )

        batch.refresh_from_db()
        self.assertEqual(batch.status, LandedCostBatch.Status.APPLIED)

