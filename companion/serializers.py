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

    class Meta:
        model = CompanionSuggestedAction
        fields = [
            "id",
            "action_type",
            "status",
            "confidence",
            "summary",
            "payload",
            "created_at",
            "source_snapshot_id",
        ]
        read_only_fields = fields
