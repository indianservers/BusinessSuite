"""Closed native leave purpose; pack selection never grants employment rights.

Canonical leave rows and ledgers remain common. Native tenant, branch, record
scope and action guards remain active; this module only closes the ORM graph.
"""
from types import MappingProxyType
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import and_, event, exists, false, inspect, or_, select, true
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause, TextClause

PURPOSE = 'hrms.leave'
_NOTIFICATIONS = WeakKeyDictionary()
_SELF_ROUTES = frozenset({('GET', '/api/v1/leave/' + path) for path in
    ('types', 'balance', 'ledger', 'my-requests', 'requests/{request_id}', 'calendar')} | {
    ('POST', '/api/v1/leave/apply'), ('PUT', '/api/v1/leave/requests/{request_id}/cancel')})


def native_self_request(db, actor, company, operation):
    """Only exact existing authenticated self-service contracts use legacy rules."""
    from .common_binding import CoreRequestBinding, MARKER
    from .common_core import OPERATIONS
    binding = db.info.get(MARKER)
    return (isinstance(binding, CoreRequestBinding) and binding.purpose == PURPOSE
        and binding.user_id == actor.id and binding.company_id == company
        and (binding.method, binding.route) in _SELF_ROUTES
        and OPERATIONS.get((binding.method, binding.route)) is operation)


def native_predicate(db, actor, company, model):
    """Company leave definitions are not employee-private operational records."""
    from .common_binding import CoreRequestBinding, MARKER
    from .common_core import OPERATIONS
    from app.models.leave import LeaveType
    from app.models.attendance import Holiday
    from app.models.security_boundary import SecurityResourceOwnership
    from app.shared.models import ServicePolicy
    binding = db.info.get(MARKER)
    if (model not in {LeaveType, Holiday, ServicePolicy} or not isinstance(binding, CoreRequestBinding)
            or binding.purpose != PURPOSE or binding.user_id != actor.id or binding.company_id != company
            or db.info.get('business_pack_scope') is not None):
        return None
    operation = OPERATIONS.get((binding.method, binding.route))
    if operation is None or operation.purpose != PURPOSE: return None
    if model is ServicePolicy:
        if (binding.method, binding.route) != ('GET', '/api/v1/leave/calendar'): return None
        from app.shared.form_defaults import scope_key
        branch = db.info.get('branch_context')
        keys = [scope_key(company), scope_key(company, 'hrms')]
        if branch is not None and branch.branch_id:
            keys += [scope_key(company, branch_id=branch.branch_id), scope_key(company, 'hrms', branch.branch_id)]
        return and_(model.organization_id == company, model.kind == 'form_defaults', model.scope_key.in_(keys))
    owner = SecurityResourceOwnership.__table__
    return model.id.in_(select(owner.c.resource_id).where(owner.c.resource_table == model.__tablename__, owner.c.company_id == company))


def operations(operation):
    read = operation('view', None, purpose=PURPOSE)
    result = {('GET', '/api/v1/leave/' + path): read for path in (
        'types', 'balance', 'ledger', 'my-requests', 'requests/{request_id}',
        'calendar')}
    for path, permission in (('requests', 'leave_approve'), ('pending-count', 'leave_manage'),
            ('balance/{employee_id}', 'leave_manage'), ('ledger/{employee_id}', 'leave_manage')):
        result[('GET', '/api/v1/leave/' + path)] = operation('view', permission, purpose=PURPOSE)
    records = frozenset({'leave_requests', 'leave_balances', 'leave_balance_ledger',
        'notifications', 'notification_delivery_logs', 'suite_service_events'})
    creates = frozenset({'leave_requests', 'leave_balance_ledger', 'notifications', 'notification_delivery_logs', 'suite_service_events'})
    result[('POST', '/api/v1/leave/apply')] = operation('create', None, records, creates, purpose=PURPOSE)
    result[('PUT', '/api/v1/leave/requests/{request_id}/cancel')] = operation('edit', None,
        records, creates - {'leave_requests'}, purpose=PURPOSE)
    result[('PUT', '/api/v1/leave/requests/{request_id}/approve')] = operation('approve', 'leave_approve',
        records, creates - {'leave_requests'}, purpose=PURPOSE)
    return MappingProxyType(result)



