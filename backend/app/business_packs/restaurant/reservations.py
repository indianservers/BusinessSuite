"""Unpriced table reservations on canonical IndustryRecord, never appointments.

The explicit kind excludes service/provider billing, checkout and worked-time
adapters. Tables and customers remain canonical; commands retain exact retries.
"""
from datetime import datetime, timedelta, timezone
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.services.commercial import customer, lock_tenant
from . import service, tabs
from .models import RestaurantTable as Table, RestaurantServiceOrder as Order

KIND = 'restaurant_reservation'


def query(db, scope):
    return db.query(IndustryRecord).filter_by(organization_id=scope.company_id, branch_id=scope.branch_id, kind=KIND)


def record(ident, db, scope):
    row = query(db, scope).filter_by(id=ident).populate_existing().with_for_update().first()
    if row is None:
        service.fail('Restaurant reservation is unavailable', 404)
    service.private(db, scope, IndustryRecord, row.id)
    if row.data.get('source') != KIND or row.project_id is not None or row.invoice_id is not None or row.stock_movement_id is not None:
        service.fail('Reservation source changed', 409)
    return row


def result(row):
    return {'id': row.id, 'revision': row.revision, 'state': row.status, 'table_id': row.data['table_id'],
        'party_size': row.data['party_size'], 'starts_at': row.starts_at.replace(tzinfo=timezone.utc).isoformat() if row.starts_at.tzinfo is None else row.starts_at.isoformat(),
        'ends_at': row.ends_at.replace(tzinfo=timezone.utc).isoformat() if row.ends_at.tzinfo is None else row.ends_at.isoformat(),
        'customer_id': row.customer_id, 'notes': row.data.get('notes', ''), 'order_id': row.data.get('order_id')}


def writer(db, actor):
    installed = service.authority(db, actor, 'reservations.schedule', write=True)
    scope, epoch = tabs.writer(db, actor)
    if installed is not scope or service.authority(db, actor, 'reservations.schedule', write=True) is not scope:
        service.fail('Reservation authority changed')
    return scope, epoch


def available(data, db, actor, scope, *, ignore=None):
    table = service.record(db, Table, scope, data.table_id)
    if not table.active or table.revision != data.expected_table_revision or table.capacity < data.party_size:
        service.fail('Table revision, capacity or availability changed', 409)
    if data.starts_at <= datetime.now(timezone.utc):
        service.fail('Choose a future reservation time', 409)
    end = data.starts_at + timedelta(minutes=data.duration_minutes)
    # Physical availability includes bookings hidden by native Own visibility.
    # Fixed conflict bits only; no foreign customer/notes bodies are projected.
    from app.business_packs.models import PackRecordOwnership
    from sqlalchemy import select
    native, ownership = IndustryRecord.__table__, PackRecordOwnership.__table__
    conflict = db.connection().scalar(select(native.c.id).select_from(native.join(ownership,
        (ownership.c.resource_table == IndustryRecord.__tablename__) & (ownership.c.resource_key == native.c.id.cast(ownership.c.resource_key.type)))).where(
        native.c.organization_id == scope.company_id, native.c.branch_id == scope.branch_id, native.c.kind == KIND,
        ownership.c.context_id == scope.context_id, ownership.c.company_id == scope.company_id, ownership.c.branch_id == scope.branch_id,
        native.c.status.in_(('booked', 'seated')), native.c.data['table_id'].as_integer() == table.id,
        native.c.starts_at < end, native.c.ends_at > data.starts_at, native.c.id != ignore if ignore is not None else True).limit(1))
    if conflict is not None:
        service.fail('Table is already reserved at that time', 409)
    return table, end


def save(data, db, actor, *, ident=None, commit=True):
    scope, epoch = writer(db, actor)
    action = 'reservation.create' if ident is None else 'reservation.schedule'
    replay = service.prior(db, actor, scope, action, ident, data)
    if replay is not None:
        return replay
    row = None if ident is None else record(ident, db, scope)
    if row is not None and (row.status != 'booked' or row.revision != data.expected_revision):
        service.fail('Only the current booked reservation can be rescheduled', 409)
    with db.begin_nested():
        table, end = available(data, db, actor, scope, ignore=ident)
        if data.customer_id is not None:
            customer(db, data.customer_id, actor)
        if row is None:
            row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, kind=KIND,
                request_id=str(data.request_key), created_by=actor.id, revision=1, status='booked')
            db.add(row)
        else:
            row.revision += 1
        row.title = 'Table reservation'
        row.customer_id, row.starts_at, row.ends_at = data.customer_id, data.starts_at, end
        row.data = {'source': KIND, 'table_id': table.id, 'party_size': data.party_size, 'notes': data.notes}
        db.flush()
        service.private(db, scope, IndustryRecord, row.id)
        if service.authority(db, actor, 'reservations.schedule', write=True) is not scope or tabs._native_epoch(db, actor, scope) != epoch:
            service.fail('Reservation authority changed')
        answer = service.save_command(db, actor, scope, action, ident, data, result(row), table=table)
    if commit:
        db.commit()
    return answer


def listing(db, actor, *, after=0, limit=50):
    scope = service.authority(db, actor, 'reservations.schedule')
    rows = query(db, scope).filter(IndustryRecord.id > after).order_by(IndustryRecord.id).limit(limit+1).all()
    values = [result(record(row.id, db, scope)) for row in rows[:limit]]
    return {'items': values, 'next': rows[limit-1].id if len(rows) > limit else None}


def transition(ident, data, db, actor, *, commit=True):
    scope, _ = writer(db, actor)
    replay = service.prior(db, actor, scope, 'reservation.transition', ident, data)
    if replay is not None:
        return replay
    row = record(ident, db, scope)
    if row.status != 'booked' or row.revision != data.expected_revision:
        service.fail('Only the current booked reservation can change state', 409)
    starts = row.starts_at.replace(tzinfo=timezone.utc) if row.starts_at.tzinfo is None else row.starts_at
    if data.status == 'no_show' and starts > datetime.now(timezone.utc):
        service.fail('A no-show can only be recorded after the reservation starts', 409)
    with db.begin_nested():
        table = service.record(db, Table, scope, row.data['table_id'])
        if data.status == 'seated':
            order = service.record(db, Order, scope, data.order_id)
            service.order_source(db, actor, scope, order)
            if not table.active or table.capacity < row.data['party_size'] or order.state != 'open' or order.table_id != table.id:
                service.fail('Seat this reservation at its active table using the current open tab', 409)
            row.data = {**row.data, 'order_id': order.id}
        row.status, row.revision = data.status, row.revision+1
        db.flush()
        answer = service.save_command(db, actor, scope, 'reservation.transition', ident, data, result(row), table=table)
    if commit:
        db.commit()
    return answer
