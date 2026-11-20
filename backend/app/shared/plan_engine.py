"""Transactional plan and entitlement operations. Callers own the transaction."""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import update
from app.apps.srm.services.commercial import tenant, lock_tenant, customer
from app.shared.offering_contracts import Plan, Benefit
from app.shared.plan_models import CustomerPlan, CustomerEntitlement, UsageLedger, PlanLifecycleEvent


def end_date(start, duration):
    if duration.unit == "lifetime":
        return None
    if duration.unit == "custom":
        return duration.end
    if duration.unit in {"day", "week"}:
        try:
            return start + timedelta(days=duration.count * (7 if duration.unit == "week" else 1))
        except OverflowError:
            raise HTTPException(422, "Plan duration exceeds the supported date range") from None
    months = duration.count * (12 if duration.unit == "year" else 1)
    month = start.month - 1 + months
    year, month = start.year + month // 12, month % 12 + 1
    if not 1 <= year <= 9999:
        raise HTTPException(422, "Plan duration exceeds the supported date range")
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def validity_dates(config, start=None):
    """Shared by assignment and read-only UX previews; expiry is exclusive."""
    if config.activation == "selected_date" and start is None:
        raise HTTPException(422, "Select an activation date")
    start = start or config.duration.start or date.today()
    end = end_date(start, config.duration)
    if end and end <= start:
        raise HTTPException(422, "Plan expiry must follow activation")
    return start, end


def snapshot(plan):
    return {"status": plan.status, "start_date": str(plan.start_date), "end_date": str(plan.end_date) if plan.end_date else None,
            "customer_id": plan.customer_id, "revision": plan.revision}


def event(db, user, plan, action, key, before, intent=None):
    db.add(PlanLifecycleEvent(organization_id=tenant(user), plan_id=plan.id, request_key=key,
        action=action, before=before, after={**snapshot(plan), **({"request": intent} if intent is not None else {})}, created_by=user.id))


def issue(db, user, source, offering_id, kind, customer_id, source_key, start=None, beneficiaries=None, *, configuration=None, price_snapshot=None, expected_version=None):
    from app.shared.catalog import item_record
    lock_tenant(db, user)
    row, detail = item_record(db, user, source, kind, offering_id, archived=False)
    if kind not in {"membership", "subscription"}:
        raise HTTPException(422, "Only membership and subscription plans can be issued")
    customer(db, customer_id, user)
    beneficiaries = list(dict.fromkeys(beneficiaries or []))
    previous = db.query(CustomerPlan).filter_by(organization_id=tenant(user), source_key=source_key).first()
    if previous:
        if (previous.offering_id, previous.customer_id, previous.kind, previous.beneficiaries) != (offering_id, customer_id, kind, beneficiaries or []):
            raise HTTPException(409, "Issuance key was already used for another purchase")
        if start and start != previous.start_date:
            raise HTTPException(409, "Issuance key has a different activation date")
        if expected_version is not None and previous.price_snapshot.get("version") != expected_version:
            raise HTTPException(409, "Issuance key has different plan terms")
        return previous
    if expected_version is not None and expected_version != (detail.version if detail else 0):
        raise HTTPException(409, "Plan terms changed. Refresh the preview before assigning.")
    config = Plan.model_validate(configuration or (row.metadata_json or {}).get("plan") or {})
    start, end = validity_dates(config, start)
    participants = list(dict.fromkeys(beneficiaries or []))
    if len(participants) > config.beneficiary_limit:
        raise HTTPException(422, "Beneficiary limit exceeded")
    # Beneficiaries use existing canonical customer records and their access rules.
    for ident in participants:
        customer(db, ident, user)
    status = "active" if config.activation in {"purchase", "selected_date"} else "pending"
    plan = CustomerPlan(organization_id=tenant(user), offering_id=row.id, customer_id=customer_id, kind=kind,
        number=f"{kind[:3].upper()}-{uuid4().hex[:16].upper()}", source_key=source_key, status=status,
        start_date=start, end_date=end, configuration=config.model_dump(mode="json"), beneficiaries=participants,
        price_snapshot={"name": row.item_name, **(price_snapshot or {"price": str(row.sales_rate), "currency": row.currency, "tax": str(row.gst_rate), "version": detail.version if detail else 0})},
        revision=1, created_by=user.id)
    db.add(plan); db.flush()
    for benefit in config.benefits:
        db.add(CustomerEntitlement(organization_id=tenant(user), plan_id=plan.id, benefit_key=benefit.key,
            definition=benefit.model_dump(mode="json"), remaining=benefit.allowance, revision=1))
    event(db, user, plan, "issue", source_key, {})
    db.flush()
    return plan


