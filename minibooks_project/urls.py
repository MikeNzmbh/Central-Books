from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from core import views
from internal_admin import views_impersonation, views_auth


urlpatterns = [
    path("", include("core.urls")),
    path("internal-admin/login/", views_auth.internal_admin_login, name="internal_admin_login"),
    path("internal-admin/", views.admin_spa, name="admin_spa"),
    re_path(r"^internal-admin/.*$", views.admin_spa),  # Catch all admin sub-routes for React Router
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
    path("api/internal-admin/", include("internal_admin.urls")),
    path("accounts/", include("allauth.urls")),  # Google OAuth login
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
