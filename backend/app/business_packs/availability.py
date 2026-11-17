"""Blind cross-context scheduling checks, never an authorization API.

Callers must validate exact selected resources/providers, branch and native
permissions and hold the company writer lock through checking and reservation.
Only boolean occupancy escapes this trusted Core reader. No source is returned.
"""
from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from app.apps.srm.industry_models import IndustryRecord
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.models.leave import LeaveRequest
from app.models.user import User
from app.access.models import AccessMembership
from app.common.models import CommonPerson
from app.core.tenant_boundary import company_ids


def _unavailable():
    raise HTTPException(409, 'Scheduling availability cannot be verified')


def _id(value):
    if type(value) is not int or value <= 0:
        _unavailable()
    return value


def _ids(values):
    try:
        result = {_id(value) for value in values}
    except TypeError:
        _unavailable()
    return result


def _company(connection, company_id):
    _id(company_id)
    if not connection.execute(select(Company.id).where(Company.id == company_id, Company.is_active.is_(True))).first():
        _unavailable()


def _employee(connection, company_id, employee_id):
    _id(employee_id)
    if not connection.execute(select(Employee.id).join(Branch, Employee.branch_id == Branch.id).where(
            Employee.id == employee_id, Branch.company_id == company_id)).first():
        _unavailable()


def _user(db, company_id, user_id, *, historical=False, employee_id=None):
    _id(user_id)
    connection = db.connection()
    row = connection.execute(select(User.id, User.is_active).where(User.id == user_id)).first()
    if row is None:
        _unavailable()
    if not historical:
        if employee_id is not None and connection.execute(select(Employee.id).join(Branch, Employee.branch_id == Branch.id).where(
                Employee.id == employee_id, Employee.user_id == user_id, Branch.company_id == company_id,
                Employee.deleted_at.is_(None), Employee.status.in_(('Active', 'Probation', 'On Leave')))).first():
            return  # Employment, rather than login/account status, schedules staff.
        if company_id not in company_ids(db, SimpleNamespace(id=user_id)):
            _unavailable()
        return
    # Revocation does not erase an existing reservation. Historical company
    # evidence includes revoked memberships; resource provenance supplies the
    # source company when a legacy user has no remaining membership evidence.
    evidence = set(connection.execute(select(AccessMembership.company_id).where(AccessMembership.user_id == user_id)).scalars())
    evidence.update(connection.execute(select(CommonPerson.organization_id).where(CommonPerson.user_id == user_id)).scalars())
    evidence.update(connection.execute(select(Branch.company_id).join(Employee, Employee.branch_id == Branch.id).where(Employee.user_id == user_id)).scalars())
    evidence.discard(None)
    if evidence and company_id not in evidence:
        _unavailable()


def _instant(value, *, stored=False):
    if not isinstance(value, datetime):
        _unavailable()
    if value.tzinfo is None or value.utcoffset() is None:
        if not stored:
            _unavailable()
        # SQLite strips tzinfo from timezone=True columns. Native writes store UTC.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resource_capacity(value):
    if value is None:
        return 1
    if type(value) is not int or not 1 <= value <= 1000:
        _unavailable()
    return value


def capacity_conflict(intervals, capacity):
    """The proposed reservation consumes one unit; endpoints are half-open."""
    events = sorted((point, delta) for start, end in intervals for point, delta in ((start, 1), (end, -1)))
    occupied = 0
    for _, delta in events:
        occupied += delta
        if occupied >= capacity:
            return True
    return False


