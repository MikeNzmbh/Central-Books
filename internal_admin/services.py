from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import BankTransaction, Business

User = get_user_model()


def compute_overview_metrics() -> Dict[str, Any]:
    """
    Pure function that returns the overview metrics payload used by the internal admin UI.
    """
    now = timezone.now()
    users_qs = User.objects.all()
    active_30d = users_qs.filter(last_login__gte=now - timedelta(days=30)).count()
    unreconciled_tx = BankTransaction.objects.filter(is_reconciled=False).count()
    unreconciled_over_60 = BankTransaction.objects.filter(
        is_reconciled=False, date__lte=now.date() - timedelta(days=60)
    ).count()
    unbalanced_journal_entries = 0
    error_rate_pct = 0.0
    p95_ms = 0
    ai_issues = 0
    failed_invoice_emails = 0

    workspace_health = []
    business_qs = Business.objects.select_related("owner_user").all()
    for business in business_qs[:10]:
        unreconciled_count = business.bank_accounts.filter(
            bank_transactions__is_reconciled=False
        ).count()
        ledger_status = "balanced"
        if unbalanced_journal_entries > 0:
            ledger_status = "attention"
        workspace_health.append(
            {
                "id": business.id,
                "name": business.name,
                "owner_email": business.owner_user.email if business.owner_user else "",
                "plan": business.plan,
                "unreconciled_count": unreconciled_count,
                "ledger_status": ledger_status,
            }
        )

    return {
        "active_users_30d": active_30d,
        "active_users_30d_change_pct": 0.0,
        "unreconciled_transactions": unreconciled_tx,
        "unreconciled_transactions_older_60d": unreconciled_over_60,
        "unbalanced_journal_entries": unbalanced_journal_entries,
        "api_error_rate_1h_pct": error_rate_pct,
        "api_p95_response_ms_1h": p95_ms,
        "ai_flagged_open_issues": ai_issues,
        "failed_invoice_emails_24h": failed_invoice_emails,
        "workspaces_health": workspace_health,
    }
