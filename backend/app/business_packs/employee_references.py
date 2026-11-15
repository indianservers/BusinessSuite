"""Single native shift-definition picker; no attendance or employment records."""
from types import MappingProxyType
from fastapi import HTTPException
from sqlalchemy import and_,event,exists,false,inspect,select,true
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause

PURPOSE='hrms.employee_references'
PATH='/api/v1/attendance/shifts'


def operations(operation):return candidate_operations(operation)


def candidate_operations(operation):
    return MappingProxyType({('GET',PATH):operation('view',None,purpose=PURPOSE)})


def native_predicate(db,actor,company,model):
    from .common_binding import CoreRequestBinding,MARKER
    from .common_core import OPERATIONS
    from app.models.attendance import Shift
    if model is not Shift:return None
    binding=db.info.get(MARKER)
    if (not isinstance(binding,CoreRequestBinding) or binding.user_id!=actor.id or binding.company_id!=company
            or db.info.get('business_pack_scope') is not None):return None
    operation=OPERATIONS.get((binding.method,binding.route))
    if operation is None or operation.purpose!=binding.purpose:return None
    if binding.purpose==PURPOSE:
        if (binding.method,binding.route)!=('GET',PATH):return None
    elif binding.purpose=='hrms.employee_management':
        if (binding.method,binding.route) not in {('POST','/api/v1/employees/'),('PUT','/api/v1/employees/{employee_id}')}:
            return None
    else:return None
    from app.models.security_boundary import SecurityResourceOwnership
    owner=SecurityResourceOwnership.__table__
    return Shift.id.in_(select(owner.c.resource_id).where(owner.c.resource_table==Shift.__tablename__,owner.c.company_id==company))


def install(db,actor,scope):
    from .common_core import deny,_native_authority,_native_operation_access
    from .common_binding import MARKER
    from .models import PackRecordOwnership
    from app.db.base_class import Base
    from app.models.attendance import Shift
    from app.models.company import Company,Branch
    from app.models.user import User,Role,Permission,role_permissions
    from app.branches.catalog import key_expression
    from app.branches.service import context as branch_context
    if (scope.method,scope.route)!=('GET',PATH) or scope.binding.purpose!=PURPOSE:
        deny('Only the registered native shift definition read is supported')
    if db.info.get('business_pack_policy') is not None:deny('Native definitions cannot mix with private operational authority')
    previous=db.info.get('business_common_core_scope')
    if previous is not None:
        if previous!=scope:deny('Native reference purpose cannot change within a request')
        return lambda:None
    if db.new or db.deleted or any(db.is_modified(row,include_collections=True) for row in db.dirty):deny('Finish pending changes before binding native definitions')
    owner=PackRecordOwnership.__table__;inspector=inspect(db.connection());present=inspector.has_table(owner.name)
    if present and not {'resource_table','resource_key','company_id','branch_id','context_id'}<={column['name'] for column in inspector.get_columns(owner.name)}:
        raise HTTPException(503,'Native Core ownership exclusion installation is incomplete')
    def unowned(table):return ~exists(select(1).where(owner.c.resource_table==table.name,owner.c.resource_key==key_expression(table))).correlate(table) if present else true()
    from app.models.security_boundary import SecurityResourceOwnership
    native=SecurityResourceOwnership.__table__
    from app.access.catalog import permission_objects
    # Managed company/branch grants can contain native name/module projections
    # rather than mapped Permission instances. Resolve only their existing
    # canonical IDs; never treat a synthetic object as a permission-row grant.
    permission_names={item.name for item in permission_objects(actor)}
    permissions=list(db.connection().scalars(select(Permission.__table__.c.id).where(
        Permission.__table__.c.name.in_(permission_names))))
    permissions.extend(db.connection().scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id==actor.role_id)))
    conditions={Shift:Shift.id.in_(select(native.c.resource_id).where(native.c.resource_table=='shifts',native.c.company_id==scope.company_id)),
        Company:Company.id==scope.company_id,Branch:Branch.company_id==scope.company_id,
        User:User.id==actor.id,Role:Role.id==actor.role_id,Permission:Permission.id.in_(permissions)}
    conditions={model:and_(condition,unowned(model.__table__)) for model,condition in conditions.items()}
    reads=set(conditions)
    options=tuple(with_loader_criteria(mapper.class_,conditions.get(mapper.class_,false()),include_aliases=True,propagate_to_loaders=False) for mapper in Base.registry.mappers)
    checking=False;identity_load=False
    def fresh():
        nonlocal checking
        if checking:return
        checking=True
        try:
            if (actor.id!=scope.user_id or actor.organization_id!=scope.company_id or db.info.get(MARKER)!=scope.binding
                    or db.info.get('business_pack_scope') is not None or db.info.get('branch_context')!=scope.branch):deny('Native reference authority changed')
            branch=str(scope.branch.branch_id) if scope.branch.branch_id is not None else 'all' if scope.branch.all_branches else None
            if branch_context(db,actor,scope.company_id,branch)!=scope.branch:deny('Native reference branch access changed')
            if _native_authority(db,actor,scope.company_id)!=scope.native_authority:deny('Native reference permissions changed')
            _native_operation_access(db,actor,scope.company_id,scope.operation)
        finally:checking=False
    def restrict(execution):
        if checking:return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:deny('Native references allow only validated mapped definition reads')
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in reads:deny('This is outside the minimal native shift definition graph')
        from .common_queries import assert_mapped_sources
        assert_mapped_sources(execution.statement,reads,trusted_identity=identity_load,allowed_associations=(role_permissions,))
        if not identity_load and not execution.is_column_load and not execution.is_relationship_load:
            for node in visitors.iterate(execution.statement):
                if isinstance(node,TextClause) or (isinstance(node,ColumnClause) and (getattr(node,'is_literal',False)
                        or (getattr(node,'table',None) is not None and not (node._annotations.get('parententity') or node._annotations.get('parentmapper'))))):
                    deny('Native reference raw SQL requires its own audited adapter')
        inherited={id(option) for option in getattr(execution.statement,'_with_options',())}
        execution.statement=execution.statement.options(*(option for option in options if id(option) not in inherited))
        execution.update_execution_options(compiled_cache=None)
    def validate(session,*args):
        fresh()
        if session.new or session.deleted or any(session.is_modified(row,include_collections=True) for row in session.dirty):deny('The shift picker cannot write native records')
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
        if not visible(type(row),inspect(row).identity):deny('Cached reference is outside native company and branch')
        previous=identity_load;identity_load=True
        try:return original_refresh(row,*args,**kwargs)
        finally:identity_load=previous
    bulk={name:getattr(db,name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject(*args,**kwargs):deny('The shift picker cannot perform bulk writes')
    fresh()
    for name in bulk:setattr(db,name,reject)
    for state in list(db.identity_map.all_states()):
        if state.class_ is Shift and state.obj() is not None:db.expire(state.obj())
    db.get,db.refresh=scoped_get,scoped_refresh;db.info['business_common_core_scope']=scope
    event.listen(db,'do_orm_execute',restrict);event.listen(db,'before_flush',validate)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'do_orm_execute',restrict);event.remove(db,'before_flush',validate)
        db.get,db.refresh=original_get,original_refresh
        for name,method in bulk.items():setattr(db,name,method)
        db.info.pop('business_common_core_scope',None)
    return cleanup
