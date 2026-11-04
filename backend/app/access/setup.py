"""Live, company-scoped setup readiness. No cached completion flags."""
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, func, cast, String
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.company import Company, Branch
from app.models.user import User
from app.access.models import AccessMembership, AccessPolicy
from app.branches.models import BranchLifecycle, BranchOwnership

router = APIRouter(prefix="/setup", tags=["Company setup"])


def valid_defaults(company):
    if not company or not re.fullmatch(r"[A-Z]{3}", company.default_currency or ""):
        return False
    if not 1 <= (company.fiscal_year_start_month or 0) <= 12:
        return False
    try:
        ZoneInfo(company.default_timezone or "")
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def essentials(db, company_id):
    # Explicit company predicates and Core queries are deliberate: setup is
    # company-wide metadata, including when the selected branch is missing.
    conn = db.connection()
    company = conn.execute(select(Company.__table__).where(Company.id == company_id)).first()
    identity = bool(company and company.is_active and (company.name or "").strip()
                    and (company.country or "").strip()
                    and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", company.email or ""))
    branches = bool(conn.execute(select(Branch.id).where(
        Branch.company_id == company_id, Branch.is_active.is_(True),
        ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))),
    ).limit(1)).first())
    # Global administrators remain a recovery path even before a company has
    # its first delegated administrator.
    administrator = bool(conn.execute(select(User.id).where(User.is_active.is_(True), or_(
        User.is_superuser.is_(True), User.id.in_(select(AccessMembership.user_id).where(
            AccessMembership.company_id == company_id, AccessMembership.active.is_(True),
            AccessMembership.is_admin.is_(True), ~AccessMembership.user_id.in_(
                select(AccessPolicy.user_id).where(AccessPolicy.company_id == company_id, AccessPolicy.status != "active")))))).limit(1)).first())
    return [
        dict(id="company", title="Company details", description="Business name, country and official email", ready=identity, destination="/settings/company-profile"),
        dict(id="branch", title="Active branch", description="Create or restore at least one branch", ready=branches, destination="/settings/branches"),
        dict(id="defaults", title="Business defaults", description="Currency, timezone and financial-year start month", ready=valid_defaults(company), destination="/settings/business-defaults"),
        dict(id="administrator", title="Administrator", description="An active company or global administrator", ready=administrator, destination="/settings/users"),
    ]


# Shared business APIs are gated by default. Explicit setup resources, reads,
# previews and account recovery stay available while essentials are incomplete.
BUSINESS_ROOTS = {
    "employees", "attendance", "leave", "payroll", "expenses", "recruitment",
    "performance", "training", "assets", "letters", "workbench",
}
MODULE_SETUP_RESOURCES = {
    "crm": {"settings", "pipelines", "pipeline-stages", "custom-fields", "approval-rules", "scoring-rules", "territories", "webhooks"},
    "pms": {"settings", "workspaces", "statuses", "workflows", "templates", "roles"},
    "fam": {"settings", "financial-years", "ledger-groups", "ledgers", "cost-centers", "branches", "voucher-types", "payment-modes", "tax-settings"},
    "srm": {"settings", "numbering", "payment-terms", "tax-rules"},
    "approvals": {"policies", "delegations", "settings"},
    "communication": {"settings", "channels", "senders", "templates", "providers", "connections", "webhooks"},
}
ATTENDANCE_SETUP = {"shifts", "weekly-offs", "roster", "holidays", "biometric", "geo", "locks", "policies"}
PAYROLL_SETUP = {"components", "salary-components", "component-categories", "categories", "structures", "settings", "policies", "schedules", "setup", "statutory"}


