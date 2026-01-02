"""
RBAC Membership Management API

Allows workspace owners to manage team member roles.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone

from .utils import get_current_business
from .models import WorkspaceMembership
from .permissions import (
    Role, 
    require_roles, 
    require_permission, 
    has_permission,
    get_role_info,
    ROLE_DESCRIPTIONS,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#    List & Create Memberships
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def api_memberships_list(request):
    """
    GET /api/workspace/memberships/
    
    Returns all memberships for the current workspace.
    Only accessible by OWNER and SYSTEM_ADMIN.
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    
    # Check permission
    if not has_permission(request.user, business, "users.manage_roles"):
        return JsonResponse(
            {"error": "Permission denied. Only workspace owners can manage team members."},
            status=403
        )
    
    memberships = (
        WorkspaceMembership.objects
        .filter(business=business)
        .select_related("user", "created_by")
        .order_by("-created_at")
    )
    
    data = []
    for m in memberships:
        try:
            role_info = get_role_info(Role(m.role))
        except ValueError:
            role_info = {"label": m.role, "description": "", "color": "gray"}
        
        data.append({
            "id": m.id,
            "user_id": m.user_id,
            "email": m.user.email,
            "username": m.user.username,
            "full_name": m.user.get_full_name() or m.user.email,
            "role": m.role,
            "role_label": role_info.get("label", m.role),
            "role_description": role_info.get("description", ""),
            "role_color": role_info.get("color", "gray"),
            "department": m.department or None,
            "region": m.region or None,
            "is_active": m.is_active,
            "is_effective": m.is_effective,
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
            "created_at": m.created_at.isoformat(),
            "created_by": m.created_by.email if m.created_by else None,
        })
    
    return JsonResponse({"memberships": data})


