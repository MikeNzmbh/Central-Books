from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from types import SimpleNamespace

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone

if TYPE_CHECKING:
    from django.db.models import Manager


class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    currency = models.CharField(max_length=3)
    fiscal_year_start = models.CharField(max_length=5, default="01-01")
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="businesses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    bank_setup_completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner_user"],
                name="uniq_business_per_owner",
            ),
        ]

    def __str__(self):
        return self.name


class Customer(models.Model):
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="customers",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="uniq_customer_per_business_name",
            )
        ]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="suppliers",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="uniq_supplier_per_business_name",
            )
        ]

    def __str__(self):
        return self.name


class TaxRate(models.Model):
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="tax_rates",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_recoverable = models.BooleanField(default=True)
    is_default_sales = models.BooleanField(default=False)
    is_default_purchases = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    country = models.CharField(max_length=2, default="CA")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                name="unique_tax_code_per_business",
            ),
            models.UniqueConstraint(
                fields=["business"],
                condition=Q(is_default_sales=True),
                name="unique_default_sales_tax",
            ),
            models.UniqueConstraint(
                fields=["business"],
                condition=Q(is_default_purchases=True),
                name="unique_default_purchase_tax",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"

    @classmethod
    def ensure_defaults(cls, business):
        if not business:
            return
        cls.objects.get_or_create(
            business=business,
            code="NONE",
            defaults={
                "name": "No tax",
                "percentage": Decimal("0.00"),
                "is_recoverable": False,
                "is_default_purchases": True,
            },
        )
        cls.objects.get_or_create(
            business=business,
            code="GST13",
            defaults={
                "name": "GST/HST 13%",
                "percentage": Decimal("13.00"),
                "is_recoverable": True,
                "is_default_sales": True,
            },
        )

    @property
    def amount_owed(self):
        cached = getattr(self, "_amount_owed_cache", None)
        if cached is not None:
            return cached

        from .models import Expense

        total = (
            Expense.objects.filter(
                supplier=self,
                status=Expense.Status.UNPAID,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        self._amount_owed_cache = total
        return total

    @property
    def ytd_spend(self):
        cached = getattr(self, "_ytd_spend_cache", None)
        if cached is not None:
            return cached

        from .models import Expense

        current_year = timezone.now().year
        total = (
            Expense.objects.filter(
                supplier=self,
                status=Expense.Status.PAID,
                date__year=current_year,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        self._ytd_spend_cache = total
        return total

    if TYPE_CHECKING:
        expenses: Manager["Expense"]
        mtd_spend: Decimal
        default_category_name: Optional[str]
        initials: str
        open_balance: Decimal
        _ytd_spend_cache: Decimal


class Account(models.Model):
    class AccountType(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"
        EQUITY = "EQUITY", "Equity"
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    code = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional short code like 1010, 4010, etc.",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=10,
        choices=AccountType.choices,
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
        help_text="Optional parent for grouping (e.g. 'Expenses' → 'Software').",
    )
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    is_favorite = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        ordering = ["type", "code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                name="unique_account_code_per_business",
            )
        ]

    def __str__(self):
        return f"{self.code} – {self.name}" if self.code else self.name


class Category(models.Model):
    class CategoryType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    type = models.CharField(
        max_length=10,
        choices=CategoryType.choices,
        default=CategoryType.EXPENSE,
    )
    code = models.CharField(max_length=32, blank=True)
    description = models.TextField(blank=True)
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="categories",
        null=True,
        blank=True,
        help_text="Underlying accounting account for this category.",
    )
    is_archived = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Categories"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name", "type"],
                name="uniq_category_name_type_per_business",
            )
        ]

    def __str__(self):
        return self.name


