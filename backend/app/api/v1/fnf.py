from __future__ import annotations
from app.access.catalog import permission_objects
from app.core.storage import persist_file, FileResponse

import calendar
import os
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.deps import RequirePermission, get_current_user, get_db
from app.crud.crud_payroll import get_prorated_salary_for_period
from app.models.employee import Employee
from app.models.exit import ExitChecklistItem, ExitRecord
from app.models.leave import LeaveBalance, LeaveType
from app.models.payroll import (
    EmployeeLoan,
    EmployeeSalary,
    FullFinalSettlement,
    FullFinalSettlementLine,
    Reimbursement,
)
from app.models.user import User

router = APIRouter(prefix="/hrms/fnf-settlements", tags=["HRMS Full & Final Settlement"])


class FnFComponentInput(BaseModel):
    id: int | None = None
    component_type: Literal["earning", "deduction"]
    name: str = Field(..., min_length=1, max_length=120)
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    source_module: str | None = None
    is_manual_adjustment: bool = True
    remarks: str | None = None


class FnFGenerateRequest(BaseModel):
    employee_id: int
    exit_id: int | None = None
    last_working_date: date
    exit_reason: str | None = None
    remarks: str | None = None


class FnFSettlementUpdate(BaseModel):
    last_working_date: date | None = None
    unpaid_salary: Decimal | None = Field(default=None, ge=0)
    leave_encashment: Decimal | None = Field(default=None, ge=0)
    gratuity_amount: Decimal | None = Field(default=None, ge=0)
    notice_recovery: Decimal | None = Field(default=None, ge=0)
    loan_recovery: Decimal | None = Field(default=None, ge=0)
    reimbursement_payable: Decimal | None = Field(default=None, ge=0)
    bonus_payable: Decimal | None = Field(default=None, ge=0)
    other_earnings: Decimal | None = Field(default=None, ge=0)
    other_deductions: Decimal | None = Field(default=None, ge=0)
    remarks: str | None = None
    components: list[FnFComponentInput] | None = None


class FnFActionRequest(BaseModel):
    remarks: str | None = None
    rejection_reason: str | None = None


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _status(value: str | None) -> str:
    text = (value or "draft").strip().lower().replace(" ", "_")
    if text == "approved":
        return "approved"
    if text in {"draft", "pending_approval", "paid", "rejected", "cancelled"}:
        return text
    return "draft"


def _org_id(user: User) -> int | None:
    return getattr(user, "organization_id", None) or getattr(user, "company_id", None)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (permission_objects(user))}


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown employee"
    return " ".join(part for part in [employee.first_name, employee.last_name] if part).strip() or employee.employee_id


def _load_settlement(db: Session, settlement_id: int) -> FullFinalSettlement:
    settlement = (
        db.query(FullFinalSettlement)
        .options(joinedload(FullFinalSettlement.lines))
        .filter(FullFinalSettlement.id == settlement_id)
        .first()
    )
    if not settlement:
        raise HTTPException(status_code=404, detail="F&F settlement not found")
    return settlement


def _enforce_view_access(db: Session, settlement: FullFinalSettlement, current_user: User) -> None:
    if _has_permission(current_user, "payroll_view") or _has_permission(current_user, "payroll_run"):
        return
    employee = db.query(Employee).filter(Employee.id == settlement.employee_id).first()
    if employee and employee.user_id == current_user.id and _status(settlement.status) in {"approved", "paid"}:
        return
    raise HTTPException(status_code=403, detail="Not authorized to view this settlement")


def _settlement_component(component: FullFinalSettlementLine) -> dict[str, Any]:
    normalized_type = "deduction" if (component.line_type or "").lower() in {"deduction", "recovery"} else "earning"
    return {
        "id": component.id,
        "component_type": normalized_type,
        "name": component.component_name,
        "amount": float(_money(component.amount)),
        "source_module": component.source,
        "is_manual_adjustment": bool(component.is_manual_adjustment),
        "remarks": component.remarks,
    }


def _clearance_status(db: Session, exit_id: int | None) -> dict[str, Any]:
    if not exit_id:
        return {"total": 0, "completed": 0, "status": "not_started"}
    items = db.query(ExitChecklistItem).filter(ExitChecklistItem.exit_record_id == exit_id).all()
    completed = sum(1 for item in items if item.is_completed)
    status = "cleared" if items and completed == len(items) else "pending"
    if not items:
        status = "not_started"
    return {"total": len(items), "completed": completed, "status": status}


