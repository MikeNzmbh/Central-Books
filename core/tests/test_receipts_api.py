import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.accounting_defaults import ensure_default_accounts
from core.llm_reasoning import RankedDocument, ReceiptsRunLLMResult, SuggestedClassification
from core.models import Business, ReceiptDocument, ReceiptRun, JournalEntry
from core.agentic_receipts import run_receipts_workflow, ReceiptInputDocument
from core.views_receipts import MAX_FILE_SIZE_BYTES

User = get_user_model()


class ReceiptApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="receipts", password="pass")
        self.business = Business.objects.create(name="Biz", currency="USD", owner_user=self.user)
        ensure_default_accounts(self.business)
        self.client = Client()
        self.client.force_login(self.user)

    def _upload_basic_run(self, file_count=2):
        files = [
            SimpleUploadedFile(f"receipt_{i}.pdf", b"fakecontent", content_type="application/pdf")
            for i in range(file_count)
        ]
        resp = self.client.post("/api/agentic/receipts/run", {"files": files, "default_currency": "USD"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], ReceiptRun.RunStatus.COMPLETED)
        return data

    def test_happy_path_and_approval_idempotent(self):
        data = self._upload_basic_run()
        doc_id = data["documents"][0]["id"]

        approve_resp = self.client.post(f"/api/agentic/receipts/{doc_id}/approve")
        approve_data = approve_resp.json()
        self.assertEqual(approve_resp.status_code, 200, msg=approve_data)
        entry_id = approve_data["journal_entry_id"]
        self.assertTrue(JournalEntry.objects.filter(pk=entry_id).exists())

        # Second approval should not duplicate
        approve_resp2 = self.client.post(f"/api/agentic/receipts/{doc_id}/approve")
        self.assertEqual(approve_resp2.status_code, 200)
        self.assertEqual(approve_resp2.json()["journal_entry_id"], entry_id)

    def test_unsupported_file_type_rejected(self):
        bad_file = SimpleUploadedFile("note.txt", b"noop", content_type="text/plain")
        resp = self.client.post("/api/agentic/receipts/run", {"files": [bad_file]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported", resp.json()["error"])

    def test_oversize_file_rejected(self):
        big_content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        big_file = SimpleUploadedFile("big.pdf", big_content, content_type="application/pdf")
        resp = self.client.post("/api/agentic/receipts/run", {"files": [big_file]})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("too large", resp.json()["error"].lower())

    def test_engine_failure_marks_run_failed(self):
        files = [SimpleUploadedFile("receipt.pdf", b"content", content_type="application/pdf")]
        with mock.patch("core.views_receipts.run_receipts_workflow", side_effect=RuntimeError("boom")):
            resp = self.client.post("/api/agentic/receipts/run", {"files": files})
        self.assertEqual(resp.status_code, 500)
        run = ReceiptRun.objects.first()
        self.assertEqual(run.status, ReceiptRun.RunStatus.FAILED)
        self.assertEqual(run.error_count, run.total_documents)

    def test_tenant_isolation_on_run_detail(self):
        data = self._upload_basic_run(file_count=1)
        run_id = data["run_id"]

        other_user = User.objects.create_user(username="other", password="pass")
        other_business = Business.objects.create(name="Other", currency="USD", owner_user=other_user)
        ensure_default_accounts(other_business)
        client2 = Client()
        client2.force_login(other_user)
        resp = client2.get(f"/api/agentic/receipts/run/{run_id}")
        self.assertEqual(resp.status_code, 404)

    def test_audit_fields_and_metrics_persisted(self):
        data = self._upload_basic_run(file_count=1)
        run = ReceiptRun.objects.get(pk=data["run_id"])
        doc = ReceiptDocument.objects.get(pk=data["documents"][0]["id"])

        self.assertIsNotNone(run.metrics.get("documents_total"))
        self.assertEqual(run.metrics.get("documents_total"), run.total_documents)
        self.assertTrue(run.trace_id)
        self.assertGreaterEqual(len(run.metrics.get("trace_events", [])), 1)
        self.assertIn("audit_score", data["documents"][0])
        self.assertTrue(isinstance(doc.audit_flags, list))
        self.assertIsNotNone(doc.audit_score)

    def test_metrics_change_with_high_risk_and_errors(self):
        files = [
            SimpleUploadedFile("receipt_1500.pdf", b"fake", content_type="application/pdf"),
            SimpleUploadedFile("receipt_error.pdf", b"fake", content_type="application/pdf"),
        ]
        resp = self.client.post("/api/agentic/receipts/run", {"files": files, "default_currency": "USD"})
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        data = resp.json()

        run = ReceiptRun.objects.get(pk=data["run_id"])
        docs = list(ReceiptDocument.objects.filter(run=run).order_by("id"))
        self.assertGreaterEqual(run.metrics.get("documents_high_risk", 0), 1)
        self.assertEqual(run.metrics.get("documents_total"), 2)
        self.assertEqual(run.error_count, 1)
        self.assertEqual(sum(1 for d in docs if d.status == ReceiptDocument.DocumentStatus.ERROR), 1)

    def test_accepts_iso_date_and_cad_currency(self):
        files = [SimpleUploadedFile("receipt_date.pdf", b"fake", content_type="application/pdf")]
        resp = self.client.post(
            "/api/agentic/receipts/run",
            {"files": files, "default_currency": "CAD", "default_date": "2025-12-06"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        data = resp.json()
        self.assertEqual(data["status"], ReceiptRun.RunStatus.COMPLETED)
        self.assertTrue(ReceiptRun.objects.filter(pk=data["run_id"]).exists())

    def test_weird_hints_do_not_block_upload(self):
        files = [SimpleUploadedFile("receipt_bad_date.pdf", b"fake", content_type="application/pdf")]
        resp = self.client.post(
            "/api/agentic/receipts/run",
            {
                "files": files,
                "default_currency": "???",
                "default_date": "12/06/2025 not-a-date",
                "default_vendor": "hint vendor",
                "default_category": "hint category",
            },
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        payload = resp.json()
        self.assertEqual(payload["status"], ReceiptRun.RunStatus.COMPLETED)
        doc = ReceiptDocument.objects.get(pk=payload["documents"][0]["id"])
        hints = doc.extracted_payload.get("user_hints", {})
        self.assertEqual(hints.get("vendor_hint"), "hint vendor")
        self.assertEqual(hints.get("category_hint"), "hint category")

    def test_llm_fields_persist_when_companion_enabled(self):
        self.business.ai_companion_enabled = True
        self.business.save(update_fields=["ai_companion_enabled"])
        payload = ReceiptsRunLLMResult(
            explanations=["Focus on vendor A"],
            ranked_documents=[RankedDocument(document_id="1", priority="high", reason="High risk")],
            suggested_classifications=[
                SuggestedClassification(document_id="1", suggested_account_code="6100", confidence=0.9, reason="Software"),
            ],
            suggested_followups=["Confirm receipt"],
        )
        with mock.patch("core.agentic_receipts.reason_about_receipts_run", return_value=payload) as mock_reason:
            data = self._upload_basic_run(file_count=1)
            mock_reason.assert_called_once()

        run = ReceiptRun.objects.get(pk=data["run_id"])
        self.assertTrue(run.llm_explanations)
        self.assertTrue(run.llm_ranked_documents)
        detail_resp = self.client.get(f"/api/agentic/receipts/run/{run.id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIn("llm_suggested_followups", detail_resp.json())

    def test_llm_not_called_when_disabled(self):
        with mock.patch("core.agentic_receipts.reason_about_receipts_run") as mock_reason:
            data = self._upload_basic_run(file_count=1)
            mock_reason.assert_not_called()
        run = ReceiptRun.objects.get(pk=data["run_id"])
        self.assertEqual(run.llm_explanations, [])

    def test_filename_camera_pattern_does_not_infer_amount_or_vendor(self):
        files = [SimpleUploadedFile("IMG_8253.png", b"fake", content_type="image/png")]
        resp = self.client.post("/api/agentic/receipts/run", {"files": files, "default_currency": "CAD"})
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        data = resp.json()
        run = ReceiptRun.objects.get(pk=data["run_id"])
        doc = ReceiptDocument.objects.get(run=run)
        payload = doc.extracted_payload
        self.assertNotEqual(payload.get("vendor"), "IMG_8253")
        self.assertEqual(payload.get("total"), "10.00")

    def test_user_overrides_are_respected_on_approval(self):
        data = self._upload_basic_run(file_count=1)
        doc_id = data["documents"][0]["id"]
        override_payload = {
          "overrides": {
            "vendor": "Custom Vendor",
            "amount": "123.45",
            "date": "2025-02-01",
            "currency": "CAD",
            "category": "Software"
          }
        }
        approve_resp = self.client.post(
            f"/api/agentic/receipts/{doc_id}/approve",
            data=json.dumps(override_payload),
            content_type="application/json",
        )
        self.assertEqual(approve_resp.status_code, 200, msg=approve_resp.content)
        doc = ReceiptDocument.objects.get(pk=doc_id)
        entry = doc.posted_journal_entry
        self.assertIsNotNone(entry)
        self.assertEqual(str(entry.description), "Receipt - Custom Vendor")
        lines = list(entry.lines.all())
        self.assertEqual(len(lines), 2)
        debits = [l.debit for l in lines]
        credits = [l.credit for l in lines]
        self.assertIn(Decimal("123.45"), debits)
        self.assertIn(Decimal("123.45"), credits)
        self.assertEqual(doc.extracted_payload.get("user_edits", {}).get("vendor"), "Custom Vendor")


class ReceiptWorkflowToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="toggle", password="pass")
        self.business = Business.objects.create(name="ToggleBiz", currency="USD", owner_user=self.user)
        ensure_default_accounts(self.business)

    def test_ai_companion_enriches_audit(self):
        doc = ReceiptInputDocument(
            document_id=1,
            storage_key="doc-key",
            original_filename="wire_transfer_1500.pdf",
            currency_hint="EUR",
            vendor_hint="Manual Wire Services",
        )
        basic = run_receipts_workflow(
            business_id=self.business.id,
            documents=[doc],
            default_currency="USD",
            triggered_by_user_id=self.user.id,
            ai_companion_enabled=False,
        )
        rich = run_receipts_workflow(
            business_id=self.business.id,
            documents=[doc],
            default_currency="USD",
            triggered_by_user_id=self.user.id,
            ai_companion_enabled=True,
        )

        basic_doc = basic.documents[0]
        rich_doc = rich.documents[0]

        self.assertGreaterEqual(len(rich_doc.audit_flags), len(basic_doc.audit_flags))
        self.assertGreater(rich_doc.audit_score, basic_doc.audit_score)
        self.assertGreaterEqual(rich.metrics.get("agent_retries", 0), 1)
