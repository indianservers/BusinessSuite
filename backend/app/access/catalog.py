"""Route and permission discovery. The frontend never maintains a module list."""

from collections import defaultdict
from app.models.user import Permission, Role

ROUTES = {}
ENDPOINT_MODULES = {}
MODULES = {}
MODULE_PERMISSIONS = defaultdict(set)
ALIASES = {
    "pms": "project_management",
    "ai_agents": "ai",
    "ai_copilot": "ai",
    "admin_security": "security",
    "customization": "customization",
    "business_os": "business_os",
    "saas": "saas",
    "scheduling": "scheduling",
    "approval_os": "approvals",
    "workflow_engine": "automation",
    "logs": "audit",
}
PATHS = {
    "project_management": "/pms",
    "ai": "/ai/copilot",
    "forms": "/pms/forms",
    "automation": "/admin/automation",
    "communication": "/admin/communication",
    "security": "/admin/security",
    "customization": "/admin/customization",
    "saas": "/admin/company-settings",
    "business_os": "/business-os",
    "interns_hub": "/hrms/interns",
    "audit": "/hrms/logs",
    "approvals": "/hrms/approvals",
    "scheduling": "/crm/calendar",
}
LABELS = {
    "project_management": "PMS",
    "srm": "Sales & Inventory",
    "fam": "Finance & Accounting",
    "hrms": "HRMS",
    "crm": "CRM",
    "ai": "AI Assistant",
    "interns_hub": "Intern Management",
    "business_os": "Business OS",
    "saas": "System Settings",
    "security": "Security & Administration",
}
ACTIONS = [
    "view",
    "create",
    "edit",
    "delete",
    "approve",
    "export",
    "assign",
    "configure",
    "manage_users",
]
SCOPES = ["own", "assigned", "team", "department", "branch", "organization"]


def key_for_source(source, default=None):
    if source.startswith("app.forms."):
        return "forms"
    if source in {
        "app.access.api",
        "app.common.profile_api",
        "app.api.v1.auth",
        "app.api.v1.users",
        "app.api.v1.scheduled_jobs",
    }:
        return None
    if "interns_hub" in source:
        return "interns_hub"
    if default:
        return default
    bits = source.split(".")
    key = bits[2] if bits[1] == "apps" else bits[-1]
    if "ai_agents" in source:
        key = "ai"
    return ALIASES.get(key, key)


def register_routes(router, source, default=None):
    key = key_for_source(source, default)
    if not key:
        return
    MODULES.setdefault(
        key,
        {
            "key": key,
            "label": LABELS.get(key, key.replace("_", " ").title()),
            "route": PATHS.get(key, "/" + key),
            "sources": [],
        },
    )
    if source not in MODULES[key]["sources"]:
        MODULES[key]["sources"].append(source)

    def walk(routes, prefix=""):
        for route in routes:
            if hasattr(route, "original_router"):
                yield from walk(
                    route.original_router.routes, prefix + route.include_context.prefix
                )
            else:
                yield prefix, route

    for prefix, route in walk(router.routes):

        def collect(dependant):
            names = getattr(getattr(dependant, "call", None), "permissions", None)
            if isinstance(names, set):
                MODULE_PERMISSIONS[key].update(names)
            for child in getattr(dependant, "dependencies", []):
                collect(child)

        collect(getattr(route, "dependant", None))
        for method in getattr(route, "methods", []):
            ROUTES[(id(route.endpoint), prefix + route.path, method)] = key
            ENDPOINT_MODULES[id(route.endpoint)] = key


def request_module(request):
    route = request.scope.get("route")
    if not route:
        return None
    path = route.path.removeprefix("/api/v1")
    return ROUTES.get(
        (id(route.endpoint), path, request.method)
    ) or ENDPOINT_MODULES.get(id(route.endpoint))


def permission_module(permission):
    name = permission.name if hasattr(permission, "name") else str(permission)
    module = getattr(permission, "module", "") or ""
    for prefix, key in [
        ("pms_", "project_management"),
        ("crm_", "crm"),
        ("srm_", "srm"),
        ("fam_", "fam"),
        ("intern_", "interns_hub"),
        ("interns_", "interns_hub"),
        ("ai_", "ai"),
        ("admin_", "security"),
        ("communication_", "communication"),
        ("automation_", "automation"),
        ("analytics_", "analytics"),
        ("saas_", "saas"),
    ]:
        if name.startswith(prefix):
            return key
    if name.startswith("forms_") or module == "forms":
        return "forms"
    return ALIASES.get(module, module) if module in MODULES else "hrms"


