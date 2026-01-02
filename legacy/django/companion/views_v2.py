from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companion.models import (
    AICommandRecord,
    AIIntegrityReport,
    BusinessPolicy,
    CanonicalLedgerProvenance,
    ProvisionalLedgerEvent,
    WorkspaceAISettings,
)
from companion.serializers_v2 import (
    AIIntegrityReportSerializer,
    BusinessPolicySerializer,
    CanonicalLedgerProvenanceSerializer,
    ProvisionalLedgerEventSerializer,
    WorkspaceAISettingsSerializer,
)
from companion.v2.commands import (
    ApplyBankMatchCommand,
    ApplyCategorizationCommand,
    ExplainabilityMetadata,
    HumanInTheLoop,
    ProposeBankMatchCommand,
    ProposeCategorizationCommand,
)
from companion.v2.guardrails import CompanionBlocked, ensure_ai_settings, global_ai_enabled, trust_breaker
from companion.v2.handlers import (
    CommandValidationError,
    apply_bank_match,
    apply_categorization,
    propose_bank_match,
    propose_categorization,
)
from core.permissions_engine import can
from core.utils import get_current_business


def _deny(message: str = "Permission denied"):
    return Response({"detail": message}, status=status.HTTP_403_FORBIDDEN)


def _require(user, workspace, action: str, *, level: str = "view"):
    if not can(user, workspace, action, level=level):
        return _deny()
    return None


def _resolve_workspace_from_request(request, *, require_explicit: bool = False):
    """
    Resolve workspace with optional explicit workspace_id.

    - If `workspace_id` is present (query param for GET, body for POST), load that workspace.
    - Otherwise fall back to the current/primary workspace selection.
    """
    workspace_id = request.query_params.get("workspace_id")
    if workspace_id is None and request.method != "GET":
        try:
            workspace_id = (request.data or {}).get("workspace_id")
        except Exception:
            workspace_id = None

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

    if require_explicit:
        return None, Response({"detail": "workspace_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    workspace = get_current_business(request.user)
    if not workspace:
        return None, _deny("No active workspace.")
    return workspace, None


def _default_metadata(*, tier: int, status_value: str, actor: str = "system_companion_v2") -> ExplainabilityMetadata:
    return ExplainabilityMetadata(
        actor=actor,
        confidence_score=None,
        logic_trace_id=None,
        rationale=None,
        business_profile_constraint=None,
        human_in_the_loop=HumanInTheLoop(tier=tier, status=status_value),  # type: ignore[arg-type]
    )


def _shadow_rejection_rate(*, workspace, window_days: int = 30) -> float:
    window_start = timezone.now() - timedelta(days=window_days)
    qs = ProvisionalLedgerEvent.objects.filter(workspace=workspace, created_at__gte=window_start)
    applied = qs.filter(status=ProvisionalLedgerEvent.Status.APPLIED).count()
    rejected = qs.filter(status=ProvisionalLedgerEvent.Status.REJECTED).count()
    total = applied + rejected
    if total <= 0:
        return 0.0
    return float(rejected) / float(total)


def _record_shadow_rejection(*, workspace, shadow_event: ProvisionalLedgerEvent, rejected_by, reason: str) -> None:
    AICommandRecord.objects.create(
        workspace=workspace,
        command_type="RejectShadowEvent",
        payload={
            "shadow_event_id": str(shadow_event.id),
            "event_type": shadow_event.event_type,
            "reason": (reason or "")[:500],
        },
        metadata={
            "reviewed_by_user_id": getattr(rejected_by, "id", None),
            "shadow_command_id": str(shadow_event.command_id) if shadow_event.command_id else None,
        },
        actor=shadow_event.actor,
        status=AICommandRecord.Status.ACCEPTED,
        error_message="",
        created_by=rejected_by,
        shadow_event=shadow_event,
    )


class CompanionV2AISettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied
        settings_row = ensure_ai_settings(workspace)
        return Response(
            {
                "global_ai_enabled": global_ai_enabled(),
                "settings": WorkspaceAISettingsSerializer(settings_row).data,
            }
        )

    def patch(self, request):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "workspace.manage_ai", level="edit")
        if denied:
            return denied
        settings_row = ensure_ai_settings(workspace)
        serializer = WorkspaceAISettingsSerializer(settings_row, data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "global_ai_enabled": global_ai_enabled(),
                "settings": WorkspaceAISettingsSerializer(settings_row).data,
            }
        )