class Item(models.Model):
    class ItemType(models.TextChoices):
        PRODUCT = "PRODUCT", "Product"
        SERVICE = "SERVICE", "Service"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="items",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.SERVICE,
    )
    sku = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional SKU or internal code.",
    )
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    income_category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
        limit_choices_to={"type": Category.CategoryType.INCOME},
    )
    income_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="items_income",
        limit_choices_to={"type": Account.AccountType.INCOME},
    )
    expense_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="items_expense",
        limit_choices_to={"type": Account.AccountType.EXPENSE},
    )
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product / Service"
        verbose_name_plural = "Products & Services"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="unique_item_name_per_business",
            )
        ]

    def __str__(self):
        return self.name


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"
        VOID = "VOID", "Void"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=50)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    description = models.TextField(blank=True, help_text="Items or services rendered.")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True,
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True,
    )
    tax_rate = models.ForeignKey(
        "core.TaxRate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    net_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    grand_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Product / service",
    )
    tax_group = models.ForeignKey(
        "taxes.TaxGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices",
    )
    posted_journal_entry = GenericRelation(
        "core.JournalEntry",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "invoice_number"],
                name="uniq_invoice_number_per_business",
            )
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status
        self._skip_tax_sync = False

    def recalc_totals(self):
        net = self.total_amount or Decimal("0.00")
        self.subtotal = net
        tax = self.tax_amount or Decimal("0.00")

        if self.tax_group_id:
            from taxes.services import TaxEngine

            currency = getattr(self.business, "currency", "CAD") or "CAD"
            fx_rate = Decimal("1.00")
            result = TaxEngine.calculate_for_line(
                business=self.business,
                transaction_line=SimpleNamespace(net_amount=net),
                tax_group=self.tax_group,
                txn_date=self.issue_date or timezone.now().date(),
                currency=currency,
                fx_rate=fx_rate,
                persist=False,
            )
            tax_txn = result["total_tax_txn_currency"]
            tax = tax_txn
            self.tax_amount = tax_txn
            self.tax_total = tax_txn
        elif self.tax_rate and self.tax_rate.percentage:
            tax = (net * (self.tax_rate.percentage / Decimal("100"))).quantize(Decimal("0.01"))
            self.tax_total = tax
        else:
            self.tax_total = tax

        self.tax_amount = tax
        self.net_total = net
        self.grand_total = net + tax
        self._recalc_payment_state()

    def _recalc_payment_state(self):
        total = self.grand_total or (self.net_total + self.tax_total)
        paid = self.amount_paid or Decimal("0.00")
        if self.status == self.Status.PAID and paid < total:
            paid = total
        paid = max(Decimal("0.00"), min(paid, total))
        self.amount_paid = paid
        self.balance = total - paid
        if self.status == self.Status.VOID:
            return
        if paid == 0:
            if self.status != self.Status.DRAFT:
                self.status = self.Status.SENT
        elif self.balance == 0:
            self.status = self.Status.PAID
        else:
            self.status = self.Status.PARTIAL

    def save(self, *args, **kwargs):
        self.recalc_totals()
        super().save(*args, **kwargs)

        if not self._skip_tax_sync:
            self._sync_tax_details()

        from .accounting_posting import (
            post_invoice_sent,
            post_invoice_paid,
            remove_invoice_sent_entry,
            remove_invoice_paid_entry,
        )

        prev_status = getattr(self, "_original_status", None)

        if self.status in (self.Status.SENT, self.Status.PAID):
            post_invoice_sent(self)
        elif prev_status in (self.Status.SENT, self.Status.PAID):
            remove_invoice_sent_entry(self)

        if self.status == self.Status.PAID:
            post_invoice_paid(self)
        elif prev_status == self.Status.PAID:
            remove_invoice_paid_entry(self)

        self._original_status = self.status

    @property
    def net_amount(self) -> Decimal:
        return self.net_total or self.amount or Decimal("0.00")

    def _sync_tax_details(self):
        """
        Refresh TransactionLineTaxDetail rows after save to keep postings aligned.
        """
        from django.contrib.contenttypes.models import ContentType
        from taxes.models import TransactionLineTaxDetail
        from taxes.services import TaxEngine

        ct = ContentType.objects.get_for_model(self.__class__)
        TransactionLineTaxDetail.objects.filter(
            business=self.business,
            transaction_line_content_type=ct,
            transaction_line_object_id=self.pk,
        ).delete()

        if not self.tax_group_id:
            return

        currency = getattr(self.business, "currency", "CAD") or "CAD"
        fx_rate = Decimal("1.00")
        # Persist details; totals already applied to fields during recalc.
        TaxEngine.calculate_for_line(
            business=self.business,
            transaction_line=self,
            tax_group=self.tax_group,
            txn_date=self.issue_date or timezone.now().date(),
            currency=currency,
            fx_rate=fx_rate,
            persist=True,
        )

    def delete(self, *args, **kwargs):
        from .accounting_posting import remove_invoice_sent_entry, remove_invoice_paid_entry

        remove_invoice_sent_entry(self)
        remove_invoice_paid_entry(self)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} – {self.customer.name}"


