from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentTemplateCreate(BaseModel):
    name: str
    template_type: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[str] = None
    is_active: bool = True


class DocumentTemplateSchema(DocumentTemplateCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class CompanyPolicyCreate(BaseModel):
    title: str
    category: Optional[str] = None
    content: Optional[str] = None
    document_url: Optional[str] = None
    version: str = "1.0"
    effective_date: Optional[datetime] = None
    is_published: bool = False
    require_acknowledgement: bool = False


class CompanyPolicySchema(CompanyPolicyCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class CompanyPolicyVersionCreate(BaseModel):
    version: str
    content: Optional[str] = None
    document_url: Optional[str] = None
    effective_date: Optional[datetime] = None
    change_summary: Optional[str] = None


class CompanyPolicyVersionSchema(CompanyPolicyVersionCreate):
    id: int
    policy_id: int
    published_by: Optional[int] = None
    published_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class GeneratedDocumentCreate(BaseModel):
    template_id: Optional[int] = None
    employee_id: int
    document_type: Optional[str] = None
    document_name: str
    file_url: Optional[str] = None


class TemplateGenerateRequest(BaseModel):
    employee_id: int
    document_name: Optional[str] = None
    variables: dict[str, str | int | float | None] = {}


class GeneratedDocumentSchema(GeneratedDocumentCreate):
    id: int
    is_signed: bool = False
    signed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class EmployeeCertificateSchema(BaseModel):
    id: int
    employee_id: int
    category: str
    certificate_type: str
    title: str
    issuing_entity: Optional[str] = None
    issuing_entity_type: Optional[str] = None
    class_or_grade: Optional[str] = None
    course_or_program: Optional[str] = None
    certificate_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    file_url: str
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    verification_status: str
    verified_by_user_id: Optional[int] = None
    verifier_name: Optional[str] = None
    verifier_company: Optional[str] = None
    verifier_designation: Optional[str] = None
    verifier_contact: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    uploaded_by: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class CertificateVerificationUpdate(BaseModel):
    verification_status: str
    verifier_name: Optional[str] = None
    verifier_company: Optional[str] = None
    verifier_designation: Optional[str] = None
    verifier_contact: Optional[str] = None
    verification_notes: Optional[str] = None


class CertificateImportExportBatchSchema(BaseModel):
    id: int
    operation_type: str
    employee_id: Optional[int] = None
    source_file_url: Optional[str] = None
    output_file_url: Optional[str] = None
    error_report_url: Optional[str] = None
    original_filename: Optional[str] = None
    status: str
    total_records: int
    success_count: int
    failure_count: int
    requested_by: Optional[int] = None
    requested_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
