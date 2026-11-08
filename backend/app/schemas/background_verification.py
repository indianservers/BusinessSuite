from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, Field, model_validator
from typing import Literal


class BackgroundVerificationVendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_email: Optional[str] = None
    provider_code: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key_ref: Optional[str] = None
    webhook_secret_ref: Optional[str] = None
    supports_api_submission: str = "No"
    status: str = "Active"


class BackgroundVerificationVendorSchema(BackgroundVerificationVendorCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BackgroundVerificationCheckCreate(BaseModel):
    check_type: str = Field(min_length=1, max_length=80)
    employee_document_id: Optional[int] = None
    document_url: Optional[str] = None
    remarks: Optional[str] = None


class BackgroundVerificationRequestCreate(BaseModel):
    vendor_id: Optional[int] = None
    candidate_id: Optional[int] = None
    employee_id: Optional[int] = None
    package_name: str = Field(min_length=1, max_length=120)
    purpose: str = Field(default="Employment verification", min_length=1, max_length=80)
    owner_user_id: Optional[int] = None
    expected_completion_date: Optional[date] = None
    vendor_reference: Optional[str] = None
    consent_url: Optional[str] = None
    remarks: Optional[str] = None
    checks: List[BackgroundVerificationCheckCreate] = Field(default_factory=list, min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_candidate_or_employee(self):
        if not self.candidate_id and not self.employee_id:
            raise ValueError("candidate_id or employee_id is required")
        names = [check.check_type.strip().lower() for check in self.checks]
        if len(set(names)) != len(names) or not all(names):
            raise ValueError("Each check must have a unique, nonblank name")
        return self


class BackgroundVerificationCheckUpdate(BaseModel):
    status: Literal["Pending", "In Progress", "Completed", "Verified", "Unable to Verify", "Not Applicable"]
    employee_document_id: Optional[int] = None
    version: Optional[int] = None
    result: Optional[str] = None
    score: Optional[Decimal] = None
    document_url: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    remarks: Optional[str] = None


class BackgroundVerificationRequestUpdate(BaseModel):
    status: Literal["Initiated", "In Progress", "On Hold", "Awaiting Review", "Completed", "Cancelled"]
    version: Optional[int] = None
    expected_completion_date: Optional[date] = None
    owner_user_id: Optional[int] = None
    review_notes: Optional[str] = Field(default=None, max_length=10000)
    completed_at: Optional[datetime] = None
    vendor_status: Optional[str] = None
    overall_result: Optional[str] = None
    report_url: Optional[str] = None
    remarks: Optional[str] = None


class BackgroundVerificationConsentUpdate(BaseModel):
    consent_url: Optional[str] = None
    consent_status: str = "Captured"
    employee_document_id: Optional[int] = None
    version: Optional[int] = None


class BackgroundVerificationSubmitResponse(BaseModel):
    id: int
    status: str
    vendor_reference: str
    submitted_at: datetime

    class Config:
        from_attributes = True


class BackgroundVerificationWebhookCheck(BackgroundVerificationCheckUpdate):
    check_type: str


class BackgroundVerificationWebhookPayload(BaseModel):
    vendor_reference: str
    event_type: str = "verification.updated"
    status: Optional[str] = None
    vendor_status: Optional[str] = None
    overall_result: Optional[str] = None
    report_url: Optional[str] = None
    remarks: Optional[str] = None
    checks: List[BackgroundVerificationWebhookCheck] = []
    raw_payload: Optional[dict[str, Any]] = None


class BackgroundVerificationConnectorEventSchema(BaseModel):
    id: int
    request_id: int
    vendor_id: Optional[int] = None
    event_type: str
    vendor_reference: Optional[str] = None
    payload_json: Any
    processing_status: str
    error_message: Optional[str] = None
    received_at: datetime

    class Config:
        from_attributes = True


class BackgroundVerificationCheckSchema(BaseModel):
    id: int
    request_id: int
    check_type: str
    status: str
    result: Optional[str] = None
    score: Optional[Decimal] = None
    document_url: Optional[str] = None
    employee_document_id: Optional[int] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


class BackgroundVerificationRequestSchema(BaseModel):
    id: int
    vendor_id: Optional[int] = None
    candidate_id: Optional[int] = None
    employee_id: Optional[int] = None
    package_name: str
    status: str
    vendor_status: Optional[str] = None
    initiated_by: Optional[int] = None
    initiated_at: datetime
    consent_status: str
    consent_captured_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    expected_completion_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    overall_result: Optional[str] = None
    vendor_reference: Optional[str] = None
    report_url: Optional[str] = None
    consent_url: Optional[str] = None
    remarks: Optional[str] = None
    purpose: Optional[str] = None
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    version: int = 1
    checks: List[BackgroundVerificationCheckSchema] = []

    class Config:
        from_attributes = True
