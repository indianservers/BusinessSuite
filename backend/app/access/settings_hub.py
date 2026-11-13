"""Server-owned settings discovery. Role labels never confer configuration access."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
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
    ("files-storage", "Files & Storage", "Company", "Google Drive, OneDrive, Box or Dropbox for attachments, module folders and the file register.", None, None, (), True),
    ("shared-companies", "Shared companies", "Company", "Business company records shared across Business Suite.", None, "crm", ("crm_view", "crm_manage", "crm_admin", "crm_companies_view", "crm_companies_manage"), False),
    ("appearance", "Homepage Banner", "Appearance", "Banner image, crop, positioning and overlay for your company homepage.", None, None, (), True),
    ("account", "My account & security", "Personal", "Your account details and password.", None, None, (), False),
    ("preferences", "Display preferences", "Personal", "Your theme and display density on this browser.", None, None, (), False),
    ("company-profile", "Company name & details", "Company & access", "Company identity, branding, contacts and shared defaults.", None, None, (), False),
    ("branches", "Branches", "Company & access", "Create branches and assign users to their authorized locations.", None, None, (), True),
    ("departments", "Departments", "Organization", "Departments and business units.", None, "hrms", ("company_manage",), True),
    ("designations", "Designations", "Organization", "Job titles, grades and reporting levels.", None, "hrms", ("company_manage",), True),
    ("shifts", "Shifts", "HR", "Work timings and attendance rules.", None, "hrms", ("attendance_manage",), False),
    ("holidays", "Holidays", "HR", "Holiday calendars by year and branch.", None, "hrms", ("attendance_manage",), False),
    ("leaveTypes", "Leave types", "HR", "Leave categories and entitlement rules.", None, "hrms", ("leave_manage",), False),
    ("salaryComponents", "Salary components", "HR", "Payroll earnings, deductions and statutory flags.", None, "hrms", ("payroll_run",), True),
    ("internships", "Internship administration", "HR", "Batches, applications, corrections and program configuration.", "/hrms/interns/batches", "hrms", ("employee_update", "intern_management_manage"), False),
    ("documents", "Letterheads & document templates", "Company", "Letterheads, signatories, placeholders and certificate templates.", "/hrms/letters-certificates?tab=templates", "hrms", ("company_manage", "settings_manage"), True),
    ("users", "Users & permissions", "Company & access", "Company users, roles and delegated module access.", "/admin/access", None, (), True),
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
# Reuse native module authorization and storage for these central editors.
OPTIONS += [
    ("starter-values", "Starter values", "Business defaults", "Add editable starter leave types, salary components, sales stages and payment methods.", None, None, (), True),
    ("crm-lead-sources", "Lead sources", "CRM", "Manage the lead sources available in sales forms.", None, "crm", ("crm_admin",), True),
    ("api-credentials", "API credentials", "Integrations", "API keys for approved integrations.", None, None, (), True),
    ("webhooks", "Integration webhooks", "Integrations", "Outbound event subscriptions and delivery configuration.", None, None, (), True),
    ("crm-webhooks", "CRM webhooks", "CRM", "CRM event subscriptions.", None, "crm", ("crm_admin",), True),
    ("crm-scoring", "Lead scoring", "CRM", "Rules for lead qualification and scoring.", None, "crm", ("crm_admin",), True),
    ("crm-territories", "Sales territories", "CRM", "Sales territory definitions and assignments.", None, "crm", ("crm_admin",), True),
    ("crm-automation", "CRM automation", "CRM", "CRM triggers and automated actions.", None, "crm", ("crm_admin",), True),
    ("business-defaults", "Defaults", "Business defaults", "Starting values for new forms: currency, country, sales, tasks and HR, with module and branch overrides.", None, None, (), False),
    ("crm-pipelines", "CRM pipelines", "CRM", "Deal stages and sales pipelines.", None, "crm", ("crm_admin",), True),
    ("crm-approvals", "CRM approval rules", "CRM", "Approval rules for CRM operations.", None, "crm", ("crm_admin",), True),
    ("financial-years", "Financial years", "Finance", "Accounting periods and financial year configuration.", None, "fam", ("fam_settings_manage", "fam_admin"), True),
    ("cost-centers", "Cost centers", "Finance", "Accounting cost center definitions.", None, "fam", ("fam_settings_manage", "fam_admin"), True),
    ("accounting-branches", "Accounting branches", "Finance", "Finance branch registrations; distinct from company access branches.", None, "fam", ("fam_settings_manage", "fam_admin"), True),
    ("voucher-types", "Voucher types & numbering", "Finance", "Accounting document types and numbering configuration.", None, "fam", ("fam_settings_manage", "fam_admin"), True),
    ("payment-modes", "Payment modes", "Finance", "Shared finance payment mode definitions.", None, "fam", ("fam_settings_manage", "fam_admin"), True),
    ("tax-settings", "GST & tax settings", "Finance", "GST defaults and statutory configuration.", None, "fam", ("fam_settings_manage", "fam_admin"), True),
    ("roles", "Roles & permission templates", "Company & access", "Custom module roles and reusable permission templates.", None, None, (), True),
]
ADMIN_ONLY = {"starter-values", "files-storage", "appearance", "roles", "users", "security", "audit", "modules", "connections", "communication", "global"}
GLOBAL_ONLY = {"files-storage", "api-credentials", "webhooks", "security", "connections", "communication", "global", "ai"}
HR_SECTIONS = {"branches", "departments", "designations", "shifts", "holidays", "leaveTypes", "salaryComponents"}


def context(db, actor):
    company = actor.organization_id
    policy = service.policy_for(db, actor, company)
    grants = (service.resolved_grants(db, policy) if policy and not actor.is_superuser
              else service.legacy_grants(db, actor, company))
    from app.branches.roles import effective_grants
    grants = effective_grants(db, actor, company, getattr(actor, '_suite_branch_id', None), grants)
    if getattr(actor, '_suite_admin_read', False):
        from app.access.admin_reads import grants as company_read_grants
        grants = company_read_grants(db, actor, grants)
    is_admin = actor.is_superuser or (service.schema_ready(db) and bool(db.query(AccessMembership).filter_by(
        user_id=actor.id, company_id=company, active=True, is_admin=True).first()))
    from app.apps.interns_hub.management_access import require_admin
    try:
        require_admin(actor)
        intern_admin = True
    except HTTPException:
        intern_admin = False
    from app.branches.service import access as branch_access
    branch_manager = branch_access(db, actor, company)[3]
    return {"branch_manager": branch_manager, "intern_admin": intern_admin, "company": company, "grants": grants, "admin": is_admin, "managed": bool(policy or getattr(actor, '_suite_branch_roles_fingerprint', None)),
            "permissions": permission_names(actor), "super": actor.is_superuser}


def allows(option, ctx):
    key, _, _, _, _, module, required, org = option
    if key in {"internships", "task-packs"} and not ctx.get("intern_admin", False):
        return False
    if key == "business-defaults":
        return can_edit_company(ctx)
    if key == "company-profile":
        return can_view_company(ctx)
    if key == "branches":
        return ctx.get("branch_manager", False)
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


def can_view_company(ctx):
    if can_edit_company(ctx):
        return True
    grant = ctx["grants"].get("hrms", {})
    return bool(grant.get("enabled") and "company_view" in grant.get("permissions", [])
                and (not ctx["managed"] or (grant.get("scope") in {"organization", "all"}
                     and "view" in grant.get("actions", []))))


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
                editable=can_edit_company(ctx) if key in {"company-profile", "business-defaults"} else True)


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
    options = [item(o, ctx) for o in OPTIONS if allows(o, ctx)]
    allowed = {o["id"] for o in options}
    states = {}
    if company:
        if "company-profile" in allowed:
            complete = bool(company.name and company.email and company.country)
            states["company-profile"] = {"state": "ready" if complete else "attention", "label": "Complete" if complete else "Needs attention", "detail": "Company name, email and country are filled in." if complete else "Add your company name, email and country."}
        if "business-defaults" in allowed:
            complete = bool(company.default_currency and company.default_timezone and company.fiscal_year_start_month)
            states["business-defaults"] = {"state": "ready" if complete else "attention", "label": "Configured" if complete else "Not configured", "detail": "Currency, timezone and financial year defaults."}
        if "branches" in allowed:
            from app.models.company import Branch
            count = db.query(Branch).filter(Branch.company_id == company.id, Branch.is_active.is_(True)).count()
            states["branches"] = {"state": "ready" if count else "attention", "label": f"{count} active" if count else "Not configured", "detail": "Active company access branches."}
        if "connections" in allowed:
            from app.models.platform import IntegrationCredential
            rows = db.query(IntegrationCredential.status).filter(IntegrationCredential.organization_id == company.id).all()
            active = sum(1 for (status,) in rows if status == "Active")
            states["connections"] = {"state": "ready" if active else "attention", "label": "Configured" if active else "Needs attention" if rows else "Not configured", "detail": f"{active} active connection configurations. Live connectivity is checked in Connected applications."}
    if "communication" in allowed:
        from app.shared.communications import provider_status
        configured = any(row["channel"] == "email" and row["status"] == "configured-unverified" for row in provider_status())
        states["communication"] = {"state": "ready" if configured else "attention", "label": "Configured" if configured else "Not configured", "detail": "Email provider configuration only; live delivery has not been verified."}
    for option in options:
        option["status"] = states.get(option["id"])
        option["historyAvailable"] = option["id"] in {"company-profile", "business-defaults"} and can_edit_company(ctx)
    return dict(companyId=ctx["company"], companyName=company.name if company else "Company", options=options)


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
    import re
    if "email" in changes and changes["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", changes["email"].strip()):
        raise HTTPException(422, "Enter a valid company email")
    if "default_currency" in changes and not re.fullmatch(r"[A-Z]{3}", changes["default_currency"] or ""):
        raise HTTPException(422, "Use a three-letter uppercase currency code")
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


@router.get("/history/{key}")
def setting_history(key: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    _, ctx = require_option(db, actor, key)
    if key not in {"company-profile", "business-defaults"} or not can_edit_company(ctx):
        raise HTTPException(403, "Change history requires company configuration access")
    from app.access.models import AccessAudit
    defaults = {"default_timezone", "default_currency", "working_days_per_week", "fiscal_year_start_month"}
    rows = db.query(AccessAudit).filter(AccessAudit.company_id == ctx["company"], AccessAudit.operation.in_(["settings.company.updated", "settings.defaults.updated"])).order_by(AccessAudit.created_at.desc(), AccessAudit.id.desc()).limit(200).all()
    result = []
    for row in rows:
        if row.operation == "settings.defaults.updated":
            if key != "business-defaults": continue
            changed = sorted(k for k in set(row.before_json or {}) | set(row.after_json or {}) if (row.before_json or {}).get(k) != (row.after_json or {}).get(k))
        else:
            changed = sorted(k for k in (row.after_json or {}) if k in Company.__table__.c and ((k in defaults) == (key == "business-defaults")))
        if not changed:
            continue
        user = db.get(User, row.actor_id)
        result.append({"id": row.id, "actor": user.email if user else "Former user", "at": row.created_at, "fields": changed, "outcome": row.outcome})
        if len(result) == 30:
            break
    return {"items": result}


class DefaultsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, object] = Field(max_length=100)
    version: int = Field(ge=0, strict=True)


@router.get("/defaults/effective")
def effective_form_defaults(module: str | None = None, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from app.shared.starter_values import lead_sources
    from app.shared.form_defaults import effective
    from app.branches.service import access
    branch_id = getattr(actor, "_suite_branch_id", None)
    branch_id = branch_id if isinstance(branch_id, int) else None
    result = effective(db, actor.organization_id, module, branch_id)
    result["leadSources"] = lead_sources(db, actor.organization_id)
    allowed, _, all_branches, _ = access(db, actor, actor.organization_id)
    if result["values"].get("branch_id") and not all_branches and result["values"]["branch_id"] not in allowed:
        result["values"]["branch_id"] = None
        result["values"]["department_id"] = None
    modules = {}
    if module is None:
        from app.shared.form_defaults import MODULES
        for name in MODULES:
            values = effective(db, actor.organization_id, name, branch_id)["values"]
            if values.get("branch_id") and not all_branches and values["branch_id"] not in allowed:
                values["branch_id"] = None
                values["department_id"] = None
            modules[name] = values
    return {**result, "modules": modules, "companyId": actor.organization_id, "branchId": branch_id, "module": module}


@router.get("/defaults/configuration")
def form_defaults_configuration(module: str | None = None, branch_id: int | None = None, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from app.shared import form_defaults as defaults
    from app.shared.models import ServicePolicy
    _, ctx = require_option(db, actor, "business-defaults")
    defaults.check_branch(db, ctx["company"], branch_id)
    key = defaults.scope_key(ctx["company"], module, branch_id)
    row = db.query(ServicePolicy).filter_by(scope_key=key, organization_id=ctx["company"], kind="form_defaults").first()
    inherited = defaults.effective(db, ctx["company"], module, branch_id, skip_scope=key)
    available = defaults.choices(db, ctx["company"])
    from app.branches.service import access as branch_access
    from app.models.company import Branch
    from sqlalchemy import select
    allowed, _, _, _ = branch_access(db, actor, ctx["company"])
    available["branches"] = [{"value": row.id, "label": row.name} for row in db.connection().execute(select(Branch.id, Branch.name).where(Branch.company_id == ctx["company"], Branch.id.in_(allowed), Branch.is_active.is_(True)).order_by(Branch.name))]
    from app.shared.starter_values import lead_sources
    fields = [{**field, "options": [{"value": value, "label": value} for value in lead_sources(db, ctx["company"])]} if field["key"] == "lead_source" else field for field in defaults.FIELDS]
    return {"fields": fields, "choices": available, "overrides": row.values_json if row else {}, "version": row.version if row else 0, "inherited": inherited["values"], "effective": defaults.effective(db, ctx["company"], module, branch_id)["values"], "companyId": ctx["company"]}


@router.put("/defaults/configuration")
def update_form_defaults(data: DefaultsUpdate, request: Request, module: str | None = None, branch_id: int | None = None, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from app.shared import form_defaults as defaults
    from app.shared.models import ServicePolicy
    from sqlalchemy.exc import IntegrityError
    _, ctx = require_option(db, actor, "business-defaults")
    defaults.check_branch(db, ctx["company"], branch_id)
    key = defaults.scope_key(ctx["company"], module, branch_id)
    row = db.query(ServicePolicy).filter_by(scope_key=key, organization_id=ctx["company"], kind="form_defaults").with_for_update().first()
    if data.version != (row.version if row else 0):
        raise HTTPException(409, "Defaults changed since you opened them. Reload before saving.")
    inherited = defaults.effective(db, ctx["company"], module, branch_id, skip_scope=key)["values"]
    values = defaults.validate(db, ctx["company"], data.values, inherited)
    before = dict(row.values_json) if row else {}
    if row:
        row.values_json = values
        row.version += 1
        row.updated_by = actor.id
    else:
        row = ServicePolicy(scope_key=key, organization_id=ctx["company"], module_key=module or "*", kind="form_defaults", values_json=values, version=1, updated_by=actor.id)
        db.add(row)
    # Keep existing consumers of the company columns in sync.
    if module is None and branch_id is None:
        company = db.get(Company, ctx["company"])
        merged = {**inherited, **values}
        for name, column in {"currency": "default_currency", "timezone": "default_timezone", "fiscal_year_start_month": "fiscal_year_start_month"}.items():
            setattr(company, column, merged[name])
        company.working_days_per_week = len(merged["working_days"])
    service.audit(db, actor, ctx["company"], "settings.defaults.updated", key, before, values, request=request)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Defaults changed since you opened them. Reload before saving.")
    return {"saved": True, "version": row.version}


@router.get("/options/{key}")
@router.get("/{key}")
def get_setting(key: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    option, ctx = require_option(db, actor, key)
    return item(option, ctx)


class StarterValuesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modules: list[str] = Field(min_length=1, max_length=3)


@router.get("/starter-values/catalog")
def starter_values_catalog(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from app.shared.starter_values import CATALOG
    _, ctx = require_option(db, actor, "starter-values")
    return {"groups": [group for group in CATALOG if ctx["grants"].get(group["key"], {}).get("enabled")]}


@router.post("/starter-values/apply")
def apply_starter_values(data: StarterValuesInput, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from sqlalchemy import select
    from app.models.company import Branch
    from app.shared.starter_values import populate, CATALOG
    _, ctx = require_option(db, actor, "starter-values")
    allowed = {group["key"] for group in CATALOG if ctx["grants"].get(group["key"], {}).get("enabled")}
    if not set(data.modules) <= allowed:
        raise HTTPException(422, "Choose enabled applications")
    branch_id = getattr(actor, "_suite_branch_id", None)
    if not isinstance(branch_id, int):
        branch_id = db.connection().execute(select(Branch.id).where(Branch.company_id == ctx["company"], Branch.is_active.is_(True)).order_by(Branch.id).limit(1)).scalar()
    try:
        counts = populate(db, ctx["company"], branch_id, set(data.modules))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    service.audit(db, actor, ctx["company"], "settings.starter-values.added", str(ctx["company"]), {}, counts, request=request)
    db.commit()
    return {"created": counts, "total": sum(counts.values())}


class LeadSourcesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sources: list[str] = Field(min_length=1, max_length=100)


@router.get("/crm-lead-sources/options")
def get_lead_sources(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from app.shared.starter_values import lead_sources, LEAD_SOURCES
    require_option(db, actor, "crm-lead-sources")
    return {"sources": lead_sources(db, actor.organization_id), "defaults": LEAD_SOURCES}


@router.put("/crm-lead-sources/options")
def update_lead_sources(data: LeadSourcesInput, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from sqlalchemy import select
    from app.apps.crm.lead_models import CRMLeadManagementConfig
    from app.shared.starter_values import lead_sources
    _, ctx = require_option(db, actor, "crm-lead-sources")
    sources = ["Other" if value.strip().casefold() == "other" else value.strip() for value in data.sources]
    if any(not value or len(value) > 80 for value in sources) or len({value.casefold() for value in sources}) != len(sources):
        raise HTTPException(422, "Use unique, non-empty source names of up to 80 characters")
    # Keep the built-in fallback valid for unconfigured or inherited form defaults.
    if "Other" not in sources:
        if len(sources) == 100:
            raise HTTPException(422, "Keep at most 99 sources plus Other")
        sources.append("Other")
    db.connection().execute(select(Company.id).where(Company.id == ctx["company"]).with_for_update()).one()
    before = lead_sources(db, ctx["company"])
    row = db.query(CRMLeadManagementConfig).filter_by(organization_id=ctx["company"]).with_for_update().first()
    if row is None:
        row = CRMLeadManagementConfig(organization_id=ctx["company"], settings_json={})
        db.add(row)
    row.settings_json = {**(row.settings_json or {}), "sources": sources}
    row.updated_by = actor.id
    service.audit(db, actor, ctx["company"], "settings.lead-sources.updated", str(ctx["company"]), {"sources": before}, {"sources": sources}, request=request)
    db.commit()
    return {"sources": sources}
