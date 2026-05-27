from datetime import date, datetime, timezone
import os
import re
import shutil
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_current_user, get_db, RequirePermission
from app.core.masking import user_has_permission
from app.models.document import (
    CertificateImportExportBatch,
    CompanyPolicy,
    CompanyPolicyVersion,
    DocumentTemplate,
    EmployeeCertificate,
    GeneratedDocument,
)
from app.models.employee import Employee
from app.models.user import User
from app.schemas.document import (
    CertificateImportExportBatchSchema,
    CertificateVerificationUpdate,
    CompanyPolicyCreate,
    CompanyPolicySchema,
    CompanyPolicyVersionCreate,
    CompanyPolicyVersionSchema,
    DocumentTemplateCreate,
    DocumentTemplateSchema,
    EmployeeCertificateSchema,
    GeneratedDocumentCreate,
    GeneratedDocumentSchema,
    TemplateGenerateRequest,
)

router = APIRouter(prefix="/documents", tags=["Documents & Policies"])


def _validate_upload(file: UploadFile, extra_extensions: set[str] | None = None) -> str:
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    allowed = set(settings.allowed_extensions_list)
    if extra_extensions:
        allowed.update(extra_extensions)
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(sorted(allowed))}")
    return ext


def _save_upload(
    file: UploadFile,
    folder: str,
    prefix: str = "",
    extra_extensions: set[str] | None = None,
) -> tuple[str, str, int]:
    ext = _validate_upload(file, extra_extensions=extra_extensions)
    upload_path = os.path.join(settings.UPLOAD_DIR, folder)
    os.makedirs(upload_path, exist_ok=True)
    filename = f"{prefix}{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(upload_path, filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    size = os.path.getsize(file_path)
    return f"/uploads/{folder}/{filename}", file.content_type or "", size


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _render_template(content: str, variables: dict) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = variables.get(key)
        return "" if value is None else str(value)

    return re.sub(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", replace, content or "")


@router.get("/templates", response_model=list[DocumentTemplateSchema])
def list_templates(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return db.query(DocumentTemplate).order_by(DocumentTemplate.created_at.desc()).all()


@router.post("/templates", response_model=DocumentTemplateSchema, status_code=status.HTTP_201_CREATED)
def create_template(data: DocumentTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    template = DocumentTemplate(**data.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.post("/templates/{template_id}/generate", response_model=GeneratedDocumentSchema, status_code=status.HTTP_201_CREATED)
def generate_from_template(
    template_id: int,
    data: TemplateGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.is_active == True).first()
    if not template:
        raise HTTPException(status_code=404, detail="Document template not found")
    employee = db.query(Employee).filter(Employee.id == data.employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    variables = {
        "employee_id": employee.employee_id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "designation": employee.designation.name if employee.designation else "",
        "department": employee.department.name if employee.department else "",
        "date_of_joining": employee.date_of_joining.isoformat() if employee.date_of_joining else "",
        "work_email": employee.work_email or "",
        "today": date.today().isoformat(),
        **data.variables,
    }
    rendered = _render_template(template.content or "", variables)
    folder = f"generated/{employee.id}"
    upload_path = os.path.join(settings.UPLOAD_DIR, folder)
    os.makedirs(upload_path, exist_ok=True)
    filename = f"{template.template_type or 'letter'}_{uuid.uuid4().hex}.html"
    file_path = os.path.join(upload_path, filename)
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    document = GeneratedDocument(
        template_id=template.id,
        employee_id=employee.id,
        document_type=template.template_type,
        document_name=data.document_name or template.name,
        file_url=f"/uploads/{folder}/{filename}",
        generated_by=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/policies", response_model=list[CompanyPolicySchema])
def list_policies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_view"))):
    return db.query(CompanyPolicy).order_by(CompanyPolicy.updated_at.desc().nullslast(), CompanyPolicy.created_at.desc()).all()


@router.post("/policies", response_model=CompanyPolicySchema, status_code=status.HTTP_201_CREATED)
def create_policy(data: CompanyPolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("company_manage"))):
    policy = CompanyPolicy(**data.model_dump())
    db.add(policy)
    db.flush()
    version = CompanyPolicyVersion(
        policy_id=policy.id,
        version=policy.version,
        content=policy.content,
        document_url=policy.document_url,
        effective_date=policy.effective_date,
        change_summary="Initial policy version",
        published_by=current_user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/policies/{policy_id}/versions", response_model=list[CompanyPolicyVersionSchema])
def list_policy_versions(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_view")),
):
    return db.query(CompanyPolicyVersion).filter(
        CompanyPolicyVersion.policy_id == policy_id
    ).order_by(CompanyPolicyVersion.published_at.desc()).all()


@router.post("/policies/{policy_id}/versions", response_model=CompanyPolicyVersionSchema, status_code=status.HTTP_201_CREATED)
def publish_policy_version(
    policy_id: int,
    data: CompanyPolicyVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    policy = db.query(CompanyPolicy).filter(CompanyPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    version = CompanyPolicyVersion(policy_id=policy_id, published_by=current_user.id, **data.model_dump())
    policy.version = data.version
    policy.content = data.content
    policy.document_url = data.document_url
    policy.effective_date = data.effective_date
    policy.is_published = True
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.get("/generated", response_model=list[GeneratedDocumentSchema])
def list_generated(employee_id: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("employee_view"))):
    query = db.query(GeneratedDocument)
    if employee_id:
        query = query.filter(GeneratedDocument.employee_id == employee_id)
    return query.order_by(GeneratedDocument.created_at.desc()).limit(200).all()


@router.post("/generated", response_model=GeneratedDocumentSchema, status_code=status.HTTP_201_CREATED)
def create_generated(data: GeneratedDocumentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("employee_update"))):
    document = GeneratedDocument(**data.model_dump(), generated_by=current_user.id)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/certificates", response_model=list[EmployeeCertificateSchema])
def list_certificates(
    employee_id: int | None = Query(None),
    category: str | None = Query(None),
    verification_status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EmployeeCertificate)
    if not user_has_permission(current_user, "employee_view"):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile linked to this user")
        if employee_id and employee_id != current_user.employee.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this employee's certificates")
        employee_id = current_user.employee.id
    if employee_id:
        query = query.filter(EmployeeCertificate.employee_id == employee_id)
    if category:
        query = query.filter(EmployeeCertificate.category == category)
    if verification_status:
        query = query.filter(EmployeeCertificate.verification_status == verification_status)
    return query.order_by(EmployeeCertificate.uploaded_at.desc()).limit(500).all()


@router.post("/certificates", response_model=EmployeeCertificateSchema, status_code=status.HTTP_201_CREATED)
async def upload_certificate(
    employee_id: int = Form(...),
    category: str = Form(...),
    certificate_type: str = Form(...),
    title: str = Form(...),
    issuing_entity: str | None = Form(None),
    issuing_entity_type: str | None = Form(None),
    class_or_grade: str | None = Form(None),
    course_or_program: str | None = Form(None),
    certificate_number: str | None = Form(None),
    issue_date: str | None = Form(None),
    expiry_date: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "employee_update"):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile linked to this user")
        if employee_id != current_user.employee.id:
            raise HTTPException(status_code=403, detail="Employees can upload only their own certificates")
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    file_url, content_type, size = _save_upload(file, f"certificates/{employee_id}", prefix="cert_")
    certificate = EmployeeCertificate(
        employee_id=employee_id,
        category=category,
        certificate_type=certificate_type,
        title=title,
        issuing_entity=issuing_entity,
        issuing_entity_type=issuing_entity_type,
        class_or_grade=class_or_grade,
        course_or_program=course_or_program,
        certificate_number=certificate_number,
        issue_date=_parse_date(issue_date),
        expiry_date=_parse_date(expiry_date),
        file_url=file_url,
        original_filename=file.filename,
        content_type=content_type,
        file_size_bytes=size,
        verification_status="Pending",
        uploaded_by=current_user.id,
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return certificate


@router.put("/certificates/{certificate_id}/verify", response_model=EmployeeCertificateSchema)
def verify_certificate(
    certificate_id: int,
    data: CertificateVerificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    if data.verification_status not in {"Pending", "Verified", "Rejected"}:
        raise HTTPException(status_code=400, detail="verification_status must be Pending, Verified, or Rejected")
    certificate = db.query(EmployeeCertificate).filter(EmployeeCertificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    certificate.verification_status = data.verification_status
    certificate.verifier_name = data.verifier_name
    certificate.verifier_company = data.verifier_company
    certificate.verifier_designation = data.verifier_designation
    certificate.verifier_contact = data.verifier_contact
    certificate.verification_notes = data.verification_notes
    certificate.verified_by_user_id = current_user.id
    certificate.verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(certificate)
    return certificate


@router.post("/certificates/imports", response_model=CertificateImportExportBatchSchema, status_code=status.HTTP_201_CREATED)
async def upload_certificate_import(
    employee_id: int | None = Form(None),
    remarks: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    file_url, _, _ = _save_upload(file, "certificate_imports", prefix="import_", extra_extensions={"csv", "xls", "xlsx"})
    batch = CertificateImportExportBatch(
        operation_type="Import",
        employee_id=employee_id,
        source_file_url=file_url,
        original_filename=file.filename,
        status="Uploaded",
        requested_by=current_user.id,
        remarks=remarks,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/certificates/exports", response_model=CertificateImportExportBatchSchema, status_code=status.HTTP_201_CREATED)
def create_certificate_export_log(
    employee_id: int | None = None,
    output_file_url: str | None = None,
    total_records: int = 0,
    remarks: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("reports_view")),
):
    batch = CertificateImportExportBatch(
        operation_type="Export",
        employee_id=employee_id,
        output_file_url=output_file_url,
        status="Completed",
        total_records=total_records,
        success_count=total_records,
        requested_by=current_user.id,
        completed_at=datetime.now(timezone.utc),
        remarks=remarks,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/certificates/import-export", response_model=list[CertificateImportExportBatchSchema])
def list_certificate_import_export_batches(
    operation_type: str | None = Query(None),
    employee_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_view")),
):
    query = db.query(CertificateImportExportBatch)
    if operation_type:
        query = query.filter(CertificateImportExportBatch.operation_type == operation_type)
    if employee_id:
        query = query.filter(CertificateImportExportBatch.employee_id == employee_id)
    return query.order_by(CertificateImportExportBatch.requested_at.desc()).limit(200).all()
