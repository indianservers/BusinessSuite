from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.apps.business_os.models import (
    BOSEnabledModule,
    BOSIntegrationRule,
    BOSLifecycleEvent,
    BOSModuleDependency,
    BOSPostingRule,
)
from app.models.user import User


CORE_MODULES = {
    "fam": {"display_name": "Accounts / FAM", "home_path": "/fam", "is_financial_backbone": True, "optional": True},
    "inventory": {"display_name": "Inventory", "home_path": "/Inventory", "is_financial_backbone": False, "optional": True},
    "crm": {"display_name": "CRM", "home_path": "/crm", "is_financial_backbone": False, "optional": True},
    "srm": {"display_name": "SRM", "home_path": "/srm", "is_financial_backbone": False, "optional": True},
    "project_management": {"display_name": "PMS", "home_path": "/pms", "is_financial_backbone": False, "optional": True},
    "hrms": {"display_name": "HRMS", "home_path": "/hrms", "is_financial_backbone": False, "optional": True},
    "ai": {"display_name": "AI", "home_path": "/ai/copilot", "is_financial_backbone": False, "optional": True},
    "portals": {"display_name": "Portals", "home_path": "/portal/customer/login", "is_financial_backbone": False, "optional": True},
    "communication": {"display_name": "Communication", "home_path": "/admin/communication", "is_financial_backbone": False, "optional": True},
}

DEFAULT_ENABLED_MODULES = {"fam", "inventory", "crm", "srm", "project_management", "hrms", "ai", "portals", "communication"}

SUPPORTED_COMBINATIONS = [
    {"name": "Accounts only", "modules": ["fam"]},
    {"name": "Accounts + Inventory", "modules": ["fam", "inventory"]},
    {"name": "CRM only", "modules": ["crm"]},
    {"name": "CRM + SRM", "modules": ["crm", "srm"]},
    {"name": "SRM only", "modules": ["srm"]},
    {"name": "PMS only", "modules": ["project_management"]},
    {"name": "SRM + PMS", "modules": ["srm", "project_management"]},
    {"name": "PMS + FAM invoicing", "modules": ["project_management", "fam"]},
    {"name": "Accounts + Inventory + SRM", "modules": ["fam", "inventory", "srm"]},
    {"name": "Full Business OS", "modules": sorted(DEFAULT_ENABLED_MODULES)},
]

DEFAULT_DEPENDENCIES = [
    ("inventory", "fam", "optional", "Inventory can post accounting entries when Accounts/FAM is enabled."),
    ("srm", "crm", "optional", "SRM can consume CRM won-deal handoffs when CRM is enabled."),
    ("srm", "fam", "optional", "SRM can post invoices, receipts, and allocations to FAM when enabled."),
    ("project_management", "srm", "optional", "PMS can receive SRM engagement project handoffs when SRM is enabled."),
    ("project_management", "fam", "optional", "PMS timesheets can support FAM invoicing when FAM is enabled."),
    ("ai", "crm", "optional", "AI can embed in CRM records when CRM is enabled."),
    ("ai", "srm", "optional", "AI can embed in SRM records when SRM is enabled."),
    ("ai", "project_management", "optional", "AI can embed in PMS records when PMS is enabled."),
    ("communication", "crm", "optional", "CRM can use communication templates and logs when Communication is enabled."),
]

DEFAULT_INTEGRATIONS = [
    ("crm_won_to_srm_order", "crm", "srm", "deal_won", "create_sales_order"),
    ("srm_engagement_to_pms_project", "srm", "project_management", "engagement_confirmed", "create_project"),
    ("srm_invoice_to_fam", "srm", "fam", "invoice_approved", "post_sales_invoice"),
    ("srm_receipt_to_fam", "srm", "fam", "receipt_confirmed", "post_receipt"),
    ("pms_timesheet_to_fam_invoice", "project_management", "fam", "timesheet_approved", "create_invoice_draft"),
    ("inventory_sales_to_srm", "inventory", "srm", "sales_order_confirmed", "reserve_stock"),
]

DEFAULT_POSTING_RULES = [
    ("srm_invoice_posting", "srm", "fam", "sales_invoice"),
    ("srm_receipt_posting", "srm", "fam", "receipt"),
    ("inventory_grni_posting", "inventory", "fam", "inventory_grni"),
    ("inventory_cogs_posting", "inventory", "fam", "inventory_cogs"),
    ("pms_invoice_posting", "project_management", "fam", "pms_invoice"),
]


def company_id_for(user: User) -> int:
    return int(getattr(user, "company_id", None) or getattr(user, "organization_id", None) or 1)


def normalize_module_key(value: str) -> str:
    value = value.strip().lower().replace("-", "_")
    if value in {"accounts", "accounting"}:
        return "fam"
    if value in {"pms", "projects"}:
        return "project_management"
    if value in {"portal"}:
        return "portals"
    if value in {"communications"}:
        return "communication"
    return value


