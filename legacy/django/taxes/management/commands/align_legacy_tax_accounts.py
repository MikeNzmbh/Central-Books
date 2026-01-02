from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import models

from core.models import Account, Business, JournalEntry, JournalLine


class Command(BaseCommand):
    help = "Report (and optionally realign) legacy tax payable account 2200 to new standard 2300/1400."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create adjusting journal entries to move 2200 balances into 2300.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        for business in Business.objects.all():
            acc_2200 = Account.objects.filter(business=business, code="2200").first()
            acc_2300 = Account.objects.filter(business=business, code="2300").first()
            acc_1400 = Account.objects.filter(business=business, code="1400").first()

            bal_2200 = self._balance(acc_2200)
            bal_2300 = self._balance(acc_2300)
            bal_1400 = self._balance(acc_1400)

            self.stdout.write(
                f"[{business.name}] 2200={bal_2200} 2300={bal_2300} 1400={bal_1400}"
            )

            if apply_changes and acc_2200 and acc_2300 and bal_2200 != Decimal("0.00"):
                self._move_balance(business, acc_2200, acc_2300, bal_2200)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Moved {bal_2200} from 2200 -> 2300 for {business.name}"
                    )
                )

    def _balance(self, account):
        if not account:
            return Decimal("0.00")
        agg = JournalLine.objects.filter(account=account).aggregate(
            debit_sum=models.Sum("debit"),
            credit_sum=models.Sum("credit"),
        )
        debit = agg["debit_sum"] or Decimal("0.00")
        credit = agg["credit_sum"] or Decimal("0.00")
        if account.type in (Account.AccountType.ASSET, Account.AccountType.EXPENSE):
            return debit - credit
        return credit - debit

    def _move_balance(self, business, from_acc, to_acc, amount):
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                business=business,
                date=timezone.now().date(),
                description="Align legacy tax payable 2200 -> 2300",
            )
            JournalLine.objects.create(
                journal_entry=entry,
                account=from_acc,
                debit=amount,
                credit=Decimal("0.00"),
                description="Close legacy tax payable",
            )
            JournalLine.objects.create(
                journal_entry=entry,
                account=to_acc,
                debit=Decimal("0.00"),
                credit=amount,
                description="Open new tax payable",
            )
            entry.check_balance()
