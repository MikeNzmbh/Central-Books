from decimal import Decimal
from threading import Lock, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from core.accounting_defaults import ensure_default_accounts
from core.models import Account, Business
from inventory.accounts import COGS_CODE, INVENTORY_ASSET_CODE
from inventory.exceptions import DomainError
from inventory.models import InventoryBalance, InventoryItem, InventoryLocation
from inventory.services.receiving import receive_stock
from inventory.services.shipping import ship_stock


User = get_user_model()


class InventoryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="invconcurrency",
            email="invconcurrency@example.com",
            password="testpass123",
        )
        self.workspace = Business.objects.create(
            name="Inventory Concurrency Co",
            owner_user=self.user,
            currency="USD",
        )
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
            sku="W-CONC",
            item_type=InventoryItem.ItemType.INVENTORY,
            costing_method=InventoryItem.CostingMethod.FIFO,
            asset_account=self.asset_account,
            cogs_account=self.cogs_account,
        )

    def test_concurrent_shipments_do_not_allow_negative_on_hand(self):
        if connection.vendor == "sqlite":
            self.skipTest("SQLite locking makes this concurrency test flaky; run on Postgres/MySQL.")

        receive_stock(
            workspace=self.workspace,
            item=self.item,
            location=self.location,
            quantity=Decimal("100.0000"),
            unit_cost=Decimal("2.0000"),
            po_reference="PO-CONC",
            created_by=self.user,
        )

        successes: list[int] = []
        failures: list[str] = []
        lock = Lock()

        def worker(ix: int):
            close_old_connections()
            try:
                ship_stock(
                    workspace=self.workspace,
                    item=self.item,
                    location=self.location,
                    quantity=Decimal("20.0000"),
                    so_reference=f"SO-{ix}",
                    created_by=self.user,
                )
                with lock:
                    successes.append(ix)
            except DomainError as exc:
                with lock:
                    failures.append(str(exc))
            finally:
                close_old_connections()

        threads = [Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        bal = InventoryBalance.objects.get(workspace=self.workspace, item=self.item, location=self.location)
        self.assertGreaterEqual(bal.qty_on_hand, Decimal("0.0000"))
        self.assertLessEqual(len(successes), 5)
        self.assertEqual(bal.qty_on_hand, Decimal("100.0000") - Decimal("20.0000") * Decimal(len(successes)))
        self.assertEqual(len(successes) + len(failures), 10)

