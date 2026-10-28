"""Suite email facade; every module shares suite_email_transport."""
import logging
import smtplib
from email.message import EmailMessage
from app.core.config import settings
import suite_email_transport as transport

logger = logging.getLogger(__name__)


def email_provider():
    return transport.email_provider(settings)


def email_configured():
    return transport.email_configured(settings)


def send_message(message, recipients=None, *, source=None):
    return transport.send_message(message, recipients, source=source, settings=settings)


def send_smtp_message(message: EmailMessage, recipient: str):
    """Compatibility entry point; respects the shared provider."""
    return send_message(message, [recipient])


def send_email(to: str, subject: str, body: str) -> str | None:
    if not email_configured():
        if settings.ENVIRONMENT in {"development", "local", "test"}:
            logger.info("email_dispatch_requested provider=unconfigured")
            return
        raise RuntimeError("Email delivery is not configured")
    message = EmailMessage()
    message["To"], message["Subject"] = to, subject
    message.set_content(body)
    return send_message(message, [to])
