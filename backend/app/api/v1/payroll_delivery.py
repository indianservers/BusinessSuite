"""HR-visible financial year, payslip branding and salary payout operations."""
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Literal
import base64
import hashlib
import uuid

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db, RequirePermission, get_current_user
from app.core.storage import persist_file, FileResponse
from app.models.payroll import PayrollPaymentBatch, PayrollPaymentLine, PayrollRecord, PayrollRun, PayrollPayoutAttempt, FullFinalSettlement
from app.models.employee import Employee
from app.services.payroll_delivery import company_for, profile_for, template_for, DEFAULT_TEMPLATE, audit_delivery

router = APIRouter(prefix="/payroll/delivery", tags=["Payroll Delivery"])


def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256((settings.SECRET_KEY + ":payroll-payouts").encode()).digest()))


class TemplateInput(BaseModel):
    layout: Literal["standard", "compact", "professional"] = "standard"
    show_employee_code: bool = True
    show_working_days: bool = True
    show_ytd: bool = True
    show_employer_contributions: bool = True
    show_reimbursements: bool = True
    show_department: bool = True
    footer: str = Field("Confidential - employee payslip", max_length=300)


class ProfileInput(BaseModel):
    ytd_basis: Literal["financial", "calendar"] = "financial"
    fy_start_month: int = Field(4, ge=1, le=12)
    regular_template: TemplateInput = Field(default_factory=TemplateInput)
    settlement_template: TemplateInput = Field(default_factory=TemplateInput)


class PayoutConfigInput(BaseModel):
    key_id: str = Field(min_length=8, max_length=120, pattern=r"^rzp_(test|live)_[A-Za-z0-9]+$")
    key_secret: str = Field("", max_length=250)
    debit_account: str = Field(min_length=5, max_length=120, pattern=r"^[0-9]+$")
    mode: Literal["test", "live"] = "test"


def describe(profile, user=None):
    branding = profile.branding or {} if profile else {}
    from app.access.catalog import permission_names
    permissions = permission_names(user) if user else set()
    return {"can_manage": bool(user and (user.is_superuser or "payroll_run" in permissions)),
        "can_approve": bool(user and (user.is_superuser or "payroll_approve" in permissions)),
        "ytd_basis": profile.ytd_basis if profile else "financial", "fy_start_month": profile.fy_start_month if profile else 4,
        "regular_template": template_for(profile), "settlement_template": template_for(profile, "settlement"),
        "logo_available": bool(branding.get("logo")), "signature_available": bool(branding.get("signature")),
        "form16_trust_configured": bool(branding.get("form16_trust_roots") or settings.FORM16_TRUST_ROOTS_PEM),
        "payout": {"provider": "razorpayx", "configured": bool(profile and profile.payout_key_id and profile.payout_secret_encrypted and profile.payout_account),
            "key_id": profile.payout_key_id if profile else "", "mode": profile.payout_mode if profile else "test",
            "debit_account_last4": profile.payout_account[-4:] if profile and profile.payout_account else ""}}


