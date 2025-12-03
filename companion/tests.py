from __future__ import annotations

from datetime import date, timedelta
import json
from unittest import mock
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from companion.llm import generate_insights_for_snapshot
from companion.models import CompanionInsight, CompanionSuggestedAction, WorkspaceCompanionProfile, WorkspaceMemory
from companion.services import (
    create_health_snapshot,
    generate_bank_match_suggestions_for_workspace,
    generate_overdue_invoice_suggestions_for_workspace,
    generate_uncategorized_expense_suggestions_for_workspace,
    get_latest_health_snapshot,
)
from core.models import Account, BankAccount, BankTransaction, Business, Category, Customer, Expense, Invoice, JournalEntry, JournalLine, Supplier


User = get_user_model()


class CompanionApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="apiuser", email="api@example.com", password="pass")
        self.workspace = Business.objects.create(
            name="API Co",
            currency="USD",
            owner_user=self.user,
        )
        self.category = Category.objects.create(
            business=self.workspace,
            name="Operations",
            type=Category.CategoryType.EXPENSE,
        )
        self.supplier = Supplier.objects.create(business=self.workspace, name="Acme Supplies")
        self.client.force_login(self.user)

    def test_overview_endpoint_returns_valid_payload(self):
        url = reverse("companion:overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("health_index", payload)
        self.assertIn("raw_metrics", payload)
        self.assertIn("next_refresh_at", payload)
        self.assertIsInstance(payload["health_index"].get("score"), int)
        self.assertIsInstance(payload["health_index"].get("breakdown"), dict)
        self.assertIn("insights", payload)

    def test_overview_blocks_unauthenticated_users(self):
        self.client.logout()
        url = reverse("companion:overview")
        response = self.client.get(url)
        self.assertIn(response.status_code, {401, 403})

    def test_overview_uses_latest_snapshot(self):
        older = CompanionInsight.objects.create(
            workspace=self.workspace,
            domain="test",
            title="Old insight",
            body="Body",
            severity="info",
        )
        # Create two snapshots, newest should be used.
        first = create_health_snapshot(self.workspace)
        first.created_at = timezone.now() - timedelta(hours=2)
        first.save(update_fields=["created_at"])
        latest = create_health_snapshot(self.workspace)

        url = reverse("companion:overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["health_index"]["score"], latest.score)
        self.assertGreaterEqual(payload["health_index"]["score"], first.score)
        self.assertIn(older.title, [i["title"] for i in payload["insights"]])

    def test_overview_includes_insights(self):
        insight = CompanionInsight.objects.create(
            workspace=self.workspace,
            domain="reconciliation",
            title="Clear recon queue",
            body="Items pending reconciliation",
            severity="warning",
            context=CompanionInsight.CONTEXT_RECONCILIATION,
        )
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        titles = [i["title"] for i in payload["insights"]]
        self.assertIn(insight.title, titles)
        matching = next((i for i in payload["insights"] if i["id"] == insight.id), None)
        self.assertIsNotNone(matching)
        self.assertEqual(matching.get("context"), CompanionInsight.CONTEXT_RECONCILIATION)

    @override_settings(COMPANION_LLM_ENABLED=False)
    def test_llm_disabled_returns_null_summary(self):
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("llm_narrative", payload)
        self.assertIsNone(payload["llm_narrative"]["summary"])

    @override_settings(
        COMPANION_LLM_ENABLED=True,
        COMPANION_LLM_API_BASE="https://api.example.com",
        COMPANION_LLM_API_KEY="test-key",
        COMPANION_LLM_MODEL="stub-model",
    )
    @mock.patch("companion.llm.call_companion_llm")
    def test_llm_narrative_parsed_into_response(self, mock_llm):
        insight = CompanionInsight.objects.create(
            workspace=self.workspace,
            domain="reconciliation",
            title="Clear recon queue",
            body="Items pending reconciliation",
            severity="warning",
        )
        mock_llm.return_value = json.dumps(
            {"summary": "Books look stable. Reconcile soon.", "insight_explanations": {str(insight.id): "Clear 3 items."}}
        )
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["llm_narrative"]["summary"], "Books look stable. Reconcile soon.")
        self.assertEqual(payload["llm_narrative"]["insight_explanations"].get(str(insight.id)), "Clear 3 items.")

    def test_expense_save_records_memory(self):
        Expense.objects.create(
            business=self.workspace,
            supplier=self.supplier,
            category=self.category,
            description="Office chairs",
            amount=Decimal("120.00"),
        )
        memory = WorkspaceMemory.objects.filter(workspace=self.workspace, key="vendor:acme supplies").first()
        self.assertIsNotNone(memory)
        self.assertEqual(memory.value.get("category_id"), self.category.id)

    def test_overview_includes_new_actions_flags(self):
        CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={"bank_transaction_id": 1},
            confidence=Decimal("0.5"),
            summary="Review bank matches",
            context=CompanionSuggestedAction.CONTEXT_BANK,
        )

        response = self.client.get(reverse("companion:overview") + "?context=bank")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("has_new_actions"))
        self.assertEqual(payload.get("new_actions_count"), 1)

    def test_mark_context_seen_resets_new_actions(self):
        profile, _ = WorkspaceCompanionProfile.objects.get_or_create(workspace=self.workspace)
        profile.last_seen_bank_at = timezone.now() - timedelta(days=2)
        profile.save(update_fields=["last_seen_bank_at"])

        action = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={"bank_transaction_id": 2},
            confidence=Decimal("0.7"),
            summary="New bank match",
            context=CompanionSuggestedAction.CONTEXT_BANK,
        )
        action.created_at = timezone.now() - timedelta(hours=1)
        action.save(update_fields=["created_at"])

        initial = self.client.get(reverse("companion:overview") + "?context=bank").json()
        self.assertTrue(initial.get("has_new_actions"))
        self.assertGreater(initial.get("new_actions_count", 0), 0)

        res = self.client.post(
            reverse("companion:context_seen"),
            data=json.dumps({"context": "bank"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)

        follow = self.client.get(reverse("companion:overview") + "?context=bank").json()
        self.assertFalse(follow.get("has_new_actions"))
        self.assertEqual(follow.get("new_actions_count"), 0)

    def test_context_seen_invalid_context_rejected(self):
        res = self.client.post(
            reverse("companion:context_seen"),
            data=json.dumps({"context": "invalid"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)


class CompanionInsightLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="insights", email="i@example.com", password="pass")
        self.workspace = Business.objects.create(name="InsightsCo", currency="USD", owner_user=self.user)
        self.client.force_login(self.user)

    def test_insight_dismiss(self):
        insight = CompanionInsight.objects.create(
            workspace=self.workspace,
            domain="invoices",
            title="Overdue invoices",
            body="Follow up",
            severity="info",
        )
        url = reverse("companion:dismiss_insight", args=[insight.id])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 204)
        insight.refresh_from_db()
        self.assertTrue(insight.is_dismissed)
        self.assertIsNotNone(insight.dismissed_at)

    def test_dismiss_requires_auth(self):
        insight = CompanionInsight.objects.create(
            workspace=self.workspace,
            domain="bank",
            title="Bank issue",
            body="Review",
            severity="warning",
        )
        self.client.logout()
        res = self.client.post(reverse("companion:dismiss_insight", args=[insight.id]))
        self.assertIn(res.status_code, {401, 403})

    def test_dismiss_only_affects_target(self):
        i1 = CompanionInsight.objects.create(workspace=self.workspace, domain="a", title="A", body="a", severity="info")
        i2 = CompanionInsight.objects.create(workspace=self.workspace, domain="b", title="B", body="b", severity="info")
        self.client.post(reverse("companion:dismiss_insight", args=[i1.id]))
        i1.refresh_from_db()
        i2.refresh_from_db()
        self.assertTrue(i1.is_dismissed)
        self.assertFalse(i2.is_dismissed)


class CompanionLLMGenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="llm", email="llm@example.com", password="pass")
        self.workspace = Business.objects.create(name="LLMCo", currency="USD", owner_user=self.user)
        self.snapshot = create_health_snapshot(self.workspace)

    def test_sample_insight_generation(self):
        generated = generate_insights_for_snapshot(self.snapshot)
        self.assertGreaterEqual(len(generated), 1)

    def test_insight_saved_correctly(self):
        generate_insights_for_snapshot(self.snapshot)
        insight = CompanionInsight.objects.filter(workspace=self.workspace).first()
        self.assertIsNotNone(insight)
        self.assertIn(insight.domain, {"reconciliation", "invoices", "expenses", "tax_fx", "ledger_integrity"})

    def test_insight_visible_in_overview_api(self):
        generate_insights_for_snapshot(self.snapshot)
        client = self.client
        client.force_login(self.user)
        res = client.get(reverse("companion:overview"))
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["insights"])


class CompanionCommandsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cmd", email="cmd@example.com", password="pass")
        self.workspace = Business.objects.create(name="CmdCo", currency="USD", owner_user=self.user)
        self.snapshot = create_health_snapshot(self.workspace)

    def test_command_generate_sample_insights(self):
        call_command("companion_generate_sample_insights", hours=24)
        self.assertTrue(CompanionInsight.objects.filter(workspace=self.workspace).exists())

    def test_memory_seed_creates_entries(self):
        call_command("companion_seed_test_data")
        self.assertTrue(WorkspaceMemory.objects.exists())

    def test_overview_uses_latest_snapshot(self):
        # Ensure existing snapshot is reused when fresh.
        latest = create_health_snapshot(self.workspace)
        res = self.client
        res.force_login(self.user)
        response = res.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["health_index"]["score"], latest.score)


class CompanionMaintenanceCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="maint", email="maint@example.com", password="pass")

    def test_maintenance_runs_with_no_workspaces(self):
        call_command("companion_run_maintenance")
        self.assertEqual(Business.objects.count(), 0)

    def test_companion_run_maintenance_refreshes_stale_workspaces(self):
        workspace = Business.objects.create(name="MaintCo", currency="USD", owner_user=self.user)
        customer = Customer.objects.create(business=workspace, name="Maint Customer")

        snapshot = create_health_snapshot(workspace)
        snapshot.created_at = timezone.now() - timedelta(days=2)
        snapshot.save(update_fields=["created_at"])

        Invoice.objects.create(
            business=workspace,
            customer=customer,
            invoice_number="INV-200",
            status=Invoice.Status.SENT,
            issue_date=timezone.now().date() - timedelta(days=30),
            due_date=timezone.now().date() - timedelta(days=10),
            total_amount=Decimal("150.00"),
            grand_total=Decimal("150.00"),
        )

        call_command("companion_run_maintenance", max_age_hours=24)

        latest = get_latest_health_snapshot(workspace)
        self.assertGreater(latest.created_at, snapshot.created_at)
        actions = CompanionSuggestedAction.objects.filter(workspace=workspace, status=CompanionSuggestedAction.STATUS_OPEN)
        self.assertTrue(actions.exists())


class CompanionActionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="actions", email="a@example.com", password="pass")
        self.workspace = Business.objects.create(name="ActionsCo", currency="USD", owner_user=self.user)
        self.bank_account = BankAccount.objects.create(
            business=self.workspace,
            name="Operating",
            bank_name="TestBank",
            account_number_mask="1234",
            usage_role=BankAccount.UsageRole.OPERATING,
        )
        self.bank_account_account = Account.objects.create(
            business=self.workspace,
            name="Cash",
            code="1000",
            type=Account.AccountType.ASSET,
        )
        self.bank_account.account = self.bank_account_account
        self.bank_account.save()
        self.revenue_account = Account.objects.create(
            business=self.workspace,
            name="Revenue",
            code="4000",
            type=Account.AccountType.INCOME,
        )
        self.client.force_login(self.user)

    def _create_journal_entry(self, amount: Decimal, date: date):
        je = JournalEntry.objects.create(business=self.workspace, date=date, description="Test entry")
        JournalLine.objects.create(journal_entry=je, account=self.revenue_account, debit=Decimal("0.00"), credit=amount)
        JournalLine.objects.create(
            journal_entry=je, account=self.bank_account_account, debit=amount, credit=Decimal("0.00")
        )
        return je

    def test_generate_suggestion_creates_action(self):
        tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Customer payment",
            amount=Decimal("100.00"),
            normalized_hash="hash1",
        )
        je = self._create_journal_entry(Decimal("100.00"), tx.date)
        generate_bank_match_suggestions_for_workspace(self.workspace)
        action = CompanionSuggestedAction.objects.filter(workspace=self.workspace).first()
        self.assertIsNotNone(action)
        self.assertEqual(action.status, CompanionSuggestedAction.STATUS_OPEN)
        self.assertEqual(action.payload.get("bank_transaction_id"), tx.id)
        self.assertEqual(action.payload.get("journal_entry_id"), je.id)
        self.assertEqual(action.context, CompanionSuggestedAction.CONTEXT_BANK)

    def test_suggestion_dedup_and_cap(self):
        tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Payment",
            amount=Decimal("50.00"),
            normalized_hash="hash2",
        )
        self._create_journal_entry(Decimal("50.00"), tx.date)
        generate_bank_match_suggestions_for_workspace(self.workspace, max_open=1)
        generate_bank_match_suggestions_for_workspace(self.workspace, max_open=1)
        self.assertEqual(
            CompanionSuggestedAction.objects.filter(workspace=self.workspace, status=CompanionSuggestedAction.STATUS_OPEN).count(),
            1,
        )

    @mock.patch("core.services.bank_reconciliation.BankReconciliationService.confirm_match")
    def test_apply_endpoint_marks_applied(self, mock_confirm):
        tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Apply me",
            amount=Decimal("75.00"),
            normalized_hash="hash3",
        )
        je = self._create_journal_entry(Decimal("75.00"), tx.date)
        action = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={"bank_transaction_id": tx.id, "journal_entry_id": je.id, "amount": "75.00", "date": str(tx.date)},
            confidence=Decimal("0.9"),
            summary="Test apply",
        )
        res = self.client.post(reverse("companion:apply_action", args=[action.id]))
        self.assertEqual(res.status_code, 200)
        action.refresh_from_db()
        self.assertEqual(action.status, CompanionSuggestedAction.STATUS_APPLIED)
        self.assertIsNotNone(action.resolved_at)
        mock_confirm.assert_called_once()

    def test_dismiss_endpoint_marks_dismissed(self):
        action = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={"bank_transaction_id": 1, "journal_entry_id": 2, "amount": "10.00", "date": "2024-08-01"},
            confidence=Decimal("0.8"),
            summary="Test dismiss",
        )
        res = self.client.post(reverse("companion:dismiss_action", args=[action.id]))
        self.assertEqual(res.status_code, 200)
        action.refresh_from_db()
        self.assertEqual(action.status, CompanionSuggestedAction.STATUS_DISMISSED)
        self.assertIsNotNone(action.resolved_at)

    def test_apply_endpoint_handles_soft_actions(self):
        action = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
            status=CompanionSuggestedAction.STATUS_OPEN,
            context=CompanionSuggestedAction.CONTEXT_INVOICES,
            payload={"invoice_id": 123, "invoice_number": "INV-100"},
            confidence=Decimal("0.0"),
            summary="Follow up",
        )
        res = self.client.post(reverse("companion:apply_action", args=[action.id]))
        self.assertEqual(res.status_code, 200)
        action.refresh_from_db()
        self.assertEqual(action.status, CompanionSuggestedAction.STATUS_APPLIED)

    def test_actions_in_overview(self):
        action = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_BANK_MATCH_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={"bank_transaction_id": 1, "journal_entry_id": 2, "amount": "10.00", "date": "2024-08-01"},
            confidence=Decimal("0.8"),
            summary="Test action",
        )
        res = self.client.get(reverse("companion:overview"))
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        ids = [a["id"] for a in payload.get("actions", [])]
        self.assertIn(action.id, ids)
        for item in payload.get("actions", []):
            self.assertIn("context", item)


class CompanionDeterministicSuggestionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="deterministic", email="d@example.com", password="pass")
        self.workspace = Business.objects.create(name="DeterministicCo", currency="USD", owner_user=self.user)
        self.customer = Customer.objects.create(business=self.workspace, name="Acme Customer")
        self.supplier = Supplier.objects.create(business=self.workspace, name="Acme Supplies")
        self.client.force_login(self.user)

    def test_overdue_invoice_actions_created_with_context_and_payload(self):
        today = timezone.now().date()
        overdue_invoice = Invoice.objects.create(
            business=self.workspace,
            customer=self.customer,
            invoice_number="INV-100",
            status=Invoice.Status.SENT,
            issue_date=today - timedelta(days=30),
            due_date=today - timedelta(days=10),
            total_amount=Decimal("120.00"),
            grand_total=Decimal("120.00"),
        )
        Invoice.objects.create(
            business=self.workspace,
            customer=self.customer,
            invoice_number="INV-101",
            status=Invoice.Status.SENT,
            issue_date=today,
            due_date=today + timedelta(days=5),
            total_amount=Decimal("80.00"),
            grand_total=Decimal("80.00"),
        )

        generate_overdue_invoice_suggestions_for_workspace(self.workspace, grace_days=7)
        actions = CompanionSuggestedAction.objects.filter(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
        )
        self.assertEqual(actions.count(), 1)
        action = actions.first()
        self.assertEqual(action.context, CompanionSuggestedAction.CONTEXT_INVOICES)
        self.assertEqual(action.payload.get("invoice_id"), overdue_invoice.id)
        self.assertGreaterEqual(action.payload.get("days_overdue"), 10)

        # Deduplicate on repeat runs
        generate_overdue_invoice_suggestions_for_workspace(self.workspace, grace_days=7)
        self.assertEqual(
            CompanionSuggestedAction.objects.filter(
                workspace=self.workspace,
                action_type=CompanionSuggestedAction.ACTION_INVOICE_REMINDER,
            ).count(),
            1,
        )

    def test_uncategorized_expense_batch_created_and_capped(self):
        suggested_category = Category.objects.create(
            business=self.workspace,
            name="Office",
            type=Category.CategoryType.EXPENSE,
        )
        WorkspaceMemory.objects.create(
            workspace=self.workspace,
            key="vendor:acme supplies",
            value={"category_id": suggested_category.id},
        )
        uncategorized = Expense.objects.create(
            business=self.workspace,
            supplier=self.supplier,
            category=None,
            description="Paper",
            amount=Decimal("25.00"),
        )
        Expense.objects.create(
            business=self.workspace,
            supplier=self.supplier,
            category=suggested_category,
            description="Categorized",
            amount=Decimal("10.00"),
        )

        generate_uncategorized_expense_suggestions_for_workspace(self.workspace, max_actions=3)
        actions = CompanionSuggestedAction.objects.filter(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
        )
        self.assertEqual(actions.count(), 1)
        action = actions.first()
        self.assertEqual(action.context, CompanionSuggestedAction.CONTEXT_EXPENSES)
        self.assertIn(uncategorized.id, action.payload.get("expense_ids"))
        expense_payloads = action.payload.get("expenses") or []
        self.assertTrue(any(item.get("suggested_category_id") == suggested_category.id for item in expense_payloads))

        generate_uncategorized_expense_suggestions_for_workspace(self.workspace, max_actions=3)
        self.assertEqual(
            CompanionSuggestedAction.objects.filter(
                workspace=self.workspace,
                action_type=CompanionSuggestedAction.ACTION_CATEGORIZE_EXPENSES_BATCH,
            ).count(),
            1,
        )
