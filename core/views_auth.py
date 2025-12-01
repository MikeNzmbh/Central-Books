"""
Authentication API views for user state management.
"""
import json
import logging
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger("auth.state")


@require_http_methods(["GET"])
def current_user(request):
    """
    Return the current authenticated user's data.
    Used by React frontend to determine auth state and display user info.
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
    
    logger.info(
        "current_user: authenticated user_id=%s email=%s from=%s",
        user.pk,
        user.email,
        request.META.get("REMOTE_ADDR")
    )
    
    return JsonResponse({
        "authenticated": True,
        "user": user_data
    }, status=200)


@csrf_exempt
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
        
        # Django's authenticate can accept username or email
        user = authenticate(request, username=username, password=password)
        
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
