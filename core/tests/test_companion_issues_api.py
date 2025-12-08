from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from core.accounting_defaults import ensure_default_accounts
from core.models import Business, CompanionIssue, ReceiptRun, BooksReviewRun

User = get_user_model()


class CompanionIssuesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="issues", password="pass")
        self.business = Business.objects.create(name="Biz", currency="USD", owner_user=self.user, ai_companion_enabled=True)
        ensure_default_accounts(self.business)
        self.client = Client()
        self.client.force_login(self.user)

    def test_issues_listing_filters_and_patch(self):
        issue1 = CompanionIssue.objects.create(
            business=self.business,
            surface="bank",
            run_type="bank_review",
            severity="high",
            status="open",
            title="Unreconciled items",
        )
        issue2 = CompanionIssue.objects.create(
            business=self.business,
            surface="receipts",
            run_type="receipts",
            severity="low",
            status="snoozed",
            title="Receipt warnings",
        )
        resp = self.client.get("/api/agentic/companion/issues?status=open")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["issues"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], issue1.id)

        patch = self.client.patch(f"/api/agentic/companion/issues/{issue1.id}", data='{"status":"resolved"}', content_type="application/json")
        self.assertEqual(patch.status_code, 200)
        issue1.refresh_from_db()
        self.assertEqual(issue1.status, "resolved")

        other_user = User.objects.create_user(username="other", password="pass")
        other_business = Business.objects.create(name="OtherBiz", currency="USD", owner_user=other_user)
        issue_other = CompanionIssue.objects.create(
            business=other_business, surface="bank", severity="high", status="open", title="Other"
        )
        self.client.force_login(other_user)
        resp_forbidden = self.client.patch(f"/api/agentic/companion/issues/{issue1.id}", data='{"status":"resolved"}', content_type="application/json")
        self.assertEqual(resp_forbidden.status_code, 404)
        resp_other = self.client.get("/api/agentic/companion/issues?status=open")
        self.assertEqual(len(resp_other.json()["issues"]), 1)
        self.assertEqual(resp_other.json()["issues"][0]["id"], issue_other.id)

    def test_summary_includes_issue_counts(self):
        CompanionIssue.objects.create(
            business=self.business,
            surface="books",
            run_type="books_review",
            severity="high",
            status="open",
            title="High-risk journals",
        )
        resp = self.client.get("/api/agentic/companion/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["global"].get("open_issues_total", 0), 1)
        self.assertIn("books", data["global"].get("open_issues_by_surface", {}))

    def test_receipts_run_creates_issue_when_ai_enabled(self):
        files = [SimpleUploadedFile("receipt_1500.pdf", b"fake", content_type="application/pdf")]
        resp = self.client.post("/api/agentic/receipts/run", {"files": files, "default_currency": "USD"})
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        # Force a high-risk metric to ensure issue creation path
        run = ReceiptRun.objects.filter(business=self.business).order_by("-id").first()
        self.assertIsNotNone(run)
        run.metrics["documents_high_risk"] = 1
        run.save(update_fields=["metrics"])
        from core.companion_issues import build_receipts_issues, persist_companion_issues

        issues = build_receipts_issues(run, run.trace_id)
        persist_companion_issues(self.business, issues, ai_companion_enabled=True)
        self.assertTrue(CompanionIssue.objects.filter(business=self.business, surface="receipts").exists())

    def test_issue_ordering_prefers_high_impact(self):
        # Create low and high impact issues
        i1 = CompanionIssue.objects.create(
            business=self.business,
            surface="bank",
            severity="medium",
            status="open",
            title="Small mismatch",
            estimated_impact="≈ 50",
        )
        i2 = CompanionIssue.objects.create(
            business=self.business,
            surface="bank",
            severity="high",
            status="open",
            title="Large unreconciled",
            estimated_impact="≈ 5000",
        )
        resp = self.client.get("/api/agentic/companion/issues?status=open")
        data = resp.json()["issues"]
        self.assertEqual(data[0]["id"], i2.id)
