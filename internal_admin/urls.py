from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminAuditLogViewSet,
    FeatureFlagViewSet,
    ImpersonationView,
    InternalBankAccountsViewSet,
    InternalUsersViewSet,
    InternalWorkspacesViewSet,
    OverviewMetricsView,
    SupportTicketViewSet,
)

router = DefaultRouter()
router.register(r"users", InternalUsersViewSet, basename="internal-users")
router.register(r"workspaces", InternalWorkspacesViewSet, basename="internal-workspaces")
router.register(r"bank-accounts", InternalBankAccountsViewSet, basename="internal-bank-accounts")
router.register(r"audit-log", AdminAuditLogViewSet, basename="internal-audit-log")
router.register(r"support-tickets", SupportTicketViewSet, basename="support-tickets")
router.register(r"feature-flags", FeatureFlagViewSet, basename="feature-flags")

urlpatterns = [
    path("", include(router.urls)),
    path("overview-metrics/", OverviewMetricsView.as_view(), name="internal-overview-metrics"),
    path("impersonations/", ImpersonationView.as_view(), name="internal-impersonations"),
]
