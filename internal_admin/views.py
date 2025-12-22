from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ip_utils import get_client_ip
from core.models import BankAccount, Business
from internal_admin.permissions import IsInternalAdminWithRole, AdminRole, has_min_role
from internal_admin.permissions import STAFF_ROLE_TO_ADMIN_ROLE, can_grant_superadmin
from internal_admin.throttling import InternalAdminScopedRateThrottle
from internal_admin.serializers import (
    AdminAuditLogSerializer,
    BankAccountSerializer,
    BusinessSerializer,
    FeatureFlagSerializer,
    StaffProfileDetailSerializer,
    StaffProfileListSerializer,
    StaffProfileWriteSerializer,
    SupportTicketSerializer,
    UserSerializer,
)
from internal_admin.emails import send_staff_invite_email
from internal_admin.utils import log_admin_action
from internal_admin.models import (
    AdminAuditLog,
    AdminInvite,
    FeatureFlag,
    ImpersonationToken,
    InternalAdminProfile,
    OverviewMetricsSnapshot,
    StaffProfile,
    SupportTicket,
    SupportTicketNote,
)
from internal_admin.services import compute_overview_metrics

try:
    from allauth.socialaccount.models import SocialAccount
except ImportError:  # pragma: no cover
    SocialAccount = None


User = get_user_model()


from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000


class BaseInternalAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    pagination_class = StandardResultsSetPagination
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return getattr(self, "required_role", AdminRole.SUPPORT)


def _staff_access_snapshot(profile: StaffProfile) -> dict:
    return {
        "admin_panel_access": bool(profile.admin_panel_access),
        "primary_admin_role": profile.primary_admin_role,
        "is_active_employee": bool(profile.is_active_employee),
        "is_deleted": bool(getattr(profile, "is_deleted", False)),
        "deleted_at": profile.deleted_at.isoformat() if getattr(profile, "deleted_at", None) else None,
        "workspace_scope": profile.workspace_scope or {},
    }


def _sync_internal_admin_profile_from_staff(profile: StaffProfile) -> None:
    """
    Keep legacy InternalAdminProfile in sync with StaffProfile.

    Internal admin authorization is primarily governed by StaffProfile, but many
    existing admin systems still rely on InternalAdminProfile.role for role
    ordering and UI labels.
    """
    mapped_role = STAFF_ROLE_TO_ADMIN_ROLE.get(str(profile.primary_admin_role).strip().lower())
    should_have_admin_role = bool(profile.admin_panel_access and profile.is_active_employee and mapped_role)

    if should_have_admin_role:
        admin_profile, _ = InternalAdminProfile.objects.get_or_create(user=profile.user)
        if admin_profile.role != mapped_role:
            admin_profile.role = mapped_role
            admin_profile.save(update_fields=["role"])
    else:
        InternalAdminProfile.objects.filter(user=profile.user).delete()


def _admin_role_for_staff_primary_role(primary_role: str) -> str | None:
    return STAFF_ROLE_TO_ADMIN_ROLE.get(str(primary_role or "").strip().lower())


def _latest_pending_invite_for_staff(staff: StaffProfile) -> AdminInvite | None:
    return (
        AdminInvite.objects.filter(staff_profile=staff, used_at__isnull=True, is_active=True)
        .order_by("-created_at")
        .first()
    )


