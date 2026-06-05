from __future__ import annotations

import html
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import smtplib
import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from email.message import EmailMessage
from math import ceil
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import asc, desc, or_
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, Integer, Numeric

from app.apps.crm.models import (
    CRMActivity,
    CRMApprovalRequest,
    CRMApprovalRequestStep,
    CRMApprovalStep,
    CRMApprovalWorkflow,
    CRMCallLog,
    CRMCalendarIntegration,
    CRMCampaign,
    CRMCompany,
    CRMContact,
    CRMCustomField,
    CRMCustomFieldValue,
    CRMDeal,
    CRMDealContact,
    CRMDealProduct,
    CRMEmailLog,
    CRMEmailTemplate,
    CRMEnrichmentLog,
    CRMFileAsset,
    CRMLead,
    CRMLeadScoringRule,
    CRMMeeting,
    CRMMessage,
    CRMMessageTemplate,
    CRMNote,
    CRMNoteMention,
    CRMOwner,
    CRMPipeline,
    CRMPipelineStage,
    CRMProduct,
    CRMQuotation,
    CRMQuotationItem,
    CRMTask,
    CRMTeam,
    CRMTicket,
    CRMTerritory,
    CRMTerritoryUser,
    CRMWebhook,
    CRMWebhookDelivery,
)
from app.core.config import settings
from app.core.deps import RequirePermission, get_db
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/crm", tags=["CRM"])


class CRMRecordPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class CRMLeadConvertPayload(BaseModel):
    createContact: bool = True
    createCompany: bool = True
    createDeal: bool = True
    dealName: str | None = None
    dealAmount: Decimal | None = None
    pipelineId: int | None = None
    stageId: int | None = None


class CRMImportRowsPayload(BaseModel):
    rows: list[dict[str, Any]]


class CRMEmailSendPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str
    entityId: int
    to: str
    cc: str | None = None
    bcc: str | None = None
    subject: str
    body: str
    saveAsDraft: bool = False


class CRMEmailTemplatePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    subject: str
    body: str
    entityType: str | None = None


class CRMMessageSendPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    channel: str
    to: str
    templateId: int | None = None
    body: str
    entityType: str
    entityId: int


class CRMMessageTemplatePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    channel: str = "sms"
    body: str
    entityType: str | None = None
    isActive: bool | None = True


class CRMCalendarIntegrationConnectPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    accessToken: str | None = None
    refreshToken: str | None = None
    expiresAt: datetime | None = None
    mock: bool | None = None


class CRMMeetingSyncPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str | None = None
    twoWay: bool | None = False


class CRMWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: list[str] | None = None
    isActive: bool | None = True


class CRMCustomFieldValueUpsertPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    customFieldId: int
    entity: str
    recordId: int
    value: Any = None


class CRMApprovalStepPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    stepOrder: int | None = None
    approverType: str = "user"
    approverId: int | None = None
    actionOnReject: str = "stop"


class CRMApprovalWorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    entityType: str | None = None
    triggerType: str | None = None
    conditions: dict[str, Any] | None = None
    isActive: bool | None = True
    steps: list[CRMApprovalStepPayload] | None = None


class CRMApprovalSubmitPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str
    entityId: int
    workflowId: int | None = None
    triggerType: str | None = "manual"
    comments: str | None = None


class CRMApprovalActionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    comments: str | None = None


class CRMDealContactPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    contactId: int | None = None
    contact_id: int | None = None
    role: str = "Stakeholder"
    influenceLevel: str | None = None
    influence_level: str | None = None
    isPrimary: bool | None = False
    is_primary: bool | None = None
    notes: str | None = None


class CRMDealContactsReplacePayload(BaseModel):
    contacts: list[CRMDealContactPayload]


class CRMDuplicateScanPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str | None = None


class CRMDuplicateMergePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str
    winnerId: int
    loserIds: list[int]
    fieldValues: dict[str, Any] | None = None


class CRMQuotationPdfEmailPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    to: str | None = None
    cc: str | None = None
    bcc: str | None = None
    subject: str | None = None
    body: str | None = None
    saveAsDraft: bool = False


class CRMTerritoryUserPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    userId: int


class CRMTerritoryAutoAssignPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str | None = None
    entityId: int | None = None
    overrideManual: bool = False


class CRMEnrichmentPreviewPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str
    entityId: int
    provider: str | None = "manual"
    data: dict[str, Any] | None = None
    enrichmentData: dict[str, Any] | None = None
    csvRow: dict[str, Any] | None = None


class CRMEnrichmentApplyPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    entityType: str
    entityId: int
    provider: str | None = "manual"
    values: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    enrichmentData: dict[str, Any] | None = None
    csvRow: dict[str, Any] | None = None
    appliedFields: list[str] | None = None
    selectedFields: list[str] | None = None


class Resource:
    def __init__(
        self,
        model: type,
        *,
        required: tuple[str, ...],
        search: tuple[str, ...],
        default_sort: str = "created_at",
        aliases: tuple[str, ...] = (),
        soft_delete: bool = True,
        owner_field: str | None = "owner_user_id",
    ) -> None:
        self.model = model
        self.required = required
        self.search = search
        self.default_sort = default_sort
        self.aliases = aliases
        self.soft_delete = soft_delete
        self.owner_field = owner_field


RESOURCES: dict[str, Resource] = {
    "leads": Resource(CRMLead, required=("first_name", "full_name"), search=("full_name", "email", "phone", "company_name", "source", "status", "rating")),
    "lead-scoring-rules": Resource(CRMLeadScoringRule, required=("name", "field", "operator", "points"), search=("name", "field", "operator", "value"), owner_field=None),
    "contacts": Resource(CRMContact, required=("first_name", "full_name"), search=("full_name", "email", "phone", "job_title", "lifecycle_stage", "source")),
    "companies": Resource(CRMCompany, required=("name",), search=("name", "industry", "email", "phone", "city", "account_type", "status"), aliases=("accounts",)),
    "deals": Resource(CRMDeal, required=("name", "pipeline_id", "stage_id"), search=("name", "description", "status", "lead_source"), aliases=("opportunities",)),
    "pipelines": Resource(CRMPipeline, required=("name",), search=("name", "description"), owner_field=None),
    "pipeline-stages": Resource(CRMPipelineStage, required=("pipeline_id", "name"), search=("name", "color"), owner_field=None),
    "activities": Resource(CRMActivity, required=("activity_type",), search=("entity_type", "activity_type", "title", "subject", "body", "description", "status", "priority"), default_sort="activity_date"),
    "notes": Resource(CRMNote, required=("body",), search=("body",), owner_field="author_user_id"),
    "tasks": Resource(CRMTask, required=("title",), search=("title", "description", "status", "priority")),
    "calls": Resource(CRMCallLog, required=("direction", "phone_number", "call_time"), search=("direction", "phone_number", "outcome", "notes"), aliases=("call-logs",)),
    "emails": Resource(CRMEmailLog, required=("subject", "to_email"), search=("subject", "body", "from_email", "to_email", "direction"), aliases=("email-logs",)),
    "email-templates": Resource(CRMEmailTemplate, required=("name", "subject", "body"), search=("name", "subject", "body", "entity_type"), owner_field=None),
    "messages": Resource(CRMMessage, required=("entity_type", "entity_id", "channel", "to", "body"), search=("entity_type", "channel", "to", "body", "status", "provider"), owner_field=None),
    "message-templates": Resource(CRMMessageTemplate, required=("name", "channel", "body"), search=("name", "channel", "body", "entity_type"), owner_field=None),
    "calendar-integrations": Resource(CRMCalendarIntegration, required=("user_id", "provider"), search=("provider",), owner_field=None),
    "webhooks": Resource(CRMWebhook, required=("name", "url", "secret"), search=("name", "url"), owner_field=None),
    "webhook-deliveries": Resource(CRMWebhookDelivery, required=("webhook_id", "event_type"), search=("event_type", "status", "response_body"), owner_field=None),
    "enrichment-logs": Resource(CRMEnrichmentLog, required=("entity_type", "entity_id"), search=("entity_type", "provider", "status"), owner_field=None),
    "meetings": Resource(CRMMeeting, required=("title", "start_time", "end_time"), search=("title", "description", "location", "status")),
    "quotations": Resource(CRMQuotation, required=("quote_number", "issue_date", "expiry_date"), search=("quote_number", "status", "currency", "terms", "notes")),
    "products": Resource(CRMProduct, required=("name",), search=("name", "sku", "category", "description", "status"), aliases=("products-services",)),
    "campaigns": Resource(CRMCampaign, required=("name", "campaign_type"), search=("name", "campaign_type", "status", "description")),
    "tickets": Resource(CRMTicket, required=("ticket_number", "subject"), search=("ticket_number", "subject", "description", "priority", "status", "category", "source")),
    "files": Resource(CRMFileAsset, required=("file_name", "original_name", "storage_path"), search=("file_name", "original_name", "mime_type", "visibility"), aliases=("file-assets",)),
    "territories": Resource(CRMTerritory, required=("name",), search=("name", "code", "country", "state", "city", "status"), owner_field=None),
    "owners": Resource(CRMOwner, required=("full_name", "email"), search=("full_name", "email", "phone", "role", "status"), aliases=("users",), owner_field=None),
    "teams": Resource(CRMTeam, required=("name",), search=("name", "team_type", "description", "status")),
    "custom-fields": Resource(CRMCustomField, required=("entity", "field_key", "label"), search=("entity", "field_key", "label", "field_type"), owner_field=None),
    "custom-field-values": Resource(CRMCustomFieldValue, required=("custom_field_id", "entity", "record_id"), search=("entity", "value_text"), owner_field=None),
}

for key, resource in list(RESOURCES.items()):
    for alias in resource.aliases:
        RESOURCES[alias] = resource

CANONICAL_ENTITY_BY_MODEL = {
    resource.model: key
    for key, resource in RESOURCES.items()
    if key not in {"accounts", "opportunities", "products-services", "call-logs", "email-logs", "users"}
}

DETAIL_ENTITY_FIELDS = {
    "leads": "lead_id",
    "contacts": "contact_id",
    "companies": "company_id",
    "deals": "deal_id",
}

TIMELINE_RESOURCES = {
    "activities": "activity_date",
    "notes": "created_at",
    "tasks": "due_date",
    "calls": "call_time",
    "emails": "sent_at",
    "meetings": "start_time",
}

ENTITY_TYPE_BY_CANONICAL = {
    "leads": "lead",
    "contacts": "contact",
    "companies": "account",
    "deals": "deal",
    "quotations": "quotation",
}

ENTITY_FIELD_BY_TYPE = {
    "lead": "lead_id",
    "contact": "contact_id",
    "account": "company_id",
    "deal": "deal_id",
    "quotation": None,
}

DUPLICATE_ENTITY_RESOURCES = {
    "lead": "leads",
    "leads": "leads",
    "contact": "contacts",
    "contacts": "contacts",
    "account": "companies",
    "accounts": "companies",
    "company": "companies",
    "companies": "companies",
}

IMPORTANT_UPDATE_FIELDS = {
    "status",
    "owner_user_id",
    "branch_id",
    "department_id",
    "assigned_team_id",
    "stage_id",
    "pipeline_id",
    "amount",
    "probability",
    "expected_close_date",
    "priority",
    "total_amount",
    "discount_amount",
    "lost_reason",
    "win_reason",
}

RESERVED_QUERY_KEYS = {
    "page",
    "per_page",
    "search",
    "q",
    "sort_by",
    "sort_order",
    "include_deleted",
    "owner_id",
}

CUSTOM_FIELD_SUPPORTED_ENTITIES = {"leads", "contacts", "companies", "deals", "quotations", "tasks"}
CUSTOM_FIELD_TYPES = {
    "text",
    "long_text",
    "number",
    "currency",
    "date",
    "datetime",
    "dropdown",
    "multi_select",
    "checkbox",
    "email",
    "phone",
    "url",
    "user",
    "owner",
}

CRM_WEBHOOK_EVENTS = {
    "lead.created",
    "lead.updated",
    "contact.created",
    "contact.updated",
    "deal.created",
    "deal.updated",
    "deal.stage_changed",
    "quotation.created",
    "quotation.sent",
    "quotation.approved",
    "task.completed",
    "approval.approved",
    "approval.rejected",
}


def _columns(model: type) -> dict[str, Any]:
    return {column.key: column for column in sa_inspect(model).columns}


def _snake(value: str) -> str:
    output = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            output.append("_")
        output.append(char.lower())
    return "".join(output).replace("-", "_")


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {_snake(key): value for key, value in payload.items()}


def _normalize_custom_field_entity(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "lead": "leads",
        "leads": "leads",
        "contact": "contacts",
        "contacts": "contacts",
        "account": "companies",
        "accounts": "companies",
        "company": "companies",
        "companies": "companies",
        "deal": "deals",
        "deals": "deals",
        "opportunity": "deals",
        "opportunities": "deals",
        "quotation": "quotations",
        "quotations": "quotations",
        "quote": "quotations",
        "task": "tasks",
        "tasks": "tasks",
    }
    entity = aliases.get(text, text)
    if entity not in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Custom fields support leads, contacts, accounts, deals, quotations, and tasks")
    return entity


def _normalize_custom_field_type(value: Any) -> str:
    text = str(value or "text").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "textarea": "long_text",
        "longtext": "long_text",
        "date_time": "datetime",
        "select": "dropdown",
        "multiselect": "multi_select",
        "multi-select": "multi_select",
        "boolean": "checkbox",
        "user_lookup": "user",
        "owner_lookup": "owner",
    }
    field_type = aliases.get(text, text)
    if field_type not in CUSTOM_FIELD_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported custom field type: {value}")
    return field_type


def _slug_field_key(value: Any) -> str:
    key = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    key = re.sub(r"_+", "_", key).strip("_")
    if not key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Custom field key is required")
    return key


def _normalize_entity_type(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip().lower().replace("_", "-")
    aliases = {
        "leads": "lead",
        "contacts": "contact",
        "accounts": "account",
        "companies": "account",
        "company": "account",
        "deals": "deal",
        "opportunities": "deal",
        "quotes": "quotation",
        "quotations": "quotation",
    }
    return aliases.get(text, text)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _parse_datetime_param(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid date: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_datetime(value: Any, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        if end_of_day:
            return datetime(value.year, value.month, value.day, 23, 59, 59, tzinfo=timezone.utc)
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return None


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MENTION_PATTERN = re.compile(r"@\[([^\]]+)\]\(user:(\d+)\)")
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


def _split_emails(value: str | None) -> list[str]:
    if not value:
        return []
    emails = [item.strip() for item in re.split(r"[;,]", value) if item.strip()]
    invalid = [email for email in emails if not EMAIL_PATTERN.match(email)]
    if invalid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid email address(es): {', '.join(invalid)}")
    return emails


def _normalize_phone_number(value: str | None) -> str:
    phone = re.sub(r"[\s().-]+", "", value or "")
    if not PHONE_PATTERN.match(phone):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid phone number. Use E.164 format, for example +919876543210.")
    return phone


def _smtp_configured() -> bool:
    return bool(settings.MAIL_SERVER and settings.MAIL_PORT and settings.MAIL_FROM and settings.MAIL_USERNAME and settings.MAIL_PASSWORD)


def _send_smtp_email(*, to: list[str], cc: list[str], bcc: list[str], subject: str, body: str) -> str:
    if not _smtp_configured():
        raise RuntimeError("SMTP credentials are not configured.")
    message = EmailMessage()
    message["From"] = settings.MAIL_FROM
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body)
    message.add_alternative(body, subtype="html")
    recipients = to + cc + bcc
    smtp_cls = smtplib.SMTP_SSL if settings.MAIL_SSL_TLS else smtplib.SMTP
    with smtp_cls(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=15) as smtp:
        if settings.MAIL_STARTTLS and not settings.MAIL_SSL_TLS:
            smtp.starttls()
        smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
        response = smtp.send_message(message, to_addrs=recipients)
    return f"smtp:{datetime.now(timezone.utc).timestamp()}" if not response else f"smtp-partial:{datetime.now(timezone.utc).timestamp()}"


def _send_smtp_email_with_attachment(*, to: list[str], cc: list[str], bcc: list[str], subject: str, body: str, attachment_path: str, attachment_name: str) -> str:
    if not _smtp_configured():
        raise RuntimeError("SMTP credentials are not configured.")
    message = EmailMessage()
    message["From"] = settings.MAIL_FROM
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body)
    message.add_alternative(body, subtype="html")
    with open(attachment_path, "rb") as handle:
        message.add_attachment(handle.read(), maintype="application", subtype="pdf", filename=attachment_name)
    recipients = to + cc + bcc
    smtp_cls = smtplib.SMTP_SSL if settings.MAIL_SSL_TLS else smtplib.SMTP
    with smtp_cls(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=15) as smtp:
        if settings.MAIL_STARTTLS and not settings.MAIL_SSL_TLS:
            smtp.starttls()
        smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
    response = smtp.send_message(message, to_addrs=recipients)
    return f"smtp:{datetime.now(timezone.utc).timestamp()}" if not response else f"smtp-partial:{datetime.now(timezone.utc).timestamp()}"


class CRMMessageProvider:
    name = "mock"

    def send(self, *, channel: str, to: str, body: str) -> tuple[str, str | None]:
        raise NotImplementedError


class MockCRMMessageProvider(CRMMessageProvider):
    name = "mock"

    def send(self, *, channel: str, to: str, body: str) -> tuple[str, str | None]:
        return "sent", f"mock-{channel}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"


class ConfiguredCRMMessageProvider(CRMMessageProvider):
    def __init__(self, name: str, configured: bool) -> None:
        self.name = name
        self.configured = configured

    def send(self, *, channel: str, to: str, body: str) -> tuple[str, str | None]:
        if not self.configured:
            raise RuntimeError(f"{self.name} credentials are not configured.")
        raise RuntimeError(f"{self.name} sending adapter is not installed.")


def _message_provider(channel: str) -> CRMMessageProvider:
    channel = channel.lower()
    configured_name = (settings.CRM_WHATSAPP_PROVIDER if channel == "whatsapp" else settings.CRM_SMS_PROVIDER) or settings.CRM_MESSAGE_PROVIDER
    provider_name = str(configured_name or "mock").strip().lower()
    if provider_name in {"", "mock", "dev", "local"}:
        return MockCRMMessageProvider()
    configured = False
    if channel == "sms":
        configured = bool(settings.CRM_SMS_API_KEY and settings.CRM_SMS_API_SECRET)
    elif channel == "whatsapp":
        configured = bool(settings.CRM_WHATSAPP_ACCESS_TOKEN and settings.CRM_WHATSAPP_PHONE_NUMBER_ID)
    return ConfiguredCRMMessageProvider(provider_name, configured)


def _calendar_fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_calendar_token(value: str | None) -> str | None:
    if not value:
        return None
    return _calendar_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt_calendar_token(value: str | None) -> str | None:
    if not value:
        return None
    return _calendar_fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def _normalize_calendar_provider(provider: str | None) -> str:
    normalized = str(provider or "").strip().lower().replace("_", "-")
    aliases = {
        "google-calendar": "google",
        "google": "google",
        "outlook": "outlook",
        "microsoft": "outlook",
        "microsoft-outlook": "outlook",
        "office365": "outlook",
        "mock": "mock",
        "dev": "mock",
    }
    result = aliases.get(normalized)
    if not result:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="provider must be google, outlook, or mock")
    return result


class CRMCalendarProvider:
    name = "mock"

    def sync_meeting(self, *, integration: CRMCalendarIntegration, meeting: CRMMeeting) -> str:
        raise NotImplementedError


class MockCRMCalendarProvider(CRMCalendarProvider):
    name = "mock"

    def sync_meeting(self, *, integration: CRMCalendarIntegration, meeting: CRMMeeting) -> str:
        return meeting.external_event_id or f"mock-calendar-{meeting.id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"


class PlaceholderCRMCalendarProvider(CRMCalendarProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    def sync_meeting(self, *, integration: CRMCalendarIntegration, meeting: CRMMeeting) -> str:
        token = _decrypt_calendar_token(integration.access_token_encrypted)
        if not token:
            raise RuntimeError(f"{self.name.title()} Calendar access token is not configured.")
        raise RuntimeError(f"{self.name.title()} Calendar OAuth adapter is not configured. TODO: exchange/refresh tokens and call the provider event API with minimal calendar event scopes.")


def _calendar_provider(provider: str) -> CRMCalendarProvider:
    provider = _normalize_calendar_provider(provider)
    if provider == "mock":
        return MockCRMCalendarProvider()
    return PlaceholderCRMCalendarProvider(provider)


def _serialize_calendar_integration(row: CRMCalendarIntegration) -> dict[str, Any]:
    item = _serialize(row)
    item.pop("access_token_encrypted", None)
    item.pop("refresh_token_encrypted", None)
    item.pop("accessTokenEncrypted", None)
    item.pop("refreshTokenEncrypted", None)
    item["connected"] = bool(row.is_active and row.access_token_encrypted)
    item["scopes"] = ["calendar.events"]
    return item


def _active_calendar_integration(db: Session, organization_id: int, user_id: int, provider: str | None = None) -> CRMCalendarIntegration | None:
    query = (
        db.query(CRMCalendarIntegration)
        .filter(
            CRMCalendarIntegration.organization_id == organization_id,
            CRMCalendarIntegration.user_id == user_id,
            CRMCalendarIntegration.is_active.is_(True),
            CRMCalendarIntegration.deleted_at.is_(None),
        )
    )
    if provider:
        query = query.filter(CRMCalendarIntegration.provider == _normalize_calendar_provider(provider))
    return query.order_by(desc(CRMCalendarIntegration.updated_at), desc(CRMCalendarIntegration.created_at), desc(CRMCalendarIntegration.id)).first()


def _sync_meeting_to_calendar(db: Session, organization_id: int, meeting: CRMMeeting, current_user: User, provider: str | None = None) -> CRMMeeting:
    integration = _active_calendar_integration(db, organization_id, current_user.id, provider)
    if not integration:
        meeting.sync_status = "not_configured"
        meeting.external_provider = _normalize_calendar_provider(provider) if provider else None
        meeting.updated_by_user_id = current_user.id
        return meeting
    adapter = _calendar_provider(integration.provider)
    meeting.external_provider = integration.provider
    try:
        meeting.external_event_id = adapter.sync_meeting(integration=integration, meeting=meeting)
        meeting.sync_status = "synced"
        meeting.last_synced_at = datetime.now(timezone.utc)
    except Exception as exc:
        meeting.sync_status = "failed"
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type="meeting",
            entity_id=meeting.id,
            activity_type="calendar_sync_failed",
            title="Calendar sync failed",
            body=str(exc),
            user_id=current_user.id,
            metadata={"provider": integration.provider, "meetingId": meeting.id},
        )
    meeting.updated_by_user_id = current_user.id
    return meeting


def _normalize_webhook_events(events: list[str] | None) -> list[str]:
    normalized = sorted({str(event or "").strip().lower() for event in (events or []) if str(event or "").strip()})
    invalid = [event for event in normalized if event not in CRM_WEBHOOK_EVENTS]
    if invalid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported webhook event(s): {', '.join(invalid)}")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one webhook event is required")
    return normalized


def _validate_webhook_url(url: str | None) -> str:
    value = str(url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Webhook URL must be an absolute http or https URL")
    if settings.ENVIRONMENT.lower() in {"production", "prod"} and settings.CRM_WEBHOOK_BLOCK_PRIVATE_URLS:
        hostname = parsed.hostname or ""
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Private, localhost, and reserved webhook URLs are not allowed in production")
        except ValueError:
            if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Private, localhost, and reserved webhook URLs are not allowed in production")
    return value


def _mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    return f"{secret[:4]}...{secret[-4:]}" if len(secret) > 10 else "********"


def _serialize_webhook(row: CRMWebhook) -> dict[str, Any]:
    item = _serialize(row)
    item["secret"] = _mask_secret(row.secret)
    item["events"] = row.events or []
    item["isActive"] = bool(row.is_active)
    return item


def _webhook_signature(secret: str, body: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _webhook_payload(event_type: str, organization_id: int, record: dict[str, Any] | None, user_id: int | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "eventType": event_type,
        "organizationId": organization_id,
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "record": record or {},
        "actorUserId": user_id,
        "data": extra or {},
    }


def _deliver_webhook(db: Session, webhook: CRMWebhook, delivery: CRMWebhookDelivery) -> CRMWebhookDelivery:
    body = json.dumps(delivery.payload or {}, separators=(",", ":"), sort_keys=True, default=str)
    headers = {
        "Content-Type": "application/json",
        "X-CRM-Event": delivery.event_type,
        "X-CRM-Delivery": str(delivery.id),
        "X-CRM-Signature": _webhook_signature(webhook.secret, body),
    }
    now = datetime.now(timezone.utc)
    delivery.attempt_count = int(delivery.attempt_count or 0) + 1
    delivery.updated_at = now
    try:
        response = httpx.post(webhook.url, content=body, headers=headers, timeout=10)
        delivery.response_code = response.status_code
        delivery.response_body = response.text[:4000] if response.text else None
        delivery.status = "delivered" if 200 <= response.status_code < 300 else "failed"
    except Exception as exc:
        delivery.response_code = None
        delivery.response_body = str(exc)[:4000]
        delivery.status = "failed"
    if delivery.status == "failed" and delivery.attempt_count < 5:
        delay_seconds = min(3600, 60 * (2 ** (delivery.attempt_count - 1)))
        delivery.next_retry_at = datetime.fromtimestamp(now.timestamp() + delay_seconds, tz=timezone.utc)
    else:
        delivery.next_retry_at = None
    return delivery


def _enqueue_webhook_event(db: Session, organization_id: int, event_type: str, record: dict[str, Any] | None, user_id: int | None = None, extra: dict[str, Any] | None = None) -> list[CRMWebhookDelivery]:
    if event_type not in CRM_WEBHOOK_EVENTS:
        return []
    webhooks = (
        db.query(CRMWebhook)
        .filter(CRMWebhook.organization_id == organization_id, CRMWebhook.is_active.is_(True), CRMWebhook.deleted_at.is_(None))
        .all()
    )
    deliveries: list[CRMWebhookDelivery] = []
    payload = _webhook_payload(event_type, organization_id, record, user_id, extra)
    for webhook in webhooks:
        if event_type not in (webhook.events or []):
            continue
        delivery = CRMWebhookDelivery(
            organization_id=organization_id,
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload,
            status="pending",
            attempt_count=0,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
        )
        db.add(delivery)
        db.flush()
        _deliver_webhook(db, webhook, delivery)
        deliveries.append(delivery)
    return deliveries


def _retry_due_webhook_deliveries(db: Session, organization_id: int, webhook_id: int | None = None) -> int:
    now = datetime.now(timezone.utc)
    query = (
        db.query(CRMWebhookDelivery)
        .join(CRMWebhook, CRMWebhook.id == CRMWebhookDelivery.webhook_id)
        .filter(
            CRMWebhookDelivery.organization_id == organization_id,
            CRMWebhookDelivery.status == "failed",
            CRMWebhookDelivery.next_retry_at.is_not(None),
            CRMWebhookDelivery.next_retry_at <= now,
            CRMWebhookDelivery.deleted_at.is_(None),
            CRMWebhook.is_active.is_(True),
            CRMWebhook.deleted_at.is_(None),
        )
    )
    if webhook_id:
        query = query.filter(CRMWebhookDelivery.webhook_id == webhook_id)
    retried = 0
    for delivery in query.order_by(asc(CRMWebhookDelivery.next_retry_at)).limit(20).all():
        _deliver_webhook(db, delivery.webhook, delivery)
        retried += 1
    return retried


def _event_type_for_create(canonical: str, item: dict[str, Any]) -> str | None:
    if canonical == "leads":
        return "lead.created"
    if canonical == "contacts":
        return "contact.created"
    if canonical == "deals":
        return "deal.created"
    if canonical == "quotations":
        status_value = str(item.get("status") or "").lower()
        return "quotation.sent" if status_value == "sent" else "quotation.created"
    return None


def _event_types_for_update(canonical: str, before: dict[str, Any], record: Any, data: dict[str, Any]) -> list[str]:
    events: list[str] = []
    if canonical == "leads":
        events.append("lead.updated")
    elif canonical == "contacts":
        events.append("contact.updated")
    elif canonical == "deals":
        events.append("deal.updated")
        if "stage_id" in data and before.get("stage_id") != getattr(record, "stage_id", None):
            events.append("deal.stage_changed")
    elif canonical == "quotations":
        status_value = str(getattr(record, "status", "") or "").lower()
        previous_status = str(before.get("status") or "").lower()
        if status_value == "sent" and previous_status != "sent":
            events.append("quotation.sent")
        if status_value == "approved" and previous_status != "approved":
            events.append("quotation.approved")
    elif canonical == "tasks":
        status_value = str(getattr(record, "status", "") or "").lower()
        previous_status = str(before.get("status") or "").lower()
        if status_value in {"done", "completed", "complete"} and previous_status not in {"done", "completed", "complete"}:
            events.append("task.completed")
    return events


def _deal_status(deal: CRMDeal) -> str:
    return _deal_status_key(getattr(deal, "status", None))


def _deal_source(deal: CRMDeal) -> str:
    return str(getattr(deal, "source", None) or deal.lead_source or "Unknown").strip() or "Unknown"


def _deal_lost_reason(deal: CRMDeal) -> str:
    return str(getattr(deal, "lost_reason", None) or deal.loss_reason or "Unspecified").strip() or "Unspecified"


def _report_datetime(value: Any) -> datetime | None:
    parsed = _as_datetime(value)
    if parsed and parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _deal_closed_datetime(deal: CRMDeal) -> datetime | None:
    status_key = _deal_status(deal)
    if status_key == "won":
        return _report_datetime(getattr(deal, "won_at", None)) or _report_datetime(getattr(deal, "closed_at", None)) or _report_datetime(deal.actual_close_date)
    if status_key == "lost":
        return _report_datetime(getattr(deal, "lost_at", None)) or _report_datetime(getattr(deal, "closed_at", None)) or _report_datetime(deal.actual_close_date)
    return _report_datetime(getattr(deal, "closed_at", None)) or _report_datetime(deal.actual_close_date)


def _deal_report_datetime(deal: CRMDeal) -> datetime:
    return _deal_closed_datetime(deal) or _report_datetime(deal.created_at) or datetime.now(timezone.utc)


def _month_key(value: datetime) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _month_label(value: str) -> str:
    return datetime.strptime(value, "%Y-%m").strftime("%b %Y")


def _month_keys_between(start: datetime, end: datetime) -> list[str]:
    keys: list[str] = []
    year = start.year
    month = start.month
    while (year, month) <= (end.year, end.month):
        keys.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return keys


def _default_report_range() -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc)
    month = today.month - 11
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


def _parse_report_range(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    default_start, default_end = _default_report_range()
    start = _parse_datetime_param(start_date, default_start) if start_date else default_start
    end = _parse_datetime_param(end_date, default_end) if end_date else default_end
    if len(start_date or "") <= 10:
        start = datetime(start.year, start.month, start.day, tzinfo=start.tzinfo or timezone.utc)
    if len(end_date or "") <= 10:
        end = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=end.tzinfo or timezone.utc)
    if start > end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="startDate must be before endDate")
    return start, end


