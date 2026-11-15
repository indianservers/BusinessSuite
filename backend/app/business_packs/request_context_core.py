"""Readonly canonical employee routing hints, not the HR workbench graph."""
from types import MappingProxyType
from weakref import WeakKeyDictionary
from fastapi import HTTPException
from sqlalchemy import and_,event,exists,false,inspect,select,String,cast
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause

PATH='/api/v1/employees/workbench/request-context'
PURPOSE='hrms.employee_references'
_CHECKS=WeakKeyDictionary()


def operations(operation):return candidate_operations(operation)


def candidate_operations(operation):return MappingProxyType({('GET',PATH):operation('view',None,purpose=PURPOSE)})


def native_self_request(db,actor,company,operation):
    from .common_binding import MARKER,CoreRequestBinding
    from .common_core import OPERATIONS
    binding=db.info.get(MARKER)
    return (isinstance(binding,CoreRequestBinding) and binding.purpose==PURPOSE
        and binding.user_id==actor.id and binding.company_id==company
        and (binding.method,binding.route)==('GET',PATH)
        and OPERATIONS.get(('GET',PATH)) is operation)


def install(db,actor,scope):
    from .common_core import deny,_native_authority,_native_operation_access
    from .common_binding import MARKER
    from .common_queries import assert_mapped_sources
    from .models import PackRecordOwnership
    from app.db.base_class import Base
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.models.user import User,Role,Permission,role_permissions
    from app.branches.models import BranchOwnership
    from app.branches.catalog import key_expression
    from app.branches.service import context as branch_context
    if (scope.method,scope.route,scope.operation.purpose)!=('GET',PATH,PURPOSE):deny('An exact native routing-hint request is required')
    previous=db.info.get('business_common_core_scope')
    if previous is not None:
        if previous!=scope:deny('Native routing hints cannot switch realms')
        return lambda:None
    if db.info.get('business_pack_policy') is not None or db.new or db.deleted or any(db.is_modified(row,include_collections=True) for row in db.dirty):
        deny('Native routing hints require a clean independent read request')
    owner=PackRecordOwnership.__table__;inspector=inspect(db.connection());present=inspector.has_table(owner.name)
    if present and not {'resource_table','resource_key','company_id','branch_id','context_id'}<={column['name'] for column in inspector.get_columns(owner.name)}:
        raise HTTPException(503,'Native routing-hint ownership exclusion is incomplete')
    def unowned(table):
        return ~exists(select(1).where(owner.c.resource_table==table.name,owner.c.resource_key==key_expression(table))).correlate(table) if present else ~false()
    native=BranchOwnership.__table__
    # Existing native tenant/branch/Own/Team predicates still narrow this proof.
    employees=exists(select(1).where(native.c.resource_table=='employees',
        native.c.resource_key==cast(Employee.id,String),native.c.company_id==scope.company_id,
        native.c.branch_id.in_(scope.branch.allowed),
        native.c.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id==scope.company_id)))).correlate(Employee.__table__)
    conditions={Employee:and_(employees,Employee.deleted_at.is_(None),unowned(Employee.__table__)),
        User:User.id==actor.id,Role:Role.id==actor.role_id,
        Permission:Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id==actor.role_id))}
    reads=set(conditions)
    options=tuple(with_loader_criteria(mapper.class_,conditions.get(mapper.class_,false()),include_aliases=True,
        propagate_to_loaders=False) for mapper in Base.registry.mappers if mapper.class_ is not Branch)
    # Native Employee visibility embeds a Branch-company subquery. Do not poison
    # that predicate with an unrelated false loader; Branch is still NOT in reads,
    # so direct mapped reads/get/refresh are rejected by the statement inventory.
    checking=False;identity_load=False
    def fresh():
        nonlocal checking
        if checking:return
        checking=True
        try:
            if (actor.id!=scope.user_id or actor.organization_id!=scope.company_id or db.info.get(MARKER)!=scope.binding
                    or db.info.get('business_pack_scope') is not None or db.info.get('branch_context')!=scope.branch):deny('Native routing authority changed')
            selected=str(scope.branch.branch_id) if scope.branch.branch_id is not None else 'all' if scope.branch.all_branches else None
            if branch_context(db,actor,scope.company_id,selected)!=scope.branch:deny('Native routing branch authority changed')
            if _native_authority(db,actor,scope.company_id)!=scope.native_authority:deny('Native routing permissions changed')
            _native_operation_access(db,actor,scope.company_id,scope.operation)
        finally:checking=False
    def restrict(execution):
        if checking:return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            deny('Native routing hints are mapped readonly projections')
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in reads:deny('This model is outside native routing hints')
        assert_mapped_sources(execution.statement,reads,trusted_identity=identity_load,allowed_associations=(role_permissions,))
        if not identity_load and not execution.is_column_load and not execution.is_relationship_load:
            for node in visitors.iterate(execution.statement):
                if isinstance(node,TextClause) or isinstance(node,ColumnClause) and (getattr(node,'is_literal',False) or
                        getattr(node,'table',None) is not None and not(node._annotations.get('parententity') or node._annotations.get('parentmapper'))):
                    deny('Native routing hints cannot run arbitrary SQL')
        inherited={id(option) for option in getattr(execution.statement,'_with_options',())}
        execution.statement=execution.statement.options(*(option for option in options if id(option) not in inherited))
        execution.update_execution_options(compiled_cache=None)
    def validate(session,*args):
        fresh()
        if session.new or session.deleted or any(session.is_modified(row,include_collections=True) for row in session.dirty):
            deny('Routing hints cannot mutate employment or business records')
    original_get,original_refresh=db.get,db.refresh
    def visible(model,identity):
        fresh();mapper=inspect(model,raiseerr=False);model=getattr(mapper,'class_',model)
        if model not in reads:return False
        keys=inspect(model).primary_key
        values=[identity.get(key.key) for key in keys] if isinstance(identity,dict) else list(identity) if isinstance(identity,(tuple,list)) else [identity]
        if len(keys)!=len(values):return False
        attributes=[getattr(model,inspect(model).get_property_by_column(key).key) for key in keys]
        with db.no_autoflush:return db.query(*attributes).filter(*(key==value for key,value in zip(attributes,values))).first() is not None
    def scoped_get(model,identity,**kwargs):
        nonlocal identity_load
        if not visible(model,identity):return None
        previous=identity_load;identity_load=True
        try:return original_get(model,identity,**kwargs)
        finally:identity_load=previous
    def scoped_refresh(row,*args,**kwargs):
        nonlocal identity_load
        if not visible(type(row),inspect(row).identity):deny('Cached identity is outside native routing authority')
        previous=identity_load;identity_load=True
        try:return original_refresh(row,*args,**kwargs)
        finally:identity_load=previous
    bulk={name:getattr(db,name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject(*args,**kwargs):deny('Native routing hints cannot perform bulk writes')
    fresh()
    for name in bulk:setattr(db,name,reject)
    for state in list(db.identity_map.all_states()):
        if state.obj() is not None and state.class_ not in {User,Role,Permission}:db.expire(state.obj())
    db.get,db.refresh=scoped_get,scoped_refresh;db.info['business_common_core_scope']=scope;_CHECKS[db]=(fresh,present)
    event.listen(db,'do_orm_execute',restrict);event.listen(db,'before_flush',validate)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'do_orm_execute',restrict);event.remove(db,'before_flush',validate)
        db.get,db.refresh=original_get,original_refresh
        for name,method in bulk.items():setattr(db,name,method)
        db.info.pop('business_common_core_scope',None);_CHECKS.pop(db,None)
    return cleanup


def project(db,actor,employee_id,kind):
    """Exact existing DTO, using only visible canonical employee parent names."""
    from .common_core import CommonCoreScope
    from .models import PackRecordOwnership
    from app.models.employee import Employee
    from app.models.company import Department,Branch
    from app.core.masking import user_has_permission
    scope=db.info.get('business_common_core_scope')
    if not isinstance(scope,CommonCoreScope) or (scope.method,scope.route,scope.operation.purpose)!=('GET',PATH,PURPOSE):return None
    proof=_CHECKS.get(db)
    if proof is None:raise HTTPException(403,'A verified native routing projection is required')
    check,present=proof;check()
    own=db.query(Employee.id).filter(Employee.user_id==actor.id).first()
    own=own.id if own else None
    if employee_id is None and own is None:raise HTTPException(400,'Link an employee profile before submitting a request')
    query=db.query(Employee.id,Employee.first_name,Employee.last_name,Employee.department_id,Employee.branch_id,Employee.reporting_manager_id)
    if not user_has_permission(actor,'employee_view'):
        from sqlalchemy import or_
        query=query.filter(or_(Employee.id==(own or 0),Employee.reporting_manager_id==(own or 0)))
    person=query.filter(Employee.id==(employee_id or own)).first()
    if person is None:raise HTTPException(404,'Employee not found in your permitted scope')
    manager=db.query(Employee.first_name,Employee.last_name).filter(Employee.id==person.reporting_manager_id).first() if person.reporting_manager_id else None
    manager_name=' '.join(part for part in manager if part).strip() if manager else None
    owner=PackRecordOwnership.__table__
    def parent_name(model,identity):
        if identity is None:return None
        if model is Branch:query=select(Branch.name).where(Branch.id==identity,Branch.company_id==scope.company_id)
        elif model is Department:query=select(Department.name).join(Branch,Branch.id==Department.branch_id).where(Department.id==identity,Branch.company_id==scope.company_id)
        else:raise HTTPException(403,'Unknown native routing parent')
        if present:query=query.where(~exists(select(1).where(owner.c.resource_table==model.__tablename__,owner.c.resource_key==str(identity))))
        return db.connection().scalar(query)
    department=parent_name(Department,person.department_id);branch=parent_name(Branch,person.branch_id)
    check()
    return {'employee_id':person.id,'employee_name':f'{person.first_name} {person.last_name}'.strip(),
        'department':department,'branch':branch,'manager_name':manager_name,
        'approval_path':([manager_name or 'Authorized HR reviewer','Finance review'] if kind=='expense' else [manager_name or 'Authorized HR reviewer']),
        'routing_note':('Manager review, followed by finance review. Authorized HR reviewers may review within their scope.' if kind=='expense'
            else 'Your reporting manager is notified when linked to an account. A reviewer with leave approval permission decides the request.'),
        'initial_status':'submitted' if kind=='expense' else 'Pending'}
