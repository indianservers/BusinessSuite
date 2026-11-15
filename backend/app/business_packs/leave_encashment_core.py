"""Finite canonical leave-encashment purpose, independent of pack selection.

Salary is a fixed calculation projection, never an ORM salary/read permission.
Payroll output is created only for the exact native request being approved.
There is no native cancellation endpoint; this adapter does not invent one.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import and_, event, exists, false, inspect, or_, select, true
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause, TextClause

PURPOSE = 'hrms.leave_encashment'
ROOT = '/api/v1/hrms/leave-encashment'
_COMMANDS = WeakKeyDictionary()
_CHECKS = WeakKeyDictionary()


def operations(operation):
    return candidate_operations(operation)


def candidate_operations(operation):
    return MappingProxyType({
        ('GET', ROOT): operation('view', None, purpose=PURPOSE),
        ('POST', ROOT + '/request'): operation('create', None,
            frozenset({'leave_encashment_requests'}), frozenset({'leave_encashment_requests'}), purpose=PURPOSE),
        ('POST', ROOT + '/{request_id}/approve'): operation('approve', ('payroll_run', 'leave_approve'),
            frozenset({'leave_encashment_requests', 'leave_balances', 'leave_balance_ledger',
                'payroll_pay_groups', 'payroll_periods', 'leave_encashment_lines'}),
            frozenset({'leave_balance_ledger', 'payroll_pay_groups', 'payroll_periods', 'leave_encashment_lines'}), purpose=PURPOSE),
        ('POST', ROOT + '/{request_id}/reject'): operation('approve', ('payroll_run', 'leave_approve'),
            frozenset({'leave_encashment_requests'}), purpose=PURPOSE),
    })


def native_self_request(db, actor, company, operation):
    from .common_binding import CoreRequestBinding, MARKER
    from .common_core import OPERATIONS
    binding = db.info.get(MARKER)
    return (isinstance(binding, CoreRequestBinding) and binding.purpose == PURPOSE
        and binding.user_id == actor.id and binding.company_id == company
        and (binding.method, binding.route) in {('GET', ROOT), ('POST', ROOT + '/request')}
        and OPERATIONS.get((binding.method, binding.route)) is operation)


def _money(value):
    from app.api.v1.leave_payroll import _money as native_money
    return native_money(value)


def _days(value):
    from app.api.v1.leave_payroll import _days as native_days
    return native_days(value)


@dataclass
class _Command:
    scope: object
    actor: object
    kind: str
    employee: object
    data: object
    request: object = None
    source: dict = field(default_factory=dict)
    balance: object = None
    balance_used: object = None
    rate: object = None
    group: object = None
    period: object = None
    line: object = None
    created_request: object = None
    ledger: object = None


def lock_tenant(db, actor, scope):
    """Canonical company lock precedes request/balance/payroll row locks."""
    from .common_core import deny
    check = _CHECKS.get(db)
    if check is None or actor.id != scope.user_id: deny('A native encashment writer is required')
    check()
    from app.core.company_writer import lock_company_writer
    lock_company_writer(db,scope.company_id)
    check()  # Revocation/branch changes while waiting must win.


@contextmanager
def command(db, actor, *, data, request_id=None):
    """Only native endpoint values and freshly visible canonical parents enter."""
    from .common_core import CommonCoreScope, deny
    from app.api.v1.leave_payroll import _can_manage_leave_payroll, _employee_for_user, _load_encashment_request
    from app.models.employee import Employee
    from app.models.payroll import LeaveEncashmentRequest
    scope = db.info.get('business_common_core_scope')
    if not isinstance(scope, CommonCoreScope) or scope.operation.purpose != PURPOSE:
        yield
        return
    check = _CHECKS.get(db)
    if check is None or actor.id != scope.user_id or db in _COMMANDS:
        deny('An exact independent native encashment command is required')
    check()
    kind = 'request' if scope.route == ROOT + '/request' else 'approve' if scope.route == ROOT + '/{request_id}/approve' else 'reject'
    if kind in {'request','approve'} and scope.branch.branch_id is None:
        deny('Select a destination branch before creating business records')
    lock_tenant(db,actor,scope)
    request = None
    if kind == 'request':
        identity = data.employeeId
        if identity is not None and not _can_manage_leave_payroll(actor):
            raise HTTPException(403, 'Only HR/payroll can request encashment for another employee')
        identity = identity or _employee_for_user(actor).id
    else:
        request = _load_encashment_request(db, request_id, actor)
        request = db.query(LeaveEncashmentRequest).filter(LeaveEncashmentRequest.id == request.id).populate_existing().with_for_update(of=LeaveEncashmentRequest).first()
        if request is None: raise HTTPException(404, 'Leave encashment request not found')
        if kind == 'approve' and request.status not in {'submitted','draft'}:
            raise HTTPException(400, 'Only draft/submitted requests can be approved')
        if kind == 'reject' and request.status in {'approved','paid'}:
            raise HTTPException(400, 'Approved or paid requests cannot be rejected')
        from app.api.v1.leave_payroll import _assert_encashment_source
        _assert_encashment_source(request,payout=kind=='approve')
        identity = request.employee_id
    employee = db.query(Employee).filter(Employee.id == identity, Employee.deleted_at.is_(None)).first()
    if employee is None: raise HTTPException(404, 'Employee not found')
    if inspect(employee).session is not db or not inspect(employee).persistent:
        deny('Encashment requires its actual canonical employee')
    plan = _Command(scope, actor, kind, employee, data, request)
    if request is not None:
        plan.source = {column.name: getattr(request, column.name) for column in request.__table__.c}
    _COMMANDS[db] = plan
    try:
        yield
    finally:
        _COMMANDS.pop(db, None)


def note_balance(db, balance):
    """Capture the actual native balance after its original validation order."""
    from .common_core import CommonCoreScope, deny
    from app.models.leave import LeaveBalance
    scope = db.info.get('business_common_core_scope')
    if not isinstance(scope, CommonCoreScope) or scope.operation.purpose != PURPOSE: return
    plan = _COMMANDS.get(db)
    if plan is None or plan.kind not in {'request','approve'}: deny('Native encashment balance requires its exact command')
    leave_type = plan.data.leaveTypeId if plan.kind == 'request' else plan.source['leave_type_id']
    if (type(balance) is not LeaveBalance or inspect(balance).session is not db or not inspect(balance).persistent
            or (balance.employee_id,balance.leave_type_id,balance.year) != (plan.employee.id,leave_type,date.today().year)
            or plan.balance not in {None,balance}): deny('Encashment balance does not match its canonical source')
    if plan.balance is None:
        plan.balance = balance
        plan.balance_used = balance.used


def daily_rate(db, employee_id):
    """Return only the original derived rate for an authorized native request."""
    from .common_core import CommonCoreScope, deny
    from .models import PackRecordOwnership
    from app.models.payroll import EmployeeSalary
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.models.security_boundary import SecurityResourceOwnership
    from app.branches.models import BranchOwnership
    scope = db.info.get('business_common_core_scope')
    if not isinstance(scope, CommonCoreScope) or scope.operation.purpose != PURPOSE:
        return None
    plan = _COMMANDS.get(db)
    check = _CHECKS.get(db)
    if (plan is None or plan.scope is not scope or plan.kind != 'request' or check is None or plan.balance is None
            or employee_id != plan.employee.id or inspect(plan.employee).session is not db):
        deny('Salary rate requires the exact authorized encashment employee')
    check()
    visible = db.query(Employee.id).filter(Employee.id == employee_id).first()
    if visible is None: deny('Encashment employee authority changed')
    connection = db.connection()
    branch_owner = BranchOwnership.__table__
    branch = connection.execute(select(branch_owner.c.company_id, branch_owner.c.branch_id).where(
        branch_owner.c.resource_table == 'employees', branch_owner.c.resource_key == str(employee_id))).first()
    if (branch is None or branch.company_id != scope.company_id or branch.branch_id not in scope.branch.allowed
            or not connection.scalar(select(Branch.id).where(Branch.id == branch.branch_id, Branch.company_id == scope.company_id))
            or plan.employee.branch_id not in {None, branch.branch_id}):
        deny('Encashment requires a verified native employee branch')
    salary = connection.execute(select(EmployeeSalary.id, EmployeeSalary.ctc, EmployeeSalary.basic, EmployeeSalary.structure_id)
        .where(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_active.is_(True))
        .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc()).limit(1)).first()
    if salary is None:
        plan.rate = Decimal('0')
        return plan.rate
    if any(not Decimal(str(value)).is_finite() or Decimal(str(value)) < 0 for value in (salary.ctc,salary.basic) if value is not None):
        raise HTTPException(503, 'Native encashment salary provenance requires reconciliation')
    salary_branch = connection.execute(select(branch_owner.c.company_id, branch_owner.c.branch_id).where(
        branch_owner.c.resource_table == 'employee_salaries', branch_owner.c.resource_key == str(salary.id))).first()
    owner = PackRecordOwnership.__table__
    private = inspect(connection).has_table(owner.name) and connection.scalar(select(exists().where(
        owner.c.resource_table == 'employee_salaries', owner.c.resource_key == str(salary.id))))
    if salary_branch is None or tuple(salary_branch) != (scope.company_id, branch.branch_id) or private:
        raise HTTPException(503, 'Native encashment salary provenance requires reconciliation')
    if salary.structure_id is not None:
        native = SecurityResourceOwnership.__table__
        if not connection.scalar(select(native.c.resource_id).where(native.c.resource_table == 'salary_structures',
                native.c.resource_id == salary.structure_id, native.c.company_id == scope.company_id)):
            raise HTTPException(503, 'Native encashment salary provenance requires reconciliation')
    from app.api.v1.leave_payroll import _salary_daily_rate
    plan.rate = _salary_daily_rate(salary)
    return plan.rate


def assert_mutable(db, actor, request):
    """Blind native payroll-lock preflight, only for the actual approved source."""
    from .common_core import CommonCoreScope, deny
    from app.models.payroll import PayrollRun
    from app.branches.models import BranchOwnership
    from app.crud.crud_payroll import PAYROLL_RUN_STATUS_LOCKED, PAYROLL_RUN_STATUS_PAID
    scope = db.info.get('business_common_core_scope')
    if not isinstance(scope, CommonCoreScope) or scope.operation.purpose != PURPOSE:
        return False
    plan = _COMMANDS.get(db)
    if (plan is None or plan.scope is not scope or plan.actor is not actor or plan.kind != 'approve'
            or plan.request is not request or inspect(request).session is not db):
        deny('Payroll lock check requires its actual authorized encashment source')
    _CHECKS[db]()
    company = scope.company_id
    branch = plan.employee.branch_id
    owner = BranchOwnership.__table__
    if branch is None:
        branch = db.connection().scalar(select(owner.c.branch_id).where(owner.c.resource_table == 'employees',
            owner.c.resource_key == str(plan.employee.id), owner.c.company_id == company))
    if branch not in scope.branch.allowed: deny('Encashment source lacks native branch authority')
    today = date.today()
    from sqlalchemy import String, cast
    from app.models.company import Branch
    # A NULL native branch denotes a company-wide payroll scope. Its anchor
    # still has to prove this company's real branch; an unrelated explicit
    # branch never becomes a lock on this employee's inputs.
    relevant = select(PayrollRun.id).outerjoin(owner,and_(owner.c.resource_table=='payroll_runs',
        owner.c.resource_key==cast(PayrollRun.id,String))).where(
        PayrollRun.month == today.month, PayrollRun.year == today.year,
        PayrollRun.status.in_([PAYROLL_RUN_STATUS_LOCKED, PAYROLL_RUN_STATUS_PAID, 'Locked', 'Paid']),
        PayrollRun.deleted_at.is_(None),
        or_(PayrollRun.company_id == company, PayrollRun.company_id.is_(None) & (owner.c.company_id==company)),
        or_(PayrollRun.branch_id.is_(None),PayrollRun.branch_id==branch))
    actual_anchor = exists(select(1).select_from(owner.join(Branch.__table__,Branch.id==owner.c.branch_id)).where(
        owner.c.resource_table=='payroll_runs',owner.c.resource_key==cast(PayrollRun.id,String),
        owner.c.company_id==company,Branch.company_id==company,
        or_(PayrollRun.branch_id.is_(None),owner.c.branch_id==PayrollRun.branch_id))).correlate(PayrollRun.__table__)
    connection=db.connection()
    if connection.execute(relevant.where(~actual_anchor).limit(1)).first():
        raise HTTPException(503,'Native payroll lock provenance requires reconciliation')
    from .models import PackRecordOwnership
    private=PackRecordOwnership.__table__
    if inspect(connection).has_table(private.name) and connection.execute(relevant.where(exists(select(1).where(
            private.c.resource_table=='payroll_runs',private.c.resource_key==cast(PayrollRun.id,String))).correlate(PayrollRun.__table__)).limit(1)).first():
        raise HTTPException(503,'Native payroll lock provenance requires reconciliation')
    locked=connection.execute(relevant.limit(1)).first()
    if locked: raise HTTPException(409, 'Payroll is locked for this period; use a payroll adjustment')
    return True


def _groups(company):
    from app.models.payroll import PayrollPayGroup
    from app.models.company import Branch
    from app.models.security_boundary import SecurityResourceOwnership
    owner = SecurityResourceOwnership.__table__
    return or_(PayrollPayGroup.branch_id.in_(select(Branch.id).where(Branch.company_id == company)),
        PayrollPayGroup.branch_id.is_(None) & PayrollPayGroup.id.in_(select(owner.c.resource_id).where(
            owner.c.resource_table == 'payroll_pay_groups', owner.c.company_id == company)))


def native_predicate(db, actor, company, model):
    from .common_binding import CoreRequestBinding, MARKER
    from .common_core import OPERATIONS
    from app.models.leave import LeaveType
    from app.models.payroll import LeaveEncashmentPolicy, PayrollPayGroup, PayrollPeriod
    from app.models.security_boundary import SecurityResourceOwnership
    binding = db.info.get(MARKER)
    if (model not in {LeaveType, LeaveEncashmentPolicy, PayrollPayGroup, PayrollPeriod}
            or not isinstance(binding, CoreRequestBinding) or binding.purpose != PURPOSE
            or binding.user_id != actor.id or binding.company_id != company
            or db.info.get('business_pack_scope') is not None): return None
    operation = OPERATIONS.get((binding.method, binding.route))
    if operation is None or operation.purpose != PURPOSE: return None
    owner = SecurityResourceOwnership.__table__
    types = select(owner.c.resource_id).where(owner.c.resource_table == 'leave_types', owner.c.company_id == company)
    if model is LeaveType: return LeaveType.id.in_(types)
    if model is LeaveEncashmentPolicy:
        return and_(LeaveEncashmentPolicy.leave_type_id.in_(types), or_(LeaveEncashmentPolicy.pay_group_id.is_(None),
            LeaveEncashmentPolicy.pay_group_id.in_(select(PayrollPayGroup.id).where(_groups(company)))))
    # Native criteria are compiled before endpoint execution. The independent
    # ORM guard below additionally requires the live source lease for reads.
    if (binding.method,binding.route) != ('POST',ROOT+'/{request_id}/approve'): return false()
    return _groups(company) if model is PayrollPayGroup else PayrollPeriod.pay_group_id.in_(
        select(PayrollPayGroup.id).where(_groups(company)))


def install(db, actor, scope):
    from .common_core import deny, _native_authority, _native_operation_access
    from .common_binding import MARKER
    from .models import PackRecordOwnership
    from .common_queries import assert_mapped_sources
    from app.db.base_class import Base
    from app.models.employee import Employee
    from app.models.company import Company, Branch
    from app.models.leave import LeaveType, LeaveBalance
    from app.models.payroll import LeaveEncashmentRequest, LeaveEncashmentPolicy, PayrollPayGroup, PayrollPeriod
    from app.models.user import User, Role, Permission, role_permissions
    from app.models.security_boundary import SecurityResourceOwnership
    from app.api.v1.leave_payroll import _can_manage_leave_payroll
    from app.branches.catalog import key_expression
    from app.branches.service import context as branch_context
    if scope.operation.purpose != PURPOSE or scope.binding.purpose != PURPOSE:
        deny('An exact native leave encashment purpose is required')
    if db.info.get('business_pack_policy') is not None: deny('Native encashment cannot mix with private pack authority')
    previous = db.info.get('business_common_core_scope')
    if previous is not None:
        if previous != scope: deny('Native encashment purpose cannot change within a request')
        return lambda: None
    if db.new or db.deleted or any(db.is_modified(row, include_collections=True) for row in db.dirty):
        deny('Finish pending changes before binding native encashment')
    owner = PackRecordOwnership.__table__
    inspector = inspect(db.connection())
    present = inspector.has_table(owner.name)
    if present and not {'resource_table','resource_key','company_id','branch_id','context_id'} <= {
            column['name'] for column in inspector.get_columns(owner.name)}:
        raise HTTPException(503, 'Native encashment ownership exclusion installation is incomplete')
    def unowned(table):
        return ~exists(select(1).where(owner.c.resource_table == table.name,
            owner.c.resource_key == key_expression(table))).correlate(table) if present else true()
    employee = and_(Employee.deleted_at.is_(None), or_(Employee.branch_id.in_(select(Branch.id).where(
        Branch.company_id == scope.company_id)), Employee.branch_id.is_(None) & (scope.company_id == 1)))
    if not _can_manage_leave_payroll(actor): employee = and_(employee, Employee.user_id == actor.id)
    employees = select(Employee.id).where(employee, unowned(Employee.__table__))
    native = SecurityResourceOwnership.__table__
    types = select(native.c.resource_id).where(native.c.resource_table == 'leave_types', native.c.company_id == scope.company_id)
    conditions = {
        Employee: employee, LeaveType: LeaveType.id.in_(types),
        LeaveEncashmentRequest: and_(LeaveEncashmentRequest.employee_id.in_(employees),
            or_(LeaveEncashmentRequest.organization_id == scope.company_id,
                LeaveEncashmentRequest.organization_id.is_(None) & (scope.company_id == 1))),
        Company: Company.id == scope.company_id, Branch: Branch.company_id == scope.company_id,
        User: User.id == actor.id, Role: Role.id == actor.role_id,
        Permission: Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == actor.role_id)),
    }
    if scope.route in {ROOT + '/request', ROOT + '/{request_id}/approve'}:
        conditions[LeaveBalance] = LeaveBalance.employee_id.in_(employees)
        conditions[LeaveEncashmentPolicy] = and_(LeaveEncashmentPolicy.leave_type_id.in_(types),
            or_(LeaveEncashmentPolicy.pay_group_id.is_(None), LeaveEncashmentPolicy.pay_group_id.in_(
                select(PayrollPayGroup.id).where(_groups(scope.company_id)))))
    if scope.route == ROOT + '/{request_id}/approve':
        conditions[PayrollPayGroup] = _groups(scope.company_id)
        conditions[PayrollPeriod] = PayrollPeriod.pay_group_id.in_(select(PayrollPayGroup.id).where(_groups(scope.company_id)))
    conditions = {model: and_(condition, unowned(model.__table__)) for model, condition in conditions.items()}
    reads = set(conditions)
    options = tuple(with_loader_criteria(mapper.class_, conditions.get(mapper.class_, false()),
        include_aliases=True, propagate_to_loaders=False) for mapper in Base.registry.mappers)
    checking = False
    identity_load = False
    def fresh():
        nonlocal checking
        if checking: return
        checking = True
        try:
            if (actor.id != scope.user_id or actor.organization_id != scope.company_id or db.info.get(MARKER) != scope.binding
                    or db.info.get('business_pack_scope') is not None or db.info.get('branch_context') != scope.branch):
                deny('Native encashment request authority changed')
            selected = str(scope.branch.branch_id) if scope.branch.branch_id else 'all' if scope.branch.all_branches else None
            if branch_context(db, actor, scope.company_id, selected) != scope.branch: deny('Native encashment branch changed')
            if _native_authority(db, actor, scope.company_id) != scope.native_authority: deny('Native encashment permissions changed')
            _native_operation_access(db, actor, scope.company_id, scope.operation)
        finally:
            checking = False
    def restrict(execution):
        if checking: return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            deny('Native encashment requires validated per-record ORM operations')
        plan = _COMMANDS.get(db)
        active_reads = reads if plan is not None and plan.kind == 'approve' else reads - {PayrollPayGroup,PayrollPeriod}
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in active_reads:
            deny('This table is outside the finite native encashment graph')
        assert_mapped_sources(execution.statement, active_reads, trusted_identity=identity_load, allowed_associations=(role_permissions,))
        if not identity_load and not execution.is_column_load and not execution.is_relationship_load:
            from .employee_core import _count_stars
            stars = _count_stars(execution.statement)
            for node in visitors.iterate(execution.statement):
                if isinstance(node, TextClause) or (isinstance(node, ColumnClause) and
                        ((getattr(node, 'is_literal', False) and id(node) not in stars) or
                        (getattr(node, 'table', None) is not None and not
                            (node._annotations.get('parententity') or node._annotations.get('parentmapper'))))):
                    deny('Native encashment raw SQL requires its own audited adapter')
        inherited = {id(option) for option in getattr(execution.statement, '_with_options', ())}
        execution.statement = execution.statement.options(*(option for option in options if id(option) not in inherited))
        execution.update_execution_options(compiled_cache=None)
    def validate(session, *args):
        fresh()
        plan = _COMMANDS.get(db)
        for row in session.new | session.dirty | session.deleted:
            state = inspect(row)
            table = state.mapper.local_table
            if (plan is None or plan.scope is not scope or plan.actor is not actor or row in session.deleted
                    or table.name not in scope.operation.writes
                    or (row in session.new and table.name not in scope.operation.creates)):
                deny('Native encashment writes require their exact canonical command')
            if state.identity and present and db.connection().scalar(select(exists().where(
                    owner.c.resource_table == table.name, owner.c.resource_key == str(state.identity[0])))):
                deny('Pack-private records cannot become native encashment')
            validate_row(db, plan, row)
    original_get, original_refresh = db.get, db.refresh
    def visible(model, identity):
        fresh()
        mapper = inspect(model, raiseerr=False); model = getattr(mapper, 'class_', model)
        if model not in reads: return False
        keys = inspect(model).primary_key
        values = [identity.get(key.key) for key in keys] if isinstance(identity, dict) else list(identity) if isinstance(identity, (tuple, list)) else [identity]
        if len(keys) != len(values): return False
        attributes = [getattr(model, inspect(model).get_property_by_column(key).key) for key in keys]
        with db.no_autoflush:
            return db.query(*attributes).filter(*(key == value for key,value in zip(attributes,values))).first() is not None
    def scoped_get(model, identity, **kwargs):
        nonlocal identity_load
        if not visible(model, identity): return None
        previous = identity_load; identity_load = True
        try: return original_get(model, identity, **kwargs)
        finally: identity_load = previous
    def scoped_refresh(row, *args, **kwargs):
        nonlocal identity_load
        if not visible(type(row), inspect(row).identity): deny('Cached record is outside native encashment authority')
        previous = identity_load; identity_load = True
        try: return original_refresh(row, *args, **kwargs)
        finally: identity_load = previous
    bulk = {name: getattr(db, name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject(*args, **kwargs): deny('Native encashment bulk writes require their own adapter')
    fresh()
    for name in bulk: setattr(db, name, reject)
    for state in list(db.identity_map.all_states()):
        if state.obj() is not None and state.class_ not in {User,Role,Permission}: db.expire(state.obj())
    db.get, db.refresh = scoped_get, scoped_refresh
    db.info['business_common_core_scope'] = scope
    _CHECKS[db] = fresh
    event.listen(db,'do_orm_execute',restrict); event.listen(db,'before_flush',validate)
    closed = False
    def cleanup():
        nonlocal closed
        if closed: return
        closed = True
        event.remove(db,'do_orm_execute',restrict); event.remove(db,'before_flush',validate)
        db.get, db.refresh = original_get, original_refresh
        for name, method in bulk.items(): setattr(db,name,method)
        db.info.pop('business_common_core_scope',None)
        _CHECKS.pop(db,None); _COMMANDS.pop(db,None)
    return cleanup


def validate_row(db, plan, row):
    from .common_core import deny
    from app.models.leave import LeaveBalance, LeaveBalanceLedger
    from app.models.payroll import LeaveEncashmentRequest, LeaveEncashmentLine, PayrollPayGroup, PayrollPeriod
    from app.api.v1.leave_payroll import _active_policy, _month_bounds, _available_days
    state = inspect(row)
    if type(row) not in {LeaveEncashmentRequest, LeaveBalance, LeaveBalanceLedger,
            LeaveEncashmentLine, PayrollPayGroup, PayrollPeriod}:
        deny('This native model is outside the encashment command')
    if row in db.new and row.id is not None: deny('Native encashment identities are database allocated')
    if state.identity and state.attrs.id.history.has_changes(): deny('Native encashment identity is immutable')
    today = date.today()
    if type(row) is LeaveEncashmentRequest:
        if row in db.new:
            if (plan.kind != 'request' or plan.created_request not in {None, row} or plan.rate is None or plan.balance is None
                    or (row.organization_id, row.employee_id, row.leave_type_id, row.days_to_encash,
                        row.encashment_rate, row.amount, row.status, row.remarks)
                    != (plan.scope.company_id, plan.employee.id, plan.data.leaveTypeId, plan.data.daysToEncash,
                        plan.rate, _money(plan.rate * plan.data.daysToEncash), 'submitted', plan.data.remarks)
                    or any(getattr(row, name) is not None for name in ('approved_by', 'approved_at',
                        'payroll_run_id', 'leave_encashment_line_id'))):
                deny('New encashment must match the exact native request and derived rate')
            from app.models.leave import LeaveType
            with db.no_autoflush:
                eligible = db.query(LeaveType.id).filter(LeaveType.id == row.leave_type_id,
                    LeaveType.is_active.is_(True),LeaveType.encashable.is_(True)).first()
                policy = _active_policy(db,row.leave_type_id,today)
            if eligible is None or row.days_to_encash > _available_days(plan.balance) or (
                    policy is not None and policy.max_days is not None and row.days_to_encash > _days(policy.max_days)):
                raise HTTPException(409,'Native leave encashment eligibility changed; reload the request')
            plan.created_request = row
        else:
            if row is not plan.request or plan.kind not in {'approve','reject'}:
                deny('Only the exact native encashment request may be reviewed')
            allowed = {'status','approved_by','approved_at','remarks'} | ({'leave_encashment_line_id'} if plan.kind == 'approve' else set())
            if any(attribute.history.has_changes() and attribute.key not in allowed for attribute in state.attrs
                    if attribute.key in row.__table__.c): deny('Native encashment source fields are immutable')
            if (row.status != ('approved' if plan.kind == 'approve' else 'rejected')
                    or row.approved_by != plan.actor.id or row.approved_at is None
                    or row.remarks != (plan.data.remarks or plan.source['remarks'])
                    or any(getattr(row, key) != value for key,value in plan.source.items() if key not in allowed)):
                deny('Native encashment review differs from its exact source transition')
            if plan.kind == 'approve' and (plan.line is None or row.leave_encashment_line_id != plan.line.id):
                deny('Approved encashment must retain its exact payroll output line')
        return
    if plan.kind != 'approve' or plan.request is None:
        deny('Payroll outputs require the exact approved native encashment source')
    if plan.source['status'] not in {'submitted','draft'} or plan.source['payroll_run_id'] is not None or plan.source['leave_encashment_line_id'] is not None:
        raise HTTPException(409, 'Native encashment source requires reconciliation')
    if type(row) is LeaveBalance:
        if row is not plan.balance or row in db.new: deny('Encashment may debit only its exact existing balance')
        if any(attribute.history.has_changes() and attribute.key != 'used' for attribute in state.attrs
                if attribute.key in row.__table__.c): deny('Encashment cannot change other native balance fields')
        if row.used != _days(plan.balance_used) + _days(plan.source['days_to_encash']):
            deny('Native encashment debit differs from the source days')
        return
    if row not in db.new: deny('Encashment output rows cannot be rewritten by this command')
    if type(row) is PayrollPayGroup:
        provided = {attribute.key for attribute in state.mapper.column_attrs if state.attrs[attribute.key].history.has_changes()}
        if (plan.group not in {None,row} or row.name != 'Default Payroll Group' or row.code != 'DEFAULT'
                or not row.is_default or not row.is_active or row.branch_id != plan.scope.branch.branch_id
                or provided - {'name','code','is_default','is_active','branch_id'}):
            deny('Only the exact existing native default pay-group creation is permitted')
        plan.group = row
        return
    if type(row) is PayrollPeriod:
        start,end = _month_bounds(f'{today.year:04d}-{today.month:02d}')
        with db.no_autoflush:
            group = db.query(PayrollPayGroup.id).filter(PayrollPayGroup.id == row.pay_group_id).first()
        expected = dict(month=today.month,year=today.year,financial_year=f'{today.year}-{str(today.year+1)[-2:]}',
            period_start=start,period_end=end,payroll_date=end,status='Open')
        if (plan.period not in {None,row} or group is None or any(getattr(row,key) != value for key,value in expected.items())
                or any(getattr(row,key) is not None for key in ('locked_by','locked_at','attendance_cutoff_at','input_cutoff_at'))):
            deny('Only the exact current native payroll period can be created')
        plan.period = row
        return
    if type(row) is LeaveEncashmentLine:
        with db.no_autoflush:
            period = db.query(PayrollPeriod).filter(PayrollPeriod.month == today.month,
                PayrollPeriod.year == today.year).order_by(PayrollPeriod.id.desc()).first()
            policy = _active_policy(db, plan.source['leave_type_id'], today)
        expected = dict(period_id=period.id if period else None,employee_id=plan.employee.id,
            policy_id=policy.id if policy else None,leave_type_id=plan.source['leave_type_id'],
            days=plan.source['days_to_encash'],rate_per_day=plan.source['encashment_rate'],amount=plan.source['amount'],
            tax_treatment=policy.tax_treatment if policy else 'Taxable',status='Approved',approved_by=plan.actor.id,
            payroll_record_id=None)
        if (plan.line not in {None,row} or period is None or row.approved_at is None
                or any(getattr(row,key) != value for key,value in expected.items())):
            deny('Native encashment payroll line differs from its exact source request')
        plan.line = row
        return
    if type(row) is LeaveBalanceLedger:
        expected = dict(employee_id=plan.employee.id,leave_type_id=plan.source['leave_type_id'],
            leave_balance_id=plan.balance.id,leave_request_id=None,year=today.year,transaction_type='encashment',
            amount=-_days(plan.source['days_to_encash']),balance_after=_available_days(plan.balance),
            reason=plan.data.remarks or 'Leave encashment approved',created_by=plan.actor.id)
        if plan.ledger not in {None,row} or any(getattr(row,key) != value for key,value in expected.items()):
            deny('Native encashment ledger differs from its exact source debit')
        plan.ledger = row
        return
    deny('Unreviewed native encashment output')
