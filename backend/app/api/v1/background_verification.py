"""Background verification over existing employee, document and exit records."""
from datetime import datetime, timezone
import hashlib
import hmac
import os
import time
from typing import List, Optional, Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from app.core.deps import RequirePermission, get_db
from app.core.masking import user_has_permission
from app.models.background_verification import BackgroundVerificationCheck as Check, BackgroundVerificationConnectorEvent as Event, BackgroundVerificationRequest as Case, BackgroundVerificationVendor as Vendor
from app.models.employee import Employee, EmployeeDocument
from app.models.recruitment import Candidate
from app.models.user import User
from app.schemas.background_verification import (
    BackgroundVerificationCheckCreate, BackgroundVerificationCheckUpdate,
    BackgroundVerificationConnectorEventSchema, BackgroundVerificationConsentUpdate,
    BackgroundVerificationRequestCreate, BackgroundVerificationRequestSchema,
    BackgroundVerificationRequestUpdate, BackgroundVerificationSubmitResponse,
    BackgroundVerificationVendorCreate, BackgroundVerificationVendorSchema,
    BackgroundVerificationWebhookPayload,
)
from app.services import background_verification as service
from app.services.metrics.queries import company_id, business_day

router = APIRouter(prefix="/background-verification", tags=["Background Verification"])
view = RequirePermission("recruitment_view", "recruitment_manage")
manage = RequirePermission("recruitment_manage")


def sensitive(user):
    service.require_evidence_access(user)


def vendor_query(db, user):
    return db.query(Vendor).filter(Vendor.organization_id == company_id(user))


def check_url(value):
    if value and not (value.startswith("/uploads/") or urlsplit(value).scheme == "https"):
        raise HTTPException(422, "Evidence must be an authorized uploaded file or an HTTPS report URL")


def case_document_urls(db, row, values):
    for key in ("document_url", "report_url", "consent_url"):
        check_url(values.get(key))
        value = values.get(key)
        if value and value.startswith("/uploads/") and row.employee_id:
            # A signed URL alone must not let HR attach another employee's document.
            from app.models.document import EmployeeCertificate
            own = db.query(EmployeeDocument.id).filter_by(employee_id=row.employee_id, file_url=value).first()
            cert = db.query(EmployeeCertificate.id).filter_by(employee_id=row.employee_id, file_url=value).first()
            if not own and not cert:
                raise HTTPException(422, "Upload evidence to this employee's existing Documents section first")


def historical_date(value):
    if value is None: return datetime.now(timezone.utc)
    value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if value > datetime.now(timezone.utc): raise HTTPException(422, "Verification date cannot be in the future")
    return value


