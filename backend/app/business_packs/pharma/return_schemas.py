"""Commands select actual issued allocations; prices and source stamps are server-owned."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel,ConfigDict,Field,StrictInt,model_validator


class OriginalLotReturn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    allocation_id:StrictInt=Field(gt=0)
    quantity:Decimal=Field(gt=0,max_digits=14,decimal_places=3,allow_inf_nan=False)


class PharmaRefund(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    method:Literal['cash','card']
    session_id:StrictInt=Field(gt=0)
    reference:str=Field(default='',max_length=200)

    @model_validator(mode='after')
    def traceable_card(self):
        if self.method=='card' and not self.reference:
            raise ValueError('Record the actual card refund reference')
        return self


class PharmaReturnInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    request_key:UUID
    checkout_id:StrictInt=Field(gt=0)
    expected_checkout_revision:StrictInt=Field(gt=0)
    lots:list[OriginalLotReturn]=Field(min_length=1,max_length=200)
    refund:PharmaRefund
    reason:str=Field(min_length=5,max_length=2000)
    expected_refund_amount:Decimal|None=Field(default=None,gt=0,max_digits=14,decimal_places=2,allow_inf_nan=False)

    @model_validator(mode='after')
    def unique_originals(self):
        if len({row.allocation_id for row in self.lots})!=len(self.lots):
            raise ValueError('Select each original sale allocation only once')
        return self
