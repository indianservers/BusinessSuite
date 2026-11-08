"""Employee verification projections over the existing HRMS records."""
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.employee import Employee, EmployeeDocument
from app.models.company import Branch
from app.models.recruitment import Candidate, Job
from app.models.background_verification import BackgroundVerificationRequest as Case, BackgroundVerificationConnectorEvent as Event
from app.services.metrics.queries import employee_records, company_id
from app.core.masking import user_has_permission

FORMER_STATUSES = ("Resigned", "Terminated", "Exited", "Retired", "Absconding")
RESOLVED_CHECKS = {"Completed", "Verified", "Unable to Verify", "Not Applicable"}


def employee_query(db, user):
    # Former staff removed through the legacy soft-delete action still have a
    # personnel file. Reuse the same company/branch restrictions for its archive.
    return employee_records(db, user, include_archived=True)


def candidate_query(db, user):
    query = db.query(Candidate).join(Job).outerjoin(Branch, Branch.id == Job.branch_id)
    query = query.filter(or_(Branch.company_id == company_id(user), (Job.branch_id.is_(None)) & (company_id(user) == 1)))
    grant = (getattr(user, "_suite_grants", None) or {}).get("hrms", {})
    scope = grant.get("scope", "organization")
    actor = user.employee
    if scope == "branch":
        query = query.filter(Job.branch_id == (actor.branch_id if actor else -1))
    elif scope == "department":
        query = query.filter(Job.department_id == (actor.department_id if actor else -1))
    elif scope in {"self", "own", "assigned", "team"}:
        query = query.filter(Job.hiring_manager_id == (actor.id if actor else -1))
    return query


def case_query(db, user):
    return db.query(Case).filter(or_(
        Case.employee_id.in_(employee_query(db, user).with_entities(Employee.id)),
        (Case.employee_id.is_(None)) & Case.candidate_id.in_(candidate_query(db, user).with_entities(Candidate.id)),
    ))


def get_case(db, user, ident, version=None):
    # Lock the parent for all case/check/consent mutations and duplicate submission checks.
    row = case_query(db, user).filter(Case.id == ident).populate_existing().with_for_update().first()
    if not row:
        raise HTTPException(404, "Verification case not found in your permitted scope")
    if version is not None and version != row.version:
        raise HTTPException(409, "Verification case changed; refresh before saving")
    return row


def require_evidence_access(user):
    if not user_has_permission(user, "employee_sensitive_view"):
        raise HTTPException(403, "Sensitive employee record access is required for verification evidence")


def evidence_document(db, case, ident):
    row = db.query(EmployeeDocument).filter_by(id=ident, employee_id=case.employee_id).first() if case.employee_id else None
    if not row or not row.file_url:
        raise HTTPException(422, "Choose an existing document belonging to this employee")
    return row


def validate_owner(db, user, ident):
    if ident is None:
        return
    from app.services.metrics.queries import registered_users
    from app.models.user import User
    if not registered_users(db, user).filter(User.id == ident, User.is_active.is_(True)).first():
        raise HTTPException(422, "Case owner must be an active user in this company")


def record_event(db, row, actor, kind, values):
    db.add(Event(request_id=row.id, vendor_id=row.vendor_id, event_type=kind,
                 vendor_reference=row.vendor_reference,
                 payload_json={"actor_id": actor.id if actor else None, **values}))
    row.version = (row.version or 1) + 1


