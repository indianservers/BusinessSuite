from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator


class ReceiptInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:UUID
    product_id:int=Field(gt=0,strict=True)
    warehouse_id:int=Field(gt=0,strict=True)
    batch_number:str=Field(min_length=1,max_length=120)
    manufacture_date:date|None=None
    expiry_date:date
    received_date:date
    quantity:Decimal=Field(gt=0,max_digits=14,decimal_places=3,allow_inf_nan=False)
    unit_cost:Decimal=Field(ge=0,max_digits=14,decimal_places=4,allow_inf_nan=False)

    @field_validator('batch_number')
    @classmethod
    def number(cls,value):
        value=value.strip()
        if not value:raise ValueError('Batch number is required')
        return value

    @model_validator(mode='after')
    def dates(self):
        if self.manufacture_date and self.expiry_date<self.manufacture_date:raise ValueError('Expiry precedes manufacture date')
        if self.expiry_date<=self.received_date:raise ValueError('Receipt requires an unexpired lot')
        if (self.quantity*self.unit_cost).quantize(Decimal('.01'))>=Decimal('1000000000000'):
            raise ValueError('Receipt value exceeds native stock ledger precision')
        return self