def _serialize(db: Session, settlement: FullFinalSettlement) -> dict[str, Any]:
    employee = db.query(Employee).filter(Employee.id == settlement.employee_id).first()
    return {
        "id": settlement.id,
        "organizationId": settlement.organization_id,
        "employeeId": settlement.employee_id,
        "employeeCode": employee.employee_id if employee else None,
        "employeeName": _employee_name(employee),
        "exitId": settlement.exit_record_id,
        "lastWorkingDate": settlement.last_working_date or settlement.settlement_date,
        "settlementStatus": _status(settlement.status),
        "unpaidSalary": float(_money(settlement.unpaid_salary)),
        "leaveEncashment": float(_money(settlement.leave_encashment_amount)),
        "gratuityAmount": float(_money(settlement.gratuity_amount)),
        "noticeRecovery": float(_money(settlement.notice_recovery_amount)),
        "loanRecovery": float(_money(settlement.loan_recovery_amount)),
        "reimbursementPayable": float(_money(settlement.reimbursement_payable)),
        "bonusPayable": float(_money(settlement.bonus_payable)),
        "otherEarnings": float(_money(settlement.other_earnings or settlement.other_payables)),
        "otherDeductions": float(_money(settlement.other_deductions or settlement.other_recoveries)),
        "netPayable": float(_money(settlement.net_payable)),
        "remarks": settlement.remarks,
        "approvedBy": settlement.approved_by,
        "approvedAt": settlement.approved_at,
        "submittedAt": settlement.submitted_at,
        "paidAt": settlement.paid_at,
        "createdAt": settlement.created_at,
        "updatedAt": settlement.updated_at,
        "clearanceStatus": _clearance_status(db, settlement.exit_record_id),
        "components": [_settlement_component(line) for line in settlement.lines],
        "timeline": [
            {"label": "Draft", "completed": True, "at": settlement.created_at},
            {"label": "Submitted", "completed": _status(settlement.status) in {"pending_approval", "approved", "paid"}, "at": settlement.submitted_at},
            {"label": "Finance approved", "completed": _status(settlement.status) in {"approved", "paid"}, "at": settlement.approved_at},
            {"label": "Paid", "completed": _status(settlement.status) == "paid", "at": settlement.paid_at},
        ],
    }


def _line(settlement: FullFinalSettlement, component_type: str, name: str, amount: Decimal, source: str, remarks: str | None = None) -> FullFinalSettlementLine:
    return FullFinalSettlementLine(
        line_type=component_type,
        component_name=name,
        amount=_money(amount),
        source=source,
        is_manual_adjustment=False,
        remarks=remarks,
    )


def _recalculate(settlement: FullFinalSettlement) -> None:
    line_earnings = Decimal("0")
    line_deductions = Decimal("0")
    for line in settlement.lines:
        if (line.line_type or "").lower() in {"deduction", "recovery"}:
            line_deductions += _money(line.amount)
        else:
            line_earnings += _money(line.amount)

    base_earnings = (
        _money(settlement.unpaid_salary)
        + _money(settlement.leave_encashment_amount)
        + _money(settlement.gratuity_amount)
        + _money(settlement.reimbursement_payable)
        + _money(settlement.bonus_payable)
        + _money(settlement.other_earnings or settlement.other_payables)
    )
    base_deductions = (
        _money(settlement.notice_recovery_amount)
        + _money(settlement.loan_recovery_amount)
        + _money(settlement.other_deductions or settlement.other_recoveries)
    )
    # If detail lines exist, they are the source of truth and already include the base components.
    settlement.net_payable = _money((line_earnings or base_earnings) - (line_deductions or base_deductions))
    settlement.other_payables = _money(settlement.other_earnings)
    settlement.other_recoveries = _money(settlement.other_deductions)


def _latest_salary(db: Session, employee_id: int) -> EmployeeSalary | None:
    return (
        db.query(EmployeeSalary)
        .filter(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_active.is_(True))
        .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
        .first()
    )


