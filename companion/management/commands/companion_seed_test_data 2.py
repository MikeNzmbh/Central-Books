from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from companion.models import WorkspaceMemory
from core.models import Business, Category, Expense, Supplier


class Command(BaseCommand):
    help = "Seed lightweight Companion test data (memory + expenses)."

    def handle(self, *args, **options):
        user_model = get_user_model()
        owner = user_model.objects.order_by("id").first()
        if owner is None:
            owner = user_model.objects.create_user(username="companion-owner", email="owner@example.com", password="pass")

        workspace, _ = Business.objects.get_or_create(
            owner_user=owner,
            defaults={"name": "Companion Workspace", "currency": "USD"},
        )
        category, _ = Category.objects.get_or_create(
            business=workspace,
            name="Office Supplies",
            type=Category.CategoryType.EXPENSE,
        )
        suppliers = [
            Supplier.objects.get_or_create(business=workspace, name="Acme Supplies")[0],
            Supplier.objects.get_or_create(business=workspace, name="Northwind Stationery")[0],
            Supplier.objects.get_or_create(business=workspace, name="Bright Telecom")[0],
        ]

        # Create expenses to trigger vendor-category memories via signal.
        for supplier in suppliers:
            Expense.objects.create(
                business=workspace,
                supplier=supplier,
                category=category,
                description=f"Seed expense for {supplier.name}",
                amount=Decimal("42.00"),
            )

        # Also seed a couple explicit memory entries.
        WorkspaceMemory.objects.update_or_create(
            workspace=workspace,
            key="vendor:acme supplies",
            defaults={"value": {"category_id": category.id, "last_expense_id": None}},
        )
        WorkspaceMemory.objects.update_or_create(
            workspace=workspace,
            key="vendor:bright telecom",
            defaults={"value": {"category_id": category.id, "last_expense_id": None}},
        )

        self.stdout.write(self.style.SUCCESS("Seeded Companion test data (memories + expenses)."))
