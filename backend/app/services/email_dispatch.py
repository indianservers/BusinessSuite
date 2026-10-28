"""Transactional outbox and delivery for suite events and legacy notifications."""
from datetime import datetime, timezone
from uuid import uuid4
import time

from sqlalchemy import or_, update

from app.core.config import settings
from app.core import email
from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification, NotificationDeliveryLog
from app.models.user import User


def queue_email(db, *, recipient, subject, body, module, organization_id=None,
                user_id=None, event_key=None, is_html=False):
    """Never commits: notification and source operation must succeed together."""
    event_key = event_key or uuid4().hex
    if any(isinstance(item, EmailOutbox) and item.event_key == event_key for item in db.new):
        return None
    if not recipient or "@" not in recipient or any(c in recipient for c in "\r\n"):
        return None
    if db.query(EmailOutbox.id).filter_by(event_key=event_key).first():
        return None
    row = EmailOutbox(event_key=event_key, organization_id=organization_id, module=module,
        recipient_user_id=user_id, recipient=recipient, subject=subject[:240], body=body, is_html=is_html, status="queued")
    db.add(row)
    return row


def user_can_receive(db, user_id, recipient, organization_id):
    if not user_id:
        return True
    user = db.get(User, user_id)
    if not user or not user.is_active or user.email.casefold() != recipient.casefold():
        return False
    if organization_id:
        from app.core.tenant_boundary import company_ids
        if organization_id not in company_ids(db, user):
            return False
    return True


def _deliver(db, row, *, notification=None):
    try:
        if isinstance(row, EmailOutbox):
            recipient, subject, body = row.recipient, row.subject, row.body
            allowed = user_can_receive(db, row.recipient_user_id, recipient, row.organization_id)
            if row.event_key.startswith("workspace-invite:"):
                from app.apps.project_management.models import PMSWorkspaceInvitation
                invitation = db.query(PMSWorkspaceInvitation).filter_by(token_hash=row.event_key.split(":", 1)[1]).first()
                expiry = invitation.expires_at if invitation else None
                if expiry and expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                allowed = allowed and bool(invitation and invitation.status == "pending" and expiry > datetime.now(timezone.utc))
            if row.event_key.startswith("portal-invite:"):
                from app.apps.saas.models import PortalSession, PortalUser
                session = db.query(PortalSession).filter_by(session_token_hash=row.event_key.split(":", 1)[1]).first()
                expiry = session.expires_at if session else None
                if expiry and expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                portal_user = db.get(PortalUser, session.portal_user_id) if session else None
                allowed = allowed and bool(session and session.status == "active" and expiry > datetime.now(timezone.utc)
                    and portal_user and portal_user.status == "active" and portal_user.email.casefold() == row.recipient.casefold())
            if row.module == "campaign":
                from app.services.email_schedules import campaign_allowed
                allowed = allowed and campaign_allowed(db, row)
        else:
            user = db.get(User, notification.user_id)
            recipient = user.email if user else ""
            allowed = user_can_receive(db, notification.user_id, recipient, notification.company_id)
            subject = "Business Suite notification"
            # Do not put private comments, HR data or approval details in an email preview.
            body = f"You have an update in {notification.module or 'Business Suite'}. Sign in to review it.\n"
            link = notification.action_url or "/dashboard"
            if link.startswith("/") and not link.startswith("//"):
                body += settings.FRONTEND_PUBLIC_URL.rstrip("/") + link
        if not allowed or not recipient:
            row.status = "suppressed"
        else:
            if isinstance(row, EmailOutbox) and row.is_html:
                from email.message import EmailMessage
                from app.core.rich_text import email_body_parts
                plain, formatted = email_body_parts(body)
                message = EmailMessage()
                message["To"], message["Subject"] = recipient, subject
                message.set_content(plain)
                message.add_alternative(formatted, subtype="html")
                message_id = email.send_message(message, [recipient])
            else:
                message_id = email.send_email(recipient, subject, body)
            if not message_id:
                raise RuntimeError("Provider did not confirm acceptance")
            row.status = "accepted"
            row.provider_message_id = message_id
            if isinstance(row, EmailOutbox):
                row.accepted_at = datetime.now(timezone.utc)
    except Exception as exc:
        # Unknown outcomes may already have reached SES. No blind automatic resend.
        import smtplib
        from botocore.exceptions import ClientError
        rejected = isinstance(exc, (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused, smtplib.SMTPDataError)) or (
            isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in {
                "MessageRejected", "MailFromDomainNotVerifiedException", "ConfigurationSetDoesNotExist",
                "AccessDenied", "AccessDeniedException", "InvalidParameterValue", "ValidationError",
                "AccountSendingPausedException", "Throttling", "ThrottlingException", "TooManyRequestsException",
            })
        row.status = "failed" if rejected else "reconciliation_required"
        error = "Provider rejected request; review configuration before retry" if rejected else "Provider outcome uncertain; reconcile before retry"
        if isinstance(row, EmailOutbox):
            row.error = error
        else:
            row.error_message = error
    if isinstance(row, EmailOutbox) and row.module == "campaign":
        from app.services.email_schedules import update_campaign_result
        update_campaign_result(db, row)
    db.commit()


