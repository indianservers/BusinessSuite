from app.core.storage import persist_file
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

from app.core.employee_scope import employee_tenant_scope
from app.apps.srm.services.commercial import tenant
router = APIRouter(prefix="/documents", tags=["Documents & Policies"], dependencies=[Depends(employee_tenant_scope)])
from app.api.v1.document_studio import router as studio_router
router.include_router(studio_router)
from app.api.v1.document_vault import router as vault_router
router.include_router(vault_router)


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
    limit=settings.MAX_UPLOAD_SIZE_MB*1024*1024
    body=file.file.read(limit+1)
    if not body or len(body)>limit:
        raise HTTPException(413,'Upload exceeds the configured file size limit')
    with open(file_path, "wb") as f:
        f.write(body)
    persist_file(file_path)
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
    template = DocumentTemplate(organization_id=tenant(current_user),**data.model_dump())
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
    persist_file(file_path)
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
    policy = CompanyPolicy(organization_id=tenant(current_user),**data.model_dump())
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
    if not user_has_permission(current_user,'employee_update') and not user_has_permission(current_user,'employee_sensitive_view'):
        query=query.filter(GeneratedDocument.employee_id==(current_user.employee.id if current_user.employee else -1))
    if employee_id:
        query = query.filter(GeneratedDocument.employee_id == employee_id)
    return query.order_by(GeneratedDocument.created_at.desc()).limit(200).all()


