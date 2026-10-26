"""Transactional SMTP delivery. Never log recipients, bodies or credentials."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_smtp_message(message: EmailMessage, recipient: str) -> None:
    if not (settings.MAIL_SERVER and settings.MAIL_USERNAME and settings.MAIL_PASSWORD and settings.MAIL_FROM):
        raise RuntimeError("Email delivery is not configured")
    if not settings.MAIL_SSL_TLS and not settings.MAIL_STARTTLS:
        raise RuntimeError("SMTP requires TLS")
    message["From"] = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))
    if "Message-ID" not in message:
        message["Message-ID"] = make_msgid(domain=settings.MAIL_FROM.split("@")[-1])
    context = ssl.create_default_context()
    smtp_class = smtplib.SMTP_SSL if settings.MAIL_SSL_TLS else smtplib.SMTP
    kwargs = {"timeout": 20}
    if settings.MAIL_SSL_TLS:
        kwargs["context"] = context
    with smtp_class(settings.MAIL_SERVER, settings.MAIL_PORT, **kwargs) as connection:
        if settings.MAIL_STARTTLS and not settings.MAIL_SSL_TLS:
            connection.ehlo()
            connection.starttls(context=context)
            connection.ehlo()
        connection.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
        refused = connection.send_message(message, from_addr=settings.MAIL_FROM, to_addrs=[recipient])
    if refused:
        raise RuntimeError("Email provider rejected the recipient")
    logger.info("email_dispatch_accepted provider=smtp")


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        if settings.ENVIRONMENT in {"development", "local", "test"}:
            logger.info("email_dispatch_requested provider=unconfigured")
            return
        raise RuntimeError("Email delivery is not configured")
    message = EmailMessage()
    message["To"], message["Subject"] = to, subject
    message.set_content(body)
    send_smtp_message(message, to)
