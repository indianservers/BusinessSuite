from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

def business_date(zone: str, at: datetime | None = None) -> date:
    stamp = at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError('The billing clock must include a timezone')
    return stamp.astimezone(ZoneInfo(zone)).date()

def billing_today(db, user):
    from app.shared.form_defaults import effective
    from app.apps.srm.services.commercial import tenant
    branch = getattr(user, '_suite_branch_id', None)
    context = db.info.get('branch_context')
    if context is not None:
        branch = context.branch_id
    values = effective(db, tenant(user), 'srm', branch if isinstance(branch, int) else None)['values']
    return business_date(values['timezone'])


def occurrence_dates(start: date, count: int, rule: str, *, offset: int = 0, interval: int = 1) -> list[date]:
    """Anchor calendar periods to the original day, avoiding month-end drift."""
    if not 1 <= count <= 120:
        raise ValueError("Occurrences must be between 1 and 120")
    if not 1 <= interval <= 120:
        raise ValueError("Repeat interval must be between 1 and 120")
    if not 0 <= offset <= 100000:
        raise ValueError("Schedule offset is outside the supported range")
    rule = rule.strip().lower()
    months = {"monthly": 1, "quarterly": 3, "yearly": 12, "annually": 12}
    if rule not in {*months, "daily", "weekly"}:
        raise ValueError("Choose daily, weekly, monthly, quarterly, or yearly")
    result = []
    for index in range(offset, offset + count):
        if rule in months:
            offset = start.year * 12 + start.month - 1 + months[rule] * index * interval
            year, month = divmod(offset, 12)
            month += 1
            result.append(date(year, month, min(start.day, monthrange(year, month)[1])))
        else:
            result.append(start + timedelta(days=index * interval * (7 if rule == "weekly" else 1)))
    return result

def apply_invoice_settings(db, invoice, milestone):
    """Use the same frozen presentation settings for manual and scheduled drafts."""
    metadata = milestone.metadata_json or {}
    if not metadata.get('recurring'):
        return
    from app.shared.models import ServicePolicy
    invoice.issue_date = milestone.due_date
    invoice.due_date = milestone.due_date + timedelta(days=int(metadata.get('payment_terms_days', 30)))
    db.flush()
    snapshot = db.query(ServicePolicy).filter_by(scope_key=f'form-snapshot:{invoice.organization_id}:srm:invoice:{invoice.id}', organization_id=invoice.organization_id).first()
    if snapshot:
        keys = ('subject', 'customer_notes', 'terms', 'invoice_template', 'payment_mode_id', 'payment_method', 'salesperson_name', 'order_number')
        snapshot.values_json = {**(snapshot.values_json or {}), **{key: metadata[key] for key in keys if key in metadata}, 'payment_terms_days': metadata.get('payment_terms_days', 30)}

def extend_ongoing_schedule(db, plan, today):
    from decimal import Decimal
    from app.shared.models import ServicePolicy
    from app.apps.srm.models import SRMBillingMilestone
    profile = db.query(ServicePolicy).filter_by(scope_key=f'recurring-profile:{plan.organization_id or 1}:{plan.id}', organization_id=plan.organization_id or 1, kind='recurring_profile').with_for_update().first()
    if profile is None:
        return 0
    values = profile.values_json
    if not values.get("ongoing", True):
        return 0
    cursor = int(values['next_index'])
    dates = occurrence_dates(date.fromisoformat(values['start_date']), 12, values['rule'], offset=cursor, interval=int(values.get('interval', 1)))
    if dates[0] > today + timedelta(days=31):
        return 0
    metadata = dict(values['metadata'])
    amount = Decimal(values['amount'])
    existing = {row.due_date for row in db.query(SRMBillingMilestone).filter_by(billing_plan_id=plan.id).all()}
    created = 0
    for due in dates:
        if due in existing:
            continue
        db.add(SRMBillingMilestone(billing_plan_id=plan.id, name=f"{metadata.get('subject') or plan.name} · {due.isoformat()}", status='ready' if metadata.get('automatic_drafts') else 'pending', due_date=due, amount=amount, metadata_json=metadata))
        created += 1
    plan.total_amount = Decimal(plan.total_amount or 0) + amount * created
    profile.values_json = {**values, 'next_index': cursor + 12}
    db.flush()
    return created


def recurring_details(db, user):
    """Occurrence details for the existing SRM report directory, without currency totals."""
    from app.apps.srm.models import SRMBillingPlan, SRMBillingMilestone, SRMEngagement, SRMInvoice
    from app.apps.srm.api.router import engagement_query, scoped, authorized_invoice_query
    rows = db.query(SRMBillingMilestone, SRMBillingPlan, SRMEngagement).join(
        SRMBillingPlan, SRMBillingPlan.id == SRMBillingMilestone.billing_plan_id).join(
        SRMEngagement, SRMEngagement.id == SRMBillingPlan.engagement_id).filter(
        scoped(SRMBillingPlan.organization_id, user),
        SRMEngagement.id.in_(engagement_query(db, user).with_entities(SRMEngagement.id)),
        SRMBillingMilestone.metadata_json['recurring'].as_boolean() == True,
    ).order_by(SRMBillingMilestone.due_date, SRMBillingMilestone.id).all()
    draft_ids = [milestone.invoice_draft_id for milestone, _, _ in rows if milestone.invoice_draft_id]
    invoices = {row.invoice_draft_id: row for row in authorized_invoice_query(db, user).filter(
        SRMInvoice.invoice_draft_id.in_(draft_ids), SRMInvoice.deleted_at.is_(None)).all()} if draft_ids else {}
    result = []
    for milestone, plan, engagement in rows:
        invoice = invoices.get(milestone.invoice_draft_id)
        result.append({'id': milestone.id, 'plan_id': plan.id, 'plan_name': plan.name,
            'customer_id': engagement.customer_id, 'engagement_id': engagement.id,
            'recurrence_rule': plan.recurrence_rule, 'plan_status': plan.status,
            'date': milestone.due_date.isoformat() if milestone.due_date else None,
            'total_amount': str(milestone.amount), 'currency': plan.currency,
            'status': invoice.status if invoice else milestone.status,
            'invoice_id': invoice.id if invoice else None,
            'invoice_number': invoice.invoice_number if invoice else None,
            'automatic_drafts': bool((milestone.metadata_json or {}).get('automatic_drafts'))})
    return result
