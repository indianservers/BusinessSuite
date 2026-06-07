from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailTemplatePayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    subject: str = Field(min_length=1, max_length=240)
    body_html: str | None = None
    body_text: str | None = None
    module_name: str = "lead"
    template_type: str = "email"
    active: bool = True


class EmailDraftPayload(BaseModel):
    related_record_type: str
    related_record_id: int
    to_email: EmailStr
    cc: str | None = None
    bcc: str | None = None
    subject: str
    body: str


class EmailSendPayload(EmailDraftPayload):
    template_id: int | None = None
    merge_data: dict[str, Any] | None = None


class WebformPayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    target_module: Literal["lead", "contact", "case", "custom"] = "lead"
    public_slug: str = Field(min_length=3, max_length=140)
    fields_json: list[dict[str, Any]] | None = None
    mapping_json: dict[str, str] | None = None
    active: bool = True
    auto_response_rule_id: int | None = None


class WebformSubmitPayload(BaseModel):
    values: dict[str, Any]
    anti_spam: str | None = None


class AutoResponseRulePayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    trigger_type: str = "webform_submission"
    template_id: int | None = None
    active: bool = True
    condition_json: dict[str, Any] | None = None


class CampaignPayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    type: Literal["email", "whatsapp", "mixed"] = "email"
    segment_json: dict[str, Any] | None = None
    template_id: int | None = None
    status: Literal["draft", "scheduled", "running", "completed", "cancelled"] = "draft"
    scheduled_at: datetime | None = None


class CampaignSchedulePayload(BaseModel):
    scheduled_at: datetime


class ConsentPayload(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    record_type: str | None = None
    record_id: int | None = None
    consent_type: str = "email"
    status: Literal["opted_in", "opted_out", "unsubscribed"] = "opted_in"
    source: str | None = None


class OptOutPayload(BaseModel):
    email: EmailStr
    channel: str = "email"
    reason: str | None = None
    source: str = "manual"


class WhatsAppTemplatePayload(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    template_key: str = Field(min_length=2, max_length=140)
    body_text: str = Field(min_length=1)
    provider_status: str = "placeholder_only"
    active: bool = True


class CommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

