"""Booking notification emails: SMTP, console backend, and a local log file backup."""

import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _booking_log_path() -> Path:
    return Path(getattr(settings, "BASE_DIR", ".")) / "booking_notifications.log"


def append_booking_email_local_copy(subject: str, body: str) -> None:
    """Always append a copy so staff can recover bookings if SMTP or inbox fails."""
    block = (
        f"\n{'=' * 60}\n"
        f"{datetime.now().isoformat(timespec='seconds')}\n"
        f"{subject}\n{body}\n"
    )
    path = _booking_log_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
    except OSError as exc:
        logger.warning("Could not append booking log %s: %s", path, exc)


def send_booking_notification(booking):
    """
    Send booking email. Always writes to booking_notifications.log first.

    Returns:
        tuple: (success: bool, email_uses_smtp: bool, message: str | None)
        success False = send_mail raised or no recipients.
        email_uses_smtp True = SMTP backend (real delivery attempted).
    """
    subject = f"[Villa booking] {booking.villa.name}"
    body = (
        f"Villa: {booking.villa.name}\n"
        f"Dates: {booking.start_date} to {booking.end_date}\n"
        f"Name: {booking.full_name}\n"
        f"Phone: {booking.phone_number}\n"
        f"Booking id: {booking.pk}\n"
    )
    append_booking_email_local_copy(subject, body)

    emails = list(getattr(settings, "BOOKING_NOTIFICATION_EMAILS", None) or [])
    if not emails and getattr(settings, "ADMINS", None):
        emails = [email for _, email in settings.ADMINS]
    if not emails:
        msg = "Configure BOOKING_NOTIFICATION_EMAILS or ADMINS in settings."
        logger.warning("Booking %s: %s", booking.pk, msg)
        return False, False, msg

    backend = getattr(settings, "EMAIL_BACKEND", "")
    email_uses_smtp = "smtp" in backend.lower()

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    logger.info(
        "Booking %s: send_mail backend=%s to=%s",
        booking.pk,
        backend,
        emails,
    )

    try:
        send_mail(subject, body, from_email, emails, fail_silently=False)
    except Exception as exc:
        logger.exception("send_mail failed for booking %s", booking.pk)
        return False, email_uses_smtp, str(exc)

    if not email_uses_smtp:
        logger.warning(
            "Booking %s: EMAIL_BACKEND is not SMTP — output went to the "
            "runserver console only. Set EMAIL_HOST_PASSWORD in .env or "
            "email_password.txt (project root, same folder as manage.py) for Gmail SMTP.",
            booking.pk,
        )
    return True, email_uses_smtp, None