def _deal_amount(deal: CRMDeal) -> float:
    try:
        return float(deal.amount or 0)
    except (TypeError, ValueError, ArithmeticError):
        return 0.0


def _rate(won: int, lost: int) -> float:
    total = won + lost
    return round((won / total) * 100, 2) if total else 0.0


def _owner_names(db: Session, owner_ids: set[int | None]) -> dict[int, str]:
    ids = [int(owner_id) for owner_id in owner_ids if owner_id]
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    return {user.id: user.email for user in users}


def _pipeline_names(db: Session, organization_id: int, pipeline_ids: set[int | None]) -> dict[int, str]:
    ids = [int(pipeline_id) for pipeline_id in pipeline_ids if pipeline_id]
    if not ids:
        return {}
    pipelines = _base_query(db, _get_resource("pipelines"), organization_id).filter(CRMPipeline.id.in_(ids)).all()
    return {pipeline.id: pipeline.name for pipeline in pipelines}


def _filtered_report_deals(
    db: Session,
    organization_id: int,
    start: datetime,
    end: datetime,
    owner_id: int | None = None,
    pipeline_id: int | None = None,
    current_user: User | None = None,
) -> list[CRMDeal]:
    query = _base_query(db, _get_resource("deals"), organization_id)
    if current_user is not None:
        query = _apply_record_visibility(query, _get_resource("deals"), current_user, db)
    if owner_id:
        query = query.filter(CRMDeal.owner_user_id == owner_id)
    if pipeline_id:
        query = query.filter(CRMDeal.pipeline_id == pipeline_id)
    rows = query.all()
    return [deal for deal in rows if start <= _deal_report_datetime(deal) <= end]


def _closed_outcomes(deals: list[CRMDeal]) -> list[CRMDeal]:
    return [deal for deal in deals if _deal_status(deal) in {"won", "lost"}]


def _bucket_outcomes(deals: list[CRMDeal], key_fn) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for deal in _closed_outcomes(deals):
        key = str(key_fn(deal) or "Unknown")
        bucket = buckets.setdefault(key, {"key": key, "won": 0, "lost": 0, "wonRevenue": 0.0, "lostAmount": 0.0})
        amount = _deal_amount(deal)
        if _deal_status(deal) == "won":
            bucket["won"] += 1
            bucket["wonRevenue"] += amount
        else:
            bucket["lost"] += 1
            bucket["lostAmount"] += amount
    rows = []
    for bucket in buckets.values():
        bucket["total"] = bucket["won"] + bucket["lost"]
        bucket["winRate"] = _rate(bucket["won"], bucket["lost"])
        rows.append(bucket)
    return sorted(rows, key=lambda item: (-int(item["total"]), str(item["key"])))


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _competitor_breakdown(db: Session, organization_id: int, deal_ids: list[int]) -> list[dict[str, Any]]:
    if not deal_ids:
        return []
    fields = (
        _base_query(db, _get_resource("custom-fields"), organization_id)
        .filter(CRMCustomField.entity.in_(["deals", "deal"]), CRMCustomField.field_key.in_(["competitor", "competitor_name", "competitors"]))
        .all()
    )
    field_ids = [field.id for field in fields]
    if not field_ids:
        return []
    values = (
        _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(CRMCustomFieldValue.custom_field_id.in_(field_ids), CRMCustomFieldValue.record_id.in_(deal_ids))
        .all()
    )
    counts: dict[str, int] = {}
    for row in values:
        raw = row.value_text or row.value_json or row.value_number or row.value_date
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            name = str(item or "").strip()
            if name:
                counts[name] = counts.get(name, 0) + 1
    return [{"competitor": name, "count": count} for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]]


def _coerce_value(column: Any, value: Any) -> Any:
    if value == "":
        return None
    column_type = column.type
    try:
        if isinstance(column_type, Integer) and value is not None:
            return int(value)
        if isinstance(column_type, Numeric) and value is not None:
            return Decimal(str(value))
        if isinstance(column_type, Boolean) and value is not None:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
        if isinstance(column_type, DateTime) and isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(column_type, Date) and not isinstance(column_type, DateTime) and isinstance(value, str):
            return date.fromisoformat(value[:10])
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid value for {column.key}") from exc
    return value


def _organization_id(db: Session, user: User) -> int:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if employee and employee.branch_id:
        branch = db.query(Branch).filter(Branch.id == employee.branch_id).first()
        if branch:
            return branch.company_id
    return 1


def _crm_user_organization_id(db: Session, user: User) -> int:
    return _organization_id(db, user)


def _crm_role_key(user: User) -> str:
    role_name = str(user.role.name if user.role else "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "crm_admin": "admin",
        "sales_admin": "admin",
        "sales_manager": "manager",
        "crm_manager": "manager",
        "sales_executive": "executive",
        "crm_executive": "executive",
        "viewer": "viewer",
        "crm_viewer": "viewer",
    }
    return aliases.get(role_name, role_name)


def _crm_user_scope(db: Session, user: User) -> dict[str, Any]:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    team_ids = [
        row.team_id
        for row in db.query(CRMOwner)
        .filter(CRMOwner.user_id == user.id, CRMOwner.status == "Active", CRMOwner.deleted_at.is_(None))
        .all()
        if row.team_id
    ]
    return {
        "role": _crm_role_key(user),
        "branch_id": employee.branch_id if employee else None,
        "department_id": employee.department_id if employee else None,
        "team_ids": sorted(set(team_ids)),
    }


def _crm_has_full_visibility(user: User) -> bool:
    return bool(user.is_superuser or _crm_role_key(user) in {"admin", "viewer", "super_admin"})


def _crm_can_assign_beyond_self(user: User) -> bool:
    return bool(user.is_superuser or _crm_role_key(user) in {"admin", "manager", "super_admin"})


def _apply_record_visibility(query, resource: Resource, current_user: User, db: Session):
    if _crm_has_full_visibility(current_user):
        return query
    columns = _columns(resource.model)
    clauses = []
    scope = _crm_user_scope(db, current_user)
    if resource.owner_field and resource.owner_field in columns:
        clauses.append(getattr(resource.model, resource.owner_field) == current_user.id)
    if "created_by_user_id" in columns:
        clauses.append(getattr(resource.model, "created_by_user_id") == current_user.id)
    if scope["branch_id"] and "branch_id" in columns:
        clauses.append(getattr(resource.model, "branch_id") == scope["branch_id"])
    if scope["department_id"] and "department_id" in columns:
        clauses.append(getattr(resource.model, "department_id") == scope["department_id"])
    if scope["team_ids"] and "assigned_team_id" in columns:
        clauses.append(getattr(resource.model, "assigned_team_id").in_(scope["team_ids"]))
    if scope["role"] == "manager" and not clauses:
        return query
    return query.filter(or_(*clauses)) if clauses else query.filter(False)


def _assert_record_visible(db: Session, resource: Resource, record_id: int, organization_id: int, current_user: User, include_deleted: bool = False) -> None:
    visible = (
        _apply_record_visibility(_base_query(db, resource, organization_id, include_deleted), resource, current_user, db)
        .filter(resource.model.id == record_id)
        .first()
    )
    if not visible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CRM record is outside your permitted visibility scope")


def _assert_write_scope(resource: Resource, data: dict[str, Any], current_user: User, db: Session) -> None:
    if _crm_can_assign_beyond_self(current_user):
        return
    columns = _columns(resource.model)
    if resource.owner_field and resource.owner_field in columns and data.get(resource.owner_field) not in {None, current_user.id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sales executives can assign records only to themselves")
    scope = _crm_user_scope(db, current_user)
    for field in ("branch_id", "department_id"):
        if field in columns and data.get(field) and scope.get(field) and data[field] != scope[field]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CRM record is outside your branch or department scope")


def _create_crm_audit_log(
    db: Session,
    *,
    user_id: int | None,
    entity_type: str,
    entity_id: int | None,
    action: str,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    description: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            method="CRM",
            endpoint=f"/crm/{entity_type}/{entity_id}" if entity_id else f"/crm/{entity_type}",
            entity_type=f"crm_{entity_type}",
            entity_id=entity_id,
            action=action.upper(),
            old_values=json.dumps(_json_ready(old_values or {})),
            new_values=json.dumps(_json_ready(new_values or {})),
            description=description,
        )
    )


def _extract_mention_user_ids(payload: dict[str, Any]) -> list[int]:
    raw_mentions = []
    for key in ("mentions", "mentionIds", "mention_ids", "mentionedUserIds", "mentioned_user_ids"):
        value = payload.pop(key, None)
        if value:
            raw_mentions.append(value)
    ids: list[int] = []
    for value in raw_mentions:
        values = value if isinstance(value, list) else [value]
        for item in values:
            mention_id = item.get("id") if isinstance(item, dict) else item
            try:
                parsed = int(mention_id)
            except (TypeError, ValueError):
                continue
            if parsed not in ids:
                ids.append(parsed)
    return ids


def _mention_ids_from_text(text: str | None) -> list[int]:
    ids: list[int] = []
    for match in MENTION_PATTERN.finditer(text or ""):
        user_id = int(match.group(2))
        if user_id not in ids:
            ids.append(user_id)
    return ids


def _user_is_in_organization(db: Session, user_id: int, organization_id: int) -> bool:
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        return False
    return _crm_user_organization_id(db, user) == organization_id


def _mention_action_url(entity_type: str | None, entity_id: int | None) -> str:
    route = {
        "lead": "leads",
        "contact": "contacts",
        "account": "accounts",
        "deal": "deals",
        "quotation": "quotations",
    }.get(entity_type or "", entity_type or "records")
    return f"/crm/{route}/{entity_id}" if entity_id else "/crm"


