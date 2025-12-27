from __future__ import annotations

from rest_framework import serializers

from companion.models import (
    AIIntegrityReport,
    BusinessPolicy,
    CanonicalLedgerProvenance,
    ProvisionalLedgerEvent,
    WorkspaceAISettings,
)


class WorkspaceAISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceAISettings
        fields = [
            "ai_enabled",
            "kill_switch",
            "ai_mode",
            "velocity_limit_per_minute",
            "value_breaker_threshold",
            "anomaly_stddev_threshold",
            "trust_downgrade_rejection_rate",
            "updated_at",
            "created_at",
        ]
        read_only_fields = ["updated_at", "created_at"]


class BusinessPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessPolicy
        fields = [
            "materiality_threshold",
            "risk_appetite",
            "commingling_risk_vendors",
            "related_entities",
            "intercompany_enabled",
            "sector_archetype",
            "updated_at",
            "created_at",
        ]
        read_only_fields = ["updated_at", "created_at"]


class ProvisionalLedgerEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProvisionalLedgerEvent
        fields = [
            "id",
            "event_type",
            "status",
            "command_id",
            "bank_transaction",
            "source_command",
            "subject_content_type",
            "subject_object_id",
            "data",
            "actor",
            "confidence_score",
            "logic_trace_id",
            "rationale",
            "business_profile_constraint",
            "human_in_the_loop",
            "metadata",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CanonicalLedgerProvenanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CanonicalLedgerProvenance
        fields = [
            "id",
            "shadow_event",
            "content_type",
            "object_id",
            "actor",
            "applied_by",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class AIIntegrityReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIIntegrityReport
        fields = [
            "id",
            "period_start",
            "period_end",
            "summary",
            "flagged_items",
            "created_at",
        ]
        read_only_fields = fields
