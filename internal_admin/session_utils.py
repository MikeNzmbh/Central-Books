from __future__ import annotations

from django.contrib.sessions.models import Session
from django.utils import timezone


def revoke_user_sessions(user_id: int, *, exclude_session_key: str | None = None) -> int:
    """
    Best-effort revocation of all active Django sessions for a given user.

    Notes:
    - This scans the session table and decodes sessions; it's acceptable for internal-admin usage.
    - Callers may exclude a session_key to avoid revoking the current session.
    """
    now = timezone.now()
    deleted = 0
    for session in Session.objects.filter(expire_date__gte=now).only("session_key", "session_data", "expire_date"):
        if exclude_session_key and session.session_key == exclude_session_key:
            continue
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if str(data.get("_auth_user_id")) == str(user_id):
            session.delete()
            deleted += 1
    return deleted