class Expense(models.Model):
    class Status(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        related_name="expenses",
        blank=True,
        null=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="expenses",
        blank=True,
        null=True,
    )
    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.UNPAID,
    )
    paid_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True,
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
        null=True,
    )
    tax_rate = models.ForeignKey(
        "core.TaxRate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    tax_group = models.ForeignKey(
        "taxes.TaxGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses",
    )
    posted_journal_entry = GenericRelation(
        "core.JournalEntry",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
    )
    net_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    grand_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["-date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status
        self._skip_tax_sync = False

    def recalc_totals(self):
        net = self.amount or Decimal("0.00")
        self.subtotal = net
        tax = self.tax_amount or Decimal("0.00")
        if self.tax_group_id:
            from taxes.services import TaxEngine

            currency = getattr(self.business, "currency", "CAD") or "CAD"
            fx_rate = Decimal("1.00")
            result = TaxEngine.calculate_for_line(
                business=self.business,
                transaction_line=SimpleNamespace(net_amount=net),
                tax_group=self.tax_group,
                txn_date=self.date or timezone.now().date(),
                currency=currency,
                fx_rate=fx_rate,
                persist=False,
            )
            tax = result["total_tax_txn_currency"]
        elif self.tax_rate and self.tax_rate.percentage:
            tax = (net * (self.tax_rate.percentage / Decimal("100"))).quantize(Decimal("0.01"))
        self.tax_amount = tax
        self.net_total = net
        self.tax_total = tax
        self.grand_total = net + tax
        self._recalc_payment_state()

    def _recalc_payment_state(self):
        total = self.grand_total or (self.net_total + self.tax_total)
        paid = self.amount_paid or Decimal("0.00")
        if self.status == self.Status.PAID and paid < total:
            paid = total
        paid = max(Decimal("0.00"), min(paid, total))
        self.amount_paid = paid
        self.balance = total - paid
        if self.status == self.Status.UNPAID and paid > 0:
            self.status = self.Status.PARTIAL
        if self.balance == 0 and paid >= total:
            self.status = self.Status.PAID
        elif self.balance == total and paid == 0:
            self.status = self.Status.UNPAID
        elif paid > 0 and self.balance > 0:
            self.status = self.Status.PARTIAL

    def mark_paid(self, paid_on=None):
        self.status = self.Status.PAID
        self.paid_date = paid_on or timezone.now().date()
        total = self.grand_total or (self.net_total + self.tax_total)
        self.amount_paid = total
        self.balance = Decimal("0.00")

    def mark_unpaid(self):
        self.status = self.Status.UNPAID
        self.paid_date = None
        self.amount_paid = Decimal("0.00")
        total = self.grand_total or (self.net_total + self.tax_total)
        self.balance = total

    def save(self, *args, **kwargs):
        self.recalc_totals()
        super().save(*args, **kwargs)

        if not self._skip_tax_sync:
            self._sync_tax_details()

        from .accounting_posting import remove_expense_entry
        from .accounting_posting_expenses import post_expense_paid

        prev_status = getattr(self, "_original_status", None)

        if self.status == self.Status.PAID:
            post_expense_paid(self)
        elif prev_status == self.Status.PAID:
            remove_expense_entry(self)

        self._original_status = self.status

    def delete(self, *args, **kwargs):
        from .accounting_posting import remove_expense_entry

        if self.status == self.Status.PAID:
            remove_expense_entry(self)
        return super().delete(*args, **kwargs)

    @property
    def gross_amount(self) -> Decimal:
        return self.grand_total or (self.net_total + self.tax_total)

    @property
    def net_amount(self) -> Decimal:
        return self.net_total or self.total_amount or Decimal("0.00")

    def _sync_tax_details(self):
        """
        Refresh TransactionLineTaxDetail rows after save to keep postings aligned.
        """
        from django.contrib.contenttypes.models import ContentType
        from taxes.models import TransactionLineTaxDetail
        from taxes.services import TaxEngine

        ct = ContentType.objects.get_for_model(self.__class__)
        TransactionLineTaxDetail.objects.filter(
            business=self.business,
            transaction_line_content_type=ct,
            transaction_line_object_id=self.pk,
        ).delete()

        if not self.tax_group_id:
            return

        currency = getattr(self.business, "currency", "CAD") or "CAD"
        fx_rate = Decimal("1.00")
        # Persist details; totals already applied to fields during recalc.
        TaxEngine.calculate_for_line(
            business=self.business,
            transaction_line=self,
            tax_group=self.tax_group,
            txn_date=self.date or timezone.now().date(),
            currency=currency,
            fx_rate=fx_rate,
            persist=True,
        )

    def __str__(self):
        return f"{self.date} – {self.description} – {self.amount}"

    if TYPE_CHECKING:
        journalentry_set: Manager["JournalEntry"]


class JournalEntry(models.Model):
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=255)
    is_void = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey("source_content_type", "source_object_id")
    allocation_operation_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["allocation_operation_id"],
                condition=models.Q(allocation_operation_id__isnull=False),
                name="unique_allocation_operation_id",
            )
        ]

    def check_balance(self):
        totals = self.lines.aggregate(
            total_debit=models.Sum("debit"),
            total_credit=models.Sum("credit"),
        )
        total_debit = totals["total_debit"] or Decimal("0.00")
        total_credit = totals["total_credit"] or Decimal("0.00")
        if total_debit != total_credit:
            raise ValidationError(
                f"Unbalanced journal entry (debits={total_debit}, credits={total_credit})."
            )
        if total_debit == Decimal("0.00"):
            raise ValidationError("Journal entry has no value.")

    def __str__(self):
        return f"{self.date} – {self.description}"

    if TYPE_CHECKING:
        id: int
        lines: Manager["JournalLine"]


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    debit = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    credit = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    description = models.CharField(max_length=255, blank=True)
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_session = models.ForeignKey(
        "core.ReconciliationSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_lines",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="jl_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(debit=0) | models.Q(credit=0),
                name="jl_single_side",
            ),
        ]


