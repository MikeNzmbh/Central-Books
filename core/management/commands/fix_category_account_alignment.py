from django.core.management.base import BaseCommand

from core.accounting_defaults import ensure_default_accounts
from core.models import Account, Business, Category


class Command(BaseCommand):
    help = "Realign category.account to appropriate INCOME/EXPENSE defaults to keep P&L accurate."

    def handle(self, *args, **options):
        fixed_income = 0
        fixed_expense = 0
        skipped = 0

        for business in Business.objects.filter(is_deleted=False):
            defaults = ensure_default_accounts(business)
            default_income = defaults.get("sales")
            default_expense = defaults.get("opex")

            for category in Category.objects.filter(business=business):
                if category.type == Category.CategoryType.INCOME:
                    if category.account and category.account.type == Account.AccountType.INCOME:
                        continue
                    if not default_income or default_income.type != Account.AccountType.INCOME:
                        skipped += 1
                        continue
                    category.account = default_income
                    category.save(update_fields=["account"])
                    fixed_income += 1
                elif category.type == Category.CategoryType.EXPENSE:
                    if category.account and category.account.type == Account.AccountType.EXPENSE:
                        continue
                    if not default_expense or default_expense.type != Account.AccountType.EXPENSE:
                        skipped += 1
                        continue
                    category.account = default_expense
                    category.save(update_fields=["account"])
                    fixed_expense += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Category alignment complete: income_fixed={fixed_income}, expense_fixed={fixed_expense}, skipped={skipped}"
            )
        )
