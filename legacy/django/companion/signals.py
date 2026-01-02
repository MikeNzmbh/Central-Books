from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Expense
from .services import remember_vendor_category


@receiver(post_save, sender=Expense)
def capture_expense_vendor_category(sender, instance: Expense, **kwargs):
    if not instance.business_id or not instance.category_id:
        return
    vendor_name = getattr(instance.supplier, "name", None)
    if not vendor_name:
        return
    remember_vendor_category(
        workspace=instance.business,
        vendor_name=vendor_name,
        category_id=instance.category_id,
        expense_id=instance.pk,
    )