def plan_for(db, user, ident, source="srm", write=False):
    from app.shared.catalog import item_record
    query = db.query(CustomerPlan).filter_by(id=ident, organization_id=tenant(user))
    plan = query.populate_existing().with_for_update().first() if write else query.first()
    if not plan:
        raise HTTPException(404, "Customer plan not found")
    customer(db, plan.customer_id, user)
    offering, _ = item_record(db, user, source, plan.kind, plan.offering_id, write=write)
    from app.shared.catalog_branches import assert_available
    assert_available(offering, user)
    return plan


def transition_changes(plan, action, until=None, customer_id=None):
    """Validate lifecycle effects without mutating a plan or granting benefits."""
    config = Plan.model_validate(plan.configuration)
    allowed = {"activate": ({"pending"}, "active"), "pause": ({"active"}, "paused"),
        "resume": ({"paused", "suspended"}, "active"), "suspend": ({"active"}, "suspended"),
        "cancel": ({"pending", "active", "paused", "suspended"}, "cancelled"),
        "expire": ({"active", "paused", "suspended"}, "expired")}
    if action in allowed:
        states, target = allowed[action]
        if plan.status not in states or (action == "pause" and not config.allow_pause):
            raise HTTPException(422, "Operation is not permitted in the current state")
        if action in {"activate", "resume"} and plan.end_date and plan.end_date <= date.today():
            raise HTTPException(422, "Expired plans must be renewed before activation")
        if action == "expire" and (plan.end_date is None or plan.end_date > date.today()):
            raise HTTPException(422, "Plan has not reached expiry")
        return {"status": target}
    elif action in {"extend", "renew"}:
        if plan.status == "cancelled" or not until or until <= max(plan.end_date or date.today(), date.today()):
            raise HTTPException(422, "Select a later expiry for a non-cancelled plan")
        return {"end_date": until, **({"status": "active"} if action == "renew" else {})}
    elif action == "transfer":
        if not config.allow_transfer or not customer_id or plan.status == "cancelled":
            raise HTTPException(422, "Transfer is not permitted")
        return {"customer_id": customer_id}
    else:
        raise HTTPException(422, "Unsupported lifecycle operation")


def transition(db, user, ident, action, key, revision, source="srm", until=None, customer_id=None):
    lock_tenant(db, user)
    plan = plan_for(db, user, ident, source, True)
    intent = {"revision": revision, "until": str(until) if until else None, "customer_id": customer_id}
    old = db.query(PlanLifecycleEvent).filter_by(organization_id=tenant(user), request_key=key).first()
    if old:
        if old.plan_id != ident or old.action != action or old.after.get("request") != intent:
            raise HTTPException(409, "Lifecycle key was already used")
        return plan
    if plan.revision != revision:
        raise HTTPException(409, "Plan changed; reload before saving")
    before = snapshot(plan)
    changes = transition_changes(plan, action, until, customer_id)
    if action == "transfer":
        customer(db, customer_id, user)
    for name, value in changes.items():
        setattr(plan, name, value)
    plan.revision += 1
    event(db, user, plan, action, key, before, intent)
    db.flush()
    return plan


def eligible(rules, day, offering_id=None, location=None, groups=()):
    return (not rules.offering_ids or offering_id in rules.offering_ids) and (not rules.locations or location in rules.locations) and (
        not rules.customer_groups or bool(set(groups) & set(rules.customer_groups))) and (
        not rules.weekdays or day.weekday() in rules.weekdays) and day not in rules.blackout_dates


