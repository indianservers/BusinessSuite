from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_db
from app.models.statutory_compliance import (
    Form16Document,
    PayrollLegalEntity,
    StatutoryComplianceEvent,
    StatutoryPortalSubmission,
    TDSReturnFiling,
)
from app.models.user import User
from app.schemas.statutory_compliance import (
    ComplianceEventUpdate,
    FilingSubmit,
    Form16DocumentCreate,
    Form16DocumentSchema,
    Form16Publish,
    PayrollLegalEntityCreate,
    PayrollLegalEntitySchema,
    PortalSubmissionSubmit,
    StatutoryComplianceEventCreate,
    StatutoryComplianceEventSchema,
    StatutoryPortalSubmissionCreate,
    StatutoryPortalSubmissionSchema,
    TDSReturnFilingCreate,
    TDSReturnFilingSchema,
)

router = APIRouter(prefix="/statutory-compliance", tags=["Statutory Compliance"])


class StatutoryCalculationRequest(BaseModel):
    basic_salary: Decimal = Field(ge=0)
    gross_salary: Decimal = Field(ge=0)
    state: str = "Karnataka"
    pf_wage_cap: Decimal = Decimal("15000")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _professional_tax(monthly_gross: Decimal, state: str) -> Decimal:
    state_key = state.strip().lower()
    amount = Decimal(monthly_gross)
    if state_key in {"karnataka", "ka"}:
        return Decimal("200") if amount >= Decimal("25000") else Decimal("0")
    if state_key in {"maharashtra", "mh"}:
        if amount <= Decimal("7500"):
            return Decimal("0")
        if amount <= Decimal("10000"):
            return Decimal("175")
        return Decimal("200")
    if state_key in {"telangana", "ts", "andhra pradesh", "ap"}:
        if amount <= Decimal("15000"):
            return Decimal("0")
        if amount <= Decimal("20000"):
            return Decimal("150")
        return Decimal("200")
    if state_key in {"tamil nadu", "tn"}:
        if amount <= Decimal("21000"):
            return Decimal("0")
        return Decimal("208")
    if state_key in {"west bengal", "wb"}:
        if amount <= Decimal("10000"):
            return Decimal("0")
        if amount <= Decimal("15000"):
            return Decimal("110")
        if amount <= Decimal("25000"):
            return Decimal("130")
        if amount <= Decimal("40000"):
            return Decimal("150")
        return Decimal("200")
    return Decimal("0")


