from app.core.input_validation import NationalPhone,CallingCode
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WhatsAppESSConfigCreate(BaseModel):
    provider: str = "WhatsApp Business"
    business_phone_number: str
    business_phone_number_country_code: str | None = None
    webhook_url: Optional[str] = None
    access_token_ref: Optional[str] = None
    app_secret_ref: Optional[str] = None
    verify_token_ref: Optional[str] = None
    default_language: str = "en"
    is_active: bool = True
    opt_in_required: bool = True


class WhatsAppESSConfigSchema(WhatsAppESSConfigCreate):
    id: int
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WhatsAppInboundMessage(BaseModel):
    phone_number: NationalPhone
    phone_number_country_code: CallingCode
    message_text: str
    provider_message_id: Optional[str] = None


class WhatsAppESSMessageSchema(BaseModel):
    id: int
    session_id: int
    employee_id: int
    direction: str
    phone_number: str
    phone_number_country_code: str | None = None
    message_text: str
    intent: Optional[str] = None
    status: str
    response_text: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WhatsAppTemplateCreate(BaseModel):
    config_id: int
    template_name: str
    intent: str
    language: str = "en"
    body_text: str
    provider_template_id: Optional[str] = None
    status: str = "Draft"


class WhatsAppTemplateSchema(WhatsAppTemplateCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WhatsAppOptInCreate(BaseModel):
    employee_id: int
    phone_number: str
    phone_number_country_code: str | None = None
    status: str = "Opted In"
    source: str = "ESS"
    consent_text: Optional[str] = None


class WhatsAppOptInSchema(WhatsAppOptInCreate):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class WhatsAppOutboundMessage(BaseModel):
    employee_id: int
    phone_number: NationalPhone
    phone_number_country_code: CallingCode
    template_id: Optional[int] = None
    message_text: Optional[str] = None
    intent: str = "notification"


class WhatsAppDeliveryCallback(BaseModel):
    provider_message_id: str
    status: str
    raw_payload: Optional[str] = None
