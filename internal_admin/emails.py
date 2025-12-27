from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from internal_admin.models import AdminInvite


def send_staff_invite_email(*, invite: AdminInvite, request=None) -> None:
    """
    Send an internal admin staff invite email.

    Uses Django's configured email backend (console in dev, SMTP in prod).
    """
    to_email = (invite.email or "").strip()
    if not to_email:
        raise ValueError("Invite email is required.")

    inviter = invite.created_by
    inviter_name = "Central Books"
    if inviter:
        inviter_name = inviter.get_full_name() or inviter.email or inviter.username or inviter_name

    invite_url = invite.get_invite_url(request)
    expires_at = invite.expires_at
    expires_str = timezone.localtime(expires_at).strftime("%Y-%m-%d %H:%M %Z") if expires_at else ""

    from_email = (
        (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
        or (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
        or "no-reply@localhost"
    )

    greeting_name = (invite.full_name or "").strip() or to_email

    subject = "You’ve been invited to Central Books internal admin"
    text_body = "\n".join(
        [
            f"Hi {greeting_name},",
            "",
            f"{inviter_name} invited you to Central Books internal admin.",
            "",
            f"Accept invite: {invite_url}",
            (f"Expires: {expires_str}" if expires_str else "This invite expires in 7 days."),
            "",
            "If you weren’t expecting this, you can ignore this email.",
        ]
    )
    html_body = "\n".join(
        [
            f"<p>Hi {greeting_name},</p>",
            f"<p><strong>{inviter_name}</strong> invited you to Central Books internal admin.</p>",
            f'<p><a href="{invite_url}">Accept invite</a></p>',
            (f"<p><small>Expires: {expires_str}</small></p>" if expires_str else "<p><small>This invite expires in 7 days.</small></p>"),
            "<p><small>If you weren’t expecting this, you can ignore this email.</small></p>",
        ]
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[to_email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send()

