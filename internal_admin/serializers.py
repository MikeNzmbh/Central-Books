from __future__ import annotations

from typing import Any, Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from core.models import BankAccount, Business
from .models import (
    AdminAuditLog,
    AdminRole,
    FeatureFlag,
    SupportTicket,
    SupportTicketNote,
)


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    admin_role = serializers.SerializerMethodField()
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
            "admin_role",
            "date_joined",
            "last_login",
            "is_staff",
            "is_superuser",
            "workspace_count",
            "has_usable_password",
            "auth_providers",
            "has_google_login",
            "social_account_count",
        ]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.email or obj.username

    def get_admin_role(self, obj: User) -> str | None:
        profile = getattr(obj, "internal_admin_profile", None)
        return profile.role if profile else None

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
        allowed_fields = {"first_name", "last_name", "email", "is_active"}
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)
        instance.save(update_fields=list(allowed_fields & set(validated_data.keys())))
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
            "action",
            "object_type",
            "object_id",
            "extra",
            "remote_ip",
            "level",
            "category",
        ]
        read_only_fields = fields


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
            "subject",
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
