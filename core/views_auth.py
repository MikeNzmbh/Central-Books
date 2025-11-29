"""
Authentication API views for user state management.
"""
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
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
