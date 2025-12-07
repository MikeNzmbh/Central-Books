from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.accounting_defaults import ensure_default_accounts
from core.forms import CategoryForm
from core.models import Account, Business, Category
from django.contrib.auth import get_user_model


class CategoryValidationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="cat-owner", email="cat@example.com", password="pass12345")
        self.business = Business.objects.create(name="CategoryCo", currency="USD", owner_user=user)
        self.defaults = ensure_default_accounts(self.business)

    def test_income_category_rejects_non_income_account(self):
        wrong_account = Account.objects.create(
            business=self.business,
            name="Wrong",
            code="1500",
            type=Account.AccountType.ASSET,
        )
        form = CategoryForm(
            data={
                "name": "Bad Income",
                "type": Category.CategoryType.INCOME,
                "account": wrong_account.id,
            },
            business=self.business,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Income categories must use an income account.", form.errors.get("account", []))

    def test_model_clean_blocks_mismatched_account_type(self):
        wrong_account = Account.objects.create(
            business=self.business,
            name="Wrong Liability",
            code="2210",
            type=Account.AccountType.LIABILITY,
        )
        category = Category(
            business=self.business,
            name="Ops",
            type=Category.CategoryType.EXPENSE,
            account=wrong_account,
        )
        with self.assertRaises(ValidationError):
            category.full_clean()
