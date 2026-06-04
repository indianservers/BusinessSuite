from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.lms import CertificationRenewal, LearningAssignment, LearningCertification, LearningCourse
from app.models.user import User
from app.schemas.lms import (
    CertificationRenewalCreate, CertificationRenewalSchema, CertificationRenewalUpdate,
    LearningAssignmentCreate, LearningAssignmentSchema, LearningAssignmentUpdate,
    LearningCertificationCreate, LearningCertificationSchema,
    LearningCourseCreate, LearningCourseSchema,
)

router = APIRouter(prefix="/lms", tags=["Learning"])


@router.post("/courses", response_model=LearningCourseSchema, status_code=201)
def create_course(data: LearningCourseCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    course = LearningCourse(**data.model_dump(), created_by=current_user.id)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/courses", response_model=list[LearningCourseSchema])
def list_courses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(LearningCourse).filter(LearningCourse.is_active == True).order_by(LearningCourse.title).all()


@router.post("/assignments", response_model=LearningAssignmentSchema, status_code=201)
def assign_course(data: LearningAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    assignment = LearningAssignment(**data.model_dump(), assigned_by=current_user.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.put("/assignments/{assignment_id}", response_model=LearningAssignmentSchema)
def update_assignment(assignment_id: int, data: LearningAssignmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assignment = db.query(LearningAssignment).filter(LearningAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not current_user.is_superuser and (not current_user.employee or current_user.employee.id != assignment.employee_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    assignment.status = data.status
    assignment.score = data.score
    if data.status == "Completed":
        assignment.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/assignments/{assignment_id}/completion-callback")
def completion_callback_placeholder(
    assignment_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    assignment = db.query(LearningAssignment).filter(LearningAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    status = payload.get("status") or payload.get("completion_status") or "Completed"
    assignment.status = "Completed" if str(status).lower() in {"completed", "passed"} else str(status)
    if payload.get("score") is not None:
        assignment.score = payload.get("score")
    if assignment.status == "Completed":
        assignment.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "accepted", "assignment_id": assignment.id, "completion_status": assignment.status}


@router.get("/assignments", response_model=list[LearningAssignmentSchema])
def list_assignments(employee_id: int | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(LearningAssignment)
    if employee_id:
        query = query.filter(LearningAssignment.employee_id == employee_id)
    elif current_user.employee and not current_user.is_superuser:
        query = query.filter(LearningAssignment.employee_id == current_user.employee.id)
    return query.order_by(LearningAssignment.id.desc()).limit(200).all()


@router.post("/certifications", response_model=LearningCertificationSchema, status_code=201)
def create_certification(data: LearningCertificationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    payload = data.model_dump()
    if payload.get("renewal_required") and not payload.get("renewal_due_on") and payload.get("expires_on"):
        payload["renewal_due_on"] = payload["expires_on"]
    if payload.get("renewal_required"):
        payload["renewal_status"] = "Due"
    cert = LearningCertification(**payload, verified_by=current_user.id)
    db.add(cert)
    db.flush()
    if cert.renewal_required and cert.renewal_due_on:
        db.add(CertificationRenewal(
            certification_id=cert.id,
            employee_id=cert.employee_id,
            due_on=cert.renewal_due_on,
            status="Due",
        ))
    db.commit()
    db.refresh(cert)
    return cert


@router.get("/certifications", response_model=list[LearningCertificationSchema])
def list_certifications(employee_id: int | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(LearningCertification)
    if employee_id:
        query = query.filter(LearningCertification.employee_id == employee_id)
    elif current_user.employee and not current_user.is_superuser:
        query = query.filter(LearningCertification.employee_id == current_user.employee.id)
    return query.order_by(LearningCertification.expires_on.asc().nullslast()).limit(200).all()


@router.post("/certification-renewals", response_model=CertificationRenewalSchema, status_code=201)
def create_certification_renewal(
    data: CertificationRenewalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_manage")),
):
    cert = db.query(LearningCertification).filter(LearningCertification.id == data.certification_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    renewal = CertificationRenewal(
        certification_id=cert.id,
        employee_id=cert.employee_id,
        due_on=data.due_on or cert.renewal_due_on or cert.expires_on,
        notes=data.notes,
    )
    if not renewal.due_on:
        raise HTTPException(status_code=400, detail="Renewal due date is required")
    cert.renewal_required = True
    cert.renewal_due_on = renewal.due_on
    cert.renewal_status = "Due"
    db.add(renewal)
    db.commit()
    db.refresh(renewal)
    return renewal


@router.get("/certification-renewals", response_model=list[CertificationRenewalSchema])
def list_certification_renewals(
    employee_id: int | None = Query(None),
    due_within_days: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CertificationRenewal)
    if employee_id:
        query = query.filter(CertificationRenewal.employee_id == employee_id)
    elif current_user.employee and not current_user.is_superuser:
        query = query.filter(CertificationRenewal.employee_id == current_user.employee.id)
    if due_within_days is not None:
        today = datetime.now(timezone.utc).date()
        query = query.filter(CertificationRenewal.due_on <= today + timedelta(days=due_within_days))
    return query.order_by(CertificationRenewal.due_on.asc()).limit(200).all()


@router.put("/certification-renewals/{renewal_id}", response_model=CertificationRenewalSchema)
def update_certification_renewal(
    renewal_id: int,
    data: CertificationRenewalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    renewal = db.query(CertificationRenewal).filter(CertificationRenewal.id == renewal_id).first()
    if not renewal:
        raise HTTPException(status_code=404, detail="Certification renewal not found")
    if not current_user.is_superuser and (not current_user.employee or current_user.employee.id != renewal.employee_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    renewal.status = data.status
    renewal.evidence_url = data.evidence_url
    renewal.notes = data.notes
    if data.status == "Completed":
        renewal.completed_at = datetime.now(timezone.utc)
        cert = db.query(LearningCertification).filter(LearningCertification.id == renewal.certification_id).first()
        if cert:
            cert.renewal_status = "Completed"
            cert.status = "Active"
    db.commit()
    db.refresh(renewal)
    return renewal


@router.post("/certification-renewals/reminders")
def mark_certification_renewal_reminders(
    due_within_days: int = Query(30),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_manage")),
):
    today = datetime.now(timezone.utc).date()
    renewals = db.query(CertificationRenewal).filter(
        CertificationRenewal.status.in_(["Due", "Reminder Sent"]),
        CertificationRenewal.due_on <= today + timedelta(days=due_within_days),
    ).all()
    now = datetime.now(timezone.utc)
    for renewal in renewals:
        renewal.status = "Reminder Sent"
        renewal.reminder_sent_at = now
    db.commit()
    return {"reminders_marked": len(renewals), "due_within_days": due_within_days}
