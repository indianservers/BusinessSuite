from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.user import User
from app.schemas.expense import ExpenseClaimCreate, ExpenseClaimReview, ExpenseClaimSchema, ExpenseReimbursementUpdate

router = APIRouter(prefix="/expenses", tags=["Expense Claims"])


def _permissions(user: User) -> set[str]:
    return {permission.name for permission in (user.role.permissions if user.role else [])}


def _role_name(user: User) -> str:
    return (user.role.name if user.role else "").lower().replace(" ", "_")


def _can_finance(user: User) -> bool:
    return user.is_superuser or "payroll_run" in _permissions(user) or "payroll_approve" in _permissions(user)


def _can_hr_or_finance(user: User) -> bool:
    return _can_finance(user) or "hr_admin" in _permissions(user) or _role_name(user) in {"hr", "hr_admin", "hr_manager", "super_admin"}


def _employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _can_view_claim(user: User, claim: ExpenseClaim) -> bool:
    if _can_hr_or_finance(user):
        return True
    if not user.employee:
        return False
    employee = claim.employee
    return claim.employee_id == user.employee.id or bool(employee and employee.reporting_manager_id == user.employee.id)


@router.post("/claims", response_model=ExpenseClaimSchema, status_code=201)
def create_claim(
    data: ExpenseClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = data.employee_id or (current_user.employee.id if current_user.employee else None)
    if not employee_id:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    if data.employee_id and (not current_user.employee or data.employee_id != current_user.employee.id) and not _can_hr_or_finance(current_user):
        raise HTTPException(status_code=403, detail="Cannot submit claim for another employee")
    _employee_or_404(db, employee_id)
    claim = ExpenseClaim(
        **data.model_dump(exclude={"employee_id"}),
        employee_id=employee_id,
        claim_number=f"EXP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        status="submitted",
        submitted_by=current_user.id,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


@router.get("/claims", response_model=list[ExpenseClaimSchema])
def list_claims(
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ExpenseClaim)
    if not _can_hr_or_finance(current_user):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="Employee profile is required")
        team_ids = [row.id for row in db.query(Employee.id).filter(Employee.reporting_manager_id == current_user.employee.id).all()]
        query = query.filter(ExpenseClaim.employee_id.in_([current_user.employee.id, *team_ids]))
    if employee_id:
        query = query.filter(ExpenseClaim.employee_id == employee_id)
    if status:
        query = query.filter(ExpenseClaim.status == status)
    return query.order_by(ExpenseClaim.created_at.desc(), ExpenseClaim.id.desc()).limit(300).all()


@router.get("/claims/my", response_model=list[ExpenseClaimSchema])
def my_claims(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="Employee profile is required")
    return db.query(ExpenseClaim).filter(ExpenseClaim.employee_id == current_user.employee.id).order_by(ExpenseClaim.id.desc()).all()


@router.put("/claims/{claim_id}/manager-review", response_model=ExpenseClaimSchema)
def manager_review_claim(
    claim_id: int,
    data: ExpenseClaimReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    employee = _employee_or_404(db, claim.employee_id)
    if not (_can_hr_or_finance(current_user) or (current_user.employee and employee.reporting_manager_id == current_user.employee.id)):
        raise HTTPException(status_code=403, detail="Only manager/HR can review this claim")
    status = data.status.lower()
    if status not in {"manager_approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be manager_approved or rejected")
    claim.status = status
    claim.approved_amount = data.approved_amount if data.approved_amount is not None else claim.amount
    claim.manager_approved_by = current_user.id
    claim.manager_approved_at = datetime.now(timezone.utc)
    claim.remarks = data.remarks
    db.commit()
    db.refresh(claim)
    return claim


@router.put("/claims/{claim_id}/finance-review", response_model=ExpenseClaimSchema)
def finance_review_claim(
    claim_id: int,
    data: ExpenseClaimReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_finance(current_user):
        raise HTTPException(status_code=403, detail="Finance permission required")
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    status = data.status.lower()
    if status not in {"finance_approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be finance_approved or rejected")
    amount = data.approved_amount if data.approved_amount is not None else claim.approved_amount or claim.amount
    if Decimal(amount) > claim.amount:
        raise HTTPException(status_code=400, detail="Approved amount cannot exceed claim amount")
    claim.status = status
    claim.approved_amount = amount
    claim.finance_approved_by = current_user.id
    claim.finance_approved_at = datetime.now(timezone.utc)
    claim.remarks = data.remarks
    db.commit()
    db.refresh(claim)
    return claim


@router.put("/claims/{claim_id}/reimburse", response_model=ExpenseClaimSchema)
def reimburse_claim(
    claim_id: int,
    data: ExpenseReimbursementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_finance(current_user):
        raise HTTPException(status_code=403, detail="Finance permission required")
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    if claim.status != "finance_approved":
        raise HTTPException(status_code=400, detail="Only finance approved claims can be reimbursed")
    claim.status = "reimbursed"
    claim.reimbursed_at = datetime.now(timezone.utc)
    claim.reimbursement_reference = data.reimbursement_reference
    claim.remarks = data.remarks or claim.remarks
    db.commit()
    db.refresh(claim)
    return claim
