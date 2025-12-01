from __future__ import annotations

from typing import Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from .models import AdminAuditLog


def _object_type_and_id(obj: Any) -> tuple[str, str]:
    if obj is None:
        return "", ""
    if hasattr(obj, "_meta"):
        model = obj._meta.model  # type: ignore[attr-defined]
        ct = ContentType.objects.get_for_model(model, for_concrete_model=False)
        object_type = f"{ct.app_label}.{ct.model}"
    else:
        object_type = obj.__class__.__name__.lower()
    object_id = ""
    if hasattr(obj, "pk"):
        object_id = str(obj.pk)
    elif hasattr(obj, "id"):
        object_id = str(getattr(obj, "id"))
    return object_type, object_id


def log_admin_action(
    request: HttpRequest,
    action: str,
    obj: Optional[Any] = None,
    extra: Optional[dict[str, Any]] = None,
    level: str = "INFO",
    category: str | None = None,
) -> AdminAuditLog:
    object_type, object_id = _object_type_and_id(obj)
    remote_ip = request.META.get("REMOTE_ADDR")
    category_value = category or ""

    entry = AdminAuditLog.objects.create(
        admin_user=getattr(request, "user", None),
        action=action,
        object_type=object_type,
        object_id=object_id,
        extra=extra or {},
        remote_ip=remote_ip,
        level=level,
        category=category_value,
    )
    return entry
