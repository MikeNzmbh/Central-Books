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
from companion.models import (
    AICommandRecord,
    AICircuitBreakerEvent,
    CompanionInsight,
    CompanionSuggestedAction,
    ProvisionalLedgerEvent,
    WorkspaceAISettings,
    WorkspaceCompanionProfile,
    WorkspaceMemory,
)
from companion.services import (
    create_health_snapshot,
    generate_bank_match_suggestions_for_workspace,
    generate_overdue_invoice_suggestions_for_workspace,
    generate_uncategorized_expense_suggestions_for_workspace,
    generate_uncategorized_transactions_cleanup_actions,
    generate_reconciliation_period_close_actions,
    generate_inactive_customers_followup,
    generate_expense_spike_category_review,
    gather_workspace_metrics,
    get_latest_health_snapshot,
)
from core.models import (
    Account,
    BankAccount,
    BankTransaction,
    Business,
    Category,
    Customer,
    Expense,
    Invoice,
    JournalEntry,
    JournalLine,
    Supplier,
    WorkspaceMembership,
)


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

    def test_overview_context_tax_fx_returns_context_insights(self):
        # Fill the global top-5 insights with non-tax items.
        for idx in range(6):
            CompanionInsight.objects.create(
                workspace=self.workspace,
                domain="other",
                title=f"Other insight {idx}",
                body="Body",
                severity="critical",
                context=CompanionInsight.CONTEXT_BANK,
            )

        tax_insight = CompanionInsight.objects.create(
            workspace=self.workspace,
            domain="tax_filing",
            title="Tax filing due soon — 2025-04",
            body="Due soon.",
            severity="warning",
            context=CompanionInsight.CONTEXT_TAX_FX,
        )

        response = self.client.get(reverse("companion:overview") + "?context=tax_fx")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("context"), CompanionInsight.CONTEXT_TAX_FX)
        titles = [i["title"] for i in payload.get("insights") or []]
        self.assertIn(tax_insight.title, titles)
        self.assertTrue(all(i.get("context") == CompanionInsight.CONTEXT_TAX_FX for i in payload.get("insights") or []))

    @override_settings(COMPANION_LLM_ENABLED=False)
    def test_llm_disabled_returns_null_summary(self):
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("llm_narrative", payload)
        self.assertIsNone(payload["llm_narrative"]["summary"])

    @override_settings(
        COMPANION_LLM_ENABLED=True,
        COMPANION_LLM_API_BASE="",
        COMPANION_LLM_API_KEY="",
    )
    def test_llm_enabled_but_missing_config_returns_calm_payload(self):
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("llm_narrative", payload)
        self.assertIsNone(payload["llm_narrative"].get("summary"))

    @override_settings(
        COMPANION_LLM_ENABLED=True,
        COMPANION_LLM_API_BASE="https://api.example.com",
        COMPANION_LLM_API_KEY="test-key",
        COMPANION_LLM_MODEL="stub-model",
    )
    @mock.patch("companion.llm.call_companion_llm", side_effect=Exception("boom"))
    def test_llm_exception_is_swallowed(self, _mock_llm):
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("llm_narrative", payload)
        self.assertIsNone(payload["llm_narrative"].get("summary"))

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
            {
                "summary": "Books look stable. Reconcile soon.",
                "context_summary": "Banking looks steady.",
                "insight_explanations": {str(insight.id): "Clear 3 items."},
            }
        )
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["llm_narrative"]["summary"], "Books look stable. Reconcile soon.")
        self.assertEqual(payload["llm_narrative"]["insight_explanations"].get(str(insight.id)), "Clear 3 items.")
        self.assertEqual(payload["llm_narrative"]["context_summary"], "Banking looks steady.")

    @override_settings(
        COMPANION_LLM_ENABLED=True,
        COMPANION_LLM_API_BASE="https://api.example.com",
        COMPANION_LLM_API_KEY="test-key",
        COMPANION_LLM_OFFLINE=True,
    )
    @mock.patch("companion.llm.requests.post")
    def test_llm_offline_mode_skips_network(self, mock_post):
        from companion.llm import call_deepseek_reasoning

        res = call_deepseek_reasoning("hello", context_tag="test_offline")
        self.assertIsNone(res)
        mock_post.assert_not_called()

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
            severity=CompanionSuggestedAction.SEVERITY_MEDIUM,
            short_title="Bank match",
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
            severity=CompanionSuggestedAction.SEVERITY_LOW,
            short_title="Bank match",
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

    def test_mark_context_seen_tax_fx(self):
        res = self.client.post(
            reverse("companion:context_seen"),
            data=json.dumps({"context": "tax_fx"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        profile = WorkspaceCompanionProfile.objects.get(workspace=self.workspace)
        self.assertIsNotNone(profile.last_seen_tax_fx_at)

    def test_context_seen_invalid_context_rejected(self):
        res = self.client.post(
            reverse("companion:context_seen"),
            data=json.dumps({"context": "invalid"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_context_reasons_all_clear_invoices(self):
        response = self.client.get(reverse("companion:overview") + "?context=invoices")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("context_all_clear"))
        self.assertIn("context_reasons", payload)
        self.assertTrue(payload.get("context_reasons"))

    def test_context_reasons_flagged_for_overdue(self):
        today = timezone.now().date()
        customer = Customer.objects.create(business=self.workspace, name="Ctx Customer")
        Invoice.objects.create(
            business=self.workspace,
            customer=customer,
            invoice_number="CTX-1",
            status=Invoice.Status.SENT,
            issue_date=today - timedelta(days=40),
            due_date=today - timedelta(days=10),
            total_amount=Decimal("50.00"),
            grand_total=Decimal("50.00"),
        )
        response = self.client.get(reverse("companion:overview") + "?context=invoices")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload.get("context_all_clear"))
        reasons = payload.get("context_reasons") or []
        self.assertTrue(any("overdue" in reason.lower() for reason in reasons))

    def test_actions_sorted_by_severity(self):
        low = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_INACTIVE_CUSTOMERS_FOLLOWUP,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={},
            confidence=Decimal("0.1"),
            summary="Low",
            severity=CompanionSuggestedAction.SEVERITY_LOW,
            short_title="Low",
        )
        high = CompanionSuggestedAction.objects.create(
            workspace=self.workspace,
            action_type=CompanionSuggestedAction.ACTION_SUSPENSE_BALANCE_REVIEW,
            status=CompanionSuggestedAction.STATUS_OPEN,
            payload={},
            confidence=Decimal("0.2"),
            summary="High",
            severity=CompanionSuggestedAction.SEVERITY_HIGH,
            short_title="High",
        )
        low.created_at = timezone.now() - timedelta(days=1)
        low.save(update_fields=["created_at"])
        response = self.client.get(reverse("companion:overview"))
        self.assertEqual(response.status_code, 200)
        actions = response.json().get("actions") or []
        self.assertGreaterEqual(len(actions), 2)
        self.assertEqual(actions[0]["summary"], "High")
        self.assertEqual(actions[0]["severity"], CompanionSuggestedAction.SEVERITY_HIGH)

    def test_overdue_invoice_severity_set(self):
        today = timezone.now().date()
        customer = Customer.objects.create(business=self.workspace, name="Client")
        Invoice.objects.create(
            business=self.workspace,
            customer=customer,
            invoice_number="INV-1",
            status=Invoice.Status.SENT,
            issue_date=today - timedelta(days=40),
            due_date=today - timedelta(days=20),
            total_amount=Decimal("600.00"),
            grand_total=Decimal("600.00"),
        )
        actions = generate_overdue_invoice_suggestions_for_workspace(self.workspace)
        self.assertTrue(actions)
        action = actions[0]
        self.assertEqual(action.severity, CompanionSuggestedAction.SEVERITY_MEDIUM)
        self.assertEqual(action.short_title, "Overdue invoices")


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
            action_type=CompanionSuggestedAction.ACTION_OVERDUE_INVOICE_REMINDERS,
        )
        self.assertEqual(actions.count(), 1)
        action = actions.first()
        self.assertEqual(action.context, CompanionSuggestedAction.CONTEXT_INVOICES)
        self.assertIn(overdue_invoice.id, action.payload.get("invoice_ids"))
        self.assertGreaterEqual(action.payload.get("invoices")[0].get("days_overdue"), 10)

        # Deduplicate on repeat runs
        generate_overdue_invoice_suggestions_for_workspace(self.workspace, grace_days=7)
        self.assertEqual(
            CompanionSuggestedAction.objects.filter(
                workspace=self.workspace,
                action_type=CompanionSuggestedAction.ACTION_OVERDUE_INVOICE_REMINDERS,
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
            action_type=CompanionSuggestedAction.ACTION_UNCATEGORIZED_EXPENSE_REVIEW,
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
                action_type=CompanionSuggestedAction.ACTION_UNCATEGORIZED_EXPENSE_REVIEW,
            ).count(),
            1,
        )

    def test_uncategorized_transactions_cleanup_action_created(self):
        suspense_account = Account.objects.create(
            business=self.workspace,
            name="Uncategorized Transactions",
            code="9999",
            type=Account.AccountType.ASSET,
        )
        journal = JournalEntry.objects.create(business=self.workspace, date=timezone.now().date(), description="Test")
        JournalLine.objects.create(journal_entry=journal, account=suspense_account, debit=Decimal("100.00"), credit=Decimal("0.00"))
        metrics = gather_workspace_metrics(self.workspace)
        actions = generate_uncategorized_transactions_cleanup_actions(self.workspace, metrics=metrics)
        self.assertTrue(actions)
        self.assertEqual(actions[0].action_type, CompanionSuggestedAction.ACTION_UNCATEGORIZED_TRANSACTIONS_CLEANUP)

    def test_reconciliation_period_close_action_created(self):
        metrics = {"has_unfinished_reconciliation_period": True, "unreconciled_count": 2}
        actions = generate_reconciliation_period_close_actions(self.workspace, metrics=metrics)
        self.assertTrue(actions)
        self.assertEqual(actions[0].action_type, CompanionSuggestedAction.ACTION_RECONCILIATION_PERIOD_TO_CLOSE)

    def test_inactive_customers_followup_action(self):
        past_date = timezone.now().date() - timedelta(days=120)
        Invoice.objects.create(
            business=self.workspace,
            customer=self.customer,
            invoice_number="INV-500",
            status=Invoice.Status.SENT,
            issue_date=past_date,
            due_date=past_date + timedelta(days=10),
            total_amount=Decimal("50.00"),
            grand_total=Decimal("50.00"),
        )
        actions = generate_inactive_customers_followup(self.workspace)
        self.assertTrue(actions)
        self.assertEqual(actions[0].action_type, CompanionSuggestedAction.ACTION_INACTIVE_CUSTOMERS_FOLLOWUP)

    def test_expense_spike_category_action(self):
        category = Category.objects.create(business=self.workspace, name="Travel", type=Category.CategoryType.EXPENSE)
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        prev_month_end = last_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        Expense.objects.create(
            business=self.workspace,
            category=category,
            supplier=self.supplier,
            date=prev_month_start + timedelta(days=1),
            amount=Decimal("100.00"),
        )
        Expense.objects.create(
            business=self.workspace,
            category=category,
            supplier=self.supplier,
            date=last_month_start + timedelta(days=1),
            amount=Decimal("300.00"),
        )
        actions = generate_expense_spike_category_review(self.workspace, threshold_pct=50)
        self.assertTrue(actions)
        self.assertEqual(actions[0].action_type, CompanionSuggestedAction.ACTION_SPIKE_EXPENSE_CATEGORY_REVIEW)


class CompanionV2ApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="v2user", email="v2@example.com", password="pass")
        self.workspace = Business.objects.create(
            name="V2 Co",
            currency="USD",
            owner_user=self.user,
            ai_companion_enabled=False,
        )
        self.client.force_login(self.user)

        self.bank_asset = Account.objects.create(
            business=self.workspace,
            code="1000",
            name="Bank",
            type=Account.AccountType.ASSET,
        )
        self.expense_account = Account.objects.create(
            business=self.workspace,
            code="6000",
            name="Office supplies",
            type=Account.AccountType.EXPENSE,
        )
        self.bank_account = BankAccount.objects.create(business=self.workspace, name="Checking", account=self.bank_asset)
        self.bank_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Staples",
            amount=Decimal("-10.00"),
        )

    def _enable_ai(self, *, mode: str, kill_switch: bool = False, value_breaker_threshold: str | None = None):
        self.workspace.ai_companion_enabled = True
        self.workspace.save(update_fields=["ai_companion_enabled"])
        settings_row, _ = WorkspaceAISettings.objects.get_or_create(
            workspace=self.workspace, defaults={"ai_enabled": True, "ai_mode": mode, "kill_switch": False}
        )
        dirty = False
        if not settings_row.ai_enabled:
            settings_row.ai_enabled = True
            dirty = True
        if settings_row.ai_mode != mode:
            settings_row.ai_mode = mode
            dirty = True
        if settings_row.kill_switch != kill_switch:
            settings_row.kill_switch = kill_switch
            dirty = True
        if value_breaker_threshold is not None and str(settings_row.value_breaker_threshold) != str(value_breaker_threshold):
            settings_row.value_breaker_threshold = Decimal(str(value_breaker_threshold))
            dirty = True
        if dirty:
            settings_row.save()
        return settings_row

    def test_v2_propose_blocked_when_ai_disabled(self):
        res = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)

    def test_v2_shadow_only_allows_propose_but_blocks_apply(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SHADOW_ONLY)

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_shadow_only",
                    "rationale": "Test proposal",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 0, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        shadow_event_id = propose.json()["id"]

        apply_res = self.client.post(
            reverse("companion:v2_proposal_apply", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id},
            content_type="application/json",
        )
        self.assertEqual(apply_res.status_code, 403)

    def test_v2_suggest_only_apply_creates_canonical_entry(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_apply_ok",
                    "rationale": "Test proposal apply path",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        shadow_event_id = propose.json()["id"]

        apply_res = self.client.post(
            reverse("companion:v2_proposal_apply", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id},
            content_type="application/json",
        )
        self.assertEqual(apply_res.status_code, 200)
        payload = apply_res.json()
        self.assertIn("result", payload)
        self.assertIsNotNone(payload["result"].get("journal_entry_id"))

        shadow = ProvisionalLedgerEvent.objects.get(id=shadow_event_id)
        self.assertEqual(shadow.status, ProvisionalLedgerEvent.Status.APPLIED)
        self.assertIsNotNone(shadow.command_id)
        self.assertEqual(shadow.logic_trace_id, "trace_test_apply_ok")
        self.assertEqual(shadow.rationale, "Test proposal apply path")

        from django.contrib.contenttypes.models import ContentType

        from companion.models import CanonicalLedgerProvenance
        from core.models import JournalEntry

        je_ct = ContentType.objects.get_for_model(JournalEntry)
        self.assertTrue(
            CanonicalLedgerProvenance.objects.filter(
                workspace=self.workspace,
                shadow_event_id=shadow_event_id,
                content_type=je_ct,
                object_id=int(payload["result"]["journal_entry_id"]),
                applied_by=self.user,
            ).exists()
        )

    def test_v2_proposals_list_returns_only_proposed(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)

        other_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Office chair",
            amount=Decimal("-25.00"),
        )

        propose1 = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_list_1",
                    "rationale": "Test list 1",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose1.status_code, 201)
        shadow_event_1 = propose1.json()["id"]

        propose2 = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": other_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "25.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_list_2",
                    "rationale": "Test list 2",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose2.status_code, 201)
        shadow_event_2 = propose2.json()["id"]

        reject_res = self.client.post(
            reverse("companion:v2_proposal_reject", kwargs={"pk": shadow_event_1}),
            data={"workspace_id": self.workspace.id, "reason": "Incorrect"},
            content_type="application/json",
        )
        self.assertEqual(reject_res.status_code, 200)

        list_res = self.client.get(reverse("companion:v2_proposals"), data={"workspace_id": self.workspace.id})
        self.assertEqual(list_res.status_code, 200)
        ids = {row["id"] for row in list_res.json()}
        self.assertNotIn(shadow_event_1, ids)
        self.assertIn(shadow_event_2, ids)

    def test_v2_reject_marks_event_rejected(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_reject",
                    "rationale": "Test reject",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        shadow_event_id = propose.json()["id"]

        reject_res = self.client.post(
            reverse("companion:v2_proposal_reject", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id, "reason": "Incorrect vendor"},
            content_type="application/json",
        )
        self.assertEqual(reject_res.status_code, 200)
        shadow = ProvisionalLedgerEvent.objects.get(id=shadow_event_id)
        self.assertEqual(shadow.status, ProvisionalLedgerEvent.Status.REJECTED)
        self.assertTrue(
            AICommandRecord.objects.filter(
                workspace=self.workspace,
                command_type="RejectShadowEvent",
                shadow_event_id=shadow_event_id,
                actor=shadow.actor,
                created_by=self.user,
            ).exists()
        )

    def test_v2_apply_blocks_when_bank_transaction_changed_since_proposal(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_drift",
                    "rationale": "Proposal used for drift test",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        shadow_event_id = propose.json()["id"]

        # Mutate the underlying bank transaction after proposal creation.
        BankTransaction.objects.filter(id=self.bank_tx.id).update(allocated_amount=Decimal("5.0000"))

        apply_res = self.client.post(
            reverse("companion:v2_proposal_apply", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id},
            content_type="application/json",
        )
        self.assertEqual(apply_res.status_code, 400)
        self.assertIn("StateConflict", (apply_res.json() or {}).get("detail", ""))

    def test_v2_trust_breaker_downgrades_autopilot_on_rejection_rate(self):
        settings_row = self._enable_ai(mode=WorkspaceAISettings.AIMode.AUTOPILOT_LIMITED)
        settings_row.trust_downgrade_rejection_rate = Decimal("0.10")
        settings_row.save(update_fields=["trust_downgrade_rejection_rate", "updated_at"])

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_trust_breaker",
                    "rationale": "Proposal used for trust breaker test",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        shadow_event_id = propose.json()["id"]

        reject_res = self.client.post(
            reverse("companion:v2_proposal_reject", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id, "reason": "Reject to trigger trust breaker"},
            content_type="application/json",
        )
        self.assertEqual(reject_res.status_code, 200)

        settings_row.refresh_from_db()
        self.assertEqual(settings_row.ai_mode, WorkspaceAISettings.AIMode.SUGGEST_ONLY)
        self.assertTrue(
            AICircuitBreakerEvent.objects.filter(workspace=self.workspace, breaker=AICircuitBreakerEvent.Breaker.TRUST).exists()
        )

    def test_v2_kill_switch_blocks_propose_and_apply(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)

        # Create one proposal first.
        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_kill_switch_seed",
                    "rationale": "Seed proposal",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        shadow_event_id = propose.json()["id"]

        # Turn on kill switch.
        settings_row = WorkspaceAISettings.objects.get(workspace=self.workspace)
        settings_row.kill_switch = True
        settings_row.save(update_fields=["kill_switch", "updated_at"])

        blocked_propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
            },
            content_type="application/json",
        )
        self.assertEqual(blocked_propose.status_code, 403)

        blocked_apply = self.client.post(
            reverse("companion:v2_proposal_apply", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id},
            content_type="application/json",
        )
        self.assertEqual(blocked_apply.status_code, 403)

        shadow = ProvisionalLedgerEvent.objects.get(id=shadow_event_id)
        self.assertEqual(shadow.status, ProvisionalLedgerEvent.Status.PROPOSED)

    def test_v2_value_breaker_forces_tier_and_risk_reason(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY, value_breaker_threshold="50.00")

        big_tx = BankTransaction.objects.create(
            bank_account=self.bank_account,
            date=timezone.now().date(),
            description="Big vendor",
            amount=Decimal("-100.00"),
        )

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": big_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "100.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_value_breaker",
                    "rationale": "Large amount should force review",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        event_id = propose.json()["id"]
        shadow = ProvisionalLedgerEvent.objects.get(id=event_id)
        human = shadow.human_in_the_loop or {}
        self.assertEqual(int(human.get("tier") or 0), 2)
        self.assertIn("value_breaker", list(human.get("risk_reasons") or []))

    def test_v2_bot_can_propose_but_cannot_apply(self):
        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)

        bot = User.objects.create_user(username="bot", email="bot@example.com", password="pass")
        WorkspaceMembership.objects.create(
            user=bot,
            business=self.workspace,
            role=WorkspaceMembership.RoleChoices.JUNIOR_ACCOUNTANT_BOT,
        )
        self.client.force_login(bot)

        propose = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
                "metadata": {
                    "actor": "system_companion_v2.1",
                    "confidence_score": 0.9,
                    "logic_trace_id": "trace_test_bot_propose",
                    "rationale": "Bot proposal",
                    "business_profile_constraint": "risk_appetite=standard",
                    "human_in_the_loop": {"tier": 1, "status": "proposed"},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(propose.status_code, 201)
        shadow_event_id = propose.json()["id"]

        apply_res = self.client.post(
            reverse("companion:v2_proposal_apply", kwargs={"pk": shadow_event_id}),
            data={"workspace_id": self.workspace.id},
            content_type="application/json",
        )
        self.assertEqual(apply_res.status_code, 403)

    def test_v2_permission_denies_view_only_user(self):
        other = User.objects.create_user(username="viewer", email="viewer@example.com", password="pass")
        WorkspaceMembership.objects.create(user=other, business=self.workspace, role=WorkspaceMembership.RoleChoices.VIEW_ONLY)
        self.client.force_login(other)

        self._enable_ai(mode=WorkspaceAISettings.AIMode.SUGGEST_ONLY)
        res = self.client.post(
            reverse("companion:v2_propose_categorization"),
            data={
                "bank_transaction_id": self.bank_tx.id,
                "proposed_splits": [{"account_id": self.expense_account.id, "amount": "10.00"}],
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)