class CompanionV2BusinessPolicyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied
        policy, _ = BusinessPolicy.objects.get_or_create(workspace=workspace)
        return Response(BusinessPolicySerializer(policy).data)

    def patch(self, request):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "workspace.manage_ai", level="edit")
        if denied:
            return denied
        policy, _ = BusinessPolicy.objects.get_or_create(workspace=workspace)
        serializer = BusinessPolicySerializer(policy, data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BusinessPolicySerializer(policy).data)


class CompanionV2ProposalsView(APIView):
    """
    Workspace-scoped list of *proposed* shadow events ("proposals").

    This is a convenience wrapper over the shadow-events listing for the UI.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied

        status_filter = request.query_params.get("status") or ProvisionalLedgerEvent.Status.PROPOSED
        qs = ProvisionalLedgerEvent.objects.filter(workspace=workspace, status=status_filter)
        event_type = request.query_params.get("event_type")
        subject_object_id = request.query_params.get("subject_object_id")
        if event_type:
            qs = qs.filter(event_type=event_type)
        if subject_object_id:
            try:
                qs = qs.filter(subject_object_id=int(subject_object_id))
            except Exception:
                pass

        limit = request.query_params.get("limit")
        if limit:
            try:
                qs = qs[: max(1, min(500, int(limit)))]
            except Exception:
                qs = qs[:200]
        else:
            qs = qs[:200]

        return Response(ProvisionalLedgerEventSerializer(qs, many=True).data)


class CompanionV2ShadowEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace = get_current_business(request.user)
        if not workspace:
            return _deny("No active workspace.")
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied

        qs = ProvisionalLedgerEvent.objects.filter(workspace=workspace)
        status_filter = request.query_params.get("status")
        event_type = request.query_params.get("event_type")
        subject_object_id = request.query_params.get("subject_object_id")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if event_type:
            qs = qs.filter(event_type=event_type)
        if subject_object_id:
            try:
                qs = qs.filter(subject_object_id=int(subject_object_id))
            except Exception:
                pass

        limit = request.query_params.get("limit")
        if limit:
            try:
                qs = qs[: max(1, min(500, int(limit)))]
            except Exception:
                qs = qs[:200]
        else:
            qs = qs[:200]

        return Response(ProvisionalLedgerEventSerializer(qs, many=True).data)


class CompanionV2ShadowEventDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: UUID):
        workspace = get_current_business(request.user)
        if not workspace:
            return _deny("No active workspace.")
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied
        event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
        if not event:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProvisionalLedgerEventSerializer(event).data)


class CompanionV2ProposeCategorizationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.shadow.write", level="edit")
        if denied:
            return denied

        payload = dict(request.data or {})
        payload["workspace_id"] = workspace.id
        if "metadata" not in payload:
            payload["metadata"] = _default_metadata(tier=2, status_value="proposed").model_dump(mode="json")

        try:
            cmd = ProposeCategorizationCommand.model_validate(payload)
            shadow_event = propose_categorization(workspace=workspace, command=cmd, created_by=request.user)
            return Response(ProvisionalLedgerEventSerializer(shadow_event).data, status=status.HTTP_201_CREATED)
        except CompanionBlocked as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except CommandValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class CompanionV2ProposeBankMatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.shadow.write", level="edit")
        if denied:
            return denied

        payload = dict(request.data or {})
        payload["workspace_id"] = workspace.id
        if "metadata" not in payload:
            payload["metadata"] = _default_metadata(tier=2, status_value="proposed").model_dump(mode="json")

        try:
            cmd = ProposeBankMatchCommand.model_validate(payload)
            shadow_event = propose_bank_match(workspace=workspace, command=cmd, created_by=request.user)
            return Response(ProvisionalLedgerEventSerializer(shadow_event).data, status=status.HTTP_201_CREATED)
        except CompanionBlocked as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except CommandValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class CompanionV2ShadowEventRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: UUID):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.actions", level="edit")
        if denied:
            return denied

        event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
        if not event:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if event.status != ProvisionalLedgerEvent.Status.PROPOSED:
            return Response({"detail": "Only proposed events can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data or {}).get("reason") or ""
        human = dict(event.human_in_the_loop or {})
        human["status"] = "rejected"
        human["rejected_by_user_id"] = getattr(request.user, "id", None)
        if reason:
            human["rejection_reason"] = str(reason)[:500]
        event.status = ProvisionalLedgerEvent.Status.REJECTED
        event.human_in_the_loop = human
        event.save(update_fields=["status", "human_in_the_loop", "updated_at"])
        _record_shadow_rejection(workspace=workspace, shadow_event=event, rejected_by=request.user, reason=str(reason))
        settings_row = ensure_ai_settings(workspace)
        trust_breaker(
            workspace=workspace,
            settings_row=settings_row,
            rejection_rate=_shadow_rejection_rate(workspace=workspace),
            action="shadow_event_reject",
        )
        return Response(ProvisionalLedgerEventSerializer(event).data)


class CompanionV2ProposalRejectView(APIView):
    """
    Reject a proposal (shadow event) with explicit workspace scoping.

    This is equivalent to rejecting a shadow event, but requires `workspace_id`
    to avoid ambiguity when users belong to multiple workspaces.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: UUID):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.actions", level="edit")
        if denied:
            return denied

        event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
        if not event:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if event.status != ProvisionalLedgerEvent.Status.PROPOSED:
            return Response({"detail": "Only proposed events can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data or {}).get("reason") or ""
        human = dict(event.human_in_the_loop or {})
        human["status"] = "rejected"
        human["rejected_by_user_id"] = getattr(request.user, "id", None)
        if reason:
            human["rejection_reason"] = str(reason)[:500]
        event.status = ProvisionalLedgerEvent.Status.REJECTED
        event.human_in_the_loop = human
        if reason:
            meta = dict(event.metadata or {})
            meta["rejection_reason"] = str(reason)[:500]
            event.metadata = meta
        event.save(update_fields=["status", "human_in_the_loop", "metadata", "updated_at"])
        _record_shadow_rejection(workspace=workspace, shadow_event=event, rejected_by=request.user, reason=str(reason))
        settings_row = ensure_ai_settings(workspace)
        trust_breaker(
            workspace=workspace,
            settings_row=settings_row,
            rejection_rate=_shadow_rejection_rate(workspace=workspace),
            action="proposal_reject",
        )
        return Response(ProvisionalLedgerEventSerializer(event).data)


class CompanionV2ShadowEventApplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: UUID):
        workspace, resp = _resolve_workspace_from_request(request)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.actions", level="edit")
        if denied:
            return denied

        event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
        if not event:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if event.status != ProvisionalLedgerEvent.Status.PROPOSED:
            return Response({"detail": "Only proposed events can be applied."}, status=status.HTTP_400_BAD_REQUEST)

        base_meta = event.metadata or {}
        tier = int((event.human_in_the_loop or {}).get("tier") or 2)
        meta = ExplainabilityMetadata(
            actor=event.actor,
            confidence_score=float(event.confidence_score) if event.confidence_score is not None else None,
            logic_trace_id=event.logic_trace_id or None,
            rationale=event.rationale or None,
            business_profile_constraint=event.business_profile_constraint or None,
            human_in_the_loop=HumanInTheLoop(tier=tier, status="accepted"),
        )

        try:
            if event.event_type == "CategorizationProposed":
                cmd = ApplyCategorizationCommand(
                    workspace_id=workspace.id,
                    shadow_event_id=event.id,
                    override_splits=(request.data or {}).get("override_splits"),
                    metadata=meta,
                )
                journal_entry, match = apply_categorization(workspace=workspace, command=cmd, approved_by=request.user)
                shadow_event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
                return Response(
                    {
                        "shadow_event": ProvisionalLedgerEventSerializer(shadow_event or event).data,
                        "result": {
                            "journal_entry_id": journal_entry.id,
                            "bank_match_id": match.id,
                        },
                    }
                )
            if event.event_type == "BankMatchProposed":
                cmd = ApplyBankMatchCommand(
                    workspace_id=workspace.id,
                    shadow_event_id=event.id,
                    metadata=meta,
                )
                match = apply_bank_match(workspace=workspace, command=cmd, approved_by=request.user)
                shadow_event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
                return Response(
                    {
                        "shadow_event": ProvisionalLedgerEventSerializer(shadow_event or event).data,
                        "result": {
                            "bank_match_id": match.id,
                        },
                    }
                )
            return Response({"detail": "Unsupported shadow event type."}, status=status.HTTP_400_BAD_REQUEST)
        except CompanionBlocked as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except CommandValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class CompanionV2ProposalApplyView(APIView):
    """
    Apply a proposal (promote from Shadow to Canonical) with explicit workspace scoping.

    Requires `workspace_id` to avoid ambiguity when users belong to multiple workspaces.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: UUID):
        workspace, resp = _resolve_workspace_from_request(request, require_explicit=True)
        if resp:
            return resp
        denied = _require(request.user, workspace, "companion.actions", level="edit")
        if denied:
            return denied

        event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
        if not event:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if event.status != ProvisionalLedgerEvent.Status.PROPOSED:
            return Response({"detail": "Only proposed events can be applied."}, status=status.HTTP_400_BAD_REQUEST)

        tier = int((event.human_in_the_loop or {}).get("tier") or 2)
        meta = ExplainabilityMetadata(
            actor=event.actor,
            confidence_score=float(event.confidence_score) if event.confidence_score is not None else None,
            logic_trace_id=event.logic_trace_id or None,
            rationale=event.rationale or None,
            business_profile_constraint=event.business_profile_constraint or None,
            human_in_the_loop=HumanInTheLoop(tier=tier, status="accepted"),
        )

        try:
            if event.event_type == "CategorizationProposed":
                cmd = ApplyCategorizationCommand(
                    workspace_id=workspace.id,
                    shadow_event_id=event.id,
                    override_splits=(request.data or {}).get("override_splits"),
                    metadata=meta,
                )
                journal_entry, match = apply_categorization(workspace=workspace, command=cmd, approved_by=request.user)
                shadow_event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
                return Response(
                    {
                        "shadow_event": ProvisionalLedgerEventSerializer(shadow_event or event).data,
                        "result": {
                            "journal_entry_id": journal_entry.id,
                            "bank_match_id": match.id,
                        },
                    }
                )
            if event.event_type == "BankMatchProposed":
                cmd = ApplyBankMatchCommand(
                    workspace_id=workspace.id,
                    shadow_event_id=event.id,
                    metadata=meta,
                )
                match = apply_bank_match(workspace=workspace, command=cmd, approved_by=request.user)
                shadow_event = ProvisionalLedgerEvent.objects.filter(workspace=workspace, id=pk).first()
                return Response(
                    {
                        "shadow_event": ProvisionalLedgerEventSerializer(shadow_event or event).data,
                        "result": {
                            "bank_match_id": match.id,
                        },
                    }
                )
            return Response({"detail": "Unsupported shadow event type."}, status=status.HTTP_400_BAD_REQUEST)
        except CompanionBlocked as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except CommandValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class CompanionV2ShadowLedgerWipeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        workspace = get_current_business(request.user)
        if not workspace:
            return _deny("No active workspace.")
        denied = _require(request.user, workspace, "companion.shadow.wipe", level="approve")
        if denied:
            return denied

        status_filter = request.query_params.get("status")
        qs = ProvisionalLedgerEvent.objects.filter(workspace=workspace)
        if status_filter:
            qs = qs.filter(status=status_filter)
        deleted_count, _ = qs.delete()
        return Response({"ok": True, "deleted": deleted_count})


class CompanionV2ProvenanceLookupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace = get_current_business(request.user)
        if not workspace:
            return _deny("No active workspace.")
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied

        content_type_id = request.query_params.get("content_type_id")
        object_id = request.query_params.get("object_id")
        shadow_event_id = request.query_params.get("shadow_event_id")

        qs = CanonicalLedgerProvenance.objects.filter(workspace=workspace)
        if content_type_id and object_id:
            try:
                qs = qs.filter(content_type_id=int(content_type_id), object_id=int(object_id))
            except Exception:
                return Response({"detail": "Invalid content_type_id/object_id"}, status=status.HTTP_400_BAD_REQUEST)
        if shadow_event_id:
            try:
                qs = qs.filter(shadow_event_id=UUID(str(shadow_event_id)))
            except Exception:
                return Response({"detail": "Invalid shadow_event_id"}, status=status.HTTP_400_BAD_REQUEST)

        qs = qs.order_by("-created_at")[:50]
        return Response(CanonicalLedgerProvenanceSerializer(qs, many=True).data)


class CompanionV2IntegrityReportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace = get_current_business(request.user)
        if not workspace:
            return _deny("No active workspace.")
        denied = _require(request.user, workspace, "companion.view", level="view")
        if denied:
            return denied

        qs = AIIntegrityReport.objects.filter(workspace=workspace).order_by("-created_at")[:12]
        return Response(AIIntegrityReportSerializer(qs, many=True).data)
