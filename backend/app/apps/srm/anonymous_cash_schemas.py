from pydantic import BaseModel,ConfigDict,Field,StrictBool,StrictInt,model_validator
from typing import Literal
class CashAccountSetup(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['create','select','status']
    label:str|None=Field(default=None,min_length=1,max_length=180)
    jurisdiction_country:str|None=Field(default=None,pattern=r'^[A-Z]{2}$')
    customer_id:StrictInt|None=Field(default=None,gt=0)
    expected_revision:StrictInt=Field(default=0,ge=0)
    active:StrictBool=True
    reason:str=Field(min_length=8,max_length=1000)
    @model_validator(mode='after')
    def coherent(self):
        if self.action!='status' and (not self.label or not self.jurisdiction_country):raise ValueError('Explicit account label and jurisdiction are required')
        if (self.action=='select')!=(self.customer_id is not None):raise ValueError('Select requires an explicit dedicated customer account')
        if self.action=='status' and self.expected_revision<1:raise ValueError('An existing account revision is required')
        return self
