"""
Bank Audit & Health Check API endpoints.

Option B Architecture: JSON-only responses, no templates.
"""
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import (
    BankAccount,
    BankTransaction,
    BankReviewRun,
    BankTransactionReview,
)
from .utils import get_current_business


def _format_currency(amount: Decimal | None, currency: str = "USD") -> str:
    """Format amount with currency symbol."""
    if amount is None:
        amount = Decimal("0.00")
    sign = "-" if amount < 0 else ""
    abs_amount = abs(amount)
    
    symbols = {"USD": "$", "CAD": "$", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency, "$")
    
    return f"{sign}{symbol}{abs_amount:,.2f}"


def _format_relative_time(dt) -> str:
    """Format datetime as relative time string."""
    if not dt:
        return "Never"
    
    now = timezone.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return "Just now"
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f"{mins} min{'s' if mins != 1 else ''} ago"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = diff.days
        return f"{days} day{'s' if days != 1 else ''} ago"


def _derive_risk_status(unreconciled_count: int, unreconciled_amount: Decimal) -> str:
    """Derive risk status based on unreconciled items."""
    if unreconciled_count == 0:
        return "low"
    elif unreconciled_count >= 5 or abs(unreconciled_amount) >= Decimal("1000"):
        return "high"
    else:
        return "medium"


def _map_transaction_status(tx_status: str, has_flags: bool = False) -> str:
    """Map BankTransaction status to UI flag status."""
    status_map = {
        "NEW": "unmatched",
        "SUGGESTED": "partial",
        "PARTIAL": "partial",
        "MATCHED_SINGLE": "matched",
        "MATCHED_MULTI": "matched",
        "LEGACY_CREATED": "matched",
        "MATCHED": "matched",
        "RECONCILED": "matched",
        "EXCLUDED": "excluded",
    }
    
    base_status = status_map.get(tx_status, "unmatched")
    
    # If transaction has audit flags from review, consider it suspicious
    if has_flags and base_status == "unmatched":
        return "suspicious"
    
    return base_status


