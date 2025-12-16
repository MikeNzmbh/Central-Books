"""
RBAC v1 Permissions Module

Implements Role-Based Access Control aligned with the Gemini RBAC Blueprint.
Provides roles, permission mappings, and utility functions for enforcement.

TODO (Future iterations):
- Full ABAC JSON policy engine with conditions
- SoD (Segregation of Duties) engine
- Cryptographic ledger chaining
- Department/Region attribute scoping
"""
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Set, Optional, Callable, Any

from django.http import JsonResponse

if TYPE_CHECKING:
    from django.http import HttpRequest
    from .models import Business, WorkspaceMembership


# ─────────────────────────────────────────────────────────────────────────────
#    Role Enum
# ─────────────────────────────────────────────────────────────────────────────

class Role(str, Enum):
    """
    Workspace roles aligned with Gemini Blueprint taxonomy.
    
    System Roles (Control Plane):
    - OWNER: Legal owner, billing, can delete tenant
    - SYSTEM_ADMIN: IT operations, user management, no financial visibility
    
    Functional Roles (Accounting Plane):
    - CONTROLLER: Full GL, reporting, tax, period close
    - CASH_MANAGER: Banking, reconciliation, can view bank balances
    - AP_SPECIALIST: Bills & Suppliers, no bank balances
    - AR_SPECIALIST: Invoices & Customers, scoped reporting
    - BOOKKEEPER: Broader operations without settings/users
    - VIEW_ONLY: Read-only, no mutations
    - EXTERNAL_ACCOUNTANT: Like Controller with time-boxed access
    - AUDITOR: Deep read-only, audit log access
    """
    # System roles
    OWNER = "OWNER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    
    # Functional roles
    CONTROLLER = "CONTROLLER"
    CASH_MANAGER = "CASH_MANAGER"
    AP_SPECIALIST = "AP_SPECIALIST"
    AR_SPECIALIST = "AR_SPECIALIST"
    BOOKKEEPER = "BOOKKEEPER"
    VIEW_ONLY = "VIEW_ONLY"
    EXTERNAL_ACCOUNTANT = "EXTERNAL_ACCOUNTANT"
    AUDITOR = "AUDITOR"
    
    @classmethod
    def choices(cls):
        """Django-compatible choices tuple."""
        return [(r.value, r.value.replace("_", " ").title()) for r in cls]
    
    @classmethod
    def values(cls):
        """List of all role values."""
        return [r.value for r in cls]


# ─────────────────────────────────────────────────────────────────────────────
#    Permission Mapping
# ─────────────────────────────────────────────────────────────────────────────