class BankAccount(models.Model):
    """
    Real-world bank / wallet / card metadata used by the Bank Feed & CSV imports.
    Ledger linking remains optional until bank rec connects to the COA.
    """

    class UsageRole(models.TextChoices):
        OPERATING = "OPERATING", "Operating / checking"
        SAVINGS = "SAVINGS", "Savings"
        CREDIT_CARD = "CREDIT_CARD", "Credit card"
        WALLET = "WALLET", "Payment wallet"
        OTHER = "OTHER", "Other"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="bank_accounts",
    )
    name = models.CharField(
        max_length=255,
        help_text="e.g. 'RBC Business Checking'",
    )
    bank_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. 'RBC', 'TD', 'Wise'",
    )
    account_number_mask = models.CharField(
        max_length=4,
        blank=True,
        help_text="Last 4 digits, e.g. '1234'",
    )
    usage_role = models.CharField(
        max_length=20,
        choices=UsageRole.choices,
        default=UsageRole.OPERATING,
        help_text="How you use this account in your business.",
    )
    account = models.OneToOneField(
        "core.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_account",
        help_text="Ledger account used for balances (optional in v1).",
    )
    is_active = models.BooleanField(default=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("business", "name")]
        ordering = ["name"]

    def __str__(self):
        mask = f" ••••{self.account_number_mask}" if self.account_number_mask else ""
        return f"{self.name}{mask}"

    @property
    def current_balance(self):
        from .ledger_services import get_account_balance  # local import to avoid circular

        if not self.account:
            return Decimal("0.00")
        return get_account_balance(self.account)

    if TYPE_CHECKING:
        id: int
        account_id: Optional[int]
        bank_transactions: Manager["BankTransaction"]
        imports: Manager["BankStatementImport"]


class BankStatementImport(models.Model):
    class ImportStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class FileFormat(models.TextChoices):
        GENERIC_DATE_DESC_AMOUNT = (
            "GENERIC_DATE_DESC_AMOUNT",
            "Generic: Date, Description, Amount",
        )
        GENERIC_DATE_DESC_DEBIT_CREDIT = (
            "GENERIC_DATE_DESC_DEBIT_CREDIT",
            "Generic: Date, Description, Debit/Credit",
        )

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="imports",
    )
    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="bank_imports",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_imports",
    )
    file = models.FileField(upload_to="bank_imports/")
    file_format = models.CharField(
        max_length=50,
        choices=FileFormat.choices,
        default=FileFormat.GENERIC_DATE_DESC_AMOUNT,
    )
    status = models.CharField(
        max_length=20,
        choices=ImportStatus.choices,
        default=ImportStatus.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.bank_account.name} import @ {self.uploaded_at:%Y-%m-%d %H:%M}"


