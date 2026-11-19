"""Discriminated, industry-neutral configuration for the canonical catalog."""
from datetime import date
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func

KINDS = ("product", "service", "membership", "subscription", "bundle")
PLAN_KINDS = ("membership", "subscription")


def offering_kind(row):
    return row.product_type if row.product_type in KINDS[1:] else "product"


def detail_column(kind):
    # All five kinds reference the same master; retain legacy service aliases.
    return "service_id" if kind == "service" else "product_id"


def kind_predicate(model, kind):
    return (func.coalesce(model.product_type, "stock").notin_(KINDS[1:])
            if kind == "product" else model.product_type == kind)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Duration(Contract):
    unit: Literal["day", "week", "month", "year", "custom", "lifetime"] = "month"
    count: int = Field(default=1, ge=1, le=12000)
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.unit == "custom" and (not self.start or not self.end):
            raise ValueError("Custom duration requires start and end dates")
        if self.start and self.end and self.end <= self.start:
            raise ValueError("End date must follow start date")
        return self


class Eligibility(Contract):
    offering_ids: list[int] = Field(default_factory=list, max_length=500)
    locations: list[Annotated[str, Field(min_length=1, max_length=180)]] = Field(default_factory=list, max_length=100)
    customer_groups: list[Annotated[str, Field(min_length=1, max_length=180)]] = Field(default_factory=list, max_length=100)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    blackout_dates: list[date] = Field(default_factory=list, max_length=366)

    @model_validator(mode="after")
    def valid(self):
        if any(v < 0 or v > 6 for v in self.weekdays) or any(v <= 0 for v in self.offering_ids):
            raise ValueError("Invalid weekday or offering ID")
        return self


class Benefit(Contract):
    key: str = Field(min_length=1, max_length=80)
    type: Literal["access", "discount_percent", "discount_fixed", "special_price", "credits", "sessions", "seats", "priority_booking", "included_service", "custom"]
    label: str = Field(min_length=1, max_length=180)
    allowance: Decimal | None = Field(default=None, ge=0, le=1000000000, decimal_places=4)
    value: Decimal = Field(default=0, ge=0, le=1000000000, decimal_places=4)
    priority: int = Field(default=0, ge=0, le=1000)
    stacking: Literal["exclusive", "best", "stack"] = "best"
    consumption_event: Literal["booking", "check_in", "attendance", "completion", "purchase"] = "completion"
    rollover: bool = False
    eligibility: Eligibility = Field(default_factory=Eligibility)

    @model_validator(mode="after")
    def percentage(self):
        if self.type == "discount_percent" and self.value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        return self


class Renewal(Contract):
    mode: Literal["manual", "automatic"] = "manual"
    reminder_days: list[Annotated[int, Field(ge=0, le=3650)]] = Field(default_factory=lambda: [30, 7, 1], max_length=20)
    price: Decimal | None = Field(default=None, ge=0, le=9999999999, decimal_places=2)


class Billing(Contract):
    mode: Literal["prepaid", "postpaid"] = "prepaid"
    recurring: bool = False
    automation: bool = False
    interval_unit: Literal["day", "week", "month", "year"] = "month"
    interval_count: int = Field(default=1, ge=1, le=1200)
    anchor_day: int = Field(default=1, ge=1, le=31)
    timezone: str = Field(default="UTC", max_length=80)
    setup_fee: Decimal = Field(default=0, ge=0, le=9999999999, decimal_places=2)
    refundable_deposit: Decimal = Field(default=0, ge=0, le=9999999999, decimal_places=2)
    trial_days: int = Field(default=0, ge=0, le=3650)
    grace_days: int = Field(default=0, ge=0, le=3650)
    proration: Literal["none", "daily"] = "none"
    overage: Literal["deny", "allow", "charge"] = "deny"

    @model_validator(mode="after")
    def supported(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown billing timezone")
        if self.automation:
            raise ValueError("Automatic billing requires an enabled invoice scheduler; use manual billing")
        return self


class Plan(Contract):
    tier: str = Field(default="", max_length=100)
    duration: Duration = Field(default_factory=Duration)
    activation: Literal["purchase", "first_use", "selected_date", "approval"] = "purchase"
    beneficiary_type: Literal["person", "organization", "family", "group"] = "person"
    beneficiary_limit: int = Field(default=1, ge=1, le=100000)
    benefits: list[Benefit] = Field(default_factory=list, max_length=100)
    eligibility: Eligibility = Field(default_factory=Eligibility)
    renewal: Renewal = Field(default_factory=Renewal)
    billing: Billing = Field(default_factory=Billing)
    allow_pause: bool = True
    allow_transfer: bool = False
    employee_ids: list[int] = Field(default_factory=list, max_length=100)
    project_template_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def unique(self):
        if len({b.key for b in self.benefits}) != len(self.benefits):
            raise ValueError("Benefit keys must be unique")
        return self


class Component(Contract):
    offering_id: int = Field(gt=0)
    quantity: Decimal = Field(default=1, gt=0, le=1000000, decimal_places=4)
    optional: bool = False
    allocated_price: Decimal | None = Field(default=None, ge=0, le=9999999999, decimal_places=2)
    fulfillment: Literal["purchase", "delivery", "completion"] = "purchase"


class Bundle(Contract):
    type: Literal["fixed", "configurable", "quantity", "prepaid", "mix_and_match"] = "fixed"
    pricing: Literal["package", "components"] = "package"
    components: list[Component] = Field(min_length=1, max_length=100)
    eligibility: Eligibility = Field(default_factory=Eligibility)

    @model_validator(mode="after")
    def unique(self):
        if len({c.offering_id for c in self.components}) != len(self.components):
            raise ValueError("Bundle components must be unique")
        return self


def validate_bundle(db, user, source, bundle, parent_id=None):
    """Validate the full graph using the same visibility rules as its parent."""
    from app.shared.catalog import item_record
    from app.apps.srm.models import SRMProduct
    def visit(ident, path):
        if ident in path:
            from fastapi import HTTPException
            raise HTTPException(422, "Circular bundle reference")
        if len(path) >= 20:
            from fastapi import HTTPException
            raise HTTPException(422, "Bundle nesting exceeds 20 levels")
        row = db.get(SRMProduct, ident)
        kind = offering_kind(row) if row else "product"
        row, _ = item_record(db, user, source, kind, ident, archived=False)
        nested = (row.metadata_json or {}).get("bundle")
        if kind == "bundle" and nested:
            for child in Bundle.model_validate(nested).components:
                visit(child.offering_id, path | {ident})
    for component in bundle.components:
        visit(component.offering_id, {parent_id} if parent_id else set())
