"""Return commands never accept a refund total or a replacement customer."""
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

ID = Annotated[StrictInt, Field(gt=0)]


class ReturnLineInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    checkout_line_id: ID
    quantity: Annotated[Decimal, Field(gt=0, le=1000000000, max_digits=24, decimal_places=10)]
    restock: StrictBool = True


class RefundInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    method: Literal['cash', 'card']
    session_id: ID
    reference: str = Field(default='', max_length=200)

    @model_validator(mode='after')
    def actual_card_reference(self):
        if self.method=='card' and not self.reference.strip():
            raise ValueError('Record the completed card refund reference')
        return self


class ReturnInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    checkout_id: ID
    expected_checkout_revision: ID
    request_key: UUID
    lines: list[ReturnLineInput] = Field(min_length=1, max_length=100)
    refund: RefundInput
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def unique_lines(self):
        if len({line.checkout_line_id for line in self.lines}) != len(self.lines):
            raise ValueError('Each original sale line may appear only once')
        if not self.reason.strip():
            raise ValueError('A return reason is required')
        return self
