from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.accounting_defaults import ensure_default_accounts
from core.llm_reasoning import BankRankedTransaction, BankReviewLLMResult
from core.models import Business, BankReviewRun, BankTransactionReview, JournalEntry, JournalLine, Account

User = get_user_model()


class BankReviewApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bankreview", password="pass")
        self.business = Business.objects.create(name="Biz", currency="USD", owner_user=self.user)
        ensure_default_accounts(self.business)
        self.client = Client()
        self.client.force_login(self.user)

        cash = Account.objects.filter(business=self.business, code="1010").first()
        opex = Account.objects.filter(business=self.business, code="5010").first()
        je = JournalEntry.objects.create(
            business=self.business,
            date=date(2025, 1, 1),
            description="Bank deposit",
        )
        JournalLine.objects.create(journal_entry=je, account=cash, debit=Decimal("100.00"), credit=0)
        JournalLine.objects.create(journal_entry=je, account=opex, debit=0, credit=Decimal("100.00"))

    def _run_review(self):
        lines = '[{"date":"2025-01-01","description":"Bank deposit","amount":100},{"date":"2025-01-05","description":"Unknown","amount":50}]'
        resp = self.client.post(
            "/api/agentic/bank-review/run",
            {"lines": lines, "period_start": "2025-01-01", "period_end": "2025-01-31"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        return resp.json()

    def test_run_review_persists_metrics_and_transactions(self):
        data = self._run_review()
        run = BankReviewRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.status, BankReviewRun.RunStatus.COMPLETED)
        self.assertTrue(run.trace_id)
        self.assertIsNotNone(run.overall_risk_score)
        self.assertGreaterEqual(run.metrics.get("transactions_total", 0), 2)
        txs = BankTransactionReview.objects.filter(run=run)
        self.assertEqual(txs.count(), 2)
        self.assertTrue(any(tx.status == BankTransactionReview.ReviewStatus.MATCHED for tx in txs))

    def test_runs_listing_and_detail(self):
        data = self._run_review()
        run_id = data["run_id"]

        list_resp = self.client.get("/api/agentic/bank-review/runs")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["runs"][0]["id"], run_id)

        detail_resp = self.client.get(f"/api/agentic/bank-review/run/{run_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.json()
        self.assertEqual(detail["id"], run_id)
        self.assertIn("transactions", detail)

    def test_llm_results_persist_when_companion_enabled(self):
        self.business.ai_companion_enabled = True
        self.business.save(update_fields=["ai_companion_enabled"])
        mock_llm_result = BankReviewLLMResult(
            explanations=["Unmatched lines need review."],
            ranked_transactions=[BankRankedTransaction(transaction_id="line-1", priority="high", reason="Unmatched withdrawal")],
            suggested_followups=["Confirm support for line-1"],
        )
        with patch("core.agentic_bank_review.reason_about_bank_review", return_value=mock_llm_result) as mock_reason:
            data = self._run_review()
            mock_reason.assert_called_once()

        run = BankReviewRun.objects.get(pk=data["run_id"])
        self.assertTrue(run.llm_explanations)
        unmatched = BankTransactionReview.objects.filter(run=run, status=BankTransactionReview.ReviewStatus.UNMATCHED).first()
        self.assertTrue(run.llm_ranked_transactions)
        self.assertEqual(run.llm_ranked_transactions[0]["transaction_id"], unmatched.id)

        detail_resp = self.client.get(f"/api/agentic/bank-review/run/{run.id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIn("llm_suggested_followups", detail_resp.json())

    def test_llm_not_called_when_disabled(self):
        with patch("core.agentic_bank_review.reason_about_bank_review") as mock_reason:
            data = self._run_review()
            mock_reason.assert_not_called()
        run = BankReviewRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.llm_explanations, [])

    def test_tenant_isolation(self):
        data = self._run_review()
        run_id = data["run_id"]
        other_user = User.objects.create_user(username="otherbank", password="pass")
        other_business = Business.objects.create(name="OtherBiz", currency="USD", owner_user=other_user)
        ensure_default_accounts(other_business)
        client2 = Client()
        client2.force_login(other_user)
        resp = client2.get(f"/api/agentic/bank-review/run/{run_id}")
        self.assertEqual(resp.status_code, 404)

    def test_run_review_returns_json_on_success(self):
        lines = '[{"date":"2025-01-01","description":"Bank deposit","amount":100}]'
        resp = self.client.post(
            "/api/agentic/bank-review/run",
            {"lines": lines, "period_start": "2025-01-01", "period_end": "2025-01-31"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertTrue(resp["Content-Type"].startswith("application/json"))
        data = resp.json()
        self.assertIn("run_id", data)
        self.assertIn("status", data)

    def test_run_review_invalid_period_returns_json_400(self):
        lines = '[{"date":"2025-01-01","description":"Bank deposit","amount":100}]'
        resp = self.client.post(
            "/api/agentic/bank-review/run",
            {"lines": lines, "period_start": "2025/01/01", "period_end": "2025/01/31"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp["Content-Type"].startswith("application/json"))
        data = resp.json()
        self.assertTrue(data.get("error", "").startswith("Invalid period"))
