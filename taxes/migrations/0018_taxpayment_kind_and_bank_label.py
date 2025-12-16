# Generated migration for TaxPayment kind and bank_account_label fields

from decimal import Decimal
from django.db import migrations, models


def backfill_kind_from_signed_amount(apps, schema_editor):
    """
    Backfill kind field based on existing signed amounts:
    - amount >= 0: keep as PAYMENT
    - amount < 0: set to REFUND and make amount positive
    """
    TaxPayment = apps.get_model("taxes", "TaxPayment")
    for payment in TaxPayment.objects.filter(amount__lt=Decimal("0.00")):
        payment.kind = "REFUND"
        payment.amount = abs(payment.amount)
        payment.save(update_fields=["kind", "amount"])


def reverse_backfill(apps, schema_editor):
    """
    Reverse: convert REFUND back to negative amounts
    """
    TaxPayment = apps.get_model("taxes", "TaxPayment")
    for payment in TaxPayment.objects.filter(kind="REFUND"):
        payment.amount = -abs(payment.amount)
        payment.save(update_fields=["amount"])


class Migration(migrations.Migration):

    dependencies = [
        ("taxes", "0017_taxpayment_bank_account"),
    ]

    operations = [
        migrations.AddField(
            model_name="taxpayment",
            name="kind",
            field=models.CharField(
                choices=[
                    ("PAYMENT", "Payment to tax authority"),
                    ("REFUND", "Refund/credit from tax authority"),
                ],
                default="PAYMENT",
                help_text="PAYMENT = money paid to authority, REFUND = money received from authority.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="taxpayment",
            name="bank_account_label",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Manual bank account label for display when FK is not set.",
                max_length=128,
            ),
        ),
        migrations.RunPython(
            backfill_kind_from_signed_amount,
            reverse_backfill,
        ),
    ]