def _generate_amounts(db: Session, employee: Employee, exit_record: ExitRecord, last_working_date: date) -> dict[str, Decimal]:
    month_start = date(last_working_date.year, last_working_date.month, 1)
    month_end = date(last_working_date.year, last_working_date.month, calendar.monthrange(last_working_date.year, last_working_date.month)[1])
    monthly_ctc, basic, _hra = get_prorated_salary_for_period(db, employee.id, month_start, month_end)
    unpaid_salary = _money((monthly_ctc / Decimal(str(month_end.day))) * Decimal(str(last_working_date.day))) if monthly_ctc else Decimal("0")
    daily_basic = _money((basic or monthly_ctc) / Decimal("30")) if (basic or monthly_ctc) else Decimal("0")

    balances = (
        db.query(LeaveBalance)
        .join(LeaveType, LeaveType.id == LeaveBalance.leave_type_id)
        .filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.year == last_working_date.year,
            LeaveType.encashable.is_(True),
        )
        .all()
    )
    encashable_days = sum(_money((b.allocated or 0) + (b.carried_forward or 0) - (b.used or 0) - (b.pending or 0)) for b in balances)
    leave_encashment = _money(max(encashable_days, Decimal("0")) * daily_basic)

    years_of_service = Decimal("0")
    if employee.date_of_joining:
        years_of_service = Decimal(str(max((last_working_date - employee.date_of_joining).days, 0))) / Decimal("365")
    gratuity = _money((basic or monthly_ctc * Decimal("0.4")) * Decimal("15") / Decimal("26") * years_of_service) if years_of_service >= Decimal("5") and (basic or monthly_ctc) else Decimal("0")

    notice_recovery = Decimal("0")
    if exit_record.notice_period_days and not exit_record.notice_waived and exit_record.resignation_date:
        served_days = max((last_working_date - exit_record.resignation_date).days + 1, 0)
        shortfall = max(exit_record.notice_period_days - served_days, 0)
        notice_recovery = _money(daily_basic * Decimal(str(shortfall)))

    loan_recovery = _money(
        sum(
            _money(loan.balance_amount)
            for loan in db.query(EmployeeLoan)
            .filter(EmployeeLoan.employee_id == employee.id, EmployeeLoan.status.in_(["Active", "Approved"]))
            .all()
        )
    )
    reimbursement_payable = _money(
        sum(
            _money(item.amount)
            for item in db.query(Reimbursement)
            .filter(
                Reimbursement.employee_id == employee.id,
                Reimbursement.status == "Approved",
                Reimbursement.payroll_record_id.is_(None),
            )
            .all()
        )
    )
    return {
        "unpaid_salary": unpaid_salary,
        "leave_encashment": leave_encashment,
        "gratuity": gratuity,
        "notice_recovery": notice_recovery,
        "loan_recovery": loan_recovery,
        "reimbursement_payable": reimbursement_payable,
        "bonus_payable": Decimal("0"),
        "other_earnings": Decimal("0"),
        "other_deductions": Decimal("0"),
    }


