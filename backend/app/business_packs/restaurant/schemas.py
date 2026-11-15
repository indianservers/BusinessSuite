"""Kitchen inputs identify existing order lines, never financial instructions."""
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

ID = Annotated[StrictInt, Field(gt=0)]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TableCreate(StrictInput):
    request_key: UUID
    name: str = Field(min_length=1, max_length=80)
    capacity: Annotated[StrictInt, Field(ge=1, le=1000)]

    @field_validator('name')
    @classmethod
    def table_name(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('A printable table name is required')
        return value


class TableUpdate(TableCreate):
    expected_revision: ID
    active: StrictBool


class KitchenSourceLine(StrictInput):
    sales_order_line_id: ID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    instruction: str = Field(default='', max_length=1000)


class KitchenSubmit(StrictInput):
    request_key: UUID
    service_order_id: ID
    expected_revision: ID
    lines: list[KitchenSourceLine] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_sources(self):
        if len({line.sales_order_line_id for line in self.lines}) != len(self.lines):
            raise ValueError('Combine quantities for each source order line')
        return self


class TicketTransition(StrictInput):
    request_key: UUID
    expected_revision: ID


class VoidOrder(TicketTransition):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator('reason')
    @classmethod
    def meaningful_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('A void reason is required')
        return value


class TableTransfer(TicketTransition):
    destination_table_id: ID
    expected_destination_revision: ID


class PaidOrderOpen(StrictInput):
    request_key: UUID
    checkout_id: ID
    expected_checkout_revision: ID
    table_id: ID | None = None
    expected_table_revision: ID | None = None

    @model_validator(mode='after')
    def table_revision(self):
        if (self.table_id is None) != (self.expected_table_revision is None):
            raise ValueError('Selecting a table requires its current revision')
        return self


class ModifierSelection(StrictInput):
    expected_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    group: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    product_id: ID
    quantity: StrictInt = Field(default=1, ge=1, le=20)


class TabMenuLine(StrictInput):
    modifiers: list[ModifierSelection] = Field(default_factory=list, max_length=100, exclude_if=lambda value: not value)
    product_id: ID
    quantity: Decimal = Field(gt=0, le=1000000000, max_digits=12, decimal_places=2, allow_inf_nan=False)
    warehouse_id: ID | None = None
    expected_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)


class TabCreate(StrictInput):
    request_key: UUID
    customer_id: ID | None = None
    currency: str = Field(default='INR', pattern=r'^[A-Z]{3}$')
    table_id: ID | None = None
    expected_table_revision: ID | None = None
    lines: list[TabMenuLine] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def table_revision(self):
        if (self.table_id is None) != (self.expected_table_revision is None):
            raise ValueError('Selecting a table requires its current revision')
        return self


class TabAdd(StrictInput):
    request_key: UUID
    expected_revision: ID
    lines: list[TabMenuLine] = Field(min_length=1, max_length=100)


class TabBill(StrictInput):
    request_key: UUID
    expected_revision: ID
    pos_session_id: ID
    expected_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)


class TabAssignCustomer(StrictInput):
    request_key: UUID
    expected_revision: ID
    customer_id: ID


class TabPayment(StrictInput):
    request_key: UUID
    expected_revision: ID
    pos_session_id: ID | None = None
    payment: 'PaymentInput'


from app.apps.srm.service_checkout_schemas import PaymentInput
TabPayment.model_rebuild()


class TabAnonymousSettle(StrictInput):
    request_key: UUID
    expected_revision: ID
    pos_session_id: ID
    expected_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    payments: list[PaymentInput] = Field(min_length=1, max_length=10)

    @model_validator(mode='after')
    def full_payment(self):
        if len({payment.payment_key for payment in self.payments}) != len(self.payments):
            raise ValueError('Payment keys must be unique')
        if sum((payment.amount for payment in self.payments), Decimal(0)) != self.expected_total:
            raise ValueError('Anonymous settlement requires the entire bill in one transaction')
        return self