def permission_objects(user):
    selected = getattr(user, "_suite_permission_objects", None)
    if selected is not None:
        return selected
    if user and not user.is_superuser:
        from sqlalchemy.orm import object_session
        from sqlalchemy.orm.exc import UnmappedInstanceError

        try:
            db = object_session(user)
        except UnmappedInstanceError:
            db = None
        if db:
            from app.access.service import policy_for, primary_company, resolved_grants

            policy = policy_for(
                db, user, getattr(user, "organization_id", primary_company(user))
            )
            if policy:
                if policy.status != "active":
                    return []
                names = {
                    name
                    for grant in resolved_grants(db, policy).values()
                    if grant.get("enabled")
                    for name in grant.get("permissions", [])
                }
                return db.query(Permission).filter(Permission.name.in_(names)).all()
    return user.role.permissions if user and user.role else []


def permission_names(user):
    return {p.name for p in permission_objects(user)}


def action_for(request):
    path = request.url.path.lower()
    if (
        any(word in path for word in ("export", "/download", "/pdf", "/excel"))
        and "preview" not in path
        and "import" not in path
    ):
        return "export"
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return "view"
    if any(
        word in path
        for word in ("/approve", "/reject", "/post-accounting", "/pay", "/run")
    ):
        return "approve"
    if any(word in path for word in ("/assign", "/members", "/invite")):
        return "assign"
    if request.method == "DELETE":
        return "delete"
    if any(word in path for word in ("/search", "/preview", "/simulate", "/validate")):
        return "view"
    return "create" if request.method == "POST" else "edit"


def action_permissions(names, tier):
    if tier == "admin":
        return names
    forbidden = (
        "admin",
        "delete",
        "approve",
        "payroll_run",
        "settings_manage",
        "manage_users",
        "post",
        "reconcile",
        "roles_manage",
        "security_manage",
    )
    if tier in {"viewer", "contributor"}:
        return [
            n for n in names if any(word in n for word in ("view", "read", "search"))
        ]
    return [n for n in names if not any(word in n for word in forbidden)]


def catalog(db):
    from app.module_registry import APP_MODULES, get_installed_app_keys
    from app.access.models import AccessRole

    all_permissions = (
        db.query(Permission).order_by(Permission.module, Permission.name).all()
    )
    grouped = defaultdict(list)
    for p in all_permissions:
        grouped[permission_module(p)].append(
            {"name": p.name, "description": p.description or p.name, "group": p.module}
        )
    modules = []
    for key, app in APP_MODULES.items():
        MODULES.setdefault(
            key,
            {
                "key": key,
                "label": app.label,
                "route": PATHS.get(key, "/" + key),
                "sources": list(app.router_modules),
            },
        )
    for key, meta in MODULES.items():
        present = {p["name"] for p in grouped[key]}
        for p in all_permissions:
            if p.name in MODULE_PERMISSIONS[key] and p.name not in present:
                grouped[key].append(
                    {
                        "name": p.name,
                        "description": p.description or p.name,
                        "group": p.module,
                    }
                )
        installed = key not in APP_MODULES or key in get_installed_app_keys()
        modules.append(
            {
                **meta,
                "installed": installed,
                "permissions": grouped[key],
                "actions": ACTIONS,
                "scopes": SCOPES,
                "routeCount": sum(1 for value in ROUTES.values() if value == key),
            }
        )
    return modules


def preset(module, tier, permissions):
    actions = {
        "viewer": ["view"],
        "contributor": ["view", "create", "edit"],
        "editor": ["view", "create", "edit", "export"],
        "manager": ["view", "create", "edit", "delete", "approve", "export", "assign"],
        "admin": ACTIONS,
    }[tier]
    names = action_permissions(
        [p["name"] for p in permissions], "admin" if tier == "manager" else tier
    )
    return {
        "enabled": True,
        "role": tier,
        "roleId": None,
        "permissions": names,
        "actions": actions,
        "scope": "organization" if tier == "admin" else "own",
    }
