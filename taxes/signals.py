from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Business
from .bootstrap import seed_canadian_defaults


@receiver(post_save, sender=Business)
def seed_tax_defaults_on_business_create(sender, instance, created, raw, **kwargs):
    if raw or not created:
        return
    seed_canadian_defaults(instance)