@router.post("/generated", response_model=GeneratedDocumentSchema, status_code=status.HTTP_201_CREATED)
def create_generated(data: GeneratedDocumentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("employee_update"))):
    if not db.query(Employee.id).filter(Employee.id==data.employee_id).first():
        raise HTTPException(404,'Employee not found')
    if data.template_id and not db.query(DocumentTemplate.id).filter(DocumentTemplate.id==data.template_id).first():
        raise HTTPException(404,'Document template not found')
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
    reminder_date: str | None = Form(None),
    remarks: str | None = Form(None),
    replace_certificate_id: int | None = Form(None),
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

    from app.api.v1.document_vault import employees
    if not employees(db,current_user).filter(Employee.id==employee_id).first(): raise HTTPException(404,"Employee not found")
    if not replace_certificate_id and certificate_number and db.query(EmployeeCertificate).filter(EmployeeCertificate.employee_id==employee_id,EmployeeCertificate.certificate_number==certificate_number,EmployeeCertificate.certificate_type==certificate_type).first(): raise HTTPException(409,"This certificate reference already exists for this employee")
    try:
        parsed_issue, parsed_expiry = _parse_date(issue_date), _parse_date(expiry_date)
    except ValueError: raise HTTPException(422,"Use valid issue and expiry dates")
    if parsed_issue and parsed_expiry and parsed_expiry < parsed_issue: raise HTTPException(422,"Expiry date must be on or after issue date")
    from app.shared.models import ServicePolicy
    from app.api.v1.document_vault import records, audit
    import hashlib
    ext=(file.filename or "").rsplit(".",1)[-1].lower()
    if ext not in {"pdf","doc","docx","jpg","jpeg","png"}: raise HTTPException(400,"Upload a PDF, Word document or image")
    if reminder_date:
        try: _parse_date(reminder_date)
        except ValueError: raise HTTPException(422,"Use a valid reminder date")
    content=file.file.read(settings.MAX_UPLOAD_SIZE_MB*1024*1024+1)
    file.file.seek(0)
    signatures={"pdf":(b"%PDF",),"png":(b"\x89PNG\r\n\x1a\n",),"jpg":(b"\xff\xd8",),"jpeg":(b"\xff\xd8",),"docx":(b"PK",),"doc":(b"\xd0\xcf\x11\xe0",)}
    if not content.startswith(signatures[ext]): raise HTTPException(400,"File content does not match the selected document format")
    digest=hashlib.sha256(content).hexdigest()
    duplicate=db.query(ServicePolicy).filter(ServicePolicy.organization_id==tenant(current_user),ServicePolicy.scope_key==f"certificate-hash:{tenant(current_user)}:{employee_id}:{digest}").first()
    if duplicate: raise HTTPException(409,"This file has already been uploaded for this employee")
    old=None
    if replace_certificate_id:
        if not user_has_permission(current_user,"employee_update"): raise HTTPException(403,"HR document replacement permission is required")
        old=records(db,current_user).filter(EmployeeCertificate.id==replace_certificate_id,EmployeeCertificate.employee_id==employee_id).first()
        if not old: raise HTTPException(404,"Document to replace not found")
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
    if old:
        db.add(ServicePolicy(scope_key=f"certificate-revision:{old.id}:{uuid.uuid4().hex}",organization_id=tenant(current_user),module_key="hrms",kind="certificate_revision",updated_by=current_user.id,values_json=EmployeeCertificateSchema.model_validate(old).model_dump(mode="json")))
        for key in ("category","certificate_type","title","issuing_entity","issuing_entity_type","class_or_grade","course_or_program","certificate_number","issue_date","expiry_date","file_url","original_filename","content_type","file_size_bytes"):
            setattr(old,key,getattr(certificate,key))
        old.verification_status="Pending";old.verified_at=None;old.verified_by_user_id=None;old.verification_notes=None
        old.verifier_name=old.verifier_company=old.verifier_designation=old.verifier_contact=None
        old.uploaded_by=current_user.id;old.uploaded_at=datetime.now(timezone.utc)
        certificate=old
    db.add(certificate);db.flush()
    db.add(ServicePolicy(scope_key=f"certificate-hash:{tenant(current_user)}:{employee_id}:{digest}",organization_id=tenant(current_user),module_key="hrms",kind="certificate_file_hash",updated_by=current_user.id,values_json={"certificate_id":certificate.id}))
    metadata=db.query(ServicePolicy).filter(ServicePolicy.scope_key==f"certificate-metadata:{certificate.id}",ServicePolicy.organization_id==tenant(current_user)).first()
    if not metadata:
        metadata=ServicePolicy(scope_key=f"certificate-metadata:{certificate.id}",organization_id=tenant(current_user),module_key="hrms",kind="certificate_metadata",updated_by=current_user.id)
        db.add(metadata)
    metadata.values_json={"remarks":remarks or "","reminder_date":reminder_date or ""};metadata.updated_by=current_user.id
    audit(db,current_user,certificate.id,"REPLACE" if old else "UPLOAD",certificate.title)
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
    if data.verification_status not in {"Pending", "Verified", "Rejected", "Correction Required"}:
        raise HTTPException(status_code=400, detail="verification_status must be Pending, Verified, Rejected, or Correction Required")
    certificate = db.query(EmployeeCertificate).filter(EmployeeCertificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    from app.api.v1.document_vault import records, audit
    if not records(db,current_user).filter(EmployeeCertificate.id==certificate_id).first(): raise HTTPException(404,"Certificate not found")
    if data.verification_status in {"Rejected", "Correction Required"} and not (data.verification_notes or "").strip(): raise HTTPException(422,"A reason is required for rejection or correction")
    audit(db,current_user,certificate_id,"VERIFY",data.verification_status)
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
    process_metadata: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("employee_update")),
):
    if employee_id and not db.query(Employee.id).filter(Employee.id==employee_id).first():
        raise HTTPException(404,'Employee not found')
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
    if process_metadata:
        from app.api.v1.document_vault import process_import
        file.file.seek(0)
        process_import(db,current_user,batch,file.file.read(),file.filename or "")
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
    if employee_id and not db.query(Employee.id).filter(Employee.id==employee_id).first():
        raise HTTPException(404,'Employee not found')
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
    from app.api.v1.document_vault import employees
    from sqlalchemy import or_
    query = db.query(CertificateImportExportBatch).filter(or_(CertificateImportExportBatch.employee_id.in_(employees(db,current_user).with_entities(Employee.id).subquery().select()), (CertificateImportExportBatch.employee_id.is_(None)) & CertificateImportExportBatch.requested_by.in_(db.query(User.id).filter(User.id==current_user.id))))
    if operation_type:
        query = query.filter(CertificateImportExportBatch.operation_type == operation_type)
    if employee_id:
        query = query.filter(CertificateImportExportBatch.employee_id == employee_id)
    return query.order_by(CertificateImportExportBatch.requested_at.desc()).limit(200).all()