def sync_employee_summary(db, employee_id):
    if not employee_id:
        return
    db.flush()
    employee = db.query(Employee).filter_by(id=employee_id).with_for_update().first()
    if not employee:
        return
    latest = db.query(Case).filter(Case.employee_id == employee_id, Case.status != "Cancelled").order_by(Case.id.desc()).first()
    if not latest:
        employee.background_verification_status = "Not Started"
        employee.background_verification_date = None
        employee.background_verification_agency = None
        return
    reviewed = latest.status == "Completed" and latest.reviewed_at is not None
    employee.background_verification_status = ("Completed" if latest.overall_result == "Clear" else "Failed" if latest.overall_result in {"Red", "Discrepancy"} else "On Hold") if reviewed else ("On Hold" if latest.status == "On Hold" else "In Progress")
    employee.background_verification_date = latest.completed_at.date() if reviewed and latest.completed_at else None
    employee.background_verification_agency = latest.vendor.name if latest.vendor else "External vendor" if latest.vendor_id else "Internal HR"


def finish_change(db, row):
    sync_employee_summary(db, row.employee_id)
    db.commit()
    db.refresh(row)
    return row


def assert_editable(row):
    if row.reviewed_at or row.status == "Cancelled":
        raise HTTPException(409, "This case is closed. Start a new verification round to retain its history")


def validate_closure(row, result, notes):
    if row.consent_status != "Captured":
        raise HTTPException(422, "Capture consent before closing verification")
    if not row.checks or any(c.status not in RESOLVED_CHECKS for c in row.checks):
        raise HTTPException(422, "Resolve every check before HR review")
    if result not in {"Clear", "Discrepancy", "Unable to Verify", "Amber", "Red"}:
        raise HTTPException(422, "Select an explicit review outcome")
    if not notes or len(notes.strip()) < 3:
        raise HTTPException(422, "Record the HR review decision and discrepancy resolution")
    if result == "Clear" and any(c.status in {"Unable to Verify", "Not Applicable"} or c.result != "Clear" for c in row.checks):
        raise HTTPException(422, "Clear requires every check to be verified with a Clear result")


