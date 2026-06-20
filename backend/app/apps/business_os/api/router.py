from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.apps.business_os.models import BOSEnabledModule, BOSEntityLink, BOSIntegrationRule, BOSLifecycleEvent, BOSModuleDependency
from app.apps.business_os.schemas import BOSModulesUpdate
from app.apps.business_os.services.handoff_engine import (
    run_crm_deal_won_handoff,
    run_inventory_to_fam_handoff,
    run_pms_to_invoice_handoff,
    run_srm_engagement_to_pms_handoff,
)
from app.apps.business_os.services.dynamic_layer import ai_answer, customer_720_sections, dashboard_widgets, module_reports, rbac_catalog
from app.apps.business_os.services.module_service import (
    CORE_MODULES,
    SUPPORTED_COMBINATIONS,
    company_id_for,
    enabled_module_keys,
    ensure_business_os_seed,
    serialize_module,
    update_enabled_modules,
)
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/business-os", tags=["Business OS"])


def admin_user(current_user: User = Depends(RequirePermission("settings_view", "settings_manage", "fam_admin", "crm_admin"))) -> User:
    return current_user


@router.get("/modules")
def get_modules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    ensure_business_os_seed(db, company_id)
    rows = (
        db.query(BOSEnabledModule)
        .filter(BOSEnabledModule.company_id == company_id, BOSEnabledModule.module_key.in_(CORE_MODULES.keys()))
        .order_by(BOSEnabledModule.module_key)
        .all()
    )
    enabled = sorted(enabled_module_keys(db, company_id))
    return {"company_id": company_id, "modules": [serialize_module(row) for row in rows], "enabled_modules": enabled, "supported_combinations": SUPPORTED_COMBINATIONS}


@router.put("/modules")
def put_modules(payload: BOSModulesUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_user)):
    company_id = company_id_for(current_user)
    ensure_business_os_seed(db, company_id)
    rows = update_enabled_modules(db, company_id, payload.enabled_modules, current_user)
    db.commit()
    return {"company_id": company_id, "modules": [serialize_module(row) for row in rows], "enabled_modules": sorted(enabled_module_keys(db, company_id)), "supported_combinations": SUPPORTED_COMBINATIONS}


@router.post("/handoffs/crm/deals/{deal_id}/won")
def crm_deal_won_handoff(deal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return run_crm_deal_won_handoff(db, current_user, deal_id)


@router.post("/handoffs/srm/engagements/{engagement_id}/pms-project")
def srm_engagement_pms_handoff(engagement_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return run_srm_engagement_to_pms_handoff(db, current_user, engagement_id)


@router.post("/handoffs/pms/{source_type}/{source_id}/invoice-draft")
def pms_invoice_handoff(source_type: str, source_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return run_pms_to_invoice_handoff(db, current_user, source_type, source_id)


@router.post("/handoffs/inventory/{movement_type}/{movement_id}/post-accounting")
def inventory_accounting_handoff(movement_type: str, movement_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return run_inventory_to_fam_handoff(db, current_user, movement_type, movement_id)


@router.get("/dependencies")
def get_dependencies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_business_os_seed(db, company_id_for(current_user))
    rows = db.query(BOSModuleDependency).order_by(BOSModuleDependency.module_key, BOSModuleDependency.depends_on_module_key).all()
    return [{"module_key": row.module_key, "depends_on_module_key": row.depends_on_module_key, "dependency_type": row.dependency_type, "reason": row.reason, "active": row.active} for row in rows]


@router.get("/dashboard")
def get_dynamic_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    enabled = enabled_module_keys(db, company_id)
    return {"enabled_modules": sorted(enabled), "widgets": dashboard_widgets(enabled)}


@router.get("/reports/catalog")
def get_module_aware_reports(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    enabled = enabled_module_keys(db, company_id)
    return {"enabled_modules": sorted(enabled), "reports": module_reports(enabled)}


@router.get("/rbac/catalog")
def get_module_aware_rbac(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    enabled = enabled_module_keys(db, company_id)
    return {"enabled_modules": sorted(enabled), "roles": rbac_catalog(enabled)}


@router.get("/customer-720")
def get_customer_720(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    enabled = enabled_module_keys(db, company_id)
    return {"enabled_modules": sorted(enabled), "sections": customer_720_sections(enabled)}


@router.post("/ai/ask")
def ask_business_os_ai(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    enabled = enabled_module_keys(db, company_id)
    return ai_answer(enabled, str(payload.get("question") or ""))


@router.get("/integration-rules")
def get_integration_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    ensure_business_os_seed(db, company_id)
    enabled = enabled_module_keys(db, company_id)
    rows = db.query(BOSIntegrationRule).filter(BOSIntegrationRule.company_id == company_id).order_by(BOSIntegrationRule.rule_key).all()
    return [
        {
            "id": row.id,
            "rule_key": row.rule_key,
            "source_module": row.source_module,
            "target_module": row.target_module,
            "event_name": row.event_name,
            "action_name": row.action_name,
            "enabled": row.enabled,
            "source_enabled": row.source_module in enabled,
            "target_enabled": row.target_module in enabled,
            "effective": bool(row.enabled and row.source_module in enabled and row.target_module in enabled),
        }
        for row in rows
    ]


@router.get("/entity-links/{module}/{entity}/{id}")
def get_entity_links(module: str, entity: str, id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    ensure_business_os_seed(db, company_id)
    rows = (
        db.query(BOSEntityLink)
        .filter(
            BOSEntityLink.company_id == company_id,
            BOSEntityLink.active.is_(True),
            or_(
                (BOSEntityLink.source_module == module) & (BOSEntityLink.source_entity == entity) & (BOSEntityLink.source_entity_id == str(id)),
                (BOSEntityLink.target_module == module) & (BOSEntityLink.target_entity == entity) & (BOSEntityLink.target_entity_id == str(id)),
            ),
        )
        .order_by(BOSEntityLink.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "source_module": row.source_module,
            "source_entity": row.source_entity,
            "source_entity_id": row.source_entity_id,
            "target_module": row.target_module,
            "target_entity": row.target_entity,
            "target_entity_id": row.target_entity_id,
            "link_type": row.link_type,
            "active": row.active,
            "metadata_json": row.metadata_json or {},
        }
        for row in rows
    ]


@router.get("/lifecycle/{module}/{entity}/{id}")
def get_lifecycle(module: str, entity: str, id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_id = company_id_for(current_user)
    ensure_business_os_seed(db, company_id)
    rows = (
        db.query(BOSLifecycleEvent)
        .filter(BOSLifecycleEvent.company_id == company_id, BOSLifecycleEvent.module_key == module, BOSLifecycleEvent.entity_type == entity, BOSLifecycleEvent.entity_id == str(id))
        .order_by(BOSLifecycleEvent.created_at.desc(), BOSLifecycleEvent.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "module_key": row.module_key,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "event_name": row.event_name,
            "status": row.status,
            "message": row.message,
            "source_module": row.source_module,
            "target_module": row.target_module,
            "evidence_json": row.evidence_json or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
