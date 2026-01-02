"""
Django signals to mark Companion story dirty when data changes.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import BankTransaction, Business, Expense, Invoice, ReceiptDocument, ReceiptRun, WorkspaceMembership

logger = logging.getLogger(__name__)


def _mark_dirty(instance) -> None:
    """Helper to mark story dirty for an instance's business."""
    # Import here to avoid circular imports
    from core.companion_story import mark_story_dirty
    
    business = getattr(instance, "business", None)
    if business:
        mark_story_dirty(business)


# Invoice changes
@receiver(post_save, sender=Invoice)
def invoice_saved(sender, instance, **kwargs):
    _mark_dirty(instance)


@receiver(post_delete, sender=Invoice)
def invoice_deleted(sender, instance, **kwargs):
    _mark_dirty(instance)


# Expense changes
@receiver(post_save, sender=Expense)
def expense_saved(sender, instance, **kwargs):
    _mark_dirty(instance)


@receiver(post_delete, sender=Expense)
def expense_deleted(sender, instance, **kwargs):
    _mark_dirty(instance)


# Receipt run changes (agentic receipt processing)
@receiver(post_save, sender=ReceiptRun)
def receipt_run_saved(sender, instance, **kwargs):
    _mark_dirty(instance)


@receiver(post_save, sender=ReceiptDocument)
def receipt_document_saved(sender, instance, **kwargs):
    # ReceiptDocument has run.business
    run = getattr(instance, "run", None)
    if run:
        business = getattr(run, "business", None)
        if business:
            from core.companion_story import mark_story_dirty
            mark_story_dirty(business)


# Bank transaction changes
@receiver(post_save, sender=BankTransaction)
def bank_transaction_saved(sender, instance, **kwargs):
    _mark_dirty(instance)


@receiver(post_delete, sender=BankTransaction)
def bank_transaction_deleted(sender, instance, **kwargs):
    _mark_dirty(instance)


@receiver(post_save, sender=Business)
def ensure_owner_membership(sender, instance: Business, created: bool, **kwargs):
    """
    RBAC v2 requires an explicit WorkspaceMembership row to evaluate permissions.

    Keep the owner's membership present and set to OWNER.
    """
    owner_id = getattr(instance, "owner_user_id", None)
    if not owner_id:
        return
    membership, created_membership = WorkspaceMembership.objects.get_or_create(
        user_id=owner_id,
        business_id=instance.id,
        defaults={"role": WorkspaceMembership.RoleChoices.OWNER, "is_active": True},
    )
    if not created_membership and (
        membership.role != WorkspaceMembership.RoleChoices.OWNER or not membership.is_active
    ):
        WorkspaceMembership.objects.filter(id=membership.id).update(
            role=WorkspaceMembership.RoleChoices.OWNER,
            is_active=True,
        )
