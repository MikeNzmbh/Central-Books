from __future__ import annotations

from django.contrib.auth import authenticate, login, get_user_model
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from internal_admin.permissions import get_user_admin_role

User = get_user_model()


def _is_internal_admin(user: User) -> bool:
    return bool(user.is_staff or get_user_admin_role(user))


@require_http_methods(["GET", "POST"])
def internal_admin_login(request):
    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = None
        username = email

        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.get_username()
        except User.DoesNotExist:
            username = email

        user = authenticate(request, username=username, password=password)
        if user is not None and _is_internal_admin(user):
            login(request, user)
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
