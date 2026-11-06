"""Company-owned starter masters. Add missing records without replacing policy."""
from datetime import time
from sqlalchemy import select, func, or_
from app.models.company import Company, Branch, Department, Designation
from app.models.leave import LeaveType
from app.models.payroll import SalaryComponent
from app.models.attendance import Shift
from app.models.security_boundary import SecurityResourceOwnership
from app.branches.models import BranchOwnership
from app.branches.catalog import SHARED

LEAD_SOURCES = ["Manual", "Website", "Referral", "Social Media", "Email", "Phone", "Cold Call", "Email Campaign", "Event", "Partner", "WhatsApp", "Other"]
CATALOG = [
    {"key": "hrms", "title": "People & HR", "values": ["Casual Leave · 12 days/year", "Sick Leave · 6 days/year", "Earned Leave · 15 days/year", "Basic Salary", "House Rent Allowance", "Transport Allowance", "Other Deduction", "General department", "Team Member and Manager designations", "General shift · 09:00–18:00, 8 working hours"], "destination": "/settings/leaveTypes"},
    {"key": "crm", "title": "CRM", "values": ["Sales pipeline: Qualification → Proposal → Negotiation → Won / Lost", *LEAD_SOURCES], "destination": "/settings/crm-lead-sources"},
    {"key": "fam", "title": "Finance", "values": ["Cash", "Bank Transfer", "Card", "Cheque"], "destination": "/settings/payment-modes"},
]


def lead_sources(db, company_id):
    from app.apps.crm.lead_models import CRMLeadManagementConfig
    table = CRMLeadManagementConfig.__table__
    values = db.connection().execute(select(table.c.settings_json).where(table.c.organization_id == company_id)).scalar()
    return (values or {}).get("sources", list(LEAD_SOURCES))


def populate(db, company_id, branch_id, modules):
    """Caller authorizes modules and commits; a company lock serializes retries."""
    conn = db.connection()
    conn.execute(select(Company.id).where(Company.id == company_id).with_for_update()).one()
    branch = conn.execute(select(Branch.id).where(Branch.id == branch_id, Branch.company_id == company_id, Branch.is_active.is_(True))).first()
    if not branch:
        raise ValueError("Choose an active branch in this company")
    counts = {}

    def scope(model):
        table = model.__table__
        if "organization_id" in table.c:
            return table.c.organization_id == company_id
        if "company_id" in table.c:
            return table.c.company_id == company_id
        owned = SecurityResourceOwnership.__table__
        return table.c.id.in_(select(owned.c.resource_id).where(owned.c.resource_table == table.name, owned.c.company_id == company_id))

    def add(model, name, *, within=None, **values):
        table = model.__table__
        identity = func.lower(table.c.name) == name.casefold()
        if "code" in values:
            identity = or_(identity, table.c.code == values["code"])
        query = select(table.c.id).where(scope(model), identity)
        if within is not None:
            query = query.where(within)
        existing = conn.execute(query.limit(1)).scalar()
        if existing is not None:
            return existing
        if "organization_id" in table.c:
            values["organization_id"] = company_id
        elif "company_id" in table.c:
            values["company_id"] = company_id
        ident = conn.execute(table.insert().values(name=name, **values).returning(table.c.id)).scalar_one()
        conn.execute(SecurityResourceOwnership.__table__.insert().values(resource_table=table.name, resource_id=ident, company_id=company_id))
        if table.name not in SHARED:
            conn.execute(BranchOwnership.__table__.insert().values(resource_table=table.name, resource_key=str(ident), company_id=company_id, branch_id=branch_id, source="starter-values"))
        counts[table.name] = counts.get(table.name, 0) + 1
        return ident

    if "hrms" in modules:
        for name, code, days, color in [("Casual Leave", "CL", 12, "#2563EB"), ("Sick Leave", "SL", 6, "#16A34A"), ("Earned Leave", "EL", 15, "#7C3AED")]:
            add(LeaveType, name, code=f"C{company_id}-{code}", days_allowed=days, accrual_frequency="annual", color=color,
                description="Starter allowance. Edit to match your company policy before allocating balances.")
        for order, (name, code, kind) in enumerate([("Basic Salary", "BASIC", "Earning"), ("House Rent Allowance", "HRA", "Earning"), ("Transport Allowance", "TRANSPORT", "Earning"), ("Other Deduction", "DEDUCT", "Deduction")]):
            add(SalaryComponent, name, code=f"C{company_id}-{code}", component_type=kind, amount=0,
                calculation_type="Fixed", payslip_group="Deductions" if kind == "Deduction" else "Earnings",
                display_sequence=(order + 1) * 10, description="Starter component. Set amounts and review tax treatment before payroll.")
        department = add(Department, "General", code="GENERAL", branch_id=branch_id, within=Department.branch_id == branch_id)
        for name, code in [("Team Member", "MEMBER"), ("Manager", "MANAGER")]:
            add(Designation, name, code=code, department_id=department, within=Designation.department_id == department)
        add(Shift, "General", code="GENERAL", start_time=time(9), end_time=time(18), working_hours=8)
    if "crm" in modules:
        from app.apps.crm.models import CRMPipeline, CRMPipelineStage
        from app.apps.crm.lead_models import CRMLeadManagementConfig
        # Leave a configured or deliberately disabled sales process intact.
        if not conn.execute(select(CRMPipeline.id).where(CRMPipeline.organization_id == company_id).limit(1)).first():
            pipeline = add(CRMPipeline, "Sales pipeline", is_default=True)
            for position, (name, probability, kind) in enumerate([("Qualification", 20, "open"), ("Proposal", 50, "open"), ("Negotiation", 75, "open"), ("Won", 100, "won"), ("Lost", 0, "lost")]):
                add(CRMPipelineStage, name, pipeline_id=pipeline, probability=probability, position=position, order_index=position,
                    stage_type=kind, is_won=kind == "won", is_lost=kind == "lost", within=CRMPipelineStage.pipeline_id == pipeline)
        config = CRMLeadManagementConfig.__table__
        settings = conn.execute(select(config.c.settings_json).where(config.c.organization_id == company_id)).first()
        if settings is None:
            conn.execute(config.insert().values(organization_id=company_id, settings_json={"sources": LEAD_SOURCES}))
            counts[config.name] = 1
        elif "sources" not in (settings.settings_json or {}):
            conn.execute(config.update().where(config.c.organization_id == company_id).values(settings_json={**(settings.settings_json or {}), "sources": LEAD_SOURCES}))
    if "fam" in modules:
        from app.apps.fam.models import FAMPaymentMode
        for name, kind in [("Cash", "cash"), ("Bank Transfer", "neft"), ("Card", "card"), ("Cheque", "cheque")]:
            add(FAMPaymentMode, name, type=kind)
    return counts
