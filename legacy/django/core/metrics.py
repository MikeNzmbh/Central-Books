"""
Central-Books Comprehensive Monitoring Metrics Collection

Collects real metrics across 7 business domains for AI-powered monitoring.
"""
import os
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Any
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg, F, Max, Min
from django.contrib.auth.models import User

from .models import (
    Business, Invoice, Expense, Customer, Supplier,
    JournalEntry, JournalLine, Account,
    BankAccount, BankTransaction, BankReconciliationMatch,
    ReconciliationSession, TaxRate
)


def build_central_books_metrics() -> Dict[str, Any]:
    """
    Build comprehensive metrics for Central-Books monitoring across 7 domains.
    
    Returns a dict matching the strict monitoring schema with:
    - meta: Metadata and time windows
    - product_engineering: Feature usage, deployments (placeholder)
    - ledger_accounting: Journal entries, accounts, balances
    - banking_reconciliation: Bank transactions, reconciliation status
    - tax_fx: Tax rates, invoice/expense line checks
    - business_revenue: MRR, customers, payments
    - marketing_traffic: Website analytics (placeholder)
    - support_feedback: Tickets and NPS (placeholder)
    """
    now = timezone.now()
    window_start = now - timedelta(hours=24)  # Last 24 hours
    window_end = now
    
    # Get business (single-tenant for now)
    business = Business.objects.first()
    
    if not business:
        return _empty_metrics(now, window_start, window_end)
    
    # === 1. META ===
    meta = _collect_meta(business, now, window_start, window_end)
    
    # === 2. PRODUCT & ENGINEERING ===
    product_engineering = _collect_product_engineering(business, window_start, window_end)
    
    # === 3. LEDGER & ACCOUNTING ===
    ledger_accounting = _collect_ledger_accounting(business, now)
    
    # === 4. BANKING & RECONCILIATION ===
    banking_reconciliation = _collect_banking_reconciliation(business, window_start, window_end)
    
    # === 5. TAX & FX ===
    tax_fx = _collect_tax_fx(business, window_start)
    
    # === 6. BUSINESS & REVENUE ===
    business_revenue = _collect_business_revenue(business, window_start, window_end)
    
    # === 7. MARKETING & TRAFFIC ===
    marketing_traffic = _collect_marketing_traffic(window_start, window_end)
    
    # === 8. SUPPORT & FEEDBACK ===
    support_feedback = _collect_support_feedback(window_start)
    
    return {
        "meta": meta,
        "product_engineering": product_engineering,
        "ledger_accounting": ledger_accounting,
        "banking_reconciliation": banking_reconciliation,
        "tax_fx": tax_fx,
        "business_revenue": business_revenue,
        "marketing_traffic": marketing_traffic,
        "support_feedback": support_feedback,
    }


