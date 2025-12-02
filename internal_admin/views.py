from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch
from django.urls import reverse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import BankAccount, Business
from internal_admin.permissions import IsInternalAdminWithRole, AdminRole, has_min_role
from internal_admin.serializers import (
    AdminAuditLogSerializer,
    BankAccountSerializer,
    BusinessSerializer,
    FeatureFlagSerializer,
    SupportTicketSerializer,
    UserSerializer,
)
from internal_admin.utils import log_admin_action
from internal_admin.models import (
    AdminAuditLog,
    FeatureFlag,
    ImpersonationToken,
    InternalAdminProfile,
    OverviewMetricsSnapshot,
    SupportTicket,
    SupportTicketNote,
)
from internal_admin.services import compute_overview_metrics

try:
    from allauth.socialaccount.models import SocialAccount
except ImportError:  # pragma: no cover
    SocialAccount = None


User = get_user_model()


class BaseInternalAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT

    def get_min_role(self, request=None):
        return getattr(self, "required_role", AdminRole.SUPPORT)


class InternalUsersViewSet(BaseInternalAdminViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("id")

    def get_min_role(self, request=None):
        if self.action in {"update", "partial_update"}:
            return AdminRole.OPS
        return AdminRole.SUPPORT

    def get_queryset(self):
        qs = super().get_queryset().select_related("internal_admin_profile")
        qs = qs.annotate(workspace_count=Count("businesses", distinct=True))

        params = self.request.query_params
        search = params.get("search") or params.get("q")
        status_filter = params.get("status")
        is_active_filter = params.get("is_active")
        has_google = params.get("has_google")

        if SocialAccount:
            qs = qs.annotate(social_account_count=Count("socialaccount", distinct=True))
            qs = qs.prefetch_related(
                Prefetch(
                    "socialaccount_set",
                    queryset=SocialAccount.objects.only("provider"),
                    to_attr="_social_accounts",
                )
            )
            has_google_bool = self._bool_param(has_google)
            if has_google_bool is True:
                qs = qs.filter(socialaccount__provider="google").distinct()
            elif has_google_bool is False:
                qs = qs.exclude(socialaccount__provider="google")

        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "suspended":
            qs = qs.filter(is_active=False)

        active_bool = self._bool_param(is_active_filter)
        if active_bool is True:
            qs = qs.filter(is_active=True)
        elif active_bool is False:
            qs = qs.filter(is_active=False)

        return qs

    def _bool_param(self, value):
        if value is None:
            return None
        val = str(value).lower()
        if val in {"1", "true", "yes", "on"}:
            return True
        if val in {"0", "false", "no", "off"}:
            return False
        return None

    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        instance = serializer.instance
        before_email = instance.email
        before_active = instance.is_active
        before_providers = UserSerializer._providers(instance)
        instance = serializer.save()
        after_providers = UserSerializer._providers(instance)
        changes: dict[str, dict[str, object]] = {}
        if before_email != instance.email:
            changes["email"] = {"from": before_email, "to": instance.email}
        if before_active != instance.is_active:
            changes["is_active"] = {"from": before_active, "to": instance.is_active}
        if before_providers != after_providers:
            changes["auth_providers"] = {"from": before_providers, "to": after_providers}
        log_admin_action(
            self.request,
            "USER_UPDATED",
            instance,
            extra={
                "changes": changes,
                "auth_providers": after_providers,
            },
        )


class InternalWorkspacesViewSet(BaseInternalAdminViewSet):
    serializer_class = BusinessSerializer
    queryset = Business.objects.select_related("owner_user").all().order_by("id")

    def get_min_role(self, request=None):
        if self.action in {"update", "partial_update"}:
            return AdminRole.OPS
        return AdminRole.SUPPORT

    def partial_update(self, request, *args, **kwargs):
        if "is_deleted" in request.data and not has_min_role(request.user, AdminRole.SUPERADMIN):
            return Response({"detail": "Only superadmin can delete workspaces."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if "is_deleted" in request.data and not has_min_role(request.user, AdminRole.SUPERADMIN):
            return Response({"detail": "Only superadmin can delete workspaces."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_admin_action(self.request, "WORKSPACE_UPDATED", instance, extra=self.request.data)


class InternalBankAccountsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    serializer_class = BankAccountSerializer
    queryset = (
        BankAccount.objects.select_related("business", "business__owner_user")
        .all()
        .order_by("id")
    )
    required_role = AdminRole.SUPPORT

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT


class AdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    serializer_class = AdminAuditLogSerializer
    queryset = AdminAuditLog.objects.select_related("admin_user").all()
    required_role = AdminRole.SUPPORT

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        admin_user = params.get("admin_user")
        action = params.get("action")
        level = params.get("level")
        category = params.get("category")
        object_type = params.get("object_type")
        object_id = params.get("object_id")
        start = params.get("start")
        end = params.get("end")
        if admin_user:
            qs = qs.filter(admin_user_id=admin_user)
        if action:
            qs = qs.filter(action__icontains=action)
        if level:
            qs = qs.filter(level=level)
        if category:
            qs = qs.filter(category=category)
        if object_type:
            qs = qs.filter(object_type=object_type)
        if object_id:
            qs = qs.filter(object_id=object_id)
        if start:
            qs = qs.filter(timestamp__gte=start)
        if end:
            qs = qs.filter(timestamp__lte=end)
        return qs

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT


class OverviewMetricsView(APIView):
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT

    def get(self, request, *args, **kwargs):
        max_age_minutes = getattr(settings, "INTERNAL_ADMIN_METRICS_MAX_AGE_MINUTES", 5)
        latest = OverviewMetricsSnapshot.objects.first()
        if latest and (timezone.now() - latest.created_at).total_seconds() < max_age_minutes * 60:
            return Response(latest.payload)

        payload = compute_overview_metrics()
        OverviewMetricsSnapshot.objects.create(payload=payload)
        return Response(payload)

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT


class ImpersonationView(APIView):
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT

    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        profile = InternalAdminProfile.objects.filter(user=request.user).first()
        caller_role = profile.role if profile else None
        if request.user.is_superuser and not caller_role:
            caller_role = AdminRole.SUPERADMIN

        target_is_internal_admin = (
            target_user.is_superuser
            or target_user.is_staff
            or InternalAdminProfile.objects.filter(user=target_user).exists()
        )

        if target_user.is_superuser:
            return Response(
                {"detail": "Impersonating superuser accounts is not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if target_is_internal_admin and caller_role != AdminRole.SUPERADMIN:
            return Response(
                {"detail": "Cannot impersonate other internal admins."},
                status=status.HTTP_403_FORBIDDEN,
            )

        token = ImpersonationToken.objects.create(
            admin=request.user,
            target_user=target_user,
            expires_at=timezone.now() + timedelta(minutes=15),
            remote_ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        log_admin_action(
            request,
            "impersonation.created",
            obj=target_user,
            extra={"token_id": str(token.id)},
        )
        redirect_path = reverse("internal-impersonate-accept", args=[token.id])
        redirect_url = request.build_absolute_uri(redirect_path)
        return Response({"redirect_url": redirect_url}, status=status.HTTP_201_CREATED)

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT


class SupportTicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    serializer_class = SupportTicketSerializer
    queryset = (
        SupportTicket.objects.select_related("user", "workspace")
        .prefetch_related("notes__admin_user")
        .all()
    )
    required_role = AdminRole.SUPPORT

    def get_min_role(self, request=None):
        if getattr(self, "action", "") in {"update", "partial_update"}:
            return AdminRole.OPS
        if getattr(self, "action", "") == "add_note":
            return AdminRole.SUPPORT
        return AdminRole.SUPPORT

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        status_filter = params.get("status")
        priority_filter = params.get("priority")
        search = params.get("search")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if priority_filter:
            qs = qs.filter(priority=priority_filter)
        if search:
            qs = qs.filter(
                Q(subject__icontains=search)
                | Q(user__email__icontains=search)
                | Q(workspace__name__icontains=search)
            )
        return qs.order_by("-created_at")

    def partial_update(self, request, *args, **kwargs):
        if not has_min_role(request.user, AdminRole.OPS):
            return Response(
                {"detail": "Only Ops or higher can update tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )
        response = super().partial_update(request, *args, **kwargs)
        ticket = self.get_object()
        log_admin_action(
            request,
            "support_ticket.updated",
            obj=ticket,
            extra={"fields": list(request.data.keys())},
            category="support",
        )
        return response

    @action(detail=True, methods=["post"])
    def add_note(self, request, pk=None):
        ticket = self.get_object()
        body = request.data.get("body", "").strip()
        if not body:
            return Response({"detail": "Note body is required."}, status=status.HTTP_400_BAD_REQUEST)
        note = SupportTicketNote.objects.create(ticket=ticket, admin_user=request.user, body=body)
        log_admin_action(
            request,
            "support_ticket.note_added",
            obj=ticket,
            extra={"note_id": note.id},
            category="support",
        )
        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FeatureFlagViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    serializer_class = FeatureFlagSerializer
    queryset = FeatureFlag.objects.all()
    required_role = AdminRole.SUPPORT

    def get_min_role(self, request=None):
        if getattr(self, "action", "") in {"update", "partial_update"}:
            return AdminRole.ENGINEERING
        return AdminRole.SUPPORT

    def partial_update(self, request, *args, **kwargs):
        flag = self.get_object()
        rollout_percent = request.data.get("rollout_percent")
        if rollout_percent is not None:
            try:
                rollout_int = int(rollout_percent)
            except (TypeError, ValueError):
                return Response({"detail": "rollout_percent must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
            if rollout_int < 0 or rollout_int > 100:
                return Response({"detail": "rollout_percent must be between 0 and 100"}, status=status.HTTP_400_BAD_REQUEST)
            request.data["rollout_percent"] = rollout_int  # type: ignore[index]
        response = super().partial_update(request, *args, **kwargs)
        log_admin_action(
            request,
            "feature_flag.updated",
            obj=flag,
            extra=dict(request.data),
            category="feature_flags",
        )
        return response
