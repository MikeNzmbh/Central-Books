import logging
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect


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


class DjangoAdminSuperuserMiddleware:
    """
    Restricts /django-admin/ to authenticated superusers.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith("/django-admin/"):
            if not request.user.is_authenticated:
                login_url = settings.LOGIN_URL
                return redirect(f"{login_url}?next={request.path}")
            if not request.user.is_superuser:
                return HttpResponseForbidden("Django admin is restricted to superusers.")
        return self.get_response(request)
