from decimal import Decimal
import datetime

from django.db import migrations


def seed_canadian_tax_groups(apps, schema_editor):
    Business = apps.get_model("core", "Business")
    Account = apps.get_model("core", "Account")
    TaxComponent = apps.get_model("taxes", "TaxComponent")
    TaxGroup = apps.get_model("taxes", "TaxGroup")
    TaxGroupComponent = apps.get_model("taxes", "TaxGroupComponent")

    def ensure_account(business, code, name, acc_type):
        account, created = Account.objects.get_or_create(
            business=business,
            code=code,
            defaults={
                "name": name,
                "type": acc_type,
            },
        )
        if not created:
            updated_fields = []
            if account.name != name:
                account.name = name
                updated_fields.append("name")
            if account.type != acc_type:
                account.type = acc_type
                updated_fields.append("type")
            if updated_fields:
                account.save(update_fields=updated_fields)
        return account

    def ensure_component(
        business,
        name,
        rate,
        authority,
        is_recoverable,
        effective_start_date,
        default_account,
    ):
        component, created = TaxComponent.objects.get_or_create(
            business=business,
            name=name,
            defaults={
                "rate_percentage": rate,
                "authority": authority,
                "is_recoverable": is_recoverable,
                "effective_start_date": effective_start_date,
                "default_coa_account": default_account,
            },
        )
        updated_fields = []
        if component.rate_percentage != rate:
            component.rate_percentage = rate
            updated_fields.append("rate_percentage")
        if component.authority != authority:
            component.authority = authority
            updated_fields.append("authority")
        if component.is_recoverable != is_recoverable:
            component.is_recoverable = is_recoverable
            updated_fields.append("is_recoverable")
        if component.effective_start_date != effective_start_date:
            component.effective_start_date = effective_start_date
            updated_fields.append("effective_start_date")
        if component.default_coa_account_id != default_account.id:
            component.default_coa_account = default_account
            updated_fields.append("default_coa_account")
        if updated_fields:
            component.save(update_fields=updated_fields)
        return component

    def ensure_group(business, display_name, components, calculation_method):
        group, _ = TaxGroup.objects.get_or_create(
            business=business,
            display_name=display_name,
            defaults={
                "is_system_locked": True,
                "calculation_method": calculation_method,
            },
        )
        updated_fields = []
        if not group.is_system_locked:
            group.is_system_locked = True
            updated_fields.append("is_system_locked")
        if group.calculation_method != calculation_method:
            group.calculation_method = calculation_method
            updated_fields.append("calculation_method")
        if updated_fields:
            group.save(update_fields=updated_fields)

        # attach components in order
        desired_components = list(components)
        for order, component in enumerate(desired_components, start=1):
            TaxGroupComponent.objects.update_or_create(
                group=group,
                component=component,
                defaults={"calculation_order": order},
            )
        TaxGroupComponent.objects.filter(group=group).exclude(
            component__in=desired_components
        ).delete()
        return group

    gst_effective_date = datetime.date(2020, 1, 1)
    ns_effective_date = datetime.date(2025, 4, 1)

    for business in Business.objects.all():
        sales_tax_payable = ensure_account(
            business,
            code="2300",
            name="Sales Tax Payable",
            acc_type="LIABILITY",
        )
        recoverable_tax_asset = ensure_account(
            business,
            code="1400",
            name="Recoverable Tax Asset (ITCs)",
            acc_type="ASSET",
        )

        gst_5 = ensure_component(
            business=business,
            name="Federal GST 5%",
            rate=Decimal("0.05"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        on_hst = ensure_component(
            business=business,
            name="Ontario HST 13%",
            rate=Decimal("0.13"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        nb_hst = ensure_component(
            business=business,
            name="New Brunswick HST 15%",
            rate=Decimal("0.15"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        nl_hst = ensure_component(
            business=business,
            name="Newfoundland and Labrador HST 15%",
            rate=Decimal("0.15"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        pe_hst = ensure_component(
            business=business,
            name="Prince Edward Island HST 15%",
            rate=Decimal("0.15"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        ns_hst = ensure_component(
            business=business,
            name="Nova Scotia HST 14%",
            rate=Decimal("0.14"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=ns_effective_date,
            default_account=recoverable_tax_asset,
        )
        bc_pst = ensure_component(
            business=business,
            name="British Columbia PST 7%",
            rate=Decimal("0.07"),
            authority="BC-PST",
            is_recoverable=False,
            effective_start_date=gst_effective_date,
            default_account=sales_tax_payable,
        )
        mb_rst = ensure_component(
            business=business,
            name="Manitoba RST 7%",
            rate=Decimal("0.07"),
            authority="MB-RST",
            is_recoverable=False,
            effective_start_date=gst_effective_date,
            default_account=sales_tax_payable,
        )
        sk_pst = ensure_component(
            business=business,
            name="Saskatchewan PST 6%",
            rate=Decimal("0.06"),
            authority="SK-PST",
            is_recoverable=False,
            effective_start_date=gst_effective_date,
            default_account=sales_tax_payable,
        )
        qc_qst = ensure_component(
            business=business,
            name="Quebec QST 9.975%",
            rate=Decimal("0.09975"),
            authority="RQ",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )

        calculation_method = "SIMPLE"

        ensure_group(
            business,
            display_name="CA-ON HST 13%",
            components=[on_hst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-NB HST 15%",
            components=[nb_hst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-NL HST 15%",
            components=[nl_hst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-PE HST 15%",
            components=[pe_hst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-NS HST 14%",
            components=[ns_hst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-AB GST 5%",
            components=[gst_5],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-YT GST 5%",
            components=[gst_5],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-NT GST 5%",
            components=[gst_5],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-NU GST 5%",
            components=[gst_5],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-BC GST 5% + PST 7%",
            components=[gst_5, bc_pst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-MB GST 5% + RST 7%",
            components=[gst_5, mb_rst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-SK GST 5% + PST 6%",
            components=[gst_5, sk_pst],
            calculation_method=calculation_method,
        )
        ensure_group(
            business,
            display_name="CA-QC GST 5% + QST 9.975% (14.975%)",
            components=[gst_5, qc_qst],
            calculation_method=calculation_method,
        )


def unseed_canadian_tax_groups(apps, schema_editor):
    TaxGroup = apps.get_model("taxes", "TaxGroup")
    TaxComponent = apps.get_model("taxes", "TaxComponent")

    group_names = [
        "CA-ON HST 13%",
        "CA-NB HST 15%",
        "CA-NL HST 15%",
        "CA-PE HST 15%",
        "CA-NS HST 14%",
        "CA-AB GST 5%",
        "CA-YT GST 5%",
        "CA-NT GST 5%",
        "CA-NU GST 5%",
        "CA-BC GST 5% + PST 7%",
        "CA-MB GST 5% + RST 7%",
        "CA-SK GST 5% + PST 6%",
        "CA-QC GST 5% + QST 9.975% (14.975%)",
    ]
    TaxGroup.objects.filter(display_name__in=group_names).delete()

    component_names = [
        "Federal GST 5%",
        "Ontario HST 13%",
        "New Brunswick HST 15%",
        "Newfoundland and Labrador HST 15%",
        "Prince Edward Island HST 15%",
        "Nova Scotia HST 14%",
        "British Columbia PST 7%",
        "Manitoba RST 7%",
        "Saskatchewan PST 6%",
        "Quebec QST 9.975%",
    ]
    TaxComponent.objects.filter(name__in=component_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_business_fiscal_year_start"),
        ("taxes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=seed_canadian_tax_groups,
            reverse_code=unseed_canadian_tax_groups,
        ),
    ]
