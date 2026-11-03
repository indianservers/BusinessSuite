"""Capture source changes atomically; never contact a provider during flush."""
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from .customer_models import CustomerEvent

SOURCES = {
    'service_follow_ups': ('follow_up', ('status', 'due_at'), 'due_at'),
    'srm_sales_orders': ('order', ('status', 'expected_end_date'), 'expected_end_date'),
    'srm_invoices': ('invoice', ('status', 'due_date', 'balance_amount', 'paid_amount'), 'due_date'),
    'srm_engagements': ('service', ('status', 'planned_start_date', 'planned_end_date'), 'planned_end_date'),
    'srm_contracts': ('contract', ('status', 'expiry_date'), 'expiry_date'),
    'crm_leads': ('lead', ('status', 'next_follow_up_at'), 'next_follow_up_at'),
    'crm_meetings': ('meeting', ('status', 'start_time'), 'start_time'),
    'crm_quotations': ('quotation', ('status', 'expiry_date', 'valid_until'), 'expiry_date'),
    'communication_customer_shipments': ('shipment', ('status', 'expected_date', 'tracking_url'), 'expected_date'),
}


def values(obj):
    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (date, datetime, Decimal)):
            value = str(value)
        if column.name in {'id', 'status', 'title', 'name', 'order_number', 'invoice_number', 'contract_number',
                           'engagement_number', 'reference', 'currency', 'total_amount', 'balance_amount',
                           'paid_amount', 'sales_order_id', 'customer_id', 'crm_contact_id', 'crm_deal_id',
                           'due_date', 'due_at', 'order_id', 'contact_id', 'expected_end_date', 'planned_start_date', 'planned_end_date',
                           'expiry_date', 'next_follow_up_at', 'start_time', 'valid_until', 'expected_date', 'tracking_url'}:
            result[column.name] = value
    return result


@event.listens_for(Session, 'before_flush')
def capture(db, context, instances):
    pending = db.info.setdefault('customer_source_events', [])
    for obj in list(db.new) + list(db.dirty):
        spec = SOURCES.get(getattr(obj, '__tablename__', ''))
        if not spec or not getattr(obj, 'organization_id', None):
            continue
        state = inspect(obj)
        if obj not in db.new and not any(name in state.attrs and state.attrs[name].history.has_changes() for name in spec[1]):
            continue
        pending.append((obj, spec, uuid4().hex))


@event.listens_for(Session, 'after_flush_postexec')
def persist(db, context):
    from app.branches.models import BranchOwnership
    for obj, spec, key in db.info.pop('customer_source_events', []):
        branch = getattr(obj, 'branch_id', None)
        if not branch:
            branch = db.connection().execute(select(BranchOwnership.branch_id).where(
                BranchOwnership.resource_table == obj.__tablename__, BranchOwnership.resource_key == str(obj.id),
                BranchOwnership.company_id == obj.organization_id)).scalar()
        db.add(CustomerEvent(organization_id=obj.organization_id, branch_id=branch,
            event_key=key, trigger=spec[0]+'.changed', source_type=spec[0], source_id=obj.id,
            snapshot=values(obj)))


@event.listens_for(Session, 'after_soft_rollback')
def discard(db, transaction):
    db.info.pop('customer_source_events', None)
