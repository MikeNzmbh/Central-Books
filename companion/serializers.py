from rest_framework import serializers

from .models import CompanionInsight, CompanionSuggestedAction, HealthIndexSnapshot


class HealthIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthIndexSnapshot
        fields = ["score", "breakdown", "raw_metrics", "created_at"]
        read_only_fields = fields


class CompanionInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanionInsight
        fields = [
            "id",
            "context",
            "domain",
            "title",
            "body",
            "severity",
            "suggested_actions",
            "created_at",
        ]
        read_only_fields = fields


class CompanionSuggestedActionSerializer(serializers.ModelSerializer):
    confidence = serializers.DecimalField(max_digits=8, decimal_places=4)
    payload = serializers.JSONField()
    impact = serializers.SerializerMethodField()

    class Meta:
        model = CompanionSuggestedAction
        fields = [
            "id",
            "context",
            "action_type",
            "status",
            "confidence",
            "summary",
            "short_title",
            "severity",
            "payload",
            "created_at",
            "source_snapshot_id",
            "impact",
        ]
        read_only_fields = fields

    def get_impact(self, obj):
        payload = obj.payload or {}
        return payload.get("impact")
