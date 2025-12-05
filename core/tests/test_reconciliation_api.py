import calendar
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.accounting_defaults import ensure_default_accounts
from core.models import (
    BankAccount,
    BankReconciliationMatch,
    BankTransaction,
    Business,
    JournalEntry,
    JournalLine,
    ReconciliationSession,
)
from core.services.bank_reconciliation import set_reconciled_state


class ReconciliationV1APITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="apiuser", password="pass")
        self.business = Business.objects.create(
            name="API Co",
            currency="USD",
            owner_user=self.user,
        )
        self.defaults = ensure_default_accounts(self.business)
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="Operating",
            usage_role=BankAccount.UsageRole.OPERATING,
            account=self.defaults["cash"],
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.offset_account = self.defaults["sales"]

    def _make_bank_tx(self, amount: Decimal, tx_date=None) -> BankTransaction:
        tx_date = tx_date or timezone.localdate()
        return BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=tx_date,
            description="Bank line",
            amount=amount,
        )

    def _post_bank_entry(self, amount: Decimal, entry_date=None) -> JournalEntry:
        entry_date = entry_date or timezone.localdate()
        je = JournalEntry.objects.create(
            business=self.business,
            date=entry_date,
            description="Ledger entry",
        )
        # Bank side
        JournalLine.objects.create(
            journal_entry=je,
            account=self.bank_account.account,
            debit=amount if amount > 0 else Decimal("0.00"),
            credit=abs(amount) if amount < 0 else Decimal("0.00"),
            description="Bank",
        )
        # Offset side to balance entry
        if self.offset_account:
            JournalLine.objects.create(
                journal_entry=je,
                account=self.offset_account,
                debit=abs(amount) if amount < 0 else Decimal("0.00"),
                credit=amount if amount > 0 else Decimal("0.00"),
                description="Offset",
            )
        return je

    def _get_session_id(self, start: date, end: date) -> int:
        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["session"]["id"]

    def _make_session(self, start: date, end: date) -> ReconciliationSession:
        session_id = self._get_session_id(start, end)
        return ReconciliationSession.objects.get(pk=session_id)

    def test_accounts_endpoint_handles_empty(self):
        BankAccount.objects.all().delete()
        resp = self.client.get(reverse("api_reco_accounts_v1"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_accounts_endpoint_lists_bank_accounts(self):
        resp = self.client.get(reverse("api_reco_accounts_v1"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.bank_account.id)

    def test_periods_endpoint_returns_current_month_when_no_activity(self):
        resp = self.client.get(reverse("api_reco_periods_v1", args=[self.bank_account.id]))
        self.assertEqual(resp.status_code, 200)
        periods = resp.json()
        self.assertGreaterEqual(len(periods), 1)
        self.assertIn("start_date", periods[0])
        self.assertIn("end_date", periods[0])

    def test_session_creation_sets_opening_and_ledger_balances(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        self._post_bank_entry(Decimal("50.00"), entry_date=start - timedelta(days=1))
        self._post_bank_entry(Decimal("20.00"), entry_date=start + timedelta(days=1))

        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        session = resp.json()["session"]
        self.assertEqual(session["opening_balance"], "50.00")
        self.assertEqual(session["ledger_ending_balance"], "70.00")
        self.assertEqual(session["cleared_balance"], "50.00")
        self.assertEqual(session["difference"], "20.00")

    def test_opening_balance_update_updates_cleared_balance(self):
        start = date(2024, 2, 1)
        end = date(2024, 2, 29)

        # Create session
        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        session_id = resp.json()["session"]["id"]

        # Update opening and statement ending balances
        update_resp = self.client.post(
            reverse("api_reco_set_statement_balance_v1", args=[session_id]),
            data=json.dumps({"opening_balance": "1000.00", "statement_ending_balance": "1500.00"}),
            content_type="application/json",
        )
        self.assertEqual(update_resp.status_code, 200)
        session = update_resp.json()["session"]
        self.assertEqual(session["opening_balance"], "1000.00")
        self.assertEqual(session["cleared_balance"], "1000.00")
        self.assertEqual(session["difference"], "500.00")

    def test_opening_balance_update_includes_reconciled_transactions(self):
        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        tx = self._make_bank_tx(Decimal("200.00"), tx_date=start)
        tx.status = BankTransaction.TransactionStatus.MATCHED
        tx.is_reconciled = True
        tx.reconciliation_status = BankTransaction.RECO_STATUS_RECONCILED
        tx.save()

        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        session_id = resp.json()["session"]["id"]

        update_resp = self.client.post(
            reverse("api_reco_set_statement_balance_v1", args=[session_id]),
            data=json.dumps({"opening_balance": "1000.00", "statement_ending_balance": "1500.00"}),
            content_type="application/json",
        )
        self.assertEqual(update_resp.status_code, 200)
        session = update_resp.json()["session"]
        self.assertEqual(session["cleared_balance"], "1200.00")
        self.assertEqual(session["difference"], "300.00")

    def test_feed_groups_transactions(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        tx_new = self._make_bank_tx(Decimal("25.00"), tx_date=start)
        tx_matched = self._make_bank_tx(Decimal("10.00"), tx_date=start)
        tx_matched.status = BankTransaction.TransactionStatus.MATCHED
        tx_matched.is_reconciled = True
        tx_matched.reconciliation_status = BankTransaction.RECO_STATUS_RECONCILED
        tx_matched.save()
        tx_excluded = self._make_bank_tx(Decimal("5.00"), tx_date=start)
        tx_excluded.status = BankTransaction.TransactionStatus.EXCLUDED
        tx_excluded.save()

        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        feed = resp.json()["feed"]
        self.assertEqual(len(feed["new"]), 1)
        self.assertEqual(feed["new"][0]["id"], tx_new.id)
        self.assertEqual(len(feed["matched"]), 1)
        self.assertEqual(feed["matched"][0]["reconciliation_status"], BankTransaction.RECO_STATUS_RECONCILED)
        self.assertEqual(len(feed["excluded"]), 1)

    def test_match_and_unmatch_flow(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        tx = self._make_bank_tx(Decimal("25.00"), tx_date=start)
        je = self._post_bank_entry(Decimal("25.00"), entry_date=start)

        session_resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        session_id = session_resp.json()["session"]["id"]

        match_resp = self.client.post(
            reverse("api_reco_match_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "journal_entry_id": je.id}),
            content_type="application/json",
        )
        self.assertEqual(match_resp.status_code, 200)
        tx.refresh_from_db()
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.MATCHED_SINGLE)
        self.assertEqual(tx.reconciliation_status, BankTransaction.RECO_STATUS_RECONCILED)
        self.assertTrue(BankReconciliationMatch.objects.filter(bank_transaction=tx, journal_entry=je).exists())

        unmatch_resp = self.client.post(
            reverse("api_reco_unmatch_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id}),
            content_type="application/json",
        )
        self.assertEqual(unmatch_resp.status_code, 200)
        tx.refresh_from_db()
        self.assertFalse(tx.is_reconciled)
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.NEW)
        self.assertEqual(tx.reconciliation_status, BankTransaction.RECO_STATUS_UNRECONCILED)
        self.assertFalse(BankReconciliationMatch.objects.filter(bank_transaction=tx).exists())

    def test_match_requires_existing_journal_entry(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        tx = self._make_bank_tx(Decimal("25.00"), tx_date=start)
        session_resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        session_id = session_resp.json()["session"]["id"]

        resp = self.client.post(
            reverse("api_reco_match_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No existing transaction found", resp.json()["error"])

    def test_confirm_match_requires_journal_entry(self):
        start = timezone.localdate().replace(day=1)
        tx = self._make_bank_tx(Decimal("25.00"), tx_date=start)
        resp = self.client.post(
            reverse("api_reco_confirm_match"),
            data=json.dumps({"bank_transaction_id": tx.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No existing transaction found", resp.json()["error"])

    def test_exclude_and_complete_session(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        tx = self._make_bank_tx(Decimal("40.00"), tx_date=start)
        self._post_bank_entry(Decimal("40.00"), entry_date=start)

        session_resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        session_payload = session_resp.json()["session"]
        session_id = session_payload["id"]

        exclude_resp = self.client.post(
            reverse("api_reco_exclude_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "excluded": True}),
            content_type="application/json",
        )
        self.assertEqual(exclude_resp.status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.EXCLUDED)

        # Align statement ending balance with opening to allow completion with no cleared txs
        set_resp = self.client.post(
            reverse("api_reco_set_statement_balance_v1", args=[session_id]),
            data=json.dumps({"statement_ending_balance": session_payload["opening_balance"]}),
            content_type="application/json",
        )
        self.assertEqual(set_resp.status_code, 200)

        complete_resp = self.client.post(reverse("reconciliation-complete-session", args=[session_id]))
        self.assertEqual(complete_resp.status_code, 200)
        session_payload = complete_resp.json()["session"]
        self.assertEqual(session_payload["status"], "COMPLETED")
        self.assertEqual(session_payload["unreconciled_count"], 0)
        self.assertEqual(session_payload["reconciled_percent"], 100.0)

    def test_complete_session_requires_zero_difference(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        self._make_bank_tx(Decimal("15.00"), tx_date=start)

        session_resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        session_id = session_resp.json()["session"]["id"]
        session = ReconciliationSession.objects.get(pk=session_id)
        session.closing_balance = Decimal("10.00")
        session.save(update_fields=["closing_balance"])

        complete_resp = self.client.post(reverse("reconciliation-complete-session", args=[session_id]))
        self.assertEqual(complete_resp.status_code, 400)
        self.assertEqual(complete_resp.json().get("code"), "difference_not_zero")

    def test_complete_session_requires_all_transactions_reconciled_or_excluded(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        self._make_bank_tx(Decimal("20.00"), tx_date=start)

        session_resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        session_id = session_resp.json()["session"]["id"]

        complete_resp = self.client.post(reverse("reconciliation-complete-session", args=[session_id]))
        self.assertEqual(complete_resp.status_code, 400)
        self.assertEqual(complete_resp.json().get("code"), "unreconciled_transactions_remaining")

    def test_exclude_include_keep_canonical_flags(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        tx = self._make_bank_tx(Decimal("15.00"), tx_date=start)
        session_id = self._get_session_id(start, end)

        exclude_resp = self.client.post(
            reverse("api_reco_exclude_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "excluded": True}),
            content_type="application/json",
        )
        self.assertEqual(exclude_resp.status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.reconciliation_session_id, session_id)
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.EXCLUDED)
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(tx.reconciliation_status, BankTransaction.RECO_STATUS_RECONCILED)

        include_resp = self.client.post(
            reverse("api_reco_exclude_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "excluded": False}),
            content_type="application/json",
        )
        self.assertEqual(include_resp.status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.reconciliation_session_id, session_id)
        self.assertFalse(tx.is_reconciled)
        self.assertEqual(tx.reconciliation_status, BankTransaction.RECO_STATUS_UNRECONCILED)
        self.assertEqual(tx.status, BankTransaction.TransactionStatus.NEW)

    def test_out_of_period_transactions_rejected(self):
        today = timezone.localdate()
        start = today.replace(day=1)
        _, last_day = calendar.monthrange(start.year, start.month)
        end = date(start.year, start.month, last_day)
        tx = self._make_bank_tx(Decimal("30.00"), tx_date=end + timedelta(days=15))
        je = self._post_bank_entry(Decimal("30.00"), entry_date=end + timedelta(days=15))
        session_id = self._get_session_id(start, end)

        resp = self.client.post(
            reverse("api_reco_match_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "journal_entry_id": je.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("outside of the session period", resp.json()["detail"])

        resp = self.client.post(
            reverse("api_reco_exclude_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "excluded": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("out of period", str(resp.json()))

    def test_cannot_move_transaction_between_sessions_without_unmatch(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        tx = self._make_bank_tx(Decimal("10.00"), tx_date=start)
        primary_session_id = self._get_session_id(start, end)
        primary_session = ReconciliationSession.objects.get(pk=primary_session_id)
        # Attach tx to primary session via helper to ensure flags are set
        set_reconciled_state(
            tx,
            reconciled=False,
            session=primary_session,
            status=BankTransaction.TransactionStatus.NEW,
        )

        # Overlapping session with different period bounds
        alt_session = ReconciliationSession.objects.create(
            business=self.business,
            bank_account=self.bank_account,
            statement_start_date=start,
            statement_end_date=date(2024, 1, 15),
            opening_balance=Decimal("0.00"),
            closing_balance=Decimal("0.00"),
        )
        je = self._post_bank_entry(Decimal("10.00"), entry_date=start)

        resp = self.client.post(
            reverse("api_reco_match_v1", args=[alt_session.id]),
            data=json.dumps({"transaction_id": tx.id, "journal_entry_id": je.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("another reconciliation session", resp.json()["error"])

    def test_completed_session_is_locked(self):
        start = timezone.localdate().replace(day=1)
        _, last_day = calendar.monthrange(start.year, start.month)
        end = date(start.year, start.month, last_day)
        tx = self._make_bank_tx(Decimal("40.00"), tx_date=start)
        je = self._post_bank_entry(Decimal("40.00"), entry_date=start)
        session_id = self._get_session_id(start, end)

        match_resp = self.client.post(
            reverse("api_reco_match_v1", args=[session_id]),
            data=json.dumps({"transaction_id": tx.id, "journal_entry_id": je.id}),
            content_type="application/json",
        )
        self.assertEqual(match_resp.status_code, 200)

        payload = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        ).json()["session"]
        close_resp = self.client.post(
            reverse("api_reco_set_statement_balance_v1", args=[session_id]),
            data=json.dumps({"statement_ending_balance": payload["cleared_balance"]}),
            content_type="application/json",
        )
        self.assertEqual(close_resp.status_code, 200)

        complete_resp = self.client.post(reverse("reconciliation-complete-session", args=[session_id]))
        self.assertEqual(complete_resp.status_code, 200)

        # Attempts to mutate should fail
        urls_and_bodies = [
            (reverse("api_reco_match_v1", args=[session_id]), {"transaction_id": tx.id, "journal_entry_id": je.id}),
            (reverse("api_reco_unmatch_v1", args=[session_id]), {"transaction_id": tx.id}),
            (reverse("api_reco_exclude_v1", args=[session_id]), {"transaction_id": tx.id, "excluded": True}),
            (reverse("api_reco_set_statement_balance_v1", args=[session_id]), {"statement_ending_balance": "0.00"}),
        ]
        for url, body in urls_and_bodies:
            resp = self.client.post(url, data=json.dumps(body), content_type="application/json")
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json().get("code"), "session_completed")

    def test_session_payload_uses_session_transactions_only(self):
        start = date(2024, 1, 1)
        _, last_day = calendar.monthrange(start.year, start.month)
        end = date(2024, 1, last_day)

        session = ReconciliationSession.objects.create(
            business=self.business,
            bank_account=self.bank_account,
            statement_start_date=start,
            statement_end_date=end,
            opening_balance=Decimal("100.00"),
            closing_balance=Decimal("300.00"),
        )

        tx_matched = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            description="Matched",
            amount=Decimal("100.00"),
            reconciliation_session=session,
            allocated_amount=Decimal("100.00"),
            status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        )
        set_reconciled_state(tx_matched, reconciled=True, session=session, status=BankTransaction.TransactionStatus.MATCHED_SINGLE)

        tx_partial = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            description="Partial",
            amount=Decimal("-80.00"),
            allocated_amount=Decimal("50.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.PARTIAL,
        )
        set_reconciled_state(tx_partial, reconciled=True, session=session, status=BankTransaction.TransactionStatus.PARTIAL)

        tx_excluded = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            description="Excluded",
            amount=Decimal("20.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.EXCLUDED,
        )
        set_reconciled_state(tx_excluded, reconciled=True, session=session, status=BankTransaction.TransactionStatus.EXCLUDED)

        tx_new = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            description="New",
            amount=Decimal("15.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.NEW,
        )
        set_reconciled_state(tx_new, reconciled=False, session=session, status=BankTransaction.TransactionStatus.NEW)

        # Out-of-session reconciled transaction (same bank, overlapping period)
        alt_session = ReconciliationSession.objects.create(
            business=self.business,
            bank_account=self.bank_account,
            statement_start_date=start,
            statement_end_date=date(2024, 1, 15),
            opening_balance=Decimal("0.00"),
            closing_balance=Decimal("0.00"),
        )
        other_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            description="Other session",
            amount=Decimal("500.00"),
            reconciliation_session=alt_session,
            status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        )
        set_reconciled_state(other_tx, reconciled=True, session=alt_session, status=BankTransaction.TransactionStatus.MATCHED_SINGLE)

        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        session_payload = resp.json()["session"]

        self.assertEqual(session_payload["total_transactions"], 4)
        self.assertEqual(session_payload["reconciled_count"], 3)
        self.assertEqual(session_payload["unreconciled_count"], 1)
        self.assertEqual(session_payload["difference"], "150.00")
        self.assertEqual(session_payload["cleared_balance"], "150.00")

    def test_ui_status_and_is_cleared_flags(self):
        start = date(2024, 1, 1)
        _, last_day = calendar.monthrange(start.year, start.month)
        end = date(2024, 1, last_day)
        session = self._make_session(start, end)

        tx_matched = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            amount=Decimal("100.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.MATCHED_SINGLE,
        )
        set_reconciled_state(tx_matched, reconciled=True, session=session, status=BankTransaction.TransactionStatus.MATCHED_SINGLE)

        tx_partial = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            amount=Decimal("-80.00"),
            allocated_amount=Decimal("50.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.PARTIAL,
        )
        set_reconciled_state(tx_partial, reconciled=True, session=session, status=BankTransaction.TransactionStatus.PARTIAL)

        tx_excluded = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            amount=Decimal("20.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.EXCLUDED,
        )
        set_reconciled_state(tx_excluded, reconciled=True, session=session, status=BankTransaction.TransactionStatus.EXCLUDED)

        tx_new = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=start,
            amount=Decimal("15.00"),
            reconciliation_session=session,
            status=BankTransaction.TransactionStatus.NEW,
        )
        set_reconciled_state(tx_new, reconciled=False, session=session, status=BankTransaction.TransactionStatus.NEW)

        resp = self.client.get(
            reverse("api_reconciliation_session"),
            {"account": self.bank_account.id, "start": start.isoformat(), "end": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        session_payload = data["session"]
        self.assertEqual(session_payload["reconciled_count"], 3)
        self.assertEqual(session_payload["excluded_count"], 1)
        self.assertEqual(session_payload["unreconciled_count"], 1)

        feed = data["feed"]
        matched_row = feed["matched"][0]
        self.assertEqual(matched_row["ui_status"], "MATCHED")
        self.assertTrue(matched_row["is_cleared"])
        partial_row = feed["partial"][0]
        self.assertEqual(partial_row["ui_status"], "PARTIAL")
        self.assertTrue(partial_row["is_cleared"])
        excluded_row = feed["excluded"][0]
        self.assertEqual(excluded_row["ui_status"], "EXCLUDED")
        self.assertFalse(excluded_row["is_cleared"])
        new_row = feed["new"][0]
        self.assertEqual(new_row["ui_status"], "NEW")
        self.assertFalse(new_row["is_cleared"])

    def test_reopen_completed_session_changes_status_and_allows_mutations(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        tx = self._make_bank_tx(Decimal("25.00"), tx_date=start)
        je = self._post_bank_entry(Decimal("25.00"), entry_date=start)
        session = self._make_session(start, end)
        # Match and complete
        self.client.post(
            reverse("api_reco_match_v1", args=[session.id]),
            data=json.dumps({"transaction_id": tx.id, "journal_entry_id": je.id}),
            content_type="application/json",
        )
        self.client.post(
            reverse("api_reco_set_statement_balance_v1", args=[session.id]),
            data=json.dumps({"statement_ending_balance": "25.00", "opening_balance": "0.00"}),
            content_type="application/json",
        )
        complete_resp = self.client.post(reverse("reconciliation-complete-session", args=[session.id]))
        self.assertEqual(complete_resp.status_code, 200)
        # Reopen as staff
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        reopen_resp = self.client.post(reverse("reconciliation-reopen-session", args=[session.id]))
        self.assertEqual(reopen_resp.status_code, 200)
        reopened = reopen_resp.json()["session"]
        self.assertEqual(reopened["status"], ReconciliationSession.Status.IN_PROGRESS)
        # Now unmatch should work (no session_completed error)
        unmatch_resp = self.client.post(
            reverse("api_reco_unmatch_v1", args=[session.id]),
            data=json.dumps({"transaction_id": tx.id}),
            content_type="application/json",
        )
        self.assertEqual(unmatch_resp.status_code, 200)

    def test_reopen_in_progress_session_not_allowed(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        session = self._make_session(start, end)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        resp = self.client.post(reverse("reconciliation-reopen-session", args=[session.id]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Only completed sessions", resp.json().get("error", ""))

    def test_reopen_requires_staff(self):
        start = timezone.localdate().replace(day=1)
        end = start + timedelta(days=27)
        session = self._make_session(start, end)
        session.status = ReconciliationSession.Status.COMPLETED
        session.save(update_fields=["status"])
        resp = self.client.post(reverse("reconciliation-reopen-session", args=[session.id]))
        self.assertEqual(resp.status_code, 403)
        self.assertIn("permission", resp.json().get("error", "").lower())