@login_required
@require_POST
def api_memberships_create(request):
    """
    POST /api/workspace/memberships/
    
    Invite a user to the workspace with a specific role.
    Only accessible by OWNER.
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "users.manage_roles"):
        return JsonResponse(
            {"error": "Permission denied. Only workspace owners can invite team members."},
            status=403
        )
    
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    email = (payload.get("email") or "").strip().lower()
    role = (payload.get("role") or "").strip().upper()
    department = (payload.get("department") or "").strip()
    region = (payload.get("region") or "").strip()
    expires_at_str = payload.get("expires_at")
    
    # Validation
    errors = {}
    
    if not email:
        errors["email"] = "Email is required."
    
    if role not in Role.values():
        errors["role"] = f"Invalid role. Must be one of: {', '.join(Role.values())}"
    
    # Cannot create another OWNER
    if role == "OWNER":
        existing_owner = WorkspaceMembership.objects.filter(
            business=business, role="OWNER"
        ).exists()
        if existing_owner:
            errors["role"] = "A workspace can only have one owner. Transfer ownership instead."
    
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    
    # Find or create user
    user = User.objects.filter(email=email).first()
    if not user:
        # Create a placeholder user (they'll need to set password on first login)
        username = email.split("@")[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User.objects.create(
            username=username,
            email=email,
            is_active=True,
        )
        logger.info("Created placeholder user for invitation: %s", email)
    
    # Check if already a member
    existing = WorkspaceMembership.objects.filter(user=user, business=business).first()
    if existing:
        return JsonResponse(
            {"error": f"User {email} is already a member of this workspace."},
            status=409
        )
    
    # Parse expires_at
    expires_at = None
    if expires_at_str:
        from django.utils.dateparse import parse_datetime
        expires_at = parse_datetime(expires_at_str)
    
    # Create membership
    membership = WorkspaceMembership.objects.create(
        user=user,
        business=business,
        role=role,
        department=department,
        region=region,
        expires_at=expires_at,
        is_active=True,
        created_by=request.user,
    )
    
    logger.info(
        "Created membership: user=%s business=%s role=%s by=%s",
        email, business.id, role, request.user.email
    )
    
    try:
        role_info = get_role_info(Role(membership.role))
    except ValueError:
        role_info = {"label": membership.role, "description": "", "color": "gray"}
    
    return JsonResponse({
        "membership": {
            "id": membership.id,
            "user_id": membership.user_id,
            "email": user.email,
            "username": user.username,
            "full_name": user.get_full_name() or user.email,
            "role": membership.role,
            "role_label": role_info.get("label", membership.role),
            "role_color": role_info.get("color", "gray"),
            "department": membership.department or None,
            "region": membership.region or None,
            "is_active": membership.is_active,
            "expires_at": membership.expires_at.isoformat() if membership.expires_at else None,
            "created_at": membership.created_at.isoformat(),
        }
    }, status=201)


# ─────────────────────────────────────────────────────────────────────────────
#    Update & Delete Memberships
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(["PATCH", "DELETE"])
def api_membership_detail(request, membership_id: int):
    """
    PATCH/DELETE /api/workspace/memberships/<id>/
    
    Update or remove a team member.
    Only accessible by OWNER.
    """
    business = get_current_business(request.user)
    if not business:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "users.manage_roles"):
        return JsonResponse(
            {"error": "Permission denied. Only workspace owners can manage team members."},
            status=403
        )
    
    membership = WorkspaceMembership.objects.filter(
        id=membership_id, business=business
    ).select_related("user").first()
    
    if not membership:
        return JsonResponse({"error": "Membership not found"}, status=404)
    
    # Cannot modify owner membership (must transfer ownership instead)
    if membership.role == "OWNER":
        return JsonResponse(
            {"error": "Cannot modify owner membership. Use transfer ownership instead."},
            status=403
        )
    
    if request.method == "DELETE":
        email = membership.user.email
        membership.delete()
        logger.info(
            "Deleted membership: user=%s business=%s by=%s",
            email, business.id, request.user.email
        )
        return JsonResponse({"status": "deleted"})
    
    # PATCH - update membership
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    updates = {}
    errors = {}
    
    if "role" in payload:
        new_role = (payload.get("role") or "").strip().upper()
        if new_role not in Role.values():
            errors["role"] = f"Invalid role. Must be one of: {', '.join(Role.values())}"
        elif new_role == "OWNER":
            errors["role"] = "Cannot promote to OWNER. Use transfer ownership instead."
        else:
            updates["role"] = new_role
    
    if "department" in payload:
        updates["department"] = (payload.get("department") or "").strip()
    
    if "region" in payload:
        updates["region"] = (payload.get("region") or "").strip()
    
    if "is_active" in payload:
        updates["is_active"] = bool(payload.get("is_active"))
    
    if "expires_at" in payload:
        expires_at_str = payload.get("expires_at")
        if expires_at_str:
            from django.utils.dateparse import parse_datetime
            updates["expires_at"] = parse_datetime(expires_at_str)
        else:
            updates["expires_at"] = None
    
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    
    for key, value in updates.items():
        setattr(membership, key, value)
    
    if updates:
        membership.save(update_fields=list(updates.keys()) + ["updated_at"])
    
    logger.info(
        "Updated membership: user=%s business=%s updates=%s by=%s",
        membership.user.email, business.id, list(updates.keys()), request.user.email
    )
    
    try:
        role_info = get_role_info(Role(membership.role))
    except ValueError:
        role_info = {"label": membership.role, "description": "", "color": "gray"}
    
    return JsonResponse({
        "membership": {
            "id": membership.id,
            "user_id": membership.user_id,
            "email": membership.user.email,
            "username": membership.user.username,
            "full_name": membership.user.get_full_name() or membership.user.email,
            "role": membership.role,
            "role_label": role_info.get("label", membership.role),
            "role_color": role_info.get("color", "gray"),
            "department": membership.department or None,
            "region": membership.region or None,
            "is_active": membership.is_active,
            "is_effective": membership.is_effective,
            "expires_at": membership.expires_at.isoformat() if membership.expires_at else None,
            "created_at": membership.created_at.isoformat(),
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
#    Available Roles (for UI dropdowns)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def api_roles_list(request):
    """
    GET /api/workspace/roles/
    
    Returns list of available roles with descriptions.
    Used by frontend for role selection dropdowns.
    """
    roles = []
    for role in Role:
        info = get_role_info(role)
        # Don't show OWNER as an assignable role
        if role == Role.OWNER:
            continue
        roles.append({
            "value": role.value,
            "label": info.get("label", role.value),
            "description": info.get("description", ""),
            "color": info.get("color", "gray"),
        })
    
    return JsonResponse({"roles": roles})
