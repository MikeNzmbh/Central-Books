from django.urls import path

from .views import (
    CompanionActionApplyView,
    CompanionActionDismissView,
    CompanionActionsView,
    CompanionInsightDismissView,
    CompanionContextSeenView,
    CompanionOverviewView,
)


app_name = "companion"

urlpatterns = [
    path("overview/", CompanionOverviewView.as_view(), name="overview"),
    path("insights/<int:pk>/dismiss/", CompanionInsightDismissView.as_view(), name="dismiss_insight"),
    path("actions/", CompanionActionsView.as_view(), name="actions"),
    path("actions/<int:pk>/apply/", CompanionActionApplyView.as_view(), name="apply_action"),
    path("actions/<int:pk>/dismiss/", CompanionActionDismissView.as_view(), name="dismiss_action"),
    path("context-seen/", CompanionContextSeenView.as_view(), name="context_seen"),
]
