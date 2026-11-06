"""Company-scoped payroll presentation and financial-year policy."""
from datetime import date
from fastapi import HTTPException
from app.models.payroll import PayrollDeliveryProfile

DEFAULT_TEMPLATE = {"layout": "standard", "show_employee_code": True, "show_working_days": True,
                    "show_ytd": True, "show_employer_contributions": True, "show_reimbursements": True,
                    "show_department": True, "footer": "Confidential - employee payslip"}


def company_for(user):
    from app.apps.srm.services.commercial import tenant
    company_id = tenant(user)
    if not company_id:
        raise HTTPException(403, "Select a company to configure payroll")
    return company_id


def profile_for(db, company_id, create=False):
    profile = db.query(PayrollDeliveryProfile).filter_by(company_id=company_id).first() if company_id else None
    if profile is None and create:
        profile = PayrollDeliveryProfile(company_id=company_id, ytd_basis="financial", fy_start_month=4,
            regular_template=dict(DEFAULT_TEMPLATE), settlement_template=dict(DEFAULT_TEMPLATE), branding={})
        db.add(profile)
        db.flush()
    return profile


def year_window(on_date, basis="financial", start_month=4):
    month = 1 if basis == "calendar" else start_month
    start_year = on_date.year if on_date.month >= month else on_date.year - 1
    start, end = date(start_year, month, 1), date(start_year + 1, month, 1)
    label = str(start_year) if basis == "calendar" else f"{start_year}-{str(start_year + 1)[-2:]}"
    return start, end, label


def record_policy(db, record):
    employee = record.employee
    company_id = record.payroll_run.company_id or (employee.branch.company_id if employee and employee.branch else None)
    profile = profile_for(db, company_id)
    basis = profile.ytd_basis if profile else "financial"
    month = profile.fy_start_month if profile else 4
    start, end, label = year_window(date(record.payroll_run.year, record.payroll_run.month, 1), basis, month)
    return {"basis": basis, "start": start, "end": end, "label": label, "company_id": company_id, "profile": profile}


def template_for(profile, kind="regular"):
    values = (profile.settlement_template if kind == "settlement" else profile.regular_template) if profile else {}
    return {**DEFAULT_TEMPLATE, **(values or {})}


def audit_delivery(db, user, company_id, action, detail, before=None, after=None):
    # Configuration has no payroll-run parent. Record its explicit company in
    # the immutable audit ledger instead of creating an unowned run-audit row.
    from app.access.models import AccessAudit
    db.add(AccessAudit(actor_id=user.id, company_id=company_id, operation=action, reason=detail, before_json=before, after_json=after, outcome="success"))
