from django.contrib import admin

from .models import TaxAnomaly, TaxJurisdiction, TaxPeriodSnapshot, TaxProductRule, TaxPayment


@admin.register(TaxJurisdiction)
class TaxJurisdictionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "jurisdiction_type", "country_code", "region_code", "sourcing_rule", "is_active")
    list_filter = ("country_code", "jurisdiction_type", "sourcing_rule", "is_active")
    search_fields = ("code", "name", "region_code")


@admin.register(TaxProductRule)
class TaxProductRuleAdmin(admin.ModelAdmin):
    list_display = ("product_code", "jurisdiction", "rule_type", "valid_from", "valid_to")
    list_filter = ("rule_type", "jurisdiction")
    search_fields = ("product_code", "jurisdiction__code")


@admin.register(TaxPeriodSnapshot)
class TaxPeriodSnapshotAdmin(admin.ModelAdmin):
    list_display = ("business", "period_key", "country", "status", "computed_at")
    list_filter = ("status", "country")
    search_fields = ("business__name", "period_key")


@admin.register(TaxAnomaly)
class TaxAnomalyAdmin(admin.ModelAdmin):
    list_display = ("code", "business", "period_key", "severity", "status", "created_at")
    list_filter = ("severity", "status")
    search_fields = ("code", "business__name", "period_key")


@admin.register(TaxPayment)
class TaxPaymentAdmin(admin.ModelAdmin):
    list_display = ("business", "period_key", "payment_date", "amount", "currency", "bank_account", "method", "reference")
    list_filter = ("currency", "method")
    search_fields = ("business__name", "period_key", "reference")
