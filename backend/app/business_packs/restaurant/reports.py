"""Daily operational counts from authorized canonical sources, without a ledger."""
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.apps.srm.models import SRMSalesOrder
from app.apps.srm.access import sales_order_query
from app.apps.srm.industry_models import IndustryRecord
from . import service
from .models import RestaurantServiceOrder as Order, RestaurantKitchenTicket as Ticket


def daily(day, timezone_name, db, actor):
    scope = service.authority(db, actor, 'reports.view')
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        service.fail('Choose a valid reporting timezone', 422)
    try:
        start = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    except (OverflowError, ValueError):
        service.fail('Reporting day is outside the supported range', 422)
    native_ids = sales_order_query(db, actor).with_entities(SRMSalesOrder.id)
    orders = service.scoped(db, Order, scope).filter(Order.sales_order_id.in_(native_ids), Order.created_at >= start, Order.created_at < end).all()
    for order in orders:
        service.private(db, scope, Order, order.id)
        service.order_source(db, actor, scope, order)
    tickets = service.scoped(db, Ticket, scope).filter(Ticket.created_at >= start, Ticket.created_at < end,
        Ticket.service_order_id.in_(service.scoped(db, Order, scope).filter(Order.sales_order_id.in_(native_ids)).with_entities(Order.id))).all()
    for ticket in tickets:
        service.private(db, scope, Ticket, ticket.id)
        parent = service.record(db, Order, scope, ticket.service_order_id)
        service.order_source(db, actor, scope, parent)
    # Industry ORM scope retains its native owner visibility and exact selected
    # pack ownership; no direct connection projection of foreign appointments.
    reservations = db.query(IndustryRecord).filter_by(organization_id=scope.company_id,
        branch_id=scope.branch_id, kind='restaurant_reservation').filter(IndustryRecord.starts_at >= start, IndustryRecord.starts_at < end).all()
    for reservation in reservations:
        service.private(db, scope, IndustryRecord, reservation.id)
    return {'day': day.isoformat(), 'timezone': timezone_name,
        'orders_opened': len(orders), 'orders': dict(Counter(row.state for row in orders)),
        'tickets_created': len(tickets), 'tickets': dict(Counter(row.state for row in tickets)),
        'reservations_starting': len(reservations), 'reservations': dict(Counter(row.status for row in reservations))}
