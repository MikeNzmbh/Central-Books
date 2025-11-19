from .utils import get_business_initials, get_current_business


def business_context(request):
    user = request.user
    business = get_current_business(user) if user.is_authenticated else None
    initials = get_business_initials(business.name) if business else None
    return {
        "business": business,
        "business_initials": initials,
    }
