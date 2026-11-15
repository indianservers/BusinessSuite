from datetime import date
from typing import Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

ID = Annotated[StrictInt, Field(gt=0)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: UUID


class PeriodCreate(Input):
    engagement_id: ID
    client_id: ID
    starts_on: date
    ends_on: date
    due_on: date
    preparer_employee_id: ID
    reviewer_employee_id: ID
    title: str = Field(min_length=1, max_length=200)

    @field_validator('title')
    @classmethod
    def title_text(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('A printable title is required')
        return value

    @model_validator(mode='after')
    def period(self):
        if self.starts_on > self.ends_on or self.due_on < self.starts_on:
            raise ValueError('Service period and due date are invalid')
        if self.preparer_employee_id == self.reviewer_employee_id:
            raise ValueError('Preparer and reviewer must be different employees')
        return self


class RevisionInput(Input):
    expected_revision: ID


class WorkUpdate(RevisionInput):
    summary: str = Field(min_length=1, max_length=4000)

    @field_validator('summary')
    @classmethod
    def summary_text(cls, value):
        if not value.strip():
            raise ValueError('A work summary is required')
        return value.strip()


class ReviewInput(RevisionInput):
    expected_work_revision: ID
    reason: str = Field(default='', max_length=2000)


class AssignmentInput(RevisionInput):
    preparer_employee_id: ID
    reviewer_employee_id: ID

    @model_validator(mode='after')
    def independent(self):
        if self.preparer_employee_id == self.reviewer_employee_id:
            raise ValueError('Preparer and reviewer must be different employees')
        return self


class EngagementCreate(Input):
    client_id: ID
    name: str = Field(min_length=1,max_length=220)
    currency: str = Field(default='INR',pattern=r'^[A-Z]{3}$')
    planned_start_date: date | None = None
    planned_end_date: date | None = None

    @field_validator('name')
    @classmethod
    def engagement_name(cls,value):
        value=value.strip()
        if not value or any(ord(char)<32 or ord(char)==127 for char in value):
            raise ValueError('A printable engagement name is required')
        return value

    @model_validator(mode='after')
    def schedule(self):
        if self.planned_start_date and self.planned_end_date and self.planned_start_date>self.planned_end_date:
            raise ValueError('Engagement end date must not precede its start')
        return self