def ensure_business_os_seed(db: Session, company_id: int = 1) -> None:
    now = datetime.now(timezone.utc)
    for module_key, meta in CORE_MODULES.items():
        row = db.query(BOSEnabledModule).filter(BOSEnabledModule.company_id == company_id, BOSEnabledModule.module_key == module_key).first()
        if not row:
            row = BOSEnabledModule(
                company_id=company_id,
                module_key=module_key,
                display_name=meta["display_name"],
                enabled=module_key in DEFAULT_ENABLED_MODULES,
                is_financial_backbone=bool(meta.get("is_financial_backbone")),
                enabled_at=now if module_key in DEFAULT_ENABLED_MODULES else None,
                metadata_json={"home_path": meta.get("home_path"), "optional": meta.get("optional", True)},
            )
            db.add(row)
        else:
            row.display_name = meta["display_name"]
            row.is_financial_backbone = bool(meta.get("is_financial_backbone"))
            row.metadata_json = {**(row.metadata_json or {}), "home_path": meta.get("home_path"), "optional": meta.get("optional", True)}
    db.flush()

    for module_key, depends_on, dep_type, reason in DEFAULT_DEPENDENCIES:
        row = db.query(BOSModuleDependency).filter(BOSModuleDependency.module_key == module_key, BOSModuleDependency.depends_on_module_key == depends_on).first()
        if not row:
            db.add(BOSModuleDependency(module_key=module_key, depends_on_module_key=depends_on, dependency_type=dep_type, reason=reason, active=True))
    db.flush()

    for rule_key, source, target, event_name, action_name in DEFAULT_INTEGRATIONS:
        row = db.query(BOSIntegrationRule).filter(BOSIntegrationRule.company_id == company_id, BOSIntegrationRule.rule_key == rule_key).first()
        if not row:
            db.add(BOSIntegrationRule(company_id=company_id, rule_key=rule_key, source_module=source, target_module=target, event_name=event_name, action_name=action_name, enabled=False))
    db.flush()

    for posting_key, source, target, transaction_type in DEFAULT_POSTING_RULES:
        row = db.query(BOSPostingRule).filter(BOSPostingRule.company_id == company_id, BOSPostingRule.posting_key == posting_key).first()
        if not row:
            db.add(BOSPostingRule(company_id=company_id, posting_key=posting_key, source_module=source, target_module=target, transaction_type=transaction_type, enabled=False))
    db.flush()


def enabled_module_keys(db: Session, company_id: int = 1) -> set[str]:
    ensure_business_os_seed(db, company_id)
    rows = db.query(BOSEnabledModule).filter(BOSEnabledModule.company_id == company_id, BOSEnabledModule.enabled.is_(True)).all()
    return {row.module_key for row in rows}


def is_module_enabled(db: Session, module_key: str, company_id: int = 1) -> bool:
    return normalize_module_key(module_key) in enabled_module_keys(db, company_id)


def assert_module_enabled(db: Session, module_key: str, company_id: int = 1) -> None:
    key = normalize_module_key(module_key)
    if not is_module_enabled(db, key, company_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Business OS module disabled: {key}")


def update_enabled_modules(db: Session, company_id: int, module_keys: Iterable[str], user: User) -> list[BOSEnabledModule]:
    normalized = {normalize_module_key(key) for key in module_keys if normalize_module_key(key) in CORE_MODULES}
    now = datetime.now(timezone.utc)
    rows: list[BOSEnabledModule] = []
    for module_key, meta in CORE_MODULES.items():
        row = db.query(BOSEnabledModule).filter(BOSEnabledModule.company_id == company_id, BOSEnabledModule.module_key == module_key).first()
        if not row:
            row = BOSEnabledModule(company_id=company_id, module_key=module_key, display_name=meta["display_name"], metadata_json={})
            db.add(row)
        next_enabled = module_key in normalized
        if row.enabled != next_enabled:
            db.add(BOSLifecycleEvent(
                company_id=company_id,
                module_key=module_key,
                entity_type="module",
                entity_id=module_key,
                event_name="module_enabled" if next_enabled else "module_disabled",
                status="completed",
                message="Historical data preserved; routes and triggers are gated by Business OS.",
                actor_user_id=user.id,
                evidence_json={"enabled": next_enabled},
            ))
        row.display_name = meta["display_name"]
        row.enabled = next_enabled
        row.is_financial_backbone = bool(meta.get("is_financial_backbone"))
        row.metadata_json = {**(row.metadata_json or {}), "home_path": meta.get("home_path"), "optional": True}
        if next_enabled:
            row.enabled_by = user.id
            row.enabled_at = row.enabled_at or now
            row.disabled_by = None
            row.disabled_at = None
        else:
            row.disabled_by = user.id
            row.disabled_at = now
        rows.append(row)
    return rows


def serialize_module(row: BOSEnabledModule) -> dict[str, object]:
    meta = row.metadata_json or {}
    return {
        "module_key": row.module_key,
        "display_name": row.display_name,
        "enabled": bool(row.enabled),
        "is_financial_backbone": bool(row.is_financial_backbone),
        "optional": bool(meta.get("optional", True)),
        "home_path": meta.get("home_path"),
        "reason": "Financial backbone available for postings" if row.is_financial_backbone else None,
    }
