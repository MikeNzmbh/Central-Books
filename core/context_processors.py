from .utils import get_business_initials, get_current_business


def business_context(request):
    user = request.user
    business = get_current_business(user) if user.is_authenticated else None
    initials = get_business_initials(business.name) if business else None
    return {
        "business": business,
        "business_initials": initials,
    }


def impersonation_context(request):
    return {
        "is_impersonating": request.session.get("is_impersonating", False),
        "impersonator_user_id": request.session.get("impersonator_user_id"),
        "impersonated_user_id": request.session.get("impersonated_user_id"),
    }