@router.post("/calculate")
def calculate_statutory_contributions(
    data: StatutoryCalculationRequest,
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    pf_wage = min(data.basic_salary, data.pf_wage_cap)
    employee_pf = _money(pf_wage * Decimal("0.12"))
    employer_pf = _money(pf_wage * Decimal("0.12"))
    esi_eligible = data.gross_salary <= Decimal("21000")
    employee_esi = _money(data.gross_salary * Decimal("0.0075")) if esi_eligible else Decimal("0.00")
    employer_esi = _money(data.gross_salary * Decimal("0.0325")) if esi_eligible else Decimal("0.00")
    professional_tax = _money(_professional_tax(data.gross_salary, data.state))
    return {
        "pf": {
            "wage": float(_money(pf_wage)),
            "employee_contribution": float(employee_pf),
            "employer_contribution": float(employer_pf),
            "rate_employee": 12,
            "rate_employer": 12,
        },
        "esi": {
            "eligible": esi_eligible,
            "threshold": 21000,
            "employee_contribution": float(employee_esi),
            "employer_contribution": float(employer_esi),
            "rate_employee": 0.75,
            "rate_employer": 3.25,
        },
        "professional_tax": {
            "state": data.state,
            "monthly_amount": float(professional_tax),
        },
        "total_employee_deduction": float(_money(employee_pf + employee_esi + professional_tax)),
        "total_employer_contribution": float(_money(employer_pf + employer_esi)),
    }


@router.get("/pt-slabs")
def professional_tax_slabs(current_user: User = Depends(RequirePermission("payroll_view"))):
    return {
        "Karnataka": [{"from": 25000, "monthly_tax": 200}],
        "Maharashtra": [{"from": 7501, "to": 10000, "monthly_tax": 175}, {"from": 10001, "monthly_tax": 200}],
        "Telangana": [{"from": 15001, "to": 20000, "monthly_tax": 150}, {"from": 20001, "monthly_tax": 200}],
        "Tamil Nadu": [{"from": 21001, "monthly_tax": 208}],
        "West Bengal": [
            {"from": 10001, "to": 15000, "monthly_tax": 110},
            {"from": 15001, "to": 25000, "monthly_tax": 130},
            {"from": 25001, "to": 40000, "monthly_tax": 150},
            {"from": 40001, "monthly_tax": 200},
        ],
    }


@router.post("/legal-entities", response_model=PayrollLegalEntitySchema, status_code=201)
def create_legal_entity(data: PayrollLegalEntityCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if data.is_default:
        db.query(PayrollLegalEntity).update({PayrollLegalEntity.is_default: False})
    item = PayrollLegalEntity(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/legal-entities", response_model=List[PayrollLegalEntitySchema])
def list_legal_entities(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(PayrollLegalEntity).filter(PayrollLegalEntity.is_active == True).order_by(PayrollLegalEntity.legal_name).all()


@router.post("/form16", response_model=Form16DocumentSchema, status_code=201)
def generate_form16(data: Form16DocumentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    document = Form16Document(
        **data.model_dump(),
        status="Generated",
        generated_by=current_user.id,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.put("/form16/{document_id}/publish", response_model=Form16DocumentSchema)
def publish_form16(document_id: int, data: Form16Publish, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    document = db.query(Form16Document).filter(Form16Document.id == document_id).first()
    if not document:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Form 16 document not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(document, field, value)
    document.status = "Published"
    document.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)
    return document


@router.get("/form16", response_model=List[Form16DocumentSchema])
def list_form16(
    financial_year: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(Form16Document)
    if financial_year:
        query = query.filter(Form16Document.financial_year == financial_year)
    if employee_id:
        query = query.filter(Form16Document.employee_id == employee_id)
    return query.order_by(Form16Document.id.desc()).all()


@router.post("/tds-filings", response_model=TDSReturnFilingSchema, status_code=201)
def create_tds_filing(data: TDSReturnFilingCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    filing = TDSReturnFiling(**data.model_dump(), status="Draft")
    db.add(filing)
    db.commit()
    db.refresh(filing)
    return filing


@router.put("/tds-filings/{filing_id}/submit", response_model=TDSReturnFilingSchema)
def submit_tds_filing(filing_id: int, data: FilingSubmit, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    from fastapi import HTTPException
    filing = db.query(TDSReturnFiling).filter(TDSReturnFiling.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="TDS filing not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(filing, field, value)
    filing.status = "Filed"
    filing.filed_at = datetime.now(timezone.utc)
    filing.filed_by = current_user.id
    db.commit()
    db.refresh(filing)
    return filing


@router.post("/portal-submissions", response_model=StatutoryPortalSubmissionSchema, status_code=201)
def create_portal_submission(data: StatutoryPortalSubmissionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    submission = StatutoryPortalSubmission(**data.model_dump())
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/portal-submissions", response_model=List[StatutoryPortalSubmissionSchema])
def list_portal_submissions(
    legal_entity_id: Optional[int] = Query(None),
    portal_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    period_month: Optional[int] = Query(None, ge=1, le=12),
    period_year: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(StatutoryPortalSubmission)
    if legal_entity_id:
        query = query.filter(StatutoryPortalSubmission.legal_entity_id == legal_entity_id)
    if portal_type:
        query = query.filter(StatutoryPortalSubmission.portal_type == portal_type)
    if status:
        query = query.filter(StatutoryPortalSubmission.status == status)
    if period_month:
        query = query.filter(StatutoryPortalSubmission.period_month == period_month)
    if period_year:
        query = query.filter(StatutoryPortalSubmission.period_year == period_year)
    return (
        query.order_by(
            StatutoryPortalSubmission.period_year.desc(),
            StatutoryPortalSubmission.period_month.desc(),
            StatutoryPortalSubmission.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.put("/portal-submissions/{submission_id}/submit", response_model=StatutoryPortalSubmissionSchema)
def submit_portal_submission(submission_id: int, data: PortalSubmissionSubmit, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    from fastapi import HTTPException
    submission = db.query(StatutoryPortalSubmission).filter(StatutoryPortalSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Portal submission not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(submission, field, value)
    submission.status = "Submitted"
    submission.submitted_at = datetime.now(timezone.utc)
    submission.submitted_by = current_user.id
    db.commit()
    db.refresh(submission)
    return submission


@router.post("/calendar", response_model=StatutoryComplianceEventSchema, status_code=201)
def create_calendar_event(data: StatutoryComplianceEventCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    event = StatutoryComplianceEvent(**data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/calendar", response_model=List[StatutoryComplianceEventSchema])
def list_calendar_events(
    status: Optional[str] = Query(None),
    compliance_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(StatutoryComplianceEvent)
    if status:
        query = query.filter(StatutoryComplianceEvent.status == status)
    if compliance_type:
        query = query.filter(StatutoryComplianceEvent.compliance_type == compliance_type)
    return query.order_by(StatutoryComplianceEvent.due_date).all()


@router.put("/calendar/{event_id}", response_model=StatutoryComplianceEventSchema)
def update_calendar_event(event_id: int, data: ComplianceEventUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    from fastapi import HTTPException
    event = db.query(StatutoryComplianceEvent).filter(StatutoryComplianceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Compliance event not found")
    event.status = data.status
    event.remarks = data.remarks
    if data.status.lower() in {"completed", "filed", "paid"}:
        event.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event
