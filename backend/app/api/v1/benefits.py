from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_db
from app.core.deps import get_current_user
from app.models.benefits import (
    BenefitClaim,
    BenefitDependent,
    BenefitEnrollmentWindow,
    BenefitPayrollDeduction,
    BenefitPlan,
    ESOPGrant,
    ESOPPlan,
    ESOPVestingSchedule,
    EmployeeBenefitEnrollment,
    EmployeeFlexiBenefitAllocation,
    FlexiBenefitPolicy,
)
from app.models.user import User
from app.schemas.benefits import (
    BenefitClaimCreate,
    BenefitClaimReview,
    BenefitClaimSchema,
    BenefitDependentCreate,
    BenefitDependentSchema,
    BenefitEnrollmentWindowCreate,
    BenefitEnrollmentWindowSchema,
    BenefitPayrollDeductionCreate,
    BenefitPayrollDeductionSchema,
    BenefitPlanCreate,
    BenefitPlanSchema,
    ESOPGrantCreate,
    ESOPGrantSchema,
    ESOPPlanCreate,
    ESOPPlanSchema,
    ESOPVestingScheduleSchema,
    EmployeeBenefitEnrollmentCreate,
    EmployeeBenefitEnrollmentSchema,
    EmployeeFlexiBenefitAllocationCreate,
    EmployeeFlexiBenefitAllocationSchema,
    FlexiBenefitPolicyCreate,
    FlexiBenefitPolicySchema,
)

router = APIRouter(prefix="/benefits", tags=["Benefits Administration"])


def _has_permission(user: User, permission: str) -> bool:
    return user.is_superuser or permission in {item.name for item in (user.role.permissions if user.role else [])}


