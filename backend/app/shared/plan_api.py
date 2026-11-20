"""Customer plans use existing catalog and customer permission checks."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.shared.catalog import Source, authorize, commit
from app.shared.plan_models import CustomerPlan, CustomerEntitlement, PlanLifecycleEvent, UsageLedger
from app.shared import plan_engine as engine
from app.shared import plan_presentation as presentation
from app.shared.offering_contracts import Duration
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
    expected_offering_version: int | None = Field(default=None, ge=0)


class AssignmentPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
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


class ValidityPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration: Duration
    activation: Literal["purchase", "first_use", "selected_date", "approval"] = "purchase"
    start_date: date | None = None
    billing_timezone: str = Field(default="UTC", max_length=80)


class LifecyclePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["activate", "pause", "resume", "suspend", "cancel", "extend", "renew"]
    revision: int = Field(ge=1)
    until: date | None = None


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


@router.post("/validity-preview")
def validity_preview(data: ValidityPreview, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    authorize(user, source, "service", True, db=db)
    from app.shared.offering_contracts import Plan
    config = Plan(duration=data.duration, activation=data.activation)
    start, end = engine.validity_dates(config, data.start_date)
    return {"start_date": start, "end_date": end, "last_access_date": end - timedelta(days=1) if end else None,
        "activation": config.activation, "estimated": config.activation == "first_use", "server_date": date.today(),
        "validity_basis": "date_only_server_calendar", "billing_timezone": data.billing_timezone,
        "automatic_billing_enabled": False, "reminder_delivery_enabled": False}


@router.post("/assignment-preview")
def assignment_preview(data: AssignmentPreview, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    from app.shared.catalog import item_record
    from app.shared.offering_contracts import Plan
    row, detail = item_record(db, user, source, data.kind, data.offering_id, archived=False)
    owner = customer(db, data.customer_id, user)
    config = Plan.model_validate((row.metadata_json or {}).get("plan") or {})
    participants = list(dict.fromkeys(data.beneficiaries))
    if len(participants) > config.beneficiary_limit:
        raise HTTPException(422, "Beneficiary limit exceeded")
    for ident in participants:
        customer(db, ident, user)
    start, end = engine.validity_dates(config, data.start_date)
    return {"offering_id": row.id, "offering_version": detail.version if detail else 0, "name": row.item_name,
        "customer_name": owner.name, "kind": data.kind, "configuration": config.model_dump(mode="json"),
        "price": row.sales_rate, "tax_percent": row.gst_rate, "currency": row.currency,
        "start_date": start, "end_date": end, "last_access_date": end - timedelta(days=1) if end else None,
        "estimated": config.activation == "first_use", "billing_timezone": config.billing.timezone,
        "validity_basis": "date_only_server_calendar", "automatic_billing_enabled": False,
        "reminder_delivery_enabled": False, "payment_collected": False}


@router.post("/{ident}/lifecycle-preview")
def lifecycle_preview(ident: int, data: LifecyclePreview, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    plan = engine.plan_for(db, user, ident, source, True)
    if plan.revision != data.revision:
        raise HTTPException(409, "Plan changed; reload before continuing")
    from app.shared.offering_contracts import Plan
    config = Plan.model_validate(plan.configuration)
    changes = engine.transition_changes(plan, data.action, data.until)
    after = {**engine.snapshot(plan), **changes}
    after_end = changes.get("end_date", plan.end_date)
    benefits = db.query(CustomerEntitlement).filter_by(organization_id=tenant(user), plan_id=ident).all()
    return {"plan_id": plan.id, "kind": plan.kind, "before": engine.snapshot(plan), "after": after,
        "benefits": [{"label": row.definition.get("label", row.benefit_key), "remaining": row.remaining} for row in benefits],
        "benefit_treatment": "retained_unusable" if data.action == "cancel" else "unchanged",
        "charge_amount": "0", "currency": plan.price_snapshot.get("currency"),
        "configured_renewal_price": config.renewal.price if data.action == "renew" else None,
        "invoice_created": False, "payment_collected": False, "refund_created": False,
        "billing_timezone": config.billing.timezone, "expiry_exclusive": True,
        "last_access_date": after_end - timedelta(days=1) if after_end else None,
        "access_after": "blocked" if after["status"] in {"cancelled", "paused", "suspended", "pending"} else "subject_to_validity_and_eligibility"}


@router.post("", status_code=201)
def issue(data: Issue, source: Source = "srm", db: Session = Depends(get_db), user=Depends(get_current_user)):
    guard(db, user, source, True)
    row = engine.issue(db, user, source, data.offering_id, data.kind, data.customer_id, data.request_key, data.start_date, data.beneficiaries, expected_version=data.expected_offering_version)
    commit(db)
    return output(row)


@router.get("")
def list_plans(customer_id: int = Query(gt=0), source: Source = "srm", page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=100), view: Literal["all", "active", "renewals"] = "all", kind: Literal['membership','subscription'] | None = None, status: Literal['active','scheduled','awaiting_first_use','pending_approval','paused','suspended','expired','cancelled'] | None = None, expiry_from: date | None = None, expiry_to: date | None = None, balance: Literal['available','exhausted'] | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
    if expiry_from and expiry_to and expiry_from > expiry_to:
        raise HTTPException(422, 'Expiry range ends before it starts')
    if kind: query = query.filter(CustomerPlan.kind == kind)
    if status: query = query.filter(presentation.state_expression() == status)
    if expiry_from: query = query.filter(CustomerPlan.end_date >= expiry_from)
    if expiry_to: query = query.filter(CustomerPlan.end_date <= expiry_to)
    if balance:
        from sqlalchemy import or_
        available = db.query(CustomerEntitlement.id).filter(CustomerEntitlement.organization_id == tenant(user), CustomerEntitlement.plan_id == CustomerPlan.id,
            or_(CustomerEntitlement.remaining.is_(None), CustomerEntitlement.remaining > 0)).exists()
        query = query.filter(available if balance == 'available' else ~available)
    if view == "active":
        from sqlalchemy import or_
        query = query.filter(CustomerPlan.status == "active", CustomerPlan.start_date <= date.today(),
            or_(CustomerPlan.end_date.is_(None), CustomerPlan.end_date > date.today()))
    elif view == "renewals":
        query = query.filter(CustomerPlan.status.in_(["active", "paused", "suspended", "expired"]), CustomerPlan.end_date.is_not(None))
    if source == "crm":
        from app.apps.crm.api.router import _apply_record_visibility
        visible = _apply_record_visibility(db.query(SRMProduct), catalog_resource(), user, db).with_entities(SRMProduct.id).subquery()
        query = query.filter(SRMProduct.id.in_(db.query(visible.c.id)))
    total = query.count()
    ordering = (CustomerPlan.end_date.asc(), CustomerPlan.id.desc()) if view == "renewals" else (CustomerPlan.id.desc(),)
    rows = query.order_by(*ordering).offset((page-1)*per_page).limit(per_page).all()
    can_issue = True
    try:
        authorize(user,source,"service",True,db=db)
    except HTTPException as exc:
        if exc.status_code != 403: raise
        can_issue = False
    plan_ids = [row.id for row in rows]
    offerings = {row.id:row for row in db.query(SRMProduct).filter(SRMProduct.organization_id == tenant(user), SRMProduct.id.in_([p.offering_id for p in rows])).all()}
    balances = {}
    for benefit in db.query(CustomerEntitlement).filter(CustomerEntitlement.organization_id == tenant(user), CustomerEntitlement.plan_id.in_(plan_ids)).all():
        balances.setdefault(benefit.plan_id, []).append(benefit)
    return {"items": [{**output(row), **presentation.summary(row, offerings[row.offering_id], balances.get(row.id,[]))} for row in rows], "total": total, "can_issue":can_issue, "server_date":date.today()}


@router.get("/{ident}")
def detail(ident: int, source: Source = "srm", usage_page: int = Query(1,ge=1), history_page: int = Query(1,ge=1), per_page: int = Query(25,ge=1,le=100), db: Session = Depends(get_db), user=Depends(get_current_user)):
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
    from app.apps.srm.models import SRMProduct
    from app.models.user import User
    history_query = db.query(PlanLifecycleEvent).filter_by(organization_id=tenant(user), plan_id=ident)
    usage_query = db.query(UsageLedger).filter(UsageLedger.organization_id==tenant(user), UsageLedger.entitlement_id.in_(ids))
    history = history_query.order_by(PlanLifecycleEvent.id.desc()).offset((history_page-1)*per_page).limit(per_page).all()
    usage = usage_query.order_by(UsageLedger.id.desc()).offset((usage_page-1)*per_page).limit(per_page).all()
    actor_ids = {e.created_by for e in [*history,*usage] if e.created_by}
    actors = {u.id:u.email for u in db.query(User).filter(User.id.in_(actor_ids)).all()}
    labels = {b.id:b.definition.get('label',b.benefit_key) for b in benefits}
    reversals = {e.reverses_id:e.id for e in usage_query.filter(UsageLedger.reverses_id.in_([e.id for e in usage])).all()}
    offering = db.get(SRMProduct, plan.offering_id)
    return {**output(plan), **presentation.summary(plan,offering,benefits), "server_date": date.today(), "can_manage": can_manage,
        "actions":presentation.actions(plan,can_manage), "benefits": [{"id": b.id, **b.definition, "remaining": b.remaining} for b in benefits],
        "history_total":history_query.count(), "usage_total":usage_query.count(),
        "history": [{"id":e.id,"action": e.action, "description":presentation.history_text(e), "before": e.before, "after": e.after, "created_by":e.created_by, "actor":actors.get(e.created_by,'System / former team member'),"created_at": e.created_at} for e in history],
        "usage": [{"id": e.id, "entitlement_id": e.entitlement_id,"benefit_name":labels[e.entitlement_id], "quantity": e.quantity, "reference": e.reference,"source_reference":e.reference, "reverses_id": e.reverses_id,"reversed_by_id":reversals.get(e.id),"created_by":e.created_by,"actor":actors.get(e.created_by,'System / former team member'), "created_at": e.created_at} for e in usage]}


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
