"""Registration is code-owned. Configuration cannot add arbitrary handlers/URLs."""

from dataclasses import dataclass
from typing import Callable
from fastapi import HTTPException
from app.access import service, entitlements
from app.access.catalog import catalog, permission_names

CAPABILITIES = (
    "authentication",
    "approvals",
    "workflows",
    "automations",
    "ai",
    "notifications",
    "email",
    "documents",
    "integrations",
    "forms",
    "custom_fields",
    "settings",
)


@dataclass(frozen=True)
class RecordContract:
    module: str
    entity: str
    read_path: str
    permission: str


RECORDS = {}


def register_record(contract):
    if (
        not isinstance(contract, RecordContract)
        or "{id}" not in contract.read_path
        or not contract.read_path.startswith("/")
        or ".." in contract.read_path
        or "://" in contract.read_path
    ):
        raise ValueError("A record contract must use a fixed local API path")
    RECORDS[(contract.module, contract.entity)] = contract


def register_action(name, tool):
    """Module registration may contribute a native API action, never user code."""
    from app.ai_operator.suite_tools import Tool, TOOLS

    if (
        not isinstance(tool, Tool)
        or tool.method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        or not tool.path.startswith("/")
        or any(value in tool.path for value in ("..", "://", "?", "#"))
    ):
        raise ValueError("Register a fixed native API action")
    if name in TOOLS and TOOLS[name] != tool:
        raise ValueError("An existing action cannot be silently replaced")
    TOOLS[name] = tool


for module, entity, path, permission in [
    ("crm", "lead", "/crm/leads/{id}", "crm_view"),
    ("crm", "quote", "/crm/quotes/{id}", "crm_view"),
    ("project_management", "project", "/project-management/projects/{id}", "pms_view"),
    ("project_management", "task", "/project-management/tasks/{id}", "pms_view"),
    ("srm", "invoice", "/srm/invoices/{id}", "srm_view"),
    ("hrms", "leave", "/leave/requests/{id}", "leave_view"),
]:
    register_record(RecordContract(module, entity, path, permission))


def authorize(db, user, company, module, action="view", permission=None):
    from app.models.company import Company

    if db.get(Company, company) is None:
        raise HTTPException(404, "Company not found")
    if not user or not user.is_active:
        raise HTTPException(403, "Active service consumer required")
    if not user.is_superuser and company not in service.companies_for(db, user):
        raise HTTPException(403, "Company membership required")
    from app.module_registry import APP_MODULES

    if module in APP_MODULES and not APP_MODULES[module].shared_services:
        raise HTTPException(
            403, "Shared services are disabled for this registered module"
        )
    meta = next((m for m in catalog(db) if m["key"] == module), None)
    if not meta or not meta["installed"]:
        raise HTTPException(
            422, "Register and install the module before using shared services"
        )
    entitlements.enforce(db, company, module)
    policy = service.policy_for(db, user, company)
    if policy and not user.is_superuser:
        grant = service.resolved_grants(db, policy).get(module, {})
        if (
            policy.status != "active"
            or not grant.get("enabled")
            or action not in grant.get("actions", [])
        ):
            raise HTTPException(403, "Shared service denied by effective module policy")
        names = set(grant.get("permissions", []))
    else:
        names = permission_names(user)
        if not user.is_superuser and action not in service.legacy_grants(
            db, user, company
        ).get(module, {}).get("actions", []):
            raise HTTPException(
                403, "Legacy module role does not authorize this shared action"
            )
        if not user.is_superuser and not any(
            p["name"] in names for p in meta["permissions"]
        ):
            raise HTTPException(403, "Module permission required")
    if permission and not user.is_superuser and permission not in names:
        raise HTTPException(403, "Native permission required: " + permission)
    return policy


def service_identity(db, user, company, module):
    if (
        not user
        or user.is_superuser
        or (
            user.role
            and user.role.name.lower() in {"super_admin", "admin", "administrator"}
        )
    ):
        raise HTTPException(422, "Choose a non-superuser managed execution identity")
    policy = authorize(db, user, company, module)
    if not policy:
        raise HTTPException(
            422, "Execution identities require an explicit central access policy"
        )
    return user


def describe(db):
    return [
        {
            "key": m["key"],
            "label": m["label"],
            "installed": m["installed"],
            "services": list(CAPABILITIES),
            "records": [
                {
                    "entity": c.entity,
                    "readPath": c.read_path,
                    "permission": c.permission,
                }
                for (key, _), c in RECORDS.items()
                if key == m["key"]
            ],
            "recordIntegration": (
                "registered"
                if any(key == m["key"] for key, _ in RECORDS)
                else "Record operations require a code-owned adapter"
            ),
        }
        for m in catalog(db)
    ]
