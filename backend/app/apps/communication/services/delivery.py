from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.communication.models import (
    CommunicationConsent,
    CommunicationDeliveryLog,
    CommunicationEmailMessage,
    CommunicationOptOut,
    CommunicationTimelineEvent,
)
from app.core.config import settings
from app.models.user import User


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MERGE_RE = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")
MAX_CAMPAIGN_SENDS_PER_REQUEST = 50


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> None:
    if not EMAIL_RE.match(email.strip()):
        raise HTTPException(status_code=422, detail="Invalid recipient email")


def merge_template(text: str | None, values: dict[str, Any] | None) -> str:
    source = text or ""
    data = values or {}
    return MERGE_RE.sub(lambda match: str(data.get(match.group(1), "")), source)


def is_opted_out(db: Session, email: str, channel: str = "email") -> bool:
    normalized = normalize_email(email)
    if db.query(CommunicationOptOut).filter(CommunicationOptOut.email == normalized, CommunicationOptOut.channel == channel).first():
        return True
    consent = (
        db.query(CommunicationConsent)
        .filter(CommunicationConsent.email == normalized, CommunicationConsent.consent_type == channel)
        .order_by(CommunicationConsent.updated_at.desc())
        .first()
    )
    return bool(consent and consent.status in {"opted_out", "unsubscribed"})


def configured_email_provider() -> str:
    provider = getattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "") or ""
    from app.core.email import email_provider
    value = provider.strip().lower()
    return email_provider() if value in {"", "smtp", "ses"} else value


def deliver_email(db: Session, message: CommunicationEmailMessage, current_user: User | None = None, *, attachments=None) -> CommunicationEmailMessage:
    provider = configured_email_provider()
    request_json = {"to_email": message.to_email, "subject": message.subject, "related_record_type": message.related_record_type, "related_record_id": message.related_record_id}

    if is_opted_out(db, message.to_email):
        message.status = "blocked"
        message.error_message = "Recipient has opted out of email communication"
        _delivery_log(db, message, provider or "none", "blocked", request_json, error_message=message.error_message)
        _timeline(db, message, "blocked", current_user)
        return message

    if provider == "stub":
        if settings.ENVIRONMENT not in {"test", "development", "local"}:
            raise HTTPException(503, "Stub delivery is restricted to development and tests")
        message.status = "sent"
        message.provider_message_id = f"stub-{message.id}"
        message.error_message = None
        message.sent_at = datetime.now(timezone.utc)
        _delivery_log(db, message, "stub", "sent", request_json, response_json={"provider_message_id": message.provider_message_id, "stubbed": True})
        _timeline(db, message, "sent", current_user)
        return message

    from app.core.email import email_configured, send_message
    if provider in {"smtp", "ses"} and email_configured():
        from email.message import EmailMessage
        validate_email(message.to_email)
        mail = EmailMessage()
        mail["To"], mail["Subject"] = message.to_email, message.subject
        from email.utils import getaddresses
        recipients = [message.to_email]
        for header, value in (("Cc", message.cc), ("Bcc", message.bcc)):
            if value:
                mail[header] = value
                recipients.extend(address for _, address in getaddresses([value]))
        mail["Message-ID"] = f"<businesssuite-{message.id}@{settings.MAIL_FROM.split('@')[-1]}>"
        from app.core.rich_text import email_body_parts
        plain, formatted = email_body_parts(message.body)
        mail.set_content(plain)
        mail.add_alternative(formatted, subtype="html")
        for name, content, mime in attachments or []:
            main, sub = mime.split("/", 1)
            mail.add_attachment(content, maintype=main, subtype=sub, filename=name)
        message.provider_message_id = send_message(mail, recipients)
        message.status, message.error_message = "sent", None
        message.sent_at = datetime.now(timezone.utc)
        _delivery_log(db, message, provider, message.status, request_json, response_json={"provider_message_id": message.provider_message_id})
        _timeline(db, message, message.status, current_user)
        return message

    message.status = "blocked"
    message.error_message = "No configured communication email provider. Set COMMUNICATION_EMAIL_PROVIDER=stub for development/test or configure a production adapter."
    _delivery_log(db, message, provider or "none", "blocked", request_json, error_message=message.error_message)
    _timeline(db, message, "blocked", current_user)
    return message


def _timeline(db: Session, message: CommunicationEmailMessage, event_type: str, current_user: User | None) -> None:
    db.add(
        CommunicationTimelineEvent(
            organization_id=getattr(message,"organization_id",None),
            record_type=message.related_record_type,
            record_id=message.related_record_id,
            channel="email",
            event_type=event_type,
            subject=message.subject,
            summary=message.error_message or f"Email {event_type} to {message.to_email}",
            metadata_json={"message_id": message.id, "status": message.status, "provider_message_id": message.provider_message_id},
            actor_user_id=current_user.id if current_user else message.sent_by,
        )
    )


def _delivery_log(db: Session, message: CommunicationEmailMessage, provider: str, status: str, request_json: dict[str, Any], response_json: dict[str, Any] | None = None, error_message: str | None = None) -> None:
    db.add(
        CommunicationDeliveryLog(
            organization_id=getattr(message,"organization_id",None),
            channel="email",
            related_message_id=message.id,
            provider=provider,
            status=status,
            request_json=request_json,
            response_json=response_json,
            error_message=error_message,
        )
    )

