from decimal import Decimal
import datetime
from typing import Iterable

from django.db import transaction


def seed_canadian_defaults(business):
    """
    Ensure built-in Canadian tax components and groups exist for the given business.
    Re-runnable and safe to call multiple times.
    """
    from core.models import Account  # imported here to avoid AppConfig import cycles
    from .models import TaxComponent, TaxGroup, TaxGroupComponent, TaxRate

    def ensure_account(code: str, name: str, acc_type: str) -> Account:
        account, created = Account.objects.get_or_create(
            business=business,
            code=code,
            defaults={
                "name": name,
                "type": acc_type,
            },
        )
        updated_fields: list[str] = []
        if not created:
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
        name: str,
        rate: Decimal,
        authority: str,
        is_recoverable: bool,
        effective_start_date: datetime.date,
        default_account: Account,
    ) -> TaxComponent:
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
        updated_fields: list[str] = []
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

    def ensure_rate(
        component: TaxComponent,
        rate: Decimal,
        effective_from: datetime.date,
        product_category: str = "STANDARD",
    ):
        TaxRate.objects.get_or_create(
            component=component,
            product_category=product_category,
            effective_from=effective_from,
            defaults={
                "rate_decimal": rate,
            },
        )

    def ensure_group(
        display_name: str,
        components: Iterable[TaxComponent],
        calculation_method: str,
    ) -> TaxGroup:
        group, _ = TaxGroup.objects.get_or_create(
            business=business,
            display_name=display_name,
            defaults={
                "is_system_locked": True,
                "calculation_method": calculation_method,
            },
        )
        updated_fields: list[str] = []
        if not group.is_system_locked:
            group.is_system_locked = True
            updated_fields.append("is_system_locked")
        if group.calculation_method != calculation_method:
            group.calculation_method = calculation_method
            updated_fields.append("calculation_method")
        if updated_fields:
            group.save(update_fields=updated_fields)

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

    with transaction.atomic():
        sales_tax_payable = ensure_account(
            code="2300",
            name="Sales Tax Payable",
            acc_type="LIABILITY",
        )
        recoverable_tax_asset = ensure_account(
            code="1400",
            name="Recoverable Tax Asset (ITCs)",
            acc_type="ASSET",
        )

        gst_effective_date = datetime.date(2020, 1, 1)
        ns_effective_date = datetime.date(2025, 4, 1)

        gst_5 = ensure_component(
            name="Federal GST 5%",
            rate=Decimal("0.05"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        on_hst = ensure_component(
            name="Ontario HST 13%",
            rate=Decimal("0.13"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        nb_hst = ensure_component(
            name="New Brunswick HST 15%",
            rate=Decimal("0.15"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        nl_hst = ensure_component(
            name="Newfoundland and Labrador HST 15%",
            rate=Decimal("0.15"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        pe_hst = ensure_component(
            name="Prince Edward Island HST 15%",
            rate=Decimal("0.15"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )
        ns_hst = ensure_component(
            name="Nova Scotia HST 14%",
            rate=Decimal("0.14"),
            authority="CRA",
            is_recoverable=True,
            effective_start_date=ns_effective_date,
            default_account=recoverable_tax_asset,
        )
        bc_pst = ensure_component(
            name="British Columbia PST 7%",
            rate=Decimal("0.07"),
            authority="BC-PST",
            is_recoverable=False,
            effective_start_date=gst_effective_date,
            default_account=sales_tax_payable,
        )
        mb_rst = ensure_component(
            name="Manitoba RST 7%",
            rate=Decimal("0.07"),
            authority="MB-RST",
            is_recoverable=False,
            effective_start_date=gst_effective_date,
            default_account=sales_tax_payable,
        )
        sk_pst = ensure_component(
            name="Saskatchewan PST 6%",
            rate=Decimal("0.06"),
            authority="SK-PST",
            is_recoverable=False,
            effective_start_date=gst_effective_date,
            default_account=sales_tax_payable,
        )
        qc_qst = ensure_component(
            name="Quebec QST 9.975%",
            rate=Decimal("0.09975"),
            authority="RQ",
            is_recoverable=True,
            effective_start_date=gst_effective_date,
            default_account=recoverable_tax_asset,
        )

        # Ensure rate rows for all components (used by TaxEngine).
        for component, rate_value, eff_date in [
            (gst_5, Decimal("0.05"), gst_effective_date),
            (on_hst, Decimal("0.13"), gst_effective_date),
            (nb_hst, Decimal("0.15"), gst_effective_date),
            (nl_hst, Decimal("0.15"), gst_effective_date),
            (pe_hst, Decimal("0.15"), gst_effective_date),
            (ns_hst, Decimal("0.14"), ns_effective_date),
            (bc_pst, Decimal("0.07"), gst_effective_date),
            (mb_rst, Decimal("0.07"), gst_effective_date),
            (sk_pst, Decimal("0.06"), gst_effective_date),
            (qc_qst, Decimal("0.09975"), gst_effective_date),
        ]:
            ensure_rate(component, rate_value, eff_date)

        calculation_method = "SIMPLE"

        ensure_group("CA-ON HST 13%", [on_hst], calculation_method)
        ensure_group("CA-NB HST 15%", [nb_hst], calculation_method)
        ensure_group("CA-NL HST 15%", [nl_hst], calculation_method)
        ensure_group("CA-PE HST 15%", [pe_hst], calculation_method)
        ensure_group("CA-NS HST 14%", [ns_hst], calculation_method)
        ensure_group("CA-AB GST 5%", [gst_5], calculation_method)
        ensure_group("CA-YT GST 5%", [gst_5], calculation_method)
        ensure_group("CA-NT GST 5%", [gst_5], calculation_method)
        ensure_group("CA-NU GST 5%", [gst_5], calculation_method)
        ensure_group("CA-BC GST 5% + PST 7%", [gst_5, bc_pst], calculation_method)
        ensure_group("CA-MB GST 5% + RST 7%", [gst_5, mb_rst], calculation_method)
        ensure_group("CA-SK GST 5% + PST 6%", [gst_5, sk_pst], calculation_method)
        ensure_group(
            "CA-QC GST 5% + QST 9.975% (14.975%)",
            [gst_5, qc_qst],
            calculation_method,
        )
