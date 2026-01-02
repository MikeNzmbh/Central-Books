from django.contrib import admin

from .models import CompanionInsight, HealthIndexSnapshot, WorkspaceCompanionProfile, WorkspaceMemory


@admin.register(WorkspaceCompanionProfile)
class WorkspaceCompanionProfileAdmin(admin.ModelAdmin):
    list_display = ["workspace", "is_enabled", "enable_health_index", "enable_suggestions", "conservatism_level"]
    readonly_fields = ["created_at", "updated_at"]
    search_fields = ["workspace__name"]


@admin.register(HealthIndexSnapshot)
class HealthIndexSnapshotAdmin(admin.ModelAdmin):
    list_display = ["workspace", "score", "created_at"]
    readonly_fields = ["workspace", "score", "breakdown", "raw_metrics", "created_at"]
    search_fields = ["workspace__name"]
    list_filter = ["created_at"]


@admin.register(CompanionInsight)
class CompanionInsightAdmin(admin.ModelAdmin):
    list_display = ["workspace", "domain", "title", "severity", "is_dismissed", "created_at", "dismissed_at"]
    list_filter = ["severity", "is_dismissed", "domain"]
    search_fields = ["title", "workspace__name"]
    readonly_fields = ["created_at", "dismissed_at"]


@admin.register(WorkspaceMemory)
class WorkspaceMemoryAdmin(admin.ModelAdmin):
    list_display = ["workspace", "key", "last_updated"]
    search_fields = ["workspace__name", "key"]
    readonly_fields = ["last_updated"]
