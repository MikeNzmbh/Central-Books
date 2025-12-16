from django.contrib.auth.models import User
from django.test import TestCase

from core.models import BankAccount, Business, RoleDefinition, UserPermissionOverride, WorkspaceMembership
from core.permissions_engine import evaluate_permission
from core.rbac_seeding import ensure_builtin_role_definitions
from core.sod import validate_role_permissions


class PermissionsEngineTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.ap = User.objects.create_user(username="ap", password="pass")
        self.cash = User.objects.create_user(username="cash", password="pass")

        self.business = Business.objects.create(name="Biz", currency="USD", owner_user=self.owner)
        ensure_builtin_role_definitions(self.business)

        self.ap_role = RoleDefinition.objects.get(business=self.business, key="AP_SPECIALIST")
        self.cash_role = RoleDefinition.objects.get(business=self.business, key="CASH_MANAGER")

        self.ap_membership = WorkspaceMembership.objects.create(
            user=self.ap,
            business=self.business,
            role="AP_SPECIALIST",
            role_definition=self.ap_role,
        )
        self.cash_membership = WorkspaceMembership.objects.create(
            user=self.cash,
            business=self.business,
            role="CASH_MANAGER",
            role_definition=self.cash_role,
        )

    def test_cash_manager_can_reconcile_but_ap_cannot(self):
        ap_decision = evaluate_permission(self.ap, self.business, "bank.reconcile", required_level="view")
        cash_decision = evaluate_permission(self.cash, self.business, "bank.reconcile", required_level="view")
        self.assertFalse(ap_decision.allowed)
        self.assertTrue(cash_decision.allowed)

    def test_bank_balance_is_masked_without_permission(self):
        # AP specialist should not be able to view balances.
        decision = evaluate_permission(self.ap, self.business, "bank.accounts.view_balance", required_level="view")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.mask_sensitive)

        decision_cash = evaluate_permission(self.cash, self.business, "bank.accounts.view_balance", required_level="view")
        self.assertTrue(decision_cash.allowed)
        self.assertFalse(decision_cash.mask_sensitive)

    def test_override_grants_scoped_balance_visibility(self):
        bank = BankAccount.objects.create(business=self.business, name="Checking", bank_name="Bank", account_number_mask="1234")

        decision = evaluate_permission(
            self.ap,
            self.business,
            "bank.accounts.view_balance",
            required_level="view",
            context={"bank_account_id": bank.id},
        )
        self.assertFalse(decision.allowed)

        UserPermissionOverride.objects.create(
            membership=self.ap_membership,
            action="bank.accounts.view_balance",
            effect=UserPermissionOverride.Effect.ALLOW,
            level_override="view",
            scope_override={"type": "selected_accounts", "account_ids": [bank.id]},
        )

        decision2 = evaluate_permission(
            self.ap,
            self.business,
            "bank.accounts.view_balance",
            required_level="view",
            context={"bank_account_id": bank.id},
        )
        self.assertTrue(decision2.allowed)

    def test_api_banking_overview_masks_balance_fields(self):
        bank = BankAccount.objects.create(business=self.business, name="Checking", bank_name="Bank", account_number_mask="1234")

        self.client.force_login(self.ap)
        res = self.client.get("/api/banking/overview/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        account = data["accounts"][0]
        self.assertIsNone(account["ledger_balance"])
        self.assertTrue(account["balance_masked"])

        res2 = self.client.get(f"/api/banking/feed/transactions/?account_id={bank.id}&status=ALL")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertIsNone(data2["account"]["ledger_balance"])
        self.assertIsNone(data2["balance"])
        self.assertTrue(data2["account"]["balance_masked"])

    def test_sod_validator_emits_expected_warning(self):
        permissions = {
            "vendor.edit_payment_details": {"level": "edit", "scope": {"type": "all"}},
            "expenses.pay": {"level": "approve", "scope": {"type": "all"}},
        }
        warnings = validate_role_permissions(permissions)
        warning_ids = {w["id"] for w in warnings}
        self.assertIn("vendor_fraud", warning_ids)