def consume(db, user, entitlement_id, quantity, key, reference, source="srm", offering_id=None, location=None, lifecycle_event="completion"):
    quantity = Decimal(str(quantity))
    if not quantity.is_finite() or quantity <= 0:
        raise HTTPException(422, "Usage quantity must be positive and finite")
    lock_tenant(db, user)
    entitlement = db.query(CustomerEntitlement).filter_by(id=entitlement_id, organization_id=tenant(user)).populate_existing().with_for_update().first()
    if not entitlement:
        raise HTTPException(404, "Entitlement not found")
    plan = plan_for(db, user, entitlement.plan_id, source, True)
    prior = db.query(UsageLedger).filter_by(organization_id=tenant(user), request_key=key).first()
    if prior:
        if prior.entitlement_id != entitlement_id or prior.quantity != quantity or prior.reference != reference or prior.reverses_id:
            raise HTTPException(409, "Usage key has another payload")
        return prior
    day = date.today()
    benefit = Benefit.model_validate(entitlement.definition)
    config = Plan.model_validate(plan.configuration)
    if plan.status == "pending" and config.activation == "first_use" and day >= plan.start_date:
        before = snapshot(plan)
        plan.status = "active"
        plan.start_date = day
        plan.end_date = end_date(day, config.duration)
        plan.revision += 1
        event(db, user, plan, "first_use", "first-use:" + str(plan.id), before)
    if plan.status != "active" or day < plan.start_date or (plan.end_date and day >= plan.end_date):
        raise HTTPException(422, "Plan is not active within its access period")
    if lifecycle_event != benefit.consumption_event:
        raise HTTPException(422, "Usage is not due at this lifecycle event")
    if not eligible(config.eligibility, day, offering_id, location) or not eligible(benefit.eligibility, day, offering_id, location):
        raise HTTPException(422, "Benefit is not eligible for this offering, location or date")
    # Conditional SQL protects the balance even on engines without row locks.
    if entitlement.remaining is not None:
        result = db.execute(update(CustomerEntitlement).where(CustomerEntitlement.id == entitlement_id,
            CustomerEntitlement.organization_id == tenant(user), CustomerEntitlement.remaining >= quantity)
            .values(remaining=CustomerEntitlement.remaining - quantity, revision=CustomerEntitlement.revision + 1).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise HTTPException(409, "Insufficient remaining credits")
        db.expire(entitlement)
    entry = UsageLedger(organization_id=tenant(user), entitlement_id=entitlement_id, request_key=key,
        quantity=quantity, reference=reference, created_by=user.id)
    db.add(entry); db.flush()
    return entry


def reverse(db, user, ledger_id, key, source="srm"):
    lock_tenant(db, user)
    entry = db.query(UsageLedger).filter_by(id=ledger_id, organization_id=tenant(user)).first()
    if not entry or entry.reverses_id:
        raise HTTPException(404, "Original usage entry not found")
    entitlement = db.query(CustomerEntitlement).filter_by(id=entry.entitlement_id, organization_id=tenant(user)).with_for_update().one()
    plan_for(db, user, entitlement.plan_id, source, True)
    prior = db.query(UsageLedger).filter_by(organization_id=tenant(user), request_key=key).first()
    if prior:
        if prior.reverses_id != entry.id:
            raise HTTPException(409, "Reversal key was already used")
        return prior
    if db.query(UsageLedger.id).filter_by(reverses_id=entry.id).first():
        raise HTTPException(409, "Usage was already reversed")
    if entitlement.remaining is not None:
        entitlement.remaining += entry.quantity
        entitlement.revision += 1
    reversal = UsageLedger(organization_id=tenant(user), entitlement_id=entry.entitlement_id, request_key=key,
        quantity=-entry.quantity, reference=entry.reference, reverses_id=entry.id, created_by=user.id)
    db.add(reversal); db.flush()
    return reversal
