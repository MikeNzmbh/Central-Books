from __future__ import annotations

from typing import Any, Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.models import BankAccount, Business
from .models import (
    AdminAuditLog,
    AdminInvite,
    AdminRole,
    FeatureFlag,
    StaffProfile,
    SupportTicket,
    SupportTicketNote,
)


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    admin_role = serializers.CharField(required=False, allow_null=True)
    workspace_count = serializers.IntegerField(read_only=True)
    has_usable_password = serializers.SerializerMethodField()
    auth_providers = serializers.SerializerMethodField()
    has_google_login = serializers.SerializerMethodField()
    social_account_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "date_joined",
            "last_login",
            "is_active",
            "is_staff",
            "is_superuser",
            "admin_role",
            "workspace_count",
            "has_usable_password",
            "auth_providers",
            "has_google_login",
            "social_account_count",
        ]
        read_only_fields = [
            "id",
            "username",
            "full_name",
            "date_joined",
            "last_login",
            "workspace_count",
            "has_usable_password",
            "auth_providers",
            "has_google_login",
            "social_account_count",
        ]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.email or obj.username

    def to_representation(self, instance: User):
        data = super().to_representation(instance)
        profile = getattr(instance, "internal_admin_profile", None)
        data["admin_role"] = profile.role if profile else None
        return data

    def validate_admin_role(self, value: str | None) -> str | None:
        if value is None:
            return None
        if value == "":
            return None
        valid = {choice[0] for choice in AdminRole.choices}
        if value not in valid:
            raise serializers.ValidationError(f"Invalid admin_role. Must be one of: {sorted(valid)}")
        return value

    def get_has_usable_password(self, obj: User) -> bool:
        return obj.has_usable_password()

    @staticmethod
    def _providers(obj: User) -> list[str]:
        providers: Iterable[str] = []
        social_accounts = getattr(obj, "_social_accounts", None) or getattr(obj, "socialaccount_set", None)
        if social_accounts is not None:
            iterable = (
                social_accounts
                if isinstance(social_accounts, (list, tuple))
                else social_accounts.all()
            )
            providers = [getattr(sa, "provider", "") for sa in iterable if getattr(sa, "provider", "")]
        return sorted(list({p for p in providers if p}))

    def get_auth_providers(self, obj: User) -> list[str]:
        return self._providers(obj)

    def get_has_google_login(self, obj: User) -> bool:
        return "google" in self._providers(obj)

    def get_social_account_count(self, obj: User) -> int:
        annotated = getattr(obj, "social_account_count", None)
        if annotated is not None:
            return annotated
        return len(self._providers(obj))

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        from .models import InternalAdminProfile
        from .permissions import has_min_role

        request = self.context.get("request")
        allowed_fields = {"first_name", "last_name", "email", "is_active"}

        # Superadmins can modify staff/superuser status
        if request and has_min_role(request.user, AdminRole.SUPERADMIN):
            allowed_fields.update({"is_staff", "is_superuser"})

        # Handle admin_role separately (it's on InternalAdminProfile)
        admin_role_present = "admin_role" in getattr(self, "initial_data", {})
        admin_role = validated_data.pop("admin_role", None)

        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)
        instance.save(update_fields=list(allowed_fields & set(validated_data.keys())))

        # Update admin_role if superadmin and role provided
        if request and has_min_role(request.user, AdminRole.SUPERADMIN) and admin_role_present:
            if admin_role:
                profile, _ = InternalAdminProfile.objects.get_or_create(user=instance)
                profile.role = admin_role
                profile.save(update_fields=["role"])
            else:
                # Remove admin role
                InternalAdminProfile.objects.filter(user=instance).delete()

        return instance


class BusinessSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner_user.email", read_only=True)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "owner_email",
            "plan",
            "status",
            "is_deleted",
            "created_at",
            "bank_setup_completed",
        ]
        read_only_fields = ["id", "owner_email", "created_at", "bank_setup_completed"]

    def update(self, instance: Business, validated_data: dict[str, Any]) -> Business:
        request = self.context.get("request")
        allowed_fields = {"name", "plan", "status"}
        if request and hasattr(request, "user"):
            from .permissions import has_min_role

            if has_min_role(request.user, AdminRole.SUPERADMIN):
                allowed_fields.add("is_deleted")
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)
        instance.save(update_fields=list(allowed_fields & set(validated_data.keys())))
        return instance


class BankAccountSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(source="business.name", read_only=True)
    owner_email = serializers.EmailField(source="business.owner_user.email", read_only=True)
    status = serializers.SerializerMethodField()
    unreconciled_count = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "workspace_name",
            "owner_email",
            "bank_name",
            "name",
            "account_number_mask",
            "usage_role",
            "is_active",
            "last_imported_at",
            "status",
            "unreconciled_count",
        ]
        read_only_fields = fields

    def get_status(self, obj: BankAccount) -> str:
        if not obj.is_active:
            return "disconnected"
        return "ok"

    def get_unreconciled_count(self, obj: BankAccount) -> int:
        return (
            obj.bank_transactions.filter(is_reconciled=False, reconciliation_status="unreconciled").count()
        )


class AdminAuditLogSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source="admin_user.email", read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = [
            "id",
            "timestamp",
            "admin_email",
            "actor_role",
            "action",
            "object_type",
            "object_id",
            "extra",
            "remote_ip",
            "user_agent",
            "request_id",
            "level",
            "category",
        ]
        read_only_fields = fields


class StaffProfileListSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    invite = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "user_id",
            "name",
            "email",
            "title",
            "department",
            "admin_panel_access",
            "primary_admin_role",
            "is_active_employee",
            "is_deleted",
            "deleted_at",
            "last_login",
            "workspace_scope",
            "invite",
        ]
        read_only_fields = fields

    def get_invite(self, obj: StaffProfile):
        request = self.context.get("request")
        now = timezone.now()

        invite_obj = None
        try:
            invites_qs: Iterable[AdminInvite] = obj.invites.all()
            for invite in sorted(invites_qs, key=lambda i: i.created_at, reverse=True):
                if invite.used_at is None and invite.is_active:
                    invite_obj = invite
                    break
        except Exception:
            invite_obj = (
                AdminInvite.objects.filter(staff_profile=obj, used_at__isnull=True, is_active=True)
                .order_by("-created_at")
                .first()
            )

        if not invite_obj:
            return None

        status = "expired" if invite_obj.expires_at and invite_obj.expires_at < now else "pending"
        return {
            "id": str(invite_obj.id),
            "status": status,
            "invited_at": invite_obj.created_at.isoformat(),
            "expires_at": invite_obj.expires_at.isoformat() if invite_obj.expires_at else None,
            "invite_url": invite_obj.get_invite_url(request),
            "email_send_failed": bool(invite_obj.email_last_error),
            "email_last_error": (invite_obj.email_last_error or "")[:500],
        }


class StaffProfileDetailSerializer(StaffProfileListSerializer):
    manager = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    recent_admin_actions = serializers.SerializerMethodField()

    class Meta(StaffProfileListSerializer.Meta):
        fields = StaffProfileListSerializer.Meta.fields + [
            "manager",
            "created_at",
            "updated_at",
            "recent_admin_actions",
        ]
        read_only_fields = fields

    def get_manager(self, obj: StaffProfile):
        if not obj.manager_id:
            return None
        manager = obj.manager
        if not manager:
            return None
        return {
            "id": manager.pk,
            "name": manager.get_full_name() or manager.email or manager.username,
            "email": manager.email,
        }

    def get_recent_admin_actions(self, obj: StaffProfile):
        qs = (
            AdminAuditLog.objects.filter(admin_user_id=obj.user_id)
            .order_by("-timestamp")
            .values("timestamp", "action", "object_type", "object_id", "level", "category")[:10]
        )
        return list(qs)


