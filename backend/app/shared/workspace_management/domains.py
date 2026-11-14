"""Module-specific workspace policies. Membership never grants record permissions."""
from dataclasses import dataclass
from fastapi import HTTPException
from app.core.deps import RequirePermission
from app.module_registry import is_app_enabled
from app.apps.fam.access import FAM_VIEW_PERMISSIONS

@dataclass(frozen=True)
class WorkspaceDomain:
    module: str
    api: str
    permission_module: str
    view: tuple[str, ...]
    configure: tuple[str, ...]
    views: tuple[str, ...]

    def authorize(self, actor, configure=False):
        if not is_app_enabled(self.permission_module):
            raise HTTPException(403, "Module is disabled")
        grants = getattr(actor, "_suite_grants", None)
        if grants is not None and not actor.is_superuser and not grants.get(self.permission_module, {}).get("enabled"):
            raise HTTPException(403, "Module access is required")
        if not configure and grants is not None and grants.get(self.permission_module, {}).get("enabled") and "view" in grants[self.permission_module].get("actions", []):
            return
        RequirePermission(*(self.configure if configure else self.view))(actor)

    def administrator(self, actor):
        if getattr(actor, "_suite_is_company_admin", False):
            return True
        try:
            if self.module == "hrms" and not actor.is_superuser:
                grants = getattr(actor, "_suite_grants", None)
                if grants is not None:
                    grant = grants.get("hrms", {})
                    if grant.get("role") not in {"admin", "hr", "hr_admin", "company_admin"} or grant.get("scope") not in {"all", "company", "organization", "branch"} or "configure" not in grant.get("actions", []):
                        return False
                elif not actor.role or actor.role.name.lower().replace(" ", "_") not in {"admin", "hr", "hr_admin", "company_admin"}:
                    return False
                RequirePermission(*self.configure)(actor)
            else:
                RequirePermission(self.configure[-1])(actor)
            return True
        except HTTPException:
            return False

DOMAINS = {
    "pms": WorkspaceDomain("pms", "project-management", "project_management", ("pms_view", "pms_manage_projects", "pms_manage_tasks", "pms_admin"), ("pms_manage_projects", "pms_admin"), ("projects", "tasks", "board", "timeline", "workload", "team", "activity", "settings")),
    "crm": WorkspaceDomain("crm", "crm", "crm", ("crm_view", "crm_manage", "crm_admin"), ("crm_manage", "crm_admin"), ("leads", "contacts", "deals", "activities", "quotes", "reports")),
    "hrms": WorkspaceDomain("hrms", "hrms", "hrms", ("employee_view", "employee_create", "employee_update", "attendance_view", "leave_view", "leave_apply", "payroll_view"), ("employee_update", "employee_create"), ("employees", "attendance", "leave", "approvals", "documents", "recruitment")),
    "srm": WorkspaceDomain("srm", "srm", "srm", ("srm_view", "srm_invoice_view", "srm_collection_view", "srm_admin"), ("srm_admin",), ("appointments", "construction", "pos", "orders", "products", "stock", "invoices", "collections")),
    "fam": WorkspaceDomain("fam", "fam", "fam", tuple(FAM_VIEW_PERMISSIONS), ("fam_admin",), ("accounts", "journals", "receivables", "payables", "reconciliation", "statements")),
}
