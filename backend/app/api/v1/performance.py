from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.core.deps import get_db, get_current_user, RequirePermission
from app.models.user import User
from app.models.employee import Employee
from app.models.performance import (
    AppraisalCycle, CompensationCycle, Competency, EmployeeCompetencyAssessment,
    CalibrationParticipant, CalibrationSession, CompensationWorksheetRow,
    CriticalRole, Feedback360Request, GoalCheckIn, MeritRecommendation, OneOnOneRecord, PayBand, PerformanceGoal,
    PerformanceRatingCriteria, PerformanceReview, ReviewTemplate, ReviewTemplateQuestion,
    RoleSkillRequirement, SuccessionCandidate,
)
from app.models.payroll import EmployeeSalary
from app.schemas.performance import (
    AppraisalCycleCreate, AppraisalCycleSchema,
    CalibrationSessionCreate, CalibrationSessionSchema, CalibrationSessionUpdate,
    CompensationWorksheetRowCreate, CompensationWorksheetRowSchema, CompensationWorksheetRowUpdate,
    CompensationCycleCreate, CompensationCycleSchema, CompetencyCreate, CompetencySchema,
    CriticalRoleCreate, CriticalRoleSchema,
    EmployeeCompetencyAssessmentCreate, EmployeeCompetencyAssessmentSchema,
    Feedback360RequestCreate, Feedback360RequestSchema, Feedback360Submit,
    GoalCheckInCreate, GoalCheckInSchema, MeritRecommendationCreate,
    MeritRecommendationReview, MeritRecommendationSchema, OneOnOneRecordCreate, OneOnOneRecordSchema,
    PayBandCreate, PayBandSchema,
    PerformanceGoalCreate, PerformanceGoalUpdate, PerformanceGoalSchema,
    PerformanceReviewCreate, PerformanceReviewSchema, ReviewTemplateCreate,
    ReviewTemplateSchema, RoleSkillRequirementCreate, RoleSkillRequirementSchema,
    SuccessionCandidateCreate, SuccessionCandidateSchema,
)

router = APIRouter(prefix="/performance", tags=["Performance Management"])


def _permissions(user: User) -> set[str]:
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def _role_name(user: User) -> str:
    return (user.role.name if user.role else "").lower().replace(" ", "_")


def _is_hr_admin(user: User) -> bool:
    return user.is_superuser or "hr_admin" in _permissions(user) or "performance_manage" in _permissions(user) or _role_name(user) in {
        "admin",
        "super_admin",
        "hr",
        "hr_admin",
        "hr_manager",
    }


def _ensure_hr_admin(user: User) -> None:
    if not _is_hr_admin(user):
        raise HTTPException(status_code=403, detail="HR admin access required")


def _has_permission(user: User, permission: str) -> bool:
    return user.is_superuser or permission in _permissions(user)


def _ensure_compensation_access(user: User) -> None:
    if not (
        _is_hr_admin(user)
        or _has_permission(user, "payroll_run")
        or _has_permission(user, "payroll_approve")
    ):
        raise HTTPException(status_code=403, detail="Compensation access required")


def _employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _cycle_or_404(db: Session, cycle_id: int) -> AppraisalCycle:
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Performance cycle not found")
    return cycle


def _cycle_status(cycle: AppraisalCycle) -> str:
    status = (cycle.status or "").strip().lower().replace(" ", "_")
    if status in {"upcoming", "draft"}:
        return "draft"
    if status in {"self_review", "manager_review", "calibration", "active"}:
        return "active"
    if status in {"completed", "closed"}:
        return "closed"
    return status or "draft"


def _require_active_cycle(cycle: AppraisalCycle) -> None:
    if _cycle_status(cycle) != "active":
        raise HTTPException(status_code=400, detail="Reviews can only be submitted while the cycle is active")


def _can_manage_employee(user: User, employee: Employee) -> bool:
    if _is_hr_admin(user):
        return True
    return bool(user.employee and employee.reporting_manager_id == user.employee.id)


def _can_write_goal(user: User, employee: Employee) -> bool:
    return bool(user.employee and employee.id == user.employee.id) or _can_manage_employee(user, employee)


def _latest_ctc(db: Session, employee_id: int) -> Decimal:
    row = (
        db.query(EmployeeSalary)
        .filter(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_active == True)
        .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
        .first()
    )
    return Decimal(row.ctc or 0) if row else Decimal("0")