# Action → Set of roles that can perform it
# This is the v1 permission model. Future ABAC will add conditions.
PERMISSIONS: dict[str, Set[Role]] = {
    # ─── User & Workspace Management ───
    "users.manage_roles": {Role.OWNER},
    "users.invite": {Role.OWNER, Role.SYSTEM_ADMIN},
    "users.remove": {Role.OWNER},
    "workspace.delete": {Role.OWNER},
    "workspace.billing": {Role.OWNER},
    "workspace.settings": {Role.OWNER, Role.CONTROLLER},
    
    # ─── Tax Guardian ───
    "tax.view_periods": {
        Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER, Role.BOOKKEEPER,
        Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR, Role.VIEW_ONLY
    },
    "tax.file_return": {Role.OWNER, Role.CONTROLLER, Role.EXTERNAL_ACCOUNTANT},
    "tax.reset_period": {Role.OWNER, Role.CONTROLLER},
    "tax.llm_enrich": {Role.OWNER, Role.CONTROLLER},
    "tax.settings.manage": {Role.OWNER, Role.CONTROLLER},
    "tax.catalog.manage": {Role.OWNER, Role.SYSTEM_ADMIN, Role.CONTROLLER},
    
    # ─── Banking ───
    "bank.view_balance": {Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER},
    "bank.view_transactions": {
        Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER, Role.BOOKKEEPER,
        Role.AP_SPECIALIST, Role.AR_SPECIALIST, Role.AUDITOR, Role.VIEW_ONLY
    },
    "bank.reconcile": {Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER, Role.BOOKKEEPER},
    "bank.import": {Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER, Role.BOOKKEEPER},
    
    # ─── Invoices (AR) ───
    "invoices.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST,
        Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR, Role.VIEW_ONLY
    },
    "invoices.create": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST},
    "invoices.edit": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST},
    "invoices.delete": {Role.OWNER, Role.CONTROLLER},  # Soft-delete/void
    "invoices.send": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST},
    "invoices.receive_payment": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST},
    
    # ─── Expenses (AP) ───
    "expenses.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST,
        Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR, Role.VIEW_ONLY
    },
    "expenses.create": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST},
    "expenses.edit": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST},
    "expenses.delete": {Role.OWNER, Role.CONTROLLER},  # Soft-delete/void
    "expenses.pay": {Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER, Role.BOOKKEEPER},
    
    # ─── General Ledger ───
    "gl.view": {
        Role.OWNER, Role.CONTROLLER, Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR
    },
    "gl.journal_entry": {Role.OWNER, Role.CONTROLLER, Role.EXTERNAL_ACCOUNTANT},
    "gl.close_period": {Role.OWNER, Role.CONTROLLER},
    
    # ─── Reports ───
    "reports.view_pl": {Role.OWNER, Role.CONTROLLER, Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR},
    "reports.view_balance_sheet": {Role.OWNER, Role.CONTROLLER, Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR},
    "reports.view_cashflow": {
        Role.OWNER, Role.CONTROLLER, Role.CASH_MANAGER, Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR
    },
    "reports.export": {Role.OWNER, Role.CONTROLLER, Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR},
    
    # ─── Customers & Suppliers ───
    "customers.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST, 
        Role.AUDITOR, Role.VIEW_ONLY
    },
    "customers.manage": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST},
    "suppliers.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST,
        Role.AUDITOR, Role.VIEW_ONLY
    },
    "suppliers.manage": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST},
    
    # ─── Products & Categories ───
    "products.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST,
        Role.AP_SPECIALIST, Role.AUDITOR, Role.VIEW_ONLY
    },
    "products.manage": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER},
    "categories.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AR_SPECIALIST,
        Role.AP_SPECIALIST, Role.AUDITOR, Role.VIEW_ONLY
    },
    "categories.manage": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER},
    
    # ─── Receipts ───
    "receipts.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST,
        Role.AUDITOR, Role.VIEW_ONLY
    },
    "receipts.upload": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.AP_SPECIALIST},
    "receipts.approve": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER},
    
    # ─── Companion / AI ───
    "companion.view": {
        Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER, Role.CASH_MANAGER,
        Role.EXTERNAL_ACCOUNTANT, Role.AUDITOR, Role.VIEW_ONLY
    },
    "companion.actions": {Role.OWNER, Role.CONTROLLER, Role.BOOKKEEPER},
    
    # ─── Audit ───
    "audit.view_log": {Role.OWNER, Role.CONTROLLER, Role.AUDITOR, Role.SYSTEM_ADMIN},
}


# ─────────────────────────────────────────────────────────────────────────────
#    Permission Utilities
# ─────────────────────────────────────────────────────────────────────────────

def get_membership(request: "HttpRequest") -> Optional["WorkspaceMembership"]:
    """
    Get the current user's workspace membership.
    Returns None if user is not authenticated or has no membership.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    
    from .models import WorkspaceMembership
    
    # Get the user's active membership (for now, first one)
    # Future: support switching workspaces
    return (
        WorkspaceMembership.objects
        .filter(user=user, is_active=True)
        .select_related("business")
        .first()
    )


def get_user_role(request: "HttpRequest") -> Optional[Role]:
    """Get the current user's role in their active workspace."""
    membership = get_membership(request)
    if not membership:
        return None
    try:
        return Role(membership.role)
    except ValueError:
        return None


def has_permission(user, business: "Business", action: str) -> bool:
    """
    Check if user has permission to perform action on business.
    
    Args:
        user: Django User instance
        business: Business instance
        action: Permission action string (e.g., "invoices.create")
    
    Returns:
        True if permitted, False otherwise
    """
    from .permissions_engine import can as can_v2

    return can_v2(user, business, action, level="view")


def check_permission(request: "HttpRequest", action: str) -> tuple[bool, Optional["WorkspaceMembership"]]:
    """
    Check if current request has permission for action.
    
    Returns:
        Tuple of (has_permission, membership)
    """
    membership = get_membership(request)
    if not membership:
        return False, None

    from .permissions_engine import evaluate_permission

    decision = evaluate_permission(request.user, membership.business, action, required_level="view")
    return decision.allowed, membership


