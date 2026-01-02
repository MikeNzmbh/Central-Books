from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.llm_reasoning import audit_high_risk_transaction
from core.models import Business, BankAccount, BankTransaction
from core.accounting_defaults import ensure_default_accounts


User = get_user_model()


class HighRiskCriticTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="critic-user", password="pass123")
        self.business = Business.objects.create(
            name="Critic Co",
            currency="USD",
            owner_user=self.user,
            ai_companion_enabled=True,
        )
        defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            account=defaults["cash"],
        )

    def test_small_amount_skips_llm(self):
        calls = []

        def fake_llm(prompt: str):
            calls.append(prompt)
            return '{"verdict": "ok", "reasons": ["ok"]}'

        result = audit_high_risk_transaction(
            amount=Decimal("1200"),
            currency="USD",
            accounts=[],
            memo="Small",
            source="test",
            llm_client=fake_llm,
        )

        self.assertFalse(result["called_llm"])
        self.assertEqual(calls, [])
        self.assertEqual(result["verdict"], "ok")

    def test_large_amount_triggers_llm(self):
        calls = []

        def fake_llm(prompt: str):
            calls.append(prompt)
            return '{"verdict": "warn", "reasons": ["Large transaction"]}'

        result = audit_high_risk_transaction(
            amount=Decimal("6000"),
            currency="USD",
            accounts=["1000"],
            memo="Big",
            source="test",
            llm_client=fake_llm,
        )

        self.assertTrue(result["called_llm"])
        self.assertEqual(result["verdict"], "warn")
        self.assertEqual(len(calls), 1)
        self.assertIn("Large transaction", result["reasons"][0])

    def test_bulk_flag_triggers_llm(self):
        calls = []

        def fake_llm(prompt: str):
            calls.append(prompt)
            return '{"verdict": "fail", "reasons": ["Bulk adjustment flagged"]}'

        result = audit_high_risk_transaction(
            amount=Decimal("100"),
            currency="USD",
            accounts=[],
            memo="Bulk move",
            source="test",
            is_bulk_adjustment=True,
            llm_client=fake_llm,
        )

        self.assertTrue(result["called_llm"])
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(len(calls), 1)

    def test_persists_when_attached_to_bank_transaction(self):
        calls = []

        def fake_llm(prompt: str):
            calls.append(prompt)
            return '{"verdict": "ok", "reasons": ["Looks fine"]}'

        tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Big wire",
            amount=Decimal("7500"),
            status=BankTransaction.TransactionStatus.NEW,
        )

        result = audit_high_risk_transaction(
            amount=tx.amount,
            currency=self.business.currency,
            accounts=["1000"],
            memo=tx.description,
            source="test",
            attach_to=tx,
            llm_client=fake_llm,
        )

        tx.refresh_from_db()
        self.assertTrue(result["called_llm"])
        self.assertEqual(result["verdict"], "ok")
        self.assertEqual(tx.high_risk_audits.count(), 1)
