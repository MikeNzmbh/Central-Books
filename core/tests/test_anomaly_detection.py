from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.anomaly_detection import bundle_anomalies, apply_llm_explanations
from core.models import Business, Account, BankAccount, BankTransaction, JournalEntry, JournalLine

User = get_user_model()


class AnomalyDetectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="anomaly", password="pass123")
        self.business = Business.objects.create(
            name="Anomaly Co",
            currency="USD",
            owner_user=self.user,
            ai_companion_enabled=True,
        )
        self.cash = Account.objects.create(business=self.business, code="1000", name="Cash", type=Account.AccountType.ASSET)
        self.suspense = Account.objects.create(business=self.business, code="9999", name="Suspense", type=Account.AccountType.ASSET, is_suspense=True)
        self.bank = BankAccount.objects.create(business=self.business, name="Operating", account=self.cash)

    def test_generates_bank_unreconciled_anomaly(self):
        BankTransaction.objects.create(
            bank_account=self.bank,
            date=timezone.localdate() - timedelta(days=20),
            description="Old tx",
            amount=Decimal("100.00"),
            status=BankTransaction.TransactionStatus.NEW,
        )
        anomalies = bundle_anomalies(
            self.business,
            period_start=timezone.localdate() - timedelta(days=30),
            period_end=timezone.localdate(),
        )
        codes = {a.code for a in anomalies}
        self.assertIn("BANK_UNRECONCILED_AGING", codes)

    def test_llm_overlay_graceful_on_invalid(self):
        # No anomalies should just return list and not throw
        anomalies = []
        enriched = apply_llm_explanations(anomalies, ai_enabled=True, user_name="Test", llm_client=lambda p: None)
        self.assertEqual(enriched, anomalies)