@router.post("/plans", response_model=BenefitPlanSchema, status_code=201)
def create_plan(data: BenefitPlanCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    plan = BenefitPlan(**data.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans", response_model=List[BenefitPlanSchema])
def list_plans(plan_type: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(BenefitPlan).filter(BenefitPlan.is_active == True)
    if plan_type:
        query = query.filter(BenefitPlan.plan_type == plan_type)
    return query.order_by(BenefitPlan.name).all()


@router.post("/enrollments", response_model=EmployeeBenefitEnrollmentSchema, status_code=201)
def create_enrollment(data: EmployeeBenefitEnrollmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    plan = db.query(BenefitPlan).filter(BenefitPlan.id == data.benefit_plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Benefit plan not found")
    enrollment = EmployeeBenefitEnrollment(
        **data.model_dump(),
        status="Active",
        approved_by=current_user.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@router.get("/enrollments", response_model=List[EmployeeBenefitEnrollmentSchema])
def list_enrollments(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(EmployeeBenefitEnrollment)
    if employee_id:
        query = query.filter(EmployeeBenefitEnrollment.employee_id == employee_id)
    return query.order_by(EmployeeBenefitEnrollment.id.desc()).all()


@router.post("/enrollments/self", response_model=EmployeeBenefitEnrollmentSchema, status_code=201)
def self_enroll(data: EmployeeBenefitEnrollmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    if data.employee_id != current_user.employee.id:
        raise HTTPException(status_code=403, detail="Employees can enroll only themselves")
    plan = db.query(BenefitPlan).filter(BenefitPlan.id == data.benefit_plan_id, BenefitPlan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Benefit plan not found")
    today = datetime.now(timezone.utc).date()
    open_window = db.query(BenefitEnrollmentWindow).filter(
        BenefitEnrollmentWindow.status == "Open",
        BenefitEnrollmentWindow.start_date <= today,
        BenefitEnrollmentWindow.end_date >= today,
        (BenefitEnrollmentWindow.plan_type.is_(None)) | (BenefitEnrollmentWindow.plan_type == plan.plan_type),
    ).first()
    if not open_window and not _has_permission(current_user, "payroll_run"):
        raise HTTPException(status_code=400, detail="No active enrollment window for this benefit plan")
    enrollment = EmployeeBenefitEnrollment(**data.model_dump(), status="Pending")
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


@router.post("/enrollment-windows", response_model=BenefitEnrollmentWindowSchema, status_code=201)
def create_enrollment_window(
    data: BenefitEnrollmentWindowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    window = BenefitEnrollmentWindow(**data.model_dump(), created_by=current_user.id)
    db.add(window)
    db.commit()
    db.refresh(window)
    return window


@router.get("/enrollment-windows", response_model=List[BenefitEnrollmentWindowSchema])
def list_enrollment_windows(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(BenefitEnrollmentWindow)
    if status:
        query = query.filter(BenefitEnrollmentWindow.status == status)
    return query.order_by(BenefitEnrollmentWindow.start_date.desc()).limit(100).all()


@router.post("/dependants", response_model=BenefitDependentSchema, status_code=201)
def add_dependent(data: BenefitDependentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee_id = data.employee_id or (current_user.employee.id if current_user.employee else None)
    if not employee_id:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    if employee_id != (current_user.employee.id if current_user.employee else None) and not _has_permission(current_user, "payroll_run"):
        raise HTTPException(status_code=403, detail="Cannot add dependant for another employee")
    dependent = BenefitDependent(**data.model_dump(exclude={"employee_id"}), employee_id=employee_id)
    db.add(dependent)
    db.commit()
    db.refresh(dependent)
    return dependent


@router.get("/dependants", response_model=List[BenefitDependentSchema])
def list_dependents(
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scoped_employee_id = employee_id
    if not _has_permission(current_user, "payroll_view"):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="Employee profile is required")
        scoped_employee_id = current_user.employee.id
    query = db.query(BenefitDependent).filter(BenefitDependent.is_active == True)
    if scoped_employee_id:
        query = query.filter(BenefitDependent.employee_id == scoped_employee_id)
    return query.order_by(BenefitDependent.full_name).all()


@router.post("/flexi-policies", response_model=FlexiBenefitPolicySchema, status_code=201)
def create_flexi_policy(data: FlexiBenefitPolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    policy = FlexiBenefitPolicy(**data.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/flexi-policies", response_model=List[FlexiBenefitPolicySchema])
def list_flexi_policies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(FlexiBenefitPolicy).filter(FlexiBenefitPolicy.is_active == True).order_by(FlexiBenefitPolicy.name).all()


@router.post("/flexi-allocations", response_model=EmployeeFlexiBenefitAllocationSchema, status_code=201)
def create_flexi_allocation(data: EmployeeFlexiBenefitAllocationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    policy = db.query(FlexiBenefitPolicy).filter(FlexiBenefitPolicy.id == data.policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Flexi benefit policy not found")
    taxable_fallback = max(data.allocated_amount - data.claimed_amount, 0) if policy.taxable_if_unclaimed else 0
    allocation = EmployeeFlexiBenefitAllocation(**data.model_dump(), taxable_fallback_amount=taxable_fallback)
    db.add(allocation)
    db.commit()
    db.refresh(allocation)
    return allocation


@router.post("/payroll-deductions", response_model=BenefitPayrollDeductionSchema, status_code=201)
def create_payroll_deduction(data: BenefitPayrollDeductionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    enrollment = db.query(EmployeeBenefitEnrollment).filter(EmployeeBenefitEnrollment.id == data.enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Benefit enrollment not found")
    deduction = BenefitPayrollDeduction(
        enrollment_id=enrollment.id,
        employee_id=enrollment.employee_id,
        payroll_record_id=data.payroll_record_id,
        month=data.month,
        year=data.year,
        employee_amount=enrollment.employee_contribution,
        employer_amount=enrollment.employer_contribution,
        status="Ready",
    )
    db.add(deduction)
    db.commit()
    db.refresh(deduction)
    return deduction


@router.post("/claims", response_model=BenefitClaimSchema, status_code=201)
def create_claim(data: BenefitClaimCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    claim = BenefitClaim(**data.model_dump(), submitted_by=current_user.id)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


@router.get("/claims", response_model=List[BenefitClaimSchema])
def list_claims(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(BenefitClaim)
    if employee_id:
        query = query.filter(BenefitClaim.employee_id == employee_id)
    if status:
        query = query.filter(BenefitClaim.status == status)
    return query.order_by(BenefitClaim.id.desc()).limit(300).all()


@router.put("/claims/{claim_id}/review", response_model=BenefitClaimSchema)
def review_claim(claim_id: int, data: BenefitClaimReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    claim = db.query(BenefitClaim).filter(BenefitClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Benefit claim not found")
    if data.approved_amount > claim.claim_amount:
        raise HTTPException(status_code=400, detail="Approved amount cannot exceed claim amount")
    claim.status = data.status
    claim.approved_amount = data.approved_amount
    claim.taxable_amount = data.taxable_amount
    claim.tax_exempt_amount = data.tax_exempt_amount
    claim.review_remarks = data.review_remarks
    claim.payroll_record_id = data.payroll_record_id
    claim.reviewed_by = current_user.id
    claim.reviewed_at = datetime.now(timezone.utc)
    if claim.policy_id:
        allocation = db.query(EmployeeFlexiBenefitAllocation).filter(
            EmployeeFlexiBenefitAllocation.employee_id == claim.employee_id,
            EmployeeFlexiBenefitAllocation.policy_id == claim.policy_id,
        ).order_by(EmployeeFlexiBenefitAllocation.id.desc()).first()
        if allocation and data.status == "Approved":
            allocation.claimed_amount = (allocation.claimed_amount or Decimal("0")) + data.approved_amount
            allocation.taxable_fallback_amount = max((allocation.allocated_amount or Decimal("0")) - allocation.claimed_amount, Decimal("0"))
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/esop/plans", response_model=ESOPPlanSchema, status_code=201)
def create_esop_plan(data: ESOPPlanCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if db.query(ESOPPlan).filter(ESOPPlan.plan_code == data.plan_code).first():
        raise HTTPException(status_code=400, detail="ESOP plan code already exists")
    plan = ESOPPlan(**data.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/esop/plans", response_model=List[ESOPPlanSchema])
def list_esop_plans(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(ESOPPlan).filter(ESOPPlan.is_active == True).order_by(ESOPPlan.name).all()


@router.post("/esop/grants", response_model=ESOPGrantSchema, status_code=201)
def create_esop_grant(data: ESOPGrantCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    plan = db.query(ESOPPlan).filter(ESOPPlan.id == data.esop_plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="ESOP plan not found")
    grant = ESOPGrant(**data.model_dump())
    db.add(grant)
    db.flush()
    total_months = max(plan.total_vesting_months or 1, 1)
    frequency_months = 12 if plan.vesting_frequency == "Annual" else 3 if plan.vesting_frequency == "Quarterly" else 1
    vest_count = max(total_months // frequency_months, 1)
    units_per_vest = (data.granted_units / Decimal(vest_count)).quantize(Decimal("0.01"))
    for index in range(vest_count):
        month_offset = (plan.cliff_months or 0) + (index * frequency_months)
        vest_year = data.grant_date.year + ((data.grant_date.month + month_offset - 1) // 12)
        vest_month = ((data.grant_date.month + month_offset - 1) % 12) + 1
        db.add(ESOPVestingSchedule(
            grant_id=grant.id,
            vesting_date=data.grant_date.replace(year=vest_year, month=vest_month),
            units=units_per_vest,
        ))
    db.commit()
    db.refresh(grant)
    return grant


@router.get("/esop/grants", response_model=List[ESOPGrantSchema])
def list_esop_grants(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(ESOPGrant)
    if employee_id:
        query = query.filter(ESOPGrant.employee_id == employee_id)
    return query.order_by(ESOPGrant.id.desc()).limit(300).all()


@router.get("/esop/grants/{grant_id}/vesting", response_model=List[ESOPVestingScheduleSchema])
def list_esop_vesting(grant_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(ESOPVestingSchedule).filter(ESOPVestingSchedule.grant_id == grant_id).order_by(ESOPVestingSchedule.vesting_date).all()
    ESOPGrantCreate,
    ESOPGrantSchema,
    ESOPPlanCreate,
    ESOPPlanSchema,
    ESOPVestingScheduleSchema,