def _nine_box_cell(performance_rating: Decimal | int | float | None, potential_rating: Decimal | int | float | None) -> str:
    perf = float(performance_rating or 0)
    pot = float(potential_rating or 0)
    perf_band = "Low" if perf < 3 else "Medium" if perf < 4 else "High"
    pot_band = "Low" if pot < 3 else "Medium" if pot < 4 else "High"
    labels = {
        ("High", "High"): "Star",
        ("High", "Medium"): "High Performer",
        ("High", "Low"): "Trusted Professional",
        ("Medium", "High"): "Growth Talent",
        ("Medium", "Medium"): "Core Contributor",
        ("Medium", "Low"): "Solid Contributor",
        ("Low", "High"): "Potential Mismatch",
        ("Low", "Medium"): "Inconsistent Performer",
        ("Low", "Low"): "Performance Risk",
    }
    return labels[(perf_band, pot_band)]


def _append_audit(session: CalibrationSession, actor_id: int | None, action: str, detail: dict) -> None:
    history = list(session.audit_json or [])
    history.append({
        "at": datetime.now(timezone.utc).isoformat(),
        "actor_user_id": actor_id,
        "action": action,
        "detail": detail,
    })
    session.audit_json = history


def _cycle_payload(data: AppraisalCycleCreate, current_user: User) -> dict:
    payload = data.model_dump(exclude_unset=True)
    start = payload.get("review_period_start") or payload.get("start_date")
    end = payload.get("review_period_end") or payload.get("end_date")
    if not start or not end:
        raise HTTPException(status_code=422, detail="review_period_start/review_period_end are required")
    payload["review_period_start"] = start
    payload["review_period_end"] = end
    payload["start_date"] = payload.get("start_date") or start
    payload["end_date"] = payload.get("end_date") or end
    payload["cycle_type"] = (payload.get("cycle_type") or "annual").lower().replace("-", "_").replace(" ", "_")
    payload["status"] = "draft"
    payload["created_by"] = current_user.id
    return payload


@router.get("/cycles", response_model=List[AppraisalCycleSchema])
def list_cycles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(AppraisalCycle).order_by(AppraisalCycle.review_period_start.desc(), AppraisalCycle.id.desc()).all()