def _collect_meta(business: Business, now: datetime, window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Collect metadata about the monitoring run."""
    env = os.getenv('MONITORING_ENV', 'local')
    
    # Get all businesses to list
    all_businesses = Business.objects.all()
    businesses_included = [b.name for b in all_businesses] if all_businesses.exists() else ["central-books-main"]
    
    return {
        "generated_at": now.isoformat(),
        "environment": env,
        "businesses_included": businesses_included,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "primary_business": {
            "id": business.id,
            "name": business.name,
            "currency": business.currency,
            "created_at": business.created_at.isoformat() if business.created_at else None,
        }
    }


def _collect_product_engineering(business: Business, window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Collect product engineering metrics."""
    # TODO: Implement request logging model for real HTTP request tracking
    
    # Feature usage based on real model activity
    total_businesses = Business.objects.count()
    businesses_with_customers = Business.objects.annotate(
        customer_count=Count('customers')
    ).filter(customer_count__gt=0).count()
    
    businesses_with_invoices = Business.objects.annotate(
        invoice_count=Count('invoices')
    ).filter(invoice_count__gt=0).count()
    
    # Onboarding completion = has both customers and invoices
    onboarding_completed = Business.objects.annotate(
        customer_count=Count('customers'),
        invoice_count=Count('invoices')
    ).filter(customer_count__gt=0, invoice_count__gt=0).count()
    
    # Activity in window
    invoices_created_in_window = Invoice.objects.filter(
        business=business,
        created_at__gte=window_start,
        created_at__lte=window_end
    ).count()
    
    expenses_created_in_window = Expense.objects.filter(
        business=business,
        created_at__gte=window_start,
        created_at__lte=window_end
    ).count()
    
    # TODO: Track bank feed imports with a dedicated import tracking field
    # For now, count bank accounts with any transactions (no created_at field on BankTransaction)
    bank_feeds_imports = BankAccount.objects.filter(
        business=business,
        bank_transactions__isnull=False
    ).distinct().count()
    
    # Reconciliation activity
    # ReconciliationSession doesn't have created_at, use statement dates
    reconciliations_started = ReconciliationSession.objects.filter(
        business=business,
        statement_end_date__gte=window_start.date(),
        statement_end_date__lte=window_end.date()
    ).count()
    
    reconciliations_completed = ReconciliationSession.objects.filter(
        business=business,
        status='COMPLETED',
        completed_at__gte=window_start,
        completed_at__lte=window_end
    ).count()
    
    return {
        "requests": {
            "total": 0,  # TODO: Implement request logging
            "by_status": {
                "2xx": 0,
                "4xx": 0,
                "5xx": 0
            },
            "avg_response_ms": 0.0
        },
        "endpoints": [],  # TODO: Add endpoint performance tracking
        "feature_usage": {
            "onboarding_started": total_businesses,
            "onboarding_completed": onboarding_completed,
            "dashboard_views": 0,  # TODO: Track page views
            "invoices_created": invoices_created_in_window,
            "expenses_created": expenses_created_in_window,
            "bank_feeds_imports": bank_feeds_imports,
            "reconciliations_started": reconciliations_started,
            "reconciliations_completed": reconciliations_completed
        },
        "deployments": {
            "last_deploy_at": None,  # TODO: Track deployments via Git or Render API
            "deploy_count_7d": 0,
            "last_deploy_status": None
        }
    }


def _collect_ledger_accounting(business: Business, now: datetime) -> Dict[str, Any]:
    """Collect ledger and accounting metrics with real data."""
    today = now.date()
    
    # Journal entries
    all_entries = JournalEntry.objects.filter(business=business)
    total_entries = all_entries.count()
    
    # Find unbalanced entries
    unbalanced_entries = []
    for entry in all_entries[:500]:  # Limit to 500 for performance
        lines = entry.lines.all()
        total_debits = sum(line.debit for line in lines)
        total_credits = sum(line.credit for line in lines)
        if abs(total_debits - total_credits) > Decimal('0.01'):
            unbalanced_entries.append(entry.id)
    
    # Future-dated entries
    future_entries = all_entries.filter(date__gt=today)
    future_dated_examples = [
        {"id": e.id, "date": e.date.isoformat()}
        for e in future_entries[:5]
    ]
    
    # Accounts
    all_accounts = Account.objects.filter(business=business)
    total_accounts = all_accounts.count()
    
    # Accounts by type
    accounts_by_type = all_accounts.values('type').annotate(count=Count('id'))
    by_type = {
        "ASSET": 0,
        "LIABILITY": 0,
        "EQUITY": 0,
        "INCOME": 0,
        "EXPENSE": 0
    }
    for item in accounts_by_type:
        by_type[item['type']] = item['count']
    
    # Get balances for key accounts (simplified - actual balance calc is complex)
    balances = []
    key_accounts = all_accounts.filter(
        Q(type='ASSET') | Q(code__in=['1200', '2000'])  # AR and AP
    )[:10]
    
    for account in key_accounts:
        # Sum journal line debits/credits for this account
        balance_data = JournalLine.objects.filter(account=account).aggregate(
            total_debits=Sum('debit'),
            total_credits=Sum('credit')
        )
        debits = balance_data['total_debits'] or Decimal('0')
        credits = balance_data['total_credits'] or Decimal('0')
        balance = debits - credits
        
        balances.append({
            "account_code": account.code or "",
            "account_name": account.name,
            "type": account.type,
            "current_balance": float(balance)
        })
    
    # Unlinked bank transactions (those without posted_journal_entry_id)
    unlinked_count = BankTransaction.objects.filter(
        bank_account__business=business,
        posted_journal_entry__isnull=True,
        status__in=['NEW', 'SUGGESTED', 'PARTIAL']
    ).count()
    
    return {
        "journal_entries": {
            "total": total_entries,
            "unbalanced_count": len(unbalanced_entries),
            "future_dated_count": future_entries.count(),
            "future_dated_examples": future_dated_examples
        },
        "accounts": {
            "total_accounts": total_accounts,
            "by_type": by_type,
            "balances": balances
        },
        "unlinked_bank_transactions_count": unlinked_count
    }


def _collect_banking_reconciliation(business: Business, window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Collect banking and reconciliation metrics."""
    bank_accounts = BankAccount.objects.filter(business=business)
    
    # Per-account reconciliation status
    bank_account_status = []
    for bank_account in bank_accounts:
        # Bank feed balance = sum of all transactions
        bank_transactions = BankTransaction.objects.filter(bank_account=bank_account)
        bank_feed_balance = bank_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Ledger balance from linked Account
        ledger_balance = Decimal('0')
        if bank_account.account:
            ledger_data = JournalLine.objects.filter(account=bank_account.account).aggregate(
                total_debits=Sum('debit'),
                total_credits=Sum('credit')
            )
            debits = ledger_data['total_debits'] or Decimal('0')
            credits = ledger_data['total_credits'] or Decimal('0')
            ledger_balance = debits - credits
        
        # Unmatched and unreconciled
        unmatched = bank_transactions.filter(
            matches__isnull=True,
            status__in=['NEW', 'SUGGESTED']
        ).count()
        
        unreconciled = bank_transactions.exclude(
            status__in=['RECONCILED', 'EXCLUDED']
        ).count()
        
        # Age analysis
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sixty_days_ago = timezone.now() - timedelta(days=60)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        unreconciled_qs = bank_transactions.exclude(status__in=['RECONCILED', 'EXCLUDED'])
        unreconciled_older_than = {
            "30d": unreconciled_qs.filter(date__lt=thirty_days_ago.date()).count(),
            "60d": unreconciled_qs.filter(date__lt=sixty_days_ago.date()).count(),
            "90d": unreconciled_qs.filter(date__lt=ninety_days_ago.date()).count()
        }
        
        # Last reconciliation
        last_session = ReconciliationSession.objects.filter(
            bank_account=bank_account,
            status='COMPLETED'
        ).order_by('-completed_at').first()
        
        bank_account_status.append({
            "account_id": bank_account.id,
            "account_name": bank_account.name,
            "bank_feed_balance": float(bank_feed_balance),
            "ledger_balance": float(ledger_balance),
            "balance_difference": float(ledger_balance - bank_feed_balance),
            "unmatched_transactions": unmatched,
            "unreconciled_transactions": unreconciled,
            "unreconciled_older_than_days": unreconciled_older_than,
            "last_reconciled_at": last_session.completed_at.isoformat() if last_session and last_session.completed_at else None
        })
    
    # Overall bank transaction summary
    all_bank_txs = BankTransaction.objects.filter(bank_account__business=business)
    # BankTransaction doesn't have created_at, use date field
    new_in_window = all_bank_txs.filter(
        date__gte=window_start.date(),
        date__lte=window_end.date()
    ).count()
    
    # Matched/added/excluded in window
    matched_in_window = BankReconciliationMatch.objects.filter(
        bank_transaction__bank_account__business=business,
        reconciled_at__gte=window_start,
        reconciled_at__lte=window_end
    ).values('bank_transaction').distinct().count()
    
    added_in_window = all_bank_txs.filter(
        date__gte=window_start.date(),
        date__lte=window_end.date(),
        status='LEGACY_CREATED'
    ).count()
    
    # BankTransaction doesn't have updated_at, just count excluded transactions in date range
    excluded_in_window = all_bank_txs.filter(
        date__gte=window_start.date(),
        date__lte=window_end.date(),
        status='EXCLUDED'
    ).count()
    
    return {
        "bank_accounts": bank_account_status,
        "bank_transactions_summary": {
            "total": all_bank_txs.count(),
            "new_in_window": new_in_window,
            "matched_in_window": matched_in_window,
            "added_in_window": added_in_window,
            "excluded_in_window": excluded_in_window
        }
    }


def _collect_tax_fx(business: Business, window_start: datetime) -> Dict[str, Any]:
    """Collect tax and FX metrics."""
    # Tax rates
    tax_rates = TaxRate.objects.filter(business=business, is_active=True)
    active_count = tax_rates.count()
    
    by_code = {}
    for rate in tax_rates:
        by_code[rate.code] = {
            "percentage": float(rate.percentage),
            "is_recoverable": rate.is_recoverable
        }
    
    # Invoice line checks (sample recent invoices)
    invoices = Invoice.objects.filter(business=business).order_by('-created_at')[:200]
    total_lines_checked = len(invoices)
    mismatched_net_tax_total_count = 0
    tax_rate_set_but_zero_tax_amount_count = 0
    
    for invoice in invoices:
        # Check if net + tax = grand_total
        calculated_total = invoice.net_total + invoice.tax_total
        if abs(calculated_total - invoice.grand_total) > Decimal('0.02'):
            mismatched_net_tax_total_count += 1
        
        # Check if tax_rate is set but tax_amount is zero
        if (invoice.tax_rate_id or invoice.tax_group_id) and invoice.tax_total == Decimal('0'):
            tax_rate_set_but_zero_tax_amount_count += 1
    
    # FX documents (multi-currency) - TODO: implement when FX tracking added
    # For now, check if business uses non-CAD currency
    fx_enabled = business.currency != 'CAD'
    
    return {
        "tax_rates": {
            "active_count": active_count,
            "by_code": by_code
        },
        "invoice_lines_checks": {
            "total_lines_checked": total_lines_checked,
            "mismatched_net_tax_total_count": mismatched_net_tax_total_count,
            "tax_rate_set_but_zero_tax_amount_count": tax_rate_set_but_zero_tax_amount_count
        },
        "fx_documents_checks": {
            "total_fx_documents": 0,  # TODO: Track FX invoices/expenses
            "mismatched_fx_totals_count": 0,
            "max_fx_deviation_pct": 0.0,
            "fx_enabled": fx_enabled
        }
    }


def _collect_business_revenue(business: Business, window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Collect business revenue and customer metrics."""
    # TODO: Implement subscription/MRR tracking
    # For now, use recurring invoices as proxy
    
    # Customer metrics
    total_customers = Customer.objects.filter(business=business).count()
    new_customers = Customer.objects.filter(
        business=business,
        created_at__gte=window_start,
        created_at__lte=window_end
    ).count()
    active_customers = Customer.objects.filter(business=business, is_active=True).count()
    
    # Payment metrics (invoices as proxy)
    # Invoice doesn't have updated_at, use created_at for paid invoices in window
    successful_payments = Invoice.objects.filter(
        business=business,
        status='PAID',
        created_at__gte=window_start,
        created_at__lte=window_end
    ).count()
    
    # Revenue calculation
    paid_invoices = Invoice.objects.filter(
        business=business,
        status='PAID'
    )
    
    # MRR approximation: average monthly revenue from paid invoices
    # This is a simplification - proper MRR needs subscription tracking
    total_revenue = paid_invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
    invoice_count = paid_invoices.count()
    current_mrr = float(total_revenue / max(invoice_count, 1)) if invoice_count > 0 else 0.0
    
    return {
        "mrr": {
            "current_mrr": current_mrr,  # TODO: Implement proper MRR tracking
            "delta_mrr": 0.0,
            "delta_mrr_breakdown": {
                "new": 0.0,
                "expansion": 0.0,
                "contraction": 0.0,
                "churn": 0.0
            }
        },
        "customers": {
            "total_customers": total_customers,
            "new_customers": new_customers,
            "churned_customers": 0,  # TODO: Track customer churn
            "active_customers": active_customers
        },
        "payments": {
            "successful_payments": successful_payments,
            "failed_payments": 0,  # TODO: Track payment failures
            "refunds": 0  # TODO: Track refunds
        }
    }


def _collect_marketing_traffic(window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Collect marketing and traffic metrics (placeholder for analytics integration)."""
    # TODO: Integrate with Google Analytics, Plausible, or similar
    
    return {
        "website": {
            "visits": 0,
            "unique_visitors": 0,
            "bounce_rate_pct": 0.0,
            "signup_conversions": 0,
            "top_sources": []
        },
        "campaigns": []
    }


def _collect_support_feedback(window_start: datetime) -> Dict[str, Any]:
    """Collect support and feedback metrics (placeholder for ticketing integration)."""
    # TODO: Integrate with Zendesk, Intercom, or similar
    
    return {
        "tickets": {
            "open": 0,
            "new_in_window": 0,
            "closed_in_window": 0,
            "avg_response_time_hours": 0.0
        },
        "common_topics": [],
        "nps": {
            "score": 0.0,
            "responses_count": 0,
            "promoters": 0,
            "detractors": 0
        },
        "notable_quotes": []
    }


def _empty_metrics(now: datetime, window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Return empty metrics structure when no business exists."""
    return {
        "meta": {
            "generated_at": now.isoformat(),
            "environment": os.getenv('MONITORING_ENV', 'local'),
            "businesses_included": [],
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "error": "No business found"
        },
        "product_engineering": {},
        "ledger_accounting": {},
        "banking_reconciliation": {},
        "tax_fx": {},
        "business_revenue": {},
        "marketing_traffic": {},
        "support_feedback": {},
    }
