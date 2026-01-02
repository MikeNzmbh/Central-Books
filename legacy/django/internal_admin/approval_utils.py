"""
Approval utilities for Maker-Checker workflow.

Aligned with Gemini spec's "Maker-Checker Pattern (Dual Approval)" safety primitive.

Usage:
    from internal_admin.approval_utils import create_approval_request, approve_request, reject_request
    
    # Maker creates request
    request = create_approval_request(
        initiator=admin_user,
        action_type="TAX_PERIOD_RESET",
        workspace=workspace,
        payload={"period_id": 123},
        reason="Customer requested reset due to data import error"
    )
    
    # Checker approves
    approve_request(request.id, approver=checker_user, audit_request=http_request)
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import models
from django.http import HttpRequest
from django.utils import timezone

from core.models import Business
from .approval_actions import ApprovalExecutionError, execute_approval_request
from .models import AdminApprovalRequest, AdminRole
from .permissions import get_user_admin_role
from .utils import log_admin_action


User = get_user_model()

# Role hierarchy for approval permissions
# Higher roles can approve actions initiated by lower roles
ROLE_HIERARCHY = {
    AdminRole.SUPPORT: 1,
    AdminRole.OPS: 2,
    AdminRole.ENGINEERING: 3,
    AdminRole.SUPERADMIN: 4,
    AdminRole.PRIMARY_ADMIN: 5,
}

# Which roles can approve which action types
# None means any role higher than initiator can approve
ACTION_APPROVER_ROLES = {
    AdminApprovalRequest.ActionType.TAX_PERIOD_RESET: [
        AdminRole.OPS,
        AdminRole.ENGINEERING,
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.LEDGER_ADJUST: [
        AdminRole.OPS,
        AdminRole.ENGINEERING,
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.WORKSPACE_DELETE: [
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.BULK_REFUND: [
        AdminRole.OPS,
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.USER_BAN: [
        AdminRole.OPS,
        AdminRole.ENGINEERING,
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.USER_REACTIVATE: [
        AdminRole.OPS,
        AdminRole.ENGINEERING,
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.USER_PRIVILEGE_CHANGE: [
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.PASSWORD_RESET_LINK: [
        AdminRole.OPS,
        AdminRole.ENGINEERING,
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
    AdminApprovalRequest.ActionType.FEATURE_FLAG_CRITICAL: [
        AdminRole.SUPERADMIN,
        AdminRole.PRIMARY_ADMIN,
    ],
}

# Minimum role required to create an approval request for an action type.
ACTION_INITIATOR_MIN_ROLE = {
    AdminApprovalRequest.ActionType.TAX_PERIOD_RESET: AdminRole.OPS,
    AdminApprovalRequest.ActionType.LEDGER_ADJUST: AdminRole.OPS,
    AdminApprovalRequest.ActionType.WORKSPACE_DELETE: AdminRole.SUPERADMIN,
    AdminApprovalRequest.ActionType.BULK_REFUND: AdminRole.OPS,
    AdminApprovalRequest.ActionType.USER_BAN: AdminRole.OPS,
    AdminApprovalRequest.ActionType.USER_REACTIVATE: AdminRole.OPS,
    AdminApprovalRequest.ActionType.USER_PRIVILEGE_CHANGE: AdminRole.SUPERADMIN,
    AdminApprovalRequest.ActionType.PASSWORD_RESET_LINK: AdminRole.OPS,
    AdminApprovalRequest.ActionType.FEATURE_FLAG_CRITICAL: AdminRole.ENGINEERING,
}


class ApprovalError(Exception):
    """Base exception for approval workflow errors."""
    pass


class InsufficientPermissionError(ApprovalError):
    """User doesn't have permission to approve this action."""
    pass


class InvalidStateError(ApprovalError):
    """Request is not in a valid state for the requested operation."""
    pass


class ExecutionFailedError(ApprovalError):
    """Action execution failed while approving the request."""

    def __init__(self, message: str, approval_req: AdminApprovalRequest):
        super().__init__(message)
        self.approval_req = approval_req


def _get_user_role(user) -> str:
    """Get the admin role for a user."""
    try:
        role = get_user_admin_role(user)
        return role or ""
    except Exception:
        return ""


