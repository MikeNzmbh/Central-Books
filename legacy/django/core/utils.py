import re
from decimal import Decimal
from functools import wraps

from django.db.models import Sum
from django.shortcuts import redirect


def get_current_business(user):
    """
    Return the primary Business for this user, or None.

    RBAC v1: Returns business if user is either:
    1. The owner (Business.owner_user)
    2. Has an active WorkspaceMembership
    
    If multiple Business rows exist for a user, we return the owned one first,
    otherwise the first membership business.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    from .models import Business, WorkspaceMembership  # local import to avoid circular deps

    # First check if user owns a business
    owned_business = Business.objects.filter(owner_user=user).order_by("id").first()
    if owned_business:
        return owned_business
    
    # Check for membership (non-owner access)
    # Wrapped in try/except for resilience during migration rollout
    try:
        membership = (
            WorkspaceMembership.objects
            .filter(user=user, is_active=True)
            .select_related("business")
            .order_by("id")
            .first()
        )
        if membership and membership.is_effective:
            return membership.business
    except Exception:
        # WorkspaceMembership table might not exist yet during migration
        pass
    
    return None


def business_required(view_func):
    """Decorator that ensures the user has an associated Business."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        business = get_current_business(request.user)
        if not business:
            return redirect("business_setup")
        return view_func(request, business=business, *args, **kwargs)

    return _wrapped


def get_business_profit_and_loss(business):
    """
    Lightweight profit & loss helper.
    """
    from .models import Expense, Invoice

    revenue = (
        Invoice.objects.filter(business=business, status=Invoice.Status.PAID).aggregate(
            total=Sum("net_total")
        )["total"]
        or Decimal("0")
    )
    expenses = (
        Expense.objects.filter(business=business).aggregate(total=Sum("net_total"))["total"]
        or Decimal("0")
    )
    net_income = revenue - expenses
    return {"revenue": revenue, "expenses": expenses, "net_income": net_income}


def get_business_initials(name: str) -> str:
    if not name:
        return "MB"

    parts = re.split(r"[\s\-]+", name.strip())
    parts = [p for p in parts if p]
    if not parts:
        return "MB"
    if len(parts) == 1:
        return parts[0][0].upper()
    return f"{parts[0][0].upper()}{parts[1][0].upper()}"


def is_empty_workspace(business) -> bool:
    if not business:
        return True
    from .models import Customer, BankAccount

    has_customer = Customer.objects.filter(business=business).exists()
    has_bank = BankAccount.objects.filter(business=business).exists()
    return not has_customer and not has_bank