@login_required
@require_GET
def api_bank_audit_summary(request):
    """
    Returns summary data for the Bank Audit & Health Check page.
    
    Option B compliant: JSON-only response.
    """
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    currency = business.currency or "USD"
    
    # --- 1. Bank Accounts Summary ---
    # Use same query as Banking page (api_banking_overview) - don't filter by is_active
    bank_accounts = BankAccount.objects.filter(
        business=business,
    ).select_related("account").order_by("name")
    
    banks_data = []
    insights_data: dict[str, list[dict]] = {}
    flagged_data: dict[str, list[dict]] = {}
    
    for bank in bank_accounts:
        # Count transactions
        all_txs = BankTransaction.objects.filter(bank_account=bank)
        total_count = all_txs.count()
        
        # Unreconciled = NEW or SUGGESTED status
        unreconciled_qs = all_txs.filter(
            status__in=[
                BankTransaction.TransactionStatus.NEW,
                BankTransaction.TransactionStatus.SUGGESTED,
                BankTransaction.TransactionStatus.PARTIAL,
            ]
        )
        unreconciled_count = unreconciled_qs.count()
        unreconciled_sum = unreconciled_qs.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")
        
        # Get current balance from linked ledger account
        balance = bank.current_balance
        
        # Derive risk status
        risk_status = _derive_risk_status(unreconciled_count, unreconciled_sum)
        
        bank_id = str(bank.id)
        banks_data.append({
            "id": bank_id,
            "name": bank.name,
            "last4": bank.account_number_mask or "••••",
            "currency": currency,
            "status": risk_status,
            "unreconciledCount": unreconciled_count,
            "unreconciledAmount": _format_currency(abs(unreconciled_sum), currency),
            "totalTransactions": total_count,
            "balance": _format_currency(balance, currency),
            "lastSynced": _format_relative_time(bank.last_imported_at),
        })
        
        # --- 2. Flagged Transactions for this bank ---
        # Get unreconciled transactions as flagged items
        flagged_txs = unreconciled_qs.order_by("-date", "-id")[:10]
        
        bank_flagged = []
        for tx in flagged_txs:
            # Check if this transaction has been reviewed
            review = BankTransactionReview.objects.filter(
                business=business,
                raw_payload__external_id=str(tx.id),
            ).order_by("-id").first()
            
            has_flags = bool(review and review.audit_flags)
            suggestion = ""
            confidence = 0
            
            if review:
                # Get AI suggestion from review
                if review.audit_explanations:
                    suggestion = review.audit_explanations[0] if isinstance(review.audit_explanations, list) else str(review.audit_explanations)
                elif review.audit_flags:
                    flags = review.audit_flags
                    if isinstance(flags, list) and flags:
                        suggestion = flags[0].get("message", "") if isinstance(flags[0], dict) else str(flags[0])
                
                # Confidence from audit score
                if review.audit_score is not None:
                    confidence = int(100 - float(review.audit_score))  # Invert risk score to confidence
            
            if not suggestion:
                # Default suggestions based on transaction type
                if tx.amount < 0:
                    suggestion = "Review expense categorization."
                else:
                    suggestion = "Match with corresponding invoice or receipt."
            
            if confidence == 0:
                confidence = tx.suggestion_confidence or 50
            
            bank_flagged.append({
                "id": str(tx.id),
                "date": tx.date.isoformat() if tx.date else "",
                "description": tx.description or "Unknown transaction",
                "amount": _format_currency(tx.amount, currency),
                "status": _map_transaction_status(tx.status, has_flags),
                "suggestion": suggestion[:100],  # Truncate long suggestions
                "confidence": min(100, max(0, confidence)),
            })
        
        flagged_data[bank_id] = bank_flagged
        
        # --- 3. AI Insights for this bank ---
        # Get insights from most recent bank review run
        recent_run = BankReviewRun.objects.filter(
            business=business,
            status=BankReviewRun.RunStatus.COMPLETED,
        ).order_by("-created_at").first()
        
        bank_insights = []
        if recent_run:
            # LLM explanations as insights
            if recent_run.llm_explanations:
                for i, explanation in enumerate(recent_run.llm_explanations[:3]):
                    bank_insights.append({
                        "id": f"insight-{recent_run.id}-{i}",
                        "type": "anomaly" if "unusual" in explanation.lower() or "mismatch" in explanation.lower() else "match",
                        "title": explanation[:50] + "..." if len(explanation) > 50 else explanation,
                        "description": explanation,
                    })
            
            # LLM suggested followups as optimization insights
            if recent_run.llm_suggested_followups:
                for i, followup in enumerate(recent_run.llm_suggested_followups[:2]):
                    bank_insights.append({
                        "id": f"followup-{recent_run.id}-{i}",
                        "type": "optimization",
                        "title": "Suggested Action",
                        "description": followup,
                    })
        
        insights_data[bank_id] = bank_insights
    
    # --- 4. Previous Audits History ---
    previous_runs = BankReviewRun.objects.filter(
        business=business,
    ).order_by("-created_at")[:5]
    
    previous_audits = []
    for run in previous_runs:
        # Format as month year
        date_str = run.created_at.strftime("%b %Y")
        
        # Determine status based on metrics
        high_risk = (run.metrics or {}).get("transactions_high_risk", 0)
        unreconciled = (run.metrics or {}).get("transactions_unreconciled", 0)
        
        if run.status == BankReviewRun.RunStatus.FAILED:
            status = "Failed"
            color = "text-rose-600"
        elif high_risk > 0:
            status = f"{high_risk} High Risk"
            color = "text-rose-600"
        elif unreconciled > 0:
            status = f"{unreconciled} Flags"
            color = "text-amber-600"
        else:
            status = "Clean"
            color = "text-emerald-600"
        
        previous_audits.append({
            "date": date_str,
            "status": status,
            "color": color,
        })
    
    return JsonResponse({
        "banks": banks_data,
        "insights": insights_data,
        "flaggedTransactions": flagged_data,
        "previousAudits": previous_audits,
        "companionEnabled": business.ai_companion_enabled,
    })
