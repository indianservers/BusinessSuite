from typing import Any

from pydantic import BaseModel, Field


class PortalUserPayload(BaseModel):
    email: str
    display_name: str
    portal_type: str = Field(pattern="^(customer|partner|vendor)$")
    customer_id: int | None = None
    partner_id: int | None = None


class PortalInvitePayload(PortalUserPayload):
    permissions: list[str] = []


class PartnerLeadPayload(BaseModel):
    company_name: str
    contact_name: str
    email: str
    value: float = 0
    notes: str | None = None


class APIKeyPayload(BaseModel):
    name: str
    scopes: list[str]


class WebhookPayload(BaseModel):
    name: str
    target_url: str
    events: list[str]
    secret: str | None = None


class MarketplaceAppPayload(BaseModel):
    name: str
    category: str = "internal"
    description: str | None = None
    configuration_schema: dict[str, Any] = {}


class SandboxPayload(BaseModel):
    name: str
    copy_sample_data: bool = False


class CompanySettingsPayload(BaseModel):
    company_name: str
    logo_url: str | None = None
    fiscal_year_start_month: int = 4
    base_currency: str = "INR"
    timezone: str = "Asia/Calcutta"
    tax_defaults: dict[str, Any] = {}
    business_hours: dict[str, Any] = {}
    numbering_settings: dict[str, Any] = {}


class FeatureFlagPayload(BaseModel):
    feature_key: str
    enabled: bool = True
    upgrade_message: str | None = None


class SubscriptionPlanPayload(BaseModel):
    code: str
    name: str
    features: list[str]
    active: bool = True


class SubscriptionPayload(BaseModel):
    edition: str = "ultimate"
    plan_id: int | None = None
    status: str = "active"
    admin_override: bool = True


class CheckInPayload(BaseModel):
    customer_name: str
    lead_id: int | None = None
    deal_id: int | None = None
    latitude: str | None = None
    longitude: str | None = None
    notes: str | None = None