def require_roles(*roles: Role) -> Callable:
    """
    Decorator to require specific roles for a view.
    
    Usage:
        @require_roles(Role.OWNER, Role.CONTROLLER)
        def my_view(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: "HttpRequest", *args: Any, **kwargs: Any):
            membership = get_membership(request)
            
            if not membership:
                return JsonResponse(
                    {"error": "No workspace access. Please contact your administrator."},
                    status=403
                )
            
            try:
                user_role = Role(membership.role)
            except ValueError:
                return JsonResponse(
                    {"error": "Invalid role configuration."},
                    status=403
                )
            
            if user_role not in roles:
                return JsonResponse(
                    {"error": f"Permission denied. Required role: {', '.join(r.value for r in roles)}"},
                    status=403
                )
            
            # Attach membership to request for convenience
            request.membership = membership
            request.user_role = user_role
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(action: str) -> Callable:
    """
    Decorator to require a specific permission action.
    
    Usage:
        @require_permission("invoices.create")
        def create_invoice(request):
            ...
    """
    from .permissions_engine import require_permission as require_permission_v2

    return require_permission_v2(action, level="view")


def get_user_permissions(user, business: "Business") -> list[str]:
    """
    Get list of all permission actions available to user for a business.
    Used by frontend to know what UI elements to show/hide.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []

    from .permissions_engine import get_effective_permission_matrix

    matrix = get_effective_permission_matrix(user, business)
    if matrix:
        return sorted([action for action, entry in matrix.items() if entry.get("allowed_unscoped")])

    # Fallback (e.g. before v2 role definitions are seeded)
    from .models import WorkspaceMembership

    membership = WorkspaceMembership.objects.filter(user=user, business=business, is_active=True).first()
    if not membership:
        return []
    try:
        role = Role(membership.role)
    except ValueError:
        return []
    return [action for action, roles in PERMISSIONS.items() if role in roles]


# ─────────────────────────────────────────────────────────────────────────────
#    Role Metadata (for UI)
# ─────────────────────────────────────────────────────────────────────────────

ROLE_DESCRIPTIONS: dict[Role, dict] = {
    Role.OWNER: {
        "label": "Owner",
        "description": "Full access to everything including billing, user management, and data deletion.",
        "color": "purple",
    },
    Role.CONTROLLER: {
        "label": "Controller",
        "description": "Full accounting access including GL, reporting, tax, and period close.",
        "color": "blue",
    },
    Role.CASH_MANAGER: {
        "label": "Cash Manager",
        "description": "Banking, reconciliation, and bank feeds. Can view bank balances.",
        "color": "emerald",
    },
    Role.AP_SPECIALIST: {
        "label": "AP Specialist",
        "description": "Bills and suppliers management. Cannot view bank balances.",
        "color": "amber",
    },
    Role.AR_SPECIALIST: {
        "label": "AR Specialist",
        "description": "Invoices and customers management. Scoped reporting access.",
        "color": "amber",
    },
    Role.BOOKKEEPER: {
        "label": "Bookkeeper",
        "description": "Broad operational access: invoices, bills, bank reconciliation.",
        "color": "sky",
    },
    Role.VIEW_ONLY: {
        "label": "View Only",
        "description": "Read-only access to most data. No ability to create or edit.",
        "color": "slate",
    },
    Role.EXTERNAL_ACCOUNTANT: {
        "label": "External Accountant",
        "description": "Similar to Controller. Typically for CPAs and external bookkeepers.",
        "color": "indigo",
    },
    Role.AUDITOR: {
        "label": "Auditor",
        "description": "Deep read-only access including audit logs. No mutations allowed.",
        "color": "rose",
    },
    Role.SYSTEM_ADMIN: {
        "label": "System Admin",
        "description": "Technical administration: users, SSO, integrations. Limited financial visibility.",
        "color": "gray",
    },
}


def get_role_info(role: Role) -> dict:
    """Get UI metadata for a role."""
    return ROLE_DESCRIPTIONS.get(role, {
        "label": role.value.replace("_", " ").title(),
        "description": "No description available.",
        "color": "gray",
    })