class BankTransaction(models.Model):
    class TransactionStatus(models.TextChoices):
        NEW = "NEW", "New"
        SUGGESTED = "SUGGESTED", "Suggested"
        PARTIAL = "PARTIAL", "Partially allocated"
        MATCHED_SINGLE = "MATCHED_SINGLE", "Matched (single)"
        MATCHED_MULTI = "MATCHED_MULTI", "Matched (split)"
        LEGACY_CREATED = "LEGACY_CREATED", "Created (legacy)"
        MATCHED = "MATCHED", "Matched"
        RECONCILED = "RECONCILED", "Reconciled"
        EXCLUDED = "EXCLUDED", "Excluded"

    RECO_STATUS_UNRECONCILED = "unreconciled"
    RECO_STATUS_RECONCILED = "reconciled"

    RECONCILIATION_STATUS_CHOICES = [
        (RECO_STATUS_UNRECONCILED, "Unreconciled"),
        (RECO_STATUS_RECONCILED, "Reconciled"),
    ]

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="bank_transactions",
    )
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=512)
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        help_text="Positive = deposit, negative = withdrawal",
    )
    allocated_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Total amount allocated via reconciliation matches.",
    )
    external_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )
    normalized_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Hash for deduplication (date + amount + description)",
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.NEW,
        db_index=True,
    )
    suggestion_confidence = models.IntegerField(
        null=True,
        blank=True,
        help_text="0-100 confidence score from suggestion engine",
    )
    suggestion_reason = models.TextField(
        blank=True,
        help_text="Explanation for the suggestion",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matched_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_bank_transactions",
    )
    matched_expense = models.ForeignKey(
        Expense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_bank_transactions",
    )
    posted_journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_bank_transactions",
    )
    is_reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_status = models.CharField(
        max_length=20,
        choices=RECONCILIATION_STATUS_CHOICES,
        default=RECO_STATUS_UNRECONCILED,
        db_index=True,
    )
    reconciliation_session = models.ForeignKey(
        "core.ReconciliationSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_transactions",
    )

    class Meta:
        unique_together = ("bank_account", "external_id")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date} – {self.description}"

    if TYPE_CHECKING:
        id: int
        posted_journal_entry_id: Optional[int]
        expense_candidates: list["Expense"]
        invoice_candidates: list["Invoice"]
        matches: Manager["BankReconciliationMatch"]


class BankReconciliationMatch(models.Model):
    """
    Links bank transactions to journal entries during reconciliation.
    Supports one-to-one, one-to-many, and many-to-many matching patterns.
    """

    MATCH_TYPE_CHOICES = [
        ("ONE_TO_ONE", "One bank transaction to one journal entry"),
        ("ONE_TO_MANY", "One bank transaction split across multiple entries"),
        ("MANY_TO_ONE", "Multiple bank transactions to one entry"),
        ("MANY_TO_MANY", "Complex multi-to-multi match"),
    ]

    # Core relationships
    bank_transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="bank_matches",
    )

    # Match metadata
    match_type = models.CharField(
        max_length=20,
        choices=MATCH_TYPE_CHOICES,
        default="ONE_TO_ONE",
    )
    match_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="0.00 to 1.00, where 1.00 is deterministic match",
    )
    matched_amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        help_text="Absolute value allocated from the bank transaction.",
    )

    # Adjustments (for fees, FX differences, etc.)
    adjustment_journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_match_adjustments",
        help_text="Optional adjustment entry for fees or FX discrepancies",
    )

    # Audit trail
    reconciled_at = models.DateTimeField(auto_now_add=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_reconciliations",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reconciled_at", "id"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(matched_amount__gt=0),
                name="brm_amount_positive",
            ),
            models.CheckConstraint(
                check=models.Q(match_confidence__gte=0) & models.Q(match_confidence__lte=1),
                name="brm_confidence_range",
            ),
        ]
        indexes = [
            models.Index(fields=["bank_transaction", "reconciled_at"]),
            models.Index(fields=["journal_entry"]),
        ]

    def __str__(self):
        return f"{self.bank_transaction_id} → {self.journal_entry_id} ({self.matched_amount})"


class ReconciliationSession(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="reconciliation_sessions",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="reconciliation_sessions",
    )
    statement_start_date = models.DateField()
    statement_end_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    closing_balance = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0.0000"))
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-statement_end_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "statement_start_date", "statement_end_date"],
                name="uniq_reco_session_per_period",
            )
        ]

    def __str__(self):
        return f"{self.bank_account.name} {self.statement_start_date} – {self.statement_end_date}"


class BankRule(models.Model):
    """
    Rule for recurring merchant categorizations during reconciliation.
    """

    business = models.ForeignKey(
        "core.Business",
        on_delete=models.CASCADE,
        related_name="bank_rules",
    )
    merchant_name = models.CharField(max_length=255, help_text="Name to display/match")
    pattern = models.CharField(max_length=255, default="", help_text="Regex or substring to match description")
    
    # Actions
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_rules",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_rules",
    )
    auto_confirm = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_rules_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "merchant_name")
        ordering = ["merchant_name"]

    def __str__(self):
        return f"{self.merchant_name} ({self.business_id})"