def _required_approver_roles(approval_req: AdminApprovalRequest) -> list[str]:
    roles = ACTION_APPROVER_ROLES.get(approval_req.action_type)
    if not roles:
        return []

    # Dynamic tightening for very sensitive privilege escalations.
    if approval_req.action_type == AdminApprovalRequest.ActionType.USER_PRIVILEGE_CHANGE:
        payload = approval_req.payload or {}
        requested_role = payload.get("admin_role")
        requested_is_superuser = payload.get("is_superuser")
        if (isinstance(requested_role, str) and requested_role.strip().upper() == AdminRole.PRIMARY_ADMIN) or bool(
            requested_is_superuser
        ):
            return [AdminRole.PRIMARY_ADMIN]

    return roles


def _can_approve(approver, approval_req: AdminApprovalRequest) -> bool:
    """
    Check if an approver can approve a specific action type.
    
    Rules:
    1. Approver cannot be the same as initiator (dual control)
    2. Approver must be in the allowed roles for this action type
    3. Approver must have equal or higher role than initiator
    """
    initiator = approval_req.initiator_admin
    if approver.id == initiator.id:
        return False  # Cannot approve own requests
    
    approver_role = _get_user_role(approver)
    initiator_role = _get_user_role(initiator)

    # Only allow approving explicitly-known action types.
    allowed_roles = _required_approver_roles(approval_req)
    if not allowed_roles:
        return False
    if approver_role not in allowed_roles:
        return False
    
    # Check role hierarchy
    approver_level = ROLE_HIERARCHY.get(approver_role, 0)
    initiator_level = ROLE_HIERARCHY.get(initiator_role, 0)
    
    return approver_level >= initiator_level


def create_approval_request(
    initiator,
    action_type: str,
    reason: str,
    workspace: Optional[Business] = None,
    target_user=None,
    payload: Optional[dict] = None,
    expires_in_hours: int = 24,
) -> AdminApprovalRequest:
    """
    Create a new approval request (Maker step).
    
    Args:
        initiator: The admin user creating the request
        action_type: One of AdminApprovalRequest.ActionType choices
        reason: Justification for the action
        workspace: Target workspace (if applicable)
        target_user: Target user (if applicable)
        payload: Action-specific data
        expires_in_hours: Hours until auto-expiry (default 24)
    
    Returns:
        Created AdminApprovalRequest instance
    """
    required_role = ACTION_INITIATOR_MIN_ROLE.get(action_type)
    if required_role is None:
        raise InsufficientPermissionError(f"Unsupported action_type: {action_type}")

    initiator_role = _get_user_role(initiator)
    if ROLE_HIERARCHY.get(initiator_role, 0) < ROLE_HIERARCHY.get(required_role, 0):
        raise InsufficientPermissionError(
            f"Role {initiator_role or 'UNKNOWN'} cannot create {action_type}; requires {required_role}"
        )

    expires_at = timezone.now() + timedelta(hours=expires_in_hours)
    
    return AdminApprovalRequest.objects.create(
        initiator_admin=initiator,
        action_type=action_type,
        workspace=workspace,
        target_user=target_user,
        payload=payload or {},
        reason=reason,
        expires_at=expires_at,
    )


