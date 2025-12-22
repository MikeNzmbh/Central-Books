from django.urls import path

from inventory.api_v1 import (
    InventoryAdjustView,
    InventoryBalancesView,
    InventoryEventsView,
    InventoryItemsView,
    InventoryLocationsView,
    InventoryReceiveView,
    InventoryReleaseView,
    InventoryReserveView,
    InventoryShipView,
    LandedCostApplyView,
    LandedCostBatchesView,
)


app_name = "inventory"

urlpatterns = [
    path("items/", InventoryItemsView.as_view(), name="items"),
    path("balances/", InventoryBalancesView.as_view(), name="balances"),
    path("locations/", InventoryLocationsView.as_view(), name="locations"),
    path("events/", InventoryEventsView.as_view(), name="events"),
    path("receive/", InventoryReceiveView.as_view(), name="receive"),
    path("ship/", InventoryShipView.as_view(), name="ship"),
    path("adjust/", InventoryAdjustView.as_view(), name="adjust"),
    path("reserve/", InventoryReserveView.as_view(), name="reserve"),
    path("release/", InventoryReleaseView.as_view(), name="release"),
    path("landed-cost/", LandedCostBatchesView.as_view(), name="landed_cost_batches"),
    path("landed-cost/<int:pk>/apply/", LandedCostApplyView.as_view(), name="landed_cost_apply"),
]