def _event_payload(db, actor, scope, payload):
    """Only native empty event data, with current cryptographically sealed AI origin."""
    from app.shared.runtime import DEPTH
    base={'depth':DEPTH.get(),'data':{}}
    request=db.info.get('ai_request_context')
    if not isinstance(request,dict) or request.get('is_ai') is not True:
        return payload==base
    if not isinstance(payload,dict) or set(payload)!={'depth','data','ai_origin'}:
        return False
    if {key:payload[key] for key in ('depth','data')}!=base:
        return False
    origin=payload['ai_origin']
    fields={'user_id','company_id','session_id','fingerprint','control_fingerprint',
        'policy','nonce','issued_at','operation','signature'}
    if not isinstance(origin,dict) or set(origin)!=fields:
        return False
    if (type(request.get('user_id')) is not int or request['user_id']!=actor.id
            or type(request.get('company_id')) is not int or request['company_id']!=scope.company_id
            or type(request.get('session_id')) is not int or request['session_id']<=0
            or type(origin.get('user_id')) is not int or origin['user_id']!=actor.id
            or type(origin.get('company_id')) is not int or origin['company_id']!=scope.company_id
            or type(origin.get('session_id')) is not int or origin['session_id']!=request['session_id']
            or origin.get('operation') is not None):
        return False
    from app.ai_agents.security import verify
    verify(db,actor,origin,history=False)
    return True

