from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.models import Business
from internal_admin.models import AdminApprovalRequest, FeatureFlag, InternalAdminProfile
from internal_admin.session_utils import revoke_user_sessions
from internal_admin.utils import log_admin_action


User = get_user_model()


class ApprovalExecutionError(Exception):
    pass


def execute_approval_request(
    approval_req: AdminApprovalRequest,
    *,
    audit_request=None,
) -> dict[str, Any]:
    """
    Execute the action described by an AdminApprovalRequest.

    Returns a small dict that can be merged into approval_req.payload["result"].
    """
    action = approval_req.action_type

    if action == AdminApprovalRequest.ActionType.WORKSPACE_DELETE:
        return _execute_workspace_delete(approval_req, audit_request=audit_request)
    if action == AdminApprovalRequest.ActionType.USER_BAN:
        return _execute_user_ban(approval_req, audit_request=audit_request)
    if action == AdminApprovalRequest.ActionType.USER_REACTIVATE:
        return _execute_user_reactivate(approval_req, audit_request=audit_request)
    if action == AdminApprovalRequest.ActionType.USER_PRIVILEGE_CHANGE:
        return _execute_user_privilege_change(approval_req, audit_request=audit_request)
    if action == AdminApprovalRequest.ActionType.PASSWORD_RESET_LINK:
        return _execute_password_reset_link(approval_req, audit_request=audit_request)
    if action == AdminApprovalRequest.ActionType.FEATURE_FLAG_CRITICAL:
        return _execute_feature_flag_critical(approval_req, audit_request=audit_request)
    if action == AdminApprovalRequest.ActionType.TAX_PERIOD_RESET:
        return _execute_tax_period_reset(approval_req, audit_request=audit_request)

    raise ApprovalExecutionError(f"Unsupported action_type: {action}")