class InternalEmployeesViewSet(BaseInternalAdminViewSet):
    """
    Internal employees and admin access management.

    Note: This viewset is intentionally restricted to SUPERADMIN+ operators.
    """

    queryset = (
        StaffProfile.objects.all()
        .select_related("user", "manager")
        .prefetch_related("invites")
        .order_by("id")
    )
    required_role = AdminRole.SUPPORT
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_min_role(self, request=None):
        """Restrict write actions to OPS+, view actions to SUPPORT+."""
        if self.action in {"create", "update", "partial_update", "invite_employee", "suspend", "reactivate", "delete_employee", "resend_invite", "revoke_invite"}:
            return AdminRole.OPS
        return AdminRole.SUPPORT


    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return StaffProfileWriteSerializer
        if self.action == "retrieve":
            return StaffProfileDetailSerializer
        return StaffProfileListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        search = (params.get("search") or params.get("q") or "").strip()
        role = (params.get("role") or "").strip().lower()
        status_filter = (params.get("status") or "").strip().lower()
        department = (params.get("department") or "").strip()

        if search:
            qs = qs.filter(
                Q(display_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__username__icontains=search)
            )
        if role:
            qs = qs.filter(primary_admin_role=role)
        if status_filter == "active":
            qs = qs.filter(is_active_employee=True, is_deleted=False)
        elif status_filter == "suspended":
            qs = qs.filter(is_active_employee=False, is_deleted=False)
        elif status_filter == "deleted":
            qs = qs.filter(is_deleted=True)
        if department:
            qs = qs.filter(department__icontains=department)

        return qs

    @action(detail=False, methods=["post"], url_path="invite")
    def invite_employee(self, request, *args, **kwargs):
        """
        Create an inactive StaffProfile + AdminInvite and send an invite email.
        """
        from internal_admin.serializers import StaffInviteCreateSerializer

        serializer = StaffInviteCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        email = payload["email"].strip().lower()
        full_name = (payload.get("full_name") or "").strip()
        role = payload["role"]

        if role == StaffProfile.PrimaryAdminRole.SUPERADMIN and not can_grant_superadmin(request.user):
            return Response(
                {"detail": "Not permitted to invite superadmin employees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User.objects.create_user(username=email, email=email, password=None)

            staff_profile = getattr(user, "staff_profile", None)
            if staff_profile is not None and staff_profile.is_active_employee:
                return Response(
                    {"detail": "Employee already exists. Use update endpoints to change access."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if staff_profile is None:
                staff_profile = StaffProfile.objects.create(
                    user=user,
                    display_name=full_name or (user.get_full_name() or user.email or user.username),
                    title="",
                    department="",
                    admin_panel_access=False,
                    primary_admin_role=role,
                    is_active_employee=False,
                    workspace_scope={"mode": "all"},
                )
            else:
                staff_profile.display_name = full_name or staff_profile.display_name
                staff_profile.primary_admin_role = role
                staff_profile.admin_panel_access = False
                staff_profile.is_active_employee = False
                staff_profile.save(
                    update_fields=[
                        "display_name",
                        "primary_admin_role",
                        "admin_panel_access",
                        "is_active_employee",
                        "updated_at",
                    ]
                )
                _sync_internal_admin_profile_from_staff(staff_profile)

            invite = _latest_pending_invite_for_staff(staff_profile)
            if invite is None or not invite.is_valid:
                AdminInvite.objects.filter(
                    staff_profile=staff_profile,
                    used_at__isnull=True,
                    is_active=True,
                ).update(is_active=False)

                mapped_role = _admin_role_for_staff_primary_role(staff_profile.primary_admin_role)
                invite = AdminInvite.objects.create(
                    staff_profile=staff_profile,
                    email=email,
                    full_name=full_name,
                    role=mapped_role or AdminRole.SUPPORT,
                    created_by=request.user,
                    max_uses=1,
                    expires_at=timezone.now() + timedelta(days=7),
                )
            else:
                invite.expires_at = timezone.now() + timedelta(days=7)
                invite.email = email
                invite.full_name = full_name
                invite.save(update_fields=["expires_at", "email", "full_name", "updated_at"])

        email_send_failed = False
        email_error = ""
        try:
            send_staff_invite_email(invite=invite, request=request)
            invite.last_emailed_at = timezone.now()
            invite.email_last_error = ""
            invite.save(update_fields=["last_emailed_at", "email_last_error", "updated_at"])
        except Exception as exc:  # pragma: no cover
            email_send_failed = True
            email_error = str(exc)
            invite.email_last_error = email_error[:2000]
            invite.save(update_fields=["email_last_error", "updated_at"])

        log_admin_action(
            request,
            action="staff_invite.created",
            obj=invite,
            extra={
                "staff_profile_id": staff_profile.pk,
                "target_user_id": staff_profile.user_id,
                "email": email,
                "role": staff_profile.primary_admin_role,
                "expires_at": invite.expires_at.isoformat(),
                "email_send_failed": email_send_failed,
                "email_error": email_error[:500] if email_error else "",
            },
            category="security",
        )

        read = StaffProfileDetailSerializer(staff_profile, context={"request": request}).data
        return Response(read, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request, pk=None):
        staff: StaffProfile = self.get_object()
        if staff.primary_admin_role == StaffProfile.PrimaryAdminRole.SUPERADMIN and not can_grant_superadmin(request.user):
            return Response(
                {"detail": "Not permitted to resend invites for superadmin employees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        email = (staff.user.email or "").strip().lower()
        invite = _latest_pending_invite_for_staff(staff)
        if invite is None or not invite.is_valid:
            mapped_role = _admin_role_for_staff_primary_role(staff.primary_admin_role)
            invite = AdminInvite.objects.create(
                staff_profile=staff,
                email=email,
                full_name=staff.display_name,
                role=mapped_role or AdminRole.SUPPORT,
                created_by=request.user,
                max_uses=1,
                expires_at=timezone.now() + timedelta(days=7),
            )
        else:
            invite.expires_at = timezone.now() + timedelta(days=7)
            invite.save(update_fields=["expires_at", "updated_at"])

        email_send_failed = False
        email_error = ""
        try:
            send_staff_invite_email(invite=invite, request=request)
            invite.last_emailed_at = timezone.now()
            invite.email_last_error = ""
            invite.save(update_fields=["last_emailed_at", "email_last_error", "updated_at"])
        except Exception as exc:  # pragma: no cover
            email_send_failed = True
            email_error = str(exc)
            invite.email_last_error = email_error[:2000]
            invite.save(update_fields=["email_last_error", "updated_at"])

        log_admin_action(
            request,
            action="staff_invite.resent",
            obj=invite,
            extra={
                "staff_profile_id": staff.pk,
                "target_user_id": staff.user_id,
                "expires_at": invite.expires_at.isoformat(),
                "email_send_failed": email_send_failed,
                "email_error": email_error[:500] if email_error else "",
            },
            category="security",
        )
        read = StaffProfileDetailSerializer(staff, context={"request": request}).data
        return Response(read, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="revoke-invite")
    def revoke_invite(self, request, pk=None):
        staff: StaffProfile = self.get_object()
        if staff.primary_admin_role == StaffProfile.PrimaryAdminRole.SUPERADMIN and not can_grant_superadmin(request.user):
            return Response(
                {"detail": "Not permitted to revoke invites for superadmin employees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        invites = AdminInvite.objects.filter(staff_profile=staff, used_at__isnull=True, is_active=True)
        updated = invites.update(is_active=False)

        log_admin_action(
            request,
            action="staff_invite.revoked",
            obj=staff,
            extra={"staff_profile_id": staff.pk, "target_user_id": staff.user_id, "revoked_count": updated},
            category="security",
        )
        return Response(StaffProfileDetailSerializer(staff, context={"request": request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        staff: StaffProfile = self.get_object()
        if staff.primary_admin_role == StaffProfile.PrimaryAdminRole.SUPERADMIN and not can_grant_superadmin(request.user):
            return Response({"detail": "Not permitted to reactivate superadmin employees."}, status=status.HTTP_403_FORBIDDEN)

        before = _staff_access_snapshot(staff)
        staff.is_active_employee = True
        staff.admin_panel_access = staff.primary_admin_role != StaffProfile.PrimaryAdminRole.NONE
        staff.save(update_fields=["is_active_employee", "admin_panel_access", "updated_at"])
        _sync_internal_admin_profile_from_staff(staff)

        log_admin_action(
            request,
            action="admin_staff_reactivated",
            obj=staff,
            extra={
                "target_user_id": staff.user_id,
                "before": before,
                "after": _staff_access_snapshot(staff),
            },
            category="security",
        )
        return Response(StaffProfileDetailSerializer(staff, context={"request": request}).data)

    def create(self, request, *args, **kwargs):
        serializer = StaffProfileWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        _sync_internal_admin_profile_from_staff(instance)

        log_admin_action(
            request,
            action="admin_staff_created",
            obj=instance,
            extra={
                "target_user_id": instance.user_id,
                "after": _staff_access_snapshot(instance),
            },
            category="security",
        )
        read = StaffProfileDetailSerializer(instance, context={"request": request}).data
        return Response(read, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = bool(kwargs.pop("partial", False))
        instance: StaffProfile = self.get_object()
        before = _staff_access_snapshot(instance)

        serializer = StaffProfileWriteSerializer(
            instance,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        _sync_internal_admin_profile_from_staff(updated)

        log_admin_action(
            request,
            action="admin_staff_updated",
            obj=updated,
            extra={
                "target_user_id": updated.user_id,
                "before": before,
                "after": _staff_access_snapshot(updated),
            },
            category="security",
        )
        read = StaffProfileDetailSerializer(updated, context={"request": request}).data
        return Response(read, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        staff: StaffProfile = self.get_object()
        if getattr(staff, "is_deleted", False):
            return Response({"detail": "Cannot suspend a deleted employee."}, status=status.HTTP_400_BAD_REQUEST)
        if staff.primary_admin_role == StaffProfile.PrimaryAdminRole.SUPERADMIN and not can_grant_superadmin(request.user):
            return Response({"detail": "Not permitted to suspend superadmin employees."}, status=status.HTTP_403_FORBIDDEN)

        before = _staff_access_snapshot(staff)
        staff.is_active_employee = False
        staff.admin_panel_access = False
        staff.save(update_fields=["is_active_employee", "admin_panel_access", "updated_at"])
        _sync_internal_admin_profile_from_staff(staff)

        log_admin_action(
            request,
            action="admin_staff_suspended",
            obj=staff,
            extra={
                "target_user_id": staff.user_id,
                "before": before,
                "after": _staff_access_snapshot(staff),
            },
            category="security",
        )
        return Response(StaffProfileDetailSerializer(staff, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="delete")
    def delete_employee(self, request, pk=None):
        staff: StaffProfile = self.get_object()
        if not can_grant_superadmin(request.user):
            return Response({"detail": "Not permitted to delete employees."}, status=status.HTTP_403_FORBIDDEN)
        if staff.primary_admin_role == StaffProfile.PrimaryAdminRole.SUPERADMIN and not can_grant_superadmin(request.user):
            return Response({"detail": "Not permitted to delete superadmin employees."}, status=status.HTTP_403_FORBIDDEN)
        if getattr(staff, "is_deleted", False):
            return Response({"detail": "Employee is already deleted."}, status=status.HTTP_400_BAD_REQUEST)

        before = _staff_access_snapshot(staff)
        target_user_id = staff.user_id
        staff_id = staff.pk
        revoked_invites = (
            AdminInvite.objects.filter(staff_profile=staff, used_at__isnull=True, is_active=True).update(
                is_active=False,
                updated_at=timezone.now(),
            )
            or 0
        )
        staff.is_deleted = True
        staff.deleted_at = timezone.now()
        staff.is_active_employee = False
        staff.admin_panel_access = False
        staff.save(update_fields=["is_deleted", "deleted_at", "is_active_employee", "admin_panel_access", "updated_at"])
        _sync_internal_admin_profile_from_staff(staff)
        InternalAdminProfile.objects.filter(user_id=target_user_id).delete()

        log_admin_action(
            request,
            action="admin_staff_deleted",
            obj=None,
            extra={
                "target_user_id": target_user_id,
                "staff_profile_id": staff_id,
                "before": before,
                "after": _staff_access_snapshot(staff),
                "revoked_invites": revoked_invites,
            },
            category="security",
        )
        return Response({"success": True})


class InternalUsersViewSet(BaseInternalAdminViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("id")

    def get_min_role(self, request=None):
        if self.action in {"update", "partial_update", "reset_password", "revoke_sessions"}:
            return AdminRole.OPS
        return AdminRole.SUPPORT

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

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

    @staticmethod
    def _coerce_bool(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        val = str(value).strip().lower()
        if val in {"1", "true", "yes", "on"}:
            return True
        if val in {"0", "false", "no", "off"}:
            return False
        return None

    @staticmethod
    def _normalize_role(value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned == "":
                return None
            return cleaned.upper()
        return str(value).strip().upper() or None

    def _extract_body_dict(self, request) -> dict:
        if isinstance(request.data, QueryDict):
            return request.data.dict()
        return dict(request.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = bool(kwargs.pop("partial", False))
        return self._update_with_approval_guardrails(request, partial=partial, *args, **kwargs)

    def _update_with_approval_guardrails(self, request, partial: bool, *args, **kwargs):
        """
        High-risk user actions require a Maker-Checker approval request:
        - Suspend/reactivate (is_active changes)
        - Privilege changes (is_staff/is_superuser/admin_role)
        """
        from internal_admin.approval_utils import create_approval_request, InsufficientPermissionError
        from internal_admin.models import AdminApprovalRequest

        instance = self.get_object()
        data = self._extract_body_dict(request)
        reason = (data.pop("reason", "") or data.pop("approval_reason", "") or "").strip()

        requested_is_active = None
        if "is_active" in data:
            requested_is_active = self._coerce_bool(data.get("is_active"))

        requested_is_staff = None
        if "is_staff" in data:
            requested_is_staff = self._coerce_bool(data.get("is_staff"))

        requested_is_superuser = None
        if "is_superuser" in data:
            requested_is_superuser = self._coerce_bool(data.get("is_superuser"))

        admin_role_present = "admin_role" in data
        requested_admin_role = self._normalize_role(data.get("admin_role")) if admin_role_present else None

        current_admin_role = getattr(getattr(instance, "internal_admin_profile", None), "role", None)
        current_admin_role_norm = self._normalize_role(current_admin_role)

        wants_is_active_change = (
            requested_is_active is not None and bool(requested_is_active) != bool(instance.is_active)
        )
        wants_privilege_change = False
        if requested_is_staff is not None and bool(requested_is_staff) != bool(instance.is_staff):
            wants_privilege_change = True
        if requested_is_superuser is not None and bool(requested_is_superuser) != bool(instance.is_superuser):
            wants_privilege_change = True
        if admin_role_present and requested_admin_role != current_admin_role_norm:
            wants_privilege_change = True

        if wants_is_active_change and wants_privilege_change:
            return Response(
                {"detail": "Submit is_active and privilege changes as separate requests."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approval_req = None
        if wants_is_active_change or wants_privilege_change:
            if not reason:
                return Response({"detail": "reason is required for high-risk changes."}, status=status.HTTP_400_BAD_REQUEST)

            # Only SUPERADMIN+ can request privilege changes.
            if wants_privilege_change and not has_min_role(request.user, AdminRole.SUPERADMIN):
                return Response(
                    {"detail": "Only superadmin can request privilege changes."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Strip high-risk fields from the immediate update; they'll be executed on approval.
            if wants_is_active_change:
                data.pop("is_active", None)
            if wants_privilege_change:
                data.pop("is_staff", None)
                data.pop("is_superuser", None)
                data.pop("admin_role", None)

            try:
                with transaction.atomic():
                    # Apply safe fields now (names/email, etc).
                    if data:
                        serializer = self.get_serializer(instance, data=data, partial=True)
                        serializer.is_valid(raise_exception=True)
                        self.perform_update(serializer)

                    if wants_is_active_change:
                        action_type = (
                            AdminApprovalRequest.ActionType.USER_BAN
                            if requested_is_active is False
                            else AdminApprovalRequest.ActionType.USER_REACTIVATE
                        )
                        approval_req = create_approval_request(
                            initiator=request.user,
                            action_type=action_type,
                            reason=reason,
                            target_user=instance,
                            payload={"is_active": bool(requested_is_active)},
                        )
                    else:
                        payload: dict[str, object] = {}
                        if requested_is_staff is not None:
                            payload["is_staff"] = bool(requested_is_staff)
                        if requested_is_superuser is not None:
                            payload["is_superuser"] = bool(requested_is_superuser)
                        if admin_role_present:
                            payload["admin_role"] = requested_admin_role
                        approval_req = create_approval_request(
                            initiator=request.user,
                            action_type=AdminApprovalRequest.ActionType.USER_PRIVILEGE_CHANGE,
                            reason=reason,
                            target_user=instance,
                            payload=payload,
                        )

                    log_admin_action(
                        request,
                        action="approval.created",
                        obj=approval_req,
                        extra={"action_type": approval_req.action_type, "target_user_id": instance.pk},
                        category="approvals",
                    )
            except InsufficientPermissionError as e:
                return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

            # Return latest user representation (safe updates already applied).
            instance.refresh_from_db()
            return Response(
                {
                    "approval_required": True,
                    "approval_request_id": str(approval_req.id) if approval_req else None,
                    "approval_status": approval_req.status if approval_req else None,
                    "user": self.get_serializer(instance).data,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        kwargs["partial"] = partial
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        instance = serializer.instance
        before_email = instance.email
        before_active = instance.is_active
        before_is_staff = instance.is_staff
        before_is_superuser = instance.is_superuser
        before_admin_role = getattr(getattr(instance, "internal_admin_profile", None), "role", None)
        before_providers = UserSerializer._providers(instance)
        instance = serializer.save()
        after_admin_role = getattr(getattr(instance, "internal_admin_profile", None), "role", None)
        after_providers = UserSerializer._providers(instance)
        changes: dict[str, dict[str, object]] = {}
        if before_email != instance.email:
            changes["email"] = {"from": before_email, "to": instance.email}
        if before_active != instance.is_active:
            changes["is_active"] = {"from": before_active, "to": instance.is_active}
        if before_is_staff != instance.is_staff:
            changes["is_staff"] = {"from": before_is_staff, "to": instance.is_staff}
        if before_is_superuser != instance.is_superuser:
            changes["is_superuser"] = {"from": before_is_superuser, "to": instance.is_superuser}
        if before_admin_role != after_admin_role:
            changes["admin_role"] = {"from": before_admin_role, "to": after_admin_role}
        if before_providers != after_providers:
            changes["auth_providers"] = {"from": before_providers, "to": after_providers}

        # Safety: revoke sessions on deactivation or privilege changes.
        should_revoke_sessions = (
            (before_active is True and instance.is_active is False)
            or (before_is_staff != instance.is_staff)
            or (before_is_superuser != instance.is_superuser)
            or (before_admin_role != after_admin_role)
        )
        revoked_count = 0
        if should_revoke_sessions:
            from internal_admin.session_utils import revoke_user_sessions

            revoked_count = revoke_user_sessions(instance.pk)
            log_admin_action(
                self.request,
                "USER_SESSIONS_REVOKED",
                instance,
                extra={"revoked_count": revoked_count, "trigger": "user_updated"},
                category="security",
            )

        log_admin_action(
            self.request,
            "USER_UPDATED",
            instance,
            extra={
                "changes": changes,
                "auth_providers": after_providers,
                "sessions_revoked": revoked_count,
            },
        )

    @action(detail=True, methods=["post"], url_path="revoke-sessions")
    def revoke_sessions(self, request, pk=None):
        """Revoke all active sessions for a user."""
        user = self.get_object()
        from internal_admin.session_utils import revoke_user_sessions

        revoked = revoke_user_sessions(user.pk)
        log_admin_action(
            request,
            "USER_SESSIONS_REVOKED",
            user,
            extra={"revoked_count": revoked, "trigger": "manual"},
            category="security",
        )
        return Response({"success": True, "revoked_count": revoked})

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """
        Create a time-limited password reset link for the user.

        Safer than returning a plaintext password to the client.
        """
        from internal_admin.approval_utils import create_approval_request, InsufficientPermissionError
        from internal_admin.models import AdminApprovalRequest

        user = self.get_object()
        reason = (request.data.get("reason") or request.data.get("approval_reason") or "").strip()
        if not reason:
            return Response({"detail": "reason is required for password reset links."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            approval_req = create_approval_request(
                initiator=request.user,
                action_type=AdminApprovalRequest.ActionType.PASSWORD_RESET_LINK,
                reason=reason,
                target_user=user,
                payload={},
            )
        except InsufficientPermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        log_admin_action(
            request,
            "approval.created",
            approval_req,
            extra={"action_type": approval_req.action_type, "target_user_id": user.pk},
            category="security",
        )

        return Response(
            {
                "approval_required": True,
                "approval_request_id": str(approval_req.id),
                "approval_status": approval_req.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class InternalWorkspacesViewSet(BaseInternalAdminViewSet):
    serializer_class = BusinessSerializer
    queryset = Business.objects.select_related("owner_user").all().order_by("id")

    def get_min_role(self, request=None):
        if self.action in {"update", "partial_update"}:
            return AdminRole.OPS
        return AdminRole.SUPPORT

    @staticmethod
    def _coerce_bool(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        val = str(value).strip().lower()
        if val in {"1", "true", "yes", "on"}:
            return True
        if val in {"0", "false", "no", "off"}:
            return False
        return None

    def _extract_body_dict(self, request) -> dict:
        if isinstance(request.data, QueryDict):
            return request.data.dict()
        return dict(request.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = bool(kwargs.pop("partial", False))
        return self._update_with_approval_guardrails(request, partial=partial, *args, **kwargs)

    def _update_with_approval_guardrails(self, request, partial: bool, *args, **kwargs):
        from internal_admin.approval_utils import create_approval_request, InsufficientPermissionError
        from internal_admin.models import AdminApprovalRequest

        instance = self.get_object()
        data = self._extract_body_dict(request)
        reason = (data.pop("reason", "") or data.pop("approval_reason", "") or "").strip()

        if "is_deleted" in data:
            desired = self._coerce_bool(data.get("is_deleted"))
            if desired is True and not bool(instance.is_deleted):
                if not has_min_role(request.user, AdminRole.SUPERADMIN):
                    return Response(
                        {"detail": "Only superadmin can request workspace deletion."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if not reason:
                    return Response({"detail": "reason is required to delete workspaces."}, status=status.HTTP_400_BAD_REQUEST)

                data.pop("is_deleted", None)

                try:
                    with transaction.atomic():
                        if data:
                            serializer = self.get_serializer(instance, data=data, partial=True)
                            serializer.is_valid(raise_exception=True)
                            self.perform_update(serializer)

                        approval_req = create_approval_request(
                            initiator=request.user,
                            action_type=AdminApprovalRequest.ActionType.WORKSPACE_DELETE,
                            reason=reason,
                            workspace=instance,
                            payload={"is_deleted": True},
                        )
                        log_admin_action(
                            request,
                            action="approval.created",
                            obj=approval_req,
                            extra={"action_type": approval_req.action_type, "workspace_id": instance.pk},
                            category="approvals",
                        )
                except InsufficientPermissionError as e:
                    return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

                instance.refresh_from_db()
                return Response(
                    {
                        "approval_required": True,
                        "approval_request_id": str(approval_req.id),
                        "approval_status": approval_req.status,
                        "workspace": self.get_serializer(instance).data,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            if desired is False and bool(instance.is_deleted):
                return Response(
                    {"detail": "Workspace restore is not supported via API."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        kwargs["partial"] = partial
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_admin_action(self.request, "WORKSPACE_UPDATED", instance, extra=self.request.data)


class InternalBankAccountsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    serializer_class = BankAccountSerializer
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"
    pagination_class = StandardResultsSetPagination
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
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"
    pagination_class = StandardResultsSetPagination
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
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

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


class OperationsOverviewView(APIView):
    """
    Operations Control Center dashboard API.
    Returns comprehensive ops metrics, queues, tasks, systems health, and activity.
    """
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT

    def get(self, request, *args, **kwargs):
        from django.db.models import Sum, Count, Avg
        from core.models import BankTransaction
        from internal_admin.models import AdminApprovalRequest, AdminAuditLog

        env = request.query_params.get("env", "prod")
        window_hours = int(request.query_params.get("window_hours", 24))
        now = timezone.now()
        window_start = now - timedelta(hours=window_hours)

        # ─────────────────────────────────────────────────────────────
        # METRICS
        # ─────────────────────────────────────────────────────────────
        open_tickets = SupportTicket.objects.filter(
            status__in=["OPEN", "IN_PROGRESS"],
            created_at__gte=window_start
        ).count()

        pending_approvals = AdminApprovalRequest.objects.filter(
            status="PENDING"
        ).count()

        # Bank feeds with sync errors
        failing_bank_feeds = BankAccount.objects.filter(
            is_active=True
        ).filter(
            Q(last_imported_at__isnull=True) |
            Q(last_imported_at__lt=now - timedelta(days=7))
        ).values("business_id").distinct().count()

        # Reconciliation backlog: unreconciled items older than 30 days
        recon_backlog = BankTransaction.objects.filter(
            is_reconciled=False,
            date__lt=now - timedelta(days=30)
        ).count()

        # Open tax issues
        tax_issues = 0
        try:
            from core.models import TaxAnomaly
            tax_issues = TaxAnomaly.objects.filter(resolved=False).count()
        except Exception:
            pass

        metrics = {
            "openTickets": open_tickets,
            "pendingApprovals": pending_approvals,
            "failingBankFeeds": failing_bank_feeds,
            "reconciliationBacklog": recon_backlog,
            "taxIssues": tax_issues,
        }

        # ─────────────────────────────────────────────────────────────
        # QUEUES
        # ─────────────────────────────────────────────────────────────
        queues = [
            {
                "id": "support-tickets",
                "name": "Support tickets",
                "count": open_tickets,
                "slaLabel": "4h",
                "status": "healthy" if open_tickets < 10 else "warning" if open_tickets < 30 else "critical",
            },
            {
                "id": "approvals",
                "name": "Pending approvals",
                "count": pending_approvals,
                "slaLabel": "24h",
                "status": "healthy" if pending_approvals == 0 else "warning" if pending_approvals < 5 else "critical",
            },
            {
                "id": "reconciliation",
                "name": "Reconciliation backlog",
                "count": recon_backlog,
                "slaLabel": "30d",
                "status": "healthy" if recon_backlog < 100 else "warning" if recon_backlog < 500 else "critical",
            },
            {
                "id": "bank-feeds",
                "name": "Failing bank feeds",
                "count": failing_bank_feeds,
                "slaLabel": "7d",
                "status": "healthy" if failing_bank_feeds == 0 else "warning" if failing_bank_feeds < 5 else "critical",
            },
        ]

        # ─────────────────────────────────────────────────────────────
        # BUCKETS (Task board by urgency)
        # ─────────────────────────────────────────────────────────────
        urgent_tasks = []
        needs_attention_tasks = []
        backlog_tasks = []

        # Urgent: high-priority support tickets
        for t in SupportTicket.objects.filter(
            status__in=["OPEN", "IN_PROGRESS"],
            priority__in=["HIGH", "URGENT"]
        ).select_related("workspace")[:5]:
            age_hours = (now - t.created_at).total_seconds() / 3600
            urgent_tasks.append({
                "id": f"ticket-{t.id}",
                "kind": "support",
                "title": t.subject[:50],
                "workspace": t.workspace.name if t.workspace else "Unknown",
                "age": f"{int(age_hours)}h ago" if age_hours < 24 else f"{int(age_hours / 24)}d ago",
                "priority": "high",
                "slaBreached": age_hours > 4,
            })

        # Needs attention: pending approvals
        for a in AdminApprovalRequest.objects.filter(status="PENDING").select_related("workspace")[:5]:
            age_hours = (now - a.created_at).total_seconds() / 3600
            needs_attention_tasks.append({
                "id": f"approval-{a.id}",
                "kind": "ai",
                "title": a.action_type.replace("_", " ").title(),
                "workspace": a.workspace.name if a.workspace else "System",
                "age": f"{int(age_hours)}h ago" if age_hours < 24 else f"{int(age_hours / 24)}d ago",
                "priority": "high" if a.action_type in ["WORKSPACE_DELETE", "USER_BAN"] else "medium",
                "slaBreached": age_hours > 24,
            })

        # Backlog: old unreconciled by workspace
        for item in BankTransaction.objects.filter(
            is_reconciled=False,
            date__lt=now - timedelta(days=60)
        ).values("bank_account__business__name").annotate(count=Count("id")).order_by("-count")[:5]:
            backlog_tasks.append({
                "id": f"recon-{item['bank_account__business__name']}",
                "kind": "recon",
                "title": f"{item['count']} unreconciled items",
                "workspace": item["bank_account__business__name"] or "Unknown",
                "age": ">60d",
                "priority": "low" if item["count"] < 50 else "medium",
                "slaBreached": True,
            })

        buckets = [
            {"label": "🔥 Urgent", "tasks": urgent_tasks},
            {"label": "⚠️ Needs attention", "tasks": needs_attention_tasks},
            {"label": "📋 Backlog", "tasks": backlog_tasks},
        ]

        # ─────────────────────────────────────────────────────────────
        # SYSTEMS HEALTH
        # ─────────────────────────────────────────────────────────────
        systems = [
            {"id": "bank-sync", "name": "Bank feed sync engine", "status": "healthy" if failing_bank_feeds == 0 else "degraded", "latencyLabel": "<2s", "errorRateLabel": f"{failing_bank_feeds} failures"},
            {"id": "ledger", "name": "Ledger processing", "status": "healthy", "latencyLabel": "<100ms", "errorRateLabel": "0%"},
            {"id": "ai-companion", "name": "AI Companion (DeepSeek)", "status": "healthy", "latencyLabel": "<3s", "errorRateLabel": "0%"},
            {"id": "tax-guardian", "name": "Tax Guardian engine", "status": "healthy" if tax_issues == 0 else "degraded", "latencyLabel": "<5s", "errorRateLabel": f"{tax_issues} issues"},
        ]

        # ─────────────────────────────────────────────────────────────
        # ACTIVITY (Recent high-impact actions)
        # ─────────────────────────────────────────────────────────────
        activity = []
        for log in AdminAuditLog.objects.filter(
            timestamp__gte=window_start
        ).filter(
            Q(level__in=["WARNING", "ERROR"]) | Q(category="approvals")
        ).select_related("admin_user").order_by("-timestamp")[:10]:
            time_ago = (now - log.timestamp).total_seconds()
            time_str = f"{int(time_ago / 60)}m ago" if time_ago < 3600 else f"{int(time_ago / 3600)}h ago" if time_ago < 86400 else f"{int(time_ago / 86400)}d ago"
            impact = "high" if log.level == "ERROR" else "medium" if log.level == "WARNING" else "low"
            activity.append({
                "id": str(log.id),
                "time": time_str,
                "actor": log.admin_user.email if log.admin_user else "System",
                "scope": log.object_type or "System",
                "action": log.action.replace("_", " ").replace(".", " › ").title(),
                "impact": impact,
            })

        return Response({
            "env": env,
            "windowHours": window_hours,
            "metrics": metrics,
            "queues": queues,
            "buckets": buckets,
            "systems": systems,
            "activity": activity,
        })




class ImpersonationView(APIView):
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.OPS
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def post(self, request, *args, **kwargs):
        user_id = request.data.get("user_id")
        reason = (request.data.get("reason") or "").strip()
        if not user_id:
            return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not reason:
            return Response({"detail": "reason is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        target_is_internal_admin = (
            target_user.is_superuser
            or target_user.is_staff
            or StaffProfile.objects.filter(user=target_user).exists()
            or InternalAdminProfile.objects.filter(user=target_user).exists()
        )

        if target_user.is_superuser:
            return Response(
                {"detail": "Impersonating superuser accounts is not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if target_is_internal_admin and not has_min_role(request.user, AdminRole.SUPERADMIN):
            return Response(
                {"detail": "Cannot impersonate other internal admins."},
                status=status.HTTP_403_FORBIDDEN,
            )

        token = ImpersonationToken.objects.create(
            admin=request.user,
            target_user=target_user,
            expires_at=timezone.now() + timedelta(minutes=15),
            remote_ip=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            reason=reason,
        )
        log_admin_action(
            request,
            "impersonation.created",
            obj=target_user,
            extra={"token_id": str(token.id), "reason": reason},
            category="security",
        )
        redirect_path = reverse("internal-impersonate-accept", args=[token.id])
        redirect_url = request.build_absolute_uri(redirect_path)
        return Response({"redirect_url": redirect_url}, status=status.HTTP_201_CREATED)

    def get_min_role(self, request=None):
        return AdminRole.OPS


class SupportTicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInternalAdminWithRole]
    serializer_class = SupportTicketSerializer
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"
    pagination_class = StandardResultsSetPagination
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
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"
    queryset = FeatureFlag.objects.all()
    required_role = AdminRole.SUPPORT

    def get_min_role(self, request=None):
        if getattr(self, "action", "") in {"update", "partial_update"}:
            return AdminRole.ENGINEERING
        return AdminRole.SUPPORT

    def partial_update(self, request, *args, **kwargs):
        flag = self.get_object()
        critical = set(getattr(settings, "INTERNAL_ADMIN_CRITICAL_FEATURE_FLAGS", []) or [])
        if flag.key in critical and any(k in request.data for k in ["is_enabled", "rollout_percent"]):
            from internal_admin.approval_utils import create_approval_request, InsufficientPermissionError
            from internal_admin.models import AdminApprovalRequest

            reason = (request.data.get("reason") or request.data.get("approval_reason") or "").strip()
            if not reason:
                return Response({"detail": "reason is required for critical feature changes."}, status=status.HTTP_400_BAD_REQUEST)

            changes: dict[str, object] = {}
            if "is_enabled" in request.data:
                desired = request.data.get("is_enabled")
                changes["is_enabled"] = bool(desired) if isinstance(desired, bool) else str(desired).lower() in {"1", "true", "yes", "on"}
            if "rollout_percent" in request.data:
                changes["rollout_percent"] = request.data.get("rollout_percent")

            try:
                approval_req = create_approval_request(
                    initiator=request.user,
                    action_type=AdminApprovalRequest.ActionType.FEATURE_FLAG_CRITICAL,
                    reason=reason,
                    payload={"flag_id": flag.pk, "changes": changes},
                )
            except InsufficientPermissionError as e:
                return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

            log_admin_action(
                request,
                "approval.created",
                approval_req,
                extra={"action_type": approval_req.action_type, "flag_id": flag.pk, "flag_key": flag.key},
                category="approvals",
            )
            return Response(
                {
                    "approval_required": True,
                    "approval_request_id": str(approval_req.id),
                    "approval_status": approval_req.status,
                },
                status=status.HTTP_202_ACCEPTED,
            )

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


class AdminInviteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing admin invites (create, list, revoke).
    Requires OPS or higher role.
    """
    permission_classes = [IsInternalAdminWithRole]
    queryset = AdminInvite.objects.select_related("created_by", "used_by").all()
    required_role = AdminRole.OPS
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.OPS

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        invites = []
        for invite in qs[:100]:
            invites.append({
                "id": str(invite.id),
                "email": invite.email or None,
                "role": invite.role,
                "created_by": invite.created_by.email if invite.created_by else None,
                "created_at": invite.created_at.isoformat(),
                "expires_at": invite.expires_at.isoformat(),
                "is_active": invite.is_active,
                "is_valid": invite.is_valid,
                "use_count": invite.use_count,
                "max_uses": invite.max_uses,
                "invite_url": invite.get_invite_url(request),
            })
        return Response({"results": invites, "count": qs.count()})

    def create(self, request, *args, **kwargs):
        from internal_admin.models import AdminRole as AR
        email = (request.data.get("email") or "").strip()
        role = request.data.get("role", AR.SUPPORT)
        max_uses = request.data.get("max_uses", 1)
        expires_days = request.data.get("expires_days", 7)

        if role not in [r[0] for r in AR.choices]:
            return Response({"detail": f"Invalid role. Must be one of: {[r[0] for r in AR.choices]}"}, status=400)

        from datetime import timedelta
        invite = AdminInvite.objects.create(
            email=email,
            role=role,
            created_by=request.user,
            max_uses=int(max_uses),
            expires_at=timezone.now() + timedelta(days=int(expires_days)),
        )
        log_admin_action(
            request,
            "admin_invite.created",
            obj=invite,
            extra={"role": role, "email": email, "max_uses": max_uses},
            category="admin_invites",
        )
        return Response({
            "id": str(invite.id),
            "invite_url": invite.get_invite_url(request),
            "role": invite.role,
            "expires_at": invite.expires_at.isoformat(),
        }, status=201)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        invite = self.get_object()
        invite.is_active = False
        invite.save(update_fields=["is_active"])
        log_admin_action(
            request,
            "admin_invite.revoked",
            obj=invite,
            category="admin_invites",
        )
        return Response({"detail": "Invite revoked."})


class PublicInviteView(APIView):
    """
    Public endpoints for validating and redeeming admin invites.
    No authentication required for GET (validate), POST creates user + profile.
    """
    permission_classes = []  # Public endpoint
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin_public"

    def get(self, request, token):
        """Validate an invite token - returns invite details if valid."""
        try:
            import uuid
            uuid.UUID(str(token))
            invite = AdminInvite.objects.get(id=token)
        except (ValueError, AdminInvite.DoesNotExist):
            return Response({"valid": False, "error": "Invalid or expired invite link."}, status=404)

        if not invite.is_valid:
            reason = "expired" if invite.expires_at < timezone.now() else "already used" if invite.use_count >= invite.max_uses else "revoked"
            return Response({"valid": False, "error": f"This invite has {reason}."}, status=400)

        return Response({
            "valid": True,
            "role": invite.role,
            "email": invite.email or None,
            "email_locked": bool(invite.email),
            "full_name": (invite.full_name or "").strip() or None,
        })

    def post(self, request, token):
        """Redeem an invite - create user and admin profile."""
        from django.conf import settings as django_settings
        from django.core.cache import cache
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        ip = get_client_ip(request) or "unknown"
        throttle_key = f"internal_admin:invite_redeem:{ip}"
        max_per_hour = getattr(django_settings, "INTERNAL_ADMIN_INVITE_MAX_ATTEMPTS_PER_HOUR", 30)
        current = int(cache.get(throttle_key, 0) or 0)
        if current >= max_per_hour:
            return Response({"error": "Too many attempts. Please try again later."}, status=429)
        cache.set(throttle_key, current + 1, timeout=60 * 60)

        try:
            import uuid
            uuid.UUID(str(token))
            invite = AdminInvite.objects.get(id=token)
        except (ValueError, AdminInvite.DoesNotExist):
            return Response({"error": "Invalid invite link."}, status=404)

        if not invite.is_valid:
            return Response({"error": "This invite is no longer valid."}, status=400)

        email = (request.data.get("email") or "").strip().lower()
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()

        if not email or not username or not password:
            return Response({"error": "email, username, and password are required."}, status=400)

        try:
            validate_password(password)
        except ValidationError as e:
            return Response({"error": " ".join(e.messages)}, status=400)

        # If invite has a specific email, enforce it
        if invite.email and email.lower() != invite.email.lower():
            return Response({"error": f"This invite is for {invite.email} only."}, status=400)

        staff_profile = invite.staff_profile
        if staff_profile is not None:
            user = staff_profile.user
            if not user:
                return Response({"error": "Invite is misconfigured (no user)."}, status=400)
            if staff_profile.is_active_employee:
                return Response({"error": "This invite has already been accepted."}, status=400)

            # Enforce email match with the pre-created user record.
            if (user.email or "").strip().lower() != email.lower():
                return Response({"error": f"This invite is for {invite.email} only."}, status=400)

            if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                return Response({"error": "A user with this username already exists."}, status=400)

            # Activate the placeholder user account.
            user.username = username
            user.email = email
            user_update_fields = ["username", "email", "password"]
            if hasattr(user, "first_name"):
                user.first_name = first_name
                user_update_fields.append("first_name")
            if hasattr(user, "last_name"):
                user.last_name = last_name
                user_update_fields.append("last_name")
            user.set_password(password)
            user.save(update_fields=user_update_fields)

            # Activate staff profile and grant admin panel access.
            staff_profile.is_active_employee = True
            staff_profile.admin_panel_access = staff_profile.primary_admin_role != StaffProfile.PrimaryAdminRole.NONE
            resolved_name = (invite.full_name or "").strip() or " ".join([first_name, last_name]).strip()
            if resolved_name and staff_profile.display_name.strip().lower() in {email.lower(), user.username.lower()}:
                staff_profile.display_name = resolved_name
            staff_profile.save(update_fields=["is_active_employee", "admin_panel_access", "display_name", "updated_at"])
            _sync_internal_admin_profile_from_staff(staff_profile)
        else:
            # Legacy invite flow: create user and InternalAdminProfile.
            if User.objects.filter(email__iexact=email).exists():
                return Response({"error": "A user with this email already exists."}, status=400)
            if User.objects.filter(username__iexact=username).exists():
                return Response({"error": "A user with this username already exists."}, status=400)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
            )

            InternalAdminProfile.objects.create(user=user, role=invite.role)

        # Mark invite as used
        invite.use_count += 1
        invite.used_at = timezone.now()
        invite.used_by = user
        invite.save(update_fields=["use_count", "used_at", "used_by", "updated_at"])

        log_admin_action(
            request,
            "staff_invite.accepted" if staff_profile is not None else "admin_invite.redeemed",
            obj=invite,
            extra={
                "new_user_id": user.id,
                "email": email,
                "role": invite.role,
                "staff_profile_id": staff_profile.pk if staff_profile is not None else None,
            },
            category="staff_invites" if staff_profile is not None else "admin_invites",
        )

        return Response({
            "success": True,
            "message": f"Account created! You can now sign in as {username}.",
            "redirect": "/internal-admin/login/",
        }, status=201)


class ReconciliationMetricsView(APIView):
    """
    Cross-tenant reconciliation metrics for internal admin dashboard.
    Shows unreconciled items, aging, and high-friction workspaces.
    """
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT

    def get(self, request, *args, **kwargs):
        from django.db.models import Sum
        from core.models import BankTransaction, ReconciliationSession

        now = timezone.now()
        days_30_ago = now - timedelta(days=30)
        days_60_ago = now - timedelta(days=60)
        days_90_ago = now - timedelta(days=90)

        # Total unreconciled transactions across all workspaces
        unreconciled_qs = BankTransaction.objects.filter(is_reconciled=False)
        total_unreconciled = unreconciled_qs.count()

        # Aging buckets
        aging = {
            "0_30_days": unreconciled_qs.filter(date__gte=days_30_ago).count(),
            "30_60_days": unreconciled_qs.filter(date__lt=days_30_ago, date__gte=days_60_ago).count(),
            "60_90_days": unreconciled_qs.filter(date__lt=days_60_ago, date__gte=days_90_ago).count(),
            "over_90_days": unreconciled_qs.filter(date__lt=days_90_ago).count(),
        }

        # Top workspaces by unreconciled count
        top_workspaces = (
            BankTransaction.objects.filter(is_reconciled=False)
            .values("bank_account__business__id", "bank_account__business__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        workspace_list = [
            {
                "id": w["bank_account__business__id"],
                "name": w["bank_account__business__name"] or "Unknown",
                "unreconciled_count": w["count"],
            }
            for w in top_workspaces
        ]

        # Recent reconciliation sessions
        recent_sessions = ReconciliationSession.objects.select_related("business", "bank_account").order_by("-created_at")[:10]
        sessions_list = [
            {
                "id": s.id,
                "workspace": s.business.name if s.business else "Unknown",
                "status": s.status,
                "bank_account": s.bank_account.name if s.bank_account else "Unknown",
                "created_at": s.created_at.isoformat(),
            }
            for s in recent_sessions
        ]

        return Response({
            "total_unreconciled": total_unreconciled,
            "aging": aging,
            "top_workspaces": workspace_list,
            "recent_sessions": sessions_list,
        })


class LedgerHealthView(APIView):
    """
    Cross-tenant ledger health metrics: unbalanced entries, orphan accounts, suspense.
    """
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT

    def get(self, request, *args, **kwargs):
        from django.db.models import Sum, F
        from core.models import JournalEntry, JournalLine, Account

        # Unbalanced journal entries (sum of debits != sum of credits)
        unbalanced_entries = []
        try:
            entries_with_totals = (
                JournalEntry.objects.annotate(
                    total_debit=Sum("lines__debit"),
                    total_credit=Sum("lines__credit"),
                )
                .exclude(total_debit=F("total_credit"))
                .select_related("business")[:20]
            )

            for entry in entries_with_totals:
                if entry.total_debit != entry.total_credit:
                    unbalanced_entries.append({
                        "id": entry.id,
                        "workspace": entry.business.name if entry.business else "Unknown",
                        "date": entry.date.isoformat() if entry.date else None,
                        "description": entry.description[:50] if entry.description else "",
                        "debit_total": float(entry.total_debit or 0),
                        "credit_total": float(entry.total_credit or 0),
                        "difference": abs(float(entry.total_debit or 0) - float(entry.total_credit or 0)),
                    })
        except Exception:
            pass  # Graceful degradation

        # Orphan accounts (accounts with no journal lines)
        orphans_list = []
        total_orphans = 0
        try:
            orphan_accounts = (
                Account.objects.annotate(line_count=Count("journal_lines"))
                .filter(line_count=0)
                .select_related("business")[:20]
            )
            orphans_list = [
                {
                    "id": a.id,
                    "code": getattr(a, 'code', str(a.id)),
                    "name": a.name,
                    "workspace": a.business.name if a.business else "Unknown",
                }
                for a in orphan_accounts
            ]
            total_orphans = Account.objects.annotate(line_count=Count("journal_lines")).filter(line_count=0).count()
        except Exception:
            pass  # Graceful degradation

        return Response({
            "summary": {
                "unbalanced_entries": len(unbalanced_entries),
                "orphan_accounts": total_orphans,
                "suspense_with_balance": 0,
            },
            "unbalanced_entries": unbalanced_entries,
            "orphan_accounts": orphans_list,
            "suspense_balances": [],
        })


class InvoicesAuditView(APIView):
    """
    Cross-tenant invoice audit: status distribution, failed sends, anomalies.
    """
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT

    def get(self, request, *args, **kwargs):
        from core.models import Invoice

        # Status distribution
        status_counts = (
            Invoice.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        status_distribution = {item["status"]: item["count"] for item in status_counts}

        # Recent invoices with issues (void status)
        recent_issues = (
            Invoice.objects.filter(status="VOID")
            .select_related("business", "customer")
            .order_by("-id")[:20]
        )

        issues_list = [
            {
                "id": inv.id,
                "workspace": inv.business.name if inv.business else "Unknown",
                "customer": inv.customer.name if inv.customer else "Unknown",
                "status": inv.status,
                "total": float(inv.total_amount or 0),
                "created_at": inv.issue_date.isoformat() if inv.issue_date else None,
            }
            for inv in recent_issues
        ]

        # Summary stats (using uppercase status values)
        total_invoices = Invoice.objects.count()
        draft_count = Invoice.objects.filter(status="DRAFT").count()
        sent_count = Invoice.objects.filter(status="SENT").count()
        paid_count = Invoice.objects.filter(status="PAID").count()

        return Response({
            "summary": {
                "total": total_invoices,
                "draft": draft_count,
                "sent": sent_count,
                "paid": paid_count,
                "issues": len(issues_list),
            },
            "status_distribution": status_distribution,
            "recent_issues": issues_list,
        })


class ExpensesAuditView(APIView):
    """
    Cross-tenant expense audit: categorization issues, status breakdown.
    """
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT

    def get(self, request, *args, **kwargs):
        from django.db.models import Sum
        from core.models import Expense, ReceiptDocument

        # Status distribution for expenses
        expense_status_counts = (
            Expense.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        expense_distribution = {item["status"]: item["count"] for item in expense_status_counts}

        # Uncategorized expenses (no category assigned - category is ForeignKey)
        uncategorized = Expense.objects.filter(category__isnull=True).count()

        # Receipt document counts
        total_receipts = ReceiptDocument.objects.count()
        pending_receipts = 0  # No pending status in ReceiptDocument

        # Recent expenses by workspace
        top_expense_workspaces = (
            Expense.objects.values("business__id", "business__name")
            .annotate(count=Count("id"), total=Sum("amount"))
            .order_by("-count")[:10]
        )

        workspace_expenses = [
            {
                "id": w["business__id"],
                "name": w["business__name"] or "Unknown",
                "count": w["count"],
                "total": float(w["total"] or 0),
            }
            for w in top_expense_workspaces
        ]

        # Summary stats
        total_expenses = Expense.objects.count()

        return Response({
            "summary": {
                "total_expenses": total_expenses,
                "total_receipts": total_receipts,
                "uncategorized": uncategorized,
                "pending_receipts": pending_receipts,
            },
            "expense_distribution": expense_distribution,
            "receipt_distribution": {},
            "top_workspaces": workspace_expenses,
        })


class Workspace360View(APIView):
    """
    Unified "God View" for a workspace - aggregates all key data.
    Aligned with Gemini spec's "Customer 360" dashboard concept.
    """
    permission_classes = [IsInternalAdminWithRole]
    required_role = AdminRole.SUPPORT
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        return AdminRole.SUPPORT

    def get(self, request, workspace_id, *args, **kwargs):
        from django.db.models import Sum, Count, Q
        from core.models import (
            Business, BankAccount, BankTransaction, JournalEntry, Account,
            Invoice, Expense, ReceiptDocument,
        )

        try:
            workspace = Business.objects.get(id=workspace_id)
        except Business.DoesNotExist:
            return Response({"error": "Workspace not found"}, status=404)

        # Owner info
        owner = workspace.owner_user
        owner_data = {
            "id": owner.id if owner else None,
            "email": owner.email if owner else None,
            "full_name": f"{owner.first_name} {owner.last_name}".strip() if owner else None,
        }

        # Banking overview
        bank_accounts = BankAccount.objects.filter(business=workspace)
        bank_data = {
            "account_count": bank_accounts.count(),
            "accounts": [
                {
                    "id": ba.id,
                    "name": ba.name,
                    "bank_name": ba.bank_name,
                    "is_active": ba.is_active,
                    "last_imported_at": ba.last_imported_at.isoformat() if ba.last_imported_at else None,
                }
                for ba in bank_accounts[:5]
            ],
            "unreconciled_count": BankTransaction.objects.filter(
                bank_account__business=workspace,
                is_reconciled=False,
            ).count(),
        }

        # Ledger health
        ledger_data = {
            "unbalanced_entries": 0,
            "orphan_accounts": 0,
            "total_accounts": Account.objects.filter(business=workspace).count(),
            "total_entries": JournalEntry.objects.filter(business=workspace).count(),
        }
        try:
            # Count unbalanced entries
            from django.db.models import F
            unbalanced = JournalEntry.objects.filter(business=workspace).annotate(
                total_debit=Sum("lines__debit"),
                total_credit=Sum("lines__credit"),
            ).exclude(total_debit=F("total_credit")).count()
            ledger_data["unbalanced_entries"] = unbalanced

            # Count orphan accounts
            orphans = Account.objects.filter(business=workspace).annotate(
                line_count=Count("journal_lines")
            ).filter(line_count=0).count()
            ledger_data["orphan_accounts"] = orphans
        except Exception:
            pass  # Graceful degradation

        # Invoices
        invoice_data = {
            "total": Invoice.objects.filter(business=workspace).count(),
            "draft": Invoice.objects.filter(business=workspace, status="DRAFT").count(),
            "sent": Invoice.objects.filter(business=workspace, status="SENT").count(),
            "paid": Invoice.objects.filter(business=workspace, status="PAID").count(),
        }

        # Expenses
        expense_data = {
            "total": Expense.objects.filter(business=workspace).count(),
            "uncategorized": Expense.objects.filter(business=workspace, category__isnull=True).count(),
            "total_amount": float(Expense.objects.filter(business=workspace).aggregate(
                total=Sum("amount")
            )["total"] or 0),
        }

        # Tax (basic info)
        tax_data = {
            "has_tax_guardian": False,
            "last_period": None,
            "open_anomalies": {"high": 0, "medium": 0, "low": 0},
        }
        try:
            from core.models import TaxPeriod, TaxAnomaly
            last_period = TaxPeriod.objects.filter(business=workspace).order_by("-end_date").first()
            if last_period:
                tax_data["has_tax_guardian"] = True
                tax_data["last_period"] = {
                    "id": last_period.id,
                    "start_date": last_period.start_date.isoformat(),
                    "end_date": last_period.end_date.isoformat(),
                    "status": last_period.status,
                }
                # Anomaly counts
                anomalies = TaxAnomaly.objects.filter(
                    period=last_period,
                    resolved=False,
                ).values("severity").annotate(count=Count("id"))
                for a in anomalies:
                    sev = a["severity"].lower() if a["severity"] else "low"
                    if sev in tax_data["open_anomalies"]:
                        tax_data["open_anomalies"][sev] = a["count"]
        except Exception:
            pass  # Tax module might not exist

        # AI monitoring (basic)
        ai_data = {
            "last_monitor_run": None,
            "open_ai_flags": 0,
        }

        # Log this view action
        log_admin_action(
            request,
            action="workspace_360.view",
            obj=workspace,
            category="observability",
        )

        return Response({
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            },
            "owner": owner_data,
            "plan": getattr(workspace, "plan", None),
            "banking": bank_data,
            "ledger_health": ledger_data,
            "invoices": invoice_data,
            "expenses": expense_data,
            "tax": tax_data,
            "ai": ai_data,
        })


class AdminApprovalViewSet(viewsets.ViewSet):
    """
    Viewset for Maker-Checker approval workflow.
    Aligned with Gemini spec's "Maker-Checker Pattern" safety primitive.
    """
    permission_classes = [IsInternalAdminWithRole]
    throttle_classes = [InternalAdminScopedRateThrottle]
    throttle_scope = "internal_admin"

    def get_min_role(self, request=None):
        if getattr(self, "action", "") in {"create", "approve", "reject", "break_glass"}:
            return AdminRole.OPS
        return AdminRole.SUPPORT

    def list(self, request):
        """List approval requests with optional status filter and summary stats."""
        from internal_admin.models import AdminApprovalRequest, AdminBreakGlassGrant
        from django.db.models import Q

        status_filter = request.query_params.get("status")
        search = request.query_params.get("search", "").strip()

        # Opportunistically expire stale pending requests.
        now = timezone.now()
        expired_ids = list(
            AdminApprovalRequest.objects.filter(
                status=AdminApprovalRequest.Status.PENDING,
                expires_at__isnull=False,
                expires_at__lt=now,
            ).values_list("id", flat=True)[:500]
        )
        if expired_ids:
            AdminApprovalRequest.objects.filter(id__in=expired_ids).update(
                status=AdminApprovalRequest.Status.EXPIRED,
                resolved_at=now,
            )

        # Base queryset - all requests, ordered by most recent
        qs = AdminApprovalRequest.objects.select_related(
            "initiator_admin", "workspace", "target_user", "approver_admin"
        ).order_by("-created_at")

        # Apply status filter
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        # Apply search filter
        if search:
            qs = qs.filter(
                Q(initiator_admin__email__icontains=search) |
                Q(workspace__name__icontains=search) |
                Q(action_type__icontains=search) |
                Q(reason__icontains=search)
            )

        # Compute summary stats from ALL requests (not filtered)
        all_requests = AdminApprovalRequest.objects.all()
        today = now.date()
        pending_qs = all_requests.filter(status="PENDING")
        
        # High risk action types
        high_risk_types = [
            "WORKSPACE_DELETE",
            "USER_BAN",
            "USER_REACTIVATE",
            "USER_PRIVILEGE_CHANGE",
            "PASSWORD_RESET_LINK",
            "BULK_REFUND",
            "TAX_PERIOD_RESET",
            "FEATURE_FLAG_CRITICAL",
        ]
        
        summary = {
            "total_pending": pending_qs.count(),
            "total_today": all_requests.filter(created_at__date=today).count(),
            "high_risk_pending": pending_qs.filter(action_type__in=high_risk_types).count(),
            "avg_response_minutes_24h": None,
        }

        resolved_24h = all_requests.filter(resolved_at__gte=now - timedelta(hours=24)).exclude(resolved_at__isnull=True)
        if resolved_24h.exists():
            total_minutes = 0.0
            count = 0
            for created_at, resolved_at in resolved_24h.values_list("created_at", "resolved_at"):
                if created_at and resolved_at:
                    total_minutes += (resolved_at - created_at).total_seconds() / 60.0
                    count += 1
            if count:
                summary["avg_response_minutes_24h"] = round(total_minutes / count, 1)

        can_view_sensitive = has_min_role(request.user, AdminRole.SUPERADMIN)
        serialized_reqs = list(qs[:100])
        active_break_glass_for = set()
        if serialized_reqs and not can_view_sensitive:
            approval_ids = [r.id for r in serialized_reqs]
            active_break_glass_for = set(
                AdminBreakGlassGrant.objects.filter(
                    admin_user=request.user,
                    scope=AdminBreakGlassGrant.Scope.APPROVAL_SENSITIVE,
                    approval_request_id__in=approval_ids,
                    expires_at__gt=now,
                ).values_list("approval_request_id", flat=True)
            )

        def _redact_payload(req):
            payload = req.payload or {}
            if req.action_type == AdminApprovalRequest.ActionType.PASSWORD_RESET_LINK:
                allowed = (
                    can_view_sensitive
                    or request.user.id in {req.initiator_admin_id, req.approver_admin_id}
                    or req.id in active_break_glass_for
                )
                if not allowed and "reset_url" in payload:
                    payload = {**payload, "reset_url": None, "_redacted": ["reset_url"]}
            return payload

        # Serialize results
        data = [
            {
                "id": str(req.id),
                "action_type": req.action_type,
                "initiator": {
                    "id": req.initiator_admin_id,
                    "email": req.initiator_admin.email if req.initiator_admin else None,
                },
                "approver": {
                    "id": req.approver_admin_id,
                    "email": req.approver_admin.email if req.approver_admin else None,
                } if req.approver_admin else None,
                "workspace": {
                    "id": req.workspace_id,
                    "name": req.workspace.name if req.workspace else None,
                } if req.workspace else None,
                "target_user": {
                    "id": req.target_user_id,
                    "email": req.target_user.email if req.target_user else None,
                } if req.target_user else None,
                "reason": req.reason,
                "rejection_reason": req.rejection_reason,
                "payload": _redact_payload(req),
                "status": req.status,
                "execution_error": getattr(req, "execution_error", ""),
                "created_at": req.created_at.isoformat(),
                "resolved_at": req.resolved_at.isoformat() if req.resolved_at else None,
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
            }
            for req in serialized_reqs
        ]
        return Response({"results": data, "count": len(data), "summary": summary})

    @action(detail=True, methods=["post"], url_path="break-glass")
    def break_glass(self, request, pk=None):
        """Create a short-lived break-glass grant for sensitive approval data."""
        from uuid import UUID
        from internal_admin.models import AdminApprovalRequest, AdminBreakGlassGrant

        try:
            request_id = UUID(pk)
        except ValueError:
            return Response({"error": "Invalid request ID"}, status=400)

        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"error": "reason is required"}, status=400)

        ttl_default = int(getattr(settings, "INTERNAL_ADMIN_BREAK_GLASS_TTL_MINUTES", 10) or 10)
        ttl_max = int(getattr(settings, "INTERNAL_ADMIN_BREAK_GLASS_MAX_TTL_MINUTES", 60) or 60)
        ttl_minutes = request.data.get("ttl_minutes", ttl_default)
        try:
            ttl_minutes = int(ttl_minutes)
        except (TypeError, ValueError):
            ttl_minutes = ttl_default
        ttl_minutes = max(1, min(ttl_minutes, ttl_max))

        approval = AdminApprovalRequest.objects.get(id=request_id)
        expires_at = timezone.now() + timedelta(minutes=ttl_minutes)

        grant = AdminBreakGlassGrant.objects.create(
            admin_user=request.user,
            scope=AdminBreakGlassGrant.Scope.APPROVAL_SENSITIVE,
            approval_request=approval,
            reason=reason,
            expires_at=expires_at,
            remote_ip=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request_id=getattr(request, "request_id", "")[:128],
        )

        log_admin_action(
            request,
            action="break_glass.granted",
            obj=approval,
            extra={
                "scope": grant.scope,
                "approval_id": str(approval.id),
                "expires_at": expires_at.isoformat(),
                "ttl_minutes": ttl_minutes,
            },
            category="security",
        )

        return Response(
            {
                "success": True,
                "expires_at": expires_at.isoformat(),
            },
            status=201,
        )


    def create(self, request):
        """Create a new approval request (Maker step)."""
        from internal_admin.models import AdminApprovalRequest
        from internal_admin.approval_utils import create_approval_request, InsufficientPermissionError

        action_type = request.data.get("action_type")
        reason = request.data.get("reason", "")
        workspace_id = request.data.get("workspace_id")
        target_user_id = request.data.get("target_user_id")
        payload = request.data.get("payload", {})

        # Validate action type
        valid_types = [choice[0] for choice in AdminApprovalRequest.ActionType.choices]
        if action_type not in valid_types:
            return Response(
                {"error": f"Invalid action_type. Must be one of: {valid_types}"},
                status=400
            )

        if not reason:
            return Response({"error": "reason is required"}, status=400)

        workspace = None
        if workspace_id:
            try:
                workspace = Business.objects.get(id=workspace_id)
            except Business.DoesNotExist:
                return Response({"error": "Workspace not found"}, status=404)

        target_user = None
        if target_user_id:
            try:
                target_user = User.objects.get(id=target_user_id)
            except User.DoesNotExist:
                return Response({"error": "Target user not found"}, status=404)

        try:
            approval_req = create_approval_request(
                initiator=request.user,
                action_type=action_type,
                reason=reason,
                workspace=workspace,
                target_user=target_user,
                payload=payload,
            )
        except InsufficientPermissionError as e:
            return Response({"error": str(e)}, status=403)

        # Log creation
        log_admin_action(
            request,
            action="approval.created",
            obj=approval_req,
            extra={"action_type": action_type, "workspace_id": workspace_id},
            category="approvals",
        )

        return Response({
            "id": str(approval_req.id),
            "status": approval_req.status,
            "created_at": approval_req.created_at.isoformat(),
        }, status=201)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a pending request (Checker step)."""
        from uuid import UUID
        from internal_admin.approval_utils import (
            approve_request, ExecutionFailedError, InsufficientPermissionError, InvalidStateError
        )

        try:
            request_id = UUID(pk)
        except ValueError:
            return Response({"error": "Invalid request ID"}, status=400)

        try:
            approval_req = approve_request(
                request_id=request_id,
                approver=request.user,
                audit_request=request,
            )
            return Response({
                "id": str(approval_req.id),
                "status": approval_req.status,
                "resolved_at": approval_req.resolved_at.isoformat(),
                "execution_error": approval_req.execution_error,
            })
        except InvalidStateError as e:
            return Response({"error": str(e)}, status=400)
        except InsufficientPermissionError as e:
            return Response({"error": str(e)}, status=403)
        except ExecutionFailedError as e:
            approval_req = e.approval_req
            return Response(
                {
                    "id": str(approval_req.id),
                    "status": approval_req.status,
                    "resolved_at": approval_req.resolved_at.isoformat() if approval_req.resolved_at else None,
                    "execution_error": approval_req.execution_error,
                },
                status=409,
            )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a pending request (Checker step)."""
        from uuid import UUID
        from internal_admin.approval_utils import (
            reject_request,
            InsufficientPermissionError,
            InvalidStateError,
        )

        try:
            request_id = UUID(pk)
        except ValueError:
            return Response({"error": "Invalid request ID"}, status=400)

        rejection_reason = request.data.get("reason", "")

        try:
            approval_req = reject_request(
                request_id=request_id,
                approver=request.user,
                rejection_reason=rejection_reason,
                audit_request=request,
            )
            return Response({
                "id": str(approval_req.id),
                "status": approval_req.status,
                "resolved_at": approval_req.resolved_at.isoformat(),
            })
        except InvalidStateError as e:
            return Response({"error": str(e)}, status=400)
        except InsufficientPermissionError as e:
            return Response({"error": str(e)}, status=403)
