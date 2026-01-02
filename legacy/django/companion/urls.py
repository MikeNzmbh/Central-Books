from django.urls import path

from .views import (
    CompanionActionApplyView,
    CompanionActionDismissView,
    CompanionActionsView,
    CompanionInsightDismissView,
    CompanionContextSeenView,
    CompanionOverviewView,
)
from .views_v2 import (
    CompanionV2AISettingsView,
    CompanionV2BusinessPolicyView,
    CompanionV2IntegrityReportsView,
    CompanionV2ProposalsView,
    CompanionV2ProposalApplyView,
    CompanionV2ProposalRejectView,
    CompanionV2ProposeBankMatchView,
    CompanionV2ProposeCategorizationView,
    CompanionV2ProvenanceLookupView,
    CompanionV2ShadowEventApplyView,
    CompanionV2ShadowEventDetailView,
    CompanionV2ShadowEventRejectView,
    CompanionV2ShadowEventsView,
    CompanionV2ShadowLedgerWipeView,
)


app_name = "companion"

urlpatterns = [
    path("overview/", CompanionOverviewView.as_view(), name="overview"),
    path("insights/<int:pk>/dismiss/", CompanionInsightDismissView.as_view(), name="dismiss_insight"),
    path("actions/", CompanionActionsView.as_view(), name="actions"),
    path("actions/<int:pk>/apply/", CompanionActionApplyView.as_view(), name="apply_action"),
    path("actions/<int:pk>/dismiss/", CompanionActionDismissView.as_view(), name="dismiss_action"),
    path("context-seen/", CompanionContextSeenView.as_view(), name="context_seen"),

    # Companion v2 (Shadow Ledger + safe accountant mode)
    path("v2/settings/", CompanionV2AISettingsView.as_view(), name="v2_settings"),
    path("v2/policy/", CompanionV2BusinessPolicyView.as_view(), name="v2_policy"),
    path("v2/proposals/", CompanionV2ProposalsView.as_view(), name="v2_proposals"),
    path("v2/proposals/<uuid:pk>/apply/", CompanionV2ProposalApplyView.as_view(), name="v2_proposal_apply"),
    path("v2/proposals/<uuid:pk>/reject/", CompanionV2ProposalRejectView.as_view(), name="v2_proposal_reject"),
    path("v2/shadow-events/", CompanionV2ShadowEventsView.as_view(), name="v2_shadow_events"),
    path("v2/shadow-events/wipe/", CompanionV2ShadowLedgerWipeView.as_view(), name="v2_shadow_wipe"),
    path("v2/shadow-events/<uuid:pk>/", CompanionV2ShadowEventDetailView.as_view(), name="v2_shadow_event_detail"),
    path("v2/shadow-events/<uuid:pk>/apply/", CompanionV2ShadowEventApplyView.as_view(), name="v2_shadow_event_apply"),
    path("v2/shadow-events/<uuid:pk>/reject/", CompanionV2ShadowEventRejectView.as_view(), name="v2_shadow_event_reject"),
    path("v2/propose/categorization/", CompanionV2ProposeCategorizationView.as_view(), name="v2_propose_categorization"),
    path("v2/propose/bank-match/", CompanionV2ProposeBankMatchView.as_view(), name="v2_propose_bank_match"),
    path("v2/provenance/", CompanionV2ProvenanceLookupView.as_view(), name="v2_provenance"),
    path("v2/integrity-reports/", CompanionV2IntegrityReportsView.as_view(), name="v2_integrity_reports"),
]
