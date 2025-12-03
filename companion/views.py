import logging
from datetime import timedelta

from django.db.models import Case, IntegerField, Sum, When
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from core.models import Expense, Invoice
from core.utils import get_current_business
from .llm import generate_companion_narrative, generate_insights_for_snapshot
from .models import CompanionInsight, CompanionSuggestedAction, WorkspaceCompanionProfile
from .serializers import CompanionInsightSerializer, CompanionSuggestedActionSerializer, HealthIndexSerializer
from .services import (
    create_health_snapshot,
    ensure_metric_insights,
    gather_workspace_metrics,
    get_latest_health_snapshot,
    get_last_seen_field_name,
    get_last_seen_value,
    get_new_actions_count,
    refresh_suggested_actions_for_workspace,
    apply_suggested_action,
    dismiss_suggested_action,
)

logger = logging.getLogger(__name__)


class CompanionOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Return Companion overview with graceful fallback.
        Never returns error status codes - always returns HTTP 200 with appropriate data or empty fallback.
        """
        context_filter = request.query_params.get("context") or None
        
        # Build fallback response structure
        def _get_fallback_response():
            return {
                "health_index": None,
                "insights": [],
                "top_insights": [],
                "raw_metrics": {},
                "next_refresh_at": None,
                "llm_narrative": {
                    "summary": None,
                    "insight_explanations": {},
                    "action_explanations": {},
                    "context_summary": None,
                },
                "actions": [],
                "has_new_actions": False,
                "new_actions_count": 0,
                "context": context_filter,
                "context_all_clear": True,
                "context_metrics": {},
            }
        
        try:
            workspace = get_current_business(request.user)
            if workspace is None:
                logger.warning("Companion overview requested but no workspace found for user %s", request.user.id)
                return Response(_get_fallback_response())

            profile, _ = WorkspaceCompanionProfile.objects.get_or_create(workspace=workspace)
            if not profile.is_enabled:
                logger.info("Companion overview requested but companion disabled for workspace %s", workspace.id)
                return Response(_get_fallback_response())

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

            context_insights = insights
            context_actions = actions_qs
            context_all_clear = False
            context_metrics = {}
            new_actions_count = 0
            has_new_actions = False

            valid_contexts = {
                CompanionInsight.CONTEXT_BANK,
                CompanionInsight.CONTEXT_RECONCILIATION,
                CompanionInsight.CONTEXT_INVOICES,
                CompanionInsight.CONTEXT_EXPENSES,
                CompanionInsight.CONTEXT_DASHBOARD,
            }
            if context_filter in valid_contexts:
                last_seen_at = get_last_seen_value(profile, context_filter)
                new_actions_count = get_new_actions_count(workspace, context_filter, last_seen_at)
                has_new_actions = new_actions_count > 0
                context_insights = [i for i in insights if getattr(i, "context", CompanionInsight.CONTEXT_DASHBOARD) == context_filter]
                context_actions = [a for a in actions_qs if getattr(a, "context", CompanionSuggestedAction.CONTEXT_DASHBOARD) == context_filter]
                if not context_insights and not context_actions:
                    context_all_clear = True

                if context_filter in {CompanionInsight.CONTEXT_BANK, CompanionInsight.CONTEXT_RECONCILIATION}:
                    context_metrics = {
                        "unreconciled_count": raw_metrics.get("unreconciled_count"),
                        "old_unreconciled_60d": raw_metrics.get("old_unreconciled_60d"),
                        "old_unreconciled_90d": raw_metrics.get("old_unreconciled_90d"),
                        "suggested_bank_matches": len(context_actions),
                    }
                elif context_filter == CompanionInsight.CONTEXT_INVOICES:
                    overdue_total = raw_metrics.get("overdue_invoices", 0)
                    open_qs = Invoice.objects.filter(
                        business=workspace,
                        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
                    )
                    open_sum = open_qs.aggregate(total=Sum("grand_total"))["total"] or 0
                    next_due = open_qs.order_by("due_date").values_list("due_date", flat=True).first()
                    context_metrics = {
                        "overdue_invoices": overdue_total,
                        "open_invoices_total": open_sum,
                        "next_due_date": next_due,
                    }
                elif context_filter == CompanionInsight.CONTEXT_EXPENSES:
                    uncategorized = raw_metrics.get("uncategorized_expenses", 0)
                    top_groups = list(
                        Expense.objects.filter(business=workspace, category__isnull=False)
                        .values("category__name")
                        .annotate(total=Sum("amount"))
                        .order_by("-total")[:3]
                    )
                    context_metrics = {
                        "uncategorized_expenses": uncategorized,
                        "top_expense_groups": top_groups,
                    }
                insights_data = CompanionInsightSerializer(context_insights, many=True).data
                actions_data = CompanionSuggestedActionSerializer(context_actions, many=True).data

            llm_narrative = (
                generate_companion_narrative(
                    snapshot,
                    context_insights if context_filter in valid_contexts else insights,
                    raw_metrics,
                    actions=list(context_actions if context_filter in valid_contexts else actions_qs),
                    context=context_filter,
                )
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
                    "has_new_actions": has_new_actions if context_filter in valid_contexts else False,
                    "new_actions_count": new_actions_count if context_filter in valid_contexts else 0,
                    "context": context_filter if context_filter in valid_contexts else None,
                    "context_all_clear": context_all_clear if context_filter in valid_contexts else False,
                    "context_metrics": context_metrics if context_filter in valid_contexts else {},
                }
            )
        except Exception as exc:
            # Catch any unexpected errors (LLM failures, database issues, etc.)
            logger.error("Companion overview failed unexpectedly: %s", exc, exc_info=True)
            return Response(_get_fallback_response())


class CompanionContextSeenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    valid_contexts = {
        CompanionSuggestedAction.CONTEXT_BANK,
        CompanionSuggestedAction.CONTEXT_RECONCILIATION,
        CompanionSuggestedAction.CONTEXT_INVOICES,
        CompanionSuggestedAction.CONTEXT_EXPENSES,
        CompanionSuggestedAction.CONTEXT_DASHBOARD,
    }

    def post(self, request):
        workspace = get_current_business(request.user)
        if workspace is None:
            return Response({"detail": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        context = (request.data or {}).get("context")
        if context not in self.valid_contexts:
            return Response({"detail": "Invalid context."}, status=status.HTTP_400_BAD_REQUEST)

        profile, _ = WorkspaceCompanionProfile.objects.get_or_create(workspace=workspace)
        field_name = get_last_seen_field_name(context)
        if not field_name:
            return Response({"detail": "Invalid context."}, status=status.HTTP_400_BAD_REQUEST)

        setattr(profile, field_name, timezone.now())
        profile.save(update_fields=[field_name, "updated_at"])
        return Response({"ok": True})


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