def approve_request(
    request_id: UUID,
    approver,
    audit_request: Optional[HttpRequest] = None,
) -> AdminApprovalRequest:
    """
    Approve a pending request (Checker step).
    
    Args:
        request_id: UUID of the approval request
        approver: The admin user approving
        audit_request: HTTP request for audit logging (optional)
    
    Returns:
        Updated AdminApprovalRequest instance
    
    Raises:
        AdminApprovalRequest.DoesNotExist: Request not found
        InvalidStateError: Request is not pending
        InsufficientPermissionError: Approver cannot approve this action
    """
    failure_error: str | None = None
    failure_req: AdminApprovalRequest | None = None
    expired_error: str | None = None
    expired_req: AdminApprovalRequest | None = None

    with transaction.atomic():
        approval_req = (
            AdminApprovalRequest.objects.select_for_update()
            .select_related("initiator_admin", "workspace", "target_user", "approver_admin")
            .get(id=request_id)
        )

        if not approval_req.is_pending:
            raise InvalidStateError(f"Request is {approval_req.status}, not PENDING")

        if approval_req.expires_at and approval_req.expires_at < timezone.now():
            approval_req.status = AdminApprovalRequest.Status.EXPIRED
            approval_req.resolved_at = timezone.now()
            approval_req.save(update_fields=["status", "resolved_at"])
            expired_error = "Request is EXPIRED, not PENDING"
            expired_req = approval_req
        else:
            if not _can_approve(approver, approval_req):
                raise InsufficientPermissionError(
                    f"User {approver} cannot approve {approval_req.action_type}"
                )

            try:
                result = execute_approval_request(approval_req, audit_request=audit_request)
                payload = approval_req.payload or {}
                payload["result"] = {
                    **(payload.get("result") or {}),
                    **(result or {}),
                    "executed_at": timezone.now().isoformat(),
                }
                approval_req.payload = payload
                approval_req.approve(approver)
            except ApprovalExecutionError as e:
                failure_error = str(e) or "Execution failed"
                failure_req = approval_req
                payload = approval_req.payload or {}
                payload["result"] = {
                    **(payload.get("result") or {}),
                    "failed_at": timezone.now().isoformat(),
                    "error": failure_error,
                }
                approval_req.payload = payload
                approval_req.fail(approver, failure_error)

                if audit_request:
                    log_admin_action(
                        audit_request,
                        action="approval.failed",
                        obj=approval_req,
                        extra={
                            "action_type": approval_req.action_type,
                            "initiator_id": approval_req.initiator_admin_id,
                            "workspace_id": approval_req.workspace_id,
                            "error": failure_error,
                        },
                        level="ERROR",
                        category="approvals",
                    )
            else:
                # Log the approval+execution action
                if audit_request:
                    log_admin_action(
                        audit_request,
                        action="approval.approved",
                        obj=approval_req,
                        extra={
                            "action_type": approval_req.action_type,
                            "initiator_id": approval_req.initiator_admin_id,
                            "workspace_id": approval_req.workspace_id,
                        },
                        category="approvals",
                    )

    if failure_error and failure_req:
        raise ExecutionFailedError(failure_error, failure_req)

    if expired_error and expired_req:
        raise InvalidStateError(expired_error)

    return approval_req


def reject_request(
    request_id: UUID,
    approver,
    rejection_reason: str = "",
    audit_request: Optional[HttpRequest] = None,
) -> AdminApprovalRequest:
    """
    Reject a pending request (Checker step).
    
    Args:
        request_id: UUID of the approval request
        approver: The admin user rejecting
        rejection_reason: Why the request was rejected
        audit_request: HTTP request for audit logging (optional)
    
    Returns:
        Updated AdminApprovalRequest instance
    """
    expired_error: str | None = None
    expired_req: AdminApprovalRequest | None = None

    with transaction.atomic():
        approval_req = (
            AdminApprovalRequest.objects.select_for_update()
            .select_related("initiator_admin", "workspace", "target_user", "approver_admin")
            .get(id=request_id)
        )

        if not approval_req.is_pending:
            raise InvalidStateError(f"Request is {approval_req.status}, not PENDING")

        if approval_req.expires_at and approval_req.expires_at < timezone.now():
            approval_req.status = AdminApprovalRequest.Status.EXPIRED
            approval_req.resolved_at = timezone.now()
            approval_req.save(update_fields=["status", "resolved_at"])
            expired_error = "Request is EXPIRED, not PENDING"
            expired_req = approval_req
        else:
            if not _can_approve(approver, approval_req):
                raise InsufficientPermissionError(
                    f"User {approver} cannot reject {approval_req.action_type}"
                )

            approval_req.reject(approver, rejection_reason)

            # Log the rejection action
            if audit_request:
                log_admin_action(
                    audit_request,
                    action="approval.rejected",
                    obj=approval_req,
                    extra={
                        "action_type": approval_req.action_type,
                        "initiator_id": approval_req.initiator_admin_id,
                        "rejection_reason": rejection_reason,
                    },
                    category="approvals",
                )

    if expired_error and expired_req:
        raise InvalidStateError(expired_error)

    return approval_req


def get_pending_approvals(
    approver=None,
    action_type: Optional[str] = None,
) -> list[AdminApprovalRequest]:
    """
    Get pending approval requests.
    
    Args:
        approver: If provided, filter to requests this user can approve
        action_type: If provided, filter to this action type
    
    Returns:
        List of pending AdminApprovalRequest instances
    """
    qs = AdminApprovalRequest.objects.filter(
        status=AdminApprovalRequest.Status.PENDING
    )
    
    if action_type:
        qs = qs.filter(action_type=action_type)
    
    # Exclude expired requests
    qs = qs.filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
    )
    
    if approver:
        # Filter to requests this user can approve
        # For now, we return all and let the caller filter
        # A more sophisticated implementation would filter by role
        pass
    
    return list(qs.select_related("initiator_admin", "workspace", "target_user"))
