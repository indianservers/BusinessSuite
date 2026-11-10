"""Employee document vault over existing certificates, policies and notifications."""

from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from uuid import uuid4
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, func
from app.core.deps import get_db, get_current_user, RequirePermission
from app.core.masking import user_has_permission
from app.apps.srm.services.commercial import tenant
from app.models.employee import Employee
from app.models.document import EmployeeCertificate, CertificateImportExportBatch
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.shared.models import ServicePolicy
from app.services.metrics.queries import employee_records
from app.schemas.document import EmployeeCertificateSchema

router = APIRouter(prefix="/certificates", tags=["Employee document vault"])


def employees(db, user):
    query = employee_records(db, user)
    if not user_has_permission(user, "employee_update"):
        query = query.filter(Employee.user_id == user.id)
    return query


def records(db, user):
    return db.query(EmployeeCertificate).filter(
        EmployeeCertificate.employee_id.in_(
            employees(db, user).with_entities(Employee.id).subquery().select()
        )
    )


def policies(db, user):
    return db.query(ServicePolicy).filter(
        ServicePolicy.organization_id == tenant(user),
        ServicePolicy.module_key == "hrms",
        ServicePolicy.kind == "document_requirement",
    )


class Requirement(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    certificate_type: str = Field(min_length=1, max_length=100)
    department_id: int | None = None
    designation_id: int | None = None
    branch_id: int | None = None
    employment_type: str = Field(default="", max_length=80)
    employee_category: str = Field(default="", max_length=80)
    mandatory: bool = True
    verification_required: bool = True
    expiry_required: bool = False
    reminder_days: int = Field(default=30, ge=0, le=365)
    reminders_enabled: bool = False
    active: bool = True
    version: int | None = None


def applies(rule, employee):
    return all(
        not rule.get(key) or rule[key] == getattr(employee, key)
        for key in ("department_id", "designation_id", "branch_id", "employment_type")
    ) and (
        not rule.get("employee_category")
        or rule["employee_category"] == employee.category
    )


def missing_for(db, user):
    rules = [
        r.values_json
        for r in policies(db, user).all()
        if r.values_json.get("active", True) and r.values_json.get("mandatory", True)
    ]
    result = {}
    if not rules:
        return result
    certificates = records(db, user).all()
    submitted = {}
    for cert in certificates:
        submitted.setdefault(cert.employee_id, []).append(cert)
    for employee in employees(db, user).all():
        missing = [
            r
            for r in rules
            if applies(r, employee)
            and not any(
                c.certificate_type.casefold() == r["certificate_type"].casefold()
                and c.verification_status not in {"Rejected", "Correction Required"}
                and (not c.expiry_date or c.expiry_date >= date.today())
                and (not r.get("expiry_required") or c.expiry_date)
                and (
                    not r.get("verification_required")
                    or c.verification_status == "Verified"
                )
                for c in submitted.get(employee.id, [])
            )
        ]
        if missing:
            result[employee.id] = missing
    return result


def employee_out(e):
    return dict(
        id=e.id,
        name=" ".join(filter(None, [e.first_name, e.last_name])),
        code=e.employee_id,
        department=e.department.name if e.department else "Unassigned",
        designation=e.designation.name if e.designation else "",
        email=e.work_email or e.personal_email,
        photo=e.profile_photo_url,
    )


def audit(db, user, identity, action, description):
    db.add(
        AuditLog(
            organization_id=tenant(user),
            user_id=user.id,
            method="POST",
            entity_type="employee_certificate",
            entity_id=identity,
            action=action,
            description=description,
            module="hrms",
        )
    )


@router.get("/requirements")
def requirements(db=Depends(get_db), user=Depends(get_current_user)):
    return [
        {"id": r.id, "version": r.version, **r.values_json}
        for r in policies(db, user).order_by(ServicePolicy.id).all()
    ]


@router.post("/requirements")
def save_requirement(
    data: Requirement,
    identity: int | None = None,
    db=Depends(get_db),
    user=Depends(RequirePermission("company_manage")),
):
    from app.models.company import Branch, Department, Designation

    for key, model in (
        ("branch_id", Branch),
        ("department_id", Department),
        ("designation_id", Designation),
    ):
        value = getattr(data, key)
        if value:
            q = db.query(model).filter(model.id == value)
            if model is Branch:
                q = q.filter(Branch.company_id == tenant(user))
            elif model is Department:
                q = q.join(Branch).filter(Branch.company_id == tenant(user))
            else:
                q = (
                    q.join(Department)
                    .join(Branch)
                    .filter(Branch.company_id == tenant(user))
                )
            if not q.first():
                raise HTTPException(404, "Requirement scope not found")
    row = (
        policies(db, user)
        .filter(ServicePolicy.id == identity)
        .with_for_update()
        .first()
        if identity
        else None
    )
    if identity and not row:
        raise HTTPException(404, "Requirement not found")
    if row and row.version != data.version:
        raise HTTPException(409, "Requirement changed; reload before editing")
    if not row:
        row = ServicePolicy(
            scope_key=f"document-requirement:{tenant(user)}:{uuid4().hex}",
            organization_id=tenant(user),
            module_key="hrms",
            kind="document_requirement",
            updated_by=user.id,
        )
        db.add(row)
    else:
        row.version += 1
    row.values_json = data.model_dump(exclude={"version"})
    row.updated_by = user.id
    audit(db, user, None, "REQUIREMENT_SAVED", data.title)
    db.commit()
    return {"id": row.id, "version": row.version, **row.values_json}


@router.get("/insights")
def insights(
    employee_id: int | None = None, db=Depends(get_db), user=Depends(get_current_user)
):
    q = records(db, user)
    eq = employees(db, user)
    if employee_id:
        q = q.filter(EmployeeCertificate.employee_id == employee_id)
        eq = eq.filter(Employee.id == employee_id)
    today = date.today()
    missing = missing_for(db, user)
    rules = [
        r.values_json
        for r in policies(db, user).all()
        if r.values_json.get("active", True) and r.values_json.get("mandatory", True)
    ]
    required_count = sum(sum(applies(r, e) for r in rules) for e in eq.all())
    if employee_id:
        missing = {k: v for k, v in missing.items() if k == employee_id}
    return dict(
        required_documents=required_count,
        employees=eq.count(),
        documents=q.count(),
        verified=q.filter(
            EmployeeCertificate.verification_status == "Verified"
        ).count(),
        pending=q.filter(EmployeeCertificate.verification_status == "Pending").count(),
        expired=q.filter(EmployeeCertificate.expiry_date < today).count(),
        expiring=q.filter(
            EmployeeCertificate.expiry_date >= today,
            EmployeeCertificate.expiry_date <= today + timedelta(days=30),
        ).count(),
        missing=len(missing),
        missing_documents=sum(map(len, missing.values())),
        missing_employees=[
            {**employee_out(e), "requirements": missing[e.id]}
            for e in eq.filter(Employee.id.in_(list(missing))).limit(100).all()
        ],
    )


@router.get("/library")
def library(
    employee_id: int | None = None,
    q: str = Query(default="", max_length=150),
    department_id: int | None = None,
    designation_id: int | None = None,
    branch_id: int | None = None,
    category: str | None = None,
    verification_status: str | None = None,
    upload_from: date | None = None,
    upload_to: date | None = None,
    expiry_from: date | None = None,
    expiry_to: date | None = None,
    mandatory: bool | None = None,
    sort: str = "uploaded_at",
    descending: bool = True,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    query = records(db, user).join(
        Employee, Employee.id == EmployeeCertificate.employee_id
    )
    for key, value in (
        ("employee_id", employee_id),
        ("department_id", department_id),
        ("designation_id", designation_id),
        ("branch_id", branch_id),
    ):
        if value:
            query = query.filter(
                (
                    EmployeeCertificate.employee_id
                    if key == "employee_id"
                    else getattr(Employee, key)
                )
                == value
            )
    if q:
        pattern = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(
            or_(
                *[
                    col.ilike(pattern, escape="\\")
                    for col in (
                        Employee.first_name,
                        Employee.last_name,
                        Employee.employee_id,
                        EmployeeCertificate.title,
                        EmployeeCertificate.certificate_type,
                        EmployeeCertificate.certificate_number,
                    )
                ]
            )
        )
    if category:
        query = query.filter(EmployeeCertificate.category == category)
    if verification_status == "Expired":
        query = query.filter(EmployeeCertificate.expiry_date < date.today())
    elif verification_status == "Expiring Soon":
        query = query.filter(
            EmployeeCertificate.expiry_date >= date.today(),
            EmployeeCertificate.expiry_date <= date.today() + timedelta(days=30),
        )
    elif verification_status:
        query = query.filter(
            EmployeeCertificate.verification_status == verification_status
        )
    for value, col, lower in (
        (upload_from, EmployeeCertificate.uploaded_at, True),
        (upload_to, EmployeeCertificate.uploaded_at, False),
        (expiry_from, EmployeeCertificate.expiry_date, True),
        (expiry_to, EmployeeCertificate.expiry_date, False),
    ):
        if value:
            query = query.filter(
                col >= value
                if lower
                else (
                    col < value + timedelta(days=1)
                    if col is EmployeeCertificate.uploaded_at
                    else col <= value
                )
            )
    rules = [
        r.values_json
        for r in policies(db, user).all()
        if r.values_json.get("active", True) and r.values_json.get("mandatory", True)
    ]
    if mandatory is not None:
        matches = [
            c.id
            for c in query.all()
            if any(
                applies(r, c.employee)
                and r["certificate_type"].casefold() == c.certificate_type.casefold()
                for r in rules
            )
        ]
        query = query.filter(
            EmployeeCertificate.id.in_(matches)
            if mandatory
            else ~EmployeeCertificate.id.in_(matches)
        )
    total = query.count()
    col = (
        getattr(EmployeeCertificate, sort, None)
        if sort
        in {
            "title",
            "category",
            "issue_date",
            "expiry_date",
            "uploaded_at",
            "verification_status",
        }
        else EmployeeCertificate.uploaded_at
    )
    rows = (
        query.order_by(
            col.desc() if descending else col.asc(), EmployeeCertificate.id.desc()
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    metadata = {
        int(row.scope_key.rsplit(":", 1)[-1]): row.values_json
        for row in db.query(ServicePolicy)
        .filter(
            ServicePolicy.organization_id == tenant(user),
            ServicePolicy.kind == "certificate_metadata",
            ServicePolicy.scope_key.in_([f"certificate-metadata:{c.id}" for c in rows]),
        )
        .all()
    }
    return {
        "total": total,
        "items": [
            {
                **EmployeeCertificateSchema.model_validate(c).model_dump(),
                "employee": employee_out(c.employee),
                **metadata.get(c.id, {}),
            }
            for c in rows
        ],
    }


@router.get("/{identity}/file")
def certificate_file(identity: int, db=Depends(get_db), user=Depends(get_current_user)):
    from app.core.storage import private_attachment_response
    from app.core.config import settings

    row = records(db, user).filter(EmployeeCertificate.id == identity).first()
    if not row:
        raise HTTPException(404, "Document not found")
    root = Path(settings.UPLOAD_DIR).resolve()
    path = (root / row.file_url.removeprefix("/uploads/")).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(404, "Document not found")
    return private_attachment_response(
        path,
        db=db,
        filename=row.original_filename or "document",
        media_type=row.content_type or "application/octet-stream",
    )


class Reminder(BaseModel):
    employee_id: int
    message: str = Field(
        default="Please review and complete your employee documents.",
        min_length=5,
        max_length=1000,
    )


@router.post("/reminders")
def remind(
    data: Reminder,
    db=Depends(get_db),
    user=Depends(RequirePermission("employee_update")),
):
    employee = employees(db, user).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(404, "Employee not found")
    if not employee.user_id:
        raise HTTPException(
            422, "This employee needs a linked user account to receive in-app reminders"
        )
    from hashlib import sha256
    from app.shared.models import ServiceEvent
    from app.schemas.notification import NotificationCreate
    from app.services.notifications import NotificationService
    from sqlalchemy.exc import IntegrityError
    from app.services.metrics.queries import business_day

    key = f"document-reminder:{employee.id}:{business_day(db,user)}:{sha256(data.message.encode()).hexdigest()[:20]}"
    existing = (
        db.query(ServiceEvent)
        .filter_by(organization_id=tenant(user), request_key=key)
        .first()
    )
    if existing:
        return {"id": existing.id, "duplicate": True}
    try:
        with db.begin_nested():
            event = ServiceEvent(
                organization_id=tenant(user),
                module_key="hrms",
                event_type="document_reminder",
                entity_type="employee",
                entity_id=employee.id,
                actor_id=user.id,
                request_key=key,
                payload_json={},
                status="completed",
            )
            db.add(event)
            db.flush()
            row = NotificationService.create_notification(
                db,
                NotificationCreate(
                    company_id=tenant(user),
                    user_id=employee.user_id,
                    module="hrms",
                    event_type="document_reminder",
                    title="Employee document reminder",
                    message=data.message,
                    action_url="/hrms/documents",
                    channels=["in_app"],
                ),
                commit=False,
            )
            audit(db, user, employee.id, "REMINDER", "Document reminder sent")
    except IntegrityError:
        return {"duplicate": True}
    db.commit()
    return {"id": row.id, "duplicate": False}


class BulkFiles(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=50)


@router.post("/download-bulk")
def bulk_download(
    data: BulkFiles,
    db=Depends(get_db),
    user=Depends(RequirePermission("employee_update")),
):
    from io import BytesIO
    from zipfile import ZipFile, ZIP_DEFLATED
    from fastapi.responses import Response
    from app.core.config import settings
    from app.core.storage import materialize_file

    rows = records(db, user).filter(EmployeeCertificate.id.in_(set(data.ids))).all()
    if len(rows) != len(set(data.ids)):
        raise HTTPException(404, "One or more documents are unavailable")
    if sum(r.file_size_bytes or 0 for r in rows) > 100 * 1024 * 1024:
        raise HTTPException(
            413, "Select fewer documents; bulk downloads are limited to 100 MB"
        )
    output = BytesIO()
    root = Path(settings.UPLOAD_DIR).resolve()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for row in rows:
            path = (root / row.file_url.removeprefix("/uploads/")).resolve()
            if not path.is_relative_to(root):
                raise HTTPException(404, "Document not found")
            local = materialize_file(str(path), db=db)
            archive.write(
                local, f"{row.id}-{Path(row.original_filename or 'document').name}"
            )
    audit(
        db, user, None, "BULK_DOWNLOAD", f"Downloaded {len(rows)} authorized documents"
    )
    db.commit()
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=employee-documents.zip",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/metadata-export")
def export_metadata(
    data=Depends(library), user=Depends(RequirePermission("reports_view"))
):
    # Permission checks remain on the export endpoint, independent of the grid.
    return data


def process_import(db, user, batch, content, filename):
    """Update existing certificate metadata; binary uploads stay a separate operation."""
    import csv
    from io import StringIO, BytesIO

    errors = []
    success = 0
    seen = set()
    try:
        if filename.lower().endswith(".csv"):
            rows = list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))
        elif filename.lower().endswith(".xlsx"):
            from openpyxl import load_workbook

            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            try:
                values = iter(workbook.active.values)
                headers = [str(v or "") for v in next(values)]
                rows = [dict(zip(headers, r)) for r in values]
            finally:
                workbook.close()
        else:
            raise ValueError("Use CSV or XLSX for metadata processing")
        if len(rows) > 5000:
            raise ValueError("Import at most 5,000 records at a time")
        batch.total_records = len(rows)
        for index, row in enumerate(rows, 2):
            try:
                identity = int(row.get("certificate_id") or row.get("record_id") or 0)
                cert = (
                    records(db, user).filter(EmployeeCertificate.id == identity).first()
                )
                if not cert:
                    raise ValueError(
                        "Use the record ID of an existing authorized document; upload binary documents separately"
                    )
                if batch.employee_id and cert.employee_id != batch.employee_id:
                    raise ValueError("Document belongs to a different employee")
                if identity in seen:
                    raise ValueError("Duplicate document record in this import")
                seen.add(identity)
                changes = {}
                for key in (
                    "title",
                    "category",
                    "certificate_type",
                    "certificate_number",
                    "issuing_entity",
                    "issue_date",
                    "expiry_date",
                ):
                    value = row.get(key)
                    if value is None or str(value).strip() == "":
                        continue
                    if key.endswith("_date"):
                        if isinstance(value, datetime):
                            value = value.date()
                        elif not isinstance(value, date):
                            value = date.fromisoformat(str(value))
                    else:
                        value = str(value).strip()
                        if (
                            len(value)
                            > {
                                "title": 250,
                                "category": 50,
                                "certificate_type": 100,
                                "certificate_number": 120,
                                "issuing_entity": 250,
                            }[key]
                        ):
                            raise ValueError(f"{key} is too long")
                    changes[key] = value
                issue = changes.get("issue_date", cert.issue_date)
                expiry = changes.get("expiry_date", cert.expiry_date)
                if issue and expiry and expiry < issue:
                    raise ValueError("Expiry date precedes issue date")
                reference = changes.get("certificate_number", cert.certificate_number)
                if (
                    reference
                    and records(db, user)
                    .filter(
                        EmployeeCertificate.employee_id == cert.employee_id,
                        EmployeeCertificate.certificate_number == reference,
                        EmployeeCertificate.certificate_type
                        == changes.get("certificate_type", cert.certificate_type),
                        EmployeeCertificate.id != cert.id,
                    )
                    .first()
                ):
                    raise ValueError(
                        "Certificate reference already exists for this employee"
                    )
                if changes:
                    db.add(
                        ServicePolicy(
                            scope_key=f"certificate-revision:{cert.id}:{uuid4().hex}",
                            organization_id=tenant(user),
                            module_key="hrms",
                            kind="certificate_revision",
                            updated_by=user.id,
                            values_json=EmployeeCertificateSchema.model_validate(
                                cert
                            ).model_dump(mode="json"),
                        )
                    )
                for key, value in changes.items():
                    setattr(cert, key, value)
                cert.verification_status = "Pending"
                cert.verified_at = None
                cert.verified_by_user_id = None
                cert.verifier_name = cert.verifier_company = (
                    cert.verifier_designation
                ) = cert.verifier_contact = None
                audit(
                    db,
                    user,
                    cert.id,
                    "METADATA_IMPORT",
                    f"Metadata imported from batch row {index}",
                )
                success += 1
            except (ValueError, TypeError) as error:
                errors.append({"row": index, "error": str(error)})
        batch.status = "Completed"
        batch.success_count = success
        batch.failure_count = len(errors)
    except Exception as error:
        batch.status = "Failed"
        batch.failure_count = 1
        errors = [{"row": 0, "error": str(error)}]
    batch.completed_at = datetime.now(timezone.utc)
    db.flush()
    db.add(
        ServicePolicy(
            scope_key=f"certificate-import-result:{batch.id}",
            organization_id=tenant(user),
            module_key="hrms",
            kind="certificate_import_result",
            updated_by=user.id,
            values_json={"errors": errors},
        )
    )


@router.get("/imports/{identity}/report")
def import_report(
    identity: int,
    db=Depends(get_db),
    user=Depends(RequirePermission("employee_update")),
):
    row = (
        db.query(ServicePolicy)
        .filter(
            ServicePolicy.scope_key == f"certificate-import-result:{identity}",
            ServicePolicy.organization_id == tenant(user),
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Import result not found")
    return row.values_json


@router.get("/{identity}/revisions")
def revisions(identity: int, db=Depends(get_db), user=Depends(get_current_user)):
    if not records(db, user).filter(EmployeeCertificate.id == identity).first():
        raise HTTPException(404, "Document not found")
    rows = (
        db.query(ServicePolicy)
        .filter(
            ServicePolicy.organization_id == tenant(user),
            ServicePolicy.kind == "certificate_revision",
            ServicePolicy.scope_key.like(f"certificate-revision:{identity}:%"),
        )
        .order_by(ServicePolicy.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "saved_at": row.updated_at,
            "title": row.values_json.get("title"),
            "verification_status": row.values_json.get("verification_status"),
            "original_filename": row.values_json.get("original_filename"),
        }
        for row in rows
    ]


@router.get("/{identity}/revisions/{revision_id}/file")
def revision_file(
    identity: int, revision_id: int, db=Depends(get_db), user=Depends(get_current_user)
):
    from app.core.storage import private_attachment_response
    from app.core.config import settings

    if not records(db, user).filter(EmployeeCertificate.id == identity).first():
        raise HTTPException(404, "Document not found")
    row = (
        db.query(ServicePolicy)
        .filter(
            ServicePolicy.id == revision_id,
            ServicePolicy.organization_id == tenant(user),
            ServicePolicy.kind == "certificate_revision",
            ServicePolicy.scope_key.like(f"certificate-revision:{identity}:%"),
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Version not found")
    root = Path(settings.UPLOAD_DIR).resolve()
    path = (root / row.values_json["file_url"].removeprefix("/uploads/")).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(404, "Version not found")
    return private_attachment_response(
        path,
        db=db,
        filename=row.values_json.get("original_filename") or "document",
        media_type=row.values_json.get("content_type") or "application/octet-stream",
    )
