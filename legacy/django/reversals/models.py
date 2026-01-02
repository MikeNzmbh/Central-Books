from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class Allocation(models.Model):
    class LedgerSide(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer (AR)"
        VENDOR = "VENDOR", "Vendor (AP)"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        VOIDED = "VOIDED", "Voided"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    ledger_side = models.CharField(
        max_length=12,
        choices=LedgerSide.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=8,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    source_object_id = models.PositiveIntegerField()
    source_object = GenericForeignKey("source_content_type", "source_object_id")

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    target_object_id = models.PositiveIntegerField()
    target_object = GenericForeignKey("target_content_type", "target_object_id")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)

    operation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allocations_created",
    )

    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["business", "source_content_type", "source_object_id"]),
            models.Index(fields=["business", "target_content_type", "target_object_id"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="allocation_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.business_id} {self.ledger_side} {self.amount} {self.currency}"


class CustomerCreditMemo(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="customer_credit_memos",
    )
    customer = models.ForeignKey(
        "core.Customer",
        on_delete=models.PROTECT,
        related_name="credit_memos",
    )
    source_invoice = models.ForeignKey(
        "core.Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_memos",
    )
    credit_memo_number = models.CharField(max_length=50, blank=True, default="")
    posting_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    memo = models.TextField(blank=True, default="")
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    tax_group = models.ForeignKey(
        "taxes.TaxGroup",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_credit_memos",
    )

    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default="")

    posted_journal_entry = GenericRelation(
        "core.JournalEntry",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-posting_date", "-id"]
        indexes = [
            models.Index(fields=["business", "customer", "status"]),
            models.Index(fields=["business", "posting_date"]),
        ]

    def __str__(self) -> str:
        label = self.credit_memo_number or f"CM-{self.pk}"
        return f"{label} ({self.customer_id})"


class CustomerDeposit(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="customer_deposits",
    )
    customer = models.ForeignKey(
        "core.Customer",
        on_delete=models.PROTECT,
        related_name="deposits",
    )
    bank_account = models.ForeignKey(
        "core.BankAccount",
        on_delete=models.PROTECT,
        related_name="customer_deposits",
    )
    posting_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    memo = models.TextField(blank=True, default="")

    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default="")

    posted_journal_entry = GenericRelation(
        "core.JournalEntry",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-posting_date", "-id"]
        indexes = [
            models.Index(fields=["business", "customer", "status"]),
            models.Index(fields=["business", "posting_date"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="customerdeposit_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"Deposit {self.amount} {self.currency} ({self.customer_id})"


class CustomerRefund(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="customer_refunds",
    )
    customer = models.ForeignKey(
        "core.Customer",
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    bank_account = models.ForeignKey(
        "core.BankAccount",
        on_delete=models.PROTECT,
        related_name="customer_refunds",
    )
    posting_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    memo = models.TextField(blank=True, default="")

    credit_memo = models.ForeignKey(
        "reversals.CustomerCreditMemo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunds",
    )
    deposit = models.ForeignKey(
        "reversals.CustomerDeposit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunds",
    )

    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default="")

    posted_journal_entry = GenericRelation(
        "core.JournalEntry",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-posting_date", "-id"]
        indexes = [
            models.Index(fields=["business", "customer", "status"]),
            models.Index(fields=["business", "posting_date"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="customerrefund_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"Refund {self.amount} {self.currency} ({self.customer_id})"