@router.get("/settings")
def read_settings(db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_view", "payroll_run", "payroll_approve"))):
    _require_hr(user)
    return describe(profile_for(db, company_for(user)), user)


@router.put("/settings")
def save_settings(data: ProfileInput, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_run"))):
    row = profile_for(db, company_for(user), True)
    row.ytd_basis, row.fy_start_month = data.ytd_basis, data.fy_start_month
    row.regular_template, row.settlement_template = data.regular_template.model_dump(), data.settlement_template.model_dump()
    row.updated_by = user.id
    audit_delivery(db, user, row.company_id, "payroll_presentation_updated", f"company={row.company_id}:basis={row.ytd_basis}:start_month={row.fy_start_month}")
    db.commit()
    return describe(row, user)


@router.put("/payout-connection")
def save_payout_connection(data: PayoutConfigInput, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_approve"))):
    if not data.key_id.startswith(f"rzp_{data.mode}_"):
        raise HTTPException(422, "API key and connection mode must match")
    row = profile_for(db, company_for(user), True)
    if not data.key_secret and (not row.payout_secret_encrypted or row.payout_key_id != data.key_id):
        raise HTTPException(422, "Provide the secret for the selected API key")
    row.payout_key_id, row.payout_account, row.payout_mode = data.key_id, data.debit_account, data.mode
    if data.key_secret:
        row.payout_secret_encrypted = cipher().encrypt(data.key_secret.encode()).decode()
    row.updated_by = user.id
    audit_delivery(db, user, row.company_id, "salary_payout_connection_updated", f"company={row.company_id}:mode={row.payout_mode}")
    db.commit()
    return describe(row, user)


@router.post("/branding/{kind}")
def upload_branding(kind: Literal["logo", "signature"], file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_run"))):
    from PIL import Image
    data = file.file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Branding image must be under 2 MB")
    try:
        picture = Image.open(BytesIO(data))
        if picture.format not in {"PNG", "JPEG"} or picture.width * picture.height > 12000000:
            raise ValueError()
        picture.verify()
    except Exception:
        raise HTTPException(422, "Upload a valid PNG or JPEG image") from None
    row = profile_for(db, company_for(user), True)
    path = Path(settings.UPLOAD_DIR) / "payroll-branding" / str(row.company_id) / f"{kind}_{uuid.uuid4().hex}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.open(BytesIO(data)).convert("RGBA").save(path, format="PNG")
    persist_file(str(path))
    row.branding = {**(row.branding or {}), kind: str(path.relative_to(settings.UPLOAD_DIR)).replace("\\", "/")}
    db.commit()
    return describe(row, user)


@router.get("/template-preview")
def template_preview(kind: Literal["regular", "settlement"] = "regular", db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_view", "payroll_run"))):
    _require_hr(user)
    from app.services.payslip_pdf import render_payslip
    from app.models.company import Company
    company_id = company_for(user)
    profile = profile_for(db, company_id)
    company = db.get(Company, company_id)
    path = Path(settings.UPLOAD_DIR) / "payroll-previews" / str(company_id) / f"{uuid.uuid4().hex}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"month": date.today().month, "year": date.today().year, "currency": "INR", "employee": {"employee_id": "SAMPLE-001", "first_name": "Sample", "last_name": "Employee"},
        "department": "Sample department", "working_days": 22, "paid_days": 22, "earnings": [{"component_name": "Basic", "amount": 40000}, {"component_name": "Allowance", "amount": 10000}],
        "deductions": [{"component_name": "Sample deduction", "amount": 2000}], "gross_salary": 50000, "total_deductions": 2000, "net_salary": 48000,
        "ytd": {"gross_salary": 100000, "total_deductions": 4000, "net_salary": 96000}, "ytd_period_label": "Financial year (sample)", "document_kind": kind, "preview": True}
    render_payslip(str(path), payload, company.name, template_for(profile, kind), profile.branding if profile else {})
    persist_file(str(path))
    return FileResponse(str(path), media_type="application/pdf", filename=f"{kind}-payslip-preview.pdf", headers={"Cache-Control": "private, no-store"})


def load_batch(db, batch_id):
    row = db.query(PayrollPaymentBatch).filter_by(id=batch_id).first()
    if not row:
        raise HTTPException(404, "Payment batch not found")
    return row


def _require_hr(user):
    from app.api.v1.form16 import _can_manage
    if not _can_manage(user):
        raise HTTPException(403, "HR payroll access is required for company payroll operations")


class PrepareInput(BaseModel):
    payroll_run_id: int = Field(gt=0)


@router.post("/payment-batches", status_code=201)
def prepare_payout_batch(data: PrepareInput, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_run"))):
    run = db.query(PayrollRun).filter_by(id=data.payroll_run_id, company_id=company_for(user), deleted_at=None).first()
    if not run:
        raise HTTPException(404, "Payroll run not found in the selected company")
    records = db.query(PayrollRecord).filter_by(payroll_run_id=run.id).all()
    batch = PayrollPaymentBatch(company_id=run.company_id, payroll_run_id=run.id, status="Generated", created_by=user.id,
        total_amount=sum((record.net_salary or Decimal("0") for record in records), Decimal("0")))
    db.add(batch)
    db.flush()
    for record in records:
        employee = db.get(Employee, record.employee_id)
        batch.lines.append(PayrollPaymentLine(payroll_record_id=record.id, employee_id=record.employee_id,
            net_amount=record.net_salary, bank_account=employee.account_number, ifsc=employee.ifsc_code, payment_status="Pending"))
    from app.services.salary_payouts import validate_batch
    validate_batch(db, batch)
    audit_delivery(db, user, run.company_id, "salary_payout_batch_prepared", f"batch={batch.id}:amount={batch.total_amount}")
    db.commit()
    return {"id": batch.id, "payroll_run_id": run.id, "total_amount": batch.total_amount, "status": batch.status}


@router.get("/payouts/{batch_id}")
def payout_status(batch_id: int, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_view", "payroll_run", "payroll_approve"))):
    _require_hr(user)
    batch = load_batch(db, batch_id)
    rows = db.query(PayrollPayoutAttempt).filter_by(batch_id=batch.id).all()
    return {"batch_id": batch.id, "status": batch.status, "approved_by": batch.approved_by,
        "total_amount": batch.total_amount, "items": [{"id": r.id, "record_id": r.payroll_record_id, "mode": r.mode,
            "status": r.status, "provider_id": r.provider_id, "utr": r.utr, "error": r.error} for r in rows]}


@router.post("/payouts/{batch_id}/approve")
def approve_payouts(batch_id: int, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_approve"))):
    from app.services.salary_payouts import validate_batch
    batch = load_batch(db, batch_id)
    validate_batch(db, batch)
    if batch.status != "Generated":
        raise HTTPException(409, "Only a generated payment batch can be approved")
    batch.approved_by = user.id
    batch.status = "Approved"
    audit_delivery(db, user, batch.payroll_run.company_id, "salary_payout_batch_approved", f"batch={batch.id}:amount={batch.total_amount}")
    db.commit()
    return payout_status(batch_id, db, user)


class SubmitInput(BaseModel):
    confirm_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    confirm_mode: Literal["test", "live"]


@router.post("/payouts/{batch_id}/submit")
def submit_payouts(batch_id: int, data: SubmitInput, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_approve"))):
    from app.services.salary_payouts import submit_batch
    batch = load_batch(db, batch_id)
    submit_batch(db, batch, data.confirm_total, data.confirm_mode, user)
    return payout_status(batch_id, db, user)


@router.post("/payouts/{batch_id}/reconcile")
def reconcile_payouts(batch_id: int, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_approve"))):
    from app.services.salary_payouts import reconcile_batch
    batch = load_batch(db, batch_id)
    reconcile_batch(db, batch, user)
    return payout_status(batch_id, db, user)


@router.post("/payouts/{batch_id}/attempts/{attempt_id}/prepare-retry")
def prepare_payout_retry(batch_id: int, attempt_id: int, data: SubmitInput, db: Session = Depends(get_db), user=Depends(RequirePermission("payroll_approve"))):
    from app.services.salary_payouts import prepare_failed_retry
    batch = load_batch(db, batch_id)
    prepare_failed_retry(db, batch, attempt_id, data.confirm_total, data.confirm_mode, user)
    return payout_status(batch_id, db, user)