def appointment_conflict(db, company_id, starts_at, ends_at, *, resource_ids=(), employee_ids=(), user_ids=(), ignore_appointment_id=None, draft_bookings=()):
    """Return occupancy across all company contexts; ignore requires prior authorization."""
    starts_at, ends_at = _instant(starts_at), _instant(ends_at)
    if starts_at >= ends_at:
        _unavailable()
    selected, employees, users = _ids(resource_ids), _ids(employee_ids), _ids(user_ids)
    if ignore_appointment_id is not None:
        _id(ignore_appointment_id)
    connection = db.connection()
    _company(connection, company_id)
    for value in employees:
        _employee(connection, company_id, value)
    for value in users:
        _user(db, company_id, value)
    record = IndustryRecord.__table__
    validated_employees, validated_users, validated_branches, resources = set(employees), set(), set(), {}
    # JSON projections keep customer/payment/notes payloads outside this reader.
    json_type = func.json_type if connection.dialect.name == 'sqlite' else func.json_typeof

    def branch(identity):
        if identity not in validated_branches:
            if not connection.execute(select(Branch.id).where(Branch.id == identity, Branch.company_id == company_id)).first():
                _unavailable()
            validated_branches.add(identity)

    def resource(identity, branch_id=None):
        if identity not in resources:
            resources[identity] = connection.execute(select(record.c.branch_id,
                record.c.data['employee_id'].label('employee_id'), record.c.data['user_id'].label('user_id'), record.c.data['capacity'].label('capacity'),
                json_type(record.c.data).label('shape')).where(record.c.id == identity, record.c.kind == 'resource',
                record.c.organization_id == company_id)).mappings().first()
        row = resources[identity]
        if not row or row['shape'] != 'object':
            _unavailable()
        branch(row['branch_id'])
        if branch_id is not None and row['branch_id'] != branch_id:
            _unavailable()
        employee, user = row['employee_id'], row['user_id']
        if employee is not None:
            _id(employee)
        if user is not None:
            _id(user)
        if employee is not None and employee not in validated_employees:
            _employee(connection, company_id, employee)
            validated_employees.add(employee)
        if user is not None and (user, branch_id is not None) not in validated_users:
            _user(db, company_id, user, historical=branch_id is not None, employee_id=employee)
            validated_users.add((user, branch_id is not None))
        return employee, user

    for identity in selected:
        employee, user = resource(identity)
        employees.update(() if employee is None else (employee,))
        users.update(() if user is None else (user,))
    # Include malformed null ranges rather than silently dropping uncertain bookings.
    rows = connection.execute(select(record.c.id, record.c.branch_id, record.c.starts_at, record.c.ends_at,
        record.c.data['resource_ids'].label('resource_ids')).where(record.c.organization_id == company_id,
        record.c.kind == 'appointment', record.c.status.in_(('booked', 'checked_in', 'in_service')),
        or_(record.c.starts_at.is_(None), record.c.ends_at.is_(None), record.c.starts_at >= record.c.ends_at,
            and_(record.c.starts_at < ends_at, record.c.ends_at > starts_at)))).mappings()
    rows = list(rows) + list(draft_bookings)
    occupancy = {identity: [] for identity in selected}
    busy = False
    for row in rows:
        if ignore_appointment_id is not None and row['id'] == ignore_appointment_id:
            continue
        old_start = _instant(row['starts_at'], stored=connection.dialect.name == 'sqlite')
        old_end = _instant(row['ends_at'], stored=connection.dialect.name == 'sqlite')
        if old_start >= old_end:
            _unavailable()
        if old_start >= ends_at or old_end <= starts_at:
            continue
        branch(row['branch_id'])
        source_ids = row['resource_ids']
        if not isinstance(source_ids, list) or not source_ids:
            _unavailable()
        prior = _ids(source_ids)
        if len(prior) != len(source_ids):
            _unavailable()
        for identity in prior & selected:
            occupancy[identity].append((max(starts_at, old_start), min(ends_at, old_end)))
        for identity in prior:
            employee, user = resource(identity, row['branch_id'])
            busy |= employee in employees or user in users
    return bool(busy or any(capacity_conflict(intervals, resource_capacity(resources[identity]['capacity'])) for identity, intervals in occupancy.items()))


def employee_leave_conflict(db, company_id, employee_id, from_date, until_date):
    if type(from_date) is not date or type(until_date) is not date or from_date > until_date:
        _unavailable()
    connection = db.connection()
    _company(connection, company_id)
    _employee(connection, company_id, employee_id)
    leave = LeaveRequest.__table__
    rows = connection.execute(select(leave.c.from_date, leave.c.to_date).where(
        leave.c.company_id == company_id, leave.c.employee_id == employee_id,
        leave.c.status == 'Approved', leave.c.deleted_at.is_(None),
        or_(leave.c.from_date.is_(None), leave.c.to_date.is_(None), leave.c.from_date > leave.c.to_date,
            and_(leave.c.from_date <= until_date, leave.c.to_date >= from_date))))
    busy = False
    for start, end in rows:
        if start is None or end is None or start > end:
            _unavailable()
        busy |= start <= until_date and end >= from_date
    return bool(busy)
