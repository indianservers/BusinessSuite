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
    def create_notification(cls, db: Session, data: NotificationCreate) -> Notification:
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
        db.add(notification)
        db.flush()

        for channel in channels:
            db.add(
                NotificationDeliveryLog(
                    notification_id=notification.id,
                    channel=channel,
                    recipient=cls._delivery_recipient(recipient, channel),
                    status="delivered" if channel == "in_app" else "queued",
                )
            )

        db.commit()
        db.refresh(notification)
        return notification


def create_notification(db: Session, data: NotificationCreate) -> Notification:
    return NotificationService.create_notification(db, data)