def _create_crm_mentions(
    db: Session,
    *,
    organization_id: int,
    note_id: int | None = None,
    activity_id: int | None = None,
    mentioned_user_ids: list[int],
    mentioned_by: int | None,
    entity_type: str | None,
    entity_id: int | None,
    record_title: str,
) -> None:
    for mentioned_user_id in mentioned_user_ids:
        if mentioned_user_id == mentioned_by:
            continue
        if not _user_is_in_organization(db, mentioned_user_id, organization_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mentioned users must belong to the same organization")
        db.add(
            CRMNoteMention(
                organization_id=organization_id,
                note_id=note_id,
                activity_id=activity_id,
                mentioned_user_id=mentioned_user_id,
                mentioned_by=mentioned_by,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        db.add(
            Notification(
                company_id=organization_id,
                user_id=mentioned_user_id,
                title="You were mentioned in CRM",
                message=f"You were mentioned on {record_title}.",
                module="crm",
                event_type="crm_mention",
                related_entity_type=entity_type,
                related_entity_id=entity_id,
                action_url=_mention_action_url(entity_type, entity_id),
                priority="normal",
                channels=["in_app"],
            )
        )


def _handle_mentions_for_record(db: Session, resource: Resource, record: Any, payload_ids: list[int], organization_id: int, current_user: User) -> None:
    if resource.model not in {CRMNote, CRMActivity}:
        return
    item = _serialize(record)
    entity_type, entity_id = _linked_entity_from_data(item)
    if resource.model is CRMActivity and (not entity_type or not entity_id):
        entity_type = _normalize_entity_type(getattr(record, "entity_type", None))
        entity_id = getattr(record, "entity_id", None)
    text = "\n".join(str(value or "") for value in (getattr(record, "body", None), getattr(record, "description", None), getattr(record, "subject", None)))
    mention_ids = []
    for user_id in payload_ids + _mention_ids_from_text(text):
        if user_id not in mention_ids:
            mention_ids.append(user_id)
    if not mention_ids:
        return
    record_title = _record_title_for_mention(db, organization_id, entity_type, entity_id)
    _create_crm_mentions(
        db,
        organization_id=organization_id,
        note_id=record.id if resource.model is CRMNote else None,
        activity_id=record.id if resource.model is CRMActivity else None,
        mentioned_user_ids=mention_ids,
        mentioned_by=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        record_title=record_title,
    )


def _record_title_for_mention(db: Session, organization_id: int, entity_type: str | None, entity_id: int | None) -> str:
    if not entity_type or not entity_id:
        return "a CRM record"
    resource_name = {
        "lead": "leads",
        "contact": "contacts",
        "account": "companies",
        "deal": "deals",
        "quotation": "quotations",
    }.get(entity_type)
    if not resource_name:
        return "a CRM record"
    try:
        record = _get_record(db, _get_resource(resource_name), int(entity_id), organization_id)
    except HTTPException:
        return "a CRM record"
    return _record_label(record, resource_name)


def _get_resource(entity: str) -> Resource:
    resource = RESOURCES.get(entity)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown CRM entity: {entity}")
    return resource


def _canonical_entity(entity: str) -> str:
    resource = _get_resource(entity)
    return CANONICAL_ENTITY_BY_MODEL.get(resource.model, entity)


def _base_query(db: Session, resource: Resource, organization_id: int, include_deleted: bool = False):
    model = resource.model
    columns = _columns(model)
    query = db.query(model)
    if "organization_id" in columns:
        query = query.filter(model.organization_id == organization_id)
    if not include_deleted and "deleted_at" in columns:
        query = query.filter(model.deleted_at.is_(None))
    return query


def _apply_filters(query, resource: Resource, request: Request, owner_id: int | None):
    model = resource.model
    columns = _columns(model)
    if owner_id is not None and resource.owner_field and resource.owner_field in columns:
        query = query.filter(getattr(model, resource.owner_field) == owner_id)

    for key, value in request.query_params.items():
        if key in RESERVED_QUERY_KEYS or value in {"", "all"}:
            continue
        column_key = _snake(key)
        if column_key in columns:
            query = query.filter(getattr(model, column_key) == _coerce_value(columns[column_key], value))
    return query


def _apply_search(query, resource: Resource, search: str | None):
    if not search:
        return query
    model = resource.model
    clauses = []
    for key in resource.search:
        if hasattr(model, key):
            clauses.append(getattr(model, key).ilike(f"%{search}%"))
    return query.filter(or_(*clauses)) if clauses else query


def _normalize_rule_values(value: Any) -> list[str]:
    if value in {None, ""}:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip().lower() for item in values if str(item or "").strip()]


def _record_company_size(record: Any) -> str:
    raw = getattr(record, "employee_count", None)
    if raw is None:
        return ""
    count = int(raw or 0)
    if count < 50:
        return "small"
    if count < 250:
        return "mid_market"
    if count < 1000:
        return "enterprise"
    return "strategic"


def _record_rule_value(record: Any, field: str) -> str:
    key = _snake(field)
    aliases = {
        "postal_code": ("postal_code", "pincode", "zip_code"),
        "zip": ("postal_code", "pincode", "zip_code"),
        "company_size": ("company_size",),
    }
    if key == "company_size":
        return _record_company_size(record)
    for candidate in aliases.get(key, (key,)):
        if hasattr(record, candidate):
            return str(getattr(record, candidate) or "").strip().lower()
    return ""


def _rule_matches_record(record: Any, rules: dict[str, Any] | None) -> bool:
    if not rules:
        return True
    standard_fields = {
        "country": "country",
        "state": "state",
        "city": "city",
        "postalCode": "postal_code",
        "postal_code": "postal_code",
        "industry": "industry",
        "companySize": "company_size",
        "company_size": "company_size",
    }
    for rule_key, record_field in standard_fields.items():
        expected = _normalize_rule_values(rules.get(rule_key))
        if not expected:
            continue
        actual = _record_rule_value(record, record_field)
        if actual not in expected:
            return False
    custom_rules = rules.get("customRules") or rules.get("custom") or []
    if isinstance(custom_rules, dict):
        custom_rules = [custom_rules]
    for rule in custom_rules if isinstance(custom_rules, list) else []:
        if not isinstance(rule, dict):
            continue
        field = str(rule.get("field") or "")
        operator = str(rule.get("operator") or "equals").lower()
        expected_values = _normalize_rule_values(rule.get("value") if "value" in rule else rule.get("values"))
        actual = _record_rule_value(record, field)
        if operator in {"equals", "eq", "is"} and expected_values and actual not in expected_values:
            return False
        if operator in {"contains"} and expected_values and not any(value in actual for value in expected_values):
            return False
        if operator in {"not_equals", "neq"} and expected_values and actual in expected_values:
            return False
    return True


def _territory_users(db: Session, territory_id: int, organization_id: int) -> list[CRMTerritoryUser]:
    return (
        db.query(CRMTerritoryUser)
        .filter(CRMTerritoryUser.organization_id == organization_id, CRMTerritoryUser.territory_id == territory_id)
        .order_by(asc(CRMTerritoryUser.id))
        .all()
    )


def _find_matching_territory(db: Session, organization_id: int, record: Any) -> CRMTerritory | None:
    territories = (
        _base_query(db, _get_resource("territories"), organization_id)
        .filter(CRMTerritory.is_active.is_(True))
        .order_by(asc(CRMTerritory.priority), asc(CRMTerritory.id))
        .all()
    )
    for territory in territories:
        rules = territory.rules_json or {}
        legacy_rules = {
            "country": territory.country,
            "state": territory.state,
            "city": territory.city,
        }
        merged = {key: value for key, value in legacy_rules.items() if value}
        if isinstance(rules, dict):
            merged.update(rules)
        if _rule_matches_record(record, merged):
            return territory
    return None


def _apply_territory_assignment(db: Session, organization_id: int, record: Any, override_manual: bool = False, override_owner: bool = False) -> bool:
    if not isinstance(record, (CRMLead, CRMCompany, CRMDeal)):
        return False
    if getattr(record, "territory_id", None) and not override_manual:
        return False
    match_record = record
    if isinstance(record, CRMDeal) and record.company_id:
        company = _base_query(db, _get_resource("companies"), organization_id).filter(CRMCompany.id == record.company_id).first()
        if company:
            match_record = company
    territory = _find_matching_territory(db, organization_id, match_record)
    if not territory:
        return False
    record.territory_id = territory.id
    assigned_users = _territory_users(db, territory.id, organization_id)
    if assigned_users and (override_manual or override_owner or not getattr(record, "owner_user_id", None)):
        record.owner_user_id = assigned_users[0].user_id
    elif territory.owner_user_id and (override_manual or override_owner or not getattr(record, "owner_user_id", None)):
        record.owner_user_id = territory.owner_user_id
    return True


def _serialize_territory(territory: CRMTerritory, db: Session | None = None, organization_id: int | None = None) -> dict[str, Any]:
    item = _serialize(territory)
    item["rules"] = territory.rules_json or {}
    item["isActive"] = bool(territory.is_active)
    if db is not None:
        org_id = organization_id or territory.organization_id or 1
        item["users"] = [{"id": row.id, "userId": row.user_id, "territoryId": row.territory_id} for row in _territory_users(db, territory.id, org_id)]
    return item


def _serialize(record: Any) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for column in sa_inspect(record.__class__).columns:
        value = getattr(record, column.key)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        item[column.key] = value

    aliases = {
        "organization_id": "organizationId",
        "owner_user_id": "ownerId",
        "branch_id": "branchId",
        "department_id": "departmentId",
        "assigned_team_id": "assignedTeamId",
        "company_id": "companyId",
        "contact_id": "contactId",
        "lead_id": "leadId",
        "deal_id": "dealId",
        "pipeline_id": "pipelineId",
        "stage_id": "stageId",
        "author_user_id": "authorId",
        "entity_type": "entityType",
        "entity_id": "entityId",
        "activity_type": "activityType",
        "activity_date": "activityDate",
        "metadata_json": "metadata",
        "old_values_json": "oldValues",
        "new_values_json": "newValues",
        "applied_fields_json": "appliedFields",
        "created_by_user_id": "createdBy",
        "updated_by_user_id": "updatedBy",
        "created_at": "createdAt",
        "updated_at": "updatedAt",
        "deleted_at": "deletedAt",
        "lead_score": "leadScore",
        "lead_score_label": "scoreLabel",
        "lead_score_mode": "leadScoreMode",
        "last_score_calculated_at": "lastScoreCalculatedAt",
        "pdf_url": "pdfUrl",
        "pdf_file_name": "pdfFileName",
        "pdf_status": "pdfStatus",
        "pdf_generated_at": "pdfGeneratedAt",
        "pdf_generated_by_user_id": "pdfGeneratedBy",
        "provider_message_id": "providerMessageId",
        "sent_by_user_id": "sentBy",
        "sent_at": "sentAt",
        "template_id": "templateId",
        "failure_reason": "failureReason",
        "user_id": "userId",
        "access_token_encrypted": "accessTokenEncrypted",
        "refresh_token_encrypted": "refreshTokenEncrypted",
        "expires_at": "expiresAt",
        "external_provider": "externalProvider",
        "external_event_id": "externalEventId",
        "sync_status": "syncStatus",
        "last_synced_at": "lastSyncedAt",
        "webhook_id": "webhookId",
        "event_type": "eventType",
        "response_code": "responseCode",
        "response_body": "responseBody",
        "attempt_count": "attemptCount",
        "next_retry_at": "nextRetryAt",
        "is_active": "isActive",
        "won_at": "wonAt",
        "lost_at": "lostAt",
        "closed_at": "closedAt",
        "lost_reason": "lostReason",
        "win_reason": "winReason",
        "expected_close_date": "expectedCloseDate",
        "actual_close_date": "actualCloseDate",
        "expected_revenue": "expectedRevenue",
        "lead_source": "leadSource",
        "quote_number": "quoteNumber",
        "issue_date": "issueDate",
        "expiry_date": "expiryDate",
        "subtotal": "subtotal",
        "discount_amount": "discountAmount",
        "tax_amount": "taxAmount",
        "total_amount": "totalAmount",
        "territory_id": "territoryId",
        "rules_json": "rules",
        "priority": "priority",
        "is_active": "isActive",
        "entity": "entityType",
        "field_name": "fieldName",
        "field_key": "fieldKey",
        "field_type": "fieldType",
        "options_json": "options",
        "is_required": "isRequired",
        "is_unique": "isUnique",
        "is_visible": "isVisible",
        "is_filterable": "isFilterable",
        "position": "displayOrder",
        "custom_field_id": "customFieldId",
        "record_id": "recordId",
        "deal_id": "dealId",
        "contact_id": "contactId",
        "influence_level": "influenceLevel",
        "is_primary": "isPrimary",
    }
    for source, target in aliases.items():
        if source in item:
            item[target] = item[source]
    if "lead_source" in item and not item.get("source"):
        item["source"] = item["lead_source"]
    return item


def _serialize_deal_contact(link: CRMDealContact) -> dict[str, Any]:
    item = _serialize(link)
    item["contact"] = _serialize(link.contact) if link.contact else None
    return item


ENRICHMENT_FIELD_MAP = {
    "jobTitle": "job_title",
    "job_title": "job_title",
    "company": "company_name",
    "companyName": "company_name",
    "company_name": "company_name",
    "companyWebsite": "company_website",
    "company_website": "company_website",
    "website": "website",
    "industry": "industry",
    "companySize": "employee_count",
    "company_size": "employee_count",
    "employeeCount": "employee_count",
    "employee_count": "employee_count",
    "linkedinUrl": "linkedin_url",
    "linkedin_url": "linkedin_url",
    "linkedInUrl": "linkedin_url",
    "location": "address",
    "city": "city",
    "state": "state",
    "country": "country",
    "phone": "phone",
    "email": "email",
    "emailVerificationStatus": "email_verification_status",
    "email_verification_status": "email_verification_status",
    "socialProfiles": "social_profiles_json",
    "social_profiles": "social_profiles_json",
    "social_profiles_json": "social_profiles_json",
}


def _enrichment_resource_for(entity_type: str) -> tuple[str, Resource]:
    resource_name = _resource_for_custom_entity(entity_type)
    if resource_name not in {"leads", "contacts"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enrichment supports lead and contact records")
    return resource_name, _get_resource(resource_name)


def _enrichment_payload_data(payload: CRMEnrichmentPreviewPayload | CRMEnrichmentApplyPayload) -> dict[str, Any]:
    return getattr(payload, "values", None) or payload.enrichmentData or payload.data or payload.csvRow or {}


def _provider_key(provider: str | None) -> str:
    key = str(provider or "manual").strip().lower().replace("-", "_")
    if key in {"manual", "csv", "import", "csv_import"}:
        return "csv_import" if key in {"csv", "import", "csv_import"} else "manual"
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provider is not configured. Add a provider adapter before using third-party enrichment.")


def _normalize_enrichment_values(raw: dict[str, Any], record: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    columns = _columns(record.__class__)
    for key, value in raw.items():
        column_key = ENRICHMENT_FIELD_MAP.get(key) or ENRICHMENT_FIELD_MAP.get(_snake(key)) or _snake(key)
        if column_key not in columns:
            continue
        if value in {"", None}:
            continue
        if column_key == "employee_count":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        values[column_key] = _json_ready(value)
    return values


def _enrichment_preview(db: Session, organization_id: int, payload: CRMEnrichmentPreviewPayload | CRMEnrichmentApplyPayload) -> dict[str, Any]:
    provider = _provider_key(payload.provider)
    resource_name, resource = _enrichment_resource_for(payload.entityType)
    record = _get_record(db, resource, payload.entityId, organization_id)
    proposed = _normalize_enrichment_values(_enrichment_payload_data(payload), record)
    current = _serialize(record)
    fields = []
    for field, proposed_value in proposed.items():
        old_value = current.get(field)
        if old_value != proposed_value:
            fields.append({"field": field, "label": field.replace("_", " ").title(), "oldValue": old_value, "newValue": proposed_value, "supported": True})
    return {
        "entityType": ENTITY_TYPE_BY_CANONICAL.get(resource_name, resource_name.rstrip("s")),
        "entityId": record.id,
        "provider": provider,
        "fields": fields,
        "oldValues": {field["field"]: field["oldValue"] for field in fields},
        "newValues": {field["field"]: field["newValue"] for field in fields},
    }


def _serialize_approval_workflow(workflow: CRMApprovalWorkflow) -> dict[str, Any]:
    item = _serialize(workflow)
    item["entityType"] = workflow.entity_type
    item["triggerType"] = workflow.trigger_type
    item["isActive"] = bool(workflow.is_active)
    item["steps"] = [_serialize_approval_step(step) for step in sorted(workflow.steps, key=lambda step: step.step_order or 0)]
    return item


def _serialize_approval_step(step: CRMApprovalStep) -> dict[str, Any]:
    item = _serialize(step)
    item["workflowId"] = step.workflow_id
    item["stepOrder"] = step.step_order
    item["approverType"] = step.approver_type
    item["approverId"] = step.approver_id
    item["actionOnReject"] = step.action_on_reject
    return item


def _serialize_approval_request(request: CRMApprovalRequest) -> dict[str, Any]:
    item = _serialize(request)
    item["workflowId"] = request.workflow_id
    item["entityType"] = request.entity_type
    item["entityId"] = request.entity_id
    item["submittedBy"] = request.submitted_by
    item["submittedAt"] = request.submitted_at.isoformat() if request.submitted_at else None
    item["completedAt"] = request.completed_at.isoformat() if request.completed_at else None
    item["workflow"] = _serialize_approval_workflow(request.workflow) if request.workflow else None
    item["steps"] = [_serialize_approval_request_step(step) for step in request.steps]
    return item


def _serialize_approval_request_step(step: CRMApprovalRequestStep) -> dict[str, Any]:
    item = _serialize(step)
    item["requestId"] = step.request_id
    item["stepId"] = step.step_id
    item["approverId"] = step.approver_id
    item["actedAt"] = step.acted_at.isoformat() if step.acted_at else None
    return item


def _validate_and_build(resource: Resource, payload: dict[str, Any], partial: bool = False) -> dict[str, Any]:
    data = _normalize_payload(payload)
    if resource.model is CRMCustomField:
        if "entity_type" in data and "entity" not in data:
            data["entity"] = data.pop("entity_type")
        if "field_name" in data and "label" not in data:
            data["label"] = data["field_name"]
        if "label" in data and "field_name" not in data:
            data["field_name"] = data["label"]
        if "options" in data and "options_json" not in data:
            data["options_json"] = data.pop("options")
        if "display_order" in data and "position" not in data:
            data["position"] = data.pop("display_order")
        if "is_visible" not in data and not partial:
            data["is_visible"] = True
        if "is_filterable" not in data and not partial:
            data["is_filterable"] = False
        if "is_unique" not in data and not partial:
            data["is_unique"] = False
        if "entity" in data:
            data["entity"] = _normalize_custom_field_entity(data["entity"])
        if "field_type" in data:
            data["field_type"] = _normalize_custom_field_type(data["field_type"])
        if "field_key" in data:
            data["field_key"] = _slug_field_key(data["field_key"])
        elif not partial and data.get("label"):
            data["field_key"] = _slug_field_key(data["label"])
        if "options_json" in data and (data["options_json"] is None or data["options_json"] == ""):
            data["options_json"] = []
        if "options_json" in data and isinstance(data["options_json"], str):
            data["options_json"] = [item.strip() for item in re.split(r"[\n,]", data["options_json"]) if item.strip()]
    if resource.model is CRMActivity:
        if "description" in data and "body" not in data:
            data["body"] = data["description"]
        if "body" in data and "description" not in data:
            data["description"] = data["body"]
        if "title" in data and "subject" not in data:
            data["subject"] = data["title"]
        if "subject" in data and "title" not in data:
            data["title"] = data["subject"]
        if "activity_date" not in data and not partial:
            data["activity_date"] = datetime.now(timezone.utc)
        if "entity_type" in data:
            data["entity_type"] = _normalize_entity_type(data["entity_type"])
        if "metadata" in data and "metadata_json" not in data:
            data["metadata_json"] = data.pop("metadata")
    if "assigned_user_id" in data and "owner_user_id" not in data:
        data["owner_user_id"] = data.pop("assigned_user_id")
    if "team_id" in data and "assigned_team_id" not in data:
        data["assigned_team_id"] = data.pop("team_id")
    if resource.model is CRMTerritory:
        if "rules" in data and "rules_json" not in data:
            data["rules_json"] = data.pop("rules")
        if "is_active" not in data and not partial:
            data["is_active"] = True
        if "priority" not in data and not partial:
            data["priority"] = 100
        if "is_active" in data and "status" not in data:
            data["status"] = "Active" if data["is_active"] else "Inactive"
    columns = _columns(resource.model)
    unknown = sorted(key for key in data if key not in columns and key not in {"owner_id", "assigned_user_id", "team_id", "created_by", "updated_by", "organization_id", "custom_fields", "custom_field_values"})
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported field(s): {', '.join(unknown)}")

    missing = [field for field in resource.required if not partial and data.get(field) in {None, ""}]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Missing required field(s): {', '.join(missing)}")

    if "owner_id" in data and resource.owner_field:
        data[resource.owner_field] = data.pop("owner_id")
    if "created_by" in data:
        data["created_by_user_id"] = data.pop("created_by")
    if "updated_by" in data:
        data["updated_by_user_id"] = data.pop("updated_by")

    data.pop("custom_fields", None)
    data.pop("custom_field_values", None)

    return {key: _coerce_value(columns[key], value) for key, value in data.items() if key in columns}


def _get_record(db: Session, resource: Resource, record_id: int, organization_id: int, include_deleted: bool = False):
    record = _base_query(db, resource, organization_id, include_deleted).filter(resource.model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CRM record not found")
    return record


ENRICHMENT_PROVIDER_ALIASES = {
    "manual": "manual",
    "csv": "csv_import",
    "csv_import": "csv_import",
    "import": "csv_import",
    "api": "third_party",
    "third_party": "third_party",
}

ENRICHMENT_FIELD_ALIASES = {
    "job_title": "jobTitle",
    "jobtitle": "jobTitle",
    "title": "jobTitle",
    "company_name": "company",
    "company": "company",
    "company_website": "companyWebsite",
    "website": "companyWebsite",
    "industry": "industry",
    "company_size": "companySize",
    "employee_count": "companySize",
    "linkedin": "linkedInUrl",
    "linkedin_url": "linkedInUrl",
    "linked_in_url": "linkedInUrl",
    "location": "location",
    "city": "location",
    "phone": "phone",
    "email_status": "emailVerificationStatus",
    "email_verification_status": "emailVerificationStatus",
    "emailVerificationStatus": "emailVerificationStatus",
    "social_profiles": "socialProfiles",
    "socialProfiles": "socialProfiles",
}

ENRICHMENT_FIELD_LABELS = {
    "jobTitle": "Job title",
    "company": "Company",
    "companyWebsite": "Company website",
    "industry": "Industry",
    "companySize": "Company size",
    "linkedInUrl": "LinkedIn URL",
    "location": "Location",
    "phone": "Phone",
    "emailVerificationStatus": "Email verification status",
    "socialProfiles": "Social profiles",
}

ENRICHMENT_MODEL_FIELDS = {
    "lead": {
        "jobTitle": "job_title",
        "company": "company_name",
        "companyWebsite": "company_website",
        "industry": "industry",
        "companySize": "employee_count",
        "linkedInUrl": "linkedin_url",
        "phone": "phone",
        "emailVerificationStatus": "email_verification_status",
        "socialProfiles": "social_profiles_json",
        "location": "city",
    },
    "contact": {
        "jobTitle": "job_title",
        "company": "company_name",
        "companyWebsite": "company_website",
        "industry": "industry",
        "companySize": "employee_count",
        "linkedInUrl": "linkedin_url",
        "phone": "phone",
        "emailVerificationStatus": "email_verification_status",
        "socialProfiles": "social_profiles_json",
        "location": "city",
    },
}


def _enrichment_entity(entity_type: str) -> tuple[str, str]:
    normalized = _normalize_entity_type(entity_type) or str(entity_type or "").strip().lower()
    resource_name = {"lead": "leads", "contact": "contacts"}.get(normalized)
    if not resource_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enrichment supports leads and contacts")
    return normalized, resource_name


def _normalize_enrichment_provider(provider: str | None) -> str:
    key = str(provider or "manual").strip().lower().replace("-", "_")
    if key not in ENRICHMENT_PROVIDER_ALIASES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported enrichment provider")
    return ENRICHMENT_PROVIDER_ALIASES[key]


def _payload_enrichment_data(payload: CRMEnrichmentPreviewPayload | CRMEnrichmentApplyPayload) -> dict[str, Any] | None:
    return getattr(payload, "values", None) or getattr(payload, "enrichmentData", None) or getattr(payload, "data", None) or getattr(payload, "csvRow", None)


def _normalize_enrichment_values(data: dict[str, Any] | None) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in (data or {}).items():
        if value is None or value == "":
            continue
        alias_key = ENRICHMENT_FIELD_ALIASES.get(key) or ENRICHMENT_FIELD_ALIASES.get(_snake(str(key))) or key
        if alias_key in ENRICHMENT_FIELD_LABELS:
            normalized[alias_key] = value
    if "companySize" in normalized:
        try:
            normalized["companySize"] = int(normalized["companySize"])
        except (TypeError, ValueError):
            normalized.pop("companySize", None)
    social = normalized.get("socialProfiles")
    if isinstance(social, dict) and not normalized.get("linkedInUrl"):
        linkedin = social.get("linkedin") or social.get("linkedIn") or social.get("linkedinUrl")
        if linkedin:
            normalized["linkedInUrl"] = linkedin
    return normalized


def _record_enrichment_value(record: Any, entity_type: str, field_key: str) -> Any:
    model_field = ENRICHMENT_MODEL_FIELDS.get(entity_type, {}).get(field_key)
    if model_field and hasattr(record, model_field):
        return getattr(record, model_field)
    return None


def _enrichment_preview_payload(record: Any, entity_type: str, provider: str, values: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for key, label in ENRICHMENT_FIELD_LABELS.items():
        if key not in values:
            continue
        model_field = ENRICHMENT_MODEL_FIELDS.get(entity_type, {}).get(key)
        old_value = _record_enrichment_value(record, entity_type, key)
        fields.append(
            {
                "key": key,
                "label": label,
                "targetField": model_field,
                "supported": bool(model_field),
                "oldValue": old_value,
                "newValue": values[key],
                "changed": str(old_value or "") != str(values[key] or ""),
            }
        )
    return {
        "entityType": entity_type,
        "entityId": record.id,
        "provider": provider,
        "fields": fields,
        "values": values,
        "supportedFields": [field["key"] for field in fields if field["supported"]],
    }


def _enrichment_log_payload(log: CRMEnrichmentLog) -> dict[str, Any]:
    item = _serialize(log)
    item["oldValues"] = log.old_values_json or {}
    item["newValues"] = log.new_values_json or {}
    item["appliedFields"] = log.applied_fields_json or []
    return item


def _list_related(db: Session, entity: str, field: str, record_id: int, organization_id: int, limit: int = 25) -> list[dict[str, Any]]:
    resource = _get_resource(entity)
    columns = _columns(resource.model)
    if field not in columns:
        return []
    rows = (
        _base_query(db, resource, organization_id)
        .filter(getattr(resource.model, field) == record_id)
        .order_by(desc(getattr(resource.model, "updated_at", getattr(resource.model, "created_at", resource.model.id))))
        .limit(limit)
        .all()
    )
    return [_serialize(row) for row in rows]


def _mentions_for(db: Session, organization_id: int, *, note_id: int | None = None, activity_id: int | None = None) -> list[dict[str, Any]]:
    query = db.query(CRMNoteMention).filter(CRMNoteMention.organization_id == organization_id)
    if note_id is not None:
        query = query.filter(CRMNoteMention.note_id == note_id)
    if activity_id is not None:
        query = query.filter(CRMNoteMention.activity_id == activity_id)
    rows = query.order_by(asc(CRMNoteMention.id)).all()
    users = {user.id: user for user in db.query(User).filter(User.id.in_([row.mentioned_user_id for row in rows])).all()} if rows else {}
    return [
        {
            **_serialize(row),
            "organizationId": row.organization_id,
            "noteId": row.note_id,
            "activityId": row.activity_id,
            "mentionedUserId": row.mentioned_user_id,
            "mentionedBy": row.mentioned_by,
            "entityType": row.entity_type,
            "entityId": row.entity_id,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
            "readAt": row.read_at.isoformat() if row.read_at else None,
            "user": {"id": row.mentioned_user_id, "email": users[row.mentioned_user_id].email} if row.mentioned_user_id in users else None,
        }
        for row in rows
    ]


def _custom_fields_for(db: Session, entity: str, record_id: int, organization_id: int) -> list[dict[str, Any]]:
    fields = (
        _base_query(db, _get_resource("custom-fields"), organization_id)
        .filter(CRMCustomField.entity.in_([entity, entity.replace("-", "_")]), CRMCustomField.is_active.is_(True))
        .order_by(asc(CRMCustomField.position), asc(CRMCustomField.label))
        .all()
    )
    values = (
        _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(CRMCustomFieldValue.entity.in_([entity, entity.replace("-", "_")]), CRMCustomFieldValue.record_id == record_id)
        .all()
    )
    value_by_field = {value.custom_field_id: value for value in values}
    output = []
    for field in fields:
        value = value_by_field.get(field.id)
        item = _serialize(field)
        item["value"] = _custom_field_value(value) if value else None
        item["valueRecord"] = _serialize(value) if value else None
        output.append(item)
    return output


def _custom_field_columns_for_rows(db: Session, entity: str, rows: list[Any], organization_id: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    if entity not in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        return [_serialize(row) for row in rows]
    fields = _custom_field_definitions(db, entity, organization_id, include_hidden=False)
    if not fields:
        return [_serialize(row) for row in rows]
    field_by_id = {field.id: field for field in fields}
    values = (
        _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(
            CRMCustomFieldValue.entity == entity,
            CRMCustomFieldValue.record_id.in_([row.id for row in rows]),
            CRMCustomFieldValue.custom_field_id.in_(list(field_by_id)),
        )
        .all()
    )
    values_by_record: dict[int, dict[int, Any]] = {}
    for value in values:
        values_by_record.setdefault(value.record_id, {})[value.custom_field_id] = _custom_field_value(value)
    output = []
    for row in rows:
        serialized = _serialize(row)
        record_values = values_by_record.get(row.id, {})
        for field in fields:
            serialized[f"cf_{field.field_key}"] = record_values.get(field.id)
        output.append(serialized)
    return output


def _custom_field_value(value: CRMCustomFieldValue | None) -> Any:
    if not value:
        return None
    for key in ("value_text", "value_number", "value_date", "value_datetime", "value_boolean", "value_json"):
        item = getattr(value, key)
        if item is not None:
            if isinstance(item, (datetime, date)):
                return item.isoformat()
            if isinstance(item, Decimal):
                return float(item)
            return item
    return None


def _custom_field_storage(field: CRMCustomField, value: Any) -> dict[str, Any]:
    field_type = str(field.field_type or "text").lower()
    data: dict[str, Any] = {
        "value_text": None,
        "value_number": None,
        "value_date": None,
        "value_datetime": None,
        "value_boolean": None,
        "value_json": None,
    }
    if value is None or value == "":
        if field.is_required:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} is required")
        return data
    options = [str(item) for item in (field.options_json or [])] if isinstance(field.options_json, list) else []
    if field_type in {"number", "currency", "decimal", "integer", "user", "owner"}:
        try:
            data["value_number"] = Decimal(str(value))
        except (ArithmeticError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be a number") from exc
    elif field_type == "date":
        try:
            data["value_date"] = date.fromisoformat(str(value)[:10])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be a date") from exc
    elif field_type in {"datetime", "date_time"}:
        try:
            data["value_datetime"] = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be a date/time") from exc
    elif field_type in {"boolean", "checkbox"}:
        if isinstance(value, bool):
            data["value_boolean"] = value
        else:
            data["value_boolean"] = str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
    elif field_type in {"dropdown", "select"}:
        text = str(value)
        if options and text not in options:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be one of: {', '.join(options)}")
        data["value_text"] = text
    elif field_type == "multi_select":
        selected = value if isinstance(value, list) else [item.strip() for item in str(value).split(",") if item.strip()]
        invalid = [item for item in selected if options and str(item) not in options]
        if invalid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} has invalid option(s): {', '.join(map(str, invalid))}")
        data["value_json"] = selected
    elif field_type == "email":
        text = str(value).strip()
        if not EMAIL_PATTERN.match(text):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be a valid email")
        data["value_text"] = text
    elif field_type == "url":
        text = str(value).strip()
        if not re.match(r"^https?://", text):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be a valid URL")
        data["value_text"] = text
    elif field_type == "phone":
        text = str(value).strip()
        if len(re.sub(r"\D+", "", text)) < 7:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} must be a valid phone number")
        data["value_text"] = text
    elif field_type == "json":
        data["value_json"] = value
    else:
        data["value_text"] = str(value)
    return data


def _extract_custom_field_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("customFields", payload.get("custom_fields", payload.get("customFieldValues", payload.get("custom_field_values", {}))))
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        output: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, dict):
                key = item.get("fieldKey") or item.get("field_key") or item.get("customFieldId") or item.get("custom_field_id") or item.get("id")
                if key is not None:
                    output[str(key)] = item.get("value")
        return output
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="customFields must be an object or list")


def _custom_field_definitions(db: Session, entity: str, organization_id: int, *, include_hidden: bool = True) -> list[CRMCustomField]:
    canonical = _normalize_custom_field_entity(entity)
    query = _base_query(db, _get_resource("custom-fields"), organization_id).filter(
        CRMCustomField.entity == canonical,
        CRMCustomField.is_active.is_(True),
    )
    if not include_hidden:
        query = query.filter(CRMCustomField.is_visible.is_(True))
    return query.order_by(asc(CRMCustomField.position), asc(CRMCustomField.label)).all()


def _custom_value_for_key(field: CRMCustomField, values: dict[str, Any]) -> tuple[bool, Any]:
    keys = {str(field.id), field.field_key, field.label, field.field_name}
    for key in keys:
        if key and key in values:
            return True, values[key]
    return False, None


def _validate_required_custom_fields(db: Session, entity: str, record_id: int | None, organization_id: int, incoming: dict[str, Any]) -> None:
    for field in _custom_field_definitions(db, entity, organization_id):
        if not field.is_required:
            continue
        provided, value = _custom_value_for_key(field, incoming)
        if provided:
            _custom_field_storage(field, value)
            continue
        if record_id:
            existing = (
                _base_query(db, _get_resource("custom-field-values"), organization_id)
                .filter(CRMCustomFieldValue.custom_field_id == field.id, CRMCustomFieldValue.record_id == record_id)
                .first()
            )
            if _custom_field_value(existing) not in {None, ""}:
                continue
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field.label} is required")


def _save_custom_field_values(db: Session, entity: str, record_id: int, organization_id: int, user_id: int, values: dict[str, Any]) -> None:
    if not values:
        return
    fields = _custom_field_definitions(db, entity, organization_id)
    by_key: dict[str, CRMCustomField] = {}
    for field in fields:
        by_key[str(field.id)] = field
        by_key[field.field_key] = field
        by_key[field.label] = field
        if field.field_name:
            by_key[field.field_name] = field
    for key, value in values.items():
        field = by_key.get(str(key))
        if not field:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown custom field: {key}")
        storage = _custom_field_storage(field, value)
        row = (
            _base_query(db, _get_resource("custom-field-values"), organization_id)
            .filter(CRMCustomFieldValue.custom_field_id == field.id, CRMCustomFieldValue.record_id == record_id)
            .first()
        )
        if not row:
            row = CRMCustomFieldValue(
                organization_id=organization_id,
                custom_field_id=field.id,
                entity=field.entity,
                record_id=record_id,
                created_by_user_id=user_id,
            )
            db.add(row)
        for storage_key, storage_value in storage.items():
            setattr(row, storage_key, storage_value)
        row.updated_by_user_id = user_id
        row.updated_at = datetime.now(timezone.utc)


def _apply_custom_field_filters(db: Session, query, resource: Resource, request: Request, organization_id: int):
    entity = CANONICAL_ENTITY_BY_MODEL.get(resource.model)
    if entity not in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        return query
    for key, value in request.query_params.items():
        if not key.startswith("cf_") or value in {"", "all"}:
            continue
        field_key = _slug_field_key(key[3:])
        field = (
            _base_query(db, _get_resource("custom-fields"), organization_id)
            .filter(CRMCustomField.entity == entity, CRMCustomField.field_key == field_key, CRMCustomField.is_filterable.is_(True))
            .first()
        )
        if not field:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Custom field is not filterable: {field_key}")
        storage = _custom_field_storage(field, value)
        value_query = db.query(CRMCustomFieldValue.record_id).filter(
            CRMCustomFieldValue.organization_id == organization_id,
            CRMCustomFieldValue.custom_field_id == field.id,
            CRMCustomFieldValue.entity == entity,
            CRMCustomFieldValue.deleted_at.is_(None),
        )
        for storage_key, storage_value in storage.items():
            if storage_value is not None:
                value_query = value_query.filter(getattr(CRMCustomFieldValue, storage_key) == storage_value)
                break
        query = query.filter(resource.model.id.in_(value_query))
    return query


def _resource_for_custom_entity(entity: str) -> str | None:
    normalized = entity.strip().lower().replace("_", "-")
    return {
        "lead": "leads",
        "leads": "leads",
        "contact": "contacts",
        "contacts": "contacts",
        "account": "companies",
        "accounts": "companies",
        "company": "companies",
        "companies": "companies",
        "deal": "deals",
        "deals": "deals",
        "quotation": "quotations",
        "quotations": "quotations",
        "task": "tasks",
        "tasks": "tasks",
    }.get(normalized)


def _timeline_for(db: Session, entity: str, record: Any, organization_id: int) -> list[dict[str, Any]]:
    field = DETAIL_ENTITY_FIELDS.get(entity)
    entity_type = ENTITY_TYPE_BY_CANONICAL.get(entity)
    events: list[dict[str, Any]] = []
    if getattr(record, "created_at", None):
        events.append({"type": "created", "title": "Record created", "occurredAt": record.created_at.isoformat(), "record": _serialize(record)})
    if getattr(record, "updated_at", None):
        events.append({"type": "updated", "title": "Record updated", "occurredAt": record.updated_at.isoformat(), "record": _serialize(record)})
    if entity_type and not field:
        activity_rows = (
            _base_query(db, _get_resource("activities"), organization_id)
            .filter(CRMActivity.entity_type == entity_type, CRMActivity.entity_id == record.id)
            .order_by(desc(CRMActivity.activity_date))
            .limit(50)
            .all()
        )
        for row in activity_rows:
            item = _serialize(row)
            events.append({"type": "activities", "title": _timeline_title("activities", item), "occurredAt": item.get("activityDate") or item.get("createdAt"), "record": item})
    if field:
        for related_entity, date_field in TIMELINE_RESOURCES.items():
            resource = _get_resource(related_entity)
            columns = _columns(resource.model)
            if field not in columns and related_entity != "activities":
                continue
            query = _base_query(db, resource, organization_id)
            if related_entity == "activities" and entity_type:
                legacy_clause = getattr(resource.model, field) == record.id if field in columns else None
                generic_clause = (resource.model.entity_type == entity_type) & (resource.model.entity_id == record.id)
                query = query.filter(or_(generic_clause, legacy_clause) if legacy_clause is not None else generic_clause)
            else:
                query = query.filter(getattr(resource.model, field) == record.id)
            rows = query.order_by(desc(getattr(resource.model, date_field, getattr(resource.model, "created_at", resource.model.id)))).limit(50).all()
            for row in rows:
                item = _serialize(row)
                if related_entity == "notes":
                    item["mentions"] = _mentions_for(db, organization_id, note_id=row.id)
                if related_entity == "activities":
                    item["mentions"] = _mentions_for(db, organization_id, activity_id=row.id)
                occurred = item.get(date_field) or item.get("createdAt") or item.get("created_at")
                events.append({"type": related_entity, "title": _timeline_title(related_entity, item), "occurredAt": occurred, "record": item})
    elif entity_type:
        rows = (
            _base_query(db, _get_resource("activities"), organization_id)
            .filter(CRMActivity.entity_type == entity_type, CRMActivity.entity_id == record.id)
            .order_by(desc(CRMActivity.activity_date))
            .limit(50)
            .all()
        )
        for row in rows:
            item = _serialize(row)
            item["mentions"] = _mentions_for(db, organization_id, activity_id=row.id)
            occurred = item.get("activity_date") or item.get("activityDate") or item.get("createdAt") or item.get("created_at")
            events.append({"type": "activities", "title": _timeline_title("activities", item), "occurredAt": occurred, "record": item})
    if entity_type and entity in {"deals", "quotations"}:
        for approval in _approval_requests_for_entity(db, organization_id, entity_type, record.id):
            events.append(
                {
                    "type": "approval",
                    "title": f"Approval {approval['status']}",
                    "occurredAt": approval.get("completedAt") or approval.get("submittedAt"),
                    "record": approval,
                }
            )
    return sorted(events, key=lambda event: str(event.get("occurredAt") or ""), reverse=True)


def _timeline_title(entity: str, item: dict[str, Any]) -> str:
    if entity == "activities":
        return str(item.get("title") or item.get("subject") or item.get("activity_type") or "Activity")
    if entity == "notes":
        return str(item.get("body") or "Note added")[:120]
    if entity == "tasks":
        return str(item.get("title") or "Task")
    if entity == "calls":
        return f"{item.get('direction') or 'Call'} call"
    if entity == "emails":
        return str(item.get("subject") or "Email")
    if entity == "meetings":
        return str(item.get("title") or "Meeting")
    return str(item.get("subject") or "Activity")


def _related_for(db: Session, entity: str, record: Any, organization_id: int) -> dict[str, Any]:
    related: dict[str, Any] = {}
    if entity in DETAIL_ENTITY_FIELDS:
        field = DETAIL_ENTITY_FIELDS[entity]
        related.update(
            {
                "activities": _list_related(db, "activities", field, record.id, organization_id),
                "notes": _list_related(db, "notes", field, record.id, organization_id),
                "tasks": _list_related(db, "tasks", field, record.id, organization_id),
                "calls": _list_related(db, "calls", field, record.id, organization_id),
                "emails": _list_related(db, "emails", field, record.id, organization_id),
                "meetings": _list_related(db, "meetings", field, record.id, organization_id),
            }
        )
    if entity in {"leads", "contacts", "companies"}:
        related["duplicates"] = _duplicate_summary_for(db, organization_id, entity, record.id)
    if entity == "leads":
        related["conversion"] = {
            "isConverted": bool(record.is_converted),
            "convertedAt": record.converted_at.isoformat() if record.converted_at else None,
            "contactId": record.converted_contact_id,
            "accountId": record.converted_company_id,
            "dealId": record.converted_deal_id,
        }
    elif entity == "contacts":
        related["account"] = _serialize(_get_record(db, _get_resource("companies"), record.company_id, organization_id)) if record.company_id else None
        related["deals"] = _list_related(db, "deals", "contact_id", record.id, organization_id)
        related["stakeholderDeals"] = [
            {"dealContact": _serialize_deal_contact(link), "deal": _serialize(link.deal) if link.deal else None}
            for link in db.query(CRMDealContact).filter(
                CRMDealContact.organization_id == organization_id,
                CRMDealContact.contact_id == record.id,
            ).order_by(desc(CRMDealContact.is_primary), asc(CRMDealContact.id)).limit(100).all()
        ]
        related["quotations"] = _list_related(db, "quotations", "contact_id", record.id, organization_id)
    elif entity == "companies":
        related["contacts"] = _list_related(db, "contacts", "company_id", record.id, organization_id)
        related["deals"] = _list_related(db, "deals", "company_id", record.id, organization_id)
        related["quotations"] = _list_related(db, "quotations", "company_id", record.id, organization_id)
    elif entity == "deals":
        related["account"] = _serialize(_get_record(db, _get_resource("companies"), record.company_id, organization_id)) if record.company_id else None
        related["contact"] = _serialize(_get_record(db, _get_resource("contacts"), record.contact_id, organization_id)) if record.contact_id else None
        related["contacts"] = _deal_contacts_for(db, record, organization_id)
        related["quotations"] = _list_related(db, "quotations", "deal_id", record.id, organization_id)
        related["products"] = _deal_products_for(db, record.id, organization_id)
        try:
            from app.apps.srm.models import SRMBillingPlan, SRMContract, SRMEngagement, SRMSalesOrder
            from app.apps.project_management.models import PMSProject

            sales_order = db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == record.id, SRMSalesOrder.deleted_at == None).first()
            engagement = db.query(SRMEngagement).filter(SRMEngagement.crm_deal_id == record.id, SRMEngagement.deleted_at == None).first()
            contract = db.query(SRMContract).filter(SRMContract.sales_order_id == sales_order.id, SRMContract.deleted_at == None).first() if sales_order else None
            billing_plan = db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == engagement.id).first() if engagement else None
            project = db.query(PMSProject).filter(PMSProject.id == engagement.pms_project_id, PMSProject.deleted_at == None).first() if engagement and engagement.pms_project_id else None
            if sales_order or engagement or project:
                related["srm"] = {
                    "salesOrder": _serialize(sales_order) if sales_order else None,
                    "engagement": _serialize(engagement) if engagement else None,
                    "contract": _serialize(contract) if contract else None,
                    "billingPlan": _serialize(billing_plan) if billing_plan else None,
                    "pmsProject": _serialize(project) if project else None,
                }
        except Exception:
            pass
        approvals = _approval_requests_for_entity(db, organization_id, "deal", record.id)
        related["approval"] = approvals[0] if approvals else {"status": "not_submitted"}
        related["approvals"] = approvals
    elif entity == "quotations":
        related["deal"] = _serialize(_get_record(db, _get_resource("deals"), record.deal_id, organization_id)) if record.deal_id else None
        related["account"] = _serialize(_get_record(db, _get_resource("companies"), record.company_id, organization_id)) if record.company_id else None
        related["contact"] = _serialize(_get_record(db, _get_resource("contacts"), record.contact_id, organization_id)) if record.contact_id else None
        related["items"] = _quotation_items_for(db, record.id)
        approvals = _approval_requests_for_entity(db, organization_id, "quotation", record.id)
        related["approval"] = approvals[0] if approvals else {"status": "not_submitted"}
        related["approvals"] = approvals
    return related


