"""Approval notifications sent only after the approval transaction commits."""
import logging

from sqlalchemy import select

from app.core.config import settings
from .confirmation_email import deliver_ses
from .management_models import ApplicationEvent
from .models import InternApplication

logger = logging.getLogger(__name__)
ATTEMPTED = ("Approval Email Sending", "Approval Email Accepted", "Approval Email Uncertain")


def send_approval(db, application):
    if not (settings.INTERN_HUB_SES_ENABLED or settings.EMAIL_PROVIDER == "ses"):
        return False
    item = db.execute(select(InternApplication).where(
        InternApplication.id == application.id).with_for_update()).scalar_one()
    if item.status != "Approved" or db.query(ApplicationEvent.id).filter(
        ApplicationEvent.application_id == item.id,
        ApplicationEvent.state.in_(ATTEMPTED),
    ).first():
        db.commit()
        return False
    event = ApplicationEvent(application_id=item.id, state="Approval Email Sending")
    db.add(event)
    db.commit()
    # Record the attempt first: a provider timeout may still mean acceptance.
    try:
        result = deliver_ses(
            Source=f"Interns Hub <{settings.INTERN_HUB_SES_FROM}>",
            Destination={"ToAddresses": [item.email]},
            Message={
                "Subject": {"Data": "Your internship application is approved", "Charset": "UTF-8"},
                "Body": {"Text": {"Data": (
                    f"Hello {item.full_name},\n\n"
                    "Your internship application has been approved and your intern account is now active.\n\n"
                    f"Application reference: {item.reference}\n\n"
                    "How to log in:\n"
                    f"1. Open {settings.FRONTEND_PUBLIC_URL.rstrip('/')}/login\n"
                    "2. Sign in with the email address you used for your application: "
                    f"{item.email}\n"
                    "3. Enter the password you created when submitting your application.\n"
                    "4. Open Interns Hub to access your internship workspace.\n\n"
                    "If you have forgotten your password, use Forgot password on the login page.\n"
                    "Keep your password private.\n\n"
                    f"{settings.INTERN_HUB_SES_BRAND} — Interns Hub\n"
                    "This mailbox does not accept replies."
                ), "Charset": "UTF-8"}},
            },
        )
        event.state = "Approval Email Accepted"
        event.note = "SES message ID: " + result["MessageId"]
    except Exception:
        event.state = "Approval Email Uncertain"
        event.note = "Delivery not confirmed. Check SES before attempting a manual resend."
        logger.warning("intern_approval_email_not_confirmed")
    db.commit()
    return event.state == "Approval Email Accepted"


def notify_approval(db, application):
    """Notification failures must not turn a committed approval into an API error."""
    try:
        return send_approval(db, application)
    except Exception:
        db.rollback()
        logger.warning("intern_approval_email_failed")
        return False