class StaffProfileWriteSerializer(serializers.ModelSerializer):
    # Create-only: attach an existing user or create a new user by email.
    display_name = serializers.CharField(required=False, allow_blank=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    manager_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "user_id",
            "email",
            "display_name",
            "title",
            "department",
            "admin_panel_access",
            "primary_admin_role",
            "is_active_employee",
            "manager_id",
            "workspace_scope",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context.get("request")
        from internal_admin.permissions import can_grant_superadmin

        instance: StaffProfile | None = getattr(self, "instance", None)
        if instance is not None and (attrs.get("user_id") is not None or attrs.get("email") is not None):
            raise serializers.ValidationError("user_id/email cannot be changed once a staff profile exists.")

        requested_role = attrs.get("primary_admin_role")
        if requested_role is not None:
            requested_role = str(requested_role).strip().lower()
            attrs["primary_admin_role"] = requested_role

        if instance is not None and instance.primary_admin_role == StaffProfile.PrimaryAdminRole.SUPERADMIN:
            if not request or not can_grant_superadmin(request.user):
                raise serializers.ValidationError("Only superadmin grantors can modify superadmin staff records.")

        if requested_role == StaffProfile.PrimaryAdminRole.SUPERADMIN:
            if not request or not can_grant_superadmin(request.user):
                raise serializers.ValidationError("Only superadmin grantors can set primary_admin_role=superadmin.")

        # If admin access is enabled, role must be set.
        admin_panel_access = attrs.get("admin_panel_access")
        if admin_panel_access is True:
            effective_role = requested_role
            if effective_role is None and instance is not None:
                effective_role = instance.primary_admin_role
            if effective_role in {None, "", StaffProfile.PrimaryAdminRole.NONE}:
                raise serializers.ValidationError("primary_admin_role must be set when admin_panel_access is enabled.")

        # Inactive employees cannot have admin access.
        if attrs.get("is_active_employee") is False and attrs.get("admin_panel_access") is True:
            raise serializers.ValidationError("Inactive employees cannot have admin_panel_access enabled.")

        return attrs

    def create(self, validated_data: dict[str, Any]) -> StaffProfile:
        from django.db import transaction

        user_id = validated_data.pop("user_id", None)
        email = (validated_data.pop("email", None) or "").strip().lower()
        manager_id = validated_data.pop("manager_id", None)

        if not user_id and not email:
            raise serializers.ValidationError("Provide either user_id or email.")

        with transaction.atomic():
            if user_id:
                user = User.objects.filter(pk=user_id).first()
                if not user:
                    raise serializers.ValidationError("User not found.")
            else:
                user = User.objects.filter(email__iexact=email).first()
                if not user:
                    username = email
                    user = User.objects.create_user(username=username, email=email, password=None)

            if manager_id is not None:
                manager = User.objects.filter(pk=manager_id).first()
                if manager_id and not manager:
                    raise serializers.ValidationError("manager_id not found.")
                validated_data["manager"] = manager

            # Default display name if not provided.
            if not validated_data.get("display_name"):
                validated_data["display_name"] = user.get_full_name() or user.email or user.username

            return StaffProfile.objects.create(user=user, **validated_data)

    def update(self, instance: StaffProfile, validated_data: dict[str, Any]) -> StaffProfile:
        manager_id = validated_data.pop("manager_id", None)
        if manager_id is not None:
            manager = User.objects.filter(pk=manager_id).first()
            if manager_id and not manager:
                raise serializers.ValidationError("manager_id not found.")
            instance.manager = manager

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class StaffInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=[
            StaffProfile.PrimaryAdminRole.SUPPORT,
            StaffProfile.PrimaryAdminRole.FINANCE,
            StaffProfile.PrimaryAdminRole.ENGINEERING,
            StaffProfile.PrimaryAdminRole.SUPERADMIN,
        ]
    )


class SupportTicketNoteSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source="admin_user.email", read_only=True)

    class Meta:
        model = SupportTicketNote
        fields = ["id", "admin_email", "body", "created_at"]
        read_only_fields = fields


class SupportTicketSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)
    notes = serializers.SerializerMethodField()
    subject = serializers.CharField(required=True, max_length=255)

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "subject",
            "status",
            "priority",
            "source",
            "created_at",
            "updated_at",
            "user_email",
            "workspace_name",
            "notes",
        ]
        read_only_fields = [
            "id",
            "source",
            "created_at",
            "updated_at",
            "user_email",
            "workspace_name",
            "notes",
        ]

    def get_notes(self, obj: SupportTicket):
        notes = obj.notes.select_related("admin_user").all()[:5]
        return SupportTicketNoteSerializer(notes, many=True).data

    def update(self, instance: SupportTicket, validated_data: dict[str, Any]) -> SupportTicket:
        allowed_fields = {"status", "priority"}
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)
        instance.save(update_fields=list(allowed_fields & set(validated_data.keys())))
        return instance


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "key",
            "label",
            "description",
            "is_enabled",
            "rollout_percent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