def _deal_products_for(db: Session, deal_id: int, organization_id: int) -> list[dict[str, Any]]:
    deal_products = db.query(CRMDealProduct).filter(CRMDealProduct.deal_id == deal_id).limit(50).all()
    product_ids = [item.product_id for item in deal_products if item.product_id]
    products = {
        product.id: _serialize(product)
        for product in _base_query(db, _get_resource("products"), organization_id).filter(CRMProduct.id.in_(product_ids)).all()
    } if product_ids else {}
    return [{**_serialize(item), "product": products.get(item.product_id)} for item in deal_products]


def _deal_contacts_for(db: Session, deal: CRMDeal, organization_id: int) -> list[dict[str, Any]]:
    links = db.query(CRMDealContact).filter(
        CRMDealContact.organization_id == organization_id,
        CRMDealContact.deal_id == deal.id,
    ).order_by(desc(CRMDealContact.is_primary), asc(CRMDealContact.id)).all()
    if not links and deal.contact_id:
        contact = _get_record(db, _get_resource("contacts"), deal.contact_id, organization_id)
        return [{
            "id": None,
            "organization_id": organization_id,
            "organizationId": organization_id,
            "deal_id": deal.id,
            "dealId": deal.id,
            "contact_id": contact.id,
            "contactId": contact.id,
            "role": "Primary",
            "influence_level": None,
            "influenceLevel": None,
            "is_primary": True,
            "isPrimary": True,
            "notes": None,
            "contact": _serialize(contact),
        }]
    return [_serialize_deal_contact(link) for link in links]


def _deal_contact_data(payload: CRMDealContactPayload) -> dict[str, Any]:
    raw = payload.model_dump(exclude_unset=True)
    contact_id = raw.get("contactId") or raw.get("contact_id")
    if not contact_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="contactId is required")
    return {
        "contact_id": int(contact_id),
        "role": str(raw.get("role") or "Stakeholder"),
        "influence_level": raw.get("influenceLevel") or raw.get("influence_level"),
        "is_primary": bool(raw.get("isPrimary") if "isPrimary" in raw else raw.get("is_primary", False)),
        "notes": raw.get("notes"),
    }


def _sync_deal_primary_contact(db: Session, deal: CRMDeal, primary_link: CRMDealContact | None = None) -> None:
    if primary_link:
        db.query(CRMDealContact).filter(
            CRMDealContact.deal_id == deal.id,
            CRMDealContact.id != primary_link.id,
        ).update({"is_primary": False}, synchronize_session=False)
        deal.contact_id = primary_link.contact_id
        return
    primary = db.query(CRMDealContact).filter(
        CRMDealContact.deal_id == deal.id,
        CRMDealContact.is_primary == True,
    ).order_by(CRMDealContact.id).first()
    deal.contact_id = primary.contact_id if primary else None


def _upsert_deal_contact(
    db: Session,
    deal: CRMDeal,
    organization_id: int,
    data: dict[str, Any],
    user_id: int | None,
) -> CRMDealContact:
    contact = _get_record(db, _get_resource("contacts"), data["contact_id"], organization_id)
    if deal.company_id and contact.company_id and contact.company_id != deal.company_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Contact belongs to a different account than the deal")
    existing = db.query(CRMDealContact).filter(
        CRMDealContact.organization_id == organization_id,
        CRMDealContact.deal_id == deal.id,
        CRMDealContact.contact_id == contact.id,
    ).first()
    if existing:
        existing.role = data["role"]
        existing.influence_level = data.get("influence_level")
        existing.is_primary = bool(data.get("is_primary"))
        existing.notes = data.get("notes")
        existing.updated_by_user_id = user_id
        link = existing
    else:
        has_links = db.query(CRMDealContact).filter(CRMDealContact.deal_id == deal.id).count() > 0
        is_primary = bool(data.get("is_primary")) or not has_links
        link = CRMDealContact(
            organization_id=organization_id,
            deal_id=deal.id,
            contact_id=contact.id,
            role=data["role"],
            influence_level=data.get("influence_level"),
            is_primary=is_primary,
            notes=data.get("notes"),
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
        )
        db.add(link)
        db.flush()
    if link.is_primary:
        _sync_deal_primary_contact(db, deal, link)
    elif not deal.contact_id:
        link.is_primary = True
        _sync_deal_primary_contact(db, deal, link)
    return link


def _create_deal_contact_links_from_payload(
    db: Session,
    deal: CRMDeal,
    contacts_payload: Any,
    organization_id: int,
    user_id: int | None,
) -> None:
    if not contacts_payload:
        if deal.contact_id:
            _upsert_deal_contact(
                db,
                deal,
                organization_id,
                {"contact_id": deal.contact_id, "role": "Primary", "is_primary": True, "influence_level": None, "notes": None},
                user_id,
            )
        return
    contacts = contacts_payload if isinstance(contacts_payload, list) else []
    for index, item in enumerate(contacts):
        payload = CRMDealContactPayload(**item) if isinstance(item, dict) else CRMDealContactPayload(contactId=int(item))
        data = _deal_contact_data(payload)
        if index == 0 and not any(
            bool((entry.get("isPrimary") if isinstance(entry, dict) else False) or (entry.get("is_primary") if isinstance(entry, dict) else False))
            for entry in contacts
        ):
            data["is_primary"] = True
        _upsert_deal_contact(db, deal, organization_id, data, user_id)


def _quotation_items_for(db: Session, quotation_id: int) -> list[dict[str, Any]]:
    return [_serialize(item) for item in db.query(CRMQuotationItem).filter(CRMQuotationItem.quotation_id == quotation_id).limit(50).all()]


def _money(value: Any, currency: str = "INR") -> str:
    amount = Decimal(str(value or 0))
    return f"{currency} {amount.quantize(Decimal('0.01'))}"


def _pdf_text(value: Any, fallback: str = "-") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _pdf_markup(value: Any, fallback: str = "-") -> str:
    return html.escape(_pdf_text(value, fallback)).replace("\n", "<br/>")


def _safe_file_part(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "quotation")).strip("-")
    return text[:80] or "quotation"


def _company_details_for_pdf(db: Session, organization_id: int) -> dict[str, Any]:
    company = db.query(Company).filter(Company.id == organization_id).first()
    if not company:
        return {
            "name": settings.PROJECT_NAME,
            "legal_name": None,
            "address": None,
            "city": None,
            "state": None,
            "country": "India",
            "pincode": None,
            "email": settings.MAIL_FROM,
            "phone": None,
            "website": None,
            "gstin": None,
            "logo_url": None,
        }
    return {
        "name": company.name,
        "legal_name": company.legal_name,
        "address": company.address,
        "city": company.city,
        "state": company.state,
        "country": company.country,
        "pincode": company.pincode,
        "email": company.email,
        "phone": company.phone,
        "website": company.website,
        "gstin": company.gstin,
        "logo_url": company.logo_url,
    }


def _address_lines(*parts: Any) -> list[str]:
    lines = []
    for part in parts:
        if part:
            lines.extend(str(part).splitlines())
    return [line.strip() for line in lines if line and line.strip()]


def _upload_path_from_url(url: str | None) -> str | None:
    if not url or not str(url).startswith("/uploads/"):
        return None
    relative = str(url).replace("/uploads/", "", 1).replace("/", os.sep)
    path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, relative))
    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    if not path.startswith(upload_root):
        return None
    return path if os.path.exists(path) else None


def _quotation_pdf_file_path(quotation: CRMQuotation) -> tuple[str, str, str]:
    file_name = f"{_safe_file_part(quotation.quote_number)}-{quotation.id}.pdf"
    pdf_dir = os.path.join(settings.UPLOAD_DIR, "crm", "quotations", str(quotation.organization_id or "global"))
    os.makedirs(pdf_dir, exist_ok=True)
    file_path = os.path.join(pdf_dir, file_name)
    file_url = f"/uploads/crm/quotations/{quotation.organization_id or 'global'}/{file_name}"
    return file_path, file_name, file_url


def _generate_quotation_pdf(db: Session, quotation: CRMQuotation, organization_id: int, user_id: int | None) -> tuple[str, str, str]:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    file_path, file_name, file_url = _quotation_pdf_file_path(quotation)
    org = _company_details_for_pdf(db, organization_id)
    account = _get_record(db, _get_resource("companies"), quotation.company_id, organization_id) if quotation.company_id else None
    contact = _get_record(db, _get_resource("contacts"), quotation.contact_id, organization_id) if quotation.contact_id else None
    items = db.query(CRMQuotationItem).filter(CRMQuotationItem.quotation_id == quotation.id).all()
    currency = quotation.currency or "INR"

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Right", parent=styles["Normal"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#475569")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading3"], fontSize=11, leading=14, spaceAfter=6, textColor=colors.HexColor("#0f172a")))

    story: list[Any] = []
    logo_path = _upload_path_from_url(org.get("logo_url"))
    if logo_path:
        logo_cell: Any = Image(logo_path, width=1.0 * inch, height=0.55 * inch, kind="proportional")
    else:
        logo_cell = Paragraph("<b>LOGO</b>", styles["Normal"])
    org_lines = _address_lines(
        org.get("legal_name") or org.get("name"),
        org.get("address"),
        ", ".join(str(part) for part in [org.get("city"), org.get("state"), org.get("pincode")] if part),
        org.get("country"),
        f"Email: {org.get('email')}" if org.get("email") else None,
        f"Phone: {org.get('phone')}" if org.get("phone") else None,
        f"GSTIN: {org.get('gstin')}" if org.get("gstin") else None,
    )
    header = Table(
        [
            [logo_cell, Paragraph(f"<b>{_pdf_markup(org.get('name'), settings.PROJECT_NAME)}</b><br/>{'<br/>'.join(_pdf_markup(line, '') for line in org_lines[1:])}", styles["Small"]), Paragraph("<font size='18'><b>QUOTATION</b></font>", styles["Right"])],
        ],
        colWidths=[1.1 * inch, 3.4 * inch, 2.2 * inch],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    story.extend([header, Spacer(1, 0.15 * inch)])

    customer_lines = []
    if account:
        customer_lines.extend(_address_lines(account.name, account.address, ", ".join(str(part) for part in [account.city, account.state, account.country] if part), account.email, account.phone))
    if contact:
        customer_lines.extend(_address_lines(f"Contact: {contact.full_name}", contact.email, contact.phone))
    if not customer_lines:
        customer_lines.append("Customer details not linked")
    quote_meta = [
        f"<b>Quotation No:</b> {_pdf_markup(quotation.quote_number)}",
        f"<b>Issue Date:</b> {_pdf_markup(quotation.issue_date.isoformat() if quotation.issue_date else None)}",
        f"<b>Expiry Date:</b> {_pdf_markup(quotation.expiry_date.isoformat() if quotation.expiry_date else None)}",
        f"<b>Status:</b> {_pdf_markup(quotation.status)}",
    ]
    details = Table(
        [[Paragraph("<b>Bill To</b><br/>" + "<br/>".join(_pdf_markup(line, "") for line in customer_lines), styles["Normal"]), Paragraph("<br/>".join(quote_meta), styles["Normal"])]],
        colWidths=[3.6 * inch, 3.1 * inch],
    )
    details.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.extend([details, Spacer(1, 0.2 * inch)])

    table_data = [["Product / Service", "Qty", "Rate", "Discount", "Tax", "Total"]]
    computed_subtotal = Decimal("0")
    computed_discount = Decimal("0")
    computed_tax = Decimal("0")
    computed_total = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity or 0))
        rate = Decimal(str(item.unit_price or 0))
        discount = Decimal(str(item.discount_amount or 0))
        tax_rate = Decimal(str(item.tax_rate or 0))
        taxable = max(Decimal("0"), (qty * rate) - discount)
        tax = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = Decimal(str(item.total_amount or 0)) or taxable + tax
        computed_subtotal += qty * rate
        computed_discount += discount
        computed_tax += tax
        computed_total += total
        table_data.append([
            Paragraph(f"<b>{_pdf_markup(item.name)}</b><br/><font size='8'>{_pdf_markup(item.description, '')}</font>", styles["Small"]),
            _pdf_text(item.quantity, "0"),
            _money(rate, currency),
            _money(discount, currency),
            Paragraph(f"{tax_rate}%<br/>{_money(tax, currency)}", styles["Small"]),
            _money(total, currency),
        ])
    if len(table_data) == 1:
        table_data.append([Paragraph("No line items recorded", styles["Small"]), "0", _money(0, currency), _money(0, currency), _money(0, currency), _money(quotation.total_amount, currency)])

    item_table = Table(table_data, colWidths=[2.55 * inch, 0.45 * inch, 0.95 * inch, 0.95 * inch, 0.95 * inch, 0.95 * inch], repeatRows=1)
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([item_table, Spacer(1, 0.15 * inch)])

    subtotal = quotation.subtotal if quotation.subtotal is not None else computed_subtotal
    discount = quotation.discount_amount if quotation.discount_amount is not None else computed_discount
    tax = quotation.tax_amount if quotation.tax_amount is not None else computed_tax
    total = quotation.total_amount if quotation.total_amount is not None else computed_total
    totals = Table(
        [
            ["Subtotal", _money(subtotal, currency)],
            ["Discount", _money(discount, currency)],
            ["Tax", _money(tax, currency)],
            [Paragraph("<b>Total</b>", styles["Normal"]), Paragraph(f"<b>{_money(total, currency)}</b>", styles["Right"])],
        ],
        colWidths=[1.4 * inch, 1.4 * inch],
        hAlign="RIGHT",
    )
    totals.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")), ("PADDING", (0, 0), (-1, -1), 6), ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    story.extend([totals, Spacer(1, 0.25 * inch)])

    terms = _pdf_text(quotation.terms, "Standard commercial terms apply unless otherwise agreed in writing.")
    story.extend([Paragraph("Terms and Conditions", styles["Section"]), Paragraph(_pdf_markup(terms), styles["Small"]), Spacer(1, 0.35 * inch)])
    signature = Table([["", "Authorized Signature"], ["", "Name / Date"]], colWidths=[4.2 * inch, 2.4 * inch])
    signature.setStyle(TableStyle([("LINEABOVE", (1, 0), (1, 0), 0.8, colors.HexColor("#0f172a")), ("ALIGN", (1, 0), (1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 1), (1, 1), colors.HexColor("#64748b"))]))
    story.append(signature)

    doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36, title=f"Quotation {quotation.quote_number}")
    doc.build(story)

    quotation.pdf_url = file_url
    quotation.pdf_file_name = file_name
    quotation.pdf_status = "generated"
    quotation.pdf_generated_at = datetime.now(timezone.utc)
    quotation.pdf_generated_by_user_id = user_id
    quotation.updated_at = datetime.now(timezone.utc)
    quotation.updated_by_user_id = user_id
    return file_path, file_name, file_url


def _detail_payload(db: Session, entity: str, record: Any, organization_id: int) -> dict[str, Any]:
    canonical = _canonical_entity(entity)
    payload = _serialize(record)
    payload["entity"] = canonical
    payload["customFields"] = _custom_fields_for(db, canonical, record.id, organization_id)
    payload["timeline"] = _timeline_for(db, canonical, record, organization_id)
    payload["related"] = _related_for(db, canonical, record, organization_id)
    return payload


def _maybe_create_srm_handoff_for_won_deal(db: Session, deal: CRMDeal, current_user: User) -> None:
    """Create SRM commercial records after CRM deal won; CRM never creates PMS directly."""
    is_won_status = str(getattr(deal, "status", "") or "").lower() == "won"
    stage = db.query(CRMPipelineStage).filter(CRMPipelineStage.id == deal.stage_id).first() if deal.stage_id else None
    if not (is_won_status or bool(getattr(stage, "is_won", False))):
        return
    try:
        from app.apps.srm.api.router import create_sales_order_from_crm_deal_service

        create_sales_order_from_crm_deal_service(deal.id, db, current_user)
        _create_timeline_activity(
            db,
            organization_id=getattr(deal, "organization_id", None) or _organization_id(db, current_user),
            entity_type="deal",
            entity_id=deal.id,
            activity_type="srm_handoff",
            title="SRM commercial handoff created",
            body="CRM won deal was handed off to SRM sales order, engagement, contract, and billing plan.",
            user_id=current_user.id,
        )
    except Exception as exc:
        _create_timeline_activity(
            db,
            organization_id=getattr(deal, "organization_id", None) or _organization_id(db, current_user),
            entity_type="deal",
            entity_id=deal.id,
            activity_type="srm_handoff_failed",
            title="SRM commercial handoff failed",
            body=str(exc),
            user_id=current_user.id,
        )


RELATED_RESOURCE_BY_FIELD = {
    "company_id": "companies",
    "contact_id": "contacts",
    "deal_id": "deals",
    "lead_id": "leads",
    "pipeline_id": "pipelines",
    "stage_id": "pipeline-stages",
    "territory_id": "territories",
    "custom_field_id": "custom-fields",
    "converted_contact_id": "contacts",
    "converted_company_id": "companies",
    "converted_deal_id": "deals",
}


def _validate_related_records(db: Session, data: dict[str, Any], organization_id: int) -> None:
    for field, resource_name in RELATED_RESOURCE_BY_FIELD.items():
        record_id = data.get(field)
        if not record_id:
            continue
        related = _get_resource(resource_name)
        _get_record(db, related, int(record_id), organization_id, include_deleted=False)
    entity_type = _normalize_entity_type(data.get("entity_type"))
    entity_id = data.get("entity_id")
    if entity_type and entity_id:
        resource_name = {
            "lead": "leads",
            "contact": "contacts",
            "account": "companies",
            "deal": "deals",
            "quotation": "quotations",
        }.get(entity_type)
        if resource_name:
            _get_record(db, _get_resource(resource_name), int(entity_id), organization_id, include_deleted=False)


