from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from core.accounting_defaults import ensure_default_accounts
from core.llm_reasoning import InvoicesRunLLMResult, RankedDocument, SuggestedClassification
from core.models import Business, InvoiceDocument, InvoiceRun, JournalEntry

User = get_user_model()


class InvoiceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="invoices", password="pass")
        self.business = Business.objects.create(name="Biz", currency="USD", owner_user=self.user)
        ensure_default_accounts(self.business)
        self.client = Client()
        self.client.force_login(self.user)

    def _upload_basic_run(self, file_count=1):
        files = [
            SimpleUploadedFile(f"invoice_{i}.pdf", b"fakecontent", content_type="application/pdf")
            for i in range(file_count)
        ]
        resp = self.client.post(
            "/api/agentic/invoices/run",
            {"files": files, "default_currency": "USD"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], InvoiceRun.RunStatus.COMPLETED)
        return data

    def test_happy_path_and_approval_idempotent(self):
        data = self._upload_basic_run()
        doc_id = data["documents"][0]["id"]

        approve_resp = self.client.post(f"/api/agentic/invoices/{doc_id}/approve")
        approve_data = approve_resp.json()
        self.assertEqual(approve_resp.status_code, 200, msg=approve_data)
        entry_id = approve_data["journal_entry_id"]
        self.assertTrue(JournalEntry.objects.filter(pk=entry_id).exists())

        approve_resp2 = self.client.post(f"/api/agentic/invoices/{doc_id}/approve")
        self.assertEqual(approve_resp2.status_code, 200)
        self.assertEqual(approve_resp2.json()["journal_entry_id"], entry_id)

    def test_unsupported_file_type_rejected(self):
        bad_file = SimpleUploadedFile("note.txt", b"noop", content_type="text/plain")
        resp = self.client.post("/api/agentic/invoices/run", {"files": [bad_file]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported", resp.json()["error"])

    def test_engine_failure_marks_run_failed(self):
        files = [SimpleUploadedFile("invoice.pdf", b"content", content_type="application/pdf")]
        with mock.patch("core.views_invoices.run_invoices_workflow", side_effect=RuntimeError("boom")):
            resp = self.client.post("/api/agentic/invoices/run", {"files": files})
        self.assertEqual(resp.status_code, 500)
        run = InvoiceRun.objects.first()
        self.assertEqual(run.status, InvoiceRun.RunStatus.FAILED)
        self.assertEqual(run.error_count, run.total_documents)

    def test_audit_fields_and_metrics_persisted(self):
        data = self._upload_basic_run(file_count=1)
        run = InvoiceRun.objects.get(pk=data["run_id"])
        doc = InvoiceDocument.objects.get(pk=data["documents"][0]["id"])

        self.assertIsNotNone(run.metrics.get("documents_total"))
        self.assertTrue(run.trace_id)
        self.assertGreaterEqual(len(run.metrics.get("trace_events", [])), 1)
        self.assertTrue(isinstance(doc.audit_flags, list))
        self.assertIsNotNone(doc.audit_score)

    def test_metrics_change_with_high_risk_and_errors(self):
        files = [
            SimpleUploadedFile("invoice_6000.pdf", b"fake", content_type="application/pdf"),
            SimpleUploadedFile("invoice_error.pdf", b"fake", content_type="application/pdf"),
        ]
        resp = self.client.post(
            "/api/agentic/invoices/run",
            {"files": files, "default_currency": "USD"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        data = resp.json()

        run = InvoiceRun.objects.get(pk=data["run_id"])
        docs = list(InvoiceDocument.objects.filter(run=run).order_by("id"))
        self.assertGreaterEqual(run.metrics.get("documents_high_risk", 0), 1)
        self.assertEqual(run.metrics.get("documents_total"), 2)
        self.assertGreaterEqual(run.error_count, 1)
        self.assertGreaterEqual(sum(1 for d in docs if d.status == InvoiceDocument.DocumentStatus.ERROR), 1)

    def test_tenant_isolation_on_run_detail(self):
        data = self._upload_basic_run(file_count=1)
        run_id = data["run_id"]

        other_user = User.objects.create_user(username="other-inv", password="pass")
        other_business = Business.objects.create(name="OtherInv", currency="USD", owner_user=other_user)
        ensure_default_accounts(other_business)
        client2 = Client()
        client2.force_login(other_user)
        resp = client2.get(f"/api/agentic/invoices/run/{run_id}")
        self.assertEqual(resp.status_code, 404)

    def test_llm_fields_persist_when_companion_enabled(self):
        self.business.ai_companion_enabled = True
        self.business.save(update_fields=["ai_companion_enabled"])
        payload = InvoicesRunLLMResult(
            explanations=["Invoices mostly healthy"],
            ranked_documents=[RankedDocument(document_id="1", priority="high", reason="Overdue and high amount")],
            suggested_classifications=[
                SuggestedClassification(document_id="1", suggested_account_code="6200", confidence=0.7, reason="Software"),
            ],
            suggested_followups=["Confirm due date on invoice 1"],
        )
        with mock.patch("core.agentic_invoices.reason_about_invoices_run", return_value=payload) as mock_reason:
            data = self._upload_basic_run(file_count=1)
            mock_reason.assert_called_once()

        run = InvoiceRun.objects.get(pk=data["run_id"])
        self.assertTrue(run.llm_ranked_documents)
        detail_resp = self.client.get(f"/api/agentic/invoices/run/{run.id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIn("llm_suggested_followups", detail_resp.json())

    def test_llm_not_called_when_disabled(self):
        with mock.patch("core.agentic_invoices.reason_about_invoices_run") as mock_reason:
            data = self._upload_basic_run(file_count=1)
            mock_reason.assert_not_called()
        run = InvoiceRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.llm_explanations, [])