def drain_outbox(db, limit=25, *, deadline=float("inf")):
    if not email.email_configured():
        return {"processed": 0, "status": "unconfigured"}
    processed = 0
    # Claim one row at a time; commits never release locks on unsent batch rows.
    for _ in range(limit):
        if time.monotonic() >= deadline:
            break
        row = db.query(EmailOutbox).filter_by(status="queued").order_by(EmailOutbox.id).with_for_update(skip_locked=True).first()
        if not row:
            break
        claimed = db.execute(update(EmailOutbox).where(EmailOutbox.id == row.id,
            EmailOutbox.status == "queued").values(status="reconciliation_required", attempts=EmailOutbox.attempts + 1),
            execution_options={"synchronize_session": False}).rowcount
        db.commit()
        if not claimed:
            continue
        db.refresh(row)
        _deliver(db, row)
        processed += 1
    return {"processed": processed, "status": "processed"}


def drain_notifications(db, limit=25, *, deadline=float("inf")):
    """Deliver old email logs that have no shared queue:message pointer."""
    if not email.email_configured():
        return 0
    processed = 0
    for _ in range(limit):
        if time.monotonic() >= deadline:
            break
        row = db.query(NotificationDeliveryLog).filter(
            NotificationDeliveryLog.channel == "email", NotificationDeliveryLog.status == "queued",
            or_(NotificationDeliveryLog.provider_message_id.is_(None),
                ~NotificationDeliveryLog.provider_message_id.startswith("queue:")),
        ).order_by(NotificationDeliveryLog.id).with_for_update(skip_locked=True).first()
        if not row:
            break
        claimed = db.execute(update(NotificationDeliveryLog).where(NotificationDeliveryLog.id == row.id,
            NotificationDeliveryLog.status == "queued").values(status="reconciliation_required"),
            execution_options={"synchronize_session": False}).rowcount
        db.commit()
        if not claimed:
            continue
        db.refresh(row)
        notification = db.get(Notification, row.notification_id)
        if notification:
            _deliver(db, row, notification=notification)
        else:
            row.status = "failed"
            db.commit()
        processed += 1
    return processed


def process_email(db, limit=25):
    from app.shared.communications import drain_email
    from app.services.email_reminders import enqueue_due_reminders
    from app.services.email_schedules import prepare_scheduled_email, prepare_engagement_email
    from app.module_registry import is_app_enabled
    deadline = time.monotonic() + 180
    scheduled = prepare_scheduled_email(db, limit=5)
    engagement = prepare_engagement_email(db, limit=limit) if is_app_enabled("hrms") else 0
    reminders = enqueue_due_reminders(db, limit=limit)
    result = drain_outbox(db, limit, deadline=deadline)
    result["reminders_queued"] = reminders
    result["scheduled"] = scheduled
    result["engagement_queued"] = engagement
    result["notifications"] = drain_notifications(db, limit, deadline=deadline)
    result["shared_notifications"] = drain_email(db, limit, deadline=deadline) if email.email_configured() else 0
    return result


def start_email_worker():
    """Long-running hosts use a thread; serverless hosts use authenticated cron."""
    import logging
    import threading
    stop = threading.Event()

    def run():
        from app.db.session import SessionLocal
        while not stop.is_set():
            try:
                with SessionLocal() as db:
                    process_email(db)
            except Exception:
                logging.getLogger(__name__).warning("email_worker_failed; check migrations and provider configuration")
            stop.wait(30)

    worker = threading.Thread(target=run, daemon=True, name="suite-email")
    worker.start()
    return stop, worker
