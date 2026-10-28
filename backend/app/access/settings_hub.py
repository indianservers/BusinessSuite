"""Server-owned settings discovery. Role labels never confer configuration access."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ConfigDict
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.access import service
from app.access.catalog import permission_names
from app.access.models import AccessMembership
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyUpdate

router = APIRouter(prefix="/settings", tags=["Shared Settings"])

# id, label, group, description, destination, module, any required permission, org scope
OPTIONS = [
    ("account", "My account & security", "Personal", "Your account details and password.", None, None, (), False),
    ("preferences", "Display preferences", "Personal", "Your theme and display density on this browser.", None, None, (), False),
    ("company-profile", "Company profile", "Company", "Company identity, branding, contacts and shared defaults.", None, None, (), False),
    ("branches", "Branches", "Organization", "Company offices and locations.", None, "hrms", ("company_manage",), True),
    ("departments", "Departments", "Organization", "Departments and business units.", None, "hrms", ("company_manage",), True),
    ("designations", "Designations", "Organization", "Job titles, grades and reporting levels.", None, "hrms", ("company_manage",), True),
    ("shifts", "Shifts", "HR", "Work timings and attendance rules.", None, "hrms", ("attendance_manage",), False),
    ("holidays", "Holidays", "HR", "Holiday calendars by year and branch.", None, "hrms", ("attendance_manage",), False),
    ("leaveTypes", "Leave types", "HR", "Leave categories and entitlement rules.", None, "hrms", ("leave_manage",), False),
    ("salaryComponents", "Salary components", "HR", "Payroll earnings, deductions and statutory flags.", None, "hrms", ("payroll_run",), True),
    ("internships", "Internship administration", "HR", "Batches, applications, corrections and program configuration.", "/hrms/interns/batches", "hrms", ("employee_update", "intern_management_manage"), False),
    ("documents", "Letterheads & document templates", "Company", "Letterheads, signatories, placeholders and certificate templates.", "/hrms/letters-certificates?tab=templates", "hrms", ("company_manage", "settings_manage"), True),
    ("users", "Users & access", "Access & security", "Company users, roles and delegated module access.", "/admin/access", None, (), True),
    ("security", "Security policies", "Access & security", "Login policies and security controls.", "/admin/control/security", None, (), True),
    ("audit", "Audit history", "Access & security", "Review configuration and access changes.", "/admin/control/audit", None, (), True),
    ("modules", "Applications & modules", "Applications", "Company module availability.", "/admin/control/modules", None, (), True),
    ("connections", "Connected applications", "Integrations", "Shared service connections and integrations.", "/admin/control/services/connections", None, (), True),
    ("communication", "Email & delivery", "Communication", "Sender configuration, delivery services and logs.", "/admin/control/services/delivery", None, (), True),
    ("global", "Shared service defaults", "Company", "Common service configuration and policies.", "/admin/control/services/settings", None, (), True),
    ("pms", "PMS configuration", "Application settings", "Project statuses, workflows and administration.", "/pms/settings", "project_management", ("pms_admin",), True),
    ("task-packs", "Intern task packs & deadlines", "Application settings", "Reusable assignments, skill variants, rubrics and deadlines.", "/pms/batch-tasks", "project_management", ("pms_manage_tasks", "pms_admin"), False),
    ("crm", "CRM configuration", "Application settings", "Custom fields and CRM defaults.", "/crm/settings", "crm", ("crm_admin",), True),
    ("sales", "Sales configuration", "Application settings", "Sales defaults, numbering and approval configuration.", "/srm/settings", "srm", ("srm_settings_manage", "srm_admin"), True),
    ("finance", "Finance configuration", "Application settings", "Financial years, currency and accounting configuration.", "/fam/settings", "fam", ("fam_settings_manage", "fam_admin"), True),
    ("ai", "AI providers & models", "Integrations", "Provider configuration and model access.", "/ai/provider-settings", "ai", ("settings_manage",), True),
]
ADMIN_ONLY = {"users", "security", "audit", "modules", "connections", "communication", "global"}
GLOBAL_ONLY = {"security", "connections", "communication", "global", "ai"}
HR_SECTIONS = {"branches", "departments", "designations", "shifts", "holidays", "leaveTypes", "salaryComponents"}


def context(db, actor):
    company = actor.organization_id
    policy = service.policy_for(db, actor, company)
    grants = (service.resolved_grants(db, policy) if policy and not actor.is_superuser
              else service.legacy_grants(db, actor, company))
    is_admin = actor.is_superuser or (service.schema_ready(db) and bool(db.query(AccessMembership).filter_by(
        user_id=actor.id, company_id=company, active=True, is_admin=True).first()))
    from app.apps.interns_hub.management_access import require_admin
    try:
        require_admin(actor)
        intern_admin = True
    except HTTPException:
        intern_admin = False
    return {"intern_admin": intern_admin, "company": company, "grants": grants, "admin": is_admin, "managed": bool(policy),
            "permissions": permission_names(actor), "super": actor.is_superuser}


def allows(option, ctx):
    key, _, _, _, _, module, required, org = option
    if key in {"internships", "task-packs"} and not ctx.get("intern_admin", False):
        return False
    if key in GLOBAL_ONLY:
        return ctx["super"]
    if key in ADMIN_ONLY:
        return ctx["admin"]
    if not required:
        return True
    if ctx["super"]:
        return bool(ctx["grants"].get(module, {}).get("enabled"))
    grant = ctx["grants"].get(module, {})
    if not grant.get("enabled") or not set(required).intersection(grant.get("permissions", [])):
        return False
    if ctx["managed"]:
        if not set(grant.get("actions", [])).intersection({"configure", "edit", "assign"}):
            return False
        if org and grant.get("scope") not in {"organization", "all"}:
            return False
    return True


def can_edit_company(ctx):
    if ctx["admin"]:
        return True
    grant = ctx["grants"].get("hrms", {})
    return (grant.get("enabled") and "company_manage" in grant.get("permissions", [])
            and (not ctx["managed"] or (grant.get("scope") in {"organization", "all"}
                 and "configure" in grant.get("actions", []))))


def item(option, ctx):
    key, title, group, description, destination, module, _, _ = option
    return dict(id=key, title=title, group=group, description=description, destination=destination,
                module=module, scope=ctx["grants"].get(module, {}).get("scope", "organization" if ctx["admin"] else "own"),
                editable=can_edit_company(ctx) if key == "company-profile" else True)


def require_option(db, actor, key):
    option = next((o for o in OPTIONS if o[0] == key), None)
    ctx = context(db, actor)
    if not option or not allows(option, ctx):
        raise HTTPException(403, "This setting is not available for your current permissions and company")
    return option, ctx


@router.get("")
def list_settings(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    ctx = context(db, actor)
    company = db.get(Company, ctx["company"])
    return dict(companyId=ctx["company"], companyName=company.name if company else "Company",
                options=[item(o, ctx) for o in OPTIONS if allows(o, ctx)])


class ProfileUpdate(CompanyUpdate):
    model_config = ConfigDict(extra="forbid")


@router.get("/company-profile")
def company_profile(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    _, ctx = require_option(db, actor, "company-profile")
    company = db.get(Company, ctx["company"])
    if not company:
        raise HTTPException(404, "Company not found")
    fields = set(ProfileUpdate.model_fields) if can_edit_company(ctx) else {
        "name", "legal_name", "website", "email", "phone", "address", "city", "state", "country", "pincode", "logo_url"}
    return {"profile": {key: getattr(company, key) for key in fields}, "editable": can_edit_company(ctx), "companyId": company.id}


@router.patch("/company-profile")
def update_company_profile(data: ProfileUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    _, ctx = require_option(db, actor, "company-profile")
    if not can_edit_company(ctx):
        raise HTTPException(403, "Company configuration permission required")
    from app.api.v1.company import _ensure_company_unique
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and (not changes["name"] or not changes["name"].strip() or len(changes["name"]) > 150):
        raise HTTPException(422, "Company name must contain 1–150 characters")
    for key, value in changes.items():
        column = Company.__table__.c[key]
        limit = getattr(column.type, "length", None)
        if value is not None and limit and len(str(value)) > limit:
            raise HTTPException(422, f"{key} must be at most {limit} characters")
    if changes.get("default_timezone"):
        try: ZoneInfo(changes["default_timezone"])
        except (ZoneInfoNotFoundError, ValueError): raise HTTPException(422, "Select a valid timezone")
    if "fiscal_year_start_month" in changes and not 1 <= (changes["fiscal_year_start_month"] or 0) <= 12:
        raise HTTPException(422, "Financial year start month must be between 1 and 12")
    if "working_days_per_week" in changes and not 1 <= (changes["working_days_per_week"] or 0) <= 7:
        raise HTTPException(422, "Working days must be between 1 and 7")
    for key in ("logo_url",):
        if changes.get(key) and not changes[key].startswith("https://"):
            raise HTTPException(422, "Use an HTTPS logo URL")
    company = db.get(Company, ctx["company"])
    if not company: raise HTTPException(404, "Company not found")
    _ensure_company_unique(db, data, exclude_id=company.id)
    before = {key: getattr(company, key) for key in changes}
    for key, value in changes.items(): setattr(company, key, value.strip() if isinstance(value, str) else value)
    service.audit(db, actor, company.id, "settings.company.updated", "Company profile configuration", before, changes, request=request)
    db.commit()
    return {"saved": True, "companyId": company.id}


@router.get("/{key}")
def get_setting(key: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    option, ctx = require_option(db, actor, key)
    return item(option, ctx)