def module_requirements(db, company_id, modules):
    """Only check installed/enabled modules; legal zero-holiday calendars are OK.

    Domain validators still check the actual selected record, approver, period,
    tax rules and sender credentials at the operation boundary.
    """
    conn = db.connection()
    items = []
    def add(key, title, description, destination, query):
        items.append(dict(id=key, title=title, description=description,
                          destination=destination, ready=bool(conn.execute(query.limit(1)).first())))
    if "hrms" in modules:
        from app.models.company import Department, Designation
        departments = select(Department.id).join(Branch, Department.branch_id == Branch.id).where(
            Branch.company_id == company_id, Branch.is_active.is_(True), Department.is_active.is_(True))
        add("departments", "Departments", "Before adding employees", "/settings/departments", departments)
        designations = select(Designation.id).join(Department, Designation.department_id == Department.id).join(
            Branch, Department.branch_id == Branch.id).where(Branch.company_id == company_id,
            Branch.is_active.is_(True), Department.is_active.is_(True), Designation.is_active.is_(True))
        add("designations", "Designations", "Before adding employees", "/settings/designations", designations)
        from app.models.attendance import Shift
        from app.models.leave import LeaveType
        from app.models.payroll import SalaryComponent
        for key, title, description, destination, model in [
            ("shifts", "Work shifts", "Before attendance processing", "/settings/shifts", Shift),
            ("leave-types", "Leave types", "Before applying for leave", "/settings/leaveTypes", LeaveType),
            ("salary-components", "Salary components", "Before payroll processing", "/settings/salaryComponents", SalaryComponent),
        ]:
            from app.branches.catalog import SHARED
            from app.models.security_boundary import SecurityResourceOwnership
            if model.__tablename__ in SHARED:
                owned = model.id.in_(select(SecurityResourceOwnership.resource_id).where(
                    SecurityResourceOwnership.resource_table == model.__tablename__,
                    SecurityResourceOwnership.company_id == company_id))
            else:
                owned = cast(model.id, String).in_(select(BranchOwnership.resource_key).where(
                    BranchOwnership.resource_table == model.__tablename__, BranchOwnership.company_id == company_id))
            add(key, title, description, destination, select(model.id).where(model.is_active.is_(True), owned))
    if "crm" in modules:
        from app.apps.crm.models import CRMPipeline, CRMPipelineStage
        add("pipeline", "Sales pipeline & stages", "Before creating deals", "/settings/crm-pipelines",
            select(CRMPipelineStage.id).join(CRMPipeline).where(CRMPipeline.organization_id == company_id,
            CRMPipeline.active.is_(True), CRMPipeline.deleted_at.is_(None), CRMPipelineStage.active.is_(True),
            CRMPipelineStage.deleted_at.is_(None)))
    if "project_management" in modules:
        from app.apps.project_management.models import PMSWorkspace
        add("workspace", "Project workspace", "Before creating projects", "/pms/workspaces",
            select(PMSWorkspace.id).where(PMSWorkspace.organization_id == company_id))
    if "fam" in modules:
        from datetime import date
        from app.apps.fam.models import FAMFinancialYear, FAMLedger
        add("financial-year", "Open financial year", "Before posting accounting entries", "/settings/financial-years",
            select(FAMFinancialYear.id).where(FAMFinancialYear.company_id == company_id,
            FAMFinancialYear.status == "open", FAMFinancialYear.start_date <= date.today(), FAMFinancialYear.end_date >= date.today()))
        add("ledgers", "Accounting ledgers", "Before posting accounting entries", "/fam/ledgers",
            select(FAMLedger.id).where(FAMLedger.company_id == company_id))
    if "srm" in modules:
        from app.apps.srm.models import SRMWarehouse
        add("warehouse", "Active warehouse", "Before inventory movements", "/srm/inventory/warehouses",
            select(SRMWarehouse.id).where(SRMWarehouse.organization_id == company_id, SRMWarehouse.active.is_(True)))
    return items


