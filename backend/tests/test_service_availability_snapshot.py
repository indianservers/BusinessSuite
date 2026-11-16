"""Prepared advisory reads retain native conflict semantics without slot-query N+1."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.service_checkout_options import _AvailabilityRead, scheduling_availability
from app.business_packs.availability import appointment_conflict
from tests.test_business_pack_availability import schedule
from tests.test_business_pack_access import packs
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def prepared(p, employee, first, start):
    return _AvailabilityRead(p.db, p.users['doctor'], 1, p.branches['a'].id,
        start - timedelta(days=1), start + timedelta(days=2),
        SimpleNamespace(id=first), SimpleNamespace(id=employee))


def outcome(call):
    try:
        return call()
    except HTTPException as error:
        return error.status_code, error.detail


def assert_conflict_parity(p, snapshot, first, second, starts):
    for offset, minutes in [(-60, 30), (-30, 30), (-15, 30), (0, 30), (30, 30), (60, 30), (90, 30)]:
        begin = starts + timedelta(minutes=offset)
        end = begin + timedelta(minutes=minutes)
        for ids in ([first], [second], [first, second]):
            expected = outcome(lambda: appointment_conflict(p.db, 1, begin, end, resource_ids=ids))
            actual = outcome(lambda: snapshot.conflict(begin, end, ids))
            assert actual == expected


def test_prepared_conflict_matches_native_reader_under_private_pack_guard(schedule):
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import PackBoundaryPolicy, install
    p, employee, first, second, _, _, starts = schedule
    scope = resolve_context(p.db, p.users['doctor'], p.ctx())
    cleanup = install(p.db, scope, policy=PackBoundaryPolicy(frozenset(), frozenset()))
    try:
        snapshot = prepared(p, employee, first, starts)
        assert_conflict_parity(p, snapshot, first, second, starts)
        assert not p.db.new and not p.db.dirty and not p.db.deleted
    finally:
        cleanup()


def test_prepared_conflict_retains_cross_branch_employee_and_user_aliases(schedule):
    p, employee, first, second, _, _, starts = schedule
    table = IndustryRecord.__table__
    p.db.connection().execute(table.update().where(table.c.id == second).values(branch_id=p.branches['b'].id))
    assert_conflict_parity(p, prepared(p, employee, first, starts), first, second, starts)
    for identity in (first, second):
        p.db.connection().execute(table.update().where(table.c.id == identity).values(data={'user_id': p.users['chef'].id}))
    assert_conflict_parity(p, prepared(p, employee, first, starts), first, second, starts)


@pytest.mark.parametrize('case', ['duplicate_ids', 'missing_resource', 'invalid_employee', 'invalid_range'])
def test_prepared_conflict_preserves_malformed_busy_data_fail_closed(schedule, case):
    p, employee, first, second, booking, _, starts = schedule
    table = IndustryRecord.__table__
    if case == 'duplicate_ids':
        p.db.connection().execute(table.update().where(table.c.id == booking).values(data={'resource_ids': [first, first]}))
    elif case == 'missing_resource':
        p.db.connection().execute(table.update().where(table.c.id == booking).values(data={'resource_ids': [99999999]}))
    elif case == 'invalid_employee':
        p.db.connection().execute(table.update().where(table.c.id == first).values(data={'employee_id': str(employee)}))
    else:
        p.db.connection().execute(table.update().where(table.c.id == booking).values(starts_at=None))
    assert_conflict_parity(p, prepared(p, employee, first, starts), first, second, starts)


@pytest.mark.parametrize('status', ['completed', 'cancelled', 'no_show'])
def test_prepared_conflict_releases_nonblocking_statuses(schedule, status):
    p, employee, first, second, booking, _, starts = schedule
    table = IndustryRecord.__table__
    p.db.connection().execute(table.update().where(table.c.id == booking).values(status=status))
    assert_conflict_parity(p, prepared(p, employee, first, starts), first, second, starts)


def test_endpoint_slots_match_native_hours_room_and_conflict_checks(db, scenario):
    from app.apps.srm.industry_api import available
    from app.apps.srm.service_checkout import _cross_pack_busy
    user, branch, catalog, basket = scenario
    booking = basket(False).lines[1].booking
    with native_writer(db, user, branch):
        provider = db.query(IndustryRecord).filter_by(id=booking.provider_resource_id).one()
        provider.data = {**provider.data, 'opens': '09:00', 'closes': '12:00'}
        room = IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title='Snapshot room',
            status='active', request_id=str(uuid4()), created_by=user.id,
            data={'resource_type': 'room', 'timezone': 'UTC', 'weekdays': list(range(7)), 'opens': '09:30', 'closes': '11:30'})
        db.add(room); db.flush()
        prior = IndustryRecord(organization_id=1, branch_id=branch, kind='appointment', title='Do not disclose',
            status='booked', request_id=str(uuid4()), created_by=user.id, starts_at=booking.starts_at,
            ends_at=booking.starts_at + timedelta(minutes=45), data={'resource_ids': [provider.id, room.id]})
        db.add(prior); db.commit()
        result = scheduling_availability(db, user, catalog[2][1], booking.eligibility_id,
            booking.starts_at.date(), 30, starts_at=booking.starts_at, resource_ids=[room.id])
        expected = []
        candidate = booking.starts_at.replace(hour=9, minute=0)
        for _ in range(11):
            try:
                available(db, user, branch, candidate, 30, [provider.id, room.id], lock=False)
                _cross_pack_busy(db, 1, branch, SimpleNamespace(provider_resource_id=provider.id,
                    employee_id=booking.employee_id, additional_resource_ids=[room.id],
                    starts_at=candidate, duration_minutes=30))
                expected.append(candidate.strftime('%H:%M'))
            except HTTPException as error:
                assert error.status_code in (409, 422)
            candidate += timedelta(minutes=15)
        assert [slot['label'] for slot in result['slots']] == expected
        assert result['selection_available'] is False
        assert result['resources'] == [{'id': room.id, 'available': False}]


def test_endpoint_sql_count_does_not_grow_with_quarter_hour_slot_count(db, scenario, record_property):
    user, branch, catalog, basket = scenario
    booking = basket(False).lines[1].booking
    engine = db.get_bind()
    with native_writer(db, user, branch):
        provider = db.query(IndustryRecord).filter_by(id=booking.provider_resource_id).one()
        def measure(opens, closes):
            provider.data = {**provider.data, 'opens': opens, 'closes': closes}
            db.commit()
            statements = []
            def record(*args):
                statements.append(args[2])
            event.listen(engine, 'before_cursor_execute', record)
            try:
                result = scheduling_availability(db, user, catalog[2][1], booking.eligibility_id,
                    booking.starts_at.date(), 30, starts_at=booking.starts_at)
            finally:
                event.remove(engine, 'before_cursor_execute', record)
            return result, len(statements)
        short, short_count = measure('09:00', '10:00')
        long, long_count = measure('00:00', '23:59')
        assert len(short['slots']) == 3
        assert len(long['slots']) >= 80
        record_property('short_day_queries', short_count)
        record_property('whole_day_queries', long_count)
        record_property('short_day_slots', len(short['slots']))
        record_property('whole_day_slots', len(long['slots']))
        assert long_count <= short_count + 8, (short_count, long_count)


@pytest.mark.parametrize('release', ['cancelled', 'deleted'])
def test_endpoint_reloads_employee_leave_between_requests(db, scenario, release):
    from app.models.leave import LeaveRequest, LeaveType
    user, branch, catalog, basket = scenario
    booking = basket(False).lines[1].booking
    with native_writer(db, user, branch):
        leave_type = LeaveType(name='Snapshot leave', code='SNAP-' + uuid4().hex[:8], days_allowed=10)
        db.add(leave_type); db.flush()
        leave = LeaveRequest(company_id=1, employee_id=booking.employee_id, leave_type_id=leave_type.id,
            from_date=booking.starts_at.date(), to_date=booking.starts_at.date(), days_count=1, status='Approved')
        db.add(leave); db.commit()
        before = scheduling_availability(db, user, catalog[2][1], booking.eligibility_id,
            booking.starts_at.date(), 30, starts_at=booking.starts_at)
        assert before['selection_available'] is False and before['slots'] == []
        if release == 'cancelled':
            leave.status = 'Cancelled'
        else:
            leave.deleted_at = datetime.now(timezone.utc)
        db.commit()
        after = scheduling_availability(db, user, catalog[2][1], booking.eligibility_id,
            booking.starts_at.date(), 30, starts_at=booking.starts_at)
        assert after['selection_available'] is True
        assert any(slot['label'] == '10:00' for slot in after['slots'])


def test_prepared_hours_match_native_across_dst_and_different_resource_timezones(db, scenario):
    from app.apps.srm.industry_api import available
    from app.models.employee import Employee
    user, branch, _, basket = scenario
    booking = basket(False).lines[1].booking
    with native_writer(db, user, branch):
        provider = db.query(IndustryRecord).filter_by(id=booking.provider_resource_id).one()
        provider.data = {**provider.data, 'timezone': 'America/New_York', 'opens': '00:00', 'closes': '23:59'}
        employee = db.get(Employee, booking.employee_id)
        room = IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title='Cross-zone room',
            status='active', request_id=str(uuid4()), created_by=user.id,
            data={'resource_type': 'room', 'timezone': 'Asia/Kolkata', 'weekdays': list(range(7)), 'opens': '00:00', 'closes': '23:59'})
        db.add(room); db.commit()
        for day, hours in [('2026-03-08', [6, 7, 17, 18]), ('2026-11-01', [5, 6, 17, 18])]:
            lower = datetime.fromisoformat(day + 'T00:00:00+00:00')
            snapshot = _AvailabilityRead(db, user, 1, branch, lower, lower + timedelta(days=2), provider, employee)
            for hour in hours:
                begin = lower.replace(hour=hour, minute=15 if hour == 18 else 45 if hour == 17 else 30)
                def reference():
                    try:
                        available(db, user, branch, begin, 30, [provider.id, room.id], lock=False)
                        return True
                    except HTTPException as error:
                        if error.status_code in (409, 422):
                            return False
                        raise
                expected = reference()
                assert expected is (hour != 18)
                assert snapshot.available(begin, 30, [provider.id, room.id]) == expected