def _execute_workspace_delete(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    if not approval_req.workspace_id:
        raise ApprovalExecutionError("workspace is required for WORKSPACE_DELETE")

    workspace = Business.objects.select_for_update().get(pk=approval_req.workspace_id)
    already_deleted = bool(workspace.is_deleted)
    if not already_deleted:
        workspace.is_deleted = True
        workspace.save(update_fields=["is_deleted"])

    if audit_request:
        log_admin_action(
            audit_request,
            action="workspace.deleted",
            obj=workspace,
            extra={"approval_id": str(approval_req.id), "already_deleted": already_deleted},
            category="security",
        )

    return {"workspace_id": workspace.pk, "is_deleted": True, "already_deleted": already_deleted}


def _execute_user_ban(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    if not approval_req.target_user_id:
        raise ApprovalExecutionError("target_user is required for USER_BAN")

    target = User.objects.select_for_update().get(pk=approval_req.target_user_id)
    was_active = bool(target.is_active)
    if was_active:
        target.is_active = False
        target.save(update_fields=["is_active"])

    revoked = revoke_user_sessions(target.pk)

    if audit_request:
        log_admin_action(
            audit_request,
            action="user.banned",
            obj=target,
            extra={"approval_id": str(approval_req.id), "was_active": was_active, "revoked_sessions": revoked},
            category="security",
        )

    return {"user_id": target.pk, "is_active": False, "was_active": was_active, "revoked_sessions": revoked}


def _execute_user_reactivate(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    if not approval_req.target_user_id:
        raise ApprovalExecutionError("target_user is required for USER_REACTIVATE")

    target = User.objects.select_for_update().get(pk=approval_req.target_user_id)
    was_active = bool(target.is_active)
    if not was_active:
        target.is_active = True
        target.save(update_fields=["is_active"])

    revoked = revoke_user_sessions(target.pk)

    if audit_request:
        log_admin_action(
            audit_request,
            action="user.reactivated",
            obj=target,
            extra={"approval_id": str(approval_req.id), "was_active": was_active, "revoked_sessions": revoked},
            category="security",
        )

    return {"user_id": target.pk, "is_active": True, "was_active": was_active, "revoked_sessions": revoked}


def _execute_user_privilege_change(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    if not approval_req.target_user_id:
        raise ApprovalExecutionError("target_user is required for USER_PRIVILEGE_CHANGE")

    payload = approval_req.payload or {}
    requested_is_staff = payload.get("is_staff", None)
    requested_is_superuser = payload.get("is_superuser", None)
    requested_admin_role = payload.get("admin_role", None)

    if requested_is_staff is None and requested_is_superuser is None and "admin_role" not in payload:
        raise ApprovalExecutionError("payload must include at least one of: is_staff, is_superuser, admin_role")

    target = User.objects.select_for_update().get(pk=approval_req.target_user_id)
    changes: dict[str, dict[str, Any]] = {}

    if requested_is_staff is not None and bool(requested_is_staff) != bool(target.is_staff):
        changes["is_staff"] = {"from": bool(target.is_staff), "to": bool(requested_is_staff)}
        target.is_staff = bool(requested_is_staff)

    if requested_is_superuser is not None and bool(requested_is_superuser) != bool(target.is_superuser):
        changes["is_superuser"] = {"from": bool(target.is_superuser), "to": bool(requested_is_superuser)}
        target.is_superuser = bool(requested_is_superuser)

    target.save(update_fields=["is_staff", "is_superuser"])

    # admin_role lives on InternalAdminProfile
    if "admin_role" in payload:
        before_role = getattr(getattr(target, "internal_admin_profile", None), "role", None)
        normalized_role = None
        if isinstance(requested_admin_role, str):
            normalized_role = requested_admin_role.strip().upper() or None
        elif requested_admin_role is None:
            normalized_role = None
        else:
            normalized_role = str(requested_admin_role).strip().upper() or None

        if normalized_role:
            profile, _ = InternalAdminProfile.objects.get_or_create(user=target)
            if profile.role != normalized_role:
                changes["admin_role"] = {"from": before_role, "to": normalized_role}
                profile.role = normalized_role
                profile.save(update_fields=["role"])
        else:
            if before_role is not None:
                changes["admin_role"] = {"from": before_role, "to": None}
            InternalAdminProfile.objects.filter(user=target).delete()

    revoked = revoke_user_sessions(target.pk)

    if audit_request:
        log_admin_action(
            audit_request,
            action="user.privileges_changed",
            obj=target,
            extra={"approval_id": str(approval_req.id), "changes": changes, "revoked_sessions": revoked},
            category="security",
        )

    return {"user_id": target.pk, "changes": changes, "revoked_sessions": revoked}


def _execute_password_reset_link(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    if not approval_req.target_user_id:
        raise ApprovalExecutionError("target_user is required for PASSWORD_RESET_LINK")

    target = User.objects.get(pk=approval_req.target_user_id)
    generator = PasswordResetTokenGenerator()
    uidb64 = urlsafe_base64_encode(force_bytes(target.pk))
    token = generator.make_token(target)
    path = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})

    if audit_request is not None:
        reset_url = audit_request.build_absolute_uri(path)
    else:
        base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
        reset_url = f"{base}{path}" if base else path

    approval_req.payload = {**(approval_req.payload or {}), "reset_url": reset_url, "generated_at": timezone.now().isoformat()}

    if audit_request:
        log_admin_action(
            audit_request,
            action="user.password_reset_link_created",
            obj=target,
            extra={"approval_id": str(approval_req.id)},
            category="security",
        )

    return {"user_id": target.pk, "reset_url": reset_url}


def _execute_feature_flag_critical(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    payload = approval_req.payload or {}
    flag_id = payload.get("flag_id")
    if not flag_id:
        raise ApprovalExecutionError("payload.flag_id is required for FEATURE_FLAG_CRITICAL")
    changes = payload.get("changes") or {}
    if not isinstance(changes, dict) or not changes:
        raise ApprovalExecutionError("payload.changes must be a non-empty object")

    flag = FeatureFlag.objects.select_for_update().get(pk=flag_id)
    applied: dict[str, Any] = {}

    if "is_enabled" in changes:
        flag.is_enabled = bool(changes["is_enabled"])
        applied["is_enabled"] = bool(flag.is_enabled)

    if "rollout_percent" in changes:
        try:
            rollout_int = int(changes["rollout_percent"])
        except (TypeError, ValueError):
            raise ApprovalExecutionError("rollout_percent must be an integer")
        if rollout_int < 0 or rollout_int > 100:
            raise ApprovalExecutionError("rollout_percent must be between 0 and 100")
        flag.rollout_percent = rollout_int
        applied["rollout_percent"] = rollout_int

    if not applied:
        raise ApprovalExecutionError("No recognized changes for FEATURE_FLAG_CRITICAL")

    flag.save(update_fields=list(applied.keys()) + ["updated_at"])

    if audit_request:
        log_admin_action(
            audit_request,
            action="feature_flag.critical_updated",
            obj=flag,
            extra={"approval_id": str(approval_req.id), "applied": applied},
            category="feature_flags",
        )

    return {"flag_id": flag.pk, "flag_key": flag.key, "applied": applied}


def _execute_tax_period_reset(approval_req: AdminApprovalRequest, *, audit_request=None) -> dict[str, Any]:
    if not approval_req.workspace_id:
        raise ApprovalExecutionError("workspace is required for TAX_PERIOD_RESET")

    payload = approval_req.payload or {}
    period_key = payload.get("period_key") or payload.get("period") or payload.get("key")
    snapshot_id = payload.get("snapshot_id")
    if not period_key and not snapshot_id:
        raise ApprovalExecutionError("payload must include period_key or snapshot_id for TAX_PERIOD_RESET")

    try:
        from taxes.models import TaxPeriodSnapshot
    except Exception as e:  # pragma: no cover
        raise ApprovalExecutionError("Tax module not available") from e

    with transaction.atomic():
        if snapshot_id:
            snapshot = TaxPeriodSnapshot.objects.select_for_update().get(pk=snapshot_id, business_id=approval_req.workspace_id)
        else:
            snapshot = TaxPeriodSnapshot.objects.select_for_update().get(business_id=approval_req.workspace_id, period_key=period_key)

        if snapshot.status != TaxPeriodSnapshot.SnapshotStatus.FILED:
            raise ApprovalExecutionError("Only FILED periods can be reset.")

        prev_filed_at = snapshot.filed_at
        snapshot.status = TaxPeriodSnapshot.SnapshotStatus.REVIEWED
        snapshot.filed_at = None
        snapshot.last_filed_at = prev_filed_at or snapshot.last_filed_at
        snapshot.last_reset_at = timezone.now()
        snapshot.last_reset_reason = (approval_req.reason or "")[:255]
        snapshot.save(update_fields=["status", "filed_at", "last_filed_at", "last_reset_at", "last_reset_reason"])

    if audit_request:
        log_admin_action(
            audit_request,
            action="tax.period_reset",
            obj=snapshot,
            extra={"approval_id": str(approval_req.id), "workspace_id": approval_req.workspace_id},
            category="tax",
        )

    return {"workspace_id": approval_req.workspace_id, "period_key": snapshot.period_key, "status": snapshot.status}

