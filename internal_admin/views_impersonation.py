from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from internal_admin.models import ImpersonationToken
from internal_admin.utils import log_admin_action

User = get_user_model()
AUTH_BACKEND = (
    settings.AUTHENTICATION_BACKENDS[0]
    if getattr(settings, "AUTHENTICATION_BACKENDS", None)
    else "django.contrib.auth.backends.ModelBackend"
)


@login_required
@require_http_methods(["GET"])
def accept_impersonation(request, token):
    try:
        impersonation = ImpersonationToken.objects.select_related("admin", "target_user").get(pk=token)
    except ImpersonationToken.DoesNotExist:
        return HttpResponse("Invalid impersonation token.", status=404)

    if request.user != impersonation.admin:
        return HttpResponseForbidden("You must be logged in as the initiating admin to accept this impersonation.")

    if (
        not impersonation.is_active
        or impersonation.used_at is not None
        or impersonation.expires_at < timezone.now()
    ):
        return HttpResponse("This impersonation link is invalid or has expired.", status=400)

    target_user = impersonation.target_user
    admin_user = impersonation.admin

    log_admin_action(
        request,
        "impersonation.accepted",
        obj=target_user,
        extra={"token_id": str(impersonation.id)},
    )

    login(request, target_user, backend=AUTH_BACKEND)
    request.session["impersonator_user_id"] = admin_user.id
    request.session["is_impersonating"] = True
    request.session["impersonated_user_id"] = target_user.id

    impersonation.is_active = False
    impersonation.used_at = timezone.now()
    impersonation.save(update_fields=["is_active", "used_at"])

    return redirect(reverse("dashboard"))


@login_required
@require_http_methods(["GET"])
def stop_impersonation(request):
    impersonator_user_id = request.session.get("impersonator_user_id")
    impersonated_user_id = request.session.get("impersonated_user_id")
    is_impersonating = request.session.get("is_impersonating")

    if not impersonator_user_id or not is_impersonating:
        return redirect(reverse("admin_spa"))

    try:
        admin_user = User.objects.get(pk=impersonator_user_id)
    except User.DoesNotExist:
        logout(request)
        return redirect(settings.LOGIN_URL)

    logout(request)
    login(request, admin_user, backend=AUTH_BACKEND)

    for key in ["is_impersonating", "impersonated_user_id", "impersonator_user_id"]:
        request.session.pop(key, None)

    log_admin_action(
        request,
        "impersonation.stopped",
        extra={
            "impersonated_user_id": impersonated_user_id,
            "restored_admin_id": admin_user.id,
        },
    )
    return redirect(reverse("admin_spa"))
