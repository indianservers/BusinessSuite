from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator


class RecallInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    request_key:UUID
    batch_id:int=Field(gt=0,strict=True)
    expected_batch_revision:int=Field(ge=0,strict=True)
    expected_batch_status:Literal['available','quarantined','recalled']
    action:Literal['quarantine','recall']
    reason:str=Field(min_length=3,max_length=2000)


class RecallCommand(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    request_key:UUID
    expected_revision:int=Field(gt=0,strict=True)
    expected_batch_revision:int=Field(ge=0,strict=True)
    expected_batch_status:Literal['available','quarantined','recalled']
    action:Literal['recall','close']
    reason:str=Field(min_length=3,max_length=2000)
