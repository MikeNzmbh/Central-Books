import logging
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponse, HttpResponseForbidden


oauth_logger = logging.getLogger("oauth.google")


class GoogleOAuthLoggingMiddleware:
    """
    Lightweight middleware to log Google OAuth entry/exit in production.
    Helps debug why the flow might short-circuit on Render.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        is_google_oauth = request.path.startswith("/accounts/google/")
        if is_google_oauth:
            # Guard against missing Google configuration in production to avoid 500s from allauth
            try:
                from django.contrib.sites.models import Site
                from allauth.socialaccount.models import SocialApp

                # In allauth 65+, get_current() was removed. Use direct query instead.
                current_site = Site.objects.get_current(request)
                google_app = SocialApp.objects.filter(
                    provider="google",
                    sites=current_site
                ).first()
                if not google_app:
                    raise ValueError("No Google SocialApp configured for this site")
            except Exception as exc:
                oauth_logger.error(
                    "Google OAuth requested but SocialApp not configured; returning 503: %s",
                    str(exc),
                    extra={"path": request.path, "host": request.get_host()},
                )
                return HttpResponse(
                    "Google login is not configured for this environment. Please use email login or contact support.",
                    status=503,
                )

            oauth_logger.info(
                "Google OAuth request: path=%s host=%s next=%s state=%s user=%s",
                request.path,
                request.get_host(),
                request.GET.get("next", ""),
                request.GET.get("state", ""),
                request.user.get_username() if request.user.is_authenticated else "anonymous",
            )

        response = self.get_response(request)

        if is_google_oauth:
            oauth_logger.info(
                "Google OAuth response: path=%s status=%s redirect=%s",
                request.path,
                response.status_code,
                response.headers.get("Location", ""),
            )

        return response


class AdminSuperuserGuardMiddleware:
    """
    Restrict Django admin access to authenticated superusers while still allowing the login page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if getattr(settings, "ENABLE_DJANGO_ADMIN", True) and request.path.startswith("/admin/"):
            if request.user.is_authenticated and not request.user.is_superuser:
                return HttpResponseForbidden("Admin access is restricted to superusers.")

        return self.get_response(request)