def _validate_deal_pipeline_stage(db: Session, pipeline_id: int | None, stage_id: int | None, organization_id: int) -> None:
    if not pipeline_id or not stage_id:
        return
    stage = _get_record(db, _get_resource("pipeline-stages"), int(stage_id), organization_id)
    if stage.pipeline_id != int(pipeline_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Deal stage must belong to the selected pipeline")


DEFAULT_LEAD_SCORING_RULES = [
    ("Has email", "email", "exists", "", 10),
    ("Has phone", "phone", "exists", "", 10),
    ("Company provided", "company_name", "exists", "", 10),
    ("Source is website", "source", "equals", "Website", 10),
    ("Budget above threshold", "estimated_value", "gte", "500000", 15),
    ("No activity in 30 days", "last_contacted_at", "older_than_days", "30", -10),
]


def _score_label(score: int) -> str:
    if score <= 30:
        return "Cold"
    if score <= 70:
        return "Warm"
    return "Hot"


def _ensure_default_scoring_rules(db: Session, organization_id: int, user_id: int | None = None) -> None:
    existing = _base_query(db, _get_resource("lead-scoring-rules"), organization_id, include_deleted=True).count()
    if existing:
        return
    for name, field, operator, value, points in DEFAULT_LEAD_SCORING_RULES:
        db.add(
            CRMLeadScoringRule(
                organization_id=organization_id,
                name=name,
                field=field,
                operator=operator,
                value=value,
                points=points,
                is_active=True,
                created_by_user_id=user_id,
                updated_by_user_id=user_id,
            )
        )
    db.flush()


def _lead_field_value(lead: CRMLead, field: str) -> Any:
    field_name = _snake(field)
    if hasattr(lead, field_name):
        return getattr(lead, field_name)
    return None


def _rule_matches(lead: CRMLead, rule: CRMLeadScoringRule, now: datetime) -> bool:
    actual = _lead_field_value(lead, rule.field)
    expected = rule.value
    operator = str(rule.operator or "").lower()
    if operator in {"exists", "has_value"}:
        return actual not in {None, ""}
    if operator in {"not_exists", "empty"}:
        return actual in {None, ""}
    if operator in {"equals", "eq", "is"}:
        return str(actual or "").lower() == str(expected or "").lower()
    if operator in {"not_equals", "neq"}:
        return str(actual or "").lower() != str(expected or "").lower()
    if operator in {"contains"}:
        return str(expected or "").lower() in str(actual or "").lower()
    if operator in {"gt", "gte", "lt", "lte"}:
        try:
            actual_number = Decimal(str(actual or 0))
            expected_number = Decimal(str(expected or 0))
        except (ArithmeticError, ValueError):
            return False
        if operator == "gt":
            return actual_number > expected_number
        if operator == "gte":
            return actual_number >= expected_number
        if operator == "lt":
            return actual_number < expected_number
        return actual_number <= expected_number
    if operator == "older_than_days":
        if not isinstance(actual, datetime):
            return actual in {None, ""}
        try:
            days = int(str(expected or 0))
        except ValueError:
            return False
        actual_dt = actual if actual.tzinfo else actual.replace(tzinfo=timezone.utc)
        return (now - actual_dt).days >= days
    return False


def _calculate_lead_score(db: Session, lead: CRMLead, organization_id: int, user_id: int | None = None) -> tuple[int, str, list[dict[str, Any]]]:
    _ensure_default_scoring_rules(db, organization_id, user_id)
    now = datetime.now(timezone.utc)
    rules = (
        _base_query(db, _get_resource("lead-scoring-rules"), organization_id)
        .filter(CRMLeadScoringRule.is_active.is_(True))
        .order_by(asc(CRMLeadScoringRule.id))
        .all()
    )
    reasons = []
    total = 0
    for rule in rules:
        matched = _rule_matches(lead, rule, now)
        if matched:
            total += int(rule.points or 0)
        reasons.append({"ruleId": rule.id, "name": rule.name, "matched": matched, "points": int(rule.points or 0) if matched else 0})
    score = max(0, min(100, total))
    return score, _score_label(score), reasons


def _apply_lead_score(db: Session, lead: CRMLead, organization_id: int, user_id: int | None = None, force: bool = False, commit: bool = False) -> dict[str, Any]:
    if not force and str(lead.lead_score_mode or "automatic").lower() == "manual":
        return {"score": int(lead.lead_score or 0), "label": lead.lead_score_label or _score_label(int(lead.lead_score or 0)), "reasons": []}
    score, label, reasons = _calculate_lead_score(db, lead, organization_id, user_id)
    lead.lead_score = score
    lead.lead_score_label = label
    lead.rating = label
    lead.lead_score_mode = "automatic"
    lead.last_score_calculated_at = datetime.now(timezone.utc)
    lead.updated_by_user_id = user_id
    if commit:
        db.commit()
        db.refresh(lead)
    return {"score": score, "label": label, "reasons": reasons}


def _recalculate_linked_lead(db: Session, data: dict[str, Any], organization_id: int, user_id: int | None) -> None:
    lead_id = data.get("lead_id")
    entity_type = _normalize_entity_type(data.get("entity_type"))
    if not lead_id and entity_type == "lead":
        lead_id = data.get("entity_id")
    if not lead_id:
        return
    lead = _base_query(db, _get_resource("leads"), organization_id).filter(CRMLead.id == int(lead_id)).first()
    if lead and str(lead.lead_score_mode or "automatic").lower() == "automatic":
        lead.last_contacted_at = datetime.now(timezone.utc)
        _apply_lead_score(db, lead, organization_id, user_id)


def _approval_resource_for(entity_type: str) -> str:
    resource_name = _resource_for_custom_entity(entity_type)
    if not resource_name or resource_name not in {"deals", "quotations"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Approvals are supported for deal and quotation records")
    return resource_name


def _approval_query(db: Session, organization_id: int):
    return db.query(CRMApprovalRequest).filter(CRMApprovalRequest.organization_id == organization_id)


def _latest_approval_for(db: Session, organization_id: int, entity_type: str, entity_id: int) -> CRMApprovalRequest | None:
    return (
        _approval_query(db, organization_id)
        .filter(CRMApprovalRequest.entity_type == entity_type, CRMApprovalRequest.entity_id == entity_id)
        .order_by(desc(CRMApprovalRequest.submitted_at), desc(CRMApprovalRequest.id))
        .first()
    )


def _active_blocking_approval(db: Session, organization_id: int, entity_type: str, entity_id: int) -> CRMApprovalRequest | None:
    request = _latest_approval_for(db, organization_id, entity_type, entity_id)
    return request if request and request.status in {"pending", "rejected"} else None


def _assert_final_action_allowed(db: Session, organization_id: int, resource: Resource, record: Any, data: dict[str, Any]) -> None:
    entity_type = CANONICAL_ENTITY_BY_MODEL.get(resource.model)
    entity_type = ENTITY_TYPE_BY_CANONICAL.get(entity_type or "")
    if entity_type not in {"deal", "quotation"}:
        return
    next_status = str(data.get("status", getattr(record, "status", "")) or "").lower()
    is_final = (entity_type == "deal" and next_status == "won") or (entity_type == "quotation" and next_status in {"sent", "accepted"})
    if not is_final:
        return
    blocking = _active_blocking_approval(db, organization_id, entity_type, record.id)
    if blocking:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Approval is {blocking.status}; final action is blocked")


def _conditions_match(record: Any, workflow: CRMApprovalWorkflow) -> bool:
    conditions = workflow.conditions or {}
    if not conditions:
        return True
    amount = Decimal(str(getattr(record, "amount", getattr(record, "total_amount", 0)) or 0))
    discount = Decimal(str(getattr(record, "discount_amount", 0) or 0))
    if conditions.get("minAmount") is not None and amount < Decimal(str(conditions["minAmount"])):
        return False
    if conditions.get("maxAmount") is not None and amount > Decimal(str(conditions["maxAmount"])):
        return False
    if conditions.get("discountAbove") is not None and discount <= Decimal(str(conditions["discountAbove"])):
        return False
    if conditions.get("stageId") is not None and int(getattr(record, "stage_id", 0) or 0) != int(conditions["stageId"]):
        return False
    if conditions.get("status") and str(getattr(record, "status", "") or "").lower() != str(conditions["status"]).lower():
        return False
    return True


def _select_approval_workflow(db: Session, organization_id: int, entity_type: str, record: Any, workflow_id: int | None, trigger_type: str | None) -> CRMApprovalWorkflow:
    query = db.query(CRMApprovalWorkflow).filter(
        CRMApprovalWorkflow.organization_id == organization_id,
        CRMApprovalWorkflow.entity_type == entity_type,
        CRMApprovalWorkflow.is_active.is_(True),
        CRMApprovalWorkflow.deleted_at.is_(None),
    )
    if workflow_id:
        workflow = query.filter(CRMApprovalWorkflow.id == workflow_id).first()
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval workflow not found")
        return workflow
    normalized_trigger = (trigger_type or "manual").strip().lower().replace("_", "-")
    workflows = query.order_by(asc(CRMApprovalWorkflow.id)).all()
    for workflow in workflows:
        workflow_trigger = str(workflow.trigger_type or "").strip().lower().replace("_", "-")
        if workflow_trigger in {normalized_trigger, "manual", "any"} and _conditions_match(record, workflow):
            return workflow
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active approval workflow matches this record")


def _resolve_approver_id(db: Session, step: CRMApprovalStep, record: Any, submitter_id: int) -> int:
    approver_type = str(step.approver_type or "user").lower()
    if approver_type == "user" and step.approver_id:
        return int(step.approver_id)
    if approver_type == "role" and step.approver_id:
        user = db.query(User).filter(User.role_id == int(step.approver_id), User.is_active.is_(True)).order_by(asc(User.id)).first()
        if user:
            return user.id
    if approver_type == "manager":
        owner_id = getattr(record, "owner_user_id", None)
        if owner_id:
            return int(owner_id)
    return submitter_id


def _approval_requests_for_entity(db: Session, organization_id: int, entity_type: str, entity_id: int) -> list[dict[str, Any]]:
    rows = (
        _approval_query(db, organization_id)
        .filter(CRMApprovalRequest.entity_type == entity_type, CRMApprovalRequest.entity_id == entity_id)
        .order_by(desc(CRMApprovalRequest.submitted_at), desc(CRMApprovalRequest.id))
        .limit(25)
        .all()
    )
    return [_serialize_approval_request(row) for row in rows]


def _deal_status_key(value: Any) -> str:
    status_text = str(value or "open").strip().lower()
    if status_text in {"won", "closed won", "closed_won", "success"}:
        return "won"
    if status_text in {"lost", "closed lost", "closed_lost", "failed"}:
        return "lost"
    return "open"


def _apply_deal_close_fields(record: CRMDeal, data: dict[str, Any]) -> None:
    if "status" not in data:
        return
    status_key = _deal_status_key(data.get("status"))
    now = datetime.now(timezone.utc)
    if status_key == "won":
        record.won_at = record.won_at or now
        record.closed_at = record.closed_at or record.won_at
        record.lost_at = None
    elif status_key == "lost":
        record.lost_at = record.lost_at or now
        record.closed_at = record.closed_at or record.lost_at
        record.won_at = None
        if data.get("lost_reason") and not record.loss_reason:
            record.loss_reason = data.get("lost_reason")


def _duplicate_resource_name(entity_type: str | None) -> str:
    normalized = str(entity_type or "").strip().lower().replace("_", "-")
    resource_name = DUPLICATE_ENTITY_RESOURCES.get(normalized)
    if not resource_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate detection supports leads, contacts, and accounts")
    return resource_name


def _duplicate_entity_type(resource_name: str) -> str:
    return "account" if resource_name == "companies" else resource_name.rstrip("s")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _domain_from(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "@" in text and not text.startswith("http"):
        text = text.split("@", 1)[1]
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    return text.split("/", 1)[0].split(":", 1)[0]


def _similarity(left: Any, right: Any) -> float:
    left_text = _clean_text(left)
    right_text = _clean_text(right)
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _record_label(record: Any, resource_name: str) -> str:
    if resource_name == "companies":
        return str(getattr(record, "name", "") or f"Account {record.id}")
    return str(getattr(record, "full_name", "") or getattr(record, "name", "") or f"Record {record.id}")


def _company_key(record: Any, resource_name: str) -> str:
    if resource_name == "leads":
        return _clean_text(getattr(record, "company_name", None))
    if resource_name == "contacts":
        return str(getattr(record, "company_id", None) or "")
    return ""


def _unique_custom_fields(db: Session, organization_id: int, resource_name: str) -> list[CRMCustomField]:
    entity_names = {resource_name, resource_name.rstrip("s"), resource_name.replace("-", "_")}
    if resource_name == "companies":
        entity_names.update({"account", "accounts", "company"})
    fields = (
        _base_query(db, _get_resource("custom-fields"), organization_id)
        .filter(CRMCustomField.entity.in_(entity_names), CRMCustomField.is_active.is_(True))
        .all()
    )

    def configured_unique(field: CRMCustomField) -> bool:
        options = field.options_json or {}
        key = str(field.field_key or "").lower()
        if bool(getattr(field, "is_unique", False)):
            return True
        if isinstance(options, dict) and any(bool(options.get(item)) for item in ("isUnique", "is_unique", "unique", "dedupe")):
            return True
        return key in {"tax_registration_number", "tax_registration", "gstin", "pan", "unique_id", "external_id"}

    return [field for field in fields if configured_unique(field)]


def _custom_unique_values(db: Session, organization_id: int, resource_name: str, record_ids: list[int]) -> dict[int, dict[str, str]]:
    if not record_ids:
        return {}
    fields = _unique_custom_fields(db, organization_id, resource_name)
    if not fields:
        return {}
    field_by_id = {field.id: field for field in fields}
    entity_names = {resource_name, resource_name.rstrip("s"), _duplicate_entity_type(resource_name)}
    if resource_name == "companies":
        entity_names.update({"account", "accounts", "company"})
    rows = (
        _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(
            CRMCustomFieldValue.custom_field_id.in_(list(field_by_id)),
            CRMCustomFieldValue.entity.in_(entity_names),
            CRMCustomFieldValue.record_id.in_(record_ids),
        )
        .all()
    )
    values: dict[int, dict[str, str]] = {}
    for row in rows:
        raw_value = _custom_field_value(row)
        if raw_value in {None, ""}:
            continue
        field = field_by_id.get(row.custom_field_id)
        if not field:
            continue
        values.setdefault(row.record_id, {})[field.field_key] = _clean_text(raw_value)
    return values


def _duplicate_pair_reasons(left: Any, right: Any, resource_name: str, custom_values: dict[int, dict[str, str]]) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    fields: list[str] = []
    if resource_name in {"leads", "contacts"}:
        left_email = _clean_text(getattr(left, "email", None))
        right_email = _clean_text(getattr(right, "email", None))
        if left_email and left_email == right_email:
            score = max(score, 100)
            reasons.append("Same email")
            fields.append("email")
        left_phone = _digits(getattr(left, "phone", None))
        right_phone = _digits(getattr(right, "phone", None))
        if left_phone and right_phone and left_phone[-10:] == right_phone[-10:]:
            score = max(score, 90)
            reasons.append("Same phone")
            fields.append("phone")
        same_company = _company_key(left, resource_name) and _company_key(left, resource_name) == _company_key(right, resource_name)
        if same_company and _similarity(getattr(left, "full_name", None), getattr(right, "full_name", None)) >= 0.82:
            score = max(score, 78)
            reasons.append("Similar name and same company")
            fields.extend(["full_name", "company"])
    else:
        left_domain = _domain_from(getattr(left, "website", None) or getattr(left, "email", None))
        right_domain = _domain_from(getattr(right, "website", None) or getattr(right, "email", None))
        if left_domain and left_domain == right_domain:
            score = max(score, 100)
            reasons.append("Same domain")
            fields.append("domain")
        if _similarity(getattr(left, "name", None), getattr(right, "name", None)) >= 0.86:
            score = max(score, 82)
            reasons.append("Similar company name")
            fields.append("name")
        left_phone = _digits(getattr(left, "phone", None))
        right_phone = _digits(getattr(right, "phone", None))
        if left_phone and right_phone and left_phone[-10:] == right_phone[-10:]:
            score = max(score, 85)
            reasons.append("Same phone")
            fields.append("phone")
    for key, left_value in custom_values.get(left.id, {}).items():
        right_value = custom_values.get(right.id, {}).get(key)
        if left_value and right_value and left_value == right_value:
            score = max(score, 100)
            reasons.append(f"Same custom unique field: {key}")
            fields.append(key)
    return score, sorted(set(reasons)), sorted(set(fields))


def _duplicate_groups(db: Session, organization_id: int, resource_name: str, target_id: int | None = None) -> list[dict[str, Any]]:
    resource = _get_resource(resource_name)
    records = _base_query(db, resource, organization_id).order_by(asc(resource.model.id)).all()
    if len(records) < 2:
        return []
    records_by_id = {record.id: record for record in records}
    custom_values = _custom_unique_values(db, organization_id, resource_name, list(records_by_id))
    parent = {record.id: record.id for record in records}
    pair_meta: dict[tuple[int, int], dict[str, Any]] = {}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            score, reasons, fields = _duplicate_pair_reasons(left, right, resource_name, custom_values)
            if score:
                union(left.id, right.id)
                pair_meta[(left.id, right.id)] = {"score": score, "reasons": reasons, "fields": fields}

    grouped_ids: dict[int, list[int]] = {}
    for record in records:
        grouped_ids.setdefault(find(record.id), []).append(record.id)

    groups: list[dict[str, Any]] = []
    entity_type = _duplicate_entity_type(resource_name)
    for ids in grouped_ids.values():
        if len(ids) < 2:
            continue
        if target_id is not None and target_id not in ids:
            continue
        group_reasons: set[str] = set()
        group_fields: set[str] = set()
        group_score = 0
        pairs = []
        for left_id in ids:
            for right_id in ids:
                if left_id >= right_id:
                    continue
                meta = pair_meta.get((left_id, right_id))
                if not meta:
                    continue
                group_score = max(group_score, int(meta["score"]))
                group_reasons.update(meta["reasons"])
                group_fields.update(meta["fields"])
                pairs.append({"recordIds": [left_id, right_id], **meta})
        serialized = [_serialize(records_by_id[record_id]) for record_id in ids]
        for item in serialized:
            item["duplicateLabel"] = _record_label(records_by_id[int(item["id"])], resource_name)
        groups.append(
            {
                "id": f"{entity_type}-{min(ids)}",
                "entityType": entity_type,
                "score": group_score,
                "reasons": sorted(group_reasons),
                "matchingFields": sorted(group_fields),
                "recordIds": ids,
                "records": serialized,
                "pairs": pairs,
            }
        )
    return sorted(groups, key=lambda group: (-int(group["score"]), group["recordIds"][0]))


def _duplicate_summary_for(db: Session, organization_id: int, resource_name: str, record_id: int) -> dict[str, Any]:
    groups = _duplicate_groups(db, organization_id, resource_name, target_id=record_id)
    return {"count": sum(len(group["recordIds"]) - 1 for group in groups), "groups": groups[:5]}


def _merge_related_records(db: Session, organization_id: int, resource_name: str, winner_id: int, loser_ids: list[int], user_id: int | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    entity_type = _duplicate_entity_type(resource_name)
    linked_field = ENTITY_FIELD_BY_TYPE.get(entity_type)
    now = datetime.now(timezone.utc)

    def update_count(label: str, count: int) -> None:
        if count:
            counts[label] = counts.get(label, 0) + count

    def update_values(model: type, values: dict[str, Any]) -> dict[str, Any]:
        output = dict(values)
        columns = _columns(model)
        if "updated_by_user_id" in columns:
            output["updated_by_user_id"] = user_id
        if "updated_at" in columns:
            output["updated_at"] = now
        return output

    if linked_field:
        for model, label in ((CRMActivity, "activities"), (CRMNote, "notes"), (CRMTask, "tasks"), (CRMCallLog, "calls"), (CRMEmailLog, "emails"), (CRMMeeting, "meetings")):
            if hasattr(model, linked_field):
                update_count(
                    label,
                    db.query(model)
                    .filter(model.organization_id == organization_id, getattr(model, linked_field).in_(loser_ids))
                    .update(update_values(model, {linked_field: winner_id}), synchronize_session=False),
                )
        update_count(
            "activities",
            db.query(CRMActivity)
            .filter(CRMActivity.organization_id == organization_id, CRMActivity.entity_type == entity_type, CRMActivity.entity_id.in_(loser_ids))
            .update(update_values(CRMActivity, {"entity_id": winner_id}), synchronize_session=False),
        )
    if resource_name == "contacts":
        update_count("deals", db.query(CRMDeal).filter(CRMDeal.organization_id == organization_id, CRMDeal.contact_id.in_(loser_ids)).update(update_values(CRMDeal, {"contact_id": winner_id}), synchronize_session=False))
        update_count("quotations", db.query(CRMQuotation).filter(CRMQuotation.organization_id == organization_id, CRMQuotation.contact_id.in_(loser_ids)).update(update_values(CRMQuotation, {"contact_id": winner_id}), synchronize_session=False))
        moved_links = 0
        for link in db.query(CRMDealContact).filter(CRMDealContact.organization_id == organization_id, CRMDealContact.contact_id.in_(loser_ids)).all():
            duplicate = db.query(CRMDealContact).filter(
                CRMDealContact.organization_id == organization_id,
                CRMDealContact.deal_id == link.deal_id,
                CRMDealContact.contact_id == winner_id,
                CRMDealContact.id != link.id,
            ).first()
            if duplicate:
                if link.is_primary and not duplicate.is_primary:
                    duplicate.is_primary = True
                    duplicate.role = duplicate.role or link.role
                    duplicate.influence_level = duplicate.influence_level or link.influence_level
                    duplicate.updated_by_user_id = user_id
                    duplicate.updated_at = now
                db.delete(link)
            else:
                link.contact_id = winner_id
                link.updated_by_user_id = user_id
                link.updated_at = now
            moved_links += 1
        update_count("deal_contacts", moved_links)
    if resource_name == "companies":
        update_count("contacts", db.query(CRMContact).filter(CRMContact.organization_id == organization_id, CRMContact.company_id.in_(loser_ids)).update(update_values(CRMContact, {"company_id": winner_id}), synchronize_session=False))
        update_count("deals", db.query(CRMDeal).filter(CRMDeal.organization_id == organization_id, CRMDeal.company_id.in_(loser_ids)).update(update_values(CRMDeal, {"company_id": winner_id}), synchronize_session=False))
        update_count("quotations", db.query(CRMQuotation).filter(CRMQuotation.organization_id == organization_id, CRMQuotation.company_id.in_(loser_ids)).update(update_values(CRMQuotation, {"company_id": winner_id}), synchronize_session=False))

    entity_names = {resource_name, resource_name.rstrip("s"), entity_type}
    if resource_name == "companies":
        entity_names.update({"account", "accounts", "company"})
    existing_custom_values = {
        (row.custom_field_id, row.entity)
        for row in _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(CRMCustomFieldValue.entity.in_(entity_names), CRMCustomFieldValue.record_id == winner_id)
        .all()
    }
    loser_custom_values = (
        _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(CRMCustomFieldValue.entity.in_(entity_names), CRMCustomFieldValue.record_id.in_(loser_ids))
        .all()
    )
    custom_count = 0
    for row in loser_custom_values:
        key = (row.custom_field_id, row.entity)
        if key in existing_custom_values:
            row.deleted_at = now
        else:
            row.record_id = winner_id
            existing_custom_values.add(key)
        row.updated_by_user_id = user_id
        row.updated_at = now
        custom_count += 1
    update_count("customFieldValues", custom_count)
    return counts


def _apply_merge_field_values(record: Any, resource: Resource, field_values: dict[str, Any] | None) -> None:
    if not field_values:
        return
    columns = _columns(resource.model)
    blocked = {"id", "organization_id", "created_at", "created_by_user_id", "deleted_at"}
    data = _normalize_payload(field_values)
    for key, value in data.items():
        if key in columns and key not in blocked:
            setattr(record, key, _coerce_value(columns[key], value))


def _linked_entity_from_data(data: dict[str, Any]) -> tuple[str | None, int | None]:
    entity_type = _normalize_entity_type(data.get("entity_type"))
    entity_id = data.get("entity_id")
    if entity_type and entity_id:
        return entity_type, int(entity_id)
    for entity_type, field in ENTITY_FIELD_BY_TYPE.items():
        if field and data.get(field):
            return entity_type, int(data[field])
    return None, None


def _sync_activity_link_fields(data: dict[str, Any]) -> None:
    entity_type, entity_id = _linked_entity_from_data(data)
    if not entity_type or not entity_id:
        return
    data["entity_type"] = entity_type
    data["entity_id"] = entity_id
    field = ENTITY_FIELD_BY_TYPE.get(entity_type)
    if field:
        data.setdefault(field, entity_id)


def _create_timeline_activity(
    db: Session,
    *,
    organization_id: int,
    entity_type: str,
    entity_id: int,
    activity_type: str,
    title: str,
    user_id: int | None = None,
    body: str | None = None,
    metadata: dict[str, Any] | None = None,
    activity_date: datetime | None = None,
    commit: bool = False,
) -> CRMActivity:
    entity_type = _normalize_entity_type(entity_type) or entity_type
    linked_field = ENTITY_FIELD_BY_TYPE.get(entity_type)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "activity_type": activity_type,
        "title": title,
        "subject": title,
        "body": body,
        "description": body,
        "metadata_json": metadata or {},
        "activity_date": activity_date or datetime.now(timezone.utc),
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
        "owner_user_id": user_id,
        "status": "Completed" if activity_type != "task" else "To Do",
    }
    if linked_field:
        values[linked_field] = entity_id
    activity = CRMActivity(**values)
    db.add(activity)
    if commit:
        db.commit()
        db.refresh(activity)
    return activity


def _activity_title_for_related(entity: str, item: dict[str, Any]) -> tuple[str, str, str | None]:
    if entity == "notes":
        return "note", "Note added", str(item.get("body") or "")
    if entity == "tasks":
        return "task", str(item.get("title") or "Task added"), str(item.get("description") or "")
    if entity == "calls":
        return "call", f"{item.get('direction') or 'Call'} call logged", str(item.get("notes") or item.get("outcome") or "")
    if entity == "emails":
        return "email", str(item.get("subject") or "Email logged"), str(item.get("body") or "")
    if entity == "meetings":
        return "meeting", str(item.get("title") or "Meeting logged"), str(item.get("description") or item.get("outcome") or "")
    if entity == "quotations":
        return "quotation", f"Quotation {item.get('quote_number') or item.get('id')} {str(item.get('status') or 'created').lower()}", str(item.get("notes") or "")
    return "system", "CRM activity", None


def _record_entity_type(entity: str) -> str | None:
    return ENTITY_TYPE_BY_CANONICAL.get(_canonical_entity(entity))


def _create_related_timeline_event(db: Session, entity: str, item: dict[str, Any], organization_id: int, user_id: int | None) -> None:
    canonical = _canonical_entity(entity)
    if canonical == "activities":
        return
    entity_type, entity_id = _linked_entity_from_data(item)
    if canonical == "quotations":
        linked_targets = []
        if item.get("deal_id"):
            linked_targets.append(("deal", int(item["deal_id"])))
        if item.get("company_id"):
            linked_targets.append(("account", int(item["company_id"])))
        if item.get("contact_id"):
            linked_targets.append(("contact", int(item["contact_id"])))
        linked_targets.append(("quotation", int(item["id"])))
        activity_type, title, body = _activity_title_for_related(canonical, item)
        for target_type, target_id in linked_targets:
            _create_timeline_activity(
                db,
                organization_id=organization_id,
                entity_type=target_type,
                entity_id=target_id,
                activity_type=activity_type,
                title=title,
                body=body,
                user_id=user_id,
                metadata={"sourceEntity": canonical, "sourceId": item.get("id"), "status": item.get("status")},
            )
        db.commit()
        return
    if not entity_type or not entity_id:
        return
    activity_type, title, body = _activity_title_for_related(canonical, item)
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        activity_type=activity_type,
        title=title,
        body=body,
        user_id=user_id,
        metadata={"sourceEntity": canonical, "sourceId": item.get("id"), "status": item.get("status")},
    )
    if canonical == "tasks" and str(item.get("status") or "").lower() in {"done", "completed", "complete"}:
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            activity_type="system",
            title="Task completed",
            body=str(item.get("title") or "Task"),
            user_id=user_id,
            metadata={"sourceEntity": canonical, "sourceId": item.get("id")},
        )
    db.commit()


def _create_update_timeline_events(
    db: Session,
    entity: str,
    record: Any,
    before: dict[str, Any],
    data: dict[str, Any],
    organization_id: int,
    user_id: int | None,
) -> None:
    canonical = _canonical_entity(entity)
    entity_type = _record_entity_type(canonical)
    if not entity_type:
        linked_data = _serialize(record)
        entity_type, entity_id = _linked_entity_from_data(linked_data)
    else:
        entity_id = record.id
    if not entity_type or not entity_id:
        return
    changed = []
    for key in IMPORTANT_UPDATE_FIELDS.intersection(data.keys()):
        old_value = before.get(key)
        new_value = getattr(record, key, None)
        if _json_ready(old_value) != _json_ready(new_value):
            changed.append((key, old_value, new_value))
    if not changed:
        return
    for key, old_value, new_value in changed:
        activity_type = "field_change"
        title = f"{key.replace('_', ' ').title()} updated"
        if key == "status":
            activity_type = "status_change"
            title = f"Status changed to {new_value}"
        elif key == "stage_id":
            activity_type = "stage_change"
            title = f"Stage changed to {new_value}"
        elif key == "owner_user_id":
            activity_type = "owner_change"
            title = f"Owner changed to {new_value or 'Unassigned'}"
        elif canonical == "quotations" and key == "status":
            activity_type = "quotation"
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=int(entity_id),
            activity_type=activity_type,
            title=title,
            body=f"{key.replace('_', ' ')} changed from {_json_ready(old_value) or '-'} to {_json_ready(new_value) or '-'}",
            user_id=user_id,
            metadata={"field": key, "old": _json_ready(old_value), "new": _json_ready(new_value), "sourceEntity": canonical, "sourceId": record.id},
        )
    if canonical == "tasks" and "status" in data and str(getattr(record, "status", "")).lower() in {"done", "completed", "complete"}:
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=int(entity_id),
            activity_type="system",
            title="Task completed",
            body=str(getattr(record, "title", "Task")),
            user_id=user_id,
            metadata={"sourceEntity": canonical, "sourceId": record.id},
        )
    db.commit()


def _email_template_rows(db: Session, organization_id: int, entity_type: str | None = None) -> list[dict[str, Any]]:
    query = _base_query(db, _get_resource("email-templates"), organization_id).filter(CRMEmailTemplate.is_active.is_(True))
    normalized = _normalize_entity_type(entity_type)
    if normalized:
        query = query.filter(or_(CRMEmailTemplate.entity_type == normalized, CRMEmailTemplate.entity_type.is_(None)))
    rows = query.order_by(asc(CRMEmailTemplate.name)).all()
    if rows:
        return [_serialize(row) for row in rows]
    defaults = [
        {
            "id": "intro",
            "name": "Introduction follow-up",
            "subject": "Following up on {{record.name}}",
            "body": "<p>Hello {{contact.name}},</p><p>Thank you for your time. I am sharing the next steps for {{record.name}}.</p>",
            "entityType": normalized,
        },
        {
            "id": "proposal",
            "name": "Proposal nudge",
            "subject": "Proposal update for {{deal.name}}",
            "body": "<p>Hi {{contact.name}},</p><p>Checking in on the proposal for {{deal.name}}. Happy to answer any questions.</p>",
            "entityType": normalized,
        },
    ]
    return defaults


def _message_template_rows(db: Session, organization_id: int, entity_type: str | None = None, channel: str | None = None) -> list[dict[str, Any]]:
    query = _base_query(db, _get_resource("message-templates"), organization_id).filter(CRMMessageTemplate.is_active.is_(True))
    normalized = _normalize_entity_type(entity_type)
    normalized_channel = str(channel or "").strip().lower()
    if normalized:
        query = query.filter(or_(CRMMessageTemplate.entity_type == normalized, CRMMessageTemplate.entity_type.is_(None)))
    if normalized_channel in {"sms", "whatsapp"}:
        query = query.filter(CRMMessageTemplate.channel == normalized_channel)
    rows = query.order_by(asc(CRMMessageTemplate.channel), asc(CRMMessageTemplate.name)).all()
    if rows:
        return [_serialize(row) for row in rows]
    defaults = [
        {
            "id": "follow-up-sms",
            "name": "Quick follow-up",
            "channel": "sms",
            "body": "Hi {{contact.name}}, following up on {{record.name}}. Please reply when convenient.",
            "entityType": normalized,
            "isActive": True,
        },
        {
            "id": "demo-whatsapp",
            "name": "Demo reminder",
            "channel": "whatsapp",
            "body": "Hi {{contact.name}}, this is a reminder for our discussion about {{record.name}}.",
            "entityType": normalized,
            "isActive": True,
        },
    ]
    if normalized_channel in {"sms", "whatsapp"}:
        defaults = [item for item in defaults if item["channel"] == normalized_channel]
    return defaults


CALENDAR_COLORS = {
    "task": "#2563eb",
    "meeting": "#7c3aed",
    "call": "#0891b2",
    "follow_up": "#f59e0b",
    "quotation": "#dc2626",
    "deal": "#16a34a",
}


def _calendar_item(
    *,
    source: str,
    record: Any,
    title: str,
    start: datetime,
    end: datetime | None = None,
    event_type: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    owner_id: int | None = None,
    status_value: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{source}:{record.id}",
        "recordId": record.id,
        "source": source,
        "title": title,
        "start": start.isoformat(),
        "end": (end or start).isoformat(),
        "type": event_type,
        "entityType": entity_type,
        "entityId": entity_id,
        "ownerId": owner_id,
        "status": status_value,
        "color": CALENDAR_COLORS.get(event_type, "#64748b"),
        "category": event_type.replace("_", " ").title(),
        "syncStatus": getattr(record, "sync_status", None),
        "externalProvider": getattr(record, "external_provider", None),
        "externalEventId": getattr(record, "external_event_id", None),
    }


def _event_link_from_record(record: Any, fallback_entity_type: str | None = None) -> tuple[str | None, int | None]:
    item = _serialize(record)
    entity_type, entity_id = _linked_entity_from_data(item)
    return entity_type or fallback_entity_type, entity_id


