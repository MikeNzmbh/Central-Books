import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from core.ledger_services import get_account_balance
from core.models import (
    Account,
    BankAccount,
    BankStatementImport,
    BankTransaction,
    Business,
    Customer,
    Expense,
    Invoice,
    JournalEntry,
    JournalLine,
    ReconciliationSession,
    TaxRate,
)


class Command(BaseCommand):
    help = "Export high-level product, finance, and operational metrics as JSON for the Master Agent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--business",
            action="append",
            dest="business_names",
            help="Limit metrics to one or more business names (can be provided multiple times).",
        )
        parser.add_argument(
            "--window-start",
            dest="window_start",
            help="Optional ISO8601 start of the reporting window (inclusive).",
        )
        parser.add_argument(
            "--window-end",
            dest="window_end",
            help="Optional ISO8601 end of the reporting window (inclusive).",
        )
        parser.add_argument(
            "--environment",
            dest="environment",
            help="Override environment label in the output (production|staging|local).",
        )

    def handle(self, *args, **options):
        window_start = self._parse_iso(options.get("window_start"))
        window_end = self._parse_iso(options.get("window_end"))
        businesses = self._get_businesses(options.get("business_names"))

        metrics = {
            "meta": self._build_meta(businesses, window_start, window_end, options.get("environment")),
            "product_engineering": self._build_product_engineering(businesses, window_start, window_end),
            "ledger_accounting": self._build_ledger_accounting(businesses),
            "banking_reconciliation": self._build_banking_reconciliation(businesses, window_start, window_end),
            "tax_fx": self._build_tax_fx(businesses),
            "business_revenue": self._build_business_revenue(businesses, window_start, window_end),
            "marketing_traffic": self._build_marketing_traffic(),
            "support_feedback": self._build_support_feedback(),
        }

        self.stdout.write(json.dumps({"central_books_metrics": metrics}, indent=2, sort_keys=True, default=str))

    def _parse_iso(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
            return parsed
        except ValueError as exc:
            raise CommandError(f"Invalid ISO8601 value: {value}") from exc

    def _apply_window(
        self,
        qs,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        field: str,
        *,
        date_only: bool = False,
    ):
        start_value = window_start.date() if (date_only and window_start) else window_start
        end_value = window_end.date() if (date_only and window_end) else window_end
        if start_value:
            qs = qs.filter(**{f"{field}__gte": start_value})
        if end_value:
            qs = qs.filter(**{f"{field}__lte": end_value})
        return qs

    def _get_businesses(self, names: Optional[Iterable[str]]):
        qs = Business.objects.all()
        if names:
            qs = qs.filter(name__in=list(names))
        return qs

    def _detect_environment(self, override: Optional[str]) -> str:
        allowed = {"production", "staging", "local"}
        if override and override in allowed:
            return override
        env = getattr(settings, "ENVIRONMENT", None)
        if env in allowed:
            return env
        if getattr(settings, "DEBUG", False):
            return "local"
        return "production"

    def _build_meta(
        self,
        businesses,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        override_env: Optional[str],
    ):
        return {
            "generated_at": timezone.now().isoformat(),
            "environment": self._detect_environment(override_env),
            "businesses_included": list(businesses.values_list("name", flat=True)),
            "window_start": window_start.isoformat() if window_start else None,
            "window_end": window_end.isoformat() if window_end else None,
        }

    def _build_product_engineering(self, businesses, window_start: Optional[datetime], window_end: Optional[datetime]):
        invoices_qs = Invoice.objects.filter(business__in=businesses)
        expenses_qs = Expense.objects.filter(business__in=businesses)
        imports_qs = BankStatementImport.objects.filter(business__in=businesses)
        reconciliations_qs = ReconciliationSession.objects.filter(business__in=businesses)

        invoices_window = self._apply_window(invoices_qs, window_start, window_end, "issue_date", date_only=True)
        expenses_window = self._apply_window(expenses_qs, window_start, window_end, "date", date_only=True)

        return {
            "requests": {
                "total_requests": 0,  # TODO: Plug into API request logs / APM
                "error_rate_pct": 0.0,  # TODO: Compute from request/response logs
                "avg_response_ms": 0.0,  # TODO: Pull from APM traces
                "p95_response_ms": 0.0,  # TODO: Pull from APM traces
            },
            "endpoints": [],  # TODO: Populate per-endpoint stats once request logging is available
            "feature_usage": {
                "onboarding_started": businesses.count(),
                "onboarding_completed": businesses.filter(bank_setup_completed=True).count(),
                "dashboard_views": 0,  # TODO: Hook up to product analytics
                "invoices_created": invoices_window.count(),
                "expenses_created": expenses_window.count(),
                "bank_feeds_imports": imports_qs.count(),
                "reconciliations_started": reconciliations_qs.count(),
                "reconciliations_completed": reconciliations_qs.filter(
                    status=ReconciliationSession.Status.COMPLETED
                ).count(),
            },
            "deployments": {
                "last_deploy_timestamp": None,  # TODO: Wire to CI/CD deployment metadata
                "last_deploy_version": None,  # TODO: Wire to git SHA / release version
                "deploy_notes": None,  # TODO: Pull from release notes
            },
        }

    def _build_ledger_accounting(self, businesses):
        journal_entries = JournalEntry.objects.filter(business__in=businesses)
        journal_entries = journal_entries.annotate(
            total_debit=Sum("lines__debit"),
            total_credit=Sum("lines__credit"),
        )

        unbalanced_count = journal_entries.filter(
            Q(total_debit__isnull=True)
            | Q(total_credit__isnull=True)
            | ~Q(total_debit=F("total_credit"))
        ).count()

        future_dated_qs = journal_entries.filter(date__gt=timezone.now().date())
        future_examples = [
            {"id": row["id"], "date": row["date"].isoformat()}
            for row in future_dated_qs.values("id", "date")[:5]
        ]

        accounts_qs = Account.objects.filter(business__in=businesses)
        accounts_by_type = {choice: 0 for choice, _ in Account.AccountType.choices}
        for row in accounts_qs.values("type").annotate(total=Count("id")):
            accounts_by_type[row["type"]] = row["total"] or 0

        account_rows = list(
            accounts_qs.values("id", "code", "name", "type").order_by("type", "code", "name")
        )
        line_sums = {
            row["account_id"]: row
            for row in JournalLine.objects.filter(account__business__in=businesses)
            .values("account_id")
            .annotate(debit_sum=Sum("debit"), credit_sum=Sum("credit"))
        }

        balances = []
        for account in account_rows:
            sums = line_sums.get(account["id"], {})
            debit = sums.get("debit_sum") or Decimal("0")
            credit = sums.get("credit_sum") or Decimal("0")
            if account["type"] in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
                balance = debit - credit
            else:
                balance = credit - debit
            balances.append(
                {
                    "account_code": account["code"] or "",
                    "account_name": account["name"],
                    "type": account["type"],
                    "balance": balance,
                }
            )

        unlinked_bank_transactions_count = BankTransaction.objects.filter(
            bank_account__business__in=businesses,
            posted_journal_entry__isnull=True,
        ).exclude(status=BankTransaction.TransactionStatus.EXCLUDED).count()

        return {
            "journal_entries": {
                "total": journal_entries.count(),
                "unbalanced_count": unbalanced_count,
                "future_dated_count": future_dated_qs.count(),
                "future_dated_examples": future_examples,
            },
            "accounts": {
                "total_accounts": accounts_qs.count(),
                "by_type": accounts_by_type,
            },
            "balances": balances,
            "unlinked_bank_transactions_count": unlinked_bank_transactions_count,
        }

    def _build_banking_reconciliation(self, businesses, window_start: Optional[datetime], window_end: Optional[datetime]):
        bank_accounts = BankAccount.objects.filter(business__in=businesses)
        bank_accounts_data = []
        today = timezone.now().date()

        for account in bank_accounts:
            txn_qs = BankTransaction.objects.filter(bank_account=account)
            txn_sums = txn_qs.aggregate(total=Sum("amount"))
            bank_feed_balance = txn_sums["total"] or Decimal("0")

            ledger_balance = Decimal("0")
            if account.account_id:
                ledger_balance = get_account_balance(account.account)

            balance_difference = bank_feed_balance - ledger_balance

            unmatched_transactions = txn_qs.filter(
                status__in=[
                    BankTransaction.TransactionStatus.NEW,
                    BankTransaction.TransactionStatus.SUGGESTED,
                    BankTransaction.TransactionStatus.PARTIAL,
                ]
            ).count()
            unreconciled_transactions = txn_qs.exclude(
                status=BankTransaction.TransactionStatus.EXCLUDED
            ).filter(is_reconciled=False).count()

            unreconciled_older_than = {}
            for days in (30, 60, 90):
                cutoff = today - timedelta(days=days)
                unreconciled_older_than[str(days)] = (
                    txn_qs.exclude(status=BankTransaction.TransactionStatus.EXCLUDED)
                    .filter(is_reconciled=False, date__lte=cutoff)
                    .count()
                )

            last_reconciled_at = (
                txn_qs.filter(reconciled_at__isnull=False).order_by("-reconciled_at").values_list(
                    "reconciled_at", flat=True
                ).first()
            )

            bank_accounts_data.append(
                {
                    "account_code": getattr(account.account, "code", "") if account.account_id else "",
                    "account_name": account.name,
                    "bank_feed_balance": bank_feed_balance,
                    "ledger_balance": ledger_balance,
                    "balance_difference": balance_difference,
                    "unmatched_transactions": unmatched_transactions,
                    "unreconciled_transactions": unreconciled_transactions,
                    "unreconciled_older_than_days": unreconciled_older_than,
                    "last_reconciled_at": last_reconciled_at.isoformat() if last_reconciled_at else None,
                }
            )

        txn_base = BankTransaction.objects.filter(bank_account__business__in=businesses)
        windowed_txns = self._apply_window(txn_base, window_start, window_end, "date", date_only=True)

        bank_transactions_summary = {
            "total": txn_base.count(),
            "new_in_window": windowed_txns.filter(status=BankTransaction.TransactionStatus.NEW).count(),
            "matched_in_window": windowed_txns.filter(status=BankTransaction.TransactionStatus.MATCHED).count(),
            "added_in_window": windowed_txns.count(),  # TODO: Track creation timestamps to differentiate "added"
            "excluded_in_window": windowed_txns.filter(status=BankTransaction.TransactionStatus.EXCLUDED).count(),
        }

        return {
            "bank_accounts": bank_accounts_data,
            "bank_transactions_summary": bank_transactions_summary,
        }

    def _build_tax_fx(self, businesses):
        tax_rates = TaxRate.objects.filter(business__in=businesses)
        active_tax_rates = tax_rates.filter(is_active=True)
        return {
            "tax_rates": {
                "active_count": active_tax_rates.count(),
                "by_code": {
                    tr.code: {"percentage": float(tr.percentage), "is_recoverable": tr.is_recoverable}
                    for tr in active_tax_rates
                },
            },
            "invoice_lines_checks": {
                "total_lines_checked": 0,  # TODO: Implement invoice line audits
                "mismatched_net_tax_total_count": 0,  # TODO: Implement invoice line audits
                "tax_rate_set_but_zero_tax_amount_count": 0,  # TODO: Implement invoice line audits
            },
            "fx_documents_checks": {
                "total_fx_documents": 0,  # TODO: Plug in FX document validations
                "mismatched_fx_totals_count": 0,  # TODO: Plug in FX document validations
                "max_fx_deviation_pct": 0.0,  # TODO: Plug in FX document validations
            },
        }

    def _build_business_revenue(
        self, businesses, window_start: Optional[datetime], window_end: Optional[datetime]
    ):
        customers_qs = Customer.objects.filter(business__in=businesses)
        customers_window = self._apply_window(customers_qs, window_start, window_end, "created_at")

        return {
            "mrr": {
                "current_mrr": Decimal("0"),  # TODO: Replace with Subscription/Payment-derived MRR
                "delta_mrr": Decimal("0"),  # TODO: Calculate MRR movement
                "delta_mrr_breakdown": {
                    "new_customers_mrr": Decimal("0"),  # TODO: Calculate from new subscriptions
                    "expansion_mrr": Decimal("0"),  # TODO: Calculate upsells
                    "churned_mrr": Decimal("0"),  # TODO: Calculate downgrades/churn
                },
            },
            "customers": {
                "total_customers": customers_qs.count(),
                "new_customers": customers_window.count(),
                "churned_customers": 0,  # TODO: Track churned customers
                "active_customers": customers_qs.filter(is_active=True).count(),
            },
            "payments": {
                "successful_payments": 0,  # TODO: Wire to payment processor events
                "failed_payments": 0,  # TODO: Wire to payment processor events
                "refunds": 0,  # TODO: Wire to payment processor events
            },
        }

    def _build_marketing_traffic(self):
        return {
            "website": {
                "visits": 0,  # TODO: Pull from analytics (e.g., GA)
                "unique_visitors": 0,  # TODO: Pull from analytics (e.g., GA)
                "bounce_rate_pct": 0.0,  # TODO: Pull from analytics
                "signup_conversions": 0,  # TODO: Pull from analytics / signup funnels
                "top_sources": [],  # TODO: Populate with source breakdown
            },
            "campaigns": [],  # TODO: Populate from marketing automation platform
        }

    def _build_support_feedback(self):
        return {
            "tickets": {
                "new_tickets": 0,  # TODO: Plug into support system
                "open_tickets": 0,  # TODO: Plug into support system
                "closed_tickets": 0,  # TODO: Plug into support system
                "median_first_response_minutes": 0.0,  # TODO: Plug into support system
            },
            "common_topics": [],  # TODO: Plug into support system
            "nps": {
                "responses": 0,  # TODO: Pull from NPS surveys
                "average_score": 0.0,  # TODO: Pull from NPS surveys
            },
            "notable_quotes": [],  # TODO: Pull from NPS/CSAT verbatims
        }
