"""Customer plans use existing catalog and customer permission checks."""
from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.shared.catalog import Source, authorize, commit
from app.shared.plan_models import CustomerPlan, CustomerEntitlement, PlanLifecycleEvent, UsageLedger
from app.shared import plan_engine as engine
from app.apps.srm.services.commercial import customer, tenant

router = APIRouter(prefix="/customer-plans", tags=["Customer plans"])


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=180)


class Issue(Input):
    offering_id: int = Field(gt=0)
    kind: Literal["membership", "subscription"]
    customer_id: int = Field(gt=0)
    start_date: date | None = None
    beneficiaries: list[int] = Field(default_factory=list, max_length=100000)


class Transition(Input):
    action: Literal["activate", "pause", "resume", "suspend", "cancel", "expire", "extend", "renew", "transfer"]
    revision: int = Field(ge=1)
    until: date | None = None
    customer_id: int | None = Field(default=None, gt=0)


class Consume(Input):
    quantity: Decimal = Field(gt=0, le=1000000000, decimal_places=4)
    reference: str = Field(min_length=1, max_length=180)
    offering_id: int | None = Field(default=None, gt=0)
    location: str | None = Field(default=None, max_length=180)
    lifecycle_event: Literal["booking", "check_in", "attendance", "completion", "purchase"] = "completion"


def output(row):
    return {"id": row.id, "offering_id": row.offering_id, "customer_id": row.customer_id, "kind": row.kind,
        "number": row.number, **engine.snapshot(row), "configuration": row.configuration,
        "beneficiaries": row.beneficiaries, "price_snapshot": row.price_snapshot}


def guard(db, user, source, write=False):
    authorize(user, source, "service", write, db=db)
    # Existing pack boundaries must not be bypassed with a new unregistered table.
    if db.info.get("business_pack_scope") is not None:
        raise HTTPException(503, "Customer plan operations require native context enrollment")


@router.post("", status_code=201)
def issue(data: Issue, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    row = engine.issue(db, user, source, data.offering_id, data.kind, data.customer_id, data.request_key, data.start_date, data.beneficiaries)
    commit(db)
    return output(row)


@router.get("")
def list_plans(customer_id: int = Query(gt=0), source: Source = "srm", page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=100), db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source)
    customer(db, customer_id, user)
    from app.apps.srm.models import SRMProduct
    from app.shared.catalog import restrict_workspaces, catalog_resource
    from app.shared.catalog_branches import availability_clause, selected_branch
    query = db.query(CustomerPlan).join(SRMProduct, SRMProduct.id == CustomerPlan.offering_id).filter(
        CustomerPlan.organization_id == tenant(user), CustomerPlan.customer_id == customer_id,
        SRMProduct.organization_id == tenant(user), SRMProduct.deleted_at.is_(None),
        availability_clause(SRMProduct, selected_branch(user)))
    query = restrict_workspaces(query, SRMProduct, db, user)
    if source == "crm":
        from app.apps.crm.api.router import _apply_record_visibility
        visible = _apply_record_visibility(db.query(SRMProduct), catalog_resource(), user, db).with_entities(SRMProduct.id).subquery()
        query = query.filter(SRMProduct.id.in_(db.query(visible.c.id)))
    total = query.count()
    rows = query.order_by(CustomerPlan.id.desc()).offset((page-1)*per_page).limit(per_page).all()
    return {"items": [output(row) for row in rows], "total": total}


@router.get("/{ident}")
def detail(ident: int, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source)
    plan = engine.plan_for(db, user, ident, source)
    can_manage = True
    try:
        engine.plan_for(db,user,ident,source,True)
    except HTTPException as exc:
        if exc.status_code not in {403,404}: raise
        can_manage = False
    benefits = db.query(CustomerEntitlement).filter_by(organization_id=tenant(user), plan_id=ident).all()
    ids = [b.id for b in benefits]
    return {**output(plan), "can_manage": can_manage, "benefits": [{"id": b.id, **b.definition, "remaining": b.remaining} for b in benefits],
        "history": [{"action": e.action, "before": e.before, "after": e.after, "created_at": e.created_at} for e in db.query(PlanLifecycleEvent).filter_by(organization_id=tenant(user), plan_id=ident).order_by(PlanLifecycleEvent.id).all()],
        "usage": [{"id": e.id, "entitlement_id": e.entitlement_id, "quantity": e.quantity, "reference": e.reference, "reverses_id": e.reverses_id, "created_at": e.created_at} for e in db.query(UsageLedger).filter(UsageLedger.organization_id==tenant(user), UsageLedger.entitlement_id.in_(ids)).order_by(UsageLedger.id.desc()).limit(200).all()]}


@router.post("/{ident}/lifecycle")
def lifecycle(ident: int, data: Transition, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    row = engine.transition(db, user, ident, data.action, data.request_key, data.revision, source, data.until, data.customer_id)
    commit(db)
    return output(row)


@router.post("/entitlements/{ident}/consume")
def consume(ident: int, data: Consume, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    row = engine.consume(db, user, ident, data.quantity, data.request_key, data.reference, source, data.offering_id, data.location, data.lifecycle_event)
    commit(db)
    return {"id": row.id, "quantity": row.quantity}


@router.post("/usage/{ident}/reverse")
def reverse(ident: int, data: Input, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    row = engine.reverse(db, user, ident, data.request_key, source)
    commit(db)
    return {"id": row.id, "quantity": row.quantity}
