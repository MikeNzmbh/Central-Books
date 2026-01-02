from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.accounting_defaults import ensure_default_accounts
from core.llm_reasoning import BooksRankedIssue, BooksReviewLLMResult
from core.models import Business, BooksReviewRun, JournalEntry, JournalLine, Account

User = get_user_model()


class BooksReviewApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="books", password="pass")
        self.business = Business.objects.create(name="Biz", currency="USD", owner_user=self.user)
        ensure_default_accounts(self.business)
        self.client = Client()
        self.client.force_login(self.user)

        # Seed a couple of journal entries
        cash = Account.objects.filter(business=self.business, code="1010").first()
        opex = Account.objects.filter(business=self.business, code="5010").first()
        for idx, amt in enumerate([100, 6000]):
            je = JournalEntry.objects.create(
                business=self.business,
                date=date(2025, 1, idx + 1),
                description="Adjustment entry" if idx == 1 else "Regular entry",
            )
            JournalLine.objects.create(journal_entry=je, account=opex, debit=amt, credit=0)
            JournalLine.objects.create(journal_entry=je, account=cash, debit=0, credit=amt)

    def _run_review(self):
        resp = self.client.post(
            "/api/agentic/books-review/run",
            {"period_start": "2025-01-01", "period_end": "2025-01-31"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        return resp.json()

    def test_run_review_and_persist_metrics(self):
        data = self._run_review()
        run = BooksReviewRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.status, BooksReviewRun.RunStatus.COMPLETED)
        self.assertTrue(run.trace_id)
        self.assertIsNotNone(run.overall_risk_score)
        self.assertGreaterEqual(len(run.findings), 1)
        self.assertGreaterEqual(run.metrics.get("journals_total", 0), 2)

    def test_runs_listing_and_detail(self):
        data = self._run_review()
        run_id = data["run_id"]
        list_resp = self.client.get("/api/agentic/books-review/runs")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["runs"][0]["id"], run_id)

        detail_resp = self.client.get(f"/api/agentic/books-review/run/{run_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.json()
        self.assertEqual(detail["id"], run_id)
        self.assertIn("findings", detail)

    def test_llm_results_persist_when_companion_enabled(self):
        self.business.ai_companion_enabled = True
        self.business.save(update_fields=["ai_companion_enabled"])
        journal_id = JournalEntry.objects.filter(business=self.business).first().id
        mock_llm_result = BooksReviewLLMResult(
            explanations=["Health looks stable."],
            ranked_issues=[
                BooksRankedIssue(
                    severity="high",
                    title="Spike",
                    message="Large adjustment",
                    related_journal_ids=[journal_id],
                    related_accounts=["1010"],
                )
            ],
            suggested_checks=["Review account 1010 for Q1"],
        )
        with patch("core.agentic_books_review.reason_about_books_review", return_value=mock_llm_result) as mock_reason:
            data = self._run_review()
            mock_reason.assert_called_once()

        run = BooksReviewRun.objects.get(pk=data["run_id"])
        self.assertGreaterEqual(len(run.llm_explanations), 1)
        self.assertEqual(run.llm_ranked_issues[0]["related_journal_ids"], [journal_id])

        detail_resp = self.client.get(f"/api/agentic/books-review/run/{run.id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIn("llm_suggested_checks", detail_resp.json())

    def test_llm_not_called_when_companion_disabled(self):
        with patch("core.agentic_books_review.reason_about_books_review") as mock_reason:
            data = self._run_review()
            mock_reason.assert_not_called()
        run = BooksReviewRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.llm_explanations, [])

    def test_tenant_isolation(self):
        data = self._run_review()
        run_id = data["run_id"]
        other_user = User.objects.create_user(username="otherbooks", password="pass")
        other_business = Business.objects.create(name="OtherBiz", currency="USD", owner_user=other_user)
        ensure_default_accounts(other_business)
        client2 = Client()
        client2.force_login(other_user)
        resp = client2.get(f"/api/agentic/books-review/run/{run_id}")
        self.assertEqual(resp.status_code, 404)

    def test_valid_date_range_from_user_request(self):
        """Test the exact date range from the user's bug report works."""
        resp = self.client.post(
            "/api/agentic/books-review/run",
            {"period_start": "2025-11-30", "period_end": "2025-12-06"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        data = resp.json()
        self.assertIn("run_id", data)
        run = BooksReviewRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.status, BooksReviewRun.RunStatus.COMPLETED)

    def test_invalid_date_format_returns_400(self):
        """Test that an invalid date format returns a clear error."""
        resp = self.client.post(
            "/api/agentic/books-review/run",
            {"period_start": "2025/11/30", "period_end": "2025/12/06"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_run_review_returns_json_on_success(self):
        resp = self.client.post(
            "/api/agentic/books-review/run",
            {"period_start": "2025-11-30", "period_end": "2025-12-06"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/json"))
        data = resp.json()
        self.assertIn("run_id", data)
        self.assertIn("status", data)

    def test_run_review_invalid_period_returns_json_400(self):
        resp = self.client.post(
            "/api/agentic/books-review/run",
            {"period_start": "2025/11/30", "period_end": "2025/12/06"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp["Content-Type"].startswith("application/json"))
        data = resp.json()
        self.assertTrue(data.get("error", "").startswith("Invalid period"))