@router.get("/owners")
def owners(search: str = Query("", max_length=150), db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    from app.services.metrics.queries import registered_users
    query = registered_users(db, current_user).filter(User.is_active.is_(True))
    if search: query = query.filter(User.email.icontains(search, autoescape=True))
    return [{"id": u.id, "label": u.email} for u in query.order_by(User.email).limit(50)]


@router.get("/employees")
def employee_options(search: str = Query("", max_length=150), db: Session = Depends(get_db), current_user: User = Depends(view)):
    sensitive(current_user)
    query = service.employee_query(db, current_user)
    if search.strip():
        term = search.strip()
        query = query.filter(or_((Employee.first_name + " " + Employee.last_name).icontains(term, autoescape=True), Employee.employee_id.icontains(term, autoescape=True)))
    return [{"id": e.id, "name": f"{e.first_name} {e.last_name}".strip(), "employee_code": e.employee_id} for e in query.order_by(Employee.first_name, Employee.id).limit(50)]


@router.get("/register")
def register(population: Literal["current", "former", "all"] = "current", search: str = Query("", max_length=150),
             verification: Literal["all", "unassessed", "open", "reviewed", "overdue"] = "all",
             page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
             db: Session = Depends(get_db), current_user: User = Depends(view)):
    sensitive(current_user)
    query = service.employee_query(db, current_user)
    if population != "all":
        former = or_(Employee.status.in_(service.FORMER_STATUSES), Employee.deleted_at.is_not(None))
        query = query.filter(former if population == "former" else ~former)
    if search.strip():
        term = search.strip()
        query = query.filter(or_(Employee.employee_id.icontains(term, autoescape=True), (Employee.first_name + " " + Employee.last_name).icontains(term, autoescape=True)))
    latest_id = db.query(func.max(Case.id)).filter(Case.employee_id == Employee.id, Case.status != "Cancelled").correlate(Employee).scalar_subquery()
    query = query.outerjoin(Case, Case.id == latest_id)
    today = business_day(db, current_user)
    if verification == "unassessed": query = query.filter(Case.id.is_(None))
    if verification == "open": query = query.filter(Case.id.is_not(None), Case.reviewed_at.is_(None))
    if verification == "reviewed": query = query.filter(Case.reviewed_at.is_not(None))
    if verification == "overdue": query = query.filter(Case.reviewed_at.is_(None), Case.expected_completion_date < today)
    total = query.count()
    rows = query.add_entity(Case).order_by(Employee.first_name, Employee.id).offset((page-1)*per_page).limit(per_page).all()
    owner_ids = {c.owner_user_id for _, c in rows if c and c.owner_user_id}
    owner_names = {u.id: u.email for u in db.query(User).filter(User.id.in_(owner_ids))} if owner_ids else {}
    return {"permissions": {"manage": user_has_permission(current_user, "recruitment_manage")}, "items": [{"id": e.id, "employee_code": e.employee_id, "name": f"{e.first_name} {e.last_name}".strip(),
            "status": e.status, "date_of_joining": e.date_of_joining, "date_of_exit": e.date_of_exit,
            "verification_status": c.status if c else "Not Assessed", "overall_result": c.overall_result if c else None,
            "case_id": c.id if c else None, "due_date": c.expected_completion_date if c else None,
            "owner_user_id": c.owner_user_id if c else None, "reviewed_at": c.reviewed_at if c else None,
            "owner_name": owner_names.get(c.owner_user_id) if c else None,
            "overdue": bool(c and not c.reviewed_at and c.expected_completion_date and c.expected_completion_date < today)} for e,c in rows],
            "total": total, "page": page, "per_page": per_page}


@router.get("/employees/{employee_id}/file")
def employee_file(employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(view)):
    sensitive(current_user)
    employee = service.employee_query(db, current_user).filter(Employee.id == employee_id).first()
    if not employee: raise HTTPException(404, "Employee not found in your permitted scope")
    return service.employee_file(db, current_user, employee)


@router.post("/vendors", response_model=BackgroundVerificationVendorSchema, status_code=201)
def create_vendor(data: BackgroundVerificationVendorCreate, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    vendor = Vendor(**data.model_dump(), organization_id=company_id(current_user))
    db.add(vendor)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A vendor with this name already exists")
    db.refresh(vendor)
    return vendor


@router.get("/vendors", response_model=List[BackgroundVerificationVendorSchema])
def list_vendors(db: Session = Depends(get_db), current_user: User = Depends(view)):
    sensitive(current_user)
    return vendor_query(db, current_user).order_by(Vendor.name).all()


@router.post("/requests", response_model=BackgroundVerificationRequestSchema, status_code=201)
def create_request(data: BackgroundVerificationRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    legacy_profile = None
    if data.employee_id:
        employee = service.employee_query(db, current_user).filter(Employee.id == data.employee_id).with_for_update().first()
        if not employee: raise HTTPException(404, "Employee not found in your permitted scope")
        if db.query(Case.id).filter(Case.employee_id == data.employee_id, Case.status != "Cancelled", or_(Case.status != "Completed", Case.reviewed_at.is_(None))).first():
            raise HTTPException(409, "An open verification case already exists; continue that case")
        if not db.query(Case.id).filter(Case.employee_id == data.employee_id).first():
            legacy_profile = {"status": employee.background_verification_status, "date": str(employee.background_verification_date) if employee.background_verification_date else None, "agency": employee.background_verification_agency}
    if data.candidate_id:
        candidate = service.candidate_query(db, current_user).filter(Candidate.id == data.candidate_id).with_for_update(of=Candidate).first()
        if not candidate: raise HTTPException(404, "Candidate not found in your permitted scope")
        # Employee/candidate identity links are made by the ATS conversion workflow only.
        if data.employee_id: raise HTTPException(422, "Select an employee or candidate; use ATS conversion to link both")
        if db.query(Case.id).filter(Case.candidate_id == data.candidate_id, Case.status != "Cancelled", or_(Case.status != "Completed", Case.reviewed_at.is_(None))).first():
            raise HTTPException(409, "An open verification case already exists; continue that case")
    if data.vendor_id and not vendor_query(db, current_user).filter(Vendor.id == data.vendor_id, Vendor.status == "Active").first():
        raise HTTPException(404, "Active vendor not found in your company")
    service.validate_owner(db, current_user, data.owner_user_id)
    row = Case(**data.model_dump(exclude={"checks"}), initiated_by=current_user.id)
    row.owner_user_id = data.owner_user_id or current_user.id
    case_document_urls(db, row, data.model_dump())
    db.add(row); db.flush()
    for item in data.checks:
        values = item.model_dump()
        case_document_urls(db, row, values)
        if item.employee_document_id: values["document_url"] = service.evidence_document(db, row, item.employee_document_id).file_url
        db.add(Check(request_id=row.id, **values))
    service.record_event(db, row, current_user, "verification.created", {"purpose": row.purpose, "checks": [c.check_type for c in data.checks], "previous_profile_verification": legacy_profile})
    return service.finish_change(db, row)


@router.get("/requests", response_model=List[BackgroundVerificationRequestSchema])
def list_requests(status: Optional[str] = Query(None), candidate_id: Optional[int] = Query(None), employee_id: Optional[int] = Query(None),
                  db: Session = Depends(get_db), current_user: User = Depends(view)):
    sensitive(current_user)
    query = service.case_query(db, current_user).options(selectinload(Case.checks))
    if status: query = query.filter(Case.status == status)
    if candidate_id: query = query.filter(Case.candidate_id == candidate_id)
    if employee_id: query = query.filter(Case.employee_id == employee_id)
    return query.order_by(Case.id.desc()).limit(500).all()


@router.put("/requests/{request_id}/consent", response_model=BackgroundVerificationRequestSchema)
def capture_consent(request_id: int, data: BackgroundVerificationConsentUpdate, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    row = service.get_case(db, current_user, request_id, data.version)
    service.assert_editable(row)
    if data.consent_status not in {"Pending", "Captured", "Rejected"}: raise HTTPException(422, "Invalid consent status")
    case_document_urls(db, row, data.model_dump())
    evidence = service.evidence_document(db, row, data.employee_document_id).file_url if data.employee_document_id else data.consent_url
    if data.consent_status == "Captured" and not (evidence or row.consent_url): raise HTTPException(422, "Consent evidence is required")
    row.consent_status = data.consent_status
    row.consent_url = evidence or row.consent_url
    row.consent_captured_at = datetime.now(timezone.utc) if data.consent_status == "Captured" else None
    service.record_event(db, row, current_user, "verification.consent", {"status": data.consent_status, "employee_document_id": data.employee_document_id})
    return service.finish_change(db, row)


@router.post("/requests/{request_id}/submit", response_model=BackgroundVerificationSubmitResponse)
def submit_to_vendor(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    row = service.get_case(db, current_user, request_id)
    service.assert_editable(row)
    if row.consent_status != "Captured": raise HTTPException(422, "Capture consent before recording vendor submission")
    if not row.vendor_id or not row.checks: raise HTTPException(422, "Vendor and checks are required")
    if not row.vendor: raise HTTPException(409, "Vendor configuration is unavailable in this company")
    if row.submitted_at: return row
    row.vendor_reference = row.vendor_reference or f"{row.vendor.provider_code or 'BGV'}-{row.id:06d}"
    row.status = "Submitted"; row.vendor_status = "Manual submission recorded"
    row.submitted_at = datetime.now(timezone.utc)
    service.record_event(db, row, current_user, "verification.submitted", {"mode": "manual", "reference": row.vendor_reference})
    return service.finish_change(db, row)


@router.put("/requests/{request_id}", response_model=BackgroundVerificationRequestSchema)
def update_request(request_id: int, data: BackgroundVerificationRequestUpdate, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    row = service.get_case(db, current_user, request_id, data.version)
    service.assert_editable(row)
    case_document_urls(db, row, data.model_dump())
    values = data.model_dump(exclude_unset=True, exclude={"version"})
    service.validate_owner(db, current_user, data.owner_user_id)
    if data.status == "Cancelled" and not (data.remarks and len(data.remarks.strip()) >= 3):
        raise HTTPException(422, "Record a reason before cancelling verification")
    if data.status == "Completed":
        service.validate_closure(row, data.overall_result, data.review_notes)
        row.reviewed_at = datetime.now(timezone.utc); row.reviewed_by = current_user.id
        values["completed_at"] = historical_date(data.completed_at)
    elif "overall_result" in values:
        # Overall result is an HR closure decision, not a progress label.
        values.pop("overall_result")
    if data.status != "Completed": values.pop("completed_at", None)
    before = {key: str(getattr(row, key)) for key in values}
    for key, value in values.items(): setattr(row, key, value)
    service.record_event(db, row, current_user, "verification.reviewed" if data.status == "Completed" else "verification.updated", {"before": before, "after": data.model_dump(mode="json", exclude_unset=True, exclude={"version"})})
    return service.finish_change(db, row)


@router.post("/requests/{request_id}/checks", response_model=BackgroundVerificationRequestSchema, status_code=201)
def add_check(request_id: int, data: BackgroundVerificationCheckCreate, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    row = service.get_case(db, current_user, request_id); service.assert_editable(row)
    if not data.check_type.strip() or any(c.check_type.strip().lower() == data.check_type.strip().lower() for c in row.checks):
        raise HTTPException(409, "This verification check already exists or has no name")
    values = data.model_dump(); case_document_urls(db, row, values)
    if data.employee_document_id: values["document_url"] = service.evidence_document(db, row, data.employee_document_id).file_url
    row.checks.append(Check(**values))
    service.record_event(db, row, current_user, "verification.check_added", {"check_type": data.check_type})
    return service.finish_change(db, row)


@router.put("/checks/{check_id}", response_model=BackgroundVerificationRequestSchema)
def update_check(check_id: int, data: BackgroundVerificationCheckUpdate, db: Session = Depends(get_db), current_user: User = Depends(manage)):
    sensitive(current_user)
    ident = db.query(Check.request_id).filter(Check.id == check_id).scalar()
    row = service.get_case(db, current_user, ident, data.version)
    service.assert_editable(row)
    check = next(c for c in row.checks if c.id == check_id)
    if row.consent_status != "Captured" and data.status != "Pending": raise HTTPException(422, "Capture consent before performing checks")
    values = data.model_dump(exclude_unset=True, exclude={"version"})
    case_document_urls(db, row, values)
    if data.employee_document_id:
        values["document_url"] = service.evidence_document(db, row, data.employee_document_id).file_url
    if data.status in service.RESOLVED_CHECKS:
        if not (data.result or check.result): raise HTTPException(422, "Record a check outcome")
        if not (data.remarks or check.remarks or values.get("document_url") or check.document_url):
            raise HTTPException(422, "Record supporting evidence or verification notes")
        values["verified_at"] = historical_date(data.verified_at or check.verified_at)
        values["verified_by"] = data.verified_by or current_user.email
    else: values["verified_at"] = None
    before = {key: str(getattr(check, key)) for key in values}
    for key, value in values.items(): setattr(check, key, value)
    row.status = "Awaiting Review" if all(c.status in service.RESOLVED_CHECKS for c in row.checks) else "In Progress"
    service.record_event(db, row, current_user, "verification.check_updated", {"check_id": check.id, "before": before, "after": data.model_dump(mode="json", exclude_unset=True, exclude={"version"})})
    return service.finish_change(db, row)


@router.get("/requests/{request_id}/events", response_model=List[BackgroundVerificationConnectorEventSchema])
def list_events(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(view)):
    sensitive(current_user); service.get_case(db, current_user, request_id)
    return db.query(Event).filter(Event.request_id == request_id).order_by(Event.id.desc()).limit(500).all()


@router.post("/webhooks/{vendor_id}")
async def ingest_vendor_webhook(vendor_id: int, request: Request, db: Session = Depends(get_db)):
    # Sign '<unix-seconds>.<raw-body>' with HMAC-SHA256. Never return employee data to a callback.
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.status == "Active").first()
    ref = vendor.webhook_secret_ref if vendor else None
    secret = os.environ.get(ref.removeprefix("env:"), "") if ref and ref.startswith("env:") else ""
    stamp = request.headers.get("X-BGV-Timestamp", "")
    signature = request.headers.get("X-BGV-Signature", "").removeprefix("sha256=")
    body = await request.body()
    if len(body) > 1024 * 1024: raise HTTPException(413, "Callback exceeds 1 MB")
    if not secret or not stamp.isdecimal() or abs(time.time()-int(stamp)) > 300:
        raise HTTPException(401, "Invalid callback authentication")
    expected = hmac.new(secret.encode(), stamp.encode()+b"."+body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature): raise HTTPException(401, "Invalid callback authentication")
    try: data = BackgroundVerificationWebhookPayload.model_validate_json(body)
    except ValueError: raise HTTPException(422, "Invalid callback payload")
    row = db.query(Case).filter_by(vendor_id=vendor_id, vendor_reference=data.vendor_reference).with_for_update().first()
    if not row: raise HTTPException(404, "Verification case not found")
    digest = hashlib.sha256(body).hexdigest()
    if db.query(Event.id).filter(Event.request_id == row.id, Event.event_type == "vendor.callback", Event.payload_json["digest"].as_string() == digest).first():
        return {"received": True, "duplicate": True}
    # Closed reports are immutable; keep later vendor messages for HR to assess.
    if not row.reviewed_at and row.status != "Cancelled":
        if row.consent_status != "Captured": raise HTTPException(409, "Consent is required before processing vendor results")
        row.vendor_status = data.vendor_status or data.status
        check_url(data.report_url)
        if data.report_url and not data.report_url.startswith("https://"): raise HTTPException(422, "Vendor report must use HTTPS")
        row.report_url = data.report_url or row.report_url
        for incoming in data.checks:
            check = next((c for c in row.checks if c.check_type.lower() == incoming.check_type.lower()), None)
            if not check:
                check = Check(check_type=incoming.check_type); row.checks.append(check)
            # Vendors cannot select local employee-document IDs or HR reviewers.
            check_url(incoming.document_url)
            if incoming.document_url and not incoming.document_url.startswith("https://"): raise HTTPException(422, "Vendor evidence must use HTTPS")
            for key, value in incoming.model_dump(exclude_unset=True, exclude={"employee_document_id", "version"}).items(): setattr(check, key, value)
            if incoming.status in service.RESOLVED_CHECKS: check.verified_at = datetime.now(timezone.utc)
        row.status = "Awaiting Review" if row.checks and all(c.status in service.RESOLVED_CHECKS for c in row.checks) else "In Progress"
        row.last_synced_at = datetime.now(timezone.utc)
    service.record_event(db, row, None, "vendor.callback", {"digest": digest, "vendor_status": data.status, "vendor_outcome": data.overall_result, "payload": data.model_dump(mode="json")})
    service.finish_change(db, row)
    return {"received": True, "duplicate": False}
