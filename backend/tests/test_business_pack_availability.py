from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from tests.test_business_pack_access import packs
from app.business_packs.access import resolve_context
from app.business_packs.boundary import PackBoundaryPolicy, install
from app.business_packs.availability import appointment_conflict, employee_leave_conflict
from app.apps.srm.industry_models import IndustryRecord
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.user import User
from app.access.models import AccessMembership


@pytest.fixture
def schedule(packs):
    p, db = packs, packs.db
    employee = Employee(employee_id='BLIND-1', first_name='Provider', last_name='Test', date_of_joining=date(2026, 1, 1), branch_id=p.branches['a'].id, status='Active')
    db.add(employee); db.flush()
    def row(kind, key, data, **extra):
        value = IndustryRecord(organization_id=1, branch_id=p.branches['a'].id, kind=kind,
            title='Never disclose', request_id=key, created_by=p.users['chef'].id, data=data, **extra)
        db.add(value); db.flush()
        return value
    first = row('resource', 'blind-resource1', {'employee_id': employee.id}, status='active')
    second = row('resource', 'blind-resource2', {'employee_id': employee.id}, status='active')
    starts = datetime(2026, 11, 14, 9, tzinfo=timezone.utc)
    booking = row('appointment', 'blind-booking', {'resource_ids': [first.id]}, status='booked',
        starts_at=starts, ends_at=starts + timedelta(hours=1))
    leave_type = LeaveType(name='Blind leave', code='BLIND', days_allowed=10)
    db.add(leave_type); db.flush()
    leave = LeaveRequest(company_id=1, employee_id=employee.id, leave_type_id=leave_type.id,
        from_date=date(2026, 11, 14), to_date=date(2026, 11, 15), days_count=2, status='Approved')
    db.add(leave); db.commit()
    return p, employee.id, first.id, second.id, booking.id, leave.id, starts


def test_blind_conflicts_work_under_guard_without_exposing_records(schedule):
    p, employee, first, second, booking, leave, starts = schedule
    scope = resolve_context(p.db, p.users['doctor'], p.ctx())
    cleanup = install(p.db, scope, policy=PackBoundaryPolicy(frozenset(), frozenset()))
    try:
        with pytest.raises(HTTPException) as denied:
            p.db.execute(select(IndustryRecord)).scalars().all()
        assert denied.value.status_code == 403
        assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second]) is True
        assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), employee_ids=[employee]) is True
        assert employee_leave_conflict(p.db, 1, employee, date(2026, 11, 15), date(2026, 11, 16)) is True
    finally:
        cleanup()


@pytest.mark.parametrize('status', ['cancelled', 'no_show', 'completed'])
def test_released_status_and_halfopen_ranges(schedule, status):
    p, employee, first, second, booking, leave, starts = schedule
    assert appointment_conflict(p.db, 1, starts + timedelta(hours=1), starts + timedelta(hours=2), resource_ids=[first]) is False
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[first], ignore_appointment_id=booking) is False
    p.db.connection().execute(IndustryRecord.__table__.update().where(IndustryRecord.id == booking).values(status=status))
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[first]) is False


@pytest.mark.parametrize('data', [None, {}, {'resource_ids': ['1']}, {'resource_ids': [999999]}, {'resource_ids': []}])
def test_invalid_reservation_metadata_fails_closed(schedule, data):
    p, employee, first, second, booking, leave, starts = schedule
    p.db.connection().execute(IndustryRecord.__table__.update().where(IndustryRecord.id == booking).values(data=data))
    with pytest.raises(HTTPException) as error:
        appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[first])
    assert error.value.status_code == 409
    assert error.value.detail == 'Scheduling availability cannot be verified'


def test_invalid_inputs_company_provider_and_null_range_fail_closed(schedule):
    p, employee, first, second, booking, leave, starts = schedule
    for args, kwargs in [((1, starts.replace(tzinfo=None), starts), {}), ((1, starts, starts), {}),
            ((2, starts, starts + timedelta(hours=1)), {'resource_ids': [first]}),
            ((1, starts, starts + timedelta(hours=1)), {'employee_ids': [True]})]:
        with pytest.raises(HTTPException):
            appointment_conflict(p.db, *args, **kwargs)
    p.db.connection().execute(IndustryRecord.__table__.update().where(IndustryRecord.id == booking).values(starts_at=None))
    with pytest.raises(HTTPException):
        appointment_conflict(p.db, 1, starts, starts + timedelta(hours=1), resource_ids=[first])