@router.post("/cycles", response_model=AppraisalCycleSchema, status_code=201)
def create_cycle(
    data: AppraisalCycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    cycle = AppraisalCycle(**_cycle_payload(data, current_user))
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.put("/cycles/{cycle_id}/activate", response_model=AppraisalCycleSchema)
def activate_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    cycle = _cycle_or_404(db, cycle_id)
    cycle.status = "active"
    db.commit()
    db.refresh(cycle)
    return cycle


@router.put("/cycles/{cycle_id}/close", response_model=AppraisalCycleSchema)
def close_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    cycle = _cycle_or_404(db, cycle_id)
    cycle.status = "closed"
    db.commit()
    db.refresh(cycle)
    return cycle


@router.put("/cycles/{cycle_id}/status")
def update_cycle_status(
    cycle_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_hr_admin(current_user)
    cycle = _cycle_or_404(db, cycle_id)
    cycle.status = status
    db.commit()
    return {"message": f"Cycle status updated to {status}"}


# ── Goals ──────────────────────────────────────────────────────────────────────

@router.get("/goals/my", response_model=List[PerformanceGoalSchema])
@router.get("/goals", response_model=List[PerformanceGoalSchema])
def list_my_goals(
    cycle_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    q = db.query(PerformanceGoal).filter(PerformanceGoal.employee_id == current_user.employee.id)
    if cycle_id:
        q = q.filter(PerformanceGoal.cycle_id == cycle_id)
    return q.all()


@router.post("/goals", response_model=PerformanceGoalSchema, status_code=201)
def create_goal(
    data: PerformanceGoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    payload = data.model_dump(exclude_unset=True)
    employee_id = payload.pop("employee_id", None) or current_user.employee.id
    employee = _employee_or_404(db, employee_id)
    if not _can_write_goal(current_user, employee):
        raise HTTPException(status_code=403, detail="Goals can only be created for self or direct reportees")
    _cycle_or_404(db, payload["cycle_id"])
    if payload.get("target_value") and not payload.get("target"):
        payload["target"] = payload["target_value"]
    goal = PerformanceGoal(employee_id=employee.id, set_by=current_user.id, **payload)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.put("/goals/{goal_id}", response_model=PerformanceGoalSchema)
def update_goal(
    goal_id: int,
    data: PerformanceGoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = db.query(PerformanceGoal).filter(PerformanceGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    employee = _employee_or_404(db, goal.employee_id)
    if not _can_write_goal(current_user, employee):
        raise HTTPException(status_code=403, detail="Not allowed to update this goal")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(goal, k, v)
    db.commit()
    db.refresh(goal)
    return goal


@router.put("/goals/{goal_id}/complete", response_model=PerformanceGoalSchema)
def complete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = db.query(PerformanceGoal).filter(PerformanceGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    employee = _employee_or_404(db, goal.employee_id)
    if not _can_write_goal(current_user, employee):
        raise HTTPException(status_code=403, detail="Not allowed to complete this goal")
    goal.status = "completed"
    db.commit()
    db.refresh(goal)
    return goal


# ── Reviews ───────────────────────────────────────────────────────────────────

@router.post("/reviews", response_model=PerformanceReviewSchema, status_code=201)
def submit_review(
    data: PerformanceReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    payload = data.model_dump(exclude={"rating_criteria"})
    review_type = (payload.get("review_type") or "self").lower()
    if not payload.get("employee_id"):
        payload["employee_id"] = current_user.employee.id
    employee = _employee_or_404(db, payload["employee_id"])
    if not payload.get("cycle_id"):
        cycle = db.query(AppraisalCycle).order_by(AppraisalCycle.review_period_start.desc(), AppraisalCycle.id.desc()).first()
        if not cycle:
            raise HTTPException(status_code=400, detail="Create an appraisal cycle before submitting reviews")
        payload["cycle_id"] = cycle.id
    cycle = _cycle_or_404(db, payload["cycle_id"])
    _require_active_cycle(cycle)
    if review_type == "self":
        if employee.id != current_user.employee.id:
            raise HTTPException(status_code=403, detail="Self reviews can only be submitted by the employee")
        existing = db.query(PerformanceReview).filter(
            PerformanceReview.employee_id == employee.id,
            PerformanceReview.cycle_id == cycle.id,
            func.lower(PerformanceReview.review_type) == "self",
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Self-review already submitted for this cycle")
    elif review_type == "manager":
        if employee.reporting_manager_id != current_user.employee.id:
            raise HTTPException(status_code=403, detail="Managers can only review their direct reportees")
    elif employee.id != current_user.employee.id and not _can_manage_employee(current_user, employee):
        raise HTTPException(status_code=403, detail="Not allowed to submit this review")

    payload["review_type"] = review_type
    review = PerformanceReview(
        reviewer_id=current_user.employee.id,
        status="submitted",
        submitted_at=datetime.now(timezone.utc),
        **payload,
    )
    db.add(review)
    db.flush()
    for criteria in data.rating_criteria:
        db.add(PerformanceRatingCriteria(review_id=review.id, **criteria.model_dump()))
    if review_type == "manager" and review.overall_rating is not None:
        employee.performance_rating = int(round(float(review.overall_rating)))
    db.commit()
    db.refresh(review)
    return review


@router.get("/reviews/my", response_model=List[PerformanceReviewSchema])
def my_reviews(
    cycle_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    query = (
        db.query(PerformanceReview)
        .options(joinedload(PerformanceReview.rating_criteria))
        .filter(PerformanceReview.employee_id == current_user.employee.id)
    )
    if cycle_id:
        query = query.filter(PerformanceReview.cycle_id == cycle_id)
    return query.order_by(PerformanceReview.created_at.desc(), PerformanceReview.id.desc()).all()


@router.get("/reviews/pending")
def pending_reviews(
    cycle_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    active_cycles = db.query(AppraisalCycle).filter(AppraisalCycle.status == "active")
    if cycle_id:
        active_cycles = active_cycles.filter(AppraisalCycle.id == cycle_id)
    cycle_ids = [cycle.id for cycle in active_cycles.all()]
    reportees = db.query(Employee).filter(
        Employee.reporting_manager_id == current_user.employee.id,
        Employee.deleted_at.is_(None),
    ).all()
    items = []
    for employee in reportees:
        reviewed_cycle_ids = {
            row.cycle_id
            for row in db.query(PerformanceReview.cycle_id).filter(
                PerformanceReview.employee_id == employee.id,
                PerformanceReview.cycle_id.in_(cycle_ids or [0]),
                func.lower(PerformanceReview.review_type) == "manager",
            )
        }
        for active_cycle_id in cycle_ids:
            if active_cycle_id not in reviewed_cycle_ids:
                items.append({
                    "employee_id": employee.id,
                    "employee_name": f"{employee.first_name} {employee.last_name}",
                    "cycle_id": active_cycle_id,
                    "review_type": "manager",
                })
    return items


@router.put("/reviews/{review_id}/acknowledge", response_model=PerformanceReviewSchema)
def acknowledge_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    review = (
        db.query(PerformanceReview)
        .options(joinedload(PerformanceReview.rating_criteria))
        .filter(PerformanceReview.id == review_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.employee_id != current_user.employee.id:
        raise HTTPException(status_code=403, detail="Only the reviewed employee can acknowledge this review")
    if (review.review_type or "").lower() != "manager":
        raise HTTPException(status_code=400, detail="Only manager reviews can be acknowledged")
    review.status = "acknowledged"
    review.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return review


@router.post("/calibration/sessions", response_model=CalibrationSessionSchema, status_code=201)
def create_calibration_session(
    data: CalibrationSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_manage")),
):
    _cycle_or_404(db, data.cycle_id)
    session = CalibrationSession(
        cycle_id=data.cycle_id,
        name=data.name,
        scheduled_at=data.scheduled_at,
        notes=data.notes,
        facilitator_user_id=current_user.id,
        audit_json=[],
    )
    db.add(session)
    db.flush()
    for participant in data.participants:
        _employee_or_404(db, participant.employee_id)
        db.add(CalibrationParticipant(session_id=session.id, updated_by=current_user.id, **participant.model_dump()))
    _append_audit(session, current_user.id, "created", {"participant_count": len(data.participants)})
    db.commit()
    db.refresh(session)
    return session


@router.get("/calibration/sessions", response_model=List[CalibrationSessionSchema])
def list_calibration_sessions(
    cycle_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_view")),
):
    query = db.query(CalibrationSession).options(joinedload(CalibrationSession.participants))
    if cycle_id:
        query = query.filter(CalibrationSession.cycle_id == cycle_id)
    return query.order_by(CalibrationSession.created_at.desc(), CalibrationSession.id.desc()).limit(100).all()


@router.put("/calibration/sessions/{session_id}", response_model=CalibrationSessionSchema)
def update_calibration_session(
    session_id: int,
    data: CalibrationSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_manage")),
):
    session = db.query(CalibrationSession).options(joinedload(CalibrationSession.participants)).filter(CalibrationSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Calibration session not found")
    before = {"status": session.status, "notes": session.notes}
    if data.status:
        session.status = data.status
    if data.notes is not None:
        session.notes = data.notes
    existing = {participant.employee_id: participant for participant in session.participants}
    for incoming in data.participants:
        _employee_or_404(db, incoming.employee_id)
        participant = existing.get(incoming.employee_id)
        payload = incoming.model_dump()
        if participant:
            for field, value in payload.items():
                setattr(participant, field, value)
            participant.updated_by = current_user.id
            participant.status = "Finalized" if incoming.final_rating is not None else participant.status
        else:
            db.add(CalibrationParticipant(session_id=session.id, updated_by=current_user.id, **payload))
    _append_audit(session, current_user.id, "updated", {"before": before, "status": session.status, "participant_count": len(data.participants)})
    db.commit()
    db.refresh(session)
    return session


@router.get("/nine-box")
def nine_box_grid(
    cycle_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_view")),
):
    participants = (
        db.query(CalibrationParticipant)
        .join(CalibrationSession, CalibrationSession.id == CalibrationParticipant.session_id)
        .options(joinedload(CalibrationParticipant.employee), joinedload(CalibrationParticipant.session))
    )
    if cycle_id:
        participants = participants.filter(CalibrationSession.cycle_id == cycle_id)
    rows = []
    for participant in participants.order_by(CalibrationParticipant.updated_at.desc().nullslast(), CalibrationParticipant.id.desc()).all():
        performance = participant.final_rating or participant.proposed_rating
        potential = participant.potential_rating
        rows.append({
            "employee_id": participant.employee_id,
            "employee_name": f"{participant.employee.first_name} {participant.employee.last_name}" if participant.employee else None,
            "cycle_id": participant.session.cycle_id if participant.session else None,
            "performance_rating": str(performance) if performance is not None else None,
            "potential_rating": str(potential) if potential is not None else None,
            "box": _nine_box_cell(performance, potential),
        })
    return {"items": rows, "count": len(rows)}


@router.post("/one-on-ones", response_model=OneOnOneRecordSchema, status_code=201)
def create_one_on_one(
    data: OneOnOneRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee and not _is_hr_admin(current_user):
        raise HTTPException(status_code=400, detail="No employee profile")
    employee = _employee_or_404(db, data.employee_id)
    manager_id = data.manager_id or (current_user.employee.id if current_user.employee else None)
    if not manager_id:
        raise HTTPException(status_code=400, detail="manager_id is required")
    if current_user.employee and manager_id != current_user.employee.id and not _is_hr_admin(current_user):
        raise HTTPException(status_code=403, detail="Managers can only create one-on-ones for themselves")
    if employee.reporting_manager_id != manager_id and not (current_user.employee and employee.id == current_user.employee.id) and not _is_hr_admin(current_user):
        raise HTTPException(status_code=403, detail="One-on-ones are limited to self, direct reportees, or HR")
    item = OneOnOneRecord(**data.model_dump(exclude={"manager_id"}), manager_id=manager_id, created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/one-on-ones", response_model=List[OneOnOneRecordSchema])
def list_one_on_ones(
    employee_id: Optional[int] = Query(None),
    manager_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(OneOnOneRecord)
    if employee_id:
        employee = _employee_or_404(db, employee_id)
        if not _can_manage_employee(current_user, employee) and not (current_user.employee and current_user.employee.id == employee.id):
            raise HTTPException(status_code=403, detail="Not allowed to view this employee's one-on-ones")
        query = query.filter(OneOnOneRecord.employee_id == employee_id)
    elif manager_id:
        if not _is_hr_admin(current_user) and (not current_user.employee or current_user.employee.id != manager_id):
            raise HTTPException(status_code=403, detail="Not allowed to view this manager's one-on-ones")
        query = query.filter(OneOnOneRecord.manager_id == manager_id)
    elif not _is_hr_admin(current_user):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        query = query.filter(
            (OneOnOneRecord.employee_id == current_user.employee.id) | (OneOnOneRecord.manager_id == current_user.employee.id)
        )
    return query.order_by(OneOnOneRecord.meeting_date.desc(), OneOnOneRecord.id.desc()).limit(200).all()


@router.get("/reviews/{employee_id}", response_model=List[PerformanceReviewSchema])
def get_employee_reviews(
    employee_id: int,
    cycle_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_view")),
):
    employee = _employee_or_404(db, employee_id)
    if not _can_manage_employee(current_user, employee) and not (current_user.employee and current_user.employee.id == employee.id):
        raise HTTPException(status_code=403, detail="Not allowed to view this employee's reviews")
    q = db.query(PerformanceReview).options(joinedload(PerformanceReview.rating_criteria)).filter(PerformanceReview.employee_id == employee_id)
    if cycle_id:
        q = q.filter(PerformanceReview.cycle_id == cycle_id)
    return q.all()


@router.get("/summary/{employee_id}")
def performance_summary(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = _employee_or_404(db, employee_id)
    if not _can_manage_employee(current_user, employee) and not (current_user.employee and current_user.employee.id == employee.id):
        raise HTTPException(status_code=403, detail="Not allowed to view this employee's performance summary")
    goals = (
        db.query(PerformanceGoal)
        .filter(PerformanceGoal.employee_id == employee.id)
        .order_by(PerformanceGoal.created_at.desc(), PerformanceGoal.id.desc())
        .all()
    )
    reviews = (
        db.query(PerformanceReview)
        .options(joinedload(PerformanceReview.rating_criteria), joinedload(PerformanceReview.cycle))
        .filter(PerformanceReview.employee_id == employee.id)
        .order_by(PerformanceReview.created_at.desc(), PerformanceReview.id.desc())
        .all()
    )
    return {
        "employee_id": employee.id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "latest_performance_score": employee.performance_rating,
        "goals": goals,
        "reviews": reviews,
    }


@router.post("/goals/check-ins", response_model=GoalCheckInSchema, status_code=201)
def create_goal_check_in(
    data: GoalCheckInCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    goal = db.query(PerformanceGoal).filter(PerformanceGoal.id == data.goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    if goal.employee_id != current_user.employee.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot check in for another employee goal")
    item = GoalCheckIn(employee_id=goal.employee_id, **data.model_dump())
    goal.status = "At Risk" if data.confidence == "At Risk" else goal.status
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/goals/{goal_id}/check-ins", response_model=List[GoalCheckInSchema])
def list_goal_check_ins(goal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(GoalCheckIn).filter(GoalCheckIn.goal_id == goal_id).order_by(GoalCheckIn.checked_in_at.desc()).all()


@router.post("/review-templates", response_model=ReviewTemplateSchema, status_code=201)
def create_review_template(data: ReviewTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    payload = data.model_dump(exclude={"questions"})
    template = ReviewTemplate(**payload)
    db.add(template)
    db.flush()
    for question in data.questions:
        db.add(ReviewTemplateQuestion(template_id=template.id, **question.model_dump()))
    db.commit()
    db.refresh(template)
    return template


@router.get("/review-templates", response_model=List[ReviewTemplateSchema])
def list_review_templates(template_type: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_view"))):
    query = db.query(ReviewTemplate).filter(ReviewTemplate.is_active == True)
    if template_type:
        query = query.filter(ReviewTemplate.template_type == template_type)
    return query.order_by(ReviewTemplate.name).all()


@router.post("/360/requests", response_model=Feedback360RequestSchema, status_code=201)
@router.post("/360-feedback-requests", response_model=Feedback360RequestSchema, status_code=201)
def create_360_request(data: Feedback360RequestCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    item = Feedback360Request(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/360/requests/{request_id}/submit", response_model=Feedback360RequestSchema)
@router.put("/360-feedback-requests/{request_id}/submit", response_model=Feedback360RequestSchema)
def submit_360_feedback(request_id: int, data: Feedback360Submit, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Feedback360Request).filter(Feedback360Request.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="360 feedback request not found")
    if current_user.employee and item.reviewer_id != current_user.employee.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only assigned reviewer can submit this feedback")
    item.responses_json = data.responses_json
    item.overall_rating = data.overall_rating
    item.comments = data.comments
    item.status = "Submitted"
    item.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.get("/360/requests", response_model=List[Feedback360RequestSchema])
@router.get("/360-feedback-requests", response_model=List[Feedback360RequestSchema])
def list_360_requests(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_view"))):
    query = db.query(Feedback360Request)
    if employee_id:
        query = query.filter(Feedback360Request.employee_id == employee_id)
    return query.order_by(Feedback360Request.id.desc()).limit(300).all()


@router.post("/competencies", response_model=CompetencySchema, status_code=201)
def create_competency(data: CompetencyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    if db.query(Competency).filter(Competency.code == data.code).first():
        raise HTTPException(status_code=400, detail="Competency code already exists")
    item = Competency(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/competencies", response_model=List[CompetencySchema])
def list_competencies(category: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_view"))):
    query = db.query(Competency).filter(Competency.is_active == True)
    if category:
        query = query.filter(Competency.category == category)
    return query.order_by(Competency.category, Competency.name).all()


@router.post("/role-skill-requirements", response_model=RoleSkillRequirementSchema, status_code=201)
def create_role_skill_requirement(data: RoleSkillRequirementCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    if not data.designation_id and not data.job_profile_id:
        raise HTTPException(status_code=400, detail="Either designation_id or job_profile_id is required")
    item = RoleSkillRequirement(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/competency-assessments", response_model=EmployeeCompetencyAssessmentSchema, status_code=201)
def create_competency_assessment(data: EmployeeCompetencyAssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_manage"))):
    item = EmployeeCompetencyAssessment(**data.model_dump(), assessed_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/employees/{employee_id}/skill-gap")
def employee_skill_gap(employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("performance_view"))):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    requirements = db.query(RoleSkillRequirement).filter(
        RoleSkillRequirement.is_active == True,
        (RoleSkillRequirement.designation_id == employee.designation_id) | (RoleSkillRequirement.job_profile_id == None),
    ).all()
    assessments = {
        row.competency_id: row
        for row in db.query(EmployeeCompetencyAssessment).filter(EmployeeCompetencyAssessment.employee_id == employee_id).all()
    }
    gaps = []
    for requirement in requirements:
        assessment = assessments.get(requirement.competency_id)
        current_level = assessment.assessed_level if assessment else 0
        if current_level < requirement.required_level:
            gaps.append({
                "competency_id": requirement.competency_id,
                "competency_code": requirement.competency.code if requirement.competency else None,
                "competency_name": requirement.competency.name if requirement.competency else None,
                "required_level": requirement.required_level,
                "current_level": current_level,
                "gap": requirement.required_level - current_level,
                "importance": requirement.importance,
                "recommendation": "Assign learning path or mentor review",
            })
    return {"employee_id": employee_id, "gap_count": len(gaps), "gaps": gaps}


@router.post("/succession/critical-roles", response_model=CriticalRoleSchema, status_code=201)
def create_critical_role(
    data: CriticalRoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_manage")),
):
    item = CriticalRole(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/succession/critical-roles", response_model=List[CriticalRoleSchema])
def list_critical_roles(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_view")),
):
    query = db.query(CriticalRole).options(joinedload(CriticalRole.successors))
    if active_only:
        query = query.filter(CriticalRole.is_active == True)
    return query.order_by(CriticalRole.role_name).limit(200).all()


@router.post("/succession/candidates", response_model=SuccessionCandidateSchema, status_code=201)
def create_succession_candidate(
    data: SuccessionCandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("performance_manage")),
):
    role = db.query(CriticalRole).filter(CriticalRole.id == data.critical_role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Critical role not found")
    _employee_or_404(db, data.employee_id)
    if data.mentor_employee_id:
        _employee_or_404(db, data.mentor_employee_id)
    item = SuccessionCandidate(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/compensation/cycles", response_model=CompensationCycleSchema, status_code=201)
def create_compensation_cycle(data: CompensationCycleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = CompensationCycle(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/compensation/cycles", response_model=List[CompensationCycleSchema])
def list_compensation_cycles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_compensation_access(current_user)
    return db.query(CompensationCycle).order_by(CompensationCycle.created_at.desc(), CompensationCycle.id.desc()).limit(100).all()


@router.post("/compensation/pay-bands", response_model=PayBandSchema, status_code=201)
def create_pay_band(data: PayBandCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if data.max_ctc and data.min_ctc and data.max_ctc < data.min_ctc:
        raise HTTPException(status_code=400, detail="max_ctc cannot be below min_ctc")
    item = PayBand(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/compensation/pay-bands", response_model=List[PayBandSchema])
def list_pay_bands(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_compensation_access(current_user)
    return db.query(PayBand).filter(PayBand.is_active == True).order_by(PayBand.name).all()


@router.post("/compensation/merit-recommendations", response_model=MeritRecommendationSchema, status_code=201)
def create_merit_recommendation(data: MeritRecommendationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    increase_percent = Decimal("0")
    if data.current_ctc and data.current_ctc > 0:
        increase_percent = ((data.recommended_ctc - data.current_ctc) / data.current_ctc * Decimal("100")).quantize(Decimal("0.01"))
    item = MeritRecommendation(**data.model_dump(), increase_percent=increase_percent)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/compensation/merit-recommendations", response_model=List[MeritRecommendationSchema])
def list_merit_recommendations(
    compensation_cycle_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_compensation_access(current_user)
    query = db.query(MeritRecommendation)
    if compensation_cycle_id:
        query = query.filter(MeritRecommendation.compensation_cycle_id == compensation_cycle_id)
    if employee_id:
        query = query.filter(MeritRecommendation.employee_id == employee_id)
    return query.order_by(MeritRecommendation.id.desc()).limit(300).all()


def _apply_worksheet_calculations(row: CompensationWorksheetRow, pay_band: PayBand | None = None) -> None:
    if pay_band:
        row.pay_band_id = pay_band.id
        row.pay_band_min = pay_band.min_ctc or 0
        row.pay_band_midpoint = pay_band.midpoint_ctc or 0
        row.pay_band_max = pay_band.max_ctc or 0
    current = Decimal(row.current_ctc or 0)
    amount = Decimal(row.proposed_merit_amount or 0)
    percent = Decimal(row.proposed_merit_percent or 0)
    if amount == 0 and percent and current:
        amount = (current * percent / Decimal("100")).quantize(Decimal("0.01"))
        row.proposed_merit_amount = amount
    elif amount and current:
        row.proposed_merit_percent = (amount / current * Decimal("100")).quantize(Decimal("0.01"))
    row.proposed_ctc = current + amount
    row.budget_impact = amount


@router.post("/compensation/worksheet", response_model=CompensationWorksheetRowSchema, status_code=201)
def create_compensation_worksheet_row(
    data: CompensationWorksheetRowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_compensation_access(current_user)
    employee = _employee_or_404(db, data.employee_id)
    pay_band = db.query(PayBand).filter(PayBand.id == data.pay_band_id).first() if data.pay_band_id else None
    current_ctc = data.current_ctc or _latest_ctc(db, data.employee_id)
    row = CompensationWorksheetRow(
        **data.model_dump(exclude={"current_ctc"}),
        current_ctc=current_ctc,
        manager_employee_id=employee.reporting_manager_id,
    )
    _apply_worksheet_calculations(row, pay_band)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/compensation/worksheet", response_model=List[CompensationWorksheetRowSchema])
def list_compensation_worksheet(
    compensation_cycle_id: Optional[int] = Query(None),
    manager_employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_compensation_access(current_user)
    query = db.query(CompensationWorksheetRow)
    if compensation_cycle_id:
        query = query.filter(CompensationWorksheetRow.compensation_cycle_id == compensation_cycle_id)
    if manager_employee_id:
        if not _is_hr_admin(current_user) and (not current_user.employee or current_user.employee.id != manager_employee_id):
            raise HTTPException(status_code=403, detail="Managers can view only their worksheet")
        query = query.filter(CompensationWorksheetRow.manager_employee_id == manager_employee_id)
    elif not _is_hr_admin(current_user) and not _has_permission(current_user, "payroll_run"):
        if not current_user.employee:
            raise HTTPException(status_code=403, detail="Compensation access required")
        query = query.filter(CompensationWorksheetRow.manager_employee_id == current_user.employee.id)
    return query.order_by(CompensationWorksheetRow.id.desc()).limit(300).all()


@router.put("/compensation/worksheet/{row_id}", response_model=CompensationWorksheetRowSchema)
def update_compensation_worksheet_row(
    row_id: int,
    data: CompensationWorksheetRowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_compensation_access(current_user)
    row = db.query(CompensationWorksheetRow).filter(CompensationWorksheetRow.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Worksheet row not found")
    if not _is_hr_admin(current_user) and not _has_permission(current_user, "payroll_run"):
        if not current_user.employee or row.manager_employee_id != current_user.employee.id:
            raise HTTPException(status_code=403, detail="Managers can update only their worksheet rows")
        if data.approval_status in {"Approved", "Rejected"}:
            raise HTTPException(status_code=403, detail="Only HR/payroll approvers can approve worksheet rows")
    payload = data.model_dump(exclude_unset=True)
    pay_band = None
    if "pay_band_id" in payload and payload["pay_band_id"]:
        pay_band = db.query(PayBand).filter(PayBand.id == payload["pay_band_id"]).first()
        if not pay_band:
            raise HTTPException(status_code=404, detail="Pay band not found")
    for field, value in payload.items():
        setattr(row, field, value)
    _apply_worksheet_calculations(row, pay_band)
    if row.approval_status in {"Approved", "Rejected"}:
        row.approved_by = current_user.id
        row.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.put("/compensation/merit-recommendations/{recommendation_id}", response_model=MeritRecommendationSchema)
def review_merit_recommendation(recommendation_id: int, data: MeritRecommendationReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    item = db.query(MeritRecommendation).filter(MeritRecommendation.id == recommendation_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Merit recommendation not found")
    item.status = data.status
    item.manager_remarks = data.manager_remarks or item.manager_remarks
    if data.status in {"Approved", "Rejected"}:
        item.approved_by = current_user.id
        item.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item
