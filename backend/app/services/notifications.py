from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.common.services.identity import IdentitySummary, SharedIdentityService
from app.models.notification import Notification, NotificationDeliveryLog
from app.schemas.notification import NotificationCreate, normalize_notification_channels


class NotificationService:
    @staticmethod
    def _delivery_recipient(identity: Optional[IdentitySummary], channel: str) -> Optional[str]:
        if not identity:
            return None
        if channel == "email":
            return identity.email
        if channel in {"whatsapp", "sms"}:
            return identity.phone_number
        if channel == "push":
            return f"user:{identity.user_id}"
        return None

    @classmethod
    def create_notification(cls, db: Session, data: NotificationCreate, *, commit: bool = True) -> Notification:
        company_id = data.company_id
        channels = normalize_notification_channels(data.channels)
        recipient = SharedIdentityService.contact_for_user(db, data.user_id)
        if company_id is None and recipient and recipient.organization_id:
            company_id = recipient.organization_id

        notification = Notification(
            company_id=company_id,
            user_id=data.user_id,
            title=data.title,
            message=data.message,
            module=data.module,
            event_type=data.event_type,
            related_entity_type=data.related_entity_type,
            related_entity_id=data.related_entity_id,
            action_url=data.action_url,
            priority=data.priority,
            channels=channels,
        )
        # Link new delivery rows before the flush. They belong to this new,
        # validated notification; the sender need not read the recipient's inbox.
        notification.delivery_logs = [
            NotificationDeliveryLog(
                channel=channel,
                recipient=cls._delivery_recipient(recipient, channel),
                status="delivered" if channel == "in_app" else "queued",
            )
            for channel in channels
        ]
        db.add(notification)
        db.flush()
        # All generated values are loaded by flush. Refreshing after commit
        # would incorrectly require the sender to read another user's inbox.
        expire_on_commit = db.expire_on_commit
        try:
            db.expire_on_commit = False
            if commit:
                db.commit()
        finally:
            db.expire_on_commit = expire_on_commit
        return notification


def create_notification(db: Session, data: NotificationCreate, *, commit: bool = True) -> Notification:
    return NotificationService.create_notification(db, data, commit=commit)
