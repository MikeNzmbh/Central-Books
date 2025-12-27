from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.accounting_defaults import ensure_default_accounts
from core.models import Account, Business, JournalEntry
from inventory.accounts import COGS_CODE, GRNI_CODE, INVENTORY_ASSET_CODE, INVENTORY_SHRINKAGE_CODE
from inventory.models import InventoryBalance, InventoryEvent, InventoryItem, InventoryLocation
from inventory.services.adjustments import adjust_stock_to_physical_count
from inventory.services.receiving import receive_stock
from inventory.services.shipping import ship_stock


User = get_user_model()


class InventoryV1Tests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="invuser",
            email="inv@example.com",
            password="testpass123",
        )
        self.workspace = Business.objects.create(
            name="Inventory Co",
            owner_user=self.user,
            currency="USD",
        )
        self.user.current_business = self.workspace
        self.user.save()
        self.client.login(username="invuser", password="testpass123")

        ensure_default_accounts(self.workspace)
        self.asset_account = Account.objects.get(business=self.workspace, code=INVENTORY_ASSET_CODE)
        self.cogs_account = Account.objects.get(business=self.workspace, code=COGS_CODE)

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

    def test_create_inventory_item_and_location(self):
        self.assertEqual(self.item.workspace_id, self.workspace.id)
        self.assertEqual(self.location.workspace_id, self.workspace.id)

    def test_receive_stock_creates_event_balance_and_gl(self):
        event, je = receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("2.5000"),
            po_reference="PO-1",
            created_by=self.user,
            actor_type="human",
            actor_id=str(self.user.id),
        )
        self.assertEqual(event.event_type, InventoryEvent.EventType.STOCK_RECEIVED)
        self.assertEqual(event.quantity_delta, Decimal("10.0000"))
        self.assertEqual(event.unit_cost, Decimal("2.5000"))
        self.assertEqual(event.source_reference, "PO-1")

        bal = InventoryBalance.objects.get(workspace=self.workspace, item=self.item, location=self.location)
        self.assertEqual(bal.qty_on_hand, Decimal("10.0000"))
        self.assertEqual(bal.qty_committed, Decimal("0.0000"))
        self.assertEqual(bal.qty_available, Decimal("10.0000"))

        lines = list(je.lines.select_related("account").order_by("id"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].account_id, self.asset_account.id)
        self.assertEqual(lines[0].debit, Decimal("25.0000"))
        self.assertEqual(lines[1].account.code, GRNI_CODE)
        self.assertEqual(lines[1].credit, Decimal("25.0000"))

    def test_ship_stock_blocks_negative_inventory(self):
        with self.assertRaisesMessage(Exception, "Insufficient stock to fulfill shipment."):
            ship_stock(
                workspace=self.workspace,
                item=self.item,
                location=self.location,
                quantity=Decimal("1.0000"),
                so_reference="SO-1",
                created_by=self.user,
            )

    def test_ship_stock_fifo_costing_and_gl(self):
        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-1",
            created_by=self.user,
        )
        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("3.0000"),
            po_reference="PO-2",
            created_by=self.user,
        )

        event, je = ship_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("15.0000"),
            so_reference="SO-1",
            created_by=self.user,
        )
        self.assertEqual(event.event_type, InventoryEvent.EventType.STOCK_SHIPPED)
        self.assertEqual(event.quantity_delta, Decimal("-15.0000"))

        bal = InventoryBalance.objects.get(workspace=self.workspace, item=self.item, location=self.location)
        self.assertEqual(bal.qty_on_hand, Decimal("5.0000"))

        lines = list(je.lines.select_related("account").order_by("id"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].account_id, self.cogs_account.id)
        self.assertEqual(lines[0].debit, Decimal("35.0000"))
        self.assertEqual(lines[1].account_id, self.asset_account.id)
        self.assertEqual(lines[1].credit, Decimal("35.0000"))

    def test_adjust_stock_shrinkage_and_gain_posts_gl(self):
        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("5.0000"),
            po_reference="PO-1",
            created_by=self.user,
        )

        event, je = adjust_stock_to_physical_count(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            physical_qty=Decimal("6.0000"),
            reason_code="COUNT",
            created_by=self.user,
        )
        self.assertEqual(event.event_type, InventoryEvent.EventType.STOCK_ADJUSTED)
        self.assertEqual(event.quantity_delta, Decimal("-4.0000"))

        shrinkage = Account.objects.get(business=self.workspace, code=INVENTORY_SHRINKAGE_CODE)
        lines = list(je.lines.select_related("account").order_by("id"))
        self.assertEqual(lines[0].account_id, shrinkage.id)
        self.assertEqual(lines[0].debit, Decimal("20.0000"))
        self.assertEqual(lines[1].account_id, self.asset_account.id)
        self.assertEqual(lines[1].credit, Decimal("20.0000"))

        event2, je2 = adjust_stock_to_physical_count(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            physical_qty=Decimal("8.0000"),
            reason_code="COUNT",
            created_by=self.user,
        )
        self.assertEqual(event2.quantity_delta, Decimal("2.0000"))
        lines2 = list(je2.lines.select_related("account").order_by("id"))
        self.assertEqual(lines2[0].account_id, self.asset_account.id)
        self.assertEqual(lines2[0].debit, Decimal("10.0000"))
        self.assertEqual(lines2[1].account_id, shrinkage.id)
        self.assertEqual(lines2[1].credit, Decimal("10.0000"))

    def test_inventory_api_receive_and_ship_end_to_end(self):
        receive_res = self.client.post(
            reverse("inventory:receive"),
            data={
                "workspace_id": self.workspace.id,
                "item_id": self.item.id,
                "location_id": self.location.id,
                "quantity": "5.0000",
                "unit_cost": "4.0000",
                "po_reference": "PO-API",
            },
        )
        self.assertEqual(receive_res.status_code, 201)
        event_id = receive_res.json()["event_id"]
        self.assertTrue(InventoryEvent.objects.filter(id=event_id, workspace=self.workspace).exists())

        ship_res = self.client.post(
            reverse("inventory:ship"),
            data={
                "workspace_id": self.workspace.id,
                "item_id": self.item.id,
                "location_id": self.location.id,
                "quantity": "2.0000",
                "so_reference": "SO-API",
            },
        )
        self.assertEqual(ship_res.status_code, 201)
        journal_entry_id = ship_res.json()["journal_entry_id"]
        self.assertTrue(JournalEntry.objects.filter(id=journal_entry_id, business=self.workspace).exists())

    def test_inventory_api_events_and_locations_endpoints(self):
        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("3.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-EVENTS",
            created_by=self.user,
        )
        ship_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("1.0000"),
            so_reference="SO-EVENTS",
            created_by=self.user,
        )

        loc_res = self.client.get(
            reverse("inventory:locations"),
            data={"workspace_id": self.workspace.id},
        )
        self.assertEqual(loc_res.status_code, 200)
        locations = loc_res.json().get("results") or []
        self.assertTrue(any(loc.get("id") == self.location.id for loc in locations))

        events_res = self.client.get(
            reverse("inventory:events"),
            data={"workspace_id": self.workspace.id, "item_id": self.item.id, "limit": 25},
        )
        self.assertEqual(events_res.status_code, 200)
        events = events_res.json().get("results") or []
        self.assertGreaterEqual(len(events), 2)
        self.assertTrue(all(ev.get("item") == self.item.id for ev in events))
        self.assertTrue(all(ev.get("workspace") == self.workspace.id for ev in events))

    def test_inventory_api_workspace_scoping_enforced(self):
        other_user = User.objects.create_user(username="other", email="other@example.com", password="pass12345")
        other_ws = Business.objects.create(name="Other Co", owner_user=other_user, currency="USD")
        ensure_default_accounts(other_ws)
        other_asset = Account.objects.get(business=other_ws, code=INVENTORY_ASSET_CODE)
        other_cogs = Account.objects.get(business=other_ws, code=COGS_CODE)
        other_loc = InventoryLocation.objects.create(workspace=other_ws, name="Other", code="O", location_type=InventoryLocation.LocationType.SITE)
        other_item = InventoryItem.objects.create(
            workspace=other_ws,
            name="OtherWidget",
            sku="O-1",
            item_type=InventoryItem.ItemType.INVENTORY,
            asset_account=other_asset,
            cogs_account=other_cogs,
        )

        res = self.client.post(
            reverse("inventory:receive"),
            data={
                "workspace_id": other_ws.id,
                "item_id": other_item.id,
                "location_id": other_loc.id,
                "quantity": "1.0000",
                "unit_cost": "1.0000",
            },
        )
        self.assertEqual(res.status_code, 403)

        events_res = self.client.get(
            reverse("inventory:events"),
            data={"workspace_id": other_ws.id, "limit": 10},
        )
        self.assertEqual(events_res.status_code, 403)

        loc_res = self.client.get(
            reverse("inventory:locations"),
            data={"workspace_id": other_ws.id},
        )
        self.assertEqual(loc_res.status_code, 403)
