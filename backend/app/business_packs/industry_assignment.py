"""Assignment-derived clinical scope; never a native SRM/HRMS permission grant.

Provider JSON account labels are not identity. A private appointment and its
private provider must both belong to the selected pack, and the canonical active
HRMS employee must directly link the actor. Only that bounded SQL proof extends
native own/assigned ownership. Normal native tenant/parent/branch guards remain.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import String, and_, bindparam, case, cast, exists, false, func, inspect, literal, or_, select

from .access import PackScope
from .boundary import _current


ASSIGNED_ROLES = frozenset({('hospital', 'doctor'), ('salon', 'stylist')})


def current_scope(db, actor, company, *, refresh=False):
    scope = db.info.get('business_pack_scope')
    if scope is None:
        return None
    if (not isinstance(scope, PackScope) or scope.user_id != actor.id or scope.company_id != company
            or getattr(actor, 'organization_id', company) not in (None, company)):
        raise HTTPException(403, 'Clinical assignment scope does not match the native actor')
    if refresh:
        _current(scope, db.connection())
    return scope


def clauses(db, actor, company, model):
    """Late-bound clauses also work when native scope installs before pack binding."""
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.apps.srm.industry_models import IndustryRecord
    from .models import PackRecordOwnership

    def selected():
        return current_scope(db, actor, company)

    context = bindparam('clinical_assignment_context', callable_=lambda: selected().context_id if selected() else -1, unique=True)
    branch = bindparam('clinical_assignment_branch', callable_=lambda: selected().branch_id if selected() else -1, unique=True)
    restricted = bindparam('clinical_assignment_required', callable_=lambda: bool(selected() and (selected().pack_key, selected().role) in ASSIGNED_ROLES), unique=True)
    if not inspect(db.connection()).has_table(PackRecordOwnership.__tablename__):
        # Uninstalled legacy schema stays native; a selected clinical role can
        # never fall back to creator ownership when assignment proof is absent.
        return false(), restricted.is_(False)
    appointment = model.__table__
    provider = IndustryRecord.__table__.alias('clinical_assignment_provider')
    employee, branches = Employee.__table__, Branch.__table__
    anchor = PackRecordOwnership.__table__

    def owned(table):
        return exists(select(literal(1)).where(anchor.c.resource_table == IndustryRecord.__tablename__,
            anchor.c.resource_key == cast(table.c.id, String), anchor.c.company_id == company,
            anchor.c.branch_id == branch, anchor.c.context_id == context)).correlate(table)

    if db.get_bind().dialect.name == 'postgresql':
        ids = case((func.json_typeof(appointment.c.data['resource_ids']) == 'array', appointment.c.data['resource_ids']), else_=literal('[]').cast(appointment.c.data.type))
        values = func.json_array_elements_text(ids).table_valued('value').alias('clinical_assignment_ids')
        integer_employee = func.json_typeof(provider.c.data['employee_id']) == 'number'
    else:
        ids = case((func.json_type(appointment.c.data, '$.resource_ids') == 'array', appointment.c.data['resource_ids']), else_='[]')
        values = func.json_each(ids).table_valued('value').alias('clinical_assignment_ids')
        integer_employee = func.json_type(provider.c.data, '$.employee_id') == 'integer'
    contains = exists(select(literal(1)).select_from(values).where(cast(values.c.value, String) == cast(provider.c.id, String))).correlate(appointment, provider)
    assigned = and_(appointment.c.kind == 'appointment', appointment.c.organization_id == company,
        appointment.c.branch_id == branch, owned(appointment), exists(select(literal(1)).select_from(
            provider.join(employee, cast(employee.c.id, String) == cast(provider.c.data['employee_id'].as_string(), String))
                    .join(branches, branches.c.id == employee.c.branch_id)
        ).where(provider.c.kind == 'resource', provider.c.organization_id == company, provider.c.branch_id == branch,
            provider.c.data['resource_type'].as_string().in_(('provider', 'doctor', 'stylist', 'consultant', 'technician', 'employee')),
            owned(provider), integer_employee, contains, branches.c.company_id == company,
            employee.c.branch_id == branch, employee.c.user_id == actor.id, employee.c.deleted_at.is_(None),
            employee.c.status.in_(('Active', 'Probation', 'On Leave')),
            or_(employee.c.date_of_exit.is_(None), employee.c.date_of_exit > datetime.now(timezone.utc).date()))).correlate(appointment))
    return assigned, or_(restricted.is_(False), assigned)


def clinical_payload(db, actor, row, payload):
    """Assigned clinical access does not expose appointment billing snapshots."""
    scope = current_scope(db, actor, row.organization_id, refresh=True)
    if scope is None or row.kind != 'appointment' or any(scope.pack_key + '.' + cap in scope.capabilities
            for cap in ('billing.view', 'billing.prepare', 'payments.record', 'checkout.create')):
        return payload
    allowed = {'customer_id', 'customer_name', 'service_id', 'service_name', 'resource_ids',
               'starts_at', 'duration_minutes', 'notes', 'walk_in', 'transition_reason'}
    return {**{key: value for key, value in payload.items() if key not in {'invoice_id', 'stock_movement_id'}},
            'data': {key: value for key, value in payload.get('data', {}).items() if key in allowed}}
