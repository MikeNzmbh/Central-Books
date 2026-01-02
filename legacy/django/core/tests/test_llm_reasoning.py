import json

from django.test import SimpleTestCase

from core.llm_reasoning import (
    BooksReviewLLMResult,
    BankReviewLLMResult,
    InvoicesRunLLMResult,
    ReceiptsRunLLMResult,
    reason_about_bank_review,
    reason_about_books_review,
    reason_about_invoices_run,
    reason_about_receipts_run,
)


class LLMReasoningTests(SimpleTestCase):
    def test_books_reasoning_parses_and_filters_ids(self):
        sample_journals = [
            {"id": 101, "date": "2025-01-01", "amount": "100.00", "accounts": [{"code": "1010"}]},
            {"id": 202, "date": "2025-01-05", "amount": "250.00", "accounts": [{"code": "2020"}]},
        ]
        llm_payload = {
            "explanations": ["Books look mostly healthy."],
            "ranked_issues": [
                {
                    "severity": "high",
                    "title": "Spike",
                    "message": "Big jump",
                    "related_journal_ids": [101, 999],
                    "related_accounts": ["1010", "9999"],
                }
            ],
            "suggested_checks": ["Review account 1010 closely."],
        }
        result = reason_about_books_review(
            metrics={"journals_total": 2},
            findings=[{"code": "TEST", "severity": "low", "message": "hi"}],
            sample_journals=sample_journals,
            llm_client=lambda prompt: json.dumps(llm_payload),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.explanations, ["Books look mostly healthy."])
        self.assertEqual(result.ranked_issues[0].related_journal_ids, [101])
        self.assertEqual(result.ranked_issues[0].related_accounts, ["1010"])

    def test_books_reasoning_returns_none_on_bad_json(self):
        result = reason_about_books_review(
            metrics={},
            findings=[],
            sample_journals=[],
            llm_client=lambda prompt: "not-json",
        )
        self.assertIsNone(result)

    def test_bank_reasoning_filters_unknown_transactions(self):
        transactions = [
            {"transaction_id": "tx-1", "date": "2025-01-01", "description": "Deposit", "amount": "100", "status": "UNMATCHED"},
            {"transaction_id": "tx-2", "date": "2025-01-02", "description": "Withdrawal", "amount": "50", "status": "MATCHED"},
        ]
        llm_payload = {
            "explanations": ["Focus on unmatched lines."],
            "ranked_transactions": [
                {"transaction_id": "tx-1", "priority": "high", "reason": "Unmatched withdrawal"},
                {"transaction_id": "missing", "priority": "low", "reason": "Should be dropped"},
            ],
            "suggested_followups": ["Confirm receipt backing for tx-1."],
        }
        result = reason_about_bank_review(
            metrics={"transactions_unreconciled": 1},
            transactions=transactions,
            llm_client=lambda prompt: json.dumps(llm_payload),
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result.ranked_transactions), 1)
        self.assertEqual(result.ranked_transactions[0].transaction_id, "tx-1")

    def test_bank_reasoning_returns_none_on_parse_failure(self):
        result = reason_about_bank_review(metrics={}, transactions=[], llm_client=lambda prompt: None)
        self.assertIsNone(result)

    def test_receipts_reasoning_filters_ids(self):
        documents = [
            {"document_id": 1, "vendor_name": "Vendor A", "amount": "100", "status": "PROCESSED"},
            {"document_id": 2, "vendor_name": "Vendor B", "amount": "50", "status": "PROCESSED"},
        ]
        llm_payload = {
            "explanations": ["Focus on vendor A."],
            "ranked_documents": [{"document_id": 1, "priority": "high", "reason": "High amount"}, {"document_id": 99, "priority": "low", "reason": "skip"}],
            "suggested_classifications": [
                {"document_id": 2, "suggested_account_code": "6100", "confidence": 0.8, "reason": "Supplies"},
                {"document_id": 77, "suggested_account_code": "9999", "confidence": 0.1, "reason": "skip"},
            ],
            "suggested_followups": ["Confirm receipt for vendor A"],
        }
        result = reason_about_receipts_run(metrics={"documents_total": 2}, documents=documents, llm_client=lambda prompt: json.dumps(llm_payload))
        self.assertIsNotNone(result)
        self.assertEqual(len(result.ranked_documents), 1)
        self.assertEqual(result.ranked_documents[0].document_id, "1")
        self.assertEqual(len(result.suggested_classifications), 1)
        self.assertEqual(result.suggested_classifications[0].document_id, "2")

    def test_invoices_reasoning_handles_invalid_json(self):
        result = reason_about_invoices_run(metrics={}, documents=[], llm_client=lambda prompt: "oops")
        self.assertIsNone(result)

    def test_invoices_reasoning_filters_ids(self):
        documents = [{"document_id": "doc-1", "vendor_name": "Vendor", "amount": "200"}]
        llm_payload = {
            "explanations": ["Look at doc-1"],
            "ranked_documents": [{"document_id": "doc-1", "priority": "high", "reason": "Overdue"}, {"document_id": "missing", "priority": "low", "reason": "skip"}],
            "suggested_classifications": [{"document_id": "doc-1", "suggested_account_code": "6200", "confidence": 0.9, "reason": "Software"}],
            "suggested_followups": ["Confirm due date"],
        }
        result = reason_about_invoices_run(metrics={}, documents=documents, llm_client=lambda prompt: json.dumps(llm_payload))
        self.assertIsNotNone(result)
        self.assertEqual(len(result.ranked_documents), 1)
        self.assertEqual(result.ranked_documents[0].document_id, "doc-1")
