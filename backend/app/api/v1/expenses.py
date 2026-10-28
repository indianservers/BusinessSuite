from app.access.catalog import permission_objects
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.employee_scope import employee_tenant_scope
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.user import User
from app.schemas.expense import ExpenseClaimCreate, ExpenseClaimReview, ExpenseClaimSchema, ExpenseReimbursementUpdate

router = APIRouter(prefix="/expenses", tags=["Expense Claims"], dependencies=[Depends(employee_tenant_scope)])


@router.get("/employees")
def expense_employees(search: str = "", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if not _can_hr_or_finance(current_user):
        if not current_user.employee:
            return []
        query = query.filter((Employee.id == current_user.employee.id) | (Employee.reporting_manager_id == current_user.employee.id))
    if search:
        query = query.filter((Employee.first_name + " " + Employee.last_name).ilike(f"%{search}%") | Employee.employee_id.ilike(f"%{search}%"))
    return [{"id": row.id, "name": f"{row.first_name} {row.last_name}", "employee_code": row.employee_id}
            for row in query.order_by(Employee.first_name, Employee.id).limit(50).all()]


@router.get("/statements/{employee_id}")
def expense_statement(employee_id: int, from_date: Optional[date] = None,
                      to_date: Optional[date] = None,
                      db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = _employee_or_404(db, employee_id)
    own = current_user.employee
    if not (_can_hr_or_finance(current_user) or (own and (own.id == employee_id or employee.reporting_manager_id == own.id))):
        raise HTTPException(403, "Cannot view this employee's expense statement")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Start date must not be after end date")
    query = db.query(ExpenseClaim).filter(ExpenseClaim.employee_id == employee_id)
    if from_date:
        query = query.filter(ExpenseClaim.expense_date >= from_date)
    if to_date:
        query = query.filter(ExpenseClaim.expense_date <= to_date)
    rows = query.order_by(ExpenseClaim.expense_date.desc(), ExpenseClaim.id.desc()).all()
    receipts = {}
    for identity, receipt in db.query(ExpenseClaim.id, ExpenseClaim.receipt_url).filter(ExpenseClaim.employee_id == employee_id, ExpenseClaim.receipt_url.isnot(None)).all():
        receipts.setdefault(receipt, []).append(identity)
    totals = {}
    for row in rows:
        total = totals.setdefault(row.currency or "INR", {key: Decimal("0") for key in ["claimed", "approved", "outstanding", "paid", "pending_review", "rejected"]})
        total["claimed"] += row.amount
        if row.status in {"finance_approved", "reimbursed"}:
            amount = row.approved_amount or Decimal("0")
            total["approved"] += amount
            total["paid" if row.status == "reimbursed" else "outstanding"] += amount
        elif row.status == "rejected":
            total["rejected"] += row.amount
        else:
            total["pending_review"] += row.amount
    return {"employee_id": employee_id, "employee_name": f"{employee.first_name} {employee.last_name}",
            "totals": [{"currency": currency, **{key: str(value) for key, value in total.items()}} for currency, total in sorted(totals.items())],
            "claims": [{**ExpenseClaimSchema.model_validate(row).model_dump(mode="json"), "duplicate_receipt_claim_ids": [identity for identity in receipts.get(row.receipt_url, []) if identity != row.id]} for row in rows],
            "can_submit": bool(_can_hr_or_finance(current_user) or (own and own.id == employee_id)),
            "can_manager_review": bool(_can_hr_or_finance(current_user) or (own and employee.reporting_manager_id == own.id)),
            "can_finance_review": _can_finance(current_user)}


def _permissions(user: User) -> set[str]:
    return {permission.name for permission in (permission_objects(user))}


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
    if data.expense_date > date.today():
        raise HTTPException(422, "Expense date cannot be in the future")
    if not data.claim_type.strip():
        raise HTTPException(422, "Choose an expense category")
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
    query = db.query(ExpenseClaim).join(Employee)
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


@router.post("/claims/{claim_id}/receipt")
async def attach_receipt(claim_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from pathlib import Path
    from hashlib import sha256
    from app.core.config import settings
    from app.core.storage import persist_file
    claim = db.query(ExpenseClaim).join(Employee).filter(ExpenseClaim.id == claim_id).with_for_update().first()
    if not claim or not _can_view_claim(current_user, claim):
        raise HTTPException(404, "Expense claim not found")
    if not _can_hr_or_finance(current_user) and (not current_user.employee or claim.employee_id != current_user.employee.id):
        raise HTTPException(403, "Only the submitting employee or HR can attach a receipt")
    if claim.status != "submitted":
        raise HTTPException(409, "Receipts cannot change after manager review")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(422, "Use a PDF, PNG or JPEG receipt")
    body = await file.read(5 * 1024 * 1024 + 1)
    if not body or len(body) > 5 * 1024 * 1024:
        raise HTTPException(413, "Receipts must be between 1 byte and 5 MB")
    valid = body.startswith(b"%PDF-") if extension == ".pdf" else body.startswith(b"\x89PNG\r\n\x1a\n") if extension == ".png" else body.startswith(b"\xff\xd8\xff")
    if not valid:
        raise HTTPException(422, "Receipt content does not match its file type")
    digest = sha256(body).hexdigest()
    duplicate_ids = [row.id for row in db.query(ExpenseClaim.id).filter(ExpenseClaim.employee_id == claim.employee_id, ExpenseClaim.id != claim.id, ExpenseClaim.receipt_url.like(f"%/{digest}.%"))]
    directory = Path(settings.UPLOAD_DIR) / "expenses" / str(claim.employee_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{digest}{extension}"
    target.write_bytes(body); persist_file(str(target))
    claim.receipt_url = f"/uploads/expenses/{claim.employee_id}/{target.name}"
    db.commit()
    return {"receipt_url": claim.receipt_url, "duplicate_claim_ids": duplicate_ids}


@router.put("/claims/{claim_id}/manager-review", response_model=ExpenseClaimSchema)
def manager_review_claim(
    claim_id: int,
    data: ExpenseClaimReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = db.query(ExpenseClaim).join(Employee).filter(ExpenseClaim.id == claim_id).with_for_update().first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    if claim.status != "submitted":
        raise HTTPException(409, "This claim has already left manager review")
    employee = _employee_or_404(db, claim.employee_id)
    if not (_can_hr_or_finance(current_user) or (current_user.employee and employee.reporting_manager_id == current_user.employee.id)):
        raise HTTPException(status_code=403, detail="Only manager/HR can review this claim")
    status = data.status.lower()
    if status not in {"manager_approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be manager_approved or rejected")
    amount = data.approved_amount if data.approved_amount is not None else claim.amount
    if amount < 0 or amount > claim.amount:
        raise HTTPException(422, "Approved amount must be between zero and the claimed amount")
    claim.status = status
    claim.approved_amount = amount if status != "rejected" else Decimal("0")
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
    claim = db.query(ExpenseClaim).join(Employee).filter(ExpenseClaim.id == claim_id).with_for_update().first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    if claim.status != "manager_approved":
        raise HTTPException(409, "Manager approval is required before finance review")
    status = data.status.lower()
    if status not in {"finance_approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be finance_approved or rejected")
    amount = data.approved_amount if data.approved_amount is not None else claim.approved_amount
    if Decimal(amount) < 0 or Decimal(amount) > claim.amount:
        raise HTTPException(status_code=400, detail="Approved amount cannot exceed claim amount")
    claim.status = status
    claim.approved_amount = amount if status != "rejected" else Decimal("0")
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
    claim = db.query(ExpenseClaim).join(Employee).filter(ExpenseClaim.id == claim_id).with_for_update().first()
    if not claim:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    if claim.status != "finance_approved":
        raise HTTPException(status_code=400, detail="Only finance approved claims can be reimbursed")
    if claim.payroll_run_id or claim.payroll_reimbursement_id:
        raise HTTPException(409, "This claim is linked to payroll. Reconcile payment through its payroll run.")
    if not data.reimbursement_reference or not data.reimbursement_reference.strip():
        raise HTTPException(422, "A payment reference is required")
    claim.status = "reimbursed"
    claim.reimbursed_at = datetime.now(timezone.utc)
    claim.reimbursement_reference = data.reimbursement_reference
    claim.remarks = data.remarks or claim.remarks
    db.commit()
    db.refresh(claim)
    return claim
