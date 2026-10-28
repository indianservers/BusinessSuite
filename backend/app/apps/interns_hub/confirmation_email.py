"""SES application receipts. Acceptance by SES does not prove inbox delivery."""
import logging
from email.message import EmailMessage

from sqlalchemy import select

from app.core.config import settings
from .models import InternApplication
from .management_models import ApplicationEvent
from .application_receipts import FREE_PROGRAM_NOTICE

logger = logging.getLogger(__name__)
ATTEMPTED = ("Confirmation Sending", "Confirmation Accepted", "Confirmation Uncertain")


def deliver_ses(**payload):
    from app.core.email import send_message
    message = EmailMessage()
    message["To"] = ", ".join(payload["Destination"]["ToAddresses"])
    message["Subject"] = payload["Message"]["Subject"]["Data"]
    message.set_content(payload["Message"]["Body"]["Text"]["Data"])
    source = None if settings.SES_FROM else payload["Source"]
    return {"MessageId": send_message(message, payload["Destination"]["ToAddresses"], source=source)}


def send_confirmation(db, application):
    if not (settings.INTERN_HUB_SES_ENABLED or settings.EMAIL_PROVIDER == "ses"):
        return False
    # Serialize receipt attempts for the same application, including backfills.
    item = db.execute(select(InternApplication).where(
        InternApplication.id == application.id).with_for_update()).scalar_one()
    if db.query(ApplicationEvent.id).filter(
        ApplicationEvent.application_id == item.id,
        ApplicationEvent.state.in_(ATTEMPTED),
    ).first():
        db.commit()
        return False
    event = ApplicationEvent(application_id=item.id, state="Confirmation Sending")
    db.add(event)
    db.commit()
    # Persist the attempt before contacting SES. Never automatically resend an
    # uncertain attempt: SES may have accepted it before a network timeout.
    try:
        result = deliver_ses(
            Source=f"Interns Hub <{settings.INTERN_HUB_SES_FROM}>",
            Destination={"ToAddresses": [item.email]},
            Message={
                "Subject": {"Data": f"Interns Hub application received — {item.reference}", "Charset": "UTF-8"},
                "Body": {"Text": {"Data": (
                    f"Hello {item.full_name},\n\n"
                    "We have received your internship application.\n\n"
                    f"Application reference: {item.reference}\n"
                    f"Current status: {item.status}\n\n"
                    "Our team will review your details. This receipt confirms submission; "
                    "it is not an internship offer or approval. Intern access becomes "
                    "available after approval. You can check Application Status in Interns Hub "
                    "using your application email and password.\n\n"
                    "Please keep your application reference for future enquiries.\n\n"
                    f"{FREE_PROGRAM_NOTICE}\n\n"
                    f"{settings.INTERN_HUB_SES_BRAND} — Interns Hub\nThis mailbox does not accept replies."
                ), "Charset": "UTF-8"}},
            },
        )
        event.state = "Confirmation Accepted"
        event.note = "SES message ID: " + result["MessageId"]
    except Exception:
        event.state = "Confirmation Uncertain"
        event.note = "Delivery not confirmed. Check SES before attempting a manual resend."
        # Do not log SDK exception text, credentials, recipient or application data.
        logger.warning("intern_application_confirmation_not_confirmed")
    db.commit()
    return event.state == "Confirmation Accepted"
