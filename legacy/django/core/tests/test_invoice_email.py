from datetime import date
import io
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from core.models import (
    Business,
    Customer,
    Invoice,
    InvoiceEmailLog,
    InvoiceEmailTemplate,
)


class InvoiceEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="owner@example.com", password="pass")
        self.business = Business.objects.create(
            name="Acme Co",
            currency="USD",
            owner_user=self.user,
            email_from="billing@acme.example.com",
        )
        self.customer = Customer.objects.create(business=self.business, name="Customer", email="cust@example.com")
        self.invoice = Invoice.objects.create(
            business=self.business,
            customer=self.customer,
            invoice_number="INV-1",
            issue_date=date.today(),
            total_amount=10,
            description="Consulting",
            status=Invoice.Status.SENT,
        )
        self.client.force_login(self.user)

    def test_send_email_requires_recipient(self):
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        resp = self.client.post(f"/api/invoices/{self.invoice.pk}/send_email/", {})
        self.assertEqual(resp.status_code, 400)

    @mock.patch("core.views.EmailMultiAlternatives")
    @mock.patch("core.views.generate_invoice_pdf")
    def test_send_email_logs_success_and_attaches_pdf(self, mock_generate_pdf, mock_email_cls):
        mock_generate_pdf.return_value = io.BytesIO(b"pdf")

        msg_mock = mock.Mock()
        msg_mock.attachments = []

        def _attach(filename=None, content=None, mimetype=None):
            msg_mock.attachments.append({"filename": filename, "content": content, "mimetype": mimetype})

        msg_mock.attach.side_effect = _attach
        msg_mock.attach_alternative = mock.Mock()
        mock_email_cls.return_value = msg_mock

        resp = self.client.post(f"/api/invoices/{self.invoice.pk}/send_email/", {})
        self.assertEqual(resp.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.email_sent_at)
        self.assertEqual(self.invoice.email_to, self.customer.email)
        log = InvoiceEmailLog.objects.filter(invoice=self.invoice).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, InvoiceEmailLog.STATUS_SENT)
        self.assertTrue(any(att.get("mimetype") == "application/pdf" for att in msg_mock.attachments))
        sent_html = msg_mock.attach_alternative.call_args[0][0]
        self.assertIn(str(log.open_token), sent_html)

    def test_open_tracking_sets_fields_once(self):
        log = InvoiceEmailLog.objects.create(
            invoice=self.invoice,
            to_email="cust@example.com",
            subject="Test",
            status=InvoiceEmailLog.STATUS_SENT,
        )
        url = reverse("invoice_email_open", args=[log.open_token])
        resp = self.client.get(url, HTTP_USER_AGENT="TestAgent")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/gif")
        log.refresh_from_db()
        first_opened_at = log.opened_at
        self.assertIsNotNone(first_opened_at)
        self.assertEqual(log.opened_user_agent, "TestAgent")

        resp = self.client.get(url, HTTP_USER_AGENT="TestAgent2")
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.opened_at, first_opened_at)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_email_includes_pdf_attachment(self):
        with mock.patch("core.views.generate_invoice_pdf") as mock_generate_pdf:
            mock_generate_pdf.return_value = io.BytesIO(b"pdf-data")

            resp = self.client.post(f"/api/invoices/{self.invoice.pk}/send_email/", {})
            self.assertEqual(resp.status_code, 200)
            self.assertGreaterEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            pdf_attachments = [
                att for att in email.attachments if isinstance(att, tuple) and att[2] == "application/pdf"
            ]
            self.assertGreaterEqual(len(pdf_attachments), 1)
            self.assertTrue(pdf_attachments[0][0].startswith("Invoice-"))

    def test_invoice_email_template_renders_and_falls_back(self):
        tpl = InvoiceEmailTemplate.objects.create(
            business=self.business,
            subject_template="Hi {{ invoice.invoice_number }} from {{ business.name }}",
            body_template="Link: {{ public_url }}",
        )
        ctx = {"invoice": self.invoice, "business": self.business, "public_url": "http://example.com"}
        subject = tpl.render_subject(ctx, "Default subject")
        body = tpl.render_body(ctx, "Default body")
        self.assertIn(self.invoice.invoice_number, subject)
        self.assertIn(self.business.name, subject)
        self.assertIn("http://example.com", body)

        tpl.subject_template = ""
        tpl.body_template = ""
        self.assertEqual(tpl.render_subject(ctx, "Default subject"), "Default subject")
        self.assertEqual(tpl.render_body(ctx, "Default body"), "Default body")