def employee_file(db, user, employee):
    """No second personnel archive: project documents, checks and exit dependencies."""
    from app.models.document import EmployeeCertificate, GeneratedDocument, StudioDocument
    from app.models.exit import ExitRecord
    from app.models.asset import AssetAssignment
    from app.models.payroll import FullFinalSettlement
    from app.models.employee import EmployeeLifecycleEvent
    from app.schemas.background_verification import BackgroundVerificationRequestSchema
    from app.schemas.employee import EmployeeDocumentSchema, EmployeeEducationSchema, EmployeeExperienceSchema
    from app.schemas.exit import ExitRecordSchema, ExitChecklistItemSchema
    cases = case_query(db, user).filter(Case.employee_id == employee.id).order_by(Case.id.desc()).all()
    documents = db.query(EmployeeDocument).filter_by(employee_id=employee.id).order_by(EmployeeDocument.id.desc()).all()
    certificates = db.query(EmployeeCertificate).filter_by(employee_id=employee.id).all()
    letters = db.query(GeneratedDocument).filter_by(employee_id=employee.id).all()
    studio = db.query(StudioDocument).filter_by(recipient_type="employee", recipient_id=employee.id, organization_id=company_id(user)).all()
    can_exit = user_has_permission(user, "exit_view") or user_has_permission(user, "exit_manage")
    exits = db.query(ExitRecord).filter_by(employee_id=employee.id).order_by(ExitRecord.id.desc()).all() if can_exit else []
    latest = next((c for c in cases if c.status != "Cancelled"), None)
    missing = []
    if not latest: missing.append("Verification not assessed")
    elif not latest.reviewed_at: missing.append("Verification awaiting HR closure")
    if not documents and not certificates: missing.append("Supporting documents missing")
    former = employee.status in FORMER_STATUSES or employee.deleted_at is not None
    if former and not employee.date_of_exit: missing.append("Employee exit date missing")
    if former and can_exit and not exits: missing.append("Exit record missing")
    latest_exit = exits[0] if exits else None
    if former and latest_exit and latest_exit.status != "Completed": missing.append("Exit checklist remains open")
    can_assets = user_has_permission(user, "asset_view") or user_has_permission(user, "asset_manage")
    assets = db.query(AssetAssignment).filter_by(employee_id=employee.id, is_active=True).count() if can_assets else None
    if former and assets: missing.append("Company assets still assigned")
    if former and employee.user and employee.user.is_active: missing.append("Login still active")
    can_payroll = user_has_permission(user, "payroll_view")
    settlements = db.query(FullFinalSettlement).filter_by(employee_id=employee.id).order_by(FullFinalSettlement.id.desc()).all() if can_payroll else []
    relevant_settlements = [s for s in settlements if latest_exit and s.exit_record_id == latest_exit.id]
    if former and can_payroll and not any(s.paid_at for s in relevant_settlements): missing.append("Final settlement payment not recorded")
    if former and settlements and not relevant_settlements: missing.append("Settlement is not linked to the latest exit")
    last_day = latest_exit.last_working_date if latest_exit else employee.date_of_exit
    issued_types = [str(l.document_type or "").lower() for l in letters if not last_day or l.created_at and l.created_at.date() >= last_day] + [str(l.document_type or "").lower() for l in studio if l.status == "Issued" and (not last_day or l.issue_date >= last_day)]
    if former and not any("reliev" in t or "experience" in t for t in issued_types): missing.append("Relieving / experience letter missing")
    return {
        "permissions": {"manage": user_has_permission(user, "recruitment_manage"), "upload": user_has_permission(user, "employee_update")},
        "legacy_verification": {"status": employee.background_verification_status, "date": employee.background_verification_date, "agency": employee.background_verification_agency} if not cases else None,
        "employee": {"id": employee.id, "employee_code": employee.employee_id, "name": f"{employee.first_name} {employee.last_name}".strip(), "status": employee.status,
                     "date_of_joining": employee.date_of_joining, "date_of_exit": employee.date_of_exit, "former": former, "archived": employee.deleted_at is not None},
        "background": {"email": employee.work_email or employee.personal_email, "phone": employee.phone_number,
                       "address": employee.present_address, "branch": employee.branch.name if employee.branch else None,
                       "department": employee.department.name if employee.department else None,
                       "designation": employee.designation.name if employee.designation else None,
                       "education": [EmployeeEducationSchema.model_validate(e).model_dump(mode="json") for e in employee.educations],
                       "experience": [EmployeeExperienceSchema.model_validate(e).model_dump(mode="json") for e in employee.experiences]},
        "cases": [BackgroundVerificationRequestSchema.model_validate(c).model_dump(mode="json") for c in cases],
        "documents": [EmployeeDocumentSchema.model_validate(d).model_dump(mode="json") for d in documents],
        "certificates": [{"id": c.id, "title": c.title, "file_url": c.file_url, "verification_status": c.verification_status} for c in certificates],
        "letters": [{"id": l.id, "name": l.document_name, "type": l.document_type, "file_url": l.file_url} for l in letters],
        "studio_letters": [{"id": l.id, "name": l.title, "type": l.document_type, "status": l.status, "issue_date": l.issue_date} for l in studio],
        "exits": [{**ExitRecordSchema.model_validate(e).model_dump(mode="json"), "checklist": [ExitChecklistItemSchema.model_validate(t).model_dump(mode="json") for t in e.checklist_items]} for e in exits],
        "settlements": [{"id": s.id, "status": s.status, "paid_at": s.paid_at, "exit_record_id": s.exit_record_id} for s in settlements],
        "active_assets": assets, "login_active": bool(employee.user and employee.user.is_active),
        "restricted": {"exit": not can_exit, "payroll": not can_payroll, "assets": not can_assets},
        "missing": missing,
        "history": [{"id": h.id, "event_type": h.event_type, "event_date": h.event_date, "from_status": h.from_status, "to_status": h.to_status, "reason": h.reason} for h in db.query(EmployeeLifecycleEvent).filter_by(employee_id=employee.id).order_by(EmployeeLifecycleEvent.id.desc()).limit(100)],
    }