@router.get("/email-templates")
def list_email_templates(
    entityType: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    return {"items": _email_template_rows(db, _organization_id(db, current_user), entityType)}


@router.post("/email-templates", status_code=status.HTTP_201_CREATED)
def create_email_template(
    payload: CRMEmailTemplatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_admin", "crm_manage")),
):
    organization_id = _organization_id(db, current_user)
    template = CRMEmailTemplate(
        organization_id=organization_id,
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
        entity_type=_normalize_entity_type(payload.entityType),
        is_active=True,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _serialize(template)


@router.post("/emails/send", status_code=status.HTTP_201_CREATED)
def send_crm_email(
    payload: CRMEmailSendPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type = _normalize_entity_type(payload.entityType)
    if entity_type not in {"lead", "contact", "account", "deal"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Email can be sent only from lead, contact, account, or deal records")
    resource_name = {"lead": "leads", "contact": "contacts", "account": "companies", "deal": "deals"}[entity_type]
    _get_record(db, _get_resource(resource_name), payload.entityId, organization_id)
    to_emails = _split_emails(payload.to)
    cc_emails = _split_emails(payload.cc)
    bcc_emails = _split_emails(payload.bcc)
    if not to_emails:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one recipient is required")

    status_value = "draft" if payload.saveAsDraft else "sent"
    provider_message_id = None
    failure_reason = None
    if not payload.saveAsDraft:
        try:
            provider_message_id = _send_smtp_email(to=to_emails, cc=cc_emails, bcc=bcc_emails, subject=payload.subject, body=payload.body)
        except Exception as exc:
            status_value = "failed"
            failure_reason = str(exc)

    sent_at = datetime.now(timezone.utc) if status_value == "sent" else None
    linked_field = ENTITY_FIELD_BY_TYPE.get(entity_type)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "owner_user_id": current_user.id,
        "entity_type": entity_type,
        "entity_id": payload.entityId,
        "subject": payload.subject,
        "body": payload.body,
        "from_email": settings.MAIL_FROM,
        "to_email": ", ".join(to_emails),
        "cc": ", ".join(cc_emails) if cc_emails else None,
        "bcc": ", ".join(bcc_emails) if bcc_emails else None,
        "direction": "Outbound",
        "status": status_value,
        "provider_message_id": provider_message_id,
        "failure_reason": failure_reason,
        "sent_by_user_id": current_user.id,
        "sent_at": sent_at,
        "created_by_user_id": current_user.id,
        "updated_by_user_id": current_user.id,
    }
    if linked_field:
        values[linked_field] = payload.entityId
    email_log = CRMEmailLog(**values)
    db.add(email_log)
    db.commit()
    db.refresh(email_log)
    item = _serialize(email_log)
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=payload.entityId,
        activity_type="email",
        title=f"Email {status_value}: {payload.subject}",
        body=payload.body if status_value != "failed" else failure_reason,
        user_id=current_user.id,
        metadata={"sourceEntity": "emails", "sourceId": email_log.id, "status": status_value, "to": item["to_email"]},
        commit=True,
    )
    return item


@router.get("/message-templates")
def list_message_templates(
    entityType: str | None = None,
    channel: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    return {"items": _message_template_rows(db, _organization_id(db, current_user), entityType, channel)}


@router.post("/message-templates", status_code=status.HTTP_201_CREATED)
def create_message_template(
    payload: CRMMessageTemplatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_admin", "crm_manage")),
):
    organization_id = _organization_id(db, current_user)
    channel = str(payload.channel or "").strip().lower()
    if channel not in {"sms", "whatsapp"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="channel must be sms or whatsapp")
    template = CRMMessageTemplate(
        organization_id=organization_id,
        name=payload.name,
        channel=channel,
        body=payload.body,
        entity_type=_normalize_entity_type(payload.entityType),
        is_active=payload.isActive is not False,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _serialize(template)


@router.get("/messages")
def list_crm_messages(
    entityType: str,
    entityId: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type = _normalize_entity_type(entityType)
    if entity_type not in {"lead", "contact", "deal"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Messages are available for lead, contact, and deal records")
    resource_name = {"lead": "leads", "contact": "contacts", "deal": "deals"}[entity_type]
    _get_record(db, _get_resource(resource_name), entityId, organization_id)
    rows = (
        _base_query(db, _get_resource("messages"), organization_id)
        .filter(CRMMessage.entity_type == entity_type, CRMMessage.entity_id == entityId)
        .order_by(desc(CRMMessage.created_at))
        .all()
    )
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


@router.post("/messages/send", status_code=status.HTTP_201_CREATED)
def send_crm_message(
    payload: CRMMessageSendPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    channel = str(payload.channel or "").strip().lower()
    if channel not in {"sms", "whatsapp"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="channel must be sms or whatsapp")
    entity_type = _normalize_entity_type(payload.entityType)
    if entity_type not in {"lead", "contact", "deal"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Messages can be sent only from lead, contact, or deal records")
    resource_name = {"lead": "leads", "contact": "contacts", "deal": "deals"}[entity_type]
    _get_record(db, _get_resource(resource_name), payload.entityId, organization_id)
    to_number = _normalize_phone_number(payload.to)
    body = str(payload.body or "").strip()
    template = None
    if payload.templateId:
        template = _get_record(db, _get_resource("message-templates"), payload.templateId, organization_id)
        if template.channel != channel:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Template channel does not match message channel")
        if template.entity_type and template.entity_type != entity_type:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Template does not support this record type")
        body = body or template.body
    if not body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message body is required")

    provider = _message_provider(channel)
    status_value = "sent"
    provider_message_id = None
    failure_reason = None
    try:
        status_value, provider_message_id = provider.send(channel=channel, to=to_number, body=body)
    except Exception as exc:
        status_value = "failed"
        failure_reason = str(exc)
    sent_at = datetime.now(timezone.utc) if status_value in {"sent", "delivered"} else None
    message = CRMMessage(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=payload.entityId,
        channel=channel,
        to=to_number,
        body=body,
        status=status_value,
        provider=provider.name,
        provider_message_id=provider_message_id,
        failure_reason=failure_reason,
        template_id=template.id if template else None,
        sent_by_user_id=current_user.id,
        sent_at=sent_at,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    item = _serialize(message)
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=payload.entityId,
        activity_type="message",
        title=f"{channel.title()} message {status_value}",
        body=body if status_value != "failed" else failure_reason,
        user_id=current_user.id,
        metadata={"sourceEntity": "messages", "sourceId": message.id, "status": status_value, "channel": channel, "to": to_number, "provider": provider.name},
        commit=True,
    )
    return item


@router.get("/webhooks")
def list_webhooks(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    _retry_due_webhook_deliveries(db, organization_id)
    db.commit()
    rows = (
        _base_query(db, _get_resource("webhooks"), organization_id)
        .order_by(asc(CRMWebhook.name), desc(CRMWebhook.id))
        .all()
    )
    return {"items": [_serialize_webhook(row) for row in rows], "total": len(rows), "events": sorted(CRM_WEBHOOK_EVENTS)}


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
def create_webhook(
    payload: CRMWebhookPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_admin", "crm_manage")),
):
    organization_id = _organization_id(db, current_user)
    if not payload.name or not payload.url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name and url are required")
    row = CRMWebhook(
        organization_id=organization_id,
        name=payload.name,
        url=_validate_webhook_url(payload.url),
        secret=payload.secret or secrets.token_urlsafe(32),
        events=_normalize_webhook_events(payload.events),
        is_active=payload.isActive is not False,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_webhook(row)


@router.patch("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: int,
    payload: CRMWebhookPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_admin", "crm_manage")),
):
    organization_id = _organization_id(db, current_user)
    row = _get_record(db, _get_resource("webhooks"), webhook_id, organization_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and payload.name:
        row.name = payload.name
    if "url" in data and payload.url:
        row.url = _validate_webhook_url(payload.url)
    if "secret" in data and payload.secret:
        row.secret = payload.secret
    if "events" in data:
        row.events = _normalize_webhook_events(payload.events)
    if "isActive" in data:
        row.is_active = payload.isActive is not False
    row.updated_by_user_id = current_user.id
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _serialize_webhook(row)


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_admin", "crm_manage")),
):
    organization_id = _organization_id(db, current_user)
    row = _get_record(db, _get_resource("webhooks"), webhook_id, organization_id)
    row.deleted_at = datetime.now(timezone.utc)
    row.is_active = False
    row.updated_by_user_id = current_user.id
    db.commit()
    return {"message": "CRM webhook deleted"}


@router.post("/webhooks/{webhook_id}/test", status_code=status.HTTP_201_CREATED)
def test_webhook(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_admin", "crm_manage")),
):
    organization_id = _organization_id(db, current_user)
    webhook = _get_record(db, _get_resource("webhooks"), webhook_id, organization_id)
    payload = _webhook_payload("lead.created", organization_id, {"id": "test", "name": "Test Lead"}, current_user.id, {"test": True})
    delivery = CRMWebhookDelivery(
        organization_id=organization_id,
        webhook_id=webhook.id,
        event_type="lead.created",
        payload=payload,
        status="pending",
        attempt_count=0,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(delivery)
    db.flush()
    _deliver_webhook(db, webhook, delivery)
    db.commit()
    db.refresh(delivery)
    return _serialize(delivery)


@router.get("/webhooks/{webhook_id}/deliveries")
def list_webhook_deliveries(
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    _get_record(db, _get_resource("webhooks"), webhook_id, organization_id)
    _retry_due_webhook_deliveries(db, organization_id, webhook_id)
    db.commit()
    rows = (
        _base_query(db, _get_resource("webhook-deliveries"), organization_id)
        .filter(CRMWebhookDelivery.webhook_id == webhook_id)
        .order_by(desc(CRMWebhookDelivery.created_at), desc(CRMWebhookDelivery.id))
        .limit(100)
        .all()
    )
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


@router.get("/approval-workflows")
def list_approval_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    workflows = (
        db.query(CRMApprovalWorkflow)
        .filter(CRMApprovalWorkflow.organization_id == organization_id, CRMApprovalWorkflow.deleted_at.is_(None))
        .order_by(asc(CRMApprovalWorkflow.entity_type), asc(CRMApprovalWorkflow.id))
        .all()
    )
    return {"items": [_serialize_approval_workflow(workflow) for workflow in workflows], "total": len(workflows)}


@router.post("/approval-workflows", status_code=status.HTTP_201_CREATED)
def create_approval_workflow(
    payload: CRMApprovalWorkflowPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type = _normalize_entity_type(payload.entityType)
    _approval_resource_for(entity_type or "")
    if not payload.name or not payload.triggerType:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name and triggerType are required")
    workflow = CRMApprovalWorkflow(
        organization_id=organization_id,
        name=payload.name,
        entity_type=entity_type,
        trigger_type=payload.triggerType,
        conditions=payload.conditions or {},
        is_active=payload.isActive is not False,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(workflow)
    db.flush()
    steps = payload.steps or [CRMApprovalStepPayload(stepOrder=1, approverType="user", approverId=current_user.id, actionOnReject="stop")]
    for index, step_payload in enumerate(steps, start=1):
        approver_type = str(step_payload.approverType or "user").lower()
        if approver_type not in {"user", "role", "manager"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="approverType must be user, role, or manager")
        db.add(
            CRMApprovalStep(
                workflow_id=workflow.id,
                step_order=step_payload.stepOrder or index,
                approver_type=approver_type,
                approver_id=step_payload.approverId,
                action_on_reject=step_payload.actionOnReject or "stop",
            )
        )
    db.commit()
    db.refresh(workflow)
    return _serialize_approval_workflow(workflow)


@router.patch("/approval-workflows/{workflow_id}")
def update_approval_workflow(
    workflow_id: int,
    payload: CRMApprovalWorkflowPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    workflow = (
        db.query(CRMApprovalWorkflow)
        .filter(CRMApprovalWorkflow.organization_id == organization_id, CRMApprovalWorkflow.id == workflow_id, CRMApprovalWorkflow.deleted_at.is_(None))
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval workflow not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and payload.name:
        workflow.name = payload.name
    if "entityType" in data and payload.entityType:
        entity_type = _normalize_entity_type(payload.entityType)
        _approval_resource_for(entity_type or "")
        workflow.entity_type = entity_type
    if "triggerType" in data and payload.triggerType:
        workflow.trigger_type = payload.triggerType
    if "conditions" in data:
        workflow.conditions = payload.conditions or {}
    if "isActive" in data:
        workflow.is_active = payload.isActive is not False
    workflow.updated_by_user_id = current_user.id
    workflow.updated_at = datetime.now(timezone.utc)
    if payload.steps is not None:
        for existing in list(workflow.steps):
            db.delete(existing)
        db.flush()
        for index, step_payload in enumerate(payload.steps, start=1):
            approver_type = str(step_payload.approverType or "user").lower()
            if approver_type not in {"user", "role", "manager"}:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="approverType must be user, role, or manager")
            db.add(
                CRMApprovalStep(
                    workflow_id=workflow.id,
                    step_order=step_payload.stepOrder or index,
                    approver_type=approver_type,
                    approver_id=step_payload.approverId,
                    action_on_reject=step_payload.actionOnReject or "stop",
                )
            )
    db.commit()
    db.refresh(workflow)
    return _serialize_approval_workflow(workflow)


@router.post("/approvals/submit", status_code=status.HTTP_201_CREATED)
def submit_approval(
    payload: CRMApprovalSubmitPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type = _normalize_entity_type(payload.entityType) or ""
    resource_name = _approval_resource_for(entity_type)
    record = _get_record(db, _get_resource(resource_name), payload.entityId, organization_id)
    existing = _active_blocking_approval(db, organization_id, entity_type, record.id)
    if existing and existing.status == "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This record already has a pending approval")
    workflow = _select_approval_workflow(db, organization_id, entity_type, record, payload.workflowId, payload.triggerType)
    if not workflow.steps:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Approval workflow has no steps")
    request = CRMApprovalRequest(
        organization_id=organization_id,
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=record.id,
        status="pending",
        submitted_by=current_user.id,
    )
    db.add(request)
    db.flush()
    for index, step in enumerate(sorted(workflow.steps, key=lambda item: item.step_order or 0)):
        db.add(
            CRMApprovalRequestStep(
                request_id=request.id,
                step_id=step.id,
                approver_id=_resolve_approver_id(db, step, record, current_user.id),
                status="pending" if index == 0 else "waiting",
            )
        )
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=record.id,
        activity_type="approval_submitted",
        title=f"Submitted for approval: {workflow.name}",
        body=payload.comments,
        user_id=current_user.id,
        metadata={"workflowId": workflow.id, "requestId": request.id},
    )
    db.commit()
    db.refresh(request)
    return _serialize_approval_request(request)


def _act_on_approval(db: Session, organization_id: int, request_id: int, current_user: User, comments: str | None, approve: bool) -> CRMApprovalRequest:
    request = _approval_query(db, organization_id).filter(CRMApprovalRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Approval is already {request.status}")
    step = (
        db.query(CRMApprovalRequestStep)
        .filter(
            CRMApprovalRequestStep.request_id == request.id,
            CRMApprovalRequestStep.status == "pending",
        )
        .order_by(asc(CRMApprovalRequestStep.id))
        .first()
    )
    if not step:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pending approval step is available")
    if not current_user.is_superuser and step.approver_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This approval step is assigned to another approver")
    now = datetime.now(timezone.utc)
    step.status = "approved" if approve else "rejected"
    step.comments = comments
    step.acted_at = now
    if approve:
        next_step = (
            db.query(CRMApprovalRequestStep)
            .filter(CRMApprovalRequestStep.request_id == request.id, CRMApprovalRequestStep.status == "waiting")
            .order_by(asc(CRMApprovalRequestStep.id))
            .first()
        )
        if next_step:
            next_step.status = "pending"
        else:
            request.status = "approved"
            request.completed_at = now
    else:
        request.status = "rejected"
        request.completed_at = now
        if step.step and step.step.action_on_reject == "send_back":
            waiting_steps = db.query(CRMApprovalRequestStep).filter(CRMApprovalRequestStep.request_id == request.id, CRMApprovalRequestStep.status == "waiting").all()
            for waiting_step in waiting_steps:
                waiting_step.status = "cancelled"
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        activity_type="approval_approved" if approve else "approval_rejected",
        title="Approval step approved" if approve else "Approval rejected",
        body=comments,
        user_id=current_user.id,
        metadata={"requestId": request.id, "stepId": step.id},
    )
    if request.status in {"approved", "rejected"}:
        event_type = "approval.approved" if request.status == "approved" else "approval.rejected"
        _enqueue_webhook_event(db, organization_id, event_type, _serialize_approval_request(request), current_user.id)
        if request.status == "approved" and request.entity_type == "quotation":
            _enqueue_webhook_event(db, organization_id, "quotation.approved", {"id": request.entity_id, "entityType": "quotation"}, current_user.id, {"approvalRequestId": request.id})
    db.commit()
    db.refresh(request)
    return request


@router.post("/approvals/{request_id}/approve")
def approve_request(
    request_id: int,
    payload: CRMApprovalActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    return _serialize_approval_request(_act_on_approval(db, _organization_id(db, current_user), request_id, current_user, payload.comments, True))


@router.post("/approvals/{request_id}/reject")
def reject_request(
    request_id: int,
    payload: CRMApprovalActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    return _serialize_approval_request(_act_on_approval(db, _organization_id(db, current_user), request_id, current_user, payload.comments, False))


@router.get("/approvals/my-pending")
def my_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    rows = (
        db.query(CRMApprovalRequest)
        .join(CRMApprovalRequestStep, CRMApprovalRequestStep.request_id == CRMApprovalRequest.id)
        .filter(
            CRMApprovalRequest.organization_id == organization_id,
            CRMApprovalRequest.status == "pending",
            CRMApprovalRequestStep.status == "pending",
            CRMApprovalRequestStep.approver_id == current_user.id,
        )
        .order_by(desc(CRMApprovalRequest.submitted_at))
        .all()
    )
    return {"items": [_serialize_approval_request(row) for row in rows], "total": len(rows)}


@router.get("/approvals")
def list_approvals(
    entityType: str | None = None,
    entityId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    query = _approval_query(db, organization_id)
    if entityType:
        entity_type = _normalize_entity_type(entityType)
        query = query.filter(CRMApprovalRequest.entity_type == entity_type)
    if entityId is not None:
        query = query.filter(CRMApprovalRequest.entity_id == entityId)
    rows = query.order_by(desc(CRMApprovalRequest.submitted_at), desc(CRMApprovalRequest.id)).limit(100).all()
    return {"items": [_serialize_approval_request(row) for row in rows], "total": len(rows)}


@router.get("/duplicates")
def list_duplicates(
    entityType: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    resource_name = _duplicate_resource_name(entityType)
    groups = _duplicate_groups(db, organization_id, resource_name)
    return {"items": groups, "total": len(groups), "entityType": _duplicate_entity_type(resource_name)}


@router.post("/duplicates/scan")
def scan_duplicates(
    payload: CRMDuplicateScanPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    resource_names = [_duplicate_resource_name(payload.entityType)] if payload.entityType else ["leads", "contacts", "companies"]
    groups: list[dict[str, Any]] = []
    for resource_name in resource_names:
        groups.extend(_duplicate_groups(db, organization_id, resource_name))
    return {"items": groups, "total": len(groups)}


@router.post("/duplicates/merge")
def merge_duplicates(
    payload: CRMDuplicateMergePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    resource_name = _duplicate_resource_name(payload.entityType)
    resource = _get_resource(resource_name)
    loser_ids = sorted({int(record_id) for record_id in payload.loserIds if int(record_id) != int(payload.winnerId)})
    if not loser_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one losing record is required")
    winner = _get_record(db, resource, payload.winnerId, organization_id)
    losers = [_get_record(db, resource, loser_id, organization_id) for loser_id in loser_ids]
    detected_groups = _duplicate_groups(db, organization_id, resource_name, target_id=winner.id)
    detected_ids = {record_id for group in detected_groups for record_id in group["recordIds"]}
    if not set(loser_ids).issubset(detected_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected records are not in a detected duplicate group")

    _apply_merge_field_values(winner, resource, payload.fieldValues)
    now = datetime.now(timezone.utc)
    columns = _columns(resource.model)
    if "updated_by_user_id" in columns:
        winner.updated_by_user_id = current_user.id
    if "updated_at" in columns:
        winner.updated_at = now
    related_counts = _merge_related_records(db, organization_id, resource_name, winner.id, loser_ids, current_user.id)
    for loser in losers:
        loser.deleted_at = now
        if "updated_by_user_id" in columns:
            loser.updated_by_user_id = current_user.id
        if "updated_at" in columns:
            loser.updated_at = now
    entity_type = _duplicate_entity_type(resource_name)
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=winner.id,
        activity_type="duplicate_merge",
        title="Merged duplicate record",
        body=f"Merged duplicate record(s): {', '.join(str(item.id) for item in losers)}",
        user_id=current_user.id,
        metadata={"winnerId": winner.id, "loserIds": loser_ids, "relatedCounts": related_counts},
    )
    for loser in losers:
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=loser.id,
            activity_type="duplicate_merge",
            title="Merged duplicate record",
            body=f"Merged into record {winner.id}",
            user_id=current_user.id,
            metadata={"winnerId": winner.id, "loserId": loser.id},
        )
    db.commit()
    db.refresh(winner)
    return {"winner": _serialize(winner), "mergedIds": loser_ids, "relatedCounts": related_counts}


@router.get("/calendar-integrations")
def list_calendar_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    rows = (
        db.query(CRMCalendarIntegration)
        .filter(CRMCalendarIntegration.organization_id == organization_id, CRMCalendarIntegration.user_id == current_user.id, CRMCalendarIntegration.deleted_at.is_(None))
        .order_by(asc(CRMCalendarIntegration.provider))
        .all()
    )
    return {"items": [_serialize_calendar_integration(row) for row in rows], "total": len(rows)}


@router.post("/calendar-integrations/connect", status_code=status.HTTP_201_CREATED)
def connect_calendar_integration(
    payload: CRMCalendarIntegrationConnectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    provider = _normalize_calendar_provider(payload.provider)
    access_token = payload.accessToken
    refresh_token = payload.refreshToken
    if payload.mock or provider == "mock":
        access_token = access_token or f"mock-access-token-{current_user.id}"
        refresh_token = refresh_token or f"mock-refresh-token-{current_user.id}"
    elif provider == "google" and not (settings.CRM_GOOGLE_CALENDAR_CLIENT_ID and settings.CRM_GOOGLE_CALENDAR_CLIENT_SECRET):
        access_token = access_token or f"placeholder-google-access-token-{current_user.id}"
        refresh_token = refresh_token or f"placeholder-google-refresh-token-{current_user.id}"
    elif provider == "outlook" and not (settings.CRM_OUTLOOK_CALENDAR_CLIENT_ID and settings.CRM_OUTLOOK_CALENDAR_CLIENT_SECRET):
        access_token = access_token or f"placeholder-outlook-access-token-{current_user.id}"
        refresh_token = refresh_token or f"placeholder-outlook-refresh-token-{current_user.id}"
    if not access_token:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="OAuth access token is required unless using the mock provider")
    existing = _active_calendar_integration(db, organization_id, current_user.id, provider)
    row = existing or CRMCalendarIntegration(organization_id=organization_id, user_id=current_user.id, provider=provider, created_by_user_id=current_user.id)
    row.access_token_encrypted = _encrypt_calendar_token(access_token)
    row.refresh_token_encrypted = _encrypt_calendar_token(refresh_token)
    row.expires_at = payload.expiresAt
    row.is_active = True
    row.updated_by_user_id = current_user.id
    row.updated_at = datetime.now(timezone.utc)
    if not existing:
        db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_calendar_integration(row)


@router.delete("/calendar-integrations/{integration_id}")
def delete_calendar_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    row = (
        db.query(CRMCalendarIntegration)
        .filter(CRMCalendarIntegration.organization_id == organization_id, CRMCalendarIntegration.user_id == current_user.id, CRMCalendarIntegration.id == integration_id, CRMCalendarIntegration.deleted_at.is_(None))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar integration not found")
    row.is_active = False
    row.deleted_at = datetime.now(timezone.utc)
    row.updated_by_user_id = current_user.id
    db.commit()
    return {"message": "Calendar integration disconnected"}


@router.post("/meetings/{meeting_id}/sync")
def sync_meeting_calendar(
    meeting_id: int,
    payload: CRMMeetingSyncPayload | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    meeting = _get_record(db, _get_resource("meetings"), meeting_id, organization_id)
    _sync_meeting_to_calendar(db, organization_id, meeting, current_user, payload.provider if payload else None)
    db.commit()
    db.refresh(meeting)
    if meeting.sync_status == "synced":
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type="meeting",
            entity_id=meeting.id,
            activity_type="calendar_sync",
            title="Meeting synced to external calendar",
            body=meeting.title,
            user_id=current_user.id,
            metadata={"provider": meeting.external_provider, "externalEventId": meeting.external_event_id, "twoWay": bool(payload.twoWay) if payload else False},
            commit=True,
        )
    return _serialize(meeting)


@router.post("/calendar/webhook")
def calendar_webhook_placeholder(request: Request):
    return {"status": "accepted", "message": "Calendar webhook placeholder. TODO: verify provider signatures and enqueue two-way sync."}


@router.get("/calendar")
def crm_calendar(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    now = datetime.now(timezone.utc)
    start = _parse_datetime_param(startDate, datetime(now.year, now.month, 1, tzinfo=timezone.utc))
    end = _parse_datetime_param(endDate, start.replace(day=28) if not endDate else now)
    if not endDate:
        end = datetime(start.year + (1 if start.month == 12 else 0), 1 if start.month == 12 else start.month + 1, 1, tzinfo=timezone.utc)
    if end < start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="endDate must be after startDate")

    organization_id = _organization_id(db, current_user)
    requested_type = (type or "").strip().lower().replace("-", "_")
    owner_id = ownerId
    events: list[dict[str, Any]] = []

    def include(event_type: str) -> bool:
        return not requested_type or requested_type in {event_type, "all"}

    if include("task"):
        query = _base_query(db, _get_resource("tasks"), organization_id).filter(CRMTask.due_date.is_not(None), CRMTask.due_date >= start, CRMTask.due_date <= end)
        if owner_id:
            query = query.filter(CRMTask.owner_user_id == owner_id)
        for task in query.order_by(asc(CRMTask.due_date)).all():
            entity_type, entity_id = _event_link_from_record(task)
            task_start = _as_datetime(task.due_date)
            if task_start:
                events.append(_calendar_item(source="tasks", record=task, title=task.title, start=task_start, event_type="task", entity_type=entity_type, entity_id=entity_id, owner_id=task.owner_user_id, status_value=task.status))

    if include("meeting"):
        query = _base_query(db, _get_resource("meetings"), organization_id).filter(CRMMeeting.start_time <= end, CRMMeeting.end_time >= start)
        if owner_id:
            query = query.filter(CRMMeeting.owner_user_id == owner_id)
        for meeting in query.order_by(asc(CRMMeeting.start_time)).all():
            entity_type, entity_id = _event_link_from_record(meeting)
            meeting_start = _as_datetime(meeting.start_time)
            meeting_end = _as_datetime(meeting.end_time)
            if meeting_start:
                events.append(_calendar_item(source="meetings", record=meeting, title=meeting.title, start=meeting_start, end=meeting_end, event_type="meeting", entity_type=entity_type, entity_id=entity_id, owner_id=meeting.owner_user_id, status_value=meeting.status))

    if include("call"):
        query = _base_query(db, _get_resource("calls"), organization_id).filter(CRMCallLog.call_time >= start, CRMCallLog.call_time <= end)
        if owner_id:
            query = query.filter(CRMCallLog.owner_user_id == owner_id)
        for call in query.order_by(asc(CRMCallLog.call_time)).all():
            entity_type, entity_id = _event_link_from_record(call)
            call_start = _as_datetime(call.call_time)
            if call_start:
                title = f"{call.direction or 'Call'} call"
                if call.phone_number:
                    title = f"{title}: {call.phone_number}"
                events.append(_calendar_item(source="calls", record=call, title=title, start=call_start, event_type="call", entity_type=entity_type, entity_id=entity_id, owner_id=call.owner_user_id, status_value=call.outcome))

    if include("follow_up"):
        activity_query = _base_query(db, _get_resource("activities"), organization_id).filter(CRMActivity.activity_date >= start, CRMActivity.activity_date <= end)
        if owner_id:
            activity_query = activity_query.filter(CRMActivity.owner_user_id == owner_id)
        for activity in activity_query.order_by(asc(CRMActivity.activity_date)).all():
            activity_start = _as_datetime(activity.activity_date)
            if activity_start:
                events.append(_calendar_item(source="activities", record=activity, title=activity.title or activity.subject or "CRM follow-up", start=activity_start, event_type="follow_up", entity_type=activity.entity_type, entity_id=activity.entity_id, owner_id=activity.owner_user_id, status_value=activity.status))

    if include("quotation"):
        quote_start = start.date()
        quote_end = end.date()
        query = _base_query(db, _get_resource("quotations"), organization_id).filter(CRMQuotation.expiry_date >= quote_start, CRMQuotation.expiry_date <= quote_end)
        if owner_id:
            query = query.filter(CRMQuotation.owner_user_id == owner_id)
        for quote in query.order_by(asc(CRMQuotation.expiry_date)).all():
            expiry = _as_datetime(quote.expiry_date)
            if expiry:
                events.append(_calendar_item(source="quotations", record=quote, title=f"Quote expires: {quote.quote_number}", start=expiry, event_type="quotation", entity_type="quotation", entity_id=quote.id, owner_id=quote.owner_user_id, status_value=quote.status))

    if include("deal"):
        deal_start = start.date()
        deal_end = end.date()
        query = _base_query(db, _get_resource("deals"), organization_id).filter(CRMDeal.expected_close_date >= deal_start, CRMDeal.expected_close_date <= deal_end)
        if owner_id:
            query = query.filter(CRMDeal.owner_user_id == owner_id)
        for deal in query.order_by(asc(CRMDeal.expected_close_date)).all():
            close_date = _as_datetime(deal.expected_close_date)
            if close_date:
                events.append(_calendar_item(source="deals", record=deal, title=f"Expected close: {deal.name}", start=close_date, event_type="deal", entity_type="deal", entity_id=deal.id, owner_id=deal.owner_user_id, status_value=deal.status))

    events.sort(key=lambda item: str(item["start"]))
    return {"items": events, "startDate": start.isoformat(), "endDate": end.isoformat(), "total": len(events)}


@router.post("/custom-field-values/upsert")
def upsert_custom_field_value(
    payload: CRMCustomFieldValueUpsertPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    field = _get_record(db, _get_resource("custom-fields"), payload.customFieldId, organization_id)
    if not field.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Custom field is inactive")
    entity = _normalize_custom_field_entity(payload.entity or field.entity)
    if entity != field.entity:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Custom field does not belong to this entity")
    resource_name = _resource_for_custom_entity(entity)
    if resource_name:
        _get_record(db, _get_resource(resource_name), payload.recordId, organization_id)
    values = _custom_field_storage(field, payload.value)
    row = (
        _base_query(db, _get_resource("custom-field-values"), organization_id)
        .filter(
            CRMCustomFieldValue.custom_field_id == field.id,
            CRMCustomFieldValue.entity.in_([field.entity, field.entity.replace("-", "_")]),
            CRMCustomFieldValue.record_id == payload.recordId,
        )
        .first()
    )
    if not row:
        row = CRMCustomFieldValue(
            organization_id=organization_id,
            custom_field_id=field.id,
            entity=field.entity,
            record_id=payload.recordId,
            created_by_user_id=current_user.id,
        )
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by_user_id = current_user.id
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    item = _serialize(row)
    item["value"] = _custom_field_value(row)
    return item


@router.post("/pipelines/{pipeline_id}/stages", status_code=status.HTTP_201_CREATED)
def create_pipeline_stage(
    pipeline_id: int,
    payload: CRMRecordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    _get_record(db, _get_resource("pipelines"), pipeline_id, organization_id)
    data = _validate_and_build(_get_resource("pipeline-stages"), {**payload.model_dump(), "pipelineId": pipeline_id}, partial=False)
    data["pipeline_id"] = pipeline_id
    data["organization_id"] = organization_id
    data["created_by_user_id"] = current_user.id
    data["updated_by_user_id"] = current_user.id
    if data.get("position") is None:
        last_position = (
            _base_query(db, _get_resource("pipeline-stages"), organization_id)
            .filter(CRMPipelineStage.pipeline_id == pipeline_id)
            .order_by(desc(CRMPipelineStage.position))
            .first()
        )
        data["position"] = (last_position.position if last_position and last_position.position is not None else 0) + 1
    stage = CRMPipelineStage(**data)
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return _serialize(stage)


@router.get("/lead-scoring-rules")
def list_lead_scoring_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    _ensure_default_scoring_rules(db, organization_id, current_user.id)
    db.commit()
    rows = _base_query(db, _get_resource("lead-scoring-rules"), organization_id).order_by(asc(CRMLeadScoringRule.id)).all()
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


@router.post("/leads/{lead_id}/recalculate-score")
def recalculate_lead_score(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    lead = _get_record(db, _get_resource("leads"), lead_id, organization_id)
    result = _apply_lead_score(db, lead, organization_id, current_user.id, force=True, commit=True)
    item = _serialize(lead)
    item["scoreReasons"] = result["reasons"]
    return item


@router.post("/leads/recalculate-scores")
def recalculate_lead_scores(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    leads = _base_query(db, _get_resource("leads"), organization_id).all()
    updated = 0
    for lead in leads:
        if str(lead.lead_score_mode or "automatic").lower() == "manual":
            continue
        _apply_lead_score(db, lead, organization_id, current_user.id)
        updated += 1
    db.commit()
    return {"updated": updated, "total": len(leads)}


@router.get("/custom-fields")
def list_custom_fields(
    entityType: str | None = None,
    entity: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    query = _base_query(db, _get_resource("custom-fields"), organization_id)
    if entityType or entity:
        query = query.filter(CRMCustomField.entity == _normalize_custom_field_entity(entityType or entity))
    rows = query.order_by(asc(CRMCustomField.entity), asc(CRMCustomField.position), asc(CRMCustomField.label)).all()
    return {"items": [_serialize(row) for row in rows], "total": len(rows), "page": 1, "per_page": len(rows), "pages": 1 if rows else 0}


@router.get("/quotations/{quotation_id}/pdf")
def generate_quotation_pdf(
    quotation_id: int,
    download: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    quotation = _get_record(db, _get_resource("quotations"), quotation_id, organization_id)
    file_path, file_name, file_url = _generate_quotation_pdf(db, quotation, organization_id, current_user.id)
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type="quotation",
        entity_id=quotation.id,
        activity_type="quotation_pdf",
        title="Quotation PDF generated",
        body=f"Generated PDF for quotation {quotation.quote_number}.",
        user_id=current_user.id,
        metadata={"pdfUrl": file_url, "fileName": file_name},
    )
    db.commit()
    disposition = "attachment" if download else "inline"
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=file_name,
        headers={"Content-Disposition": f'{disposition}; filename="{file_name}"'},
    )


@router.post("/quotations/{quotation_id}/send-pdf-email", status_code=status.HTTP_201_CREATED)
def send_quotation_pdf_email(
    quotation_id: int,
    payload: CRMQuotationPdfEmailPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    quotation = _get_record(db, _get_resource("quotations"), quotation_id, organization_id)
    file_path, file_name, file_url = _generate_quotation_pdf(db, quotation, organization_id, current_user.id)
    contact = _get_record(db, _get_resource("contacts"), quotation.contact_id, organization_id) if quotation.contact_id else None
    account = _get_record(db, _get_resource("companies"), quotation.company_id, organization_id) if quotation.company_id else None
    to_emails = _split_emails(payload.to or getattr(contact, "email", None) or getattr(account, "email", None))
    cc_emails = _split_emails(payload.cc)
    bcc_emails = _split_emails(payload.bcc)
    if not to_emails:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A recipient email address is required")

    subject = payload.subject or f"Quotation {quotation.quote_number}"
    body = payload.body or f"Please find attached quotation {quotation.quote_number}."
    status_value = "draft" if payload.saveAsDraft else "sent"
    provider_message_id = None
    failure_reason = None
    if not payload.saveAsDraft:
        try:
            provider_message_id = _send_smtp_email_with_attachment(
                to=to_emails,
                cc=cc_emails,
                bcc=bcc_emails,
                subject=subject,
                body=body,
                attachment_path=file_path,
                attachment_name=file_name,
            )
        except RuntimeError as exc:
            status_value = "failed"
            failure_reason = str(exc)
        except Exception as exc:  # pragma: no cover - SMTP integration failure details vary by provider.
            status_value = "failed"
            failure_reason = str(exc)

    email_log = CRMEmailLog(
        organization_id=organization_id,
        owner_user_id=current_user.id,
        entity_type="quotation",
        entity_id=quotation.id,
        subject=subject,
        body=body,
        from_email=settings.MAIL_FROM,
        to_email=", ".join(to_emails),
        cc=", ".join(cc_emails) if cc_emails else None,
        bcc=", ".join(bcc_emails) if bcc_emails else None,
        direction="Outbound",
        status=status_value,
        provider_message_id=provider_message_id,
        failure_reason=failure_reason,
        sent_by_user_id=current_user.id,
        contact_id=quotation.contact_id,
        company_id=quotation.company_id,
        deal_id=quotation.deal_id,
        sent_at=datetime.now(timezone.utc) if status_value == "sent" else None,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(email_log)
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type="quotation",
        entity_id=quotation.id,
        activity_type="quotation_pdf",
        title="Quotation PDF generated",
        body=f"Generated PDF for quotation {quotation.quote_number}.",
        user_id=current_user.id,
        metadata={"pdfUrl": file_url, "fileName": file_name},
    )
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type="quotation",
        entity_id=quotation.id,
        activity_type="email",
        title=f"Quotation PDF email {status_value}",
        body=body,
        user_id=current_user.id,
        metadata={"pdfUrl": file_url, "fileName": file_name, "to": ", ".join(to_emails), "status": status_value},
    )
    db.commit()
    db.refresh(email_log)
    return {"email": _serialize(email_log), "pdfUrl": file_url, "pdfFileName": file_name, "status": status_value}


def _win_loss_payload(db: Session, organization_id: int, deals: list[CRMDeal], start: datetime, end: datetime) -> dict[str, Any]:
    closed = _closed_outcomes(deals)
    won_deals = [deal for deal in closed if _deal_status(deal) == "won"]
    lost_deals = [deal for deal in closed if _deal_status(deal) == "lost"]
    won_revenue = round(sum(_deal_amount(deal) for deal in won_deals), 2)
    lost_amount = round(sum(_deal_amount(deal) for deal in lost_deals), 2)

    monthly = {key: {"month": key, "label": _month_label(key), "won": 0, "lost": 0, "wonRevenue": 0.0, "lostAmount": 0.0} for key in _month_keys_between(start, end)}
    for deal in closed:
        key = _month_key(_deal_report_datetime(deal))
        bucket = monthly.setdefault(key, {"month": key, "label": _month_label(key), "won": 0, "lost": 0, "wonRevenue": 0.0, "lostAmount": 0.0})
        amount = _deal_amount(deal)
        if _deal_status(deal) == "won":
            bucket["won"] += 1
            bucket["wonRevenue"] += amount
        else:
            bucket["lost"] += 1
            bucket["lostAmount"] += amount
    monthly_rows = []
    for bucket in monthly.values():
        bucket["total"] = bucket["won"] + bucket["lost"]
        bucket["winRate"] = _rate(bucket["won"], bucket["lost"])
        bucket["wonRevenue"] = round(bucket["wonRevenue"], 2)
        bucket["lostAmount"] = round(bucket["lostAmount"], 2)
        monthly_rows.append(bucket)
    monthly_rows.sort(key=lambda item: item["month"])

    owner_names = _owner_names(db, {deal.owner_user_id for deal in closed})
    pipeline_names = _pipeline_names(db, organization_id, {deal.pipeline_id for deal in closed})
    by_owner = _bucket_outcomes(deals, lambda deal: owner_names.get(deal.owner_user_id, f"User {deal.owner_user_id}" if deal.owner_user_id else "Unassigned"))
    by_pipeline = _bucket_outcomes(deals, lambda deal: pipeline_names.get(deal.pipeline_id, f"Pipeline {deal.pipeline_id}" if deal.pipeline_id else "Unassigned"))
    by_source = _bucket_outcomes(deals, _deal_source)

    lost_reasons: dict[str, dict[str, Any]] = {}
    for deal in lost_deals:
        reason = _deal_lost_reason(deal)
        row = lost_reasons.setdefault(reason, {"reason": reason, "count": 0, "amount": 0.0})
        row["count"] += 1
        row["amount"] += _deal_amount(deal)
    lost_reason_rows = sorted(lost_reasons.values(), key=lambda item: (-int(item["count"]), str(item["reason"])))
    for row in lost_reason_rows:
        row["amount"] = round(row["amount"], 2)

    cycle_days = []
    for deal in won_deals:
        created = _report_datetime(deal.created_at)
        closed_at = _deal_closed_datetime(deal)
        if created and closed_at:
            cycle_days.append(max(0.0, (closed_at - created).total_seconds() / 86400))

    return {
        "summary": {
            "totalDeals": len(deals),
            "closedDeals": len(closed),
            "wonDeals": len(won_deals),
            "lostDeals": len(lost_deals),
            "winRate": _rate(len(won_deals), len(lost_deals)),
            "wonRevenue": won_revenue,
            "lostAmount": lost_amount,
            "averageWonDealSize": _average([_deal_amount(deal) for deal in won_deals]),
            "averageLostDealSize": _average([_deal_amount(deal) for deal in lost_deals]),
            "averageSalesCycleDays": _average(cycle_days),
        },
        "winRateByMonth": monthly_rows,
        "winRateByOwner": by_owner,
        "winRateByPipeline": by_pipeline,
        "winLossBySource": by_source,
        "averageDealSize": {
            "won": _average([_deal_amount(deal) for deal in won_deals]),
            "lost": _average([_deal_amount(deal) for deal in lost_deals]),
        },
        "lostReasonBreakdown": lost_reason_rows,
        "topCompetitors": _competitor_breakdown(db, organization_id, [deal.id for deal in lost_deals]),
        "revenueWonTrend": [{"month": row["month"], "label": row["label"], "revenue": row["wonRevenue"], "won": row["won"]} for row in monthly_rows],
        "deals": [
            {
                "id": deal.id,
                "name": deal.name,
                "status": deal.status,
                "amount": _deal_amount(deal),
                "source": _deal_source(deal),
                "owner": owner_names.get(deal.owner_user_id, ""),
                "pipeline": pipeline_names.get(deal.pipeline_id, ""),
                "closedAt": _json_ready(_deal_closed_datetime(deal)),
                "lostReason": _deal_lost_reason(deal) if _deal_status(deal) == "lost" else None,
            }
            for deal in closed
        ],
    }


@router.get("/reports/win-loss")
def win_loss_report(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    pipelineId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    start, end = _parse_report_range(startDate, endDate)
    deals = _filtered_report_deals(db, organization_id, start, end, ownerId, pipelineId, current_user)
    payload = _win_loss_payload(db, organization_id, deals, start, end)
    payload["filters"] = {"startDate": start.date().isoformat(), "endDate": end.date().isoformat(), "ownerId": ownerId, "pipelineId": pipelineId}
    return payload


@router.get("/reports/sales-funnel")
def sales_funnel_report(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    pipelineId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    start, end = _parse_report_range(startDate, endDate)
    deals = _filtered_report_deals(db, organization_id, start, end, ownerId, pipelineId, current_user)
    stage_ids = {deal.stage_id for deal in deals if deal.stage_id}
    stages = (
        _base_query(db, _get_resource("pipeline-stages"), organization_id)
        .filter(CRMPipelineStage.id.in_([int(stage_id) for stage_id in stage_ids]))
        .order_by(asc(CRMPipelineStage.position), asc(CRMPipelineStage.id))
        .all()
        if stage_ids
        else []
    )
    stage_order = {stage.id: index for index, stage in enumerate(stages)}
    buckets: dict[int, dict[str, Any]] = {
        stage.id: {"stageId": stage.id, "stage": stage.name, "pipelineId": stage.pipeline_id, "count": 0, "amount": 0.0, "won": 0, "lost": 0}
        for stage in stages
    }
    for deal in deals:
        stage_id = int(deal.stage_id or 0)
        bucket = buckets.setdefault(stage_id, {"stageId": stage_id, "stage": f"Stage {stage_id}" if stage_id else "Unassigned", "pipelineId": deal.pipeline_id, "count": 0, "amount": 0.0, "won": 0, "lost": 0})
        bucket["count"] += 1
        bucket["amount"] += _deal_amount(deal)
        if _deal_status(deal) == "won":
            bucket["won"] += 1
        elif _deal_status(deal) == "lost":
            bucket["lost"] += 1
    rows = sorted(buckets.values(), key=lambda item: stage_order.get(int(item["stageId"] or 0), 9999))
    first_count = rows[0]["count"] if rows else 0
    previous_count: int | None = None
    for row in rows:
        row["amount"] = round(row["amount"], 2)
        row["conversionRate"] = round((row["count"] / first_count) * 100, 2) if first_count else 0.0
        row["stageToStageRate"] = round((row["count"] / previous_count) * 100, 2) if previous_count else 100.0 if row["count"] else 0.0
        previous_count = row["count"]
    return {"items": rows, "total": len(rows), "filters": {"startDate": start.date().isoformat(), "endDate": end.date().isoformat(), "ownerId": ownerId, "pipelineId": pipelineId}}


@router.get("/reports/revenue-trend")
def revenue_trend_report(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    pipelineId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    start, end = _parse_report_range(startDate, endDate)
    deals = _filtered_report_deals(db, organization_id, start, end, ownerId, pipelineId, current_user)
    payload = _win_loss_payload(db, organization_id, deals, start, end)
    return {"items": payload["revenueWonTrend"], "total": len(payload["revenueWonTrend"]), "filters": {"startDate": start.date().isoformat(), "endDate": end.date().isoformat(), "ownerId": ownerId, "pipelineId": pipelineId}}


@router.get("/reports/lead-source")
def lead_source_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    leads = _apply_record_visibility(_base_query(db, _get_resource("leads"), organization_id), _get_resource("leads"), current_user, db).all()
    rows: dict[str, dict[str, Any]] = {}
    for lead in leads:
        source = str(lead.source or "Unknown")
        row = rows.setdefault(source, {"source": source, "leads": 0, "converted": 0, "estimatedValue": 0.0})
        row["leads"] += 1
        row["converted"] += 1 if lead.is_converted else 0
        row["estimatedValue"] += float(lead.estimated_value or 0)
    for row in rows.values():
        row["conversionRate"] = round((row["converted"] / row["leads"]) * 100, 2) if row["leads"] else 0.0
        row["estimatedValue"] = round(row["estimatedValue"], 2)
    items = sorted(rows.values(), key=lambda row: (-row["leads"], row["source"]))
    return {"items": items, "total": len(items)}


@router.get("/reports/lead-conversion")
def lead_conversion_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    leads = _apply_record_visibility(_base_query(db, _get_resource("leads"), organization_id), _get_resource("leads"), current_user, db).all()
    converted = [lead for lead in leads if lead.is_converted]
    by_status: dict[str, int] = {}
    for lead in leads:
        by_status[str(lead.status or "Unknown")] = by_status.get(str(lead.status or "Unknown"), 0) + 1
    return {
        "summary": {
            "totalLeads": len(leads),
            "convertedLeads": len(converted),
            "conversionRate": round((len(converted) / len(leads)) * 100, 2) if leads else 0.0,
        },
        "byStatus": [{"status": key, "count": value} for key, value in sorted(by_status.items())],
        "items": [_serialize(lead) for lead in converted[:100]],
    }


@router.get("/reports/sales-pipeline")
def sales_pipeline_report(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    pipelineId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    return sales_funnel_report(startDate, endDate, ownerId, pipelineId, db, current_user)


@router.get("/reports/deal-stage")
def deal_stage_report(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    pipelineId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    return sales_funnel_report(startDate, endDate, ownerId, pipelineId, db, current_user)


@router.get("/reports/salesperson-performance")
def salesperson_performance_report(
    startDate: str | None = None,
    endDate: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    start, end = _parse_report_range(startDate, endDate)
    deals = _filtered_report_deals(db, organization_id, start, end, current_user=current_user)
    owner_names = _owner_names(db, {deal.owner_user_id for deal in deals})
    buckets: dict[int | None, dict[str, Any]] = {}
    for deal in deals:
        row = buckets.setdefault(deal.owner_user_id, {"ownerId": deal.owner_user_id, "owner": owner_names.get(deal.owner_user_id, "Unassigned"), "openDeals": 0, "wonDeals": 0, "lostDeals": 0, "pipelineAmount": 0.0, "wonRevenue": 0.0})
        amount = _deal_amount(deal)
        if _deal_status(deal) == "won":
            row["wonDeals"] += 1
            row["wonRevenue"] += amount
        elif _deal_status(deal) == "lost":
            row["lostDeals"] += 1
        else:
            row["openDeals"] += 1
            row["pipelineAmount"] += amount
    for row in buckets.values():
        row["winRate"] = _rate(int(row["wonDeals"]), int(row["lostDeals"]))
        row["pipelineAmount"] = round(row["pipelineAmount"], 2)
        row["wonRevenue"] = round(row["wonRevenue"], 2)
    items = sorted(buckets.values(), key=lambda row: (-row["wonRevenue"], row["owner"]))
    return {"items": items, "total": len(items), "filters": {"startDate": start.date().isoformat(), "endDate": end.date().isoformat()}}


@router.get("/reports/follow-up-overdue")
def follow_up_overdue_report(
    ownerId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    return overdue_activities_dashboard(ownerId, db, current_user)


@router.get("/reports/monthly-revenue-forecast")
def monthly_revenue_forecast_report(
    startDate: str | None = None,
    endDate: str | None = None,
    ownerId: int | None = None,
    pipelineId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    start, end = _parse_report_range(startDate, endDate)
    deals = _filtered_report_deals(db, organization_id, start, end, ownerId, pipelineId, current_user)
    months = {key: {"month": key, "label": _month_label(key), "dealCount": 0, "amount": 0.0, "expectedRevenue": 0.0} for key in _month_keys_between(start, end)}
    for deal in deals:
        close_at = _as_datetime(deal.expected_close_date) or _deal_report_datetime(deal)
        key = _month_key(close_at)
        row = months.setdefault(key, {"month": key, "label": _month_label(key), "dealCount": 0, "amount": 0.0, "expectedRevenue": 0.0})
        amount = _deal_amount(deal)
        row["dealCount"] += 1
        row["amount"] += amount
        row["expectedRevenue"] += float(deal.expected_revenue or Decimal(str(amount)) * Decimal(int(deal.probability or 0)) / Decimal("100"))
    for row in months.values():
        row["amount"] = round(row["amount"], 2)
        row["expectedRevenue"] = round(row["expectedRevenue"], 2)
    items = sorted(months.values(), key=lambda row: row["month"])
    return {"items": items, "total": len(items), "filters": {"startDate": start.date().isoformat(), "endDate": end.date().isoformat(), "ownerId": ownerId, "pipelineId": pipelineId}}


@router.get("/reports/territories")
def territory_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "reports_view")),
):
    organization_id = _organization_id(db, current_user)
    territories = _base_query(db, _get_resource("territories"), organization_id).order_by(asc(CRMTerritory.priority), asc(CRMTerritory.name)).all()
    rows: list[dict[str, Any]] = []
    for territory in territories:
        deals = _base_query(db, _get_resource("deals"), organization_id).filter(CRMDeal.territory_id == territory.id).all()
        won = [deal for deal in deals if _deal_status(deal) == "won"]
        rows.append(
            {
                "territoryId": territory.id,
                "territory": territory.name,
                "priority": territory.priority,
                "isActive": bool(territory.is_active),
                "users": len(_territory_users(db, territory.id, organization_id)),
                "leads": _base_query(db, _get_resource("leads"), organization_id).filter(CRMLead.territory_id == territory.id).count(),
                "accounts": _base_query(db, _get_resource("companies"), organization_id).filter(CRMCompany.territory_id == territory.id).count(),
                "deals": len(deals),
                "openDeals": len([deal for deal in deals if _deal_status(deal) == "open"]),
                "wonDeals": len(won),
                "wonRevenue": round(sum(_deal_amount(deal) for deal in won), 2),
            }
        )
    return {"items": rows, "total": len(rows)}


@router.get("/territories")
def list_territories(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    rows = _base_query(db, _get_resource("territories"), organization_id).order_by(asc(CRMTerritory.priority), asc(CRMTerritory.name)).all()
    return {"items": [_serialize_territory(row, db, organization_id) for row in rows], "total": len(rows)}


@router.post("/territories", status_code=status.HTTP_201_CREATED)
def create_territory(
    payload: CRMRecordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    data = _validate_and_build(_get_resource("territories"), payload.model_dump(), partial=False)
    data["organization_id"] = organization_id
    data["created_by_user_id"] = current_user.id
    data["updated_by_user_id"] = current_user.id
    territory = CRMTerritory(**data)
    db.add(territory)
    db.commit()
    db.refresh(territory)
    return _serialize_territory(territory, db, organization_id)


@router.patch("/territories/{territory_id}")
def update_territory(
    territory_id: int,
    payload: CRMRecordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    territory = _get_record(db, _get_resource("territories"), territory_id, organization_id)
    data = _validate_and_build(_get_resource("territories"), payload.model_dump(exclude_unset=True), partial=True)
    if "organization_id" in data and data["organization_id"] != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot move territories across organizations")
    for key, value in data.items():
        if key not in {"id", "organization_id", "created_at", "created_by_user_id"}:
            setattr(territory, key, value)
    territory.updated_by_user_id = current_user.id
    territory.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(territory)
    return _serialize_territory(territory, db, organization_id)


@router.delete("/territories/{territory_id}")
def delete_territory(
    territory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    territory = _get_record(db, _get_resource("territories"), territory_id, organization_id, include_deleted=True)
    territory.deleted_at = datetime.now(timezone.utc)
    territory.is_active = False
    territory.status = "Inactive"
    territory.updated_by_user_id = current_user.id
    db.commit()
    return {"message": "CRM territory deleted"}


@router.post("/territories/{territory_id}/users", status_code=status.HTTP_201_CREATED)
def add_territory_user(
    territory_id: int,
    payload: CRMTerritoryUserPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    territory = _get_record(db, _get_resource("territories"), territory_id, organization_id)
    if not _user_is_in_organization(db, payload.userId, organization_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Territory users must belong to the same organization")
    existing = (
        db.query(CRMTerritoryUser)
        .filter(CRMTerritoryUser.organization_id == organization_id, CRMTerritoryUser.territory_id == territory.id, CRMTerritoryUser.user_id == payload.userId)
        .first()
    )
    if existing:
        return {"item": {"id": existing.id, "territoryId": existing.territory_id, "userId": existing.user_id}, "territory": _serialize_territory(territory, db, organization_id)}
    row = CRMTerritoryUser(organization_id=organization_id, territory_id=territory.id, user_id=payload.userId, created_by_user_id=current_user.id)
    db.add(row)
    if not territory.owner_user_id:
        territory.owner_user_id = payload.userId
    db.commit()
    db.refresh(row)
    db.refresh(territory)
    return {"item": {"id": row.id, "territoryId": row.territory_id, "userId": row.user_id}, "territory": _serialize_territory(territory, db, organization_id)}


@router.post("/territories/auto-assign")
def auto_assign_territories(
    payload: CRMTerritoryAutoAssignPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity = _normalize_custom_field_entity(payload.entityType) if payload.entityType else None
    if entity and entity not in {"leads", "companies", "deals"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Territory auto-assignment supports leads, accounts, and deals")
    resources = [entity] if entity else ["leads", "companies", "deals"]
    updated = 0
    items: list[dict[str, Any]] = []
    for resource_name in resources:
        resource = _get_resource(resource_name)
        query = _base_query(db, resource, organization_id)
        if payload.entityId:
            query = query.filter(resource.model.id == payload.entityId)
        for record in query.all():
            if _apply_territory_assignment(db, organization_id, record, override_manual=payload.overrideManual):
                updated += 1
                items.append({"entityType": resource_name, "entityId": record.id, "territoryId": getattr(record, "territory_id", None), "ownerId": getattr(record, "owner_user_id", None)})
    db.commit()
    return {"updated": updated, "items": items}


@router.post("/enrichment/preview")
def enrichment_preview(
    payload: CRMEnrichmentPreviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type, resource_name = _enrichment_entity(payload.entityType)
    provider = _normalize_enrichment_provider(payload.provider)
    record = _get_record(db, _get_resource(resource_name), payload.entityId, organization_id)
    values = _normalize_enrichment_values(_payload_enrichment_data(payload))
    preview = _enrichment_preview_payload(record, entity_type, provider, values)
    log = CRMEnrichmentLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=record.id,
        provider=provider,
        old_values_json={field["key"]: field["oldValue"] for field in preview["fields"]},
        new_values_json=values,
        applied_fields_json=[],
        status="previewed",
        created_by_user_id=current_user.id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    preview["logId"] = log.id
    return preview


@router.post("/enrichment/apply")
def enrichment_apply(
    payload: CRMEnrichmentApplyPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type, resource_name = _enrichment_entity(payload.entityType)
    provider = _normalize_enrichment_provider(payload.provider)
    record = _get_record(db, _get_resource(resource_name), payload.entityId, organization_id)
    values = _normalize_enrichment_values(_payload_enrichment_data(payload))
    selected = payload.appliedFields or payload.selectedFields or list(values)
    preview = _enrichment_preview_payload(record, entity_type, provider, values)
    allowed = {field["key"]: field for field in preview["fields"] if field["supported"]}
    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    applied: list[str] = []
    for field_key in selected:
        field = allowed.get(field_key)
        if not field:
            continue
        target = str(field["targetField"])
        column = _columns(record.__class__)[target]
        old_values[field_key] = _json_ready(getattr(record, target, None))
        setattr(record, target, _coerce_value(column, values[field_key]))
        new_values[field_key] = values[field_key]
        applied.append(field_key)
    if hasattr(record, "updated_by_user_id"):
        record.updated_by_user_id = current_user.id
    if hasattr(record, "updated_at"):
        record.updated_at = datetime.now(timezone.utc)
    log = CRMEnrichmentLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=record.id,
        provider=provider,
        old_values_json=old_values,
        new_values_json=new_values,
        applied_fields_json=applied,
        status="applied" if applied else "skipped",
        created_by_user_id=current_user.id,
    )
    db.add(log)
    if applied:
        _create_timeline_activity(
            db,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=record.id,
            activity_type="enrichment",
            title="Contact enrichment applied",
            body=f"{provider.replace('_', ' ').title()} enrichment updated {len(applied)} field(s).",
            user_id=current_user.id,
            metadata={"provider": provider, "appliedFields": applied, "newValues": new_values},
        )
    db.commit()
    db.refresh(record)
    db.refresh(log)
    return {"record": _detail_payload(db, resource_name, record, organization_id), "log": _enrichment_log_payload(log), "appliedFields": applied}


@router.get("/enrichment/history")
def enrichment_history(
    entityType: str,
    entityId: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    entity_type, resource_name = _enrichment_entity(entityType)
    _get_record(db, _get_resource(resource_name), entityId, organization_id)
    rows = (
        db.query(CRMEnrichmentLog)
        .filter(CRMEnrichmentLog.organization_id == organization_id, CRMEnrichmentLog.entity_type == entity_type, CRMEnrichmentLog.entity_id == entityId)
        .order_by(desc(CRMEnrichmentLog.created_at), desc(CRMEnrichmentLog.id))
        .limit(50)
        .all()
    )
    return {"items": [_enrichment_log_payload(row) for row in rows], "total": len(rows)}


@router.get("/module-info")
def module_info() -> dict[str, Any]:
    return {
        "key": "crm",
        "name": "VyaparaCRM",
        "status": "installed",
        "modules": sorted(key for key in RESOURCES if key not in {"accounts", "opportunities", "products-services", "call-logs", "email-logs", "users"}),
    }


@router.get("/roles")
def crm_roles(
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
) -> dict[str, Any]:
    return {
        "items": [
            {"key": "crm_admin", "name": "CRM Admin", "permissions": ["crm_admin", "crm_manage", "crm_view", "reports_view"], "visibility": "all_records"},
            {"key": "sales_manager", "name": "Sales Manager", "permissions": ["crm_manage", "crm_view", "reports_view"], "visibility": "team_branch_department_records"},
            {"key": "sales_executive", "name": "Sales Executive", "permissions": ["crm_manage", "crm_view"], "visibility": "owned_branch_department_team_records"},
            {"key": "crm_viewer", "name": "Viewer", "permissions": ["crm_view", "reports_view"], "visibility": "read_only_all_records"},
        ],
        "currentRole": _crm_role_key(current_user),
    }


@router.get("/audit-logs")
def crm_audit_logs(
    entityType: str | None = None,
    entityId: int | None = None,
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
) -> dict[str, Any]:
    query = db.query(AuditLog).filter(AuditLog.entity_type.ilike("crm_%"))
    if entityType:
        query = query.filter(AuditLog.entity_type == f"crm_{_canonical_entity(entityType)}")
    if entityId:
        query = query.filter(AuditLog.entity_id == entityId)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    rows = query.order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "entityType": row.entity_type,
                "entityId": row.entity_id,
                "action": row.action,
                "description": row.description,
                "oldValues": json.loads(row.old_values or "{}"),
                "newValues": json.loads(row.new_values or "{}"),
                "createdAt": row.created_at.isoformat() if row.created_at else None,
                "userId": row.user_id,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/deals/kanban")
def deals_kanban(
    pipelineId: int | None = None,
    ownerId: int | None = None,
    branchId: int | None = None,
    departmentId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
) -> dict[str, Any]:
    organization_id = _organization_id(db, current_user)
    stage_query = _base_query(db, _get_resource("pipeline-stages"), organization_id)
    if pipelineId:
        stage_query = stage_query.filter(CRMPipelineStage.pipeline_id == pipelineId)
    stages = stage_query.order_by(asc(CRMPipelineStage.position), asc(CRMPipelineStage.id)).all()

    deal_query = _apply_record_visibility(_base_query(db, _get_resource("deals"), organization_id), _get_resource("deals"), current_user, db)
    if pipelineId:
        deal_query = deal_query.filter(CRMDeal.pipeline_id == pipelineId)
    if ownerId:
        deal_query = deal_query.filter(CRMDeal.owner_user_id == ownerId)
    if branchId:
        deal_query = deal_query.filter(CRMDeal.branch_id == branchId)
    if departmentId:
        deal_query = deal_query.filter(CRMDeal.department_id == departmentId)
    deals = deal_query.order_by(asc(CRMDeal.position), desc(CRMDeal.updated_at), desc(CRMDeal.created_at)).all()
    owner_names = _owner_names(db, {deal.owner_user_id for deal in deals})
    by_stage: dict[int, list[CRMDeal]] = {}
    for deal in deals:
        by_stage.setdefault(int(deal.stage_id or 0), []).append(deal)
    columns = []
    for stage in stages:
        rows = by_stage.get(stage.id, [])
        amount = sum(_deal_amount(deal) for deal in rows)
        expected = sum(float(deal.expected_revenue or Decimal(str(_deal_amount(deal))) * Decimal(int(deal.probability or stage.probability or 0)) / Decimal("100")) for deal in rows)
        columns.append(
            {
                "stageId": stage.id,
                "stage": stage.name,
                "pipelineId": stage.pipeline_id,
                "probability": stage.probability,
                "count": len(rows),
                "amount": round(amount, 2),
                "expectedRevenue": round(expected, 2),
                "deals": [
                    {
                        **_serialize(deal),
                        "ownerName": owner_names.get(deal.owner_user_id, "Unassigned"),
                        "expectedRevenue": float(deal.expected_revenue or Decimal(str(_deal_amount(deal))) * Decimal(int(deal.probability or stage.probability or 0)) / Decimal("100")),
                    }
                    for deal in rows
                ],
            }
        )
    return {"items": columns, "totalDeals": len(deals), "filters": {"pipelineId": pipelineId, "ownerId": ownerId, "branchId": branchId, "departmentId": departmentId}}


@router.get("/dashboards/overdue-activities")
def overdue_activities_dashboard(
    ownerId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
) -> dict[str, Any]:
    organization_id = _organization_id(db, current_user)
    now = datetime.now(timezone.utc)
    task_query = _apply_record_visibility(_base_query(db, _get_resource("tasks"), organization_id), _get_resource("tasks"), current_user, db).filter(
        CRMTask.due_date.is_not(None),
        CRMTask.due_date < now,
        CRMTask.status.notin_(["Done", "Completed", "Complete", "Cancelled"]),
    )
    activity_query = _apply_record_visibility(_base_query(db, _get_resource("activities"), organization_id), _get_resource("activities"), current_user, db).filter(
        CRMActivity.due_date.is_not(None),
        CRMActivity.due_date < now,
        CRMActivity.status.notin_(["Done", "Completed", "Complete", "Cancelled"]),
    )
    if ownerId:
        task_query = task_query.filter(CRMTask.owner_user_id == ownerId)
        activity_query = activity_query.filter(CRMActivity.owner_user_id == ownerId)
    tasks = task_query.order_by(asc(CRMTask.due_date)).limit(100).all()
    activities = activity_query.order_by(asc(CRMActivity.due_date)).limit(100).all()
    items = [{"type": "task", **_serialize(row)} for row in tasks] + [{"type": "activity", **_serialize(row)} for row in activities]
    items.sort(key=lambda item: str(item.get("dueDate") or ""))
    return {
        "items": items,
        "total": len(items),
        "summary": {
            "tasks": len(tasks),
            "activities": len(activities),
            "highPriority": sum(1 for item in items if str(item.get("priority") or "").lower() == "high"),
        },
    }


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    lead_id: int,
    payload: CRMLeadConvertPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    lead = _get_record(db, _get_resource("leads"), lead_id, organization_id)
    _assert_record_visible(db, _get_resource("leads"), lead_id, organization_id, current_user)
    if lead.is_converted:
        raise HTTPException(status_code=400, detail="Lead is already converted")

    company = None
    if payload.createCompany and lead.company_name:
        company = db.query(CRMCompany).filter(
            CRMCompany.organization_id == organization_id,
            CRMCompany.deleted_at.is_(None),
            CRMCompany.name == lead.company_name,
        ).first()
        if not company:
            company = CRMCompany(
                organization_id=organization_id,
                owner_user_id=lead.owner_user_id or current_user.id,
                branch_id=lead.branch_id,
                department_id=lead.department_id,
                assigned_team_id=lead.assigned_team_id,
                name=lead.company_name,
                industry=lead.industry,
                website=lead.company_website or lead.website,
                phone=lead.phone,
                email=lead.email,
                city=lead.city,
                state=lead.state,
                country=lead.country,
                employee_count=lead.employee_count,
                account_type="Prospect",
                status="Active",
                created_by_user_id=current_user.id,
                updated_by_user_id=current_user.id,
            )
            db.add(company)
            db.flush()

    contact = None
    if payload.createContact:
        contact = CRMContact(
            organization_id=organization_id,
            owner_user_id=lead.owner_user_id or current_user.id,
            branch_id=lead.branch_id,
            department_id=lead.department_id,
            assigned_team_id=lead.assigned_team_id,
            company_id=company.id if company else None,
            first_name=lead.first_name,
            last_name=lead.last_name,
            full_name=lead.full_name,
            email=lead.email,
            phone=lead.phone,
            alternate_phone=lead.alternate_phone,
            job_title=lead.job_title,
            lifecycle_stage="Lead",
            source=lead.source,
            company_name=lead.company_name,
            company_website=lead.company_website,
            industry=lead.industry,
            employee_count=lead.employee_count,
            website=lead.website,
            linkedin_url=lead.linkedin_url,
            email_verification_status=lead.email_verification_status,
            social_profiles_json=lead.social_profiles_json,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            address=lead.address,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
        )
        db.add(contact)
        db.flush()

    deal = None
    if payload.createDeal:
        pipeline_id = payload.pipelineId
        stage_id = payload.stageId
        if not pipeline_id or not stage_id:
            default_pipeline = _base_query(db, _get_resource("pipelines"), organization_id).order_by(desc(CRMPipeline.is_default), CRMPipeline.id).first()
            if not default_pipeline:
                raise HTTPException(status_code=400, detail="Create a CRM pipeline before converting leads to deals")
            pipeline_id = pipeline_id or default_pipeline.id
            default_stage = (
                db.query(CRMPipelineStage)
                .filter(CRMPipelineStage.pipeline_id == pipeline_id, CRMPipelineStage.deleted_at.is_(None))
                .order_by(CRMPipelineStage.position.asc(), CRMPipelineStage.id.asc())
                .first()
            )
            if not default_stage:
                raise HTTPException(status_code=400, detail="Create a pipeline stage before converting leads to deals")
            stage_id = stage_id or default_stage.id
        _validate_deal_pipeline_stage(db, pipeline_id, stage_id, organization_id)
        amount = payload.dealAmount if payload.dealAmount is not None else lead.estimated_value
        stage = db.query(CRMPipelineStage).filter(CRMPipelineStage.id == stage_id).first()
        probability = int(stage.probability or 0) if stage else 0
        deal = CRMDeal(
            organization_id=organization_id,
            owner_user_id=lead.owner_user_id or current_user.id,
            branch_id=lead.branch_id,
            department_id=lead.department_id,
            assigned_team_id=lead.assigned_team_id,
            company_id=company.id if company else None,
            contact_id=contact.id if contact else None,
            pipeline_id=pipeline_id,
            stage_id=stage_id,
            name=payload.dealName or f"{lead.company_name or lead.full_name} opportunity",
            amount=amount or Decimal("0"),
            probability=probability,
            expected_revenue=(amount or Decimal("0")) * Decimal(probability) / Decimal("100"),
            expected_close_date=lead.expected_close_date,
            status="Open",
            lead_source=lead.source,
            source=lead.source,
            next_follow_up_at=lead.next_follow_up_at,
            tags_text=lead.tags_text,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
        )
        db.add(deal)
        db.flush()

    lead.is_converted = True
    lead.converted_at = datetime.now(timezone.utc)
    lead.converted_contact_id = contact.id if contact else None
    lead.converted_company_id = company.id if company else None
    lead.converted_deal_id = deal.id if deal else None
    lead.status = "Converted"
    lead.updated_by_user_id = current_user.id
    _create_timeline_activity(
        db,
        organization_id=organization_id,
        entity_type="lead",
        entity_id=lead.id,
        activity_type="conversion",
        title="Lead converted",
        body="Lead converted into CRM customer records.",
        user_id=current_user.id,
        metadata={
            "contactId": contact.id if contact else None,
            "companyId": company.id if company else None,
            "dealId": deal.id if deal else None,
        },
    )
    _create_crm_audit_log(
        db,
        user_id=current_user.id,
        entity_type="leads",
        entity_id=lead.id,
        action="CONVERT",
        old_values={"status": "Open"},
        new_values={
            "status": "Converted",
            "converted_contact_id": contact.id if contact else None,
            "converted_company_id": company.id if company else None,
            "converted_deal_id": deal.id if deal else None,
        },
        description="Lead converted into account, contact and deal",
    )
    db.commit()
    db.refresh(lead)
    return {
        "lead": _serialize(lead),
        "contact": _serialize(contact) if contact else None,
        "company": _serialize(company) if company else None,
        "deal": _serialize(deal) if deal else None,
    }


@router.post("/{entity}/import")
def import_records(
    entity: str,
    payload: CRMImportRowsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    organization_id = _organization_id(db, current_user)
    created = []
    errors = []
    for index, row in enumerate(payload.rows, start=1):
        try:
            data = _validate_and_build(resource, dict(row), partial=False)
            columns = _columns(resource.model)
            if "organization_id" in columns:
                data["organization_id"] = organization_id
            if resource.owner_field and resource.owner_field in columns and not data.get(resource.owner_field):
                data[resource.owner_field] = current_user.id
            _assert_write_scope(resource, data, current_user, db)
            if "created_by_user_id" in columns:
                data["created_by_user_id"] = current_user.id
            if "updated_by_user_id" in columns:
                data["updated_by_user_id"] = current_user.id
            _validate_related_records(db, data, organization_id)
            if resource.model is CRMDeal:
                _validate_deal_pipeline_stage(db, data.get("pipeline_id"), data.get("stage_id"), organization_id)
            record = resource.model(**data)
            db.add(record)
            db.flush()
            created.append(_serialize(record))
        except Exception as exc:
            errors.append({"row": index, "error": str(getattr(exc, "detail", exc))})
    if errors:
        db.rollback()
        return {"created": 0, "errors": errors}
    db.commit()
    return {"created": len(created), "items": created, "errors": []}


@router.get("/deals/{deal_id}/contacts")
def list_deal_contacts(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    deal = _get_record(db, _get_resource("deals"), deal_id, organization_id)
    return {"items": _deal_contacts_for(db, deal, organization_id)}


@router.post("/deals/{deal_id}/contacts", status_code=status.HTTP_201_CREATED)
def add_deal_contact(
    deal_id: int,
    payload: CRMDealContactPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    deal = _get_record(db, _get_resource("deals"), deal_id, organization_id)
    link = _upsert_deal_contact(db, deal, organization_id, _deal_contact_data(payload), current_user.id)
    deal.updated_by_user_id = current_user.id
    deal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return _serialize_deal_contact(link)


@router.put("/deals/{deal_id}/contacts")
def replace_deal_contacts(
    deal_id: int,
    payload: CRMDealContactsReplacePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    deal = _get_record(db, _get_resource("deals"), deal_id, organization_id)
    db.query(CRMDealContact).filter(CRMDealContact.organization_id == organization_id, CRMDealContact.deal_id == deal.id).delete(synchronize_session=False)
    db.flush()
    _create_deal_contact_links_from_payload(db, deal, [item.model_dump(exclude_unset=True) for item in payload.contacts], organization_id, current_user.id)
    _sync_deal_primary_contact(db, deal)
    deal.updated_by_user_id = current_user.id
    deal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"items": _deal_contacts_for(db, deal, organization_id)}


@router.patch("/deals/{deal_id}/contacts/{deal_contact_id}")
def update_deal_contact(
    deal_id: int,
    deal_contact_id: int,
    payload: CRMDealContactPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    deal = _get_record(db, _get_resource("deals"), deal_id, organization_id)
    link = db.query(CRMDealContact).filter(
        CRMDealContact.organization_id == organization_id,
        CRMDealContact.deal_id == deal.id,
        CRMDealContact.id == deal_contact_id,
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal contact not found")
    raw = payload.model_dump(exclude_unset=True)
    if "contactId" in raw or "contact_id" in raw:
        contact_id = raw.get("contactId") or raw.get("contact_id")
        _get_record(db, _get_resource("contacts"), int(contact_id), organization_id)
        duplicate = db.query(CRMDealContact).filter(
            CRMDealContact.organization_id == organization_id,
            CRMDealContact.deal_id == deal.id,
            CRMDealContact.contact_id == int(contact_id),
            CRMDealContact.id != link.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contact is already linked to this deal")
        link.contact_id = int(contact_id)
    if "role" in raw:
        link.role = raw["role"]
    if "influenceLevel" in raw or "influence_level" in raw:
        link.influence_level = raw.get("influenceLevel") or raw.get("influence_level")
    if "notes" in raw:
        link.notes = raw["notes"]
    if "isPrimary" in raw or "is_primary" in raw:
        link.is_primary = bool(raw.get("isPrimary") if "isPrimary" in raw else raw.get("is_primary"))
    link.updated_by_user_id = current_user.id
    if link.is_primary:
        _sync_deal_primary_contact(db, deal, link)
    else:
        _sync_deal_primary_contact(db, deal)
    deal.updated_by_user_id = current_user.id
    deal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return _serialize_deal_contact(link)


@router.delete("/deals/{deal_id}/contacts/{deal_contact_id}")
def delete_deal_contact(
    deal_id: int,
    deal_contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    organization_id = _organization_id(db, current_user)
    deal = _get_record(db, _get_resource("deals"), deal_id, organization_id)
    link = db.query(CRMDealContact).filter(
        CRMDealContact.organization_id == organization_id,
        CRMDealContact.deal_id == deal.id,
        CRMDealContact.id == deal_contact_id,
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal contact not found")
    was_primary = bool(link.is_primary)
    db.delete(link)
    db.flush()
    if was_primary:
        replacement = db.query(CRMDealContact).filter(
            CRMDealContact.organization_id == organization_id,
            CRMDealContact.deal_id == deal.id,
        ).order_by(CRMDealContact.id).first()
        if replacement:
            replacement.is_primary = True
            _sync_deal_primary_contact(db, deal, replacement)
        else:
            deal.contact_id = None
    deal.updated_by_user_id = current_user.id
    deal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Deal contact removed"}


@router.get("/{entity}/export")
def export_records(
    entity: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    organization_id = _organization_id(db, current_user)
    rows = _base_query(db, resource, organization_id).limit(5000).all()
    columns = [column.key for column in resource.model.__table__.columns if column.key not in {"deleted_at"}]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        serialized = _serialize(row)
        writer.writerow({column: serialized.get(column) for column in columns})
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entity}.csv"'},
    )


@router.get("/{entity}")
def list_records(
    entity: str,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = None,
    q: str | None = None,
    sort_by: str | None = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    include_deleted: bool = False,
    owner_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    organization_id = _organization_id(db, current_user)
    query = _base_query(db, resource, organization_id, include_deleted)
    query = _apply_record_visibility(query, resource, current_user, db)
    query = _apply_filters(query, resource, request, owner_id)
    query = _apply_custom_field_filters(db, query, resource, request, organization_id)
    query = _apply_search(query, resource, search or q)
    total = query.count()

    columns = _columns(resource.model)
    sort_key = sort_by or resource.default_sort
    if sort_key not in columns:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Cannot sort by {sort_key}")
    sort_column = getattr(resource.model, sort_key)
    query = query.order_by(asc(sort_column) if sort_order == "asc" else desc(sort_column))
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    canonical = CANONICAL_ENTITY_BY_MODEL.get(resource.model)
    items = _custom_field_columns_for_rows(db, canonical, rows, organization_id) if canonical in CUSTOM_FIELD_SUPPORTED_ENTITIES else [_serialize(row) for row in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }


@router.get("/{entity}/{record_id}")
def get_record(
    entity: str,
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    organization_id = _organization_id(db, current_user)
    record = _get_record(db, resource, record_id, organization_id)
    _assert_record_visible(db, resource, record_id, organization_id, current_user)
    canonical = _canonical_entity(entity)
    if canonical in {"leads", "contacts", "companies", "deals", "quotations", "tasks"}:
        return _detail_payload(db, entity, record, organization_id)
    return _serialize(record)


@router.get("/{entity}/{record_id}/related")
def get_related_records(
    entity: str,
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    organization_id = _organization_id(db, current_user)
    record = _get_record(db, resource, record_id, organization_id)
    _assert_record_visible(db, resource, record_id, organization_id, current_user)
    canonical = _canonical_entity(entity)
    if canonical not in {"leads", "contacts", "companies", "deals", "quotations"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CRM related records are not configured for this entity")
    return {
        "entity": canonical,
        "id": record.id,
        "related": _related_for(db, canonical, record, organization_id),
        "timeline": _timeline_for(db, canonical, record, organization_id),
        "customFields": _custom_fields_for(db, canonical, record.id, organization_id),
    }


@router.post("/{entity}", status_code=status.HTTP_201_CREATED)
def create_record(
    entity: str,
    payload: CRMRecordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    raw_payload = payload.model_dump()
    deal_contacts_payload = None
    if resource.model is CRMDeal:
        for key in ("contacts", "dealContacts", "deal_contacts", "stakeholders"):
            if key in raw_payload:
                deal_contacts_payload = raw_payload.pop(key)
                break
    mention_user_ids = _extract_mention_user_ids(raw_payload)
    custom_values = _extract_custom_field_payload(raw_payload)
    validation_payload = dict(raw_payload)
    if resource.model is CRMMeeting:
        for transient_key in ("syncToCalendar", "sync_to_calendar", "provider"):
            validation_payload.pop(transient_key, None)
    data = _validate_and_build(resource, validation_payload, partial=False)
    owner_was_provided = any(key in raw_payload for key in {"ownerId", "owner_id", "owner_user_id"})
    organization_id = _organization_id(db, current_user)
    columns = _columns(resource.model)
    canonical = _canonical_entity(entity)
    if canonical in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        _validate_required_custom_fields(db, canonical, None, organization_id, custom_values)
    if resource.model is CRMActivity:
        _sync_activity_link_fields(data)
    if "organization_id" in columns:
        data["organization_id"] = organization_id
    if resource.model is CRMCustomField:
        existing = (
            _base_query(db, resource, organization_id, include_deleted=True)
            .filter(CRMCustomField.entity == data.get("entity"), CRMCustomField.field_key == data.get("field_key"))
            .first()
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Custom field key already exists for this entity")
    _validate_related_records(db, data, organization_id)
    if resource.model is CRMDeal:
        _validate_deal_pipeline_stage(db, data.get("pipeline_id"), data.get("stage_id"), organization_id)
    if resource.owner_field and resource.owner_field in columns and not data.get(resource.owner_field):
        data[resource.owner_field] = current_user.id
    _assert_write_scope(resource, data, current_user, db)
    if "author_user_id" in columns and not data.get("author_user_id"):
        data["author_user_id"] = current_user.id
    if "created_by_user_id" in columns:
        data["created_by_user_id"] = current_user.id
    if "updated_by_user_id" in columns:
        data["updated_by_user_id"] = current_user.id
    if resource.model is CRMLead and "lead_score" in data:
        score = max(0, min(100, int(data["lead_score"] or 0)))
        data["lead_score"] = score
        data["lead_score_label"] = _score_label(score)
        data["rating"] = data["lead_score_label"]
        data["lead_score_mode"] = "manual"

    record = resource.model(**data)
    if resource.model is CRMDeal:
        _apply_deal_close_fields(record, data)
    db.add(record)
    db.flush()
    if resource.model is CRMDeal:
        _create_deal_contact_links_from_payload(db, record, deal_contacts_payload, organization_id, current_user.id)
    if resource.model is CRMMeeting and raw_payload.get("syncToCalendar"):
        _sync_meeting_to_calendar(db, organization_id, record, current_user, raw_payload.get("externalProvider") or raw_payload.get("provider"))
    if canonical in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        _save_custom_field_values(db, canonical, record.id, organization_id, current_user.id, custom_values)
    if resource.model is CRMLead and data.get("lead_score_mode") != "manual":
        _apply_lead_score(db, record, organization_id, current_user.id)
    _apply_territory_assignment(db, organization_id, record, override_manual=False, override_owner=not owner_was_provided)
    _handle_mentions_for_record(db, resource, record, mention_user_ids, organization_id, current_user)
    create_event = _event_type_for_create(canonical, _serialize(record))
    if create_event:
        _enqueue_webhook_event(db, organization_id, create_event, _serialize(record), current_user.id)
    db.commit()
    db.refresh(record)
    _create_related_timeline_event(db, entity, _serialize(record), organization_id, current_user.id)
    if resource.model is not CRMLead:
        _recalculate_linked_lead(db, _serialize(record), organization_id, current_user.id)
        db.commit()
    if resource.model is CRMDeal:
        _maybe_create_srm_handoff_for_won_deal(db, record, current_user)
        db.commit()
    return _serialize(record)


@router.patch("/{entity}/{record_id}")
def update_record(
    entity: str,
    record_id: int,
    payload: CRMRecordPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    organization_id = _organization_id(db, current_user)
    record = _get_record(db, resource, record_id, organization_id)
    _assert_record_visible(db, resource, record_id, organization_id, current_user)
    before = {key: getattr(record, key) for key in _columns(resource.model) if key in IMPORTANT_UPDATE_FIELDS}
    raw_payload = payload.model_dump(exclude_unset=True)
    deal_contacts_payload = None
    if resource.model is CRMDeal:
        for key in ("contacts", "dealContacts", "deal_contacts", "stakeholders"):
            if key in raw_payload:
                deal_contacts_payload = raw_payload.pop(key)
                break
    custom_values = _extract_custom_field_payload(raw_payload)
    validation_payload = dict(raw_payload)
    if resource.model is CRMMeeting:
        for transient_key in ("syncToCalendar", "sync_to_calendar", "provider"):
            validation_payload.pop(transient_key, None)
    data = _validate_and_build(resource, validation_payload, partial=True)
    owner_was_provided = any(key in raw_payload for key in {"ownerId", "owner_id", "owner_user_id"})
    columns = _columns(resource.model)
    canonical = _canonical_entity(entity)
    if canonical in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        _validate_required_custom_fields(db, canonical, record.id, organization_id, custom_values)
    if resource.model is CRMActivity:
        _sync_activity_link_fields(data)
    if "organization_id" in data and data["organization_id"] != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot move CRM records across organizations")
    if resource.model is CRMCustomField and ("entity" in data or "field_key" in data):
        next_entity = data.get("entity", record.entity)
        next_key = data.get("field_key", record.field_key)
        duplicate = (
            _base_query(db, resource, organization_id, include_deleted=True)
            .filter(CRMCustomField.entity == next_entity, CRMCustomField.field_key == next_key, CRMCustomField.id != record.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Custom field key already exists for this entity")
    _validate_related_records(db, data, organization_id)
    if resource.model is CRMDeal:
        _validate_deal_pipeline_stage(db, data.get("pipeline_id", record.pipeline_id), data.get("stage_id", record.stage_id), organization_id)
    _assert_write_scope(resource, {**_serialize(record), **data}, current_user, db)
    _assert_final_action_allowed(db, organization_id, resource, record, data)
    for key, value in data.items():
        if key not in {"id", "organization_id", "created_at", "created_by_user_id"}:
            setattr(record, key, value)
    if resource.model is CRMDeal:
        _apply_deal_close_fields(record, data)
    if resource.model is CRMMeeting and any(key in data for key in {"title", "description", "location", "start_time", "end_time", "status"}):
        if getattr(record, "external_event_id", None):
            record.sync_status = "pending"
        if raw_payload.get("syncToCalendar"):
            _sync_meeting_to_calendar(db, organization_id, record, current_user, raw_payload.get("externalProvider") or raw_payload.get("provider"))
    if "updated_by_user_id" in columns:
        record.updated_by_user_id = current_user.id
    if "updated_at" in columns:
        record.updated_at = datetime.now(timezone.utc)
    if resource.model is CRMLead:
        if "lead_score" in data:
            score = max(0, min(100, int(data["lead_score"] or 0)))
            record.lead_score = score
            record.lead_score_label = _score_label(score)
            record.rating = record.lead_score_label
            record.lead_score_mode = "manual"
        elif str(getattr(record, "lead_score_mode", "automatic") or "automatic").lower() == "automatic":
            _apply_lead_score(db, record, organization_id, current_user.id)
    if canonical in CUSTOM_FIELD_SUPPORTED_ENTITIES:
        _save_custom_field_values(db, canonical, record.id, organization_id, current_user.id, custom_values)
    if resource.model is CRMDeal and deal_contacts_payload is not None:
        db.query(CRMDealContact).filter(CRMDealContact.organization_id == organization_id, CRMDealContact.deal_id == record.id).delete(synchronize_session=False)
        db.flush()
        _create_deal_contact_links_from_payload(db, record, deal_contacts_payload, organization_id, current_user.id)
        _sync_deal_primary_contact(db, record)
    if resource.model in {CRMLead, CRMCompany, CRMDeal} and "territory_id" not in data:
        _apply_territory_assignment(db, organization_id, record, override_manual=False, override_owner=not owner_was_provided)
    db.commit()
    db.refresh(record)
    _create_update_timeline_events(db, entity, record, before, data, organization_id, current_user.id)
    changed_audit = {
        key: {"old": _json_ready(before.get(key)), "new": _json_ready(getattr(record, key, None))}
        for key in IMPORTANT_UPDATE_FIELDS.intersection(data.keys())
        if _json_ready(before.get(key)) != _json_ready(getattr(record, key, None))
    }
    if changed_audit:
        action = "UPDATE"
        if resource.model is CRMDeal and "stage_id" in changed_audit:
            action = "STAGE_CHANGE"
        elif "owner_user_id" in changed_audit:
            action = "ASSIGNMENT_CHANGE"
        elif resource.model is CRMQuotation and "status" in changed_audit:
            action = "QUOTATION_STATUS_CHANGE"
        _create_crm_audit_log(
            db,
            user_id=current_user.id,
            entity_type=_canonical_entity(entity),
            entity_id=record.id,
            action=action,
            old_values={key: value["old"] for key, value in changed_audit.items()},
            new_values={key: value["new"] for key, value in changed_audit.items()},
            description=f"CRM {action.lower().replace('_', ' ')}",
        )
    for event_type in _event_types_for_update(canonical, before, record, data):
        _enqueue_webhook_event(db, organization_id, event_type, _serialize(record), current_user.id, {"changedFields": sorted(data)})
    db.commit()
    if resource.model is not CRMLead:
        _recalculate_linked_lead(db, _serialize(record), organization_id, current_user.id)
        db.commit()
    if resource.model is CRMDeal:
        _maybe_create_srm_handoff_for_won_deal(db, record, current_user)
        db.commit()
    return _serialize(record)


@router.delete("/{entity}/{record_id}")
def delete_record(
    entity: str,
    record_id: int,
    remapStageId: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("crm_manage", "crm_admin")),
):
    resource = _get_resource(entity)
    record = _get_record(db, resource, record_id, _organization_id(db, current_user), include_deleted=True)
    organization_id = _organization_id(db, current_user)
    _assert_record_visible(db, resource, record_id, organization_id, current_user, include_deleted=True)
    if resource.model is CRMPipeline:
        active_deals = _base_query(db, _get_resource("deals"), organization_id).filter(CRMDeal.pipeline_id == record.id).count()
        if active_deals:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a pipeline while deals are assigned to it")
    if resource.model is CRMPipelineStage:
        remap_stage_id = remapStageId
        active_deals = _base_query(db, _get_resource("deals"), organization_id).filter(CRMDeal.stage_id == record.id).count()
        if active_deals and not remap_stage_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stage has deals. Provide remapStageId to move deals before deletion.")
        if active_deals and remap_stage_id:
            remap_stage = _get_record(db, _get_resource("pipeline-stages"), remap_stage_id, organization_id)
            if remap_stage.pipeline_id != record.pipeline_id:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Remap stage must belong to the same pipeline")
            _base_query(db, _get_resource("deals"), organization_id).filter(CRMDeal.stage_id == record.id).update(
                {"stage_id": remap_stage.id, "pipeline_id": remap_stage.pipeline_id, "updated_by_user_id": current_user.id, "updated_at": datetime.now(timezone.utc)},
                synchronize_session=False,
            )
    columns = _columns(resource.model)
    if resource.soft_delete and "deleted_at" in columns:
        record.deleted_at = datetime.now(timezone.utc)
        if "updated_by_user_id" in columns:
            record.updated_by_user_id = current_user.id
    else:
        db.delete(record)
    _create_crm_audit_log(
        db,
        user_id=current_user.id,
        entity_type=_canonical_entity(entity),
        entity_id=record_id,
        action="DELETE",
        old_values=_serialize(record),
        description="CRM record deleted",
    )
    db.commit()
    return {"message": "CRM record deleted"}
