from decimal import Decimal
from datetime import datetime

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
    Account,
    Business,
    Category,
    Customer,
    Expense,
    Invoice,
    Supplier,
    Item,
    BankAccount,
    BankStatementImport,
    TaxRate,
)
from taxes.models import TaxGroup
from .utils import get_current_business


CURRENCY_CHOICES = [
    ("USD", "USD"),
    ("EUR", "EUR"),
    ("RWF", "RWF"),
    ("CAD", "CAD"),
]


class SignupForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        pwd = (cleaned.get("password") or "").strip()
        pwd2 = (cleaned.get("password_confirm") or "").strip()
        if pwd != pwd2:
            self.add_error("password_confirm", "Passwords do not match.")
        if len(pwd) < 8:
            self.add_error("password", "Password must be at least 8 characters.")
        return cleaned


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Another user already uses this email.")
        return email


class BusinessForm(forms.ModelForm):
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES)

    class Meta:
        model = Business
        fields = ["name", "currency", "fiscal_year_start"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("Business name is required.")
        return name

    def clean_fiscal_year_start(self):
        value = (self.cleaned_data.get("fiscal_year_start") or "").strip()
        if not value:
            raise ValidationError("Financial year start is required.")
        try:
            datetime.strptime(value, "%m-%d")
        except ValueError:
            raise ValidationError("Use MM-DD format, e.g. 01-01 for January 1.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")

        if self.user and not self.instance.pk:
            existing = get_current_business(self.user)
            if existing is not None:
                raise ValidationError("You already have a business linked to this account.")

        if name:
            qs = Business.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "A business with this name already exists. Please choose a different name."
                )
        return cleaned_data


class BusinessProfileForm(forms.ModelForm):
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES)

    class Meta:
        model = Business
        fields = ["name", "currency", "fiscal_year_start"]

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("Business name is required.")
        qs = Business.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Another business already uses this name.")
        return name

    def clean_fiscal_year_start(self):
        value = (self.cleaned_data.get("fiscal_year_start") or "").strip()
        if not value:
            raise ValidationError("Financial year start is required.")
        try:
            datetime.strptime(value, "%m-%d")
        except ValueError:
            raise ValidationError("Use MM-DD format, e.g. 01-01 for January 1.")
        return value


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "is_active"]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")

        if self.business and name:
            qs = Customer.objects.filter(business=self.business, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "A customer with this name already exists for your business."
                )
        return cleaned_data


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "email", "phone"]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")

        if self.business and name:
            qs = Supplier.objects.filter(business=self.business, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "A supplier with this name already exists for your business."
                )
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "type", "code", "description", "account"]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self.business and "account" in self.fields:
            self.fields["account"].queryset = Account.objects.filter(business=self.business)

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        type_ = cleaned_data.get("type")

        if self.business and name and type_:
            qs = Category.objects.filter(
                business=self.business,
                name__iexact=name,
                type=type_,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "This category already exists for your business."
                )
        return cleaned_data


class InvoiceForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=Item.objects.all(),
        required=False,
        label="Product / service",
        empty_label="Select product or service",
    )
    tax_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label="Tax amount",
    )

    tax_rate = forms.ModelChoiceField(
        queryset=TaxRate.objects.none(),
        required=False,
        label="Tax rate",
        empty_label="Select tax rate",
    )
    tax_group = forms.ModelChoiceField(
        queryset=TaxGroup.objects.none(),
        required=False,
        label="Tax group",
        empty_label="Select tax group",
    )

    class Meta:
        model = Invoice
        fields = [
            "customer",
            "invoice_number",
            "issue_date",
            "due_date",
            "item",
            "description",
            "total_amount",
            "tax_amount",
            "tax_rate",
            "tax_group",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self.business:
            TaxRate.ensure_defaults(self.business)
            self.fields["customer"].queryset = Customer.objects.filter(
                business=self.business
            )
            self.fields["item"].queryset = Item.objects.filter(
                business=self.business, is_archived=False
            )
            tax_qs = TaxRate.objects.filter(business=self.business, is_active=True).order_by("name")
            self.fields["tax_rate"].queryset = tax_qs
            if not self.instance.pk:
                default_rate = tax_qs.filter(is_default_sales=True).first()
                if default_rate:
                    self.fields["tax_rate"].initial = default_rate.pk
            self.fields["tax_group"].queryset = TaxGroup.objects.filter(business=self.business).order_by(
                "display_name"
            )

    def clean_customer(self):
        customer = self.cleaned_data.get("customer")
        if self.business and customer and customer.business_id != self.business.id:
            raise ValidationError("This customer does not belong to your current business.")
        return customer

    def clean_tax_amount(self):
        value = self.cleaned_data.get("tax_amount")
        tax_rate = self.cleaned_data.get("tax_rate")
        tax_group = self.cleaned_data.get("tax_group")
        if tax_rate or tax_group:
            return Decimal("0.00")
        if value is None:
            value = Decimal("0.00")
        if value < 0:
            raise ValidationError("Tax amount cannot be negative.")
        return value

    def clean_tax_rate(self):
        rate = self.cleaned_data.get("tax_rate")
        if rate and self.business and rate.business_id != self.business.id:
            raise ValidationError("Invalid tax rate for this business.")
        return rate

    def clean_tax_group(self):
        group = self.cleaned_data.get("tax_group")
        if group and self.business and group.business_id != self.business.id:
            raise ValidationError("Invalid tax group for this business.")
        return group


class ExpenseForm(forms.ModelForm):
    tax_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label="Tax amount",
    )
    tax_rate = forms.ModelChoiceField(
        queryset=TaxRate.objects.none(),
        required=False,
        label="Tax rate",
        empty_label="Select tax rate",
    )
    tax_group = forms.ModelChoiceField(
        queryset=TaxGroup.objects.none(),
        required=False,
        label="Tax group",
        empty_label="Select tax group",
    )

    class Meta:
        model = Expense
        fields = [
            "supplier",
            "category",
            "date",
            "description",
            "amount",
            "tax_amount",
            "tax_rate",
            "tax_group",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self.business:
            TaxRate.ensure_defaults(self.business)
            self.fields["supplier"].queryset = Supplier.objects.filter(
                business=self.business
            )
            self.fields["category"].queryset = Category.objects.filter(
                business=self.business, type=Category.CategoryType.EXPENSE
            )
            tax_qs = TaxRate.objects.filter(business=self.business, is_active=True).order_by("name")
            self.fields["tax_rate"].queryset = tax_qs
            if not self.instance.pk:
                default_rate = tax_qs.filter(is_default_purchases=True).first()
                if default_rate:
                    self.fields["tax_rate"].initial = default_rate.pk
            self.fields["tax_group"].queryset = TaxGroup.objects.filter(business=self.business).order_by(
                "display_name"
            )

    def clean_tax_amount(self):
        value = self.cleaned_data.get("tax_amount")
        tax_rate = self.cleaned_data.get("tax_rate")
        tax_group = self.cleaned_data.get("tax_group")
        if tax_rate or tax_group:
            return Decimal("0.00")
        if value is None:
            value = Decimal("0.00")
        if value < 0:
            raise ValidationError("Tax amount cannot be negative.")
        return value

    def clean_tax_rate(self):
        rate = self.cleaned_data.get("tax_rate")
        if rate and self.business and rate.business_id != self.business.id:
            raise ValidationError("Invalid tax rate for this business.")
        return rate

    def clean_tax_group(self):
        group = self.cleaned_data.get("tax_group")
        if group and self.business and group.business_id != self.business.id:
            raise ValidationError("Invalid tax group for this business.")
        return group


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "name",
            "type",
            "income_category",
            "income_account",
            "expense_account",
            "unit_price",
            "sku",
            "description",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if self.business is not None and "income_category" in self.fields:
            self.fields["income_category"].queryset = Category.objects.filter(
                business=self.business,
                type=Category.CategoryType.INCOME,
                is_archived=False,
            )
        if self.business is not None and "income_account" in self.fields:
            self.fields["income_account"].queryset = Account.objects.filter(
                business=self.business,
                type=Account.AccountType.INCOME,
                is_active=True,
            )
        if self.business is not None and "expense_account" in self.fields:
            self.fields["expense_account"].queryset = Account.objects.filter(
                business=self.business,
                type=Account.AccountType.EXPENSE,
                is_active=True,
            )
        self.fields["name"].label = "Item name"
        if "unit_price" in self.fields:
            self.fields["unit_price"].label = "Default price"
        if "income_category" in self.fields:
            self.fields["income_category"].label = "Default income category"
        if "is_active" in self.fields:
            self.fields["is_active"].widget = forms.HiddenInput()

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("Item name is required.")
        return name

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("name")

        if self.business and name:
            qs = Item.objects.filter(business=self.business, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("An item with this name already exists.")
        return cleaned


class BankStatementImportForm(forms.ModelForm):
    class Meta:
        model = BankStatementImport
        fields = ["bank_account", "file_format", "file"]

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business is not None:
            self.fields["bank_account"].queryset = BankAccount.objects.filter(
                business=business,
                is_active=True,
            )
        for name in ("bank_account", "file_format", "file"):
            field = self.fields.get(name)
            if field:
                field.widget.attrs.setdefault("class", "mb-input")
        self.fields["file"].widget.attrs.update({"accept": ".csv"})


class BankMatchInvoiceForm(forms.Form):
    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(),
        label="Invoice to match",
        widget=forms.Select(attrs={"class": "mb-input"}),
    )

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business")
        bank_tx = kwargs.pop("bank_tx")
        super().__init__(*args, **kwargs)
        candidates = Invoice.objects.filter(
            business=business,
            grand_total=bank_tx.amount,
            status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
        ).order_by("-issue_date")
        self.fields["invoice"].queryset = candidates


class BankQuickExpenseForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        label="Category",
        help_text="Where should this show up on your Profit & Loss?",
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.none(),
        required=False,
        label="Supplier",
        help_text="Optional – who did you pay?",
    )
    memo = forms.CharField(
        required=False,
        label="Internal notes",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        if business is not None:
            self.fields["category"].queryset = Category.objects.filter(
                business=business,
                type=Category.CategoryType.EXPENSE,
            ).order_by("name")
            self.fields["supplier"].queryset = Supplier.objects.filter(
                business=business
            ).order_by("name")


class BankAccountForm(forms.ModelForm):
    LINK_MODE_CREATE = "create"
    LINK_MODE_EXISTING = "existing"

    link_mode = forms.ChoiceField(
        choices=(
            (LINK_MODE_CREATE, "Create a new ledger account for this bank"),
            (LINK_MODE_EXISTING, "Link to an existing ledger account"),
        ),
        widget=forms.RadioSelect,
        initial=LINK_MODE_CREATE,
        label="Ledger link",
    )
    ledger_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        required=False,
        label="Existing ledger account",
        help_text="We only show active Asset accounts (cash/bank).",
    )

    class Meta:
        model = BankAccount
        fields = [
            "name",
            "bank_name",
            "account_number_mask",
            "usage_role",
        ]

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop("business", None)
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "link_mode":
                field.widget.attrs.setdefault("class", "mb-radio")
            else:
                field.widget.attrs.setdefault("class", "mb-input")

        if self.business is not None:
            self.fields["ledger_account"].queryset = (
                Account.objects.filter(
                    business=self.business,
                    type=Account.AccountType.ASSET,
                    is_active=True,
                )
                .order_by("code", "name")
            )
            self.fields["ledger_account"].empty_label = "Select a ledger account"

        if self.instance.pk and self.instance.account_id:
            self.initial.setdefault("link_mode", self.LINK_MODE_EXISTING)
            self.initial.setdefault("ledger_account", self.instance.account_id)
        else:
            self.initial.setdefault("link_mode", self.LINK_MODE_CREATE)

    def _generate_account_code(self) -> str | None:
        if not self.business:
            return None
        existing_codes = set(
            Account.objects.filter(business=self.business)
            .exclude(code__isnull=True)
            .exclude(code__exact="")
            .values_list("code", flat=True)
        )
        next_code = 1000
        # Keep incrementing until we find an unused 4-digit code
        while True:
            candidate = f"{next_code:04d}"
            if candidate not in existing_codes:
                return candidate
            next_code += 1

    def clean(self):
        cleaned = super().clean()
        link_mode = cleaned.get("link_mode")
        ledger_account = cleaned.get("ledger_account")
        if link_mode == self.LINK_MODE_EXISTING:
            if not ledger_account:
                self.add_error("ledger_account", "Select a ledger account to link to.")
            elif self.business and ledger_account.business_id != self.business.id:
                self.add_error("ledger_account", "Select an account from this business.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.business is not None:
            obj.business = self.business

        if hasattr(self, "cleaned_data"):
            link_mode = self.cleaned_data.get("link_mode")
            selected_account = self.cleaned_data.get("ledger_account")
        else:
            link_mode = self.LINK_MODE_CREATE
            selected_account = None

        if self.business is not None:
            if link_mode == self.LINK_MODE_EXISTING and selected_account is not None:
                obj.account = selected_account
            else:
                account_name = obj.name or "Bank account"
                if obj.account_number_mask:
                    account_name = f"{account_name} ••••{obj.account_number_mask}"
                if obj.account_id:
                    if obj.account.name != account_name:
                        obj.account.name = account_name
                        obj.account.save(update_fields=["name"])
                else:
                    next_code = self._generate_account_code()
                    obj.account = Account.objects.create(
                        business=self.business,
                         code=next_code,
                        name=account_name,
                        type=Account.AccountType.ASSET,
                    )
        if commit:
            obj.save()
        return obj
