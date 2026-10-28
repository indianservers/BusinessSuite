"""Transactional notification fan-out over the existing notification/email tables."""

from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.models.user import User
from app.models.notification import Notification, NotificationDeliveryLog
from app.apps.communication.models import CommunicationEmailMessage
from app.shared.contracts import authorize
from app.shared.gateway import read_record
from app.shared.settings import effective


def notify(
    db,
    actor,
    company,
    module,
    entity,
    entity_id,
    recipient_id,
    title,
    message,
    channels=None,
    critical=False,
):
    authorize(db, actor, company, module, "create")
    read_record(db, actor, company, module, entity, entity_id)
    recipient = db.get(User, recipient_id)
    if not recipient or not recipient.is_active:
        raise HTTPException(422, "Choose an active recipient")
    # Recipient must independently be able to see this exact source record.
    read_record(db, recipient, company, module, entity, entity_id)
    policy = effective(db, company, module)["values"]
    requested = channels or ["in_app"]
    if set(requested) - set(policy["notification_channels"]):
        raise HTTPException(422, "Channel is not allowed by effective company policy")
    if (
        not isinstance(title, str)
        or not title.strip()
        or len(title) > 200
        or not isinstance(message, str)
        or len(message) > 10000
    ):
        raise HTTPException(422, "Notification content exceeds limits")
    start, end = policy.get("quiet_start"), policy.get("quiet_end")
    hour = datetime.now(ZoneInfo(policy["timezone"])).hour
    quiet = (
        start is not None
        and end is not None
        and (start <= hour < end if start < end else hour >= start or hour < end)
    )
    row = Notification(
        company_id=company,
        user_id=recipient_id,
        title=title,
        message=message,
        module=module,
        event_type="shared.notification",
        related_entity_type=entity,
        related_entity_id=entity_id,
        priority="critical" if critical else "normal",
        channels=requested,
    )
    db.add(row)
    db.flush()
    for channel in requested:
        status = (
            "suppressed"
            if quiet and not critical
            else "delivered" if channel == "in_app" else "queued"
        )
        delivery = NotificationDeliveryLog(
            notification_id=row.id,
            channel=channel,
            recipient=f"user:{recipient_id}",
            status=status,
            error_message="Quiet hours" if status == "suppressed" else None,
        )
        db.add(delivery)
        if channel == "email" and status != "suppressed":
            email = CommunicationEmailMessage(
                organization_id=company,
                related_record_type=entity,
                related_record_id=entity_id,
                to_email=recipient.email,
                subject=title,
                body=message,
                status="queued",
                sent_by=actor.id,
            )
            db.add(email)
            db.flush()
            delivery.provider_message_id = f"queue:{email.id}"
    if quiet and not critical:
        # Suppressed notifications must not still appear as unread in-app items.
        row.is_read = True
    from app.access.service import audit

    audit(
        db,
        actor,
        company,
        "shared.notification.created",
        "Authorized record notification",
        after={
            "notificationId": row.id,
            "module": module,
            "recipientId": recipient_id,
            "channels": requested,
        },
    )
    return row


def drain_email(db, limit=10, *, deadline=float("inf")):
    from app.apps.communication.services.delivery import deliver_email
    from app.shared.contracts import service_identity

    processed = 0
    from sqlalchemy import update
    import time
    for _ in range(limit):
        if time.monotonic() >= deadline:
            break
        pair = (db.query(NotificationDeliveryLog, Notification)
            .join(Notification, Notification.id == NotificationDeliveryLog.notification_id)
            .filter(NotificationDeliveryLog.channel == "email", NotificationDeliveryLog.status == "queued",
                NotificationDeliveryLog.provider_message_id.startswith("queue:"))
            .order_by(NotificationDeliveryLog.id).with_for_update(skip_locked=True).first())
        if not pair:
            break
        log, notification = pair
        message = db.get(
            CommunicationEmailMessage, int(log.provider_message_id.split(":", 1)[1])
        )
        if not message:
            log.status, log.error_message = "failed", "Queued email no longer exists"
            db.commit()
            continue
        actor = db.get(User, message.sent_by)
        try:
            service_identity(db, actor, notification.company_id, notification.module)
            read_record(
                db,
                actor,
                notification.company_id,
                notification.module,
                notification.related_entity_type,
                notification.related_entity_id,
            )
            recipient = db.get(User, notification.user_id)
            if not recipient or not recipient.is_active or recipient.email.casefold() != message.to_email.casefold():
                log.status, log.error_message = "suppressed", "Recipient account changed"
                db.commit()
                processed += 1
                continue
            read_record(
                db,
                recipient,
                notification.company_id,
                notification.module,
                notification.related_entity_type,
                notification.related_entity_id,
            )
            # Reserve an unknown-outcome state before crossing the provider boundary.
            claimed = db.execute(update(NotificationDeliveryLog).where(
                NotificationDeliveryLog.id == log.id, NotificationDeliveryLog.status == "queued"
            ).values(status="reconciliation_required"), execution_options={"synchronize_session": False}).rowcount
            db.commit()
            if not claimed:
                continue
            db.refresh(log)
            deliver_email(db, message, actor)
            log.status = "accepted" if message.status == "sent" else "failed"
            log.provider_message_id = message.provider_message_id
            log.error_message = message.error_message
        except HTTPException as error:
            if log.status != "reconciliation_required":
                log.status = "failed"
            log.error_message = f"Authorized delivery failed (HTTP {error.status_code})"
        except Exception:
            log.error_message = "Provider outcome uncertain; reconcile before retry"
        db.commit()
        processed += 1
    return processed


def provider_status():
    from app.apps.communication.services.delivery import configured_email_provider
    from app.core.config import settings

    provider = configured_email_provider()
    from app.core.email import email_configured
    configured = provider in {"smtp", "ses"} and email_configured()
    return [
        {
            "channel": "in_app",
            "status": "operational",
            "deliverySemantics": "Persisted in the authorized recipient inbox",
        },
        {
            "channel": "email",
            "provider": provider or "none",
            "status": "configured-unverified" if configured else "unconfigured",
            "deliverySemantics": "Provider acceptance is not confirmed delivery",
        },
        *[
            {"channel": c, "status": "unconfigured"}
            for c in ("sms", "whatsapp", "mobile_push", "web_push")
        ],
    ]
