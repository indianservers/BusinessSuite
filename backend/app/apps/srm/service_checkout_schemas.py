from app.shared.employee_categories import WorkCategories
"""Strict source inputs for the server-owned atomic checkout operation."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from app.shared.follow_ups import ScheduleTemplate
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictBool, field_validator, model_validator

ID = Annotated[StrictInt, Field(gt=0)]
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class BookingSelection(Strict):
    policy_id: ID
    expected_policy_revision: ID
    eligibility_id: ID
    expected_eligibility_revision: ID
    provider_resource_id: ID
    employee_id: ID
    additional_resource_ids: list[ID] = Field(default_factory=list, max_length=9)
    starts_at: datetime
    duration_minutes: Annotated[StrictInt, Field(ge=5, le=720)]
    @model_validator(mode='after')
    def resources(self):
        if len(set(self.additional_resource_ids)) != len(self.additional_resource_ids) or self.provider_resource_id in self.additional_resource_ids:
            raise ValueError('Select each resource once')
        return self
    @field_validator('starts_at')
    @classmethod
    def aware(cls,value):
        if value.utcoffset() is None: raise ValueError('Booking time requires a timezone offset')
        return value.astimezone(timezone.utc)

class CheckoutFollowUp(ScheduleTemplate):
    model_config = ConfigDict(extra="forbid")


class CheckoutLineInput(Strict):
    client_line_key: UUID
    line_kind: Literal['product','unscheduled_service','booked_service']
    product_id: ID
    quantity: Decimal = Field(default=Decimal(1),gt=0,le=1000000000,decimal_places=3,allow_inf_nan=False,
                              description='Up to three decimals only for authorized Pharma batch-and-expiry medicines; all other checkout quantities retain two decimals.')
    unit_price: Decimal | None = Field(default=None,ge=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    discount_amount: Decimal = Field(default=Decimal(0),ge=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    note: str = Field(default="",max_length=10000)
    follow_up: CheckoutFollowUp | None = None
    warehouse_id: ID | None = None
    booking: BookingSelection | None = None
    @model_validator(mode='after')
    def kind(self):
        if (self.line_kind=='booked_service') != (self.booking is not None):
            raise ValueError('Only booked service lines require a booking')
        if self.booking and self.quantity != 1: raise ValueError('Each booking is one distinct service occurrence')
        return self

class PaymentInput(Strict):
    payment_key: UUID
    method: Literal['cash','card','bank_transfer','upi']
    amount: Decimal = Field(gt=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    reference: str | None = Field(default=None,max_length=160)

class CheckoutInput(Strict):
    buyer_mode: Literal['registered','anonymous_cash'] = 'registered'
    request_id: UUID
    customer_id: StrictInt | None = Field(default=None,ge=0)
    pos_session_id: ID
    currency: str = Field(default='INR',pattern=r'^[A-Z]{3}$')
    billing_mode: Literal['invoice_at_checkout'] = 'invoice_at_checkout'
    note: str = Field(default='',max_length=4000)
    expected_total: Decimal | None = Field(default=None,ge=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    bill_discount_amount: Decimal = Field(default=Decimal(0),ge=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    lines: list[CheckoutLineInput] = Field(min_length=1,max_length=100)
    payments: list[PaymentInput] = Field(default_factory=list,max_length=10)
    @model_validator(mode='after')
    def unique(self):
        if self.buyer_mode=='registered' and (self.customer_id is None or self.customer_id==0):raise ValueError('A named customer is required')
        if self.buyer_mode=='anonymous_cash' and self.customer_id not in (None,0):raise ValueError('Anonymous counter account is resolved by the server, never a supplied customer ID')
        if len({line.client_line_key for line in self.lines})!=len(self.lines): raise ValueError('Cart line keys must be unique')
        if len({p.payment_key for p in self.payments})!=len(self.payments): raise ValueError('Payment keys must be unique')
        return self

class PolicyInput(Strict):
    required_resource_types: list[Literal['room', 'chair', 'equipment', 'location']] | None = Field(default=None, max_length=4)
    @field_validator('required_resource_types')
    @classmethod
    def unique_resource_types(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError('Choose each required resource type once')
        return value

    employee_categories: WorkCategories = Field(default_factory=list)
    service_product_id: ID
    default_duration_minutes: Annotated[StrictInt, Field(ge=5,le=720)]
    min_duration_minutes: Annotated[StrictInt, Field(ge=5,le=720)]
    max_duration_minutes: Annotated[StrictInt, Field(ge=5,le=720)]
    booking_required: StrictBool = True
    allow_duration_override: StrictBool = False
    active: StrictBool = True
    expected_revision: ID | None = None
    @model_validator(mode='after')
    def durations(self):
        if not self.min_duration_minutes<=self.default_duration_minutes<=self.max_duration_minutes:
            raise ValueError('Default duration must lie inside the duration bounds')
        return self

class EligibilityInput(Strict):
    policy_id: ID
    expected_policy_revision: ID
    provider_resource_id: ID
    employee_id: ID
    active: StrictBool = True
    expected_revision: ID | None = None
class AppendPaymentInput(Strict):
    pos_session_id: ID | None = None
    expected_revision: ID
    payment: PaymentInput
class GroupedRescheduleInput(Strict):
    expected_appointment_revision: ID
    expected_occurrence_revision: ID
    booking: BookingSelection
    additional_resource_ids: list[ID] = Field(default_factory=list,max_length=9)
    @model_validator(mode='after')
    def resources(self):
        if len(set(self.additional_resource_ids))!=len(self.additional_resource_ids) or self.booking.provider_resource_id in self.additional_resource_ids:
            raise ValueError('Select each resource once')
        return self
