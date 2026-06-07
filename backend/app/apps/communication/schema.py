from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.apps.communication.models import (
    CommunicationAutoResponseRule,
    CommunicationCampaign,
    CommunicationCampaignMember,
    CommunicationCampaignSend,
    CommunicationConsent,
    CommunicationDeliveryLog,
    CommunicationEmailAttachment,
    CommunicationEmailMessage,
    CommunicationEmailTemplate,
    CommunicationOptOut,
    CommunicationTimelineEvent,
    CommunicationWebform,
    CommunicationWebformField,
    CommunicationWebformSubmission,
    CommunicationWhatsAppTemplate,
)


COMMUNICATION_TABLE_MODELS = [
    CommunicationEmailTemplate,
    CommunicationEmailMessage,
    CommunicationEmailAttachment,
    CommunicationWebform,
    CommunicationWebformField,
    CommunicationWebformSubmission,
    CommunicationAutoResponseRule,
    CommunicationCampaign,
    CommunicationCampaignMember,
    CommunicationCampaignSend,
    CommunicationConsent,
    CommunicationOptOut,
    CommunicationWhatsAppTemplate,
    CommunicationTimelineEvent,
    CommunicationDeliveryLog,
]


def ensure_communication_schema(db: Session) -> None:
    inspector = inspect(db.bind)
    existing_tables = set(inspector.get_table_names())
    missing = [model.__table__ for model in COMMUNICATION_TABLE_MODELS if model.__tablename__ not in existing_tables]
    if missing:
        CommunicationEmailTemplate.metadata.create_all(bind=db.bind, tables=missing)

