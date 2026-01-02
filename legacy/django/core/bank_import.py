import csv
import hashlib
from decimal import Decimal

from django.db import transaction

from .models import BankStatementImport


def _make_external_id(bank_account_id, row):
    raw = f"{bank_account_id}|{row.get('date')}|{row.get('description')}|{row.get('amount')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def process_bank_import(import_obj: BankStatementImport):
    """Very simple v1 CSV parser."""

    from .models import BankTransaction  # local import to avoid cycles

    import_obj.status = BankStatementImport.ImportStatus.PROCESSING
    import_obj.save(update_fields=["status"])

    try:
        with import_obj.file.open("r", encoding="utf-8") as fh, transaction.atomic():
            reader = csv.DictReader(fh)
            for row in reader:
                amount = Decimal(row["amount"])
                external_id = _make_external_id(import_obj.bank_account_id, row)

                BankTransaction.objects.get_or_create(
                    bank_account=import_obj.bank_account,
                    external_id=external_id,
                    defaults={
                        "date": row["date"],
                        "description": row["description"][:512],
                        "amount": amount,
                    },
                )

        import_obj.status = BankStatementImport.ImportStatus.COMPLETED
        import_obj.error_message = ""
    except Exception as exc:
        import_obj.status = BankStatementImport.ImportStatus.FAILED
        import_obj.error_message = str(exc)
    import_obj.save(update_fields=["status", "error_message"])
