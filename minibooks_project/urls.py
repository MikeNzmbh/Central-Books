from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.test.signals import setting_changed
from django.urls import include, path
from internal_admin import views_impersonation


def _build_urlpatterns():
    patterns = [
        path("", include("core.urls")),
        path(
            "internal/impersonate/<uuid:token>/",
            views_impersonation.accept_impersonation,
            name="internal-impersonate-accept",
        ),
        path(
            "internal/impersonate/stop/",
            views_impersonation.stop_impersonation,
            name="internal-impersonate-stop",
        ),
        path("api/companion/", include("companion.urls")),
        path("api/admin/", include("internal_admin.urls")),
        path("api/internal-admin/", include("internal_admin.urls")),
        path("accounts/", include("allauth.urls")),  # Google OAuth login
    ]

    if settings.ENABLE_DJANGO_ADMIN:
        patterns.insert(0, path("admin/", admin.site.urls))

    if settings.DEBUG:
        patterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    return patterns


urlpatterns = _build_urlpatterns()


def _reload_urlpatterns(**kwargs):
    if kwargs.get("setting") in {"ENABLE_DJANGO_ADMIN", "DEBUG"}:
        global urlpatterns
        urlpatterns = _build_urlpatterns()


setting_changed.connect(_reload_urlpatterns)
