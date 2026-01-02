from __future__ import annotations

from django.contrib.auth import authenticate, login, get_user_model
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from internal_admin.permissions import can_access_admin_panel
from internal_admin.access_policy import has_required_sso, is_ip_allowed
from core.ip_utils import get_client_ip
from internal_admin.utils import log_admin_action

User = get_user_model()


def _is_internal_admin(user: User) -> bool:
    return can_access_admin_panel(user)


@require_http_methods(["GET", "POST"])
def internal_admin_login(request):
    error = None

    # Defense-in-depth: optional IP allowlist for the login surface.
    if not is_ip_allowed(get_client_ip(request)):
        return render(
            request,
            "internal_admin/login.html",
            {"error": "Access restricted by internal admin policy."},
            status=403,
        )

    if request.method == "POST":
        # Accept username or email
        username_or_email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = None
        username = username_or_email

        # Try to authenticate with username first
        user = authenticate(request, username=username_or_email, password=password)

        # If that fails and input looks like an email, try to find user by email
        if user is None and "@" in username_or_email:
            try:
                user_obj = User.objects.get(email__iexact=username_or_email)
                username = user_obj.get_username()
                user = authenticate(request, username=username, password=password)
            except User.DoesNotExist:
                pass

        if user is not None and _is_internal_admin(user):
            if not has_required_sso(user):
                error = "SSO is required for internal admin. Please sign in with Google."
                return render(
                    request,
                    "internal_admin/login.html",
                    {
                        "error": error,
                    },
                    status=403,
                )
            login(request, user)
            # Log the admin login
            log_admin_action(request, "ADMIN_LOGIN", user, extra={"method": "password"})
            next_url = request.GET.get("next") or reverse("admin_spa")
            return redirect(next_url)
        error = "Invalid credentials or not authorized for internal admin."

    return render(
        request,
        "internal_admin/login.html",
        {
            "error": error,
        },
    )
