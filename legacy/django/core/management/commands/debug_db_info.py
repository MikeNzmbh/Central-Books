import datetime
import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print the active database path plus a few row counts to confirm which DB is in use."

    def handle(self, *args, **options):
        db_settings = settings.DATABASES.get("default", {})
        engine = db_settings.get("ENGINE")
        name = db_settings.get("NAME")

        self.stdout.write(f"ENGINE: {engine}")
        self.stdout.write(f"NAME:   {name}")

        if engine == "django.db.backends.sqlite3" and name:
            path = Path(name).expanduser().resolve()
            exists = path.exists()
            self.stdout.write(f"Resolved path: {path}")
            self.stdout.write(f"Exists:        {exists}")
            if exists:
                stat = path.stat()
                size_mb = stat.st_size / (1024 * 1024)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                self.stdout.write(f"Size:          {size_mb:.2f} MB")
                self.stdout.write(f"Last modified: {mtime}")
        else:
            self.stdout.write("Non-SQLite engine or missing NAME; skipping file inspection.")

        self.stdout.write("\nTable row counts (skip missing tables):")
        models_to_check = [
            "auth.User",
            "core.Business",
            "core.Customer",
            "core.Supplier",
            "core.Account",
            "core.Invoice",
            "core.Expense",
            "core.BankTransaction",
        ]

        for label in models_to_check:
            try:
                model = apps.get_model(label)
            except LookupError:
                self.stdout.write(f"- {label}: missing")
                continue

            try:
                count = model.objects.count()
            except Exception as exc:  # pragma: no cover - defensive logging only
                self.stdout.write(f"- {label}: error ({exc})")
                continue

            self.stdout.write(f"- {label}: {count}")
