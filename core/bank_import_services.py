import csv
import hashlib
from datetime import datetime
from decimal import Decimal
from io import TextIOWrapper

from django.db import transaction

from .models import BankTransaction, BankStatementImport


def _stable_external_id(bank_account_id, date_str, description, amount_str):
    raw = f"{bank_account_id}|{date_str}|{description}|{amount_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def process_bank_statement_import(import_obj: BankStatementImport):
    """Process uploaded CSV and create BankTransaction rows."""

    import_obj.status = BankStatementImport.ImportStatus.PROCESSING
    import_obj.save(update_fields=["status"])

    created = 0
    skipped = 0

    wrapper = TextIOWrapper(import_obj.file.open("rb"), encoding="utf-8")
    reader = csv.DictReader(wrapper)

    with transaction.atomic():
        for row in reader:
            date_raw = (row.get("Date") or row.get("date") or "").strip()
            description = (row.get("Description") or row.get("description") or "").strip()

            if not date_raw or not description:
                skipped += 1
                continue

            try:
                date_obj = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except ValueError:
                skipped += 1
                continue

            if import_obj.file_format == "generic_debit_credit":
                debit_raw = row.get("Debit") or row.get("debit") or "0"
                credit_raw = row.get("Credit") or row.get("credit") or "0"
                amount = Decimal(credit_raw or "0") - Decimal(debit_raw or "0")
            else:
                amount_raw = row.get("Amount") or row.get("amount")
                if not amount_raw:
                    skipped += 1
                    continue
                amount = Decimal(amount_raw)

            external_id = _stable_external_id(
                import_obj.bank_account_id, date_raw, description, str(amount)
            )

            obj, created_flag = BankTransaction.objects.get_or_create(
                bank_account=import_obj.bank_account,
                external_id=external_id,
                defaults={
                    "date": date_obj,
                    "description": description,
                    "amount": amount,
                },
            )
            if created_flag:
                created += 1
            else:
                skipped += 1

    import_obj.status = BankStatementImport.ImportStatus.COMPLETED
    import_obj.error_message = f"Created {created} transactions, skipped {skipped}."
    import_obj.save(update_fields=["status", "error_message"])