def install(db, actor, scope):
    from .common_core import deny, _native_authority, _native_operation_access
    from .common_binding import MARKER
    from .models import PackRecordOwnership
    from app.db.base_class import Base
    from app.models.leave import LeaveRequest, LeaveBalance, LeaveBalanceLedger, LeaveType
    from app.models.employee import Employee
    from app.models.company import Company, Branch, Department, Designation
    from app.models.attendance import Holiday
    from app.models.user import User, Role, Permission, role_permissions
    from app.models.notification import Notification, NotificationDeliveryLog
    from app.models.security_boundary import SecurityResourceOwnership
    from app.shared.models import ServicePolicy, ServiceEvent
    from app.shared.form_defaults import scope_key
    from app.branches.catalog import key_expression, resource_key
    from app.branches.service import context as branch_context
    if scope.operation.purpose != PURPOSE or scope.binding.purpose != PURPOSE:
        deny('A registered native leave request is required')
    if db.info.get('business_pack_policy') is not None:
        deny('Native leave and private operational authority cannot be mixed')
    previous = db.info.get('business_common_core_scope')
    if previous is not None:
        if previous != scope: deny('Native leave purpose cannot change within a request')
        return lambda: None
    if db.new or db.deleted or any(db.is_modified(row, include_collections=True) for row in db.dirty):
        deny('Finish pending changes before binding native leave')
    owner = PackRecordOwnership.__table__
    inspector = inspect(db.connection())
    present = inspector.has_table(owner.name)
    if present and not {'resource_table', 'resource_key', 'company_id', 'branch_id', 'context_id'} <= {
            column['name'] for column in inspector.get_columns(owner.name)}:
        raise HTTPException(503, 'Native leave ownership exclusion installation is incomplete')
    def unowned(table):
        return ~exists(select(1).where(owner.c.resource_table == table.name,
            owner.c.resource_key == key_expression(table))).correlate(table) if present else true()
    employee_company = or_(Employee.branch_id.in_(select(Branch.id).where(Branch.company_id == scope.company_id)),
        Employee.branch_id.is_(None) & (scope.company_id == 1))
    employees = select(Employee.id).where(employee_company, unowned(Employee.__table__))
    native = SecurityResourceOwnership.__table__
    def company_definition(model):
        return model.id.in_(select(native.c.resource_id).where(native.c.resource_table == model.__tablename__,
            native.c.company_id == scope.company_id))
    requests = select(LeaveRequest.id).where(LeaveRequest.employee_id.in_(employees),
        or_(LeaveRequest.company_id == scope.company_id, LeaveRequest.company_id.is_(None) & (scope.company_id == 1)),
        unowned(LeaveRequest.__table__))
    balances = select(LeaveBalance.id).where(LeaveBalance.employee_id.in_(employees), unowned(LeaveBalance.__table__))
    keys = [scope_key(scope.company_id), scope_key(scope.company_id, 'hrms')]
    if scope.branch.branch_id:
        keys += [scope_key(scope.company_id, branch_id=scope.branch.branch_id),
            scope_key(scope.company_id, 'hrms', scope.branch.branch_id)]
    conditions = {
        Employee: employee_company,
        LeaveRequest: and_(LeaveRequest.employee_id.in_(employees), or_(LeaveRequest.company_id == scope.company_id,
            LeaveRequest.company_id.is_(None) & (scope.company_id == 1))),
        LeaveBalance: LeaveBalance.employee_id.in_(employees),
        LeaveBalanceLedger: and_(LeaveBalanceLedger.employee_id.in_(employees),
            or_(LeaveBalanceLedger.leave_request_id.is_(None), LeaveBalanceLedger.leave_request_id.in_(requests)),
            or_(LeaveBalanceLedger.leave_balance_id.is_(None), LeaveBalanceLedger.leave_balance_id.in_(balances))),
        LeaveType: company_definition(LeaveType), Holiday: company_definition(Holiday),
        Company: Company.id == scope.company_id, Branch: Branch.company_id == scope.company_id,
        Department: Department.branch_id.in_(select(Branch.id).where(Branch.company_id == scope.company_id)),
        Designation: Designation.department_id.in_(select(Department.id).where(Department.branch_id.in_(
            select(Branch.id).where(Branch.company_id == scope.company_id)))),
        User: User.id == actor.id, Role: Role.id == actor.role_id,
        Permission: Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == actor.role_id)),
        ServicePolicy: and_(ServicePolicy.organization_id == scope.company_id, ServicePolicy.kind == 'form_defaults',
            ServicePolicy.scope_key.in_(keys)),
    }
    conditions = {model: and_(condition, unowned(model.__table__)) for model, condition in conditions.items()}
    reads = set(conditions)
    options = tuple(with_loader_criteria(mapper.class_, conditions.get(mapper.class_, false()),
        include_aliases=True, propagate_to_loaders=False) for mapper in Base.registry.mappers)
    checking = False
    identity_load = False
    validated_requests = {}
    def fresh():
        nonlocal checking
        if checking: return
        checking = True
        try:
            if (actor.id != scope.user_id or actor.organization_id != scope.company_id
                    or db.info.get(MARKER) != scope.binding or db.info.get('business_pack_scope') is not None
                    or db.info.get('branch_context') != scope.branch): deny('Native leave request authority changed')
            selected = str(scope.branch.branch_id) if scope.branch.branch_id else 'all' if scope.branch.all_branches else None
            if branch_context(db, actor, scope.company_id, selected) != scope.branch: deny('Native leave branch authority changed')
            if _native_authority(db, actor, scope.company_id) != scope.native_authority: deny('Native leave permissions changed')
            _native_operation_access(db, actor, scope.company_id, scope.operation)
        finally:
            checking = False
    def restrict(execution):
        if checking: return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            deny('Native leave requires validated per-record ORM operations')
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in reads:
            deny('This table is outside the native leave graph')
        from .common_queries import assert_mapped_sources
        assert_mapped_sources(execution.statement, reads, trusted_identity=identity_load,
            allowed_associations=(role_permissions,))
        if not identity_load and not execution.is_column_load and not execution.is_relationship_load:
            from .employee_core import _count_stars
            count_stars = _count_stars(execution.statement)
            for node in visitors.iterate(execution.statement):
                if isinstance(node, TextClause) or (isinstance(node, ColumnClause) and
                        ((getattr(node, 'is_literal', False) and id(node) not in count_stars) or (getattr(node, 'table', None) is not None and not
                        (node._annotations.get('parententity') or node._annotations.get('parentmapper'))))):
                    deny('Native leave raw SQL requires a separate audited adapter')
        inherited = {id(option) for option in getattr(execution.statement, '_with_options', ())}
        execution.statement = execution.statement.options(*(option for option in options if id(option) not in inherited))
        execution.update_execution_options(compiled_cache=None)
    def validate(session, *args):
        fresh()
        for row in session.new | session.dirty | session.deleted:
            state = inspect(row)
            table = state.mapper.local_table
            if (type(row) not in {LeaveRequest, LeaveBalance, LeaveBalanceLedger, Notification, NotificationDeliveryLog, ServiceEvent}
                    or table.name not in scope.operation.writes or row in session.deleted
                    or (row in session.new and table.name not in scope.operation.creates)):
                deny('This native leave route cannot mutate that record')
            if isinstance(row, ServiceEvent):
                source = getattr(row, '_suite_source_record', None)
                from app.shared.runtime import DEPTH
                from uuid import UUID
                try: valid_key = UUID(row.request_key).version == 4
                except (ValueError, TypeError, AttributeError): valid_key = False
                proof = validated_requests.get(source)
                if (row not in session.new or proof is None or type(source) is not LeaveRequest
                        or inspect(source).session is not session or not inspect(source).persistent
                        or (row.organization_id, row.actor_id, row.module_key, row.entity_type, row.entity_id)
                            != (scope.company_id, actor.id, 'hrms', 'leave', source.id)
                        or row.event_type != proof or not valid_key
                        or not _event_payload(db,actor,scope,row.payload_json)
                        or row.status != ('depth_limited' if DEPTH.get() >= 6 else 'pending')):
                    deny('Native leave events require the actual validated source transition')
                continue
            if isinstance(row, (Notification, NotificationDeliveryLog)):
                validate_notification(db, actor, scope, row)
                continue
            if isinstance(row, LeaveBalanceLedger) and row not in session.new:
                deny('Native leave ledger entries are append-only')
            if row not in session.new:
                allowed = ({'pending', 'used'} if isinstance(row, LeaveBalance) and scope.operation.action == 'approve'
                    else {'pending'} if isinstance(row, LeaveBalance)
                    else {'status', 'reviewed_by', 'reviewed_at', 'review_remarks'} if scope.operation.action == 'approve'
                    else {'status'})
                if any(attribute.history.has_changes() and attribute.key not in allowed for attribute in state.attrs
                        if attribute.key in table.c):
                    deny('This leave action cannot change that native field')
            values = {column.name: getattr(row, column.name) for column in table.primary_key}
            if present and all(value is not None for value in values.values()) and db.connection().scalar(select(exists().where(
                    owner.c.resource_table == table.name, owner.c.resource_key == resource_key(table, values)))):
                deny('Pack-private records cannot be adopted into native leave')
            if row not in session.new and any(state.attrs[field].history.has_changes() for field in
                    {'employee_id', 'leave_type_id', 'company_id', 'leave_request_id', 'leave_balance_id', 'year'} & set(table.c.keys())):
                deny('Native leave identity and ledger parents are immutable')
            with db.no_autoflush:
                if isinstance(row, LeaveRequest) and row in session.new:
                    applicant = session.query(Employee.id).filter(Employee.id == row.employee_id, Employee.user_id == actor.id).first()
                    if applicant is None: deny('Native leave application must belong to the current employee')
                if isinstance(row, LeaveBalanceLedger):
                    balance = session.query(LeaveBalance).filter(LeaveBalance.id == row.leave_balance_id,
                        LeaveBalance.employee_id == row.employee_id, LeaveBalance.leave_type_id == row.leave_type_id,
                        LeaveBalance.year == row.year).first()
                    request = session.query(LeaveRequest).filter(LeaveRequest.id == row.leave_request_id,
                        LeaveRequest.employee_id == row.employee_id, LeaveRequest.leave_type_id == row.leave_type_id).first()
                    if balance is None or request is None:
                        deny('Native leave ledger requires matching canonical request and balance parents')
                for column in table.c:
                    value = getattr(row, column.name)
                    if value is None: continue
                    for fk in column.foreign_keys:
                        parent = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}.get(fk.column.table.name)
                        if parent is User and column.name in {'created_by', 'reviewed_by', 'deleted_by'}:
                            if (row in session.new or state.attrs[column.name].history.has_changes()) and value != actor.id:
                                deny('Native leave authorship must match the actor')
                            continue
                        if parent not in reads: deny('Native leave cannot reference an unreviewed graph')
                        attribute = getattr(parent, inspect(parent).get_property_by_column(fk.column).key)
                        if not session.query(attribute).filter(attribute == value).first():
                            deny('Native leave parent is outside the authorized scope')
            if isinstance(row, LeaveRequest):
                validated_requests[row] = ('record.created' if row in session.new else
                    'status.changed' if state.attrs.status.history.has_changes() else 'record.updated')
    original_get, original_refresh = db.get, db.refresh
    def visible(model, identity):
        fresh()
        mapper = inspect(model, raiseerr=False)
        model = getattr(mapper, 'class_', model)
        if model not in reads: return False
        keys = inspect(model).primary_key
        values = [identity.get(key.key) for key in keys] if isinstance(identity, dict) else list(identity) if isinstance(identity, (tuple, list)) else [identity]
        if len(keys) != len(values): return False
        attributes = [getattr(model, inspect(model).get_property_by_column(key).key) for key in keys]
        with db.no_autoflush:
            return db.query(*attributes).filter(*(key == value for key, value in zip(attributes, values))).first() is not None
    def scoped_get(model, identity, **kwargs):
        nonlocal identity_load
        if not visible(model, identity): return None
        previous = identity_load; identity_load = True
        try: return original_get(model, identity, **kwargs)
        finally: identity_load = previous
    def scoped_refresh(row, *args, **kwargs):
        nonlocal identity_load
        if not visible(type(row), inspect(row).identity): deny('Cached record is outside native leave authority')
        previous = identity_load; identity_load = True
        try: return original_refresh(row, *args, **kwargs)
        finally: identity_load = previous
    bulk = {name: getattr(db, name) for name in ('bulk_insert_mappings', 'bulk_update_mappings', 'bulk_save_objects')}
    def reject(*args, **kwargs): deny('Native leave bulk writes require a separate adapter')
    fresh()
    for name in bulk: setattr(db, name, reject)
    for state in list(db.identity_map.all_states()):
        if state.obj() is not None and state.class_ not in {User, Role, Permission}: db.expire(state.obj())
    db.get, db.refresh = scoped_get, scoped_refresh
    db.info['business_common_core_scope'] = scope
    event.listen(db, 'do_orm_execute', restrict); event.listen(db, 'before_flush', validate)
    closed = False
    def cleanup():
        nonlocal closed
        if closed: return
        closed = True
        event.remove(db, 'do_orm_execute', restrict); event.remove(db, 'before_flush', validate)
        db.get, db.refresh = original_get, original_refresh
        for name, method in bulk.items(): setattr(db, name, method)
        db.info.pop('business_common_core_scope', None)
        _NOTIFICATIONS.pop(db, None)
    return cleanup


