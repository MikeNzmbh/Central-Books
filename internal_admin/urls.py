from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminAuditLogViewSet,
    AdminInviteViewSet,
    AdminApprovalViewSet,
    AdminAISettingsView,
    AdminIntegrityReportsView,
    ExpensesAuditView,
    FeatureFlagViewSet,
    ImpersonationView,
    InternalEmployeesViewSet,
    InternalBankAccountsViewSet,
    InternalUsersViewSet,
    InternalWorkspacesViewSet,
    InvoicesAuditView,
    LedgerHealthView,
    OperationsOverviewView,
    OverviewMetricsView,
    PublicInviteView,
    ReconciliationMetricsView,
    SupportTicketViewSet,
    Workspace360View,
)

router = DefaultRouter()
router.register(r"users", InternalUsersViewSet, basename="internal-users")
router.register(r"workspaces", InternalWorkspacesViewSet, basename="internal-workspaces")
router.register(r"bank-accounts", InternalBankAccountsViewSet, basename="internal-bank-accounts")
router.register(r"employees", InternalEmployeesViewSet, basename="internal-employees")
router.register(r"audit-log", AdminAuditLogViewSet, basename="internal-audit-log")
router.register(r"support-tickets", SupportTicketViewSet, basename="support-tickets")
router.register(r"feature-flags", FeatureFlagViewSet, basename="feature-flags")
router.register(r"invites", AdminInviteViewSet, basename="internal-invites")
router.register(r"approvals", AdminApprovalViewSet, basename="internal-approvals")

urlpatterns = [
    path("", include(router.urls)),
    path("overview-metrics/", OverviewMetricsView.as_view(), name="internal-overview-metrics"),
    path("operations-overview/", OperationsOverviewView.as_view(), name="internal-operations-overview"),
    path("impersonations/", ImpersonationView.as_view(), name="internal-impersonations"),
    path("ai/settings/", AdminAISettingsView.as_view(), name="internal-ai-settings"),
    path("ai/integrity-reports/", AdminIntegrityReportsView.as_view(), name="internal-ai-integrity-reports"),
    # Public invite validation/redemption (no auth required)
    path("invite/<uuid:token>/", PublicInviteView.as_view(), name="internal-invite-public"),
    # Dashboard section APIs
    path("reconciliation-metrics/", ReconciliationMetricsView.as_view(), name="internal-reconciliation-metrics"),
    path("ledger-health/", LedgerHealthView.as_view(), name="internal-ledger-health"),
    path("invoices-audit/", InvoicesAuditView.as_view(), name="internal-invoices-audit"),
    path("expenses-audit/", ExpensesAuditView.as_view(), name="internal-expenses-audit"),
    # Workspace 360 "God View"
    path("workspaces/<int:workspace_id>/overview/", Workspace360View.as_view(), name="internal-workspace-360"),
]
