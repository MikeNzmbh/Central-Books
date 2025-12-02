import logging
from datetime import timedelta

from django.db.models import Case, IntegerField, When
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import get_current_business
from .llm import generate_companion_narrative, generate_insights_for_snapshot
from .models import CompanionInsight, CompanionSuggestedAction, WorkspaceCompanionProfile
from .serializers import CompanionInsightSerializer, CompanionSuggestedActionSerializer, HealthIndexSerializer
from .services import (
    create_health_snapshot,
    ensure_metric_insights,
    gather_workspace_metrics,
    get_latest_health_snapshot,
    refresh_suggested_actions_for_workspace,
    apply_suggested_action,
    dismiss_suggested_action,
)

logger = logging.getLogger(__name__)


class CompanionOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace = get_current_business(request.user)
        if workspace is None:
            return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        profile, _ = WorkspaceCompanionProfile.objects.get_or_create(workspace=workspace)
        if not profile.is_enabled:
            return Response({"detail": "Companion is disabled for this workspace."}, status=status.HTTP_403_FORBIDDEN)

        refresh_minutes = 60  # 1 hour refresh for fresh data
        snapshot = get_latest_health_snapshot(workspace, max_age_minutes=refresh_minutes)
        if snapshot is None and profile.enable_health_index:
            snapshot = create_health_snapshot(workspace)

        health_payload = HealthIndexSerializer(snapshot).data if snapshot else None
        raw_metrics = snapshot.raw_metrics if snapshot else gather_workspace_metrics(workspace)

        insights = []
        insights_data = []
        if profile.enable_suggestions:
            ensure_metric_insights(workspace, raw_metrics)

            if snapshot and not CompanionInsight.objects.filter(workspace=workspace, is_dismissed=False).exists():
                # Seed sample insights via stub generator to avoid empty state.
                try:
                    generate_insights_for_snapshot(snapshot)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to generate sample insights: %s", exc)

            severity_order = Case(
                When(severity="critical", then=0),
                When(severity="warning", then=1),
                default=2,
                output_field=IntegerField(),
            )
            insights = (
                CompanionInsight.objects.filter(workspace=workspace, is_dismissed=False)
                .order_by(severity_order, "-created_at")[:5]
            )
            insights_data = CompanionInsightSerializer(insights, many=True).data

        refresh_suggested_actions_for_workspace(workspace, snapshot=snapshot)
        actions_qs = CompanionSuggestedAction.objects.filter(
            workspace=workspace, status=CompanionSuggestedAction.STATUS_OPEN
        ).order_by("-created_at")
        actions_data = CompanionSuggestedActionSerializer(actions_qs, many=True).data

        llm_narrative = (
            generate_companion_narrative(snapshot, insights, raw_metrics, actions=list(actions_qs))
            if snapshot
            else {"summary": None, "insight_explanations": {}, "action_explanations": {}}
        )

        next_refresh_at = None
        if snapshot and snapshot.created_at:
            next_refresh_at = snapshot.created_at + timedelta(minutes=refresh_minutes)

        return Response(
            {
                "health_index": health_payload,
                "insights": insights_data,
                "top_insights": insights_data,  # alias for existing clients
                "raw_metrics": raw_metrics,
                "next_refresh_at": next_refresh_at.isoformat() if next_refresh_at else None,
                "llm_narrative": llm_narrative,
                "actions": actions_data,
            }
        )


class CompanionInsightDismissView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        workspace = get_current_business(request.user)
        if workspace is None:
            return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            insight = CompanionInsight.objects.get(pk=pk, workspace=workspace)
        except CompanionInsight.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        insight.is_dismissed = True
        insight.dismissed_at = timezone.now()
        insight.save(update_fields=["is_dismissed", "dismissed_at"])
        logger.info(
            "Companion insight dismissed",
            extra={"actor_id": getattr(request.user, "id", None), "workspace_id": workspace.id, "insight_id": insight.id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompanionActionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace = get_current_business(request.user)
        if workspace is None:
            return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        actions = CompanionSuggestedAction.objects.filter(
            workspace=workspace, status=CompanionSuggestedAction.STATUS_OPEN
        ).order_by("-created_at")
        data = CompanionSuggestedActionSerializer(actions, many=True).data
        return Response(data)


class CompanionActionApplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        workspace = get_current_business(request.user)
        if workspace is None:
            return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            action = CompanionSuggestedAction.objects.get(pk=pk, workspace=workspace)
        except CompanionSuggestedAction.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if action.status != CompanionSuggestedAction.STATUS_OPEN:
            return Response({"detail": "Action already resolved."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            apply_suggested_action(action, user=request.user)
        except Exception as exc:
            logger.warning("Failed to apply companion action %s: %s", action.id, exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        logger.info(
            "Companion action applied",
            extra={"actor_id": getattr(request.user, "id", None), "workspace_id": workspace.id, "action_id": action.id},
        )
        return Response(CompanionSuggestedActionSerializer(action).data)


class CompanionActionDismissView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        workspace = get_current_business(request.user)
        if workspace is None:
            return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            action = CompanionSuggestedAction.objects.get(pk=pk, workspace=workspace)
        except CompanionSuggestedAction.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if action.status != CompanionSuggestedAction.STATUS_OPEN:
            return Response({"detail": "Action already resolved."}, status=status.HTTP_400_BAD_REQUEST)
        dismiss_suggested_action(action)
        logger.info(
            "Companion action dismissed",
            extra={"actor_id": getattr(request.user, "id", None), "workspace_id": workspace.id, "action_id": action.id},
        )
        return Response(CompanionSuggestedActionSerializer(action).data)