@pytest.mark.parametrize('values', [{'status': 'Pending'}, {'status': 'Cancelled'}, {'deleted_at': datetime(2026, 11, 1)}])
def test_only_approved_nondeleted_leave_blocks(schedule, values):
    p, employee, first, second, booking, leave, starts = schedule
    p.db.connection().execute(LeaveRequest.__table__.update().where(LeaveRequest.id == leave).values(**values))
    assert employee_leave_conflict(p.db, 1, employee, date(2026, 11, 14), date(2026, 11, 14)) is False


def test_other_branch_same_employee_and_user_alias_are_busy(schedule):
    p, employee, first, second, booking, leave, starts = schedule
    p.db.connection().execute(IndustryRecord.__table__.update().where(IndustryRecord.id == second).values(branch_id=p.branches['b'].id))
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second])
    for identity in (first, second):
        p.db.connection().execute(IndustryRecord.__table__.update().where(IndustryRecord.id == identity).values(data={'user_id': p.users['chef'].id}))
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second])
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), user_ids=[p.users['chef'].id])


@pytest.mark.parametrize('change', ['foreign_resource_company', 'resource_branch_mismatch', 'foreign_employee', 'foreign_user'])
def test_provider_source_company_and_branch_consistency(schedule, change):
    p, employee, first, second, booking, leave, starts = schedule
    connection = p.db.connection()
    if change == 'foreign_resource_company':
        connection.execute(IndustryRecord.__table__.update().where(IndustryRecord.id == first).values(organization_id=2))
    elif change == 'resource_branch_mismatch':
        connection.execute(IndustryRecord.__table__.update().where(IndustryRecord.id == first).values(branch_id=p.branches['b'].id))
    elif change == 'foreign_employee':
        connection.execute(Employee.__table__.update().where(Employee.id == employee).values(branch_id=p.branches['foreign'].id))
    else:
        connection.execute(IndustryRecord.__table__.update().where(IndustryRecord.id == first).values(data={'user_id': p.users['foreign'].id}))
    with pytest.raises(HTTPException) as error:
        appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second])
    assert error.value.status_code == 409


def test_historical_revoked_user_still_reserves_employee_without_blocking_unrelated_provider(schedule):
    p, employee, first, second, booking, leave, starts = schedule
    connection = p.db.connection()
    chef_id = p.users['chef'].id
    connection.execute(IndustryRecord.__table__.update().where(IndustryRecord.id == first).values(data={'employee_id': employee, 'user_id': chef_id}))
    connection.execute(User.__table__.update().where(User.id == chef_id).values(is_active=False))
    connection.execute(AccessMembership.__table__.update().where(AccessMembership.user_id == chef_id).values(active=False))
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second])
    other = Employee(employee_id='BLIND-OTHER', first_name='Other', last_name='Provider', date_of_joining=date(2026, 1, 1), branch_id=p.branches['a'].id)
    p.db.add(other); p.db.flush()
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), employee_ids=[other.id]) is False


def test_disabled_linked_login_does_not_block_employed_provider(schedule):
    p, employee, first, second, booking, leave, starts = schedule
    chef_id = p.users['chef'].id
    connection = p.db.connection()
    connection.execute(Employee.__table__.update().where(Employee.id == employee).values(user_id=chef_id))
    connection.execute(User.__table__.update().where(User.id == chef_id).values(is_active=False))
    connection.execute(AccessMembership.__table__.update().where(AccessMembership.user_id == chef_id).values(active=False))
    connection.execute(IndustryRecord.__table__.update().where(IndustryRecord.id == second).values(data={'employee_id': employee, 'user_id': chef_id}))
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second])


def test_out_of_range_valid_history_is_not_loaded_or_validated(schedule):
    p, employee, first, second, booking, leave, starts = schedule
    p.db.connection().execute(IndustryRecord.__table__.update().where(IndustryRecord.id == booking).values(
        starts_at=starts - timedelta(days=90), ends_at=starts - timedelta(days=89), data={'resource_ids': [999999], 'secret_notes': 'never fetched'}))
    assert appointment_conflict(p.db, 1, starts, starts + timedelta(minutes=30), resource_ids=[second]) is False
