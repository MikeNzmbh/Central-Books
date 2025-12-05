from django.contrib import admin

from .models import TaxRate


admin.site.site_header = "CERN Books – System Admin (Legacy)"
admin.site.site_title = "CERN Books System Admin"


def _superuser_only(request):
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _superuser_only


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "country",
        "region",
        "display_rate",
        "is_active",
        "applies_to_sales",
        "applies_to_purchases",
    )
    list_filter = ("country", "region", "is_active", "applies_to_sales", "applies_to_purchases")
    search_fields = ("name", "code")
    ordering = ("name",)

    @admin.display(description="Rate")
    def display_rate(self, obj):
        return f"{obj.percentage}%"