@router.get("", dependencies=[Depends(RequirePermission("payroll_view", "payroll_run"))])
def list_fnf_settlements(
    status: str | None = Query(default=None),
    employee_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(FullFinalSettlement).options(joinedload(FullFinalSettlement.lines))
    if status:
        query = query.filter(FullFinalSettlement.status.in_([status, status.title(), status.replace("_", " ").title()]))
    if employee_id:
        query = query.filter(FullFinalSettlement.employee_id == employee_id)
    org_id = _org_id(current_user)
    if org_id is not None:
        query = query.filter(and_(FullFinalSettlement.organization_id == org_id))
    settlements = query.order_by(FullFinalSettlement.created_at.desc(), FullFinalSettlement.id.desc()).all()
    return [_serialize(db, settlement) for settlement in settlements]


@router.get("/{settlement_id}")
def get_fnf_settlement(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settlement = _load_settlement(db, settlement_id)
    _enforce_view_access(db, settlement, current_user)
    return _serialize(db, settlement)


@router.post("/generate", dependencies=[Depends(RequirePermission("payroll_run", "payroll_view"))])
def generate_fnf_settlement(
    payload: FnFGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    exit_record = None
    if payload.exit_id:
        exit_record = db.query(ExitRecord).filter(ExitRecord.id == payload.exit_id, ExitRecord.employee_id == employee.id).first()
        if not exit_record:
            raise HTTPException(status_code=404, detail="Exit record not found for employee")
    else:
        exit_record = db.query(ExitRecord).filter(ExitRecord.employee_id == employee.id).first()

    if not exit_record:
        exit_record = ExitRecord(
            employee_id=employee.id,
            exit_type="Resignation",
            resignation_date=date.today(),
            last_working_date=payload.last_working_date,
            reason=payload.exit_reason,
            status="Initiated",
        )
        db.add(exit_record)
        db.flush()
    else:
        exit_record.last_working_date = payload.last_working_date
        if payload.exit_reason:
            exit_record.reason = payload.exit_reason

    amounts = _generate_amounts(db, employee, exit_record, payload.last_working_date)
    settlement = FullFinalSettlement(
        organization_id=_org_id(current_user),
        employee_id=employee.id,
        exit_record_id=exit_record.id,
        settlement_date=date.today(),
        last_working_date=payload.last_working_date,
        status="draft",
        unpaid_salary=amounts["unpaid_salary"],
        leave_encashment_amount=amounts["leave_encashment"],
        gratuity_amount=amounts["gratuity"],
        notice_recovery_amount=amounts["notice_recovery"],
        loan_recovery_amount=amounts["loan_recovery"],
        reimbursement_payable=amounts["reimbursement_payable"],
        bonus_payable=amounts["bonus_payable"],
        other_earnings=amounts["other_earnings"],
        other_deductions=amounts["other_deductions"],
        prepared_by=current_user.id,
        remarks=payload.remarks,
    )
    db.add(settlement)
    db.flush()
    settlement.lines.extend(
        [
            _line(settlement, "earning", "Unpaid salary", amounts["unpaid_salary"], "payroll"),
            _line(settlement, "earning", "Leave encashment", amounts["leave_encashment"], "leave"),
            _line(settlement, "earning", "Gratuity", amounts["gratuity"], "payroll"),
            _line(settlement, "earning", "Reimbursement payable", amounts["reimbursement_payable"], "payroll"),
            _line(settlement, "earning", "Bonus / variable pay", amounts["bonus_payable"], "payroll"),
            _line(settlement, "deduction", "Notice period recovery", amounts["notice_recovery"], "exit"),
            _line(settlement, "deduction", "Loan / advance recovery", amounts["loan_recovery"], "payroll"),
        ]
    )
    _recalculate(settlement)
    db.commit()
    db.refresh(settlement)
    return _serialize(db, settlement)


@router.patch("/{settlement_id}", dependencies=[Depends(RequirePermission("payroll_run"))])
def update_fnf_settlement(
    settlement_id: int,
    payload: FnFSettlementUpdate,
    db: Session = Depends(get_db),
):
    settlement = _load_settlement(db, settlement_id)
    if _status(settlement.status) not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected settlements can be edited")

    field_map = {
        "last_working_date": "last_working_date",
        "unpaid_salary": "unpaid_salary",
        "leave_encashment": "leave_encashment_amount",
        "gratuity_amount": "gratuity_amount",
        "notice_recovery": "notice_recovery_amount",
        "loan_recovery": "loan_recovery_amount",
        "reimbursement_payable": "reimbursement_payable",
        "bonus_payable": "bonus_payable",
        "other_earnings": "other_earnings",
        "other_deductions": "other_deductions",
        "remarks": "remarks",
    }
    data = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    for source, target in field_map.items():
        if source in data:
            setattr(settlement, target, data[source])

    if payload.components is not None:
        settlement.lines.clear()
        db.flush()
        for component in payload.components:
            settlement.lines.append(
                FullFinalSettlementLine(
                    line_type=component.component_type,
                    component_name=component.name,
                    amount=_money(component.amount),
                    source=component.source_module,
                    is_manual_adjustment=component.is_manual_adjustment,
                    remarks=component.remarks,
                )
            )
    _recalculate(settlement)
    db.commit()
    db.refresh(settlement)
    return _serialize(db, settlement)


@router.post("/{settlement_id}/submit", dependencies=[Depends(RequirePermission("payroll_run"))])
def submit_fnf_settlement(settlement_id: int, db: Session = Depends(get_db)):
    settlement = _load_settlement(db, settlement_id)
    if _status(settlement.status) not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Settlement cannot be submitted from current status")
    settlement.status = "pending_approval"
    settlement.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settlement)
    return _serialize(db, settlement)


@router.post("/{settlement_id}/approve", dependencies=[Depends(RequirePermission("payroll_approve"))])
def approve_fnf_settlement(
    settlement_id: int,
    payload: FnFActionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settlement = _load_settlement(db, settlement_id)
    if _status(settlement.status) != "pending_approval":
        raise HTTPException(status_code=400, detail="Only submitted settlements can be approved")
    settlement.status = "approved"
    settlement.approved_by = current_user.id
    settlement.approved_at = datetime.now(timezone.utc)
    if payload and payload.remarks:
        settlement.remarks = payload.remarks
    db.commit()
    db.refresh(settlement)
    return _serialize(db, settlement)


@router.post("/{settlement_id}/reject", dependencies=[Depends(RequirePermission("payroll_approve"))])
def reject_fnf_settlement(
    settlement_id: int,
    payload: FnFActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settlement = _load_settlement(db, settlement_id)
    if _status(settlement.status) != "pending_approval":
        raise HTTPException(status_code=400, detail="Only submitted settlements can be rejected")
    settlement.status = "rejected"
    settlement.rejected_by = current_user.id
    settlement.rejected_at = datetime.now(timezone.utc)
    settlement.remarks = payload.rejection_reason or payload.remarks or settlement.remarks
    db.commit()
    db.refresh(settlement)
    return _serialize(db, settlement)


@router.post("/{settlement_id}/mark-paid", dependencies=[Depends(RequirePermission("payroll_approve", "payroll_run"))])
def mark_fnf_settlement_paid(
    settlement_id: int,
    payload: FnFActionRequest | None = None,
    db: Session = Depends(get_db),
):
    settlement = _load_settlement(db, settlement_id)
    if _status(settlement.status) != "approved":
        raise HTTPException(status_code=400, detail="Only approved settlements can be marked paid")
    settlement.status = "paid"
    settlement.paid_at = datetime.now(timezone.utc)
    if payload and payload.remarks:
        settlement.remarks = payload.remarks
    if settlement.exit_record_id:
        exit_record = db.query(ExitRecord).filter(ExitRecord.id == settlement.exit_record_id).first()
        if exit_record:
            exit_record.final_settlement_amount = settlement.net_payable
            exit_record.final_settlement_date = date.today()
            exit_record.status = "Completed"
    db.commit()
    db.refresh(settlement)
    return _serialize(db, settlement)


@router.get("/{settlement_id}/pdf")
def download_fnf_statement(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settlement = _load_settlement(db, settlement_id)
    _enforce_view_access(db, settlement, current_user)
    if _status(settlement.status) not in {"approved", "paid"} and not _has_permission(current_user, "payroll_view"):
        raise HTTPException(status_code=403, detail="Settlement statement is available after approval")

    data = _serialize(db, settlement)
    out_dir = os.path.join(settings.UPLOAD_DIR, "fnf-settlements")
    os.makedirs(out_dir, exist_ok=True)
    file_path = os.path.join(out_dir, f"fnf_settlement_{settlement.id}.pdf")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        y = height - 48
        c.setFont("Helvetica-Bold", 16)
        c.drawString(48, y, "Full & Final Settlement Statement")
        y -= 34
        c.setFont("Helvetica", 10)
        for label, value in [
            ("Employee", f"{data['employeeName']} ({data['employeeCode'] or data['employeeId']})"),
            ("Last working date", str(data["lastWorkingDate"])),
            ("Status", data["settlementStatus"].replace("_", " ").title()),
            ("Net payable", f"INR {data['netPayable']:.2f}"),
        ]:
            c.drawString(48, y, f"{label}: {value}")
            y -= 18
        y -= 10
        c.setFont("Helvetica-Bold", 12)
        c.drawString(48, y, "Components")
        y -= 20
        c.setFont("Helvetica", 10)
        for component in data["components"]:
            if y < 90:
                c.showPage()
                y = height - 48
                c.setFont("Helvetica", 10)
            c.drawString(56, y, f"{component['component_type'].title()} - {component['name']}")
            c.drawRightString(width - 56, y, f"INR {component['amount']:.2f}")
            y -= 16
        y -= 20
        c.line(48, y, 220, y)
        c.drawString(48, y - 14, "Authorized signature")
        c.save()
    except Exception:
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(f"Full & Final Settlement Statement\nEmployee: {data['employeeName']}\nNet payable: INR {data['netPayable']:.2f}\n")
        persist_file(file_path)

    persist_file(file_path)
    return FileResponse(file_path, media_type="application/pdf", filename=os.path.basename(file_path))