def validate_notification(db, actor, scope, row):
    from .common_core import deny
    from app.models.notification import NotificationDeliveryLog
    proof = _NOTIFICATIONS.get(db, {}).get(row)
    if row not in db.new or proof is None or proof[0] != scope:
        deny('Native leave notifications require their exact canonical source')
    if any(getattr(row, key) != value for key, value in proof[1].items()):
        deny('Native leave notification identity and payload cannot change')
    if isinstance(row, NotificationDeliveryLog) and row.notification_id not in {None, row.notification.id}:
        deny('Native leave delivery must retain its canonical notification')


def notify(db, user_id, title, message, event_type, request_id):
    """Native in-app notification only, proved from the actual leave transition.

    The original leave endpoint requests only in_app. Avoid loading unrelated
    contact/profile graphs for a channel that has no external recipient.
    """
    from .common_core import CommonCoreScope, deny
    from app.models.leave import LeaveRequest
    from app.models.employee import Employee
    from app.models.notification import Notification, NotificationDeliveryLog
    scope = db.info.get('business_common_core_scope')
    if not isinstance(scope, CommonCoreScope) or scope.operation.purpose != PURPOSE:
        return False
    row = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    employee = db.query(Employee).filter(Employee.id == row.employee_id).first() if row else None
    if row is None or employee is None or row.company_id not in {None, scope.company_id}:
        deny('Native leave notification source is unavailable')
    if scope.method == 'POST' and scope.route == '/api/v1/leave/apply':
        if employee.user_id != scope.user_id or row.status != 'Pending':
            deny('Leave submission notification requires the actual applicant')
        manager = db.query(Employee).filter(Employee.id == employee.reporting_manager_id).first() if employee.reporting_manager_id else None
        name = ' '.join(part for part in (employee.first_name, employee.last_name) if part) or employee.employee_id or 'An employee'
        expected = (manager.user_id if manager else None, 'Leave Request Pending Approval',
            f'{name} has applied for leave from {row.from_date} to {row.to_date}.', 'leave_submitted')
    elif scope.method == 'PUT' and scope.route == '/api/v1/leave/requests/{request_id}/approve':
        if row.reviewed_by != scope.user_id or row.status not in {'Approved', 'Rejected'}:
            deny('Leave review notification requires the actual reviewer')
        remarks = f' Remarks: {row.review_remarks}' if row.review_remarks else ''
        expected = (employee.user_id, f'Leave {row.status}',
            f'Your leave request ({row.from_date} - {row.to_date}) has been {row.status.lower()}.{remarks}',
            f'leave_{row.status.lower()}')
    else:
        deny('This native leave action cannot send notifications')
    if user_id is None or (user_id, title, message, event_type) != expected:
        deny('Leave notification does not match its canonical recipient and event')
    values = dict(company_id=scope.company_id, user_id=user_id, title=title, message=message,
        module='leave', event_type=event_type, related_entity_type='leave_request',
        related_entity_id=row.id, action_url='/leave', priority='normal', channels=['in_app'])
    notification = Notification(**values)
    delivery_values = dict(channel='in_app', recipient=None, status='delivered')
    delivery = NotificationDeliveryLog(**delivery_values)
    notification.delivery_logs = [delivery]
    proofs = _NOTIFICATIONS.setdefault(db, {})
    from copy import deepcopy
    proofs[notification] = (scope, deepcopy(values))
    proofs[delivery] = (scope, {**delivery_values, 'notification': notification})
    db.add(notification)
    db.flush()
    expire = db.expire_on_commit
    try:
        db.expire_on_commit = False
        db.commit()
    finally:
        db.expire_on_commit = expire
        _NOTIFICATIONS.pop(db, None)
    return True
