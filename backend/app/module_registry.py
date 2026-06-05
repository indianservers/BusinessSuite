from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Iterable

from fastapi import APIRouter

from app.core.config import settings


@dataclass(frozen=True)
class AppModule:
    key: str
    label: str
    router_modules: tuple[str, ...] = ()
    model_modules: tuple[str, ...] = ()
    seed_module: str | None = None


COMMON_ROUTER_MODULES = (
    "app.api.v1.auth",
    "app.api.v1.approval_os",
    "app.api.v1.logs",
    "app.api.v1.users",
    "app.api.v1.workflow_engine",
    "app.ai_agents.api",
)

COMMON_MODEL_MODULES = (
    "app.models.user",
    "app.common.models",
    "app.models.audit",
    "app.models.approval_os",
    "app.models.notification",
    "app.models.sso",
    "app.models.workflow_engine",
    "app.ai_agents.models",
)

APP_MODULES: dict[str, AppModule] = {
    "hrms": AppModule(
        key="hrms",
        label="HRMS",
        router_modules=(
            "app.api.v1.ai",
            "app.api.v1.assets",
            "app.api.v1.attendance",
            "app.api.v1.background_verification",
            "app.api.v1.benefits",
            "app.api.v1.company",
            "app.api.v1.custom_fields",
            "app.api.v1.documents",
            "app.api.v1.engagement",
            "app.api.v1.employees",
            "app.api.v1.expenses",
            "app.api.v1.exit",
            "app.api.v1.fnf",
            "app.api.v1.form16",
            "app.api.v1.helpdesk",
            "app.api.v1.holidays",
            "app.api.v1.hrms_compliance_exports",
            "app.api.v1.leave",
            "app.api.v1.leave_payroll",
            "app.api.v1.lms",
            "app.api.v1.notifications",
            "app.api.v1.onboarding",
            "app.api.v1.org_structure",
            "app.api.v1.payroll",
            "app.api.v1.payroll_extensions",
            "app.api.v1.payroll_bank_advice",
            "app.api.v1.performance",
            "app.api.v1.profile_change_requests",
            "app.api.v1.probation",
            "app.api.v1.recruitment",
            "app.api.v1.reports",
            "app.api.v1.enterprise",
            "app.api.v1.sso",
            "app.api.v1.shift_roster",
            "app.api.v1.statutory",
            "app.api.v1.statutory_compliance",
            "app.api.v1.tax_declaration",
            "app.api.v1.timesheets",
            "app.api.v1.whatsapp_ess",
            "app.api.v1.workflow",
        ),
        model_modules=(
            "app.models.company",
            "app.models.employee",
            "app.models.expense",
            "app.models.attendance",
            "app.models.leave",
            "app.models.payroll",
            "app.models.timesheet",
            "app.models.recruitment",
            "app.models.onboarding",
            "app.models.performance",
            "app.models.helpdesk",
            "app.models.document",
            "app.models.asset",
            "app.models.exit",
            "app.models.target",
            "app.models.platform",
            "app.models.lms",
            "app.models.engagement",
            "app.models.whatsapp_ess",
            "app.models.statutory_compliance",
            "app.models.benefits",
            "app.models.background_verification",
        ),
        seed_module="app.db.init_db",
    ),
    "crm": AppModule(
        key="crm",
        label="CRM",
        router_modules=("app.apps.crm.api.router",),
        model_modules=("app.apps.crm.models",),
    ),
    "project_management": AppModule(
        key="project_management",
        label="Project Management",
        router_modules=("app.apps.project_management.api.router",),
        model_modules=("app.apps.project_management.models",),
    ),
    "srm": AppModule(
        key="srm",
        label="Sales & Revenue Management",
        router_modules=("app.apps.srm.api.router",),
        model_modules=("app.apps.srm.models",),
    ),
}


def normalize_app_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def get_installed_app_keys() -> list[str]:
    keys = [normalize_app_key(item) for item in settings.INSTALLED_APPS]
    return [key for key in keys if key in APP_MODULES]


def is_app_enabled(key: str) -> bool:
    return normalize_app_key(key) in get_installed_app_keys()


def iter_enabled_modules() -> Iterable[AppModule]:
    for key in get_installed_app_keys():
        yield APP_MODULES[key]


def import_model_modules() -> None:
    for module_name in COMMON_MODEL_MODULES:
        import_module(module_name)
    for module in iter_enabled_modules():
        for module_name in module.model_modules:
            import_module(module_name)


def build_api_router() -> APIRouter:
    api_router = APIRouter()
    for module_name in COMMON_ROUTER_MODULES:
        module = import_module(module_name)
        api_router.include_router(module.router)
    for app_module in iter_enabled_modules():
        for module_name in app_module.router_modules:
            module = import_module(module_name)
            api_router.include_router(module.router)
    return api_router
