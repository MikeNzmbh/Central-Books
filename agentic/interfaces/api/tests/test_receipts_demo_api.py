"""
Tests for Receipts Demo API

Tests the POST /agentic/demo/receipts-run/ endpoint.
"""

import json

from django.test import TestCase, Client
from django.urls import reverse


class ReceiptsDemoAPITests(TestCase):
    """Tests for the receipts demo API endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.url = reverse("agentic_receipts_demo_run")

    def test_receipts_demo_run_basic(self):
        """Basic happy path test - processes documents and returns results."""
        payload = {
            "documents": [
                {"filename": "office_receipt.pdf", "content": "fake-content"},
                {"filename": "coffee_receipt.pdf", "content": "another-doc"},
            ]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["workflow_name"], "receipts_to_journal_entries")
        self.assertIn(data["status"], ["success", "partial"])
        self.assertIsInstance(data["extracted_documents"], list)
        self.assertIsInstance(data["transactions"], list)
        self.assertIsInstance(data["journal_entries"], list)
        self.assertEqual(len(data["extracted_documents"]), 2)
        self.assertEqual(len(data["journal_entries"]), 2)

    def test_receipts_demo_requires_documents(self):
        """Should return 400 when documents array is missing."""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("documents", response.json()["detail"].lower())

    def test_receipts_demo_requires_non_empty_documents(self):
        """Should return 400 when documents array is empty."""
        response = self.client.post(
            self.url,
            data=json.dumps({"documents": []}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("documents", response.json()["detail"].lower())

    def test_receipts_demo_includes_compliance_and_audit(self):
        """Response should include compliance and audit fields."""
        payload = {
            "documents": [{"filename": "test.pdf", "content": "x"}]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("compliance", data)
        self.assertIn("audit", data)

    def test_receipts_demo_includes_steps(self):
        """Response should include workflow steps with status."""
        payload = {
            "documents": [{"filename": "test.pdf"}]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("steps", data)
        self.assertEqual(len(data["steps"]), 6)  # 6-step workflow

        step_names = [s["name"] for s in data["steps"]]
        self.assertIn("ingest", step_names)
        self.assertIn("extract", step_names)
        self.assertIn("normalize", step_names)
        self.assertIn("generate_entries", step_names)
        self.assertIn("compliance", step_names)
        self.assertIn("audit", step_names)

    def test_receipts_demo_includes_summary(self):
        """Response should include summary string."""
        payload = {
            "documents": [
                {"filename": "receipt1.pdf"},
                {"filename": "receipt2.pdf"},
            ]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("2 document", data["summary"])
        self.assertIn("2 journal entr", data["summary"])

    def test_receipts_demo_invalid_json(self):
        """Should return 400 for invalid JSON."""
        response = self.client.post(
            self.url,
            data="not valid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid JSON", response.json()["detail"])

    def test_receipts_demo_get_returns_usage_info(self):
        """GET request should return usage information."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("endpoint", data)
        self.assertIn("request_body", data)

    def test_vendor_extraction_based_on_filename(self):
        """Should extract vendor based on filename keywords."""
        payload = {
            "documents": [
                {"filename": "office_supplies.pdf"},
                {"filename": "software_license.pdf"},
            ]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        vendors = [d.get("vendor_name") for d in data["extracted_documents"]]
        self.assertIn("Office Depot", vendors)
        self.assertIn("GitHub", vendors)


class ReceiptsDemoPageTests(TestCase):
    """Tests for the receipts demo page."""

    def test_receipts_demo_page_renders(self):
        """Demo page should render successfully."""
        from django.urls import reverse

        response = self.client.get(reverse("agentic_receipts_demo_page"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("agentic-receipts-root", response.content.decode())
