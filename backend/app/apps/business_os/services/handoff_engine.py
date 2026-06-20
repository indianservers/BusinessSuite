from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.apps.business_os.models import BOSEntityLink, BOSLifecycleEvent
from app.apps.business_os.services.adapters import CRMAdapter, FAMAdapter, InventoryAdapter, PMSAdapter, SRMAdapter
from app.apps.business_os.services.module_service import company_id_for, is_module_enabled
from app.models.user import User


def _event(
    db: Session,
    user: User,
    *,
    company_id: int,
    module_key: str,
    entity_type: str,
    entity_id: int | str,
    event_name: str,
    status: str,
    message: str,
    source_module: str | None = None,
    target_module: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    db.add(
        BOSLifecycleEvent(
            company_id=company_id,
            module_key=module_key,
            entity_type=entity_type,
            entity_id=str(entity_id),
            event_name=event_name,
            status=status,
            message=message,
            source_module=source_module,
            target_module=target_module,
            actor_user_id=user.id,
            evidence_json=evidence or {},
        )
    )


def _link(
    db: Session,
    *,
    company_id: int,
    source_module: str,
    source_entity: str,
    source_entity_id: int | str,
    target_module: str,
    target_entity: str,
    target_entity_id: int | str,
    link_type: str,
    metadata: dict[str, Any] | None = None,
) -> BOSEntityLink | None:
    existing = (
        db.query(BOSEntityLink)
        .filter(
            BOSEntityLink.company_id == company_id,
            BOSEntityLink.source_module == source_module,
            BOSEntityLink.source_entity == source_entity,
            BOSEntityLink.source_entity_id == str(source_entity_id),
            BOSEntityLink.target_module == target_module,
            BOSEntityLink.target_entity == target_entity,
            BOSEntityLink.target_entity_id == str(target_entity_id),
        )
        .first()
    )
    if existing:
        return existing
    row = BOSEntityLink(
        company_id=company_id,
        source_module=source_module,
        source_entity=source_entity,
        source_entity_id=str(source_entity_id),
        target_module=target_module,
        target_entity=target_entity,
        target_entity_id=str(target_entity_id),
        link_type=link_type,
        metadata_json=metadata or {},
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return row


def _skipped(db: Session, user: User, company_id: int, *, source_module: str, target_module: str, entity_type: str, entity_id: int | str, event_name: str, message: str) -> dict[str, Any]:
    _event(
        db,
        user,
        company_id=company_id,
        module_key=source_module,
        entity_type=entity_type,
        entity_id=entity_id,
        event_name=event_name,
        status="skipped",
        message=message,
        source_module=source_module,
        target_module=target_module,
    )
    db.commit()
    return {"status": "skipped", "idempotent": True, "message": message, "source_module": source_module, "target_module": target_module}


def run_crm_deal_won_handoff(db: Session, user: User, deal_id: int) -> dict[str, Any]:
    company_id = company_id_for(user)
    crm = CRMAdapter(db, user, company_id)
    srm = SRMAdapter(db, user, company_id)
    if not crm.is_enabled():
        return _skipped(db, user, company_id, source_module="crm", target_module="srm", entity_type="deal", entity_id=deal_id, event_name="crm_deal_won_handoff_skipped", message="CRM is not enabled")
    if not srm.is_enabled():
        return _skipped(db, user, company_id, source_module="crm", target_module="srm", entity_type="deal", entity_id=deal_id, event_name="crm_deal_won_handoff_skipped", message="SRM not enabled")

    result = srm.create_linked_record("sales_order_from_crm_deal", {"deal_id": deal_id})
    sales_order = result.get("sales_order") or {}
    engagement = result.get("engagement") or {}
    billing_plan = result.get("billing_plan") or {}
    if sales_order.get("id"):
        _link(db, company_id=company_id, source_module="crm", source_entity="deal", source_entity_id=deal_id, target_module="srm", target_entity="sales_order", target_entity_id=sales_order["id"], link_type="crm_won_handoff")
    if engagement.get("id"):
        _link(db, company_id=company_id, source_module="crm", source_entity="deal", source_entity_id=deal_id, target_module="srm", target_entity="engagement", target_entity_id=engagement["id"], link_type="crm_won_handoff")
    if billing_plan.get("id"):
        _link(db, company_id=company_id, source_module="crm", source_entity="deal", source_entity_id=deal_id, target_module="srm", target_entity="billing_plan", target_entity_id=billing_plan["id"], link_type="quote_billing_basis")
    _event(
        db,
        user,
        company_id=company_id,
        module_key="crm",
        entity_type="deal",
        entity_id=deal_id,
        event_name="crm_deal_won_handoff",
        status="idempotent" if result.get("idempotent") else "created",
        message="CRM Deal Won processed through Business OS optional handoff engine.",
        source_module="crm",
        target_module="srm",
        evidence={"sales_order_id": sales_order.get("id"), "engagement_id": engagement.get("id"), "billing_plan_id": billing_plan.get("id")},
    )
    db.commit()
    return result | {"status": "idempotent" if result.get("idempotent") else "created"}


def run_srm_engagement_to_pms_handoff(db: Session, user: User, engagement_id: int) -> dict[str, Any]:
    company_id = company_id_for(user)
    srm = SRMAdapter(db, user, company_id)
    pms = PMSAdapter(db, user, company_id)
    if not srm.is_enabled():
        return _skipped(db, user, company_id, source_module="srm", target_module="project_management", entity_type="engagement", entity_id=engagement_id, event_name="srm_pms_handoff_skipped", message="SRM is not enabled")
    if not pms.is_enabled():
        return _skipped(db, user, company_id, source_module="srm", target_module="project_management", entity_type="engagement", entity_id=engagement_id, event_name="srm_pms_handoff_skipped", message="PMS is not enabled")

    from app.apps.srm.api.router import create_pms_project

    result = create_pms_project(engagement_id, db, user)
    project = result.get("project") or {}
    if project.get("id"):
        _link(db, company_id=company_id, source_module="srm", source_entity="engagement", source_entity_id=engagement_id, target_module="project_management", target_entity="project", target_entity_id=project["id"], link_type="delivery_handoff")
    _event(
        db,
        user,
        company_id=company_id,
        module_key="srm",
        entity_type="engagement",
        entity_id=engagement_id,
        event_name="srm_engagement_to_pms_project",
        status="idempotent" if result.get("idempotent") else "created",
        message="SRM engagement processed through Business OS optional handoff engine.",
        source_module="srm",
        target_module="project_management",
        evidence={"pms_project_id": project.get("id")},
    )
    db.commit()
    return result | {"status": "idempotent" if result.get("idempotent") else "created"}


def run_pms_to_invoice_handoff(db: Session, user: User, source_type: str, source_id: int) -> dict[str, Any]:
    company_id = company_id_for(user)
    pms = PMSAdapter(db, user, company_id)
    srm_enabled = is_module_enabled(db, "srm", company_id)
    fam_enabled = is_module_enabled(db, "fam", company_id)
    if not pms.is_enabled():
        return _skipped(db, user, company_id, source_module="project_management", target_module="srm", entity_type=source_type, entity_id=source_id, event_name="pms_invoice_handoff_skipped", message="PMS is not enabled")
    if not (srm_enabled or fam_enabled):
        return _skipped(db, user, company_id, source_module="project_management", target_module="srm", entity_type=source_type, entity_id=source_id, event_name="pms_invoice_handoff_skipped", message="Billing module not enabled")
    _event(db, user, company_id=company_id, module_key="project_management", entity_type=source_type, entity_id=source_id, event_name="pms_invoice_handoff_ready", status="ready", message="Billing module is enabled; invoice draft creation can proceed.", source_module="project_management", target_module="srm" if srm_enabled else "fam")
    db.commit()
    return {"status": "ready", "message": "Billing module is enabled", "source_module": "project_management", "target_module": "srm" if srm_enabled else "fam"}


def run_inventory_to_fam_handoff(db: Session, user: User, movement_type: str, movement_id: int) -> dict[str, Any]:
    company_id = company_id_for(user)
    inventory = InventoryAdapter(db, user, company_id)
    fam = FAMAdapter(db, user, company_id)
    if not inventory.is_enabled():
        return _skipped(db, user, company_id, source_module="srm", target_module="fam", entity_type=movement_type, entity_id=movement_id, event_name="srm_inventory_accounting_handoff_skipped", message="Sales & Inventory is not enabled")
    result = fam.post_accounting(movement_type, {"movement_id": movement_id, "movement_type": movement_type})
    _event(
        db,
        user,
        company_id=company_id,
        module_key="srm",
        entity_type=movement_type,
        entity_id=movement_id,
        event_name="srm_inventory_to_fam_accounting",
        status=result["status"],
        message=result["message"],
        source_module="srm",
        target_module="fam",
        evidence=result,
    )
    db.commit()
    return result