def optional_requirements(db, company_id, modules):
    """Recommendations never participate in business-write enforcement."""
    specs = []
    if "crm" in modules:
        from app.apps.crm.models import CRMLeadScoringRule, CRMCustomField
        specs += [
            ("crm", "scoring", "Prioritize leads", "Add active scoring rules to help your team qualify leads.", "/settings/crm-scoring", CRMLeadScoringRule, CRMLeadScoringRule.is_active.is_(True)),
            ("crm", "custom-fields", "Capture your sales details", "Add custom fields when your sales process needs extra information.", "/settings/crm", CRMCustomField, CRMCustomField.is_active.is_(True) & CRMCustomField.deleted_at.is_(None)),
        ]
    if "srm" in modules:
        from app.apps.srm.models import SRMProductCategory
        specs.append(("srm", "categories", "Organize your catalog", "Group inventory products into active categories for easier browsing.", "/srm/inventory/stock-groups", SRMProductCategory, SRMProductCategory.active.is_(True)))
    if "project_management" in modules:
        from app.apps.project_management.models import PMSCustomField
        specs.append(("project_management", "custom-fields", "Tailor project tracking", "Add custom fields when tasks need information beyond the standard fields.", "/pms/custom-fields", PMSCustomField, PMSCustomField.archived.is_(False)))
    if "hrms" in modules:
        from datetime import date
        from app.models.attendance import Holiday
        year = date.today().year
        specs.append(("hrms", "holidays", "Plan your holiday calendar", "If your company observes holidays, add this year's dates for attendance planning. A calendar without holidays is also valid.", "/settings/holidays", Holiday,
                      Holiday.is_active.is_(True) & (Holiday.holiday_date >= date(year, 1, 1)) & (Holiday.holiday_date <= date(year, 12, 31))))
    if "fam" in modules:
        from app.apps.fam.models import FAMCostCenter, FAMPaymentMode
        specs += [
            ("fam", "cost-centers", "Track costs by team or activity", "Add active cost centers when you need separate expense and profitability reporting.", "/settings/cost-centers", FAMCostCenter, FAMCostCenter.active.is_(True)),
            ("fam", "payment-modes", "Configure payment methods", "Add active payment modes to standardize how receipts and payments are recorded.", "/settings/payment-modes", FAMPaymentMode, FAMPaymentMode.active.is_(True)),
        ]
    items = []
    for module, key, title, description, destination, model, predicate in specs:
        if hasattr(model, "company_id"):
            scope = model.company_id == company_id
        elif hasattr(model, "organization_id"):
            scope = model.organization_id == company_id
        else:
            scope = cast(model.id, String).in_(select(BranchOwnership.resource_key).where(
                BranchOwnership.resource_table == model.__tablename__, BranchOwnership.company_id == company_id))
        items.append(dict(id=f"{module}-{key}", module=module, required=False, title=title,
                          description=description, destination=destination,
                          ready=bool(db.connection().execute(select(model.id).where(scope, predicate).limit(1)).first())))
    return items



def operation_requirements(method, path):
    path = path.rstrip("/")
    if method == "POST":
        if path == "/api/v1/employees": return "hrms", {"departments", "designations"}
        if path == "/api/v1/leave/apply": return "hrms", {"leave-types"}
        if path.startswith("/api/v1/attendance/compute/") or path == "/api/v1/attendance/bulk-entry": return "hrms", {"shifts"}
        if path in {"/api/v1/payroll/run", "/api/v1/payroll/runs"} or re.fullmatch(r"/api/v1/payroll/runs/\d+/(?:worksheet/)?process", path):
            return "hrms", {"salary-components"}
        if path == "/api/v1/crm/deals": return "crm", {"pipeline"}
        if path == "/api/v1/project-management/projects": return "project_management", {"workspace"}
        if re.fullmatch(r"/api/v1/fam/vouchers/\d+/post", path): return "fam", {"financial-year", "ledgers"}
        if path in {"/api/v1/srm/inventory/" + action for action in ("opening-stock", "stock-movements", "stock-transfers", "stock-adjustments")}:
            return "srm", {"warehouse"}
    return None, set()


def is_business_write(method, path):
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    parts = path.removeprefix("/api/v1/").strip("/").split("/")
    if parts[0] == "project-management":
        parts[0] = "pms"
    if parts[:2] == ["power-apps", "approvals"]:
        parts = parts[1:]
    root = parts[0]
    if parts[-1] in {"preview", "search", "validate", "lookup", "export"}:
        return False
    child = parts[1] if len(parts) > 1 else ""
    if root == "crm" and child == "lead-management":
        return len(parts) > 2 and parts[2] in {"leads", "imports"}
    if root == "srm" and child == "inventory":
        return len(parts) > 2 and parts[2] not in {"categories", "warehouses", "settings", "units"}
    if root == "srm" and child in {"procurement", "handoff"}:
        return True
    if root == "attendance" and child in ATTENDANCE_SETUP:
        return False
    if root == "leave" and child in {"types", "policies", "settings"}:
        return False
    if root == "payroll" and child in PAYROLL_SETUP:
        return False
    return root in BUSINESS_ROOTS or (root in MODULE_SETUP_RESOURCES and child not in MODULE_SETUP_RESOURCES[root])


