import logging
import uuid
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponseForbidden


oauth_logger = logging.getLogger("oauth.google")


class RequestIDMiddleware:
    """
    Ensure every request has a stable request ID for correlation.

    - Accepts incoming `X-Request-ID` when present (up to 128 chars).
    - Generates a UUID4 hex when missing/invalid.
    - Exposes it as `request.request_id` and returns it as `X-Request-ID` response header.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = (request.META.get("HTTP_X_REQUEST_ID") or "").strip()
        if not request_id or len(request_id) > 128:
            request_id = uuid.uuid4().hex

        setattr(request, "request_id", request_id)
        response = self.get_response(request)

        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request_id
        return response


class CorsMiddleware:
    """
    Minimal CORS handler for API endpoints.

    Allows configured frontend origins to access /api/* with credentials.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        origin = request.META.get("HTTP_ORIGIN", "")
        if not origin or not request.path.startswith("/api/"):
            return self.get_response(request)

        allowed_origins = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        if origin not in allowed_origins:
            return self.get_response(request)

        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            request.META.get("HTTP_ACCESS_CONTROL_REQUEST_HEADERS")
            or "Authorization, Content-Type, X-CSRFToken, X-Requested-With, X-Request-ID"
        )
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
        return response


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


class AdminMutationAuditMiddleware:
    """
    Log admin mutations for an audit trail.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path.startswith(
            ("/api/admin/", "/api/internal-admin/")
        ):
            try:
                from internal_admin.utils import log_admin_action

                log_admin_action(
                    request,
                    action="admin_api.mutation",
                    obj=None,
                    extra={
                        "path": request.path,
                        "method": request.method,
                        "status_code": response.status_code,
                    },
                    category="admin_api",
                )
            except Exception:
                pass

        return response
