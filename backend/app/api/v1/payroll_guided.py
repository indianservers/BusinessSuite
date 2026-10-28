"""A guided payroll path using existing calculation, approval and payment services."""
import hashlib
import json
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.access.catalog import permission_objects
from app.apps.srm.services.commercial import tenant
from app.models.payroll import PayrollRun, PayrollRecord, PayrollRunAuditLog, PayrollPaymentBatch
from app.models.employee import Employee
from app.crud import crud_payroll

router = APIRouter()


def context(db, run_id, user):
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id, PayrollRun.deleted_at.is_(None)).with_for_update().first()
    if not run or (not user.is_superuser and (run.company_id or 1) != tenant(user)):
        raise HTTPException(404, "Payroll run not found")
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).order_by(PayrollRecord.id).all()
    fingerprint = hashlib.sha256(json.dumps([[r.id, str(r.gross_salary), str(r.net_salary), str(r.total_deductions)] for r in records]).encode()).hexdigest()
    reviewed = db.query(PayrollRunAuditLog.id).filter(PayrollRunAuditLog.payroll_run_id == run_id,
        PayrollRunAuditLog.action == "guided_changes_reviewed", PayrollRunAuditLog.details == fingerprint).first() is not None
    return run, records, fingerprint, reviewed


def blockers(db, run, records):
    from app.api.v1.payroll import _payroll_input_blockers
    readiness = crud_payroll.payroll_readiness_summary(db, run.month, run.year, company_id=run.company_id,
        branch_id=run.branch_id, department_id=run.department_id, pay_group_id=run.pay_group_id, employee_category=run.employee_category)
    issues = []
    for key, issue in readiness["issues"].items():
        if issue["count"]:
            issues.append({"key": key, **issue})
    extra = _payroll_input_blockers(db, run)
    if not records:
        extra.append("No calculated employee records. Calculate payroll first.")
    if any((row.net_salary or 0) < 0 for row in records):
        extra.append("Negative net pay must be resolved.")
    return issues, extra, readiness["critical_issue_count"] > 0 or bool(extra)


@router.get("/runs/{run_id}/guided")
def overview(run_id: int, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_view"))):
    run, records, fingerprint, reviewed = context(db, run_id, user)
    issues, extra, blocked = blockers(db, run, records)
    batches = db.query(PayrollPaymentBatch).filter(PayrollPaymentBatch.payroll_run_id == run_id).order_by(PayrollPaymentBatch.id.desc()).all()
    people = {row.id: row for row in db.query(Employee).filter(Employee.id.in_([r.employee_id for r in records])).all()}
    permissions = {p.name for p in permission_objects(user)}
    return {"id": run.id, "status": crud_payroll.normalize_payroll_run_status(run.status), "reviewed": reviewed,
            "blocked": blocked, "issues": issues, "blockers": extra,
            "can_process": user.is_superuser or "payroll_run" in permissions,
            "can_approve": user.is_superuser or "payroll_approve" in permissions,
            "records": [{"id": r.id, "employee_id": r.employee_id,
                         "employee_name": f"{people[r.employee_id].first_name} {people[r.employee_id].last_name}" if r.employee_id in people else str(r.employee_id),
                         "gross": str(r.gross_salary), "deductions": str(r.total_deductions), "net": str(r.net_salary)} for r in records],
            "batches": [{"id": b.id, "status": b.status, "total": str(b.total_amount), "file_url": b.generated_file_url,
                         "lines": [{"employee_id": l.employee_id, "payroll_record_id": l.payroll_record_id, "status": l.payment_status,
                                    "utr": l.utr_number, "failure_reason": l.failure_reason} for l in b.lines]} for b in batches]}


class GuidedAction(BaseModel):
    action: Literal["review", "approve", "lock", "pay", "reconcile"]
    remarks: str = Field(min_length=3, max_length=1000)


@router.post("/runs/{run_id}/guided")
def advance(run_id: int, data: GuidedAction, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_view"))):
    from app.api.v1.payroll import approve_payroll, create_payment_batch
    from app.schemas.payroll import PayrollRunApproval, PayrollPaymentBatchCreate
    run, records, fingerprint, reviewed = context(db, run_id, user)
    permissions = {p.name for p in permission_objects(user)}
    needed = "payroll_run" if data.action in {"review", "pay"} else "payroll_approve"
    if not user.is_superuser and needed not in permissions:
        raise HTTPException(403, f"{needed} permission is required")
    status = crud_payroll.normalize_payroll_run_status(run.status)
    if data.action in {"review", "approve"}:
        _, _, blocked = blockers(db, run, records)
        if blocked:
            raise HTTPException(409, "Resolve payroll blockers before reviewing or approving")
        if status != "calculated":
            raise HTTPException(409, "Payroll must be calculated before this step")
    if data.action == "review":
        db.add(PayrollRunAuditLog(payroll_run_id=run_id, action="guided_changes_reviewed", actor_user_id=user.id, details=fingerprint))
        db.commit()
        return {"reviewed": True}
    if data.action == "approve":
        if not reviewed:
            raise HTTPException(409, "Review the current calculated changes first")
        if not user.is_superuser and db.query(PayrollRunAuditLog.id).filter(PayrollRunAuditLog.payroll_run_id == run_id,
            PayrollRunAuditLog.action == "guided_changes_reviewed", PayrollRunAuditLog.details == fingerprint,
            PayrollRunAuditLog.actor_user_id == user.id).first():
            raise HTTPException(403, "A different approver must approve the reviewed payroll")
        return approve_payroll(run_id, PayrollRunApproval(action="approve", remarks=data.remarks), db, user)
    if data.action == "lock":
        return approve_payroll(run_id, PayrollRunApproval(action="lock", remarks=data.remarks), db, user)
    if data.action == "pay":
        if status != "locked":
            raise HTTPException(409, "Approve and lock payroll before preparing payment")
        if db.query(PayrollPaymentBatch.id).filter(PayrollPaymentBatch.payroll_run_id == run_id).first():
            raise HTTPException(409, "A payment batch already exists. Reconcile that batch instead of generating another.")
        return create_payment_batch(PayrollPaymentBatchCreate(payroll_run_id=run_id), db, user)
    if status != "locked":
        raise HTTPException(409, "Only locked payroll can be reconciled")
    batches = db.query(PayrollPaymentBatch).filter(PayrollPaymentBatch.payroll_run_id == run_id).all()
    lines = [line for batch in batches for line in batch.lines]
    record_ids = {row.id for row in records}
    if not lines or len(lines) != len(records) or {line.payroll_record_id for line in lines} != record_ids or any(line.payment_status != "Paid" or not line.utr_number for line in lines):
        raise HTTPException(409, "Every employee payment must be confirmed paid with a bank reference; resolve missing, duplicate or failed lines")
    values = {row.id: row.net_salary for row in records}
    if any(line.net_amount != values[line.payroll_record_id] for line in lines):
        raise HTTPException(409, "Payment amounts do not match calculated net pay")
    result = approve_payroll(run_id, PayrollRunApproval(action="paid", remarks=data.remarks), db, user)
    # Existing payroll reimbursement service links claims; payment evidence now closes their lifecycle.
    from app.models.expense import ExpenseClaim
    from datetime import datetime, timezone
    for claim in db.query(ExpenseClaim).filter(ExpenseClaim.payroll_run_id == run_id, ExpenseClaim.status == "finance_approved").all():
        line = next((line for line in lines if line.employee_id == claim.employee_id), None)
        if line:
            claim.status = "reimbursed"; claim.reimbursed_at = datetime.now(timezone.utc); claim.reimbursement_reference = line.utr_number
    db.commit()
    return result
