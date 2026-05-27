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
    Feedback360Request, GoalCheckIn, MeritRecommendation, PayBand, PerformanceGoal,
    PerformanceRatingCriteria, PerformanceReview, ReviewTemplate, ReviewTemplateQuestion,
    RoleSkillRequirement,
)
from app.schemas.performance import (
    AppraisalCycleCreate, AppraisalCycleSchema,
    CompensationCycleCreate, CompensationCycleSchema, CompetencyCreate, CompetencySchema,
    EmployeeCompetencyAssessmentCreate, EmployeeCompetencyAssessmentSchema,
    Feedback360RequestCreate, Feedback360RequestSchema, Feedback360Submit,
    GoalCheckInCreate, GoalCheckInSchema, MeritRecommendationCreate,
    MeritRecommendationReview, MeritRecommendationSchema, PayBandCreate, PayBandSchema,
    PerformanceGoalCreate, PerformanceGoalUpdate, PerformanceGoalSchema,
    PerformanceReviewCreate, PerformanceReviewSchema, ReviewTemplateCreate,
    ReviewTemplateSchema, RoleSkillRequirementCreate, RoleSkillRequirementSchema,
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


@router.post("/compensation/cycles", response_model=CompensationCycleSchema, status_code=201)
def create_compensation_cycle(data: CompensationCycleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = CompensationCycle(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/compensation/pay-bands", response_model=PayBandSchema, status_code=201)
def create_pay_band(data: PayBandCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if data.max_ctc and data.min_ctc and data.max_ctc < data.min_ctc:
        raise HTTPException(status_code=400, detail="max_ctc cannot be below min_ctc")
    item = PayBand(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


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
