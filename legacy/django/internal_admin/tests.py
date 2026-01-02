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
    AdminInvite,
    AdminRole,
    FeatureFlag,
    ImpersonationToken,
    InternalAdminProfile,
    OverviewMetricsSnapshot,
    StaffProfile,
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
            name="Clover Books Labs Inc.",
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
        resp = self.client.patch(
            f"/api/internal-admin/users/{target.pk}/",
            {"is_active": False, "reason": "Suspicious activity"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(resp.data.get("approval_required"))
        self.assertIn("approval_request_id", resp.data)

    def test_internal_admin_ip_allowlist_enforced(self):
        from django.test import override_settings

        with override_settings(INTERNAL_ADMIN_IP_ALLOWLIST=["203.0.113.0/24"]):
            self.client.force_authenticate(user=self.support_user)
            denied = self.client.get("/api/internal-admin/users/", REMOTE_ADDR="198.51.100.10")
            self.assertEqual(denied.status_code, 403)

            allowed = self.client.get("/api/internal-admin/users/", REMOTE_ADDR="203.0.113.10")
            self.assertEqual(allowed.status_code, 200)

            self.web_client.force_login(self.support_user)
            denied_spa = self.web_client.get("/internal-admin/", REMOTE_ADDR="198.51.100.10")
            self.assertEqual(denied_spa.status_code, 403)

    def test_internal_admin_requires_sso_when_enabled(self):
        from django.test import override_settings

        # support_user has an internal admin profile but no SocialAccount by default.
        with override_settings(INTERNAL_ADMIN_REQUIRE_SSO=True, INTERNAL_ADMIN_SSO_PROVIDERS=["google"]):
            self.client.force_authenticate(user=self.support_user)
            resp = self.client.get("/api/internal-admin/users/")
            self.assertEqual(resp.status_code, 403)

            SocialAccount.objects.create(user=self.support_user, provider="google", uid="support-123")
            resp = self.client.get("/api/internal-admin/users/")
            self.assertEqual(resp.status_code, 200)

    def test_user_update_logs_audit(self):
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(
            f"/api/internal-admin/users/{self.support_user.pk}/",
            {"is_active": False, "email": "new-email@example.com", "reason": "Policy violation"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)

        self.support_user.refresh_from_db()
        self.assertEqual(self.support_user.email, "new-email@example.com")
        self.assertTrue(self.support_user.is_active)  # Not executed until approval

        self.assertEqual(AdminAuditLog.objects.filter(action="USER_UPDATED").count(), 1)
        entry = AdminAuditLog.objects.filter(action="USER_UPDATED").first()
        self.assertIn("changes", entry.extra)
        changes = entry.extra.get("changes", {})
        self.assertIn("email", changes)
        self.assertIn("auth_providers", entry.extra)
        self.assertEqual(AdminAuditLog.objects.filter(action="approval.created").count(), 1)

    def test_user_deactivation_revokes_sessions(self):
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sessions.models import Session

        target = User.objects.create_user(username="sess", email="sess@example.com", password="pass1234")
        store = SessionStore()
        store["_auth_user_id"] = str(target.pk)
        store.save()
        self.assertTrue(Session.objects.filter(session_key=store.session_key).exists())

        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(
            f"/api/internal-admin/users/{target.pk}/",
            {"is_active": False, "reason": "Security incident"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)

        approval_id = resp.data["approval_request_id"]
        target.refresh_from_db()
        self.assertTrue(target.is_active)  # Not executed until approval
        self.assertTrue(Session.objects.filter(session_key=store.session_key).exists())

        ops2 = make_admin_user("ops2@example.com", AdminRole.OPS)
        self.client.force_authenticate(user=ops2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)

        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertFalse(Session.objects.filter(session_key=store.session_key).exists())

    def test_revoke_sessions_endpoint(self):
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sessions.models import Session

        target = User.objects.create_user(username="sess2", email="sess2@example.com", password="pass1234")
        store = SessionStore()
        store["_auth_user_id"] = str(target.pk)
        store.save()
        self.assertTrue(Session.objects.filter(session_key=store.session_key).exists())

        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.post(f"/api/internal-admin/users/{target.pk}/revoke-sessions/", format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("success"))
        self.assertGreaterEqual(resp.data.get("revoked_count", 0), 1)
        self.assertFalse(Session.objects.filter(session_key=store.session_key).exists())

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

        # Superadmin can request delete (executed on approval)
        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.patch(
            f"/api/internal-admin/workspaces/{self.business.pk}/",
            {"is_deleted": True, "reason": "Workspace requested to be closed"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        approval_id = resp.data["approval_request_id"]

        self.business.refresh_from_db()
        self.assertFalse(self.business.is_deleted)

        super2 = make_admin_user("super2@example.com", AdminRole.SUPERADMIN)
        self.client.force_authenticate(user=super2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)

        self.business.refresh_from_db()
        self.assertTrue(self.business.is_deleted)

    def test_workspace_editing_by_ops_with_audit_log(self):
        """Test OPS can edit workspace name, plan, status"""
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.patch(
            f"/api/internal-admin/workspaces/{self.business.pk}/",
            {"name": "Updated Name", "plan": "Enterprise", "status": "active"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Updated Name")
        self.assertEqual(self.business.plan, "Enterprise")
        self.assertEqual(self.business.status, "active")

    def test_bank_accounts_read_only(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/bank-accounts/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        self.assertGreaterEqual(len(resp.data["results"]), 1)

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
            {"user_id": self.support_user.pk, "reason": "Test"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_impersonation_create_token_and_redirect(self):
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.post(
            "/api/internal-admin/impersonations/",
            {"user_id": self.normal_user.pk, "reason": "Customer reported a UI issue"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("redirect_url", resp.data)
        self.assertIn("/internal/impersonate/", resp.data["redirect_url"])
        self.assertEqual(ImpersonationToken.objects.count(), 1)
        self.assertEqual(AdminAuditLog.objects.filter(action="impersonation.created").count(), 1)

    def test_ops_admin_cannot_impersonate_internal_admin(self):
        self.client.force_authenticate(user=self.ops_user)
        target_admin = User.objects.create_user(
            username="staffer",
            email="staffer@example.com",
            password="pass1234",
            is_staff=True,
        )
        resp = self.client.post(
            "/api/internal-admin/impersonations/",
            {"user_id": target_admin.pk, "reason": "Debug access"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Cannot impersonate other internal admins", resp.data.get("detail", ""))

    def test_superadmin_cannot_impersonate_superuser_and_may_impersonate_staff_admin(self):
        self.client.force_authenticate(user=self.superadmin_user)
        staff_admin = User.objects.create_user(
            username="staffadmin",
            email="staffadmin@example.com",
            password="pass1234",
            is_staff=True,
        )
        resp = self.client.post(
            "/api/internal-admin/impersonations/",
            {"user_id": staff_admin.pk, "reason": "Assist with configuration"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("redirect_url", resp.data)
        self.assertEqual(ImpersonationToken.objects.filter(target_user=staff_admin).count(), 1)

        super_target = User.objects.create_superuser(
            username="rooted",
            email="rooted@example.com",
            password="pass1234",
        )
        resp = self.client.post(
            "/api/internal-admin/impersonations/",
            {"user_id": super_target.pk, "reason": "Test"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("superuser", resp.data.get("detail", ""))

    def test_accept_impersonation_switches_user_and_marks_token(self):
        token = ImpersonationToken.objects.create(
            admin=self.ops_user,
            target_user=self.normal_user,
            expires_at=timezone.now() + timedelta(minutes=15),
            reason="Customer reported a UI issue",
        )
        self.web_client.force_login(self.ops_user)
        resp = self.web_client.get(reverse("internal-impersonate-accept", args=[token.id]))
        self.assertEqual(resp.status_code, 200)
        resp = self.web_client.post(reverse("internal-impersonate-accept", args=[token.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("dashboard"))
        token.refresh_from_db()
        self.assertFalse(token.is_active)
        self.assertIsNotNone(token.used_at)
        session = self.web_client.session
        self.assertTrue(session.get("is_impersonating"))
        self.assertEqual(session.get("impersonator_user_id"), self.ops_user.id)
        self.assertEqual(session.get("impersonated_user_id"), self.normal_user.id)
        self.assertEqual(int(session.get("_auth_user_id")), self.normal_user.id)
        self.assertEqual(AdminAuditLog.objects.filter(action="impersonation.accepted").count(), 1)

    def test_accept_impersonation_rejects_wrong_admin(self):
        token = ImpersonationToken.objects.create(
            admin=self.ops_user,
            target_user=self.normal_user,
            expires_at=timezone.now() + timedelta(minutes=15),
            reason="Test",
        )
        self.web_client.force_login(self.support_user)
        resp = self.web_client.get(reverse("internal-impersonate-accept", args=[token.id]))
        self.assertEqual(resp.status_code, 403)
        token.refresh_from_db()
        self.assertTrue(token.is_active)
        self.assertIsNone(token.used_at)

    def test_accept_impersonation_rejects_expired_or_used(self):
        expired = ImpersonationToken.objects.create(
            admin=self.ops_user,
            target_user=self.normal_user,
            expires_at=timezone.now() - timedelta(minutes=1),
            reason="Test",
        )
        self.web_client.force_login(self.ops_user)
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
            admin=self.ops_user,
            target_user=self.normal_user,
            expires_at=timezone.now() + timedelta(minutes=15),
            reason="Test",
        )
        self.web_client.force_login(self.ops_user)
        self.web_client.get(reverse("internal-impersonate-accept", args=[token.id]))
        self.web_client.post(reverse("internal-impersonate-accept", args=[token.id]))
        resp = self.web_client.get(reverse("internal-impersonate-stop"))
        self.assertEqual(resp.status_code, 200)
        resp = self.web_client.post(reverse("internal-impersonate-stop"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("admin_spa"))
        session = self.web_client.session
        self.assertFalse(session.get("is_impersonating"))
        self.assertEqual(int(session.get("_auth_user_id")), self.ops_user.id)
        self.assertEqual(AdminAuditLog.objects.filter(action="impersonation.stopped").count(), 1)

    def test_stop_impersonation_logs_out_if_admin_missing(self):
        self.web_client.force_login(self.normal_user)
        session = self.web_client.session
        session["is_impersonating"] = True
        session["impersonator_user_id"] = 9999
        session.save()

        resp = self.web_client.post(reverse("internal-impersonate-stop"))
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

    def test_support_ticket_create_requires_subject(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.post(
            "/api/internal-admin/support-tickets/",
            {"priority": SupportTicket.Priority.NORMAL},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subject", resp.data)

    def test_support_ticket_create_success_with_subject(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.post(
            "/api/internal-admin/support-tickets/",
            {"subject": "Assistance needed", "priority": SupportTicket.Priority.NORMAL},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data.get("subject"), "Assistance needed")
        self.assertEqual(SupportTicket.objects.count(), 1)

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

    def test_critical_feature_flag_requires_approval(self):
        from internal_admin.models import AdminApprovalRequest
        from django.test import override_settings

        with override_settings(INTERNAL_ADMIN_CRITICAL_FEATURE_FLAGS=["critical-flag"]):
            flag = FeatureFlag.objects.create(key="critical-flag", label="Critical Flag")

            # Engineering can request, but change is executed only on approval.
            self.client.force_authenticate(user=self.engineering_user)
            resp = self.client.patch(
                f"/api/internal-admin/feature-flags/{flag.pk}/",
                {"is_enabled": True, "reason": "Enable for incident mitigation"},
                format="json",
            )
            self.assertEqual(resp.status_code, 202)
            approval_id = resp.data["approval_request_id"]

            flag.refresh_from_db()
            self.assertFalse(flag.is_enabled)

            super2 = make_admin_user("super-ff@example.com", AdminRole.SUPERADMIN)
            self.client.force_authenticate(user=super2)
            approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
            self.assertEqual(approve_resp.status_code, 200)
            self.assertEqual(approve_resp.data["status"], AdminApprovalRequest.Status.APPROVED)

            flag.refresh_from_db()
            self.assertTrue(flag.is_enabled)

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
        self.assertEqual(len(resp.data["results"]), 1)

    def test_internal_admin_login_flow(self):
        staff_user = User.objects.create_user(username="staff", email="staff@example.com", password="pass1234")
        StaffProfile.objects.create(
            user=staff_user,
            display_name="Staff User",
            department="Ops",
            admin_panel_access=True,
            primary_admin_role=StaffProfile.PrimaryAdminRole.SUPPORT,
            is_active_employee=True,
            workspace_scope={"mode": "all"},
        )
        resp = self.web_client.post(
            "/internal-admin/login/",
            {"username": staff_user.email, "password": "pass1234"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].endswith("/internal-admin/"))

        # Non-staff rejected
        resp = self.web_client.post(
            "/internal-admin/login/",
            {"username": self.normal_user.email, "password": "pass1234"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid credentials", status_code=200)

    def test_current_user_api_exposes_internal_admin_role_for_profile(self):
        """Test /api/auth/me exposes internal admin role for users with InternalAdminProfile"""
        import json
        # Support user (not is_staff) should get internalAdmin data
        self.web_client.force_login(self.support_user)
        resp = self.web_client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["authenticated"], True)
        user_data = data["user"]
        self.assertIsNotNone(user_data.get("internalAdmin"))
        self.assertEqual(user_data["internalAdmin"]["role"], AdminRole.SUPPORT)
        self.assertTrue(user_data["internalAdmin"]["canAccessInternalAdmin"])
        self.assertFalse(user_data["internalAdmin"]["canManageAdminUsers"])
        self.assertFalse(user_data["internalAdmin"]["canGrantSuperadmin"])

    def test_current_user_api_returns_null_for_normal_user(self):
        """Test /api/auth/me returns null internalAdmin for normal users"""
        import json
        self.web_client.force_login(self.normal_user)
        resp = self.web_client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        user_data = data["user"]
        self.assertIsNone(user_data.get("internalAdmin"))

    def test_current_user_api_denies_staff_without_explicit_admin_access(self):
        """Test /api/auth/me does not treat is_staff alone as internal admin access."""
        import json
        staff_user = User.objects.create_user(
            username="staffonly",
            email="staffonly@example.com",
            password="pass1234",
            is_staff=True,
        )
        self.web_client.force_login(staff_user)
        resp = self.web_client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        user_data = data["user"]
        self.assertIsNone(user_data.get("internalAdmin"))

    def test_current_user_api_allows_superuser_break_glass(self):
        """Test /api/auth/me exposes SUPERADMIN for Django superusers as break-glass."""
        import json

        superuser = User.objects.create_user(
            username="root",
            email="root@example.com",
            password="pass1234",
            is_superuser=True,
        )
        self.web_client.force_login(superuser)
        resp = self.web_client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        user_data = data["user"]
        self.assertIsNotNone(user_data.get("internalAdmin"))
        self.assertEqual(user_data["internalAdmin"]["role"], AdminRole.SUPERADMIN)
        self.assertTrue(user_data["internalAdmin"]["canAccessInternalAdmin"])
        self.assertTrue(user_data["internalAdmin"]["canManageAdminUsers"])
        self.assertTrue(user_data["internalAdmin"]["canGrantSuperadmin"])

    # =========================================================================
    # Employees / Admin Access
    # =========================================================================

    def test_employees_endpoints_require_superadmin(self):
        target = User.objects.create_user(username="emp1", email="emp1@example.com", password="pass1234")
        StaffProfile.objects.create(
            user=target,
            display_name="Emp One",
            department="Support",
            admin_panel_access=True,
            primary_admin_role=StaffProfile.PrimaryAdminRole.SUPPORT,
            is_active_employee=True,
            workspace_scope={"mode": "all"},
        )

        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/employees/")
        self.assertEqual(resp.status_code, 403)

        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.get("/api/internal-admin/employees/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["email"], "emp1@example.com")

    def test_only_primary_admin_can_grant_superadmin_role(self):
        target = User.objects.create_user(username="emp2", email="emp2@example.com", password="pass1234")
        staff = StaffProfile.objects.create(
            user=target,
            display_name="Emp Two",
            department="Engineering",
            admin_panel_access=True,
            primary_admin_role=StaffProfile.PrimaryAdminRole.ENGINEERING,
            is_active_employee=True,
            workspace_scope={"mode": "all"},
        )

        # SUPERADMIN can manage employees but cannot grant SUPERADMIN role.
        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.patch(
            f"/api/internal-admin/employees/{staff.pk}/",
            {"primary_admin_role": "superadmin"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        staff.refresh_from_db()
        self.assertEqual(staff.primary_admin_role, StaffProfile.PrimaryAdminRole.ENGINEERING)

        # PRIMARY_ADMIN can grant SUPERADMIN.
        primary = make_admin_user("primary-grant@example.com", AdminRole.PRIMARY_ADMIN)
        self.client.force_authenticate(user=primary)
        resp = self.client.patch(
            f"/api/internal-admin/employees/{staff.pk}/",
            {"primary_admin_role": "superadmin"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        staff.refresh_from_db()
        self.assertEqual(staff.primary_admin_role, StaffProfile.PrimaryAdminRole.SUPERADMIN)
        self.assertTrue(InternalAdminProfile.objects.filter(user=target, role=AdminRole.SUPERADMIN).exists())

    def test_suspend_employee_revokes_admin_access_and_logs_audit(self):
        target = User.objects.create_user(username="emp3", email="emp3@example.com", password="pass1234")
        staff = StaffProfile.objects.create(
            user=target,
            display_name="Emp Three",
            department="Ops",
            admin_panel_access=True,
            primary_admin_role=StaffProfile.PrimaryAdminRole.FINANCE,
            is_active_employee=True,
            workspace_scope={"mode": "all"},
        )
        InternalAdminProfile.objects.create(user=target, role=AdminRole.OPS)

        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.post(f"/api/internal-admin/employees/{staff.pk}/suspend/", format="json")
        self.assertEqual(resp.status_code, 200)

        staff.refresh_from_db()
        self.assertFalse(staff.is_active_employee)
        self.assertFalse(staff.admin_panel_access)
        self.assertFalse(InternalAdminProfile.objects.filter(user=target).exists())

        audit = AdminAuditLog.objects.filter(action="admin_staff_suspended").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.extra.get("target_user_id"), target.pk)
        self.assertIn("before", audit.extra)
        self.assertIn("after", audit.extra)

    def test_delete_employee_requires_primary_admin(self):
        target = User.objects.create_user(username="emp4", email="emp4@example.com", password="pass1234")
        staff = StaffProfile.objects.create(
            user=target,
            display_name="Emp Four",
            department="Support",
            admin_panel_access=False,
            primary_admin_role=StaffProfile.PrimaryAdminRole.NONE,
            is_active_employee=True,
            workspace_scope={"mode": "all"},
        )

        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.post(f"/api/internal-admin/employees/{staff.pk}/delete/", format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(StaffProfile.objects.filter(pk=staff.pk).exists())

        primary = make_admin_user("primary-delete@example.com", AdminRole.PRIMARY_ADMIN)
        self.client.force_authenticate(user=primary)
        resp = self.client.post(f"/api/internal-admin/employees/{staff.pk}/delete/", format="json")
        self.assertEqual(resp.status_code, 200)
        staff.refresh_from_db()
        self.assertTrue(staff.is_deleted)
        self.assertFalse(staff.is_active_employee)
        self.assertFalse(staff.admin_panel_access)
        self.assertIsNotNone(staff.deleted_at)
        self.assertEqual(AdminAuditLog.objects.filter(action="admin_staff_deleted").count(), 1)

    def test_invite_employee_creates_staff_profile_and_sends_email(self):
        from unittest import mock

        self.client.force_authenticate(user=self.superadmin_user)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1) as send_mock:
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "newstaff@example.com", "full_name": "New Staff", "role": "support"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)
        send_mock.assert_called()

        staff = StaffProfile.objects.filter(user__email="newstaff@example.com").first()
        self.assertIsNotNone(staff)
        self.assertFalse(staff.is_active_employee)
        self.assertFalse(staff.admin_panel_access)
        self.assertEqual(staff.primary_admin_role, StaffProfile.PrimaryAdminRole.SUPPORT)

        invite = AdminInvite.objects.filter(staff_profile=staff).order_by("-created_at").first()
        self.assertIsNotNone(invite)
        self.assertTrue(invite.is_active)
        self.assertIsNone(invite.used_at)
        self.assertEqual(invite.email, "newstaff@example.com")
        self.assertEqual(invite.full_name, "New Staff")
        self.assertEqual(invite.email_last_error, "")
        self.assertIsNotNone(invite.last_emailed_at)

        audit = AdminAuditLog.objects.filter(action="staff_invite.created").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.extra.get("target_user_id"), staff.user_id)

    def test_invite_employee_returns_warning_when_email_send_fails(self):
        from unittest import mock

        self.client.force_authenticate(user=self.superadmin_user)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", side_effect=Exception("smtp down")):
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "failmail@example.com", "full_name": "Fail Mail", "role": "support"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data.get("invite", {}).get("email_send_failed"))

        staff = StaffProfile.objects.get(user__email="failmail@example.com")
        invite = AdminInvite.objects.filter(staff_profile=staff).order_by("-created_at").first()
        self.assertIsNotNone(invite)
        self.assertNotEqual(invite.email_last_error, "")

    def test_invite_employee_requires_superadmin(self):
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.post(
            "/api/internal-admin/employees/invite/",
            {"email": "blocked@example.com", "full_name": "Blocked", "role": "support"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_invite_employee_superadmin_role_requires_primary_admin(self):
        from unittest import mock

        self.client.force_authenticate(user=self.superadmin_user)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1):
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "superstaff@example.com", "full_name": "Super Staff", "role": "superadmin"},
                format="json",
            )
        self.assertEqual(resp.status_code, 403)

        primary = make_admin_user("primary-invite@example.com", AdminRole.PRIMARY_ADMIN)
        self.client.force_authenticate(user=primary)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1):
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "superstaff@example.com", "full_name": "Super Staff", "role": "superadmin"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)

    def test_resend_and_revoke_invite_are_audited(self):
        from unittest import mock

        self.client.force_authenticate(user=self.superadmin_user)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1):
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "pending@example.com", "full_name": "Pending", "role": "support"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)
        staff = StaffProfile.objects.get(user__email="pending@example.com")

        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1):
            resp = self.client.post(f"/api/internal-admin/employees/{staff.pk}/resend-invite/", format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(AdminAuditLog.objects.filter(action="staff_invite.resent").exists())

        resp = self.client.post(f"/api/internal-admin/employees/{staff.pk}/revoke-invite/", format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(AdminAuditLog.objects.filter(action="staff_invite.revoked").exists())
        self.assertFalse(AdminInvite.objects.filter(staff_profile=staff, used_at__isnull=True, is_active=True).exists())

    def test_staff_invite_accept_activates_staff_profile(self):
        from unittest import mock

        self.client.force_authenticate(user=self.superadmin_user)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1):
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "acceptme@example.com", "full_name": "Accept Me", "role": "support"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)

        staff = StaffProfile.objects.get(user__email="acceptme@example.com")
        invite = AdminInvite.objects.filter(staff_profile=staff).order_by("-created_at").first()
        self.assertIsNotNone(invite)

        # Public accept flow: set username/password and activate staff profile.
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            f"/api/internal-admin/invite/{invite.id}/",
            {
                "email": "acceptme@example.com",
                "username": "acceptme",
                "password": "StrongPass123!",
                "first_name": "Accept",
                "last_name": "Me",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        staff.refresh_from_db()
        self.assertTrue(staff.is_active_employee)
        self.assertTrue(staff.admin_panel_access)
        self.assertTrue(InternalAdminProfile.objects.filter(user=staff.user, role=AdminRole.SUPPORT).exists())

        invite.refresh_from_db()
        self.assertIsNotNone(invite.used_at)
        self.assertIsNotNone(invite.used_by_id)
        self.assertEqual(invite.use_count, 1)
        self.assertTrue(AdminAuditLog.objects.filter(action="staff_invite.accepted").exists())

    def test_staff_invite_accept_rejects_revoked(self):
        from unittest import mock

        self.client.force_authenticate(user=self.superadmin_user)
        with mock.patch("internal_admin.emails.EmailMultiAlternatives.send", return_value=1):
            resp = self.client.post(
                "/api/internal-admin/employees/invite/",
                {"email": "revoked@example.com", "full_name": "Revoked", "role": "support"},
                format="json",
            )
        self.assertEqual(resp.status_code, 201)
        staff = StaffProfile.objects.get(user__email="revoked@example.com")
        invite = AdminInvite.objects.filter(staff_profile=staff).order_by("-created_at").first()
        invite.is_active = False
        invite.save(update_fields=["is_active"])

        self.client.force_authenticate(user=None)
        resp = self.client.post(
            f"/api/internal-admin/invite/{invite.id}/",
            {
                "email": "revoked@example.com",
                "username": "revoked",
                "password": "StrongPass123!",
                "first_name": "Revoked",
                "last_name": "User",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    # =========================================================================
    # Central Admin Phase 3: Workspace 360 and Approvals Tests
    # =========================================================================

    def test_workspace_360_endpoint_returns_aggregated_data(self):
        """Test GET /api/internal-admin/workspaces/<id>/overview/ returns unified view"""
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get(f"/api/internal-admin/workspaces/{self.business.pk}/overview/")
        self.assertEqual(resp.status_code, 200)

        # Check main sections exist
        for key in ["workspace", "owner", "banking", "ledger_health", "invoices", "expenses", "tax", "ai"]:
            self.assertIn(key, resp.data)

        # Verify workspace data
        self.assertEqual(resp.data["workspace"]["id"], self.business.pk)
        self.assertEqual(resp.data["workspace"]["name"], self.business.name)

        # Verify banking data includes our bank account
        self.assertGreaterEqual(resp.data["banking"]["account_count"], 1)

        # Audit log should be created
        self.assertEqual(AdminAuditLog.objects.filter(action="workspace_360.view").count(), 1)

    def test_workspace_360_requires_admin(self):
        """Test Workspace 360 endpoint requires admin authentication"""
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get(f"/api/internal-admin/workspaces/{self.business.pk}/overview/")
        self.assertEqual(resp.status_code, 403)

    def test_workspace_360_returns_404_for_invalid_id(self):
        """Test Workspace 360 returns 404 for non-existent workspace"""
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/workspaces/99999/overview/")
        self.assertEqual(resp.status_code, 404)

    def test_approvals_list_endpoint(self):
        """Test GET /api/internal-admin/approvals/ returns pending approvals"""
        self.client.force_authenticate(user=self.support_user)
        resp = self.client.get("/api/internal-admin/approvals/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        self.assertIn("count", resp.data)

    def test_approvals_create_endpoint(self):
        """Test POST /api/internal-admin/approvals/ creates approval request"""
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.post(
            "/api/internal-admin/approvals/",
            {
                "action_type": "TAX_PERIOD_RESET",
                "reason": "Customer requested reset due to import error",
                "workspace_id": self.business.pk,
                "payload": {"period_id": 123},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.data)
        self.assertEqual(resp.data["status"], "PENDING")

        # Audit log should be created
        self.assertEqual(AdminAuditLog.objects.filter(action="approval.created").count(), 1)

    def test_approvals_create_requires_reason(self):
        """Test approval creation requires a reason"""
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.post(
            "/api/internal-admin/approvals/",
            {"action_type": "TAX_PERIOD_RESET", "workspace_id": self.business.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("reason", resp.data.get("error", ""))

    def test_approvals_invalid_action_type_rejected(self):
        """Test approval creation rejects invalid action types"""
        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.post(
            "/api/internal-admin/approvals/",
            {"action_type": "INVALID_ACTION", "reason": "Test"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_approvals_approve_and_reject(self):
        """Test approval approve/reject endpoints"""
        from internal_admin.models import AdminApprovalRequest

        target = User.objects.create_user(username="ban1", email="ban1@example.com", password="pass1234")

        # Create an approval request (OPS+ only)
        self.client.force_authenticate(user=self.ops_user)
        create_resp = self.client.post(
            "/api/internal-admin/approvals/",
            {
                "action_type": "USER_BAN",
                "reason": "Chargeback abuse",
                "target_user_id": target.pk,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        request_id = create_resp.data["id"]

        # Different OPS approves and executes
        ops2 = make_admin_user("ops-approve@example.com", AdminRole.OPS)
        self.client.force_authenticate(user=ops2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{request_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.data["status"], "APPROVED")

        approval = AdminApprovalRequest.objects.get(id=request_id)
        self.assertEqual(approval.status, AdminApprovalRequest.Status.APPROVED)
        self.assertEqual(approval.approver_admin, ops2)

        target.refresh_from_db()
        self.assertFalse(target.is_active)

        # Reject flow
        target2 = User.objects.create_user(username="ban2", email="ban2@example.com", password="pass1234")
        self.client.force_authenticate(user=self.ops_user)
        create_resp2 = self.client.post(
            "/api/internal-admin/approvals/",
            {
                "action_type": "USER_BAN",
                "reason": "Test reject",
                "target_user_id": target2.pk,
            },
            format="json",
        )
        self.assertEqual(create_resp2.status_code, 201)
        request_id2 = create_resp2.data["id"]

        self.client.force_authenticate(user=ops2)
        reject_resp = self.client.post(
            f"/api/internal-admin/approvals/{request_id2}/reject/",
            {"reason": "Insufficient evidence"},
            format="json",
        )
        self.assertEqual(reject_resp.status_code, 200)
        self.assertEqual(reject_resp.data["status"], "REJECTED")

    def test_approval_reject_enforces_permissions(self):
        """Reject requires an eligible checker (and cannot be done by maker)."""
        from internal_admin.models import AdminApprovalRequest

        support2 = make_admin_user("support2@example.com", AdminRole.SUPPORT)

        target = User.objects.create_user(username="ban3", email="ban3@example.com", password="pass1234")

        self.client.force_authenticate(user=self.ops_user)
        create_resp = self.client.post(
            "/api/internal-admin/approvals/",
            {
                "action_type": "USER_BAN",
                "reason": "Test reject permissions",
                "target_user_id": target.pk,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        request_id = create_resp.data["id"]

        # Maker cannot reject
        self.client.force_authenticate(user=self.ops_user)
        reject_resp = self.client.post(
            f"/api/internal-admin/approvals/{request_id}/reject/",
            {"reason": "No longer needed"},
            format="json",
        )
        self.assertEqual(reject_resp.status_code, 403)

        # Support cannot reject (endpoint requires OPS)
        self.client.force_authenticate(user=support2)
        reject_resp = self.client.post(
            f"/api/internal-admin/approvals/{request_id}/reject/",
            {"reason": "Not allowed"},
            format="json",
        )
        self.assertEqual(reject_resp.status_code, 403)

        # OPS can reject
        ops2 = make_admin_user("ops-reject@example.com", AdminRole.OPS)
        self.client.force_authenticate(user=ops2)
        reject_resp = self.client.post(
            f"/api/internal-admin/approvals/{request_id}/reject/",
            {"reason": "Insufficient justification"},
            format="json",
        )
        self.assertEqual(reject_resp.status_code, 200)
        self.assertEqual(reject_resp.data["status"], "REJECTED")

        approval = AdminApprovalRequest.objects.get(id=request_id)
        self.assertEqual(approval.status, AdminApprovalRequest.Status.REJECTED)
        self.assertEqual(approval.approver_admin, ops2)

        self.assertEqual(AdminAuditLog.objects.filter(action="approval.rejected").count(), 1)

    def test_approval_expired_requests_are_blocked(self):
        from internal_admin.models import AdminApprovalRequest
        from django.utils import timezone
        from datetime import timedelta

        req = AdminApprovalRequest.objects.create(
            initiator_admin=self.support_user,
            action_type=AdminApprovalRequest.ActionType.TAX_PERIOD_RESET,
            workspace=self.business,
            payload={},
            reason="Expired request",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.client.force_authenticate(user=self.ops_user)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{req.id}/approve/")
        self.assertEqual(approve_resp.status_code, 400)

        req.refresh_from_db()
        self.assertEqual(req.status, AdminApprovalRequest.Status.EXPIRED)

    def test_user_admin_role_can_be_set_and_removed_by_superadmin(self):
        from internal_admin.models import AdminApprovalRequest

        target = User.objects.create_user(username="t1", email="t1@example.com", password="pass1234")

        self.client.force_authenticate(user=self.superadmin_user)
        resp = self.client.patch(
            f"/api/internal-admin/users/{target.pk}/",
            {"admin_role": "OPS", "reason": "Grant ops access"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        approval_id = resp.data["approval_request_id"]
        self.assertFalse(InternalAdminProfile.objects.filter(user=target).exists())

        super2 = make_admin_user("super-approve@example.com", AdminRole.SUPERADMIN)
        self.client.force_authenticate(user=super2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.data["status"], AdminApprovalRequest.Status.APPROVED)
        self.assertTrue(InternalAdminProfile.objects.filter(user=target, role=AdminRole.OPS).exists())

        target.refresh_from_db()
        resp = self.client.patch(
            f"/api/internal-admin/users/{target.pk}/",
            {"admin_role": None, "reason": "Remove admin access"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        approval_id2 = resp.data["approval_request_id"]

        super3 = make_admin_user("super-approve2@example.com", AdminRole.SUPERADMIN)
        self.client.force_authenticate(user=super3)
        approve_resp2 = self.client.post(f"/api/internal-admin/approvals/{approval_id2}/approve/")
        self.assertEqual(approve_resp2.status_code, 200)
        self.assertEqual(approve_resp2.data["status"], AdminApprovalRequest.Status.APPROVED)
        self.assertFalse(InternalAdminProfile.objects.filter(user=target).exists())

    def test_primary_admin_can_delete_workspaces(self):
        primary = make_admin_user("primary@example.com", AdminRole.PRIMARY_ADMIN)
        self.client.force_authenticate(user=primary)
        resp = self.client.patch(
            f"/api/internal-admin/workspaces/{self.business.pk}/",
            {"is_deleted": True, "reason": "Close tenant"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        approval_id = resp.data["approval_request_id"]

        self.business.refresh_from_db()
        self.assertFalse(self.business.is_deleted)

        primary2 = make_admin_user("primary2@example.com", AdminRole.PRIMARY_ADMIN)
        self.client.force_authenticate(user=primary2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)

        self.business.refresh_from_db()
        self.assertTrue(self.business.is_deleted)

    def test_password_reset_link_endpoint_returns_url_and_works(self):
        import urllib.parse
        from internal_admin.models import AdminApprovalRequest

        target = User.objects.create_user(username="pwr", email="pwr@example.com", password="OldPass123!")

        self.client.force_authenticate(user=self.ops_user)
        resp = self.client.post(
            f"/api/internal-admin/users/{target.pk}/reset-password/",
            {"reason": "Account recovery"},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        approval_id = resp.data["approval_request_id"]

        ops2 = make_admin_user("ops-reset@example.com", AdminRole.OPS)
        self.client.force_authenticate(user=ops2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.data["status"], AdminApprovalRequest.Status.APPROVED)

        approval = AdminApprovalRequest.objects.get(id=approval_id)
        reset_url = approval.payload.get("reset_url")
        self.assertTrue(reset_url)

        parsed = urllib.parse.urlparse(reset_url)
        reset_path = parsed.path

        get_resp = self.web_client.get(reset_path, follow=True)
        self.assertEqual(get_resp.status_code, 200)
        # Django redirects to a "set-password" URL to avoid leaking token in referrers.
        final_path = get_resp.redirect_chain[-1][0] if get_resp.redirect_chain else reset_path
        final_path = urllib.parse.urlparse(final_path).path

        post_resp = self.web_client.post(
            final_path,
            {"new_password1": "SuperStrongPassword123!", "new_password2": "SuperStrongPassword123!"},
            follow=True,
        )
        self.assertEqual(post_resp.status_code, 200)

        target.refresh_from_db()
        self.assertTrue(target.check_password("SuperStrongPassword123!"))

    def test_break_glass_reveals_redacted_reset_url_for_approval(self):
        from internal_admin.models import AdminApprovalRequest

        target = User.objects.create_user(username="bg1", email="bg1@example.com", password="OldPass123!")

        # Maker: create a password reset link request
        self.client.force_authenticate(user=self.ops_user)
        create_resp = self.client.post(
            "/api/internal-admin/approvals/",
            {
                "action_type": "PASSWORD_RESET_LINK",
                "reason": "Account recovery",
                "target_user_id": target.pk,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201)
        approval_id = create_resp.data["id"]

        # Checker: approve+execute (generates reset_url into payload)
        ops2 = make_admin_user("ops-bg-approve@example.com", AdminRole.OPS)
        self.client.force_authenticate(user=ops2)
        approve_resp = self.client.post(f"/api/internal-admin/approvals/{approval_id}/approve/")
        self.assertEqual(approve_resp.status_code, 200)

        approval = AdminApprovalRequest.objects.get(id=approval_id)
        self.assertTrue(approval.payload.get("reset_url"))

        # Non-superadmin, non-participant sees redacted reset_url
        self.client.force_authenticate(user=self.engineering_user)
        list_resp = self.client.get("/api/internal-admin/approvals/?status=APPROVED")
        self.assertEqual(list_resp.status_code, 200)
        entry = next((r for r in list_resp.data["results"] if r["id"] == approval_id), None)
        self.assertIsNotNone(entry)
        self.assertIsNone(entry["payload"].get("reset_url"))
        self.assertIn("reset_url", entry["payload"].get("_redacted", []))

        # Break-glass grant reveals it (time-bound + audited)
        bg_resp = self.client.post(
            f"/api/internal-admin/approvals/{approval_id}/break-glass/",
            {"reason": "Need to deliver link securely"},
            format="json",
        )
        self.assertEqual(bg_resp.status_code, 201)
        self.assertIn("expires_at", bg_resp.data)

        list_resp2 = self.client.get("/api/internal-admin/approvals/?status=APPROVED")
        entry2 = next((r for r in list_resp2.data["results"] if r["id"] == approval_id), None)
        self.assertTrue(entry2["payload"].get("reset_url"))


class AuthLoginCSRFTargetTests(TestCase):
    def test_api_login_requires_csrf(self):
        import json
        from django.test import Client

        user = User.objects.create_user(username="u1", email="u1@example.com", password="pass1234")
        client = Client(enforce_csrf_checks=True)

        # No CSRF -> forbidden
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": user.username, "password": "pass1234"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

        # Fetch CSRF cookie then login with token
        client.get("/api/auth/config")
        csrf_token = client.cookies.get("csrftoken").value
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": user.username, "password": "pass1234"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(resp.status_code, 200)