def enforce_setup(db, user, request):
    if not is_business_write(request.method, request.url.path):
        return
    checks = essentials(db, user.organization_id)
    module, required = operation_requirements(request.method, request.url.path)
    if module:
        checks += [i for i in module_requirements(db, user.organization_id, {module}) if i["id"] in required]
    missing = [item["title"] for item in checks if not item["ready"]]
    if missing:
        raise HTTPException(409, "Complete company setup before continuing: " + ", ".join(missing),
                            headers={"X-Suite-Setup-Required": "1"})


@router.get("")
def readiness(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.access.settings_hub import context, can_edit_company, allows, OPTIONS
    ctx = context(db, user)
    items = essentials(db, user.organization_id)
    for item in items:
        key = item["destination"].rsplit("/", 1)[-1]
        option = next(o for o in OPTIONS if o[0] == key)
        item["canRepair"] = bool(can_edit_company(ctx) if key in {"company-profile", "business-defaults"} else allows(option, ctx))
    modules = {key for key, grant in ctx["grants"].items() if grant.get("enabled")}
    module_items = module_requirements(db, user.organization_id, modules)
    module_by_id = {"pipeline": "crm", "workspace": "project_management", "warehouse": "srm", "financial-year": "fam", "ledgers": "fam"}
    for item in items:
        item.update(module="company", required=True)
    for item in module_items:
        item.update(module=module_by_id.get(item["id"], "hrms"), required=True)
    recommendations = optional_requirements(db, user.organization_id, modules)
    for item in module_items + recommendations:
        key = item["destination"].rsplit("/", 1)[-1]
        option = next((o for o in OPTIONS if o[0] == key), None)
        item["canRepair"] = bool(allows(option, ctx) if option else ctx["admin"])
    return {"companyId": user.organization_id, "ready": all(i["ready"] for i in items), "items": items, "moduleItems": module_items, "recommendations": recommendations}


def protect_last_company_admin(db, membership, active, is_admin):
    if not membership or not membership.active or not membership.is_admin or (active and is_admin):
        return
    # Lock the company to serialize competing administrator removals.
    conn = db.connection()
    conn.execute(select(Company.id).where(Company.id == membership.company_id).with_for_update()).first()
    remaining = conn.execute(select(func.count()).select_from(AccessMembership).join(
        User, User.id == AccessMembership.user_id).where(
        AccessMembership.company_id == membership.company_id,
        AccessMembership.id != membership.id, AccessMembership.active.is_(True),
        AccessMembership.is_admin.is_(True), User.is_active.is_(True),
        ~AccessMembership.user_id.in_(select(AccessPolicy.user_id).where(
            AccessPolicy.company_id == membership.company_id, AccessPolicy.status != "active")))).scalar_one()
    if not remaining:
        raise HTTPException(409, "Keep at least one active company administrator. Assign a replacement first.")


def protect_administrator_account(db, target):
    """Account suspension can affect administrator access in multiple companies."""
    if target.is_superuser and target.is_active:
        conn = db.connection()
        # Match the access console's stable lock order for global admins.
        conn.execute(select(User.id).where(User.is_superuser.is_(True)).order_by(User.id).with_for_update()).all()
        remaining = conn.execute(select(User.id).where(User.is_superuser.is_(True),
            User.is_active.is_(True), User.id != target.id).limit(1)).first()
        if not remaining:
            raise HTTPException(409, "Keep at least one active global administrator. Assign a replacement first.")
    memberships = db.connection().execute(select(AccessMembership.__table__).where(
        AccessMembership.user_id == target.id, AccessMembership.active.is_(True),
        AccessMembership.is_admin.is_(True)).order_by(AccessMembership.company_id)).all()
    for membership in memberships:
        protect_last_company_admin(db, membership, False, False)
