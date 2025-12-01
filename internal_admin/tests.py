from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import BankAccount, BankTransaction, Business
from allauth.socialaccount.models import SocialAccount
from internal_admin.models import (
    AdminAuditLog,
    AdminRole,
    FeatureFlag,
    ImpersonationToken,
    InternalAdminProfile,
    OverviewMetricsSnapshot,
    SupportTicket,
    SupportTicketNote,
)
from internal_admin.services import compute_overview_metrics


User = get_user_model()


def make_admin_user(email: str, role: str, **extra) -> User:
    user = User.objects.create_user(
        username=email,
        email=email,
        password="pass1234",
        **extra,
    )
    InternalAdminProfile.objects.create(user=user, role=role)
    return user


class InternalAdminAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.web_client = Client()
        self.support_user = make_admin_user("support@example.com", AdminRole.SUPPORT)
        self.ops_user = make_admin_user("ops@example.com", AdminRole.OPS)
        self.engineering_user = make_admin_user("eng@example.com", AdminRole.ENGINEERING)
        self.superadmin_user = make_admin_user("super@example.com", AdminRole.SUPERADMIN)
        self.normal_user = User.objects.create_user(username="regular", email="regular@example.com", password="pass1234")

        self.workspace_owner = User.objects.create_user(username="owner", email="owner@example.com", password="pass1234")
        self.business = Business.objects.create(
            name="CERN Books Labs Inc.",
            currency="USD",
            owner_user=self.workspace_owner,
            plan="Internal / staging",
        )
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name="RBC Operating",
            bank_name="RBC",
            account_number_mask="1234",
        )
        BankTransaction.objects.create(
            bank_account=self.bank_account,
            date="2024-01-01",
            description="Deposit",
            amount=100,
        )
        self.social_user = User.objects.create_user(
            username="googleuser",
            email="googleuser@example.com",
            password="pass1234",
        )
        SocialAccount.objects.create(user=self.social_user, provider="google", uid="123")

    def test_permissions_matrix_for_users(self):
        # Non-admin denied
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get("/api/internal-admin/users/")
        self.assertEqual(resp.status_code, 403)

        # Support can list
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/users/")
        self.assertEqual(resp.status_code, 200)

        # Support cannot patch
        target = User.objects.create_user(username="target", email="target@example.com")
        resp = self.client.patch(f"/api/internal-admin/users/{target.pk}/", {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 403)

        # Ops can patch
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(f"/api/internal-admin/users/{target.pk}/", {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_user_update_logs_audit(self):
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(
            f"/api/internal-admin/users/{self.support_user.pk}/",
            {"is_active": False, "email": "new-email@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AdminAuditLog.objects.filter(action="USER_UPDATED").count(), 1)
        entry = AdminAuditLog.objects.filter(action="USER_UPDATED").first()
        self.assertIn("changes", entry.extra)
        changes = entry.extra.get("changes", {})
        self.assertIn("is_active", changes)
        self.assertIn("email", changes)
        self.assertIn("auth_providers", entry.extra)
        self.assertIn("from", changes["is_active"])
        self.assertIn("to", changes["is_active"])

    def test_workspace_update_and_delete_permissions(self):
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(
            f"/api/internal-admin/workspaces/{self.business.pk}/",
            {"plan": "Pro", "status": "active"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        # Ops cannot delete
        resp = self.client.patch(
            f"/api/internal-admin/workspaces/{self.business.pk}/",
            {"is_deleted": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

        # Superadmin can delete
        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.patch(
            f"/api/internal-admin/workspaces/{self.business.pk}/",
            {"is_deleted": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.business.refresh_from_db()
        self.assertTrue(self.business.is_deleted)

    def test_bank_accounts_read_only(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/bank-accounts/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_metrics_endpoint_requires_admin(self):
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get("/api/internal-admin/overview-metrics/")
        self.assertEqual(resp.status_code, 403)

        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/overview-metrics/")
        self.assertEqual(resp.status_code, 200)
        for key in [
            "active_users_30d",
            "unreconciled_transactions",
            "unbalanced_journal_entries",
            "workspaces_health",
        ]:
            self.assertIn(key, resp.data)
        self.assertEqual(OverviewMetricsSnapshot.objects.count(), 1)

    def test_metrics_endpoint_uses_cached_snapshot(self):
        self.client.force_authenticate(user=self.support_user)
        OverviewMetricsSnapshot.objects.create(payload={"cached": True})
        resp = self.client.get("/api/internal-admin/overview-metrics/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get("cached"), True)
        self.assertEqual(OverviewMetricsSnapshot.objects.count(), 1)

    def test_metrics_endpoint_refreshes_when_snapshot_is_stale(self):
        self.client.force_authenticate(user=self.support_user)
        stale = OverviewMetricsSnapshot.objects.create(payload={"cached": True})
        OverviewMetricsSnapshot.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        resp = self.client.get("/api/internal-admin/overview-metrics/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(OverviewMetricsSnapshot.objects.count(), 2)
        latest = OverviewMetricsSnapshot.objects.first()
        self.assertIsNotNone(latest)
        self.assertNotEqual(latest.payload, {"cached": True})

    def test_compute_overview_metrics_keys(self):
        metrics = compute_overview_metrics()
        for key in [
            "active_users_30d",
            "active_users_30d_change_pct",
            "unreconciled_transactions",
            "unreconciled_transactions_older_60d",
            "unbalanced_journal_entries",
            "workspaces_health",
        ]:
            self.assertIn(key, metrics)

    def test_management_command_refresh_internal_admin_metrics(self):
        OverviewMetricsSnapshot.objects.all().delete()
        call_command("refresh_internal_admin_metrics")
        self.assertEqual(OverviewMetricsSnapshot.objects.count(), 1)

    def test_impersonation_create_requires_admin(self):
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.post(
            "/api/internal-admin/impersonations/",
            {"user_id": self.support_user.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_impersonation_create_token_and_redirect(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.post(
            "/api/internal-admin/impersonations/",
            {"user_id": self.normal_user.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("redirect_url", resp.data)
        self.assertIn("/internal/impersonate/", resp.data["redirect_url"])
        self.assertEqual(ImpersonationToken.objects.count(), 1)
        self.assertEqual(AdminAuditLog.objects.filter(action="impersonation.created").count(), 1)

    def test_accept_impersonation_switches_user_and_marks_token(self):
        token = ImpersonationToken.objects.create(
            admin=self.support_user,
            target_user=self.normal_user,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.web_client.force_login(self.support_user)
        resp = self.web_client.get(reverse("internal-impersonate-accept", args=[token.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("dashboard"))
        token.refresh_from_db()
        self.assertFalse(token.is_active)
        self.assertIsNotNone(token.used_at)
        session = self.web_client.session
        self.assertTrue(session.get("is_impersonating"))
        self.assertEqual(session.get("impersonator_user_id"), self.support_user.id)
        self.assertEqual(session.get("impersonated_user_id"), self.normal_user.id)
        self.assertEqual(int(session.get("_auth_user_id")), self.normal_user.id)
        self.assertEqual(AdminAuditLog.objects.filter(action="impersonation.accepted").count(), 1)

    def test_accept_impersonation_rejects_wrong_admin(self):
        token = ImpersonationToken.objects.create(
            admin=self.support_user,
            target_user=self.normal_user,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.web_client.force_login(self.ops_user)
        resp = self.web_client.get(reverse("internal-impersonate-accept", args=[token.id]))
        self.assertEqual(resp.status_code, 403)
        token.refresh_from_db()
        self.assertTrue(token.is_active)
        self.assertIsNone(token.used_at)

    def test_accept_impersonation_rejects_expired_or_used(self):
        expired = ImpersonationToken.objects.create(
            admin=self.support_user,
            target_user=self.normal_user,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.web_client.force_login(self.support_user)
        resp = self.web_client.get(reverse("internal-impersonate-accept", args=[expired.id]))
        self.assertEqual(resp.status_code, 400)

        expired.refresh_from_db()
        self.assertTrue(expired.is_active)
        self.assertIsNone(expired.used_at)

        expired.used_at = timezone.now()
        expired.is_active = False
        expired.save(update_fields=["used_at", "is_active"])
        resp = self.web_client.get(reverse("internal-impersonate-accept", args=[expired.id]))
        self.assertEqual(resp.status_code, 400)

    def test_stop_impersonation_restores_admin_and_clears_flags(self):
        token = ImpersonationToken.objects.create(
            admin=self.support_user,
            target_user=self.normal_user,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.web_client.force_login(self.support_user)
        self.web_client.get(reverse("internal-impersonate-accept", args=[token.id]))
        resp = self.web_client.get(reverse("internal-impersonate-stop"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("admin_spa"))
        session = self.web_client.session
        self.assertFalse(session.get("is_impersonating"))
        self.assertEqual(int(session.get("_auth_user_id")), self.support_user.id)
        self.assertEqual(AdminAuditLog.objects.filter(action="impersonation.stopped").count(), 1)

    def test_stop_impersonation_logs_out_if_admin_missing(self):
        self.web_client.force_login(self.normal_user)
        session = self.web_client.session
        session["is_impersonating"] = True
        session["impersonator_user_id"] = 9999
        session.save()

        resp = self.web_client.get(reverse("internal-impersonate-stop"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].endswith(settings.LOGIN_URL))

    def test_users_api_includes_auth_metadata_and_filters(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/users/")
        self.assertEqual(resp.status_code, 200)
        payload_list = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        payload = payload_list[0]
        for key in [
            "auth_providers",
            "has_google_login",
            "workspace_count",
            "has_usable_password",
            "date_joined",
            "last_login",
            "social_account_count",
        ]:
            self.assertIn(key, payload)
        social_payload = next((u for u in payload_list if u["email"] == self.social_user.email), None)
        self.assertIsNotNone(social_payload)
        self.assertIn("google", social_payload["auth_providers"])
        self.assertTrue(social_payload["has_google_login"])
        self.assertGreaterEqual(social_payload.get("social_account_count", 0), 1)

        resp = self.client.get("/api/internal-admin/users/?has_google=true")
        self.assertEqual(resp.status_code, 200)
        emails = [
            u["email"]
            for u in (resp.data["results"] if isinstance(resp.data, dict) else resp.data)
        ]
        self.assertIn(self.social_user.email, emails)

        resp = self.client.get("/api/internal-admin/users/?has_google=false")
        data_list = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        emails = [u["email"] for u in data_list]
        self.assertNotIn(self.social_user.email, emails)

        self.normal_user.is_active = False
        self.normal_user.save()
        resp = self.client.get("/api/internal-admin/users/?is_active=false")
        data_list = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        emails = [u["email"] for u in data_list]
        self.assertIn(self.normal_user.email, emails)

    def test_support_tickets_permissions_and_updates(self):
        ticket = SupportTicket.objects.create(
            subject="Help me",
            user=self.normal_user,
            workspace=self.business,
            priority=SupportTicket.Priority.NORMAL,
            status=SupportTicket.Status.OPEN,
        )
        # Support can list
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/support-tickets/")
        self.assertEqual(resp.status_code, 200)
        # Support cannot patch
        resp = self.client.patch(
            f"/api/internal-admin/support-tickets/{ticket.pk}/",
            {"status": SupportTicket.Status.RESOLVED},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

        # Ops can patch
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(
            f"/api/internal-admin/support-tickets/{ticket.pk}/",
            {"status": SupportTicket.Status.IN_PROGRESS, "priority": SupportTicket.Priority.HIGH},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.IN_PROGRESS)
        self.assertEqual(ticket.priority, SupportTicket.Priority.HIGH)
        self.assertEqual(AdminAuditLog.objects.filter(action="support_ticket.updated").count(), 1)

    def test_support_ticket_add_note_logs_audit(self):
        ticket = SupportTicket.objects.create(subject="Billing", user=self.normal_user, workspace=self.business)
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.post(
            f"/api/internal-admin/support-tickets/{ticket.pk}/add_note/",
            {"body": "Investigating."},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(SupportTicketNote.objects.filter(ticket=ticket).count(), 1)
        self.assertEqual(AdminAuditLog.objects.filter(action="support_ticket.note_added").count(), 1)

    def test_feature_flags_permissions_and_updates(self):
        flag = FeatureFlag.objects.create(key="beta-test", label="Beta Test")
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/feature-flags/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.patch(
            f"/api/internal-admin/feature-flags/{flag.pk}/",
            {"is_enabled": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

        # Engineering can update
        self.client.force_authenticate(user=self.engineering_user)
        resp = self.client.patch(
            f"/api/internal-admin/feature-flags/{flag.pk}/",
            {"is_enabled": True, "rollout_percent": 50},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        flag.refresh_from_db()
        self.assertTrue(flag.is_enabled)
        self.assertEqual(flag.rollout_percent, 50)
        self.assertEqual(AdminAuditLog.objects.filter(action="feature_flag.updated").count(), 1)

    def test_audit_log_filters_level_category_and_action_contains(self):
        AdminAuditLog.objects.create(
            admin_user=self.support_user,
            action="support_ticket.updated",
            object_type="supportticket",
            object_id="1",
            level="WARNING",
            category="support",
        )
        AdminAuditLog.objects.create(
            admin_user=self.support_user,
            action="feature_flag.updated",
            object_type="featureflag",
            object_id="1",
            level="INFO",
            category="feature_flags",
        )
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/audit-log/?level=WARNING&category=support&action=support")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_internal_admin_login_flow(self):
        staff_user = User.objects.create_user(
            username="staff", email="staff@example.com", password="pass1234", is_staff=True
        )
        resp = self.web_client.post(
            "/internal-admin/login/",
            {"email": staff_user.email, "password": "pass1234"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].endswith("/internal-admin/"))

        # Non-staff rejected
        resp = self.web_client.post(
            "/internal-admin/login/",
            {"email": self.normal_user.email, "password": "pass1234"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid credentials", status_code=200)

    def test_django_admin_guard_blocks_non_superuser(self):
        staff_user = User.objects.create_user(
            username="staff2", email="staff2@example.com", password="pass1234", is_staff=True
        )
        self.web_client.force_login(staff_user)
        resp = self.web_client.get("/django-admin/")
        self.assertEqual(resp.status_code, 403)

        super_user = User.objects.create_superuser(
            username="root", email="root@example.com", password="pass1234"
        )
        self.web_client.force_login(super_user)
        resp = self.web_client.get("/django-admin/")
        self.assertNotEqual(resp.status_code, 403)
