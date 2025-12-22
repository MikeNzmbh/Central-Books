"""
Authentication API views for user state management.
"""
import json
import logging
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger("auth.state")


@require_http_methods(["GET"])
def current_user(request):
    """
    Return the current authenticated user's data.
    Used by React frontend to determine auth state and display user info.
    Also includes RBAC role and permissions for the active workspace.
    """
    user = request.user
    
    if not user.is_authenticated:
        logger.info("current_user: anonymous request from %s", request.META.get("REMOTE_ADDR"))
        return JsonResponse({
            "authenticated": False,
            "user": None
        }, status=200)
    
    # Get user data
    user_data = {
        "id": user.pk,
        "email": user.email,
        "username": user.username,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "fullName": user.get_full_name() or user.email or user.username,
        "isStaff": user.is_staff,
        "isSuperuser": user.is_superuser,
    }
    
    # Add internal admin information
    internal_admin_data = None
    try:
        from internal_admin.permissions import (
            can_access_admin_panel,
            can_grant_superadmin,
            can_manage_admin_users,
            get_user_admin_role,
        )

        if can_access_admin_panel(user):
            internal_admin_data = {
                "role": get_user_admin_role(user),
                "canAccessInternalAdmin": True,
                "adminPanelAccess": True,
                "canManageAdminUsers": can_manage_admin_users(user),
                "canGrantSuperadmin": can_grant_superadmin(user),
            }
    except ImportError:
        # internal_admin app not installed - allow break-glass for Django superusers.
        if user.is_superuser:
            internal_admin_data = {
                "role": "SUPERADMIN",
                "canAccessInternalAdmin": True,
                "adminPanelAccess": True,
                "canManageAdminUsers": True,
                "canGrantSuperadmin": True,
            }
    
    user_data["internalAdmin"] = internal_admin_data
    
    # RBAC: Add workspace role and permissions (v1-compatible, powered by v2 engine)
    from .utils import get_current_business
    from .permissions import get_user_permissions, get_role_info, Role
    from .permissions_engine import get_effective_permission_matrix
    
    business = get_current_business(user)
    workspace_data = None
    
    if business:
        from .models import WorkspaceMembership
        membership = WorkspaceMembership.objects.filter(
            user=user,
            business=business,
            is_active=True
        ).first()
        
        if membership and membership.is_effective:
            try:
                role = Role(membership.role)
                role_info = get_role_info(role)
            except ValueError:
                role = None
                role_info = {"label": "Unknown", "description": "", "color": "gray"}
            
            permissions = get_user_permissions(user, business)
            permission_matrix = get_effective_permission_matrix(user, business)
            
            workspace_data = {
                "businessId": business.id,
                "businessName": business.name,
                "role": membership.role,
                "roleLabel": role_info.get("label", membership.role),
                "roleDescription": role_info.get("description", ""),
                "roleColor": role_info.get("color", "gray"),
                "permissions": permissions,
                "permissionLevels": {k: v.get("level") for k, v in permission_matrix.items()},
                "isOwner": membership.role == "OWNER",
                "department": membership.department or None,
                "region": membership.region or None,
            }
    
    user_data["workspace"] = workspace_data
    
    logger.info(
        "current_user: authenticated user_id=%s email=%s role=%s from=%s",
        user.pk,
        user.email,
        workspace_data.get("role") if workspace_data else "no_workspace",
        request.META.get("REMOTE_ADDR")
    )
    
    return JsonResponse({
        "authenticated": True,
        "user": user_data
    }, status=200)


@require_http_methods(["POST"])
def api_login(request):
    """
    API endpoint for JSON-based login.
    Accepts username or email and password.
    """
    try:
        data = json.loads(request.body)
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        
        if not username or not password:
            return JsonResponse({
                "detail": "Username and password are required"
            }, status=400)
        
        # Try to authenticate with username first
        user = authenticate(request, username=username, password=password)
        
        # If that fails and input looks like an email, try to find user by email
        if user is None and "@" in username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                email_user = User.objects.get(email__iexact=username)
                user = authenticate(request, username=email_user.username, password=password)
            except User.DoesNotExist:
                pass
        
        if user is not None:
            login(request, user)
            logger.info(
                "api_login: successful login user_id=%s email=%s from=%s",
                user.pk,
                user.email,
                request.META.get("REMOTE_ADDR")
            )
            
            return JsonResponse({
                "success": True,
                "user": {
                    "id": user.pk,
                    "email": user.email,
                    "username": user.username,
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                    "fullName": user.get_full_name() or user.email or user.username,
                    "isStaff": user.is_staff,
                    "isSuperuser": user.is_superuser,
                }
            }, status=200)
        else:
            logger.warning(
                "api_login: failed login attempt username=%s from=%s",
                username,
                request.META.get("REMOTE_ADDR")
            )
            return JsonResponse({
                "detail": "Invalid credentials"
            }, status=401)
            
    except json.JSONDecodeError:
        return JsonResponse({
            "detail": "Invalid JSON"
        }, status=400)


@require_http_methods(["GET"])
def api_auth_config(request):
    """
    API endpoint for login page configuration.
    Returns CSRF token, OAuth availability, and redirect URLs.
    Option B compliant: React fetches this instead of Django template logic.
    """
    from django.middleware.csrf import get_token
    from django.contrib.sites.models import Site
    from allauth.socialaccount.models import SocialApp

    # Check if Google OAuth is configured for current site
    google_enabled = False
    google_login_url = None
    try:
        current_site = Site.objects.get_current()
        google_app = SocialApp.objects.filter(
            provider="google",
            sites=current_site
        ).first()
        if google_app:
            google_enabled = True
            google_login_url = "/accounts/google/login/"
    except Exception:
        pass  # Google OAuth not available

    # Determine next URL
    next_url = request.GET.get("next", "")
    if not next_url:
        next_url = "/dashboard"

    return JsonResponse({
        "csrfToken": get_token(request),
        "googleEnabled": google_enabled,
        "googleLoginUrl": google_login_url,
        "nextUrl": next_url,
        "loginUrl": "/api/auth/login/",
    })
