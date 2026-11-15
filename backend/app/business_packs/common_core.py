"""Closed native HRMS purposes, independent of the selected Business Pack.

Only registered actual-time, employee-management, reference and leave routes
enter their respective finite adapters. Other native graphs require their own
review. Native module, record, field, company and branch guards stay bound.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType

from fastapi import HTTPException
from sqlalchemy import and_, event, exists, false, inspect, or_, select, true
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause, TextClause

from app.db.base_class import Base
from app.branches.catalog import key_expression, resource_key
from app.branches.service import BranchContext
from .common_binding import CoreRequestBinding, MARKER, canonical_route as _canonical, request_binding
from .models import PackRecordOwnership


@dataclass(frozen=True)
class CoreOperation:
    action: str
    permission: str | tuple[str,...] | None
    writes: frozenset[str] = frozenset()
    creates: frozenset[str] = frozenset()
    deletes: frozenset[str] = frozenset()
    purpose: str = 'hrms.actual_time'
    module: str = 'hrms'


_TIME_OPERATIONS = {
    ('GET','/api/v1/timesheets/projects'):CoreOperation('view','timesheet_view'),
    ('GET','/api/v1/timesheets/projects/{identity}'):CoreOperation('view','timesheet_view'),
    ('POST','/api/v1/timesheets/projects'):CoreOperation('create','timesheet_manage',frozenset({'projects'}),frozenset({'projects'})),
    ('PUT','/api/v1/timesheets/projects/{identity}'):CoreOperation('edit','timesheet_manage',frozenset({'projects'})),
    ('DELETE','/api/v1/timesheets/projects/{identity}'):CoreOperation('delete','timesheet_manage',frozenset({'projects'}),deletes=frozenset({'projects'})),
    ('GET','/api/v1/timesheets/'):CoreOperation('view','timesheet_view'),
    ('POST','/api/v1/timesheets/'):CoreOperation('create','timesheet_view',frozenset({'timesheets'}),frozenset({'timesheets'})),
    ('POST','/api/v1/timesheets/{timesheet_id}/entries'):CoreOperation('create','timesheet_view',frozenset({'timesheets','timesheet_entries'}),frozenset({'timesheet_entries'})),
    ('PUT','/api/v1/timesheets/{timesheet_id}/submit'):CoreOperation('edit','timesheet_view',frozenset({'timesheets'})),
    ('PUT','/api/v1/timesheets/{timesheet_id}/review'):CoreOperation('approve','timesheet_approve',frozenset({'timesheets'})),
}
from .employee_core import operations as employee_operations
from .employee_references import operations as reference_operations
from .leave_core import operations as leave_operations
from .leave_encashment_core import operations as encashment_operations
from .request_context_core import operations as request_context_operations
from .payroll_register import operations as payroll_register_operations
from .payroll_review import operations as payroll_review_operations
from .payroll_variance import operations as payroll_variance_operations
from .company_master_core import operations as company_master_operations
from .payroll_payslip import operations as payroll_payslip_operations
from .hrms_home_core import operations as hrms_home_operations
OPERATIONS = MappingProxyType({**_TIME_OPERATIONS,**employee_operations(CoreOperation),**reference_operations(CoreOperation),**leave_operations(CoreOperation),**encashment_operations(CoreOperation),**request_context_operations(CoreOperation),**payroll_register_operations(CoreOperation),**payroll_review_operations(CoreOperation),**payroll_variance_operations(CoreOperation),**company_master_operations(CoreOperation),**payroll_payslip_operations(CoreOperation),**hrms_home_operations(CoreOperation)})


@dataclass(frozen=True)
class CommonCoreScope:
    user_id: int
    company_id: int
    branch: BranchContext
    binding: CoreRequestBinding
    method: str
    route: str
    operation: CoreOperation
    native_authority: str


def deny(message):
    raise HTTPException(403,message)


def _native_authority(db,actor,company,*,employee_before=None,employee_expected=None,role_transition=None):
    """Core-only revocation fingerprint; no credentials or HR profile fields."""
    from app.models.user import User,Role,Permission,role_permissions
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.access.models import AccessMembership,AccessPolicy,AccessRole
    from app.branches.models import BranchGrant,BranchPolicy,BranchLifecycle
    connection=db.connection()
    user=connection.execute(select(User.id,User.is_active,User.is_superuser,User.role_id).where(User.id==actor.id)).first()
    if not user or not user.is_active:deny('Fresh native Common Core actor is required')
    role_identity=user.role_id
    if role_transition is not None:
        from .employee_core import verify_self_role_transition
        role_identity=verify_self_role_transition(db,actor,company,role_transition,user)
    elif user.role_id!=actor.role_id or bool(user.is_superuser)!=bool(actor.is_superuser):
        deny('Native Common Core actor role changed; reload authorization')
    policy=connection.execute(select(AccessPolicy.status,AccessPolicy.version,AccessPolicy.grants).where(AccessPolicy.user_id==actor.id,AccessPolicy.company_id==company)).first()
    bound_version=getattr(actor,'_suite_policy_version',None)
    if (policy and policy.status!='active') or (bound_version is not None and (policy is None or policy.version!=bound_version)):
        deny('Native Common Core policy changed; reload authorization')
    administrative_read=bool(getattr(actor,'_suite_admin_read',False) and db.info.get('admin_read_company')==company)
    if not administrative_read and not user.is_superuser and getattr(actor,'_suite_grants',None) is None:
        compiled=getattr(actor,'_suite_permission_objects',None)
        if compiled is None:
            compiled=actor.role.permissions if actor.role else []
        expected={(item.id,item.name,item.module) for item in compiled}
        actual={tuple(row) for row in connection.execute(select(Permission.id,Permission.name,Permission.module).join(
            role_permissions,role_permissions.c.permission_id==Permission.id).where(role_permissions.c.role_id==user.role_id))}
        if expected!=actual:deny('Initial native role permissions changed; reload authorization')
    if not administrative_read:
        # The foreground native predicate was compiled with these resolved
        # managed-role revisions. A new hash must never legitimize stale scope.
        for module,grant in (getattr(actor,'_suite_grants',None) or {}).items():
            role_id=grant.get('roleId')
            if not role_id:continue
            revision=grant.get('roleVersion')
            current_role=connection.execute(select(AccessRole.company_id,AccessRole.module_key,AccessRole.active,AccessRole.version).where(AccessRole.id==role_id)).first()
            if (type(role_id) is not int or type(revision) is not int or not current_role
                    or current_role.company_id!=company or current_role.module_key!=module
                    or not current_role.active or current_role.version!=revision):
                deny('Native Common Core managed role changed; reload authorization')
    statements=[
        select(Role.id,Role.name).where(Role.id==role_identity),
        select(AccessMembership.active,AccessMembership.is_admin).where(AccessMembership.user_id==actor.id,AccessMembership.company_id==company),
        select(AccessRole.id,AccessRole.active,AccessRole.version,AccessRole.permissions,AccessRole.actions,AccessRole.scope).where(AccessRole.company_id==company).order_by(AccessRole.id),
        select(BranchGrant.branch_id,BranchGrant.can_write,BranchGrant.module_grants).where(BranchGrant.user_id==actor.id,BranchGrant.company_id==company).order_by(BranchGrant.branch_id),
        select(BranchPolicy.all_branches,BranchPolicy.manage_access,BranchPolicy.use_home_branch,BranchPolicy.version).where(BranchPolicy.user_id==actor.id,BranchPolicy.company_id==company),
        select(Branch.id,Branch.is_active,BranchLifecycle.deleted_at,BranchLifecycle.version).select_from(Branch.__table__.outerjoin(BranchLifecycle,BranchLifecycle.branch_id==Branch.id)).where(Branch.company_id==company).order_by(Branch.id),
        select(Permission.id,Permission.name,Permission.module).join(role_permissions,role_permissions.c.permission_id==Permission.id).where(role_permissions.c.role_id==role_identity).order_by(Permission.id),
        # Native own/team/department scope captures these exact identity links.
        # Detect a reassignment before reusing any compiled native predicate.
        select(Employee.id,Employee.user_id,Employee.branch_id,Employee.department_id,Employee.reporting_manager_id,Employee.deleted_at).where(
            or_(Employee.branch_id.in_(select(Branch.id).where(Branch.company_id==company)),Employee.branch_id.is_(None)&(company==1))).order_by(Employee.id),
    ]
    captured=[[list(row) for row in connection.execute(statement)] for statement in statements]
    if employee_before is not None:
        current={row[0]:row for row in captured[-1]}
        for identity,expected in (employee_expected or {}).items():
            actual=current.get(identity)
            before=employee_before.get(identity)
            if actual!=list(expected) and actual!=(list(before) if before is not None else None):
                deny('Canonical employee changed outside its validated write transition')
        for identity,before in employee_before.items():
            if before is None:current.pop(identity,None)
            else:current[identity]=list(before)
        captured[-1]=[current[key] for key in sorted(current)]
    native_user=list(user);native_user[3]=role_identity
    rows=[native_user,list(policy) if policy else None,*captured]
    enabled=Base.metadata.tables.get('bos_enabled_modules')
    if enabled is not None:
        rows.append([list(row) for row in connection.execute(select(enabled.c.id,enabled.c.company_id,enabled.c.module_key,enabled.c.enabled).where(enabled.c.company_id==company).order_by(enabled.c.id))])
    return sha256(json.dumps(rows,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def _native_operation_access(db,actor,company,operation):
    # Foreground company-admin inspection is an existing native read authority,
    # not the stricter worker/background grant. It never grants mutation rights.
    if operation.action=='view' and getattr(actor,'_suite_admin_read',False):
        if db.info.get('admin_read_company')!=company:
            deny('Native administrative read context changed; reload authorization')
        from app.models.user import User
        from app.branches.service import company_administrator
        current=db.connection().execute(select(User.is_active,User.is_superuser).where(User.id==actor.id)).first()
        if not current or not current.is_active or not (current.is_superuser or company_administrator(db,actor,company)):
            deny('Fresh native administrative read authority is required')
        return
    from app.access.service import check_background_access
    compiled_branch_role=getattr(actor,'_suite_branch_roles_fingerprint',None)
    # Native self-timesheet endpoints require timesheet_view for creation and
    # submission. The worker's broad "manage/create" name heuristic must not
    # introduce employee-management permission into that bounded self-service
    # contract. Explicit company/branch policies still govern the real action.
    from .leave_core import native_self_request
    from .leave_encashment_core import native_self_request as encashment_self_request
    from .request_context_core import native_self_request as context_self_request
    from .payroll_payslip import native_self_request as payslip_self_request
    from .hrms_home_core import native_self_request as home_self_request
    if operation.permission is None and (native_self_request(db, actor, company, operation) or encashment_self_request(db, actor, company, operation) or context_self_request(db, actor, company, operation) or payslip_self_request(db, actor, company, operation) or home_self_request(db,actor,company,operation)):
        # These exact native self-service endpoints require authenticated native
        # employment, not a legacy role-name/module permission. Explicit policies
        # and branch module grants continue to authorize their actual action.
        from app.access.service import policy_for
        from app.branches.roles import effective_grants
        branch = db.info.get('branch_context')
        selected = (branch.branch_id or 'all') if branch else db.info.get('background_branch')
        if policy_for(db, actor, company) is None and effective_grants(db, actor, company, selected, None) is None:
            from app.enterprise.controls import governance_module_check
            governance_module_check(db, actor, company, operation.module, operation.action)
            return
    legacy_self_time = False
    if (operation.purpose == 'hrms.actual_time' and operation.module == 'hrms'
            and operation.permission == 'timesheet_view' and operation.action in {'create', 'edit'}):
        from app.access.service import policy_for
        from app.branches.roles import effective_grants
        branch = db.info.get('branch_context')
        selected = (branch.branch_id or 'all') if branch else db.info.get('background_branch')
        legacy_self_time = (policy_for(db, actor, company) is None
            and effective_grants(db, actor, company, selected, None) is None)
    if legacy_self_time:
        from app.enterprise.controls import governance_module_check
        governance_module_check(db, actor, company, operation.module, operation.action)
        check_background_access(db, actor, operation.module, 'view')
    else:
        check_background_access(db,actor,operation.module,operation.action)
    if getattr(actor,'_suite_branch_roles_fingerprint',None)!=compiled_branch_role:
        deny('Native branch module authority changed; reload authorization')


def resolve_request(db,actor,request,branch_ctx,binding):
    """None means NOT this closed adapter; caller must keep its operation gate."""
    path=_canonical(request)
    operation=OPERATIONS.get((request.method,path))
    if operation is None:return None
    if (not isinstance(binding,CoreRequestBinding) or db.info.get(MARKER)!=binding
            or db.info.get('business_pack_scope') is not None
            or binding!=request_binding(actor,request)
            or not isinstance(branch_ctx,BranchContext) or branch_ctx.company_id!=binding.company_id
            or actor.id!=binding.user_id or actor.organization_id!=binding.company_id):
        deny('Common Core requires its real independent native request binding')
    from app.branches.service import context as native_branch_context
    selected=request.headers.get('X-Suite-Branch')
    if selected is None and getattr(actor,'_suite_admin_read',False):selected='all'
    if native_branch_context(db,actor,actor.organization_id,selected)!=branch_ctx:
        deny('Native branch authority changed before Common Core resolution')
    from app.access.catalog import permission_names
    _native_operation_access(db,actor,actor.organization_id,operation)
    native_directory=(operation.permission is None and (operation.purpose,request.method,path) in {
        ('hrms.employee_management','GET','/api/v1/employees/directory'),
        ('hrms.employee_references','GET','/api/v1/attendance/shifts'),
        ('hrms.employee_references','GET','/api/v1/employees/workbench/request-context')}) or (operation.purpose in {'hrms.leave','hrms.leave_encashment','hrms.payroll_payslip','hrms.home'} and operation.permission is None)
    required=(operation.permission,) if isinstance(operation.permission,str) else operation.permission or ()
    if not (native_directory or actor.is_superuser or getattr(actor,'_suite_admin_read',False) or set(required)&set(permission_names(actor))):
        deny('Native HRMS permission is required for this Common Core operation')
    return CommonCoreScope(actor.id,actor.organization_id,branch_ctx,binding,
        request.method,path,operation,_native_authority(db,actor,actor.organization_id))


def install(db,actor,scope):
    """Closed additive graph, no pack stamps and no native authorization bypass."""
    if (not isinstance(scope,CommonCoreScope) or not isinstance(scope.binding,CoreRequestBinding)
            or scope.operation!=OPERATIONS.get((scope.method,scope.route))
            or scope.binding.purpose!=scope.operation.purpose
            or (scope.binding.user_id,scope.binding.company_id,scope.binding.method,scope.binding.route)!=(scope.user_id,scope.company_id,scope.method,scope.route)
            or scope.user_id!=actor.id or scope.company_id!=actor.organization_id):
        deny('A verified immutable Common Core scope is required')
    if scope.operation.purpose=='hrms.home':
        from .hrms_home_core import install as install_home
        return install_home(db,actor,scope)
    if scope.operation.purpose=='crm.company_master':
        from .company_master_core import install as install_company_master
        return install_company_master(db,actor,scope)
    if scope.operation.purpose=='hrms.employee_management':
        from .employee_core import install as install_employee
        return install_employee(db,actor,scope)
    if scope.operation.purpose=='hrms.employee_references':
        if scope.route=='/api/v1/employees/workbench/request-context':
            from .request_context_core import install as install_context
            return install_context(db,actor,scope)
        from .employee_references import install as install_references
        return install_references(db,actor,scope)
    if scope.operation.purpose=='hrms.leave':
        from .leave_core import install as install_leave
        return install_leave(db,actor,scope)
    if scope.operation.purpose=='hrms.payroll_payslip':
        from .payroll_payslip import install as install_payslip
        return install_payslip(db,actor,scope)
    if scope.operation.purpose=='hrms.payroll_variance':
        from .payroll_variance import install as install_variance
        return install_variance(db,actor,scope)
    if scope.operation.purpose=='hrms.payroll_review':
        from .payroll_review import install as install_review
        return install_review(db,actor,scope)
    if scope.operation.purpose=='hrms.payroll_register':
        from .payroll_register import install as install_register
        return install_register(db,actor,scope)
    if scope.operation.purpose=='hrms.leave_encashment':
        from .leave_encashment_core import install as install_encashment
        return install_encashment(db,actor,scope)
    previous=db.info.get('business_common_core_scope')
    if previous is not None:
        if previous!=scope:deny('Common Core context cannot change inside a request')
        return lambda:None
    if db.info.get('business_pack_policy') is not None:deny('Common Core and private pack boundaries cannot be mixed')
    if db.new or db.deleted or any(db.is_modified(item,include_collections=True) for item in db.dirty):
        deny('Finish pending changes before binding Common Core')
    from app.models.employee import Employee
    from app.models.company import Branch,Company,Department,Designation
    from app.models.user import User,Role,Permission,role_permissions
    from app.models.timesheet import Project,Timesheet,TimesheetEntry
    records={Project,Timesheet,TimesheetEntry,Employee}
    reads=records|{Branch,Company,Department,Designation,User,Role,Permission}
    ownership=PackRecordOwnership.__table__
    inspector=inspect(db.connection())
    ownership_present=inspector.has_table(ownership.name)
    if ownership_present and not {'resource_table','resource_key','company_id','branch_id','context_id'}<={column['name'] for column in inspector.get_columns(ownership.name)}:
        raise HTTPException(503,'Native Core ownership exclusion installation is incomplete')
    def unowned(table):
        if not ownership_present:return true()
        return ~exists(select(1).where(ownership.c.resource_table==table.name,ownership.c.resource_key==key_expression(table))).correlate(table)
    employee_company=or_(Employee.branch_id.in_(select(Branch.id).where(Branch.company_id==scope.company_id)),Employee.branch_id.is_(None)&(scope.company_id==1))
    employee_ids=select(Employee.id).where(employee_company,unowned(Employee.__table__))
    # Native current project assignment must not rewrite visibility of actual
    # historical hours. Parent writes still use mapped Project authorization.
    project_table=Project.__table__
    project_ids=select(project_table.c.id).where(project_table.c.organization_id==scope.company_id,unowned(project_table))
    sheet_ids=select(Timesheet.id).where(Timesheet.employee_id.in_(employee_ids),Timesheet.project_id.in_(project_ids),unowned(Timesheet.__table__))
    conditions={Employee:and_(employee_company,unowned(Employee.__table__)),Project:and_(Project.organization_id==scope.company_id,unowned(Project.__table__)),
        Timesheet:and_(Timesheet.employee_id.in_(employee_ids),Timesheet.project_id.in_(project_ids),unowned(Timesheet.__table__)),
        TimesheetEntry:and_(TimesheetEntry.timesheet_id.in_(sheet_ids),unowned(TimesheetEntry.__table__)),
        User:User.id==scope.user_id,Company:Company.id==scope.company_id,Branch:Branch.company_id==scope.company_id,
        Department:Department.branch_id.in_(select(Branch.id).where(Branch.company_id==scope.company_id)),
        Designation:Designation.department_id.in_(select(Department.id).where(Department.branch_id.in_(select(Branch.id).where(Branch.company_id==scope.company_id)))),
    }
    options=tuple(with_loader_criteria(mapper.class_,conditions.get(mapper.class_,True if mapper.class_ in reads else false()),include_aliases=True,propagate_to_loaders=False) for mapper in Base.registry.mappers)
    checking=False
    def fresh():
        nonlocal checking
        if checking:return
        checking=True
        try:
            if (actor.id!=scope.user_id or actor.organization_id!=scope.company_id
                    or db.info.get('branch_context')!=scope.branch
                    or db.info.get('business_pack_scope') is not None
                    or db.info.get(MARKER)!=scope.binding):deny('Native Core request context changed during this operation')
            from app.branches.service import context as native_branch_context
            selected=str(scope.branch.branch_id) if scope.branch.branch_id is not None else 'all' if scope.branch.all_branches else None
            if native_branch_context(db,actor,scope.company_id,selected)!=scope.branch:
                deny('Native branch authority changed during Common Core operation')
            if _native_authority(db,actor,scope.company_id)!=scope.native_authority:deny('Native Common Core authority changed; reload before continuing')
            _native_operation_access(db,actor,scope.company_id,scope.operation)
        finally:checking=False
    fresh()
    def restrict(execution):
        if checking:return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            deny('Common Core uses validated native per-record ORM operations')
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in reads:
            deny('This table is outside the closed Common Core timesheet graph')
        from .common_queries import assert_mapped_sources
        assert_mapped_sources(execution.statement,reads,allowed_associations=(role_permissions,))
        for node in (() if execution.is_column_load or execution.is_relationship_load else visitors.iterate(execution.statement)):
            if isinstance(node,TextClause):deny('Common Core textual SQL requires a separate audited adapter')
            if isinstance(node,ColumnClause) and (getattr(node,'is_literal',False) or (getattr(node,'table',None) is not None and not (node._annotations.get('parententity') or node._annotations.get('parentmapper')))):
                deny('Common Core raw columns require a separate audited adapter')
        inherited={id(option) for option in getattr(execution.statement,'_with_options',())}
        execution.statement=execution.statement.options(*(option for option in options if id(option) not in inherited))
        execution.update_execution_options(compiled_cache=None)
    def validate(session,*args):
        fresh()
        for row in session.new|session.dirty|session.deleted:
            state=inspect(row);table=state.mapper.local_table
            if table.name not in scope.operation.writes or (row in session.new and table.name not in scope.operation.creates) or (row in session.deleted and table.name not in scope.operation.deletes):
                deny('This Common Core route cannot mutate that native record')
            if row in session.deleted and table.name=='projects' and db.connection().scalar(select(exists().where(Timesheet.project_id==row.id))):
                raise HTTPException(409,'Native projects with actual timesheets must be retained')
            values={key.name:getattr(row,key.name) for key in table.primary_key}
            if ownership_present and all(value is not None for value in values.values()) and db.connection().scalar(select(exists().where(ownership.c.resource_table==table.name,ownership.c.resource_key==resource_key(table,values)))):
                deny('Pack-private records cannot be adopted into Common Core')
            if row not in session.new:
                immutable={column.name for column in table.primary_key}|({'employee_id','project_id','timesheet_id','organization_id'}&set(table.c.keys()))
                if any(state.attrs[field].history.has_changes() for field in immutable):deny('Common Core native identity and parent links are immutable')
            with db.no_autoflush:
                for column in table.c:
                    value=getattr(row,column.name)
                    if value is None:continue
                    for fk in column.foreign_keys:
                        parent={mapper.local_table.name:mapper.class_ for mapper in Base.registry.mappers}.get(fk.column.table.name)
                        if parent not in reads:deny('Common Core cannot reference an unreviewed native graph')
                        if parent is User and column.name in {'created_by','reviewed_by'}:
                            if (row in session.new or state.attrs[column.name].history.has_changes()) and value!=scope.user_id:deny('Common Core authorship must match the native actor')
                            continue
                        attr=getattr(parent,inspect(parent).get_property_by_column(fk.column).key)
                        if not session.query(attr).filter(attr==value).first():deny('Common Core parent is outside native authorized scope')
    original_get,original_refresh=db.get,db.refresh
    def visible(model,identity):
        fresh()
        mapper=inspect(model,raiseerr=False)
        model=getattr(mapper,'class_',model)
        if model not in reads:return False
        keys=inspect(model).primary_key
        values=[identity.get(key.key) for key in keys] if isinstance(identity,dict) else list(identity) if isinstance(identity,(tuple,list)) else [identity]
        if len(values)!=len(keys):return False
        attrs=[getattr(model,inspect(model).get_property_by_column(key).key) for key in keys]
        with db.no_autoflush:
            return db.query(*attrs).filter(*(attr==value for attr,value in zip(attrs,values))).first() is not None
    def scoped_get(model,identity,**kwargs):
        return original_get(model,identity,**kwargs) if visible(model,identity) else None
    def scoped_refresh(row,*args,**kwargs):
        if not visible(type(row),inspect(row).identity):deny('Cached native record is outside Common Core authority')
        return original_refresh(row,*args,**kwargs)
    original_bulk={name:getattr(db,name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject_bulk(*args,**kwargs):deny('Common Core bulk writes require a separate audited adapter')
    for name in original_bulk:setattr(db,name,reject_bulk)
    for state in list(db.identity_map.all_states()):
        if state.class_ in records and state.obj() is not None:db.expire(state.obj())
    db.get,db.refresh=scoped_get,scoped_refresh
    db.info['business_common_core_scope']=scope
    event.listen(db,'do_orm_execute',restrict);event.listen(db,'before_flush',validate)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'do_orm_execute',restrict);event.remove(db,'before_flush',validate)
        db.get,db.refresh=original_get,original_refresh
        for name,method in original_bulk.items():setattr(db,name,method)
        db.info.pop('business_common_core_scope',None)
    return cleanup
