from __future__ import annotations

from django.db import IntegrityError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions_engine import can
from inventory.exceptions import DomainError
from inventory.models import InventoryBalance, InventoryEvent, InventoryItem, InventoryLocation
from inventory.serializers import (
    InventoryAdjustSerializer,
    InventoryBalanceSerializer,
    InventoryEventSerializer,
    InventoryItemCreateSerializer,
    InventoryItemSerializer,
    InventoryLocationSerializer,
    InventoryReceiveSerializer,
    InventoryReleaseSerializer,
    InventoryReserveSerializer,
    InventoryShipSerializer,
    LandedCostBatchCreateSerializer,
    LandedCostBatchSerializer,
)
from inventory.services.adjustments import adjust_stock_to_physical_count
from inventory.services.commitment import commit_stock, uncommit_stock
from inventory.services.landed_cost import apply_landed_cost, create_landed_cost_batch
from inventory.services.receiving import receive_stock
from inventory.services.shipping import ship_stock


def _deny(message: str = "Permission denied"):
    return Response({"detail": message}, status=status.HTTP_403_FORBIDDEN)


def _resolve_workspace_from_request(request, *, require_explicit: bool = True):
    workspace_id = request.query_params.get("workspace_id")
    if workspace_id is None and request.method != "GET":
        try:
            workspace_id = (request.data or {}).get("workspace_id")
        except Exception:
            workspace_id = None

    if not workspace_id and require_explicit:
        return None, Response({"detail": "workspace_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    if workspace_id:
        try:
            workspace_id_int = int(workspace_id)
        except Exception:
            return None, Response({"detail": "Invalid workspace_id."}, status=status.HTTP_400_BAD_REQUEST)
        from core.models import Business

        workspace = Business.objects.filter(id=workspace_id_int).first()
        if not workspace:
            return None, Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        return workspace, None

    from core.utils import get_current_business

    workspace = get_current_business(request.user)
    if not workspace:
        return None, _deny("No active workspace.")
    return workspace, None


def _require(user, workspace, action: str, *, level: str = "view"):
    if not can(user, workspace, action, level=level):
        return _deny()
    return None


class InventoryItemsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        # TODO: Re-enable when permissions are fully set up
        # denied = _require(request.user, workspace, "inventory.view", level="view")
        # if denied:
        #     return denied

        items = InventoryItem.objects.filter(workspace=workspace).order_by("name", "sku", "id")
        return Response({"results": InventoryItemSerializer(items, many=True).data})

    def post(self, request):
        serializer = InventoryItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from core.models import Business

        workspace = Business.objects.get(id=serializer.validated_data["workspace_id"])
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        data = serializer.validated_data
        try:
            item = InventoryItem.objects.create(
                workspace=workspace,
                name=data["name"],
                sku=data["sku"],
                item_type=data["item_type"],
                costing_method=data.get("costing_method") or InventoryItem.CostingMethod.FIFO,
                default_uom=data.get("default_uom") or "",
                asset_account_id=data.get("asset_account_id"),
                cogs_account_id=data.get("cogs_account_id"),
                revenue_account_id=data.get("revenue_account_id"),
                is_active=data.get("is_active", True),
            )
        except IntegrityError:
            return Response({"detail": "SKU must be unique per workspace."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InventoryItemSerializer(item).data, status=status.HTTP_201_CREATED)


class InventoryBalancesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        # TODO: Re-enable when permissions are fully set up
        # denied = _require(request.user, workspace, "inventory.view", level="view")
        # if denied:
        #     return denied

        qs = InventoryBalance.objects.filter(workspace=workspace).select_related("item", "location")
        item_id = request.query_params.get("item_id")
        location_id = request.query_params.get("location_id")
        if item_id:
            qs = qs.filter(item_id=int(item_id))
        if location_id:
            qs = qs.filter(location_id=int(location_id))
        return Response({"results": InventoryBalanceSerializer(qs.order_by("item_id", "location_id"), many=True).data})


class InventoryLocationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        # TODO: Re-enable when permissions are fully set up
        # denied = _require(request.user, workspace, "inventory.view", level="view")
        # if denied:
        #     return denied

        qs = InventoryLocation.objects.filter(workspace=workspace).order_by("name", "code", "id")
        return Response({"results": InventoryLocationSerializer(qs, many=True).data})


class InventoryEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        # TODO: Re-enable when permissions are fully set up
        # denied = _require(request.user, workspace, "inventory.view", level="view")
        # if denied:
        #     return denied

        qs = InventoryEvent.objects.filter(workspace=workspace).select_related("item", "location").order_by("-created_at", "-id")

        item_id = request.query_params.get("item_id")
        location_id = request.query_params.get("location_id")
        limit_raw = request.query_params.get("limit")

        if item_id:
            try:
                qs = qs.filter(item_id=int(item_id))
            except Exception:
                return Response({"detail": "Invalid item_id."}, status=status.HTTP_400_BAD_REQUEST)

        if location_id:
            try:
                qs = qs.filter(location_id=int(location_id))
            except Exception:
                return Response({"detail": "Invalid location_id."}, status=status.HTTP_400_BAD_REQUEST)

        limit = 100
        if limit_raw:
            try:
                limit = int(limit_raw)
            except Exception:
                return Response({"detail": "Invalid limit."}, status=status.HTTP_400_BAD_REQUEST)
        limit = max(1, min(limit, 200))

        return Response({"results": InventoryEventSerializer(qs[:limit], many=True).data})


class InventoryReceiveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InventoryReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        if workspace.id != data["workspace_id"]:
            return Response({"detail": "workspace_id mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        item = InventoryItem.objects.filter(id=data["item_id"], workspace=workspace).first()
        if not item:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        location = InventoryLocation.objects.filter(id=data["location_id"], workspace=workspace).first()
        if not location:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            event, journal = receive_stock(
                workspace=workspace,
                item=item,
                location=location,
                quantity=data["quantity"],
                unit_cost=data["unit_cost"],
                po_reference=data.get("po_reference"),
                actor_type="human",
                actor_id=str(getattr(request.user, "id", "")),
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"event_id": event.id, "journal_entry_id": journal.id}, status=status.HTTP_201_CREATED)


class InventoryShipView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InventoryShipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        if workspace.id != data["workspace_id"]:
            return Response({"detail": "workspace_id mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        item = InventoryItem.objects.filter(id=data["item_id"], workspace=workspace).first()
        if not item:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        location = InventoryLocation.objects.filter(id=data["location_id"], workspace=workspace).first()
        if not location:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            event, journal = ship_stock(
                workspace=workspace,
                item=item,
                location=location,
                quantity=data["quantity"],
                so_reference=data.get("so_reference"),
                actor_type="human",
                actor_id=str(getattr(request.user, "id", "")),
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"event_id": event.id, "journal_entry_id": journal.id}, status=status.HTTP_201_CREATED)


class InventoryAdjustView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InventoryAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        if workspace.id != data["workspace_id"]:
            return Response({"detail": "workspace_id mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        item = InventoryItem.objects.filter(id=data["item_id"], workspace=workspace).first()
        if not item:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        location = InventoryLocation.objects.filter(id=data["location_id"], workspace=workspace).first()
        if not location:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            event, journal = adjust_stock_to_physical_count(
                workspace=workspace,
                item=item,
                location=location,
                physical_qty=data["physical_qty"],
                reason_code=data["reason_code"],
                actor_type="human",
                actor_id=str(getattr(request.user, "id", "")),
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not event:
            return Response({"detail": "No change."}, status=status.HTTP_200_OK)
        return Response({"event_id": event.id, "journal_entry_id": journal.id}, status=status.HTTP_201_CREATED)


class InventoryReserveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InventoryReserveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        if workspace.id != data["workspace_id"]:
            return Response({"detail": "workspace_id mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        item = InventoryItem.objects.filter(id=data["item_id"], workspace=workspace).first()
        if not item:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        location = InventoryLocation.objects.filter(id=data["location_id"], workspace=workspace).first()
        if not location:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            event, balance = commit_stock(
                workspace=workspace,
                item=item,
                location=location,
                quantity=data["quantity"],
                so_reference=data["reference"],
                actor_type="human",
                actor_id=str(getattr(request.user, "id", "")),
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "event_id": event.id,
                "qty_on_hand": str(balance.qty_on_hand),
                "qty_committed": str(balance.qty_committed),
                "qty_on_order": str(balance.qty_on_order),
                "qty_available": str(balance.qty_available),
            },
            status=status.HTTP_201_CREATED,
        )


class InventoryReleaseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InventoryReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        if workspace.id != data["workspace_id"]:
            return Response({"detail": "workspace_id mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        item = InventoryItem.objects.filter(id=data["item_id"], workspace=workspace).first()
        if not item:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        location = InventoryLocation.objects.filter(id=data["location_id"], workspace=workspace).first()
        if not location:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            event, balance = uncommit_stock(
                workspace=workspace,
                item=item,
                location=location,
                quantity=data["quantity"],
                so_reference=data["reference"],
                actor_type="human",
                actor_id=str(getattr(request.user, "id", "")),
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "event_id": event.id,
                "qty_on_hand": str(balance.qty_on_hand),
                "qty_committed": str(balance.qty_committed),
                "qty_on_order": str(balance.qty_on_order),
                "qty_available": str(balance.qty_available),
            },
            status=status.HTTP_201_CREATED,
        )


class LandedCostBatchesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        from inventory.models import LandedCostBatch

        qs = LandedCostBatch.objects.filter(workspace=workspace).prefetch_related("allocations")
        return Response({"results": LandedCostBatchSerializer(qs.order_by("-created_at"), many=True).data})

    def post(self, request):
        serializer = LandedCostBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        if workspace.id != data["workspace_id"]:
            return Response({"detail": "workspace_id mismatch."}, status=status.HTTP_400_BAD_REQUEST)
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        try:
            batch = create_landed_cost_batch(
                workspace=workspace,
                description=data.get("description") or "",
                allocation_method=data.get("allocation_method") or "manual",
                total_extra_cost=data["total_extra_cost"],
                credit_account_id=data.get("credit_account_id"),
                allocations=data["allocations"],
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        batch = batch.__class__.objects.filter(id=batch.id).prefetch_related("allocations").get()
        return Response(LandedCostBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class LandedCostApplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        denied = _require(request.user, workspace, "inventory.manage", level="edit")
        if denied:
            return denied

        try:
            batch, journal = apply_landed_cost(
                workspace=workspace,
                batch_id=int(pk),
                actor_type="human",
                actor_id=str(getattr(request.user, "id", "")),
                created_by=request.user,
            )
        except DomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"batch_id": batch.id, "journal_entry_id": journal.id}, status=status.HTTP_201_CREATED)
