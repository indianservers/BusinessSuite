"""Unpublished readonly HR home counts and masked canonical summaries."""
from types import MappingProxyType
from weakref import WeakKeyDictionary
from fastapi import HTTPException
from sqlalchemy import and_,event,exists,false,inspect,select,String,cast
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause

PATH='/api/v1/employees/workbench/home'
PURPOSE='hrms.home'
_CHECKS=WeakKeyDictionary()
_READERS=WeakKeyDictionary()
_PREDICATES=WeakKeyDictionary()


def operations(operation):return MappingProxyType({})


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
    reads={User,Role,Permission}
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


def project(db,actor,requested_scope):
    """Run only the fixed native home computation in a closed readonly session."""
    from contextlib import ExitStack
    from sqlalchemy.orm import object_session,load_only
    from sqlalchemy.sql.elements import BindParameter
    from .common_core import CommonCoreScope
    from .common_binding import MARKER
    from .common_queries import assert_mapped_sources
    from .payroll_review import _Reader,_actor
    from .models import PackRecordOwnership
    from app.models.user import User
    from app.models.employee import Employee
    from app.models.company import Company,Branch,Department
    from app.models.leave import LeaveRequest
    from app.models.attendance import Attendance,AttendanceRegularization
    from app.models.expense import ExpenseClaim
    from app.models.timesheet import Timesheet
    from app.models.exit import ExitRecord
    from app.models.helpdesk import HelpdeskTicket
    from app.branches.models import BranchOwnership
    from app.branches.catalog import key_expression
    scope=db.info.get('business_common_core_scope')
    if not isinstance(scope,CommonCoreScope):return None
    if (scope.method,scope.route,scope.operation.purpose)!=('GET',PATH,PURPOSE):
        raise HTTPException(403,'Actual native HR home request required')
    proof=_CHECKS.get(db)
    if (proof is None or type(actor) is not User or object_session(actor) is not db or not inspect(actor).persistent
            or scope.user_id!=actor.id or db.info.get(MARKER)!=scope.binding):
        raise HTTPException(403,'Actual native HR home actor and guard required')
    check,present=proof;check()
    thin={Employee:('id','user_id','employee_id','first_name','last_name','status','date_of_joining','department_id',
        'branch_id','reporting_manager_id','work_email','personal_email','phone_number','deleted_at'),
        Branch:('id','company_id','name'),Department:('id','branch_id','organization_id','name'),
        Company:('id','name','default_timezone'),ExitRecord:('id','employee_id','status','last_working_date')}
    scalars={LeaveRequest:('id','employee_id','status','deleted_at'),AttendanceRegularization:('id','employee_id','status'),
        ExpenseClaim:('id','employee_id','status'),Timesheet:('id','employee_id','status'),HelpdeskTicket:('id','employee_id','status'),
        Attendance:('id','employee_id','attendance_date','check_in','check_out')}
    reads=set(thin)|set(scalars);view=_actor(db,actor,scope.company_id,present)
    connection=db.connection();transaction=connection.get_transaction();nested=connection.get_nested_transaction()
    reader=_Reader(bind=connection,autoflush=False,expire_on_commit=False,join_transaction_mode='rollback_only',close_resets_only=False)
    reader.info[MARKER]=scope.binding;reader.info['business_pack_scope']=None;reader.info['security_write_request']=False
    private=PackRecordOwnership.__table__;native=BranchOwnership.__table__;branches=Branch.__table__
    def unowned(table):return ~exists(select(1).where(private.c.resource_table==table.name,
        private.c.resource_key==key_expression(table))).correlate(table) if present else ~false()
    def owned(table):
        from sqlalchemy import or_
        anchor=and_(native.c.resource_table==table.name,native.c.resource_key==key_expression(table),
            native.c.company_id==scope.company_id,native.c.branch_id.in_(scope.branch.allowed),
            native.c.branch_id.in_(select(branches.c.id).where(branches.c.company_id==scope.company_id)))
        if 'branch_id' in table.c:anchor=and_(anchor,or_(table.c.branch_id.is_(None),table.c.branch_id==native.c.branch_id))
        if 'company_id' in table.c:anchor=and_(anchor,or_(table.c.company_id.is_(None),table.c.company_id==scope.company_id))
        if 'organization_id' in table.c:anchor=and_(anchor,or_(table.c.organization_id.is_(None),table.c.organization_id==scope.company_id))
        return and_(exists(select(1).where(anchor)).correlate(table),unowned(table))
    conditions={}
    for model in reads:
        table=model.__table__
        if model is Company:criterion=and_(Company.id==scope.company_id,unowned(table))
        elif model is Branch:criterion=and_(Branch.company_id==scope.company_id,Branch.id.in_(scope.branch.allowed),unowned(table))
        else:criterion=owned(table)
        if model in scalars or model is ExitRecord:
            criterion=and_(criterion,table.c.employee_id.in_(select(Employee.__table__.c.id).where(owned(Employee.__table__))))
        conditions[model]=criterion
    options=tuple(with_loader_criteria(model,criterion,include_aliases=True,propagate_to_loaders=False) for model,criterion in conditions.items())
    def entity_model(expression):
        mapper=inspect(expression,raiseerr=False)
        return getattr(mapper,'class_',None) if mapper is not None and (getattr(mapper,'is_mapper',False) or getattr(mapper,'is_aliased_class',False)) else None
    def restrict(execution):
        check()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            raise HTTPException(403,'Native HR home accepts only fixed mapped readonly computations')
        from sqlalchemy import true
        from sqlalchemy.orm.util import LoaderCriteriaOption
        validation=visitors.replacement_traverse(execution.statement,{},lambda node:
            node if isinstance(node,LoaderCriteriaOption) else true() if _verified_predicate(reader,scope,node) else None)
        assert_mapped_sources(validation,reads)
        _literal_projection_guard(validation)
        added=list(options)
        for item in getattr(execution.statement,'column_descriptions',()):
            model=entity_model(item.get('expr'))
            if model in scalars:raise HTTPException(403,'HR home counts cannot load request bodies')
            if model in thin:added.append(load_only(*(getattr(item['entity'],key) for key in thin[model]),raiseload=True))
        for node in visitors.iterate(validation):
            if isinstance(node,TextClause):raise HTTPException(403,'Native HR home cannot execute raw SQL')
            if isinstance(node,ColumnClause):
                annotations=getattr(node,'_annotations',{});mapper=annotations.get('parentmapper') or annotations.get('parententity')
                model=getattr(mapper,'class_',None)
                if model is not None and node.key not in (thin.get(model) or scalars.get(model) or ()):
                    raise HTTPException(403,'Native HR home cannot read private fields')

        execution.statement=execution.statement.options(*added)
        execution.update_execution_options(compiled_cache=None)
    try:
        with ExitStack() as stack:
            from app.core.tenant_boundary import install as tenant_install
            from app.branches.boundary import install as branch_install
            from app.access.scope import install_scope
            stack.callback(tenant_install(reader,view,scope.company_id,enforce_superuser_company=True))
            stack.callback(branch_install(reader,view,scope.branch))
            if view._suite_grants is not None:stack.callback(install_scope(reader,view,scope.company_id,view._suite_grants))
            event.listen(reader,'do_orm_execute',restrict);stack.callback(lambda:event.remove(reader,'do_orm_execute',restrict))
            _READERS[reader]=(scope,view,check)
            stack.callback(lambda:_READERS.pop(reader,None))
            from app.api.v1.hr_workbench import native_home
            result=native_home(requested_scope,reader,view)
            if reader.new or reader.deleted or any(reader.is_modified(row,include_collections=True) for row in reader.dirty):
                raise HTTPException(403,'Native HR home cannot change source records')
            check();return result
    finally:
        reader.close()
        if connection.get_transaction() is not transaction or connection.get_nested_transaction() is not nested:
            raise HTTPException(503,'Native HR home must retain its native transaction')

def certify_employee_query(db,actor,query):
    """Certify only native employee_records' unchanged tenancy EXISTS atoms.

    The presence of a CommonPerson is an ownership predicate, never permission
    to fetch that person's identity, profile or body. Other uses stay denied.
    """
    lease=_READERS.get(db)
    if lease is None:return query
    scope,actual,check=lease;check()
    if actual is not actor or scope.operation.purpose!=PURPOSE:
        raise HTTPException(403,'Actual native HR home employee predicate required')
    from app.common.models import CommonPerson
    from app.models.employee import Employee
    from sqlalchemy.sql.selectable import Exists
    from .catalog_predicate import _fingerprint
    expected=(exists(select(CommonPerson.id).where(CommonPerson.user_id==Employee.user_id,
        CommonPerson.organization_id==scope.company_id)),exists(select(CommonPerson.id).where(CommonPerson.user_id==Employee.user_id)))
    for clause in query._where_criteria:
        for node in visitors.iterate(clause):
            if isinstance(node,Exists) and any(_native_predicate_shape(node,db)==_native_predicate_shape(atom,db) for atom in expected):
                _PREDICATES[node]=(db,scope,_fingerprint(node,db.get_bind().dialect))
    return query


def _verified_predicate(db,scope,node):
    from sqlalchemy.sql.selectable import Exists
    if not isinstance(node,Exists):return False
    lease=_READERS.get(db);entry=_PREDICATES.get(node)
    if lease is None or entry is None or lease[0] is not scope:return False
    actual,verified,fingerprint=entry
    if actual is not db or verified is not scope:return False
    from .catalog_predicate import _fingerprint
    return fingerprint==_fingerprint(node,db.get_bind().dialect)


def _native_predicate_shape(node,db):
    from .catalog_predicate import _fingerprint
    # SQL plus exact values and mapper/table identities: a raw/name-adapted alias
    # cannot certify an ORM tenant predicate merely by copying its caption.
    columns=tuple((item.key,id(getattr(item,'table',None)),id(item._annotations.get('parentmapper')),
        id(item._annotations.get('parententity'))) for item in visitors.iterate(node)
        if isinstance(item,ColumnClause))
    return _fingerprint(node,db.get_bind().dialect)[:2],columns


def _literal_projection_guard(statement):
    from sqlalchemy.sql.functions import count
    def visit(node):
        # Only the exact count(*) argument occurrence is exempt. Reusing that
        # same star anywhere outside this function still follows the deny path.
        if isinstance(node,count):
            args=tuple(node.clauses)
            if len(args)==1 and isinstance(args[0],ColumnClause) and args[0].is_literal and args[0].name=='*':return
        if isinstance(node,ColumnClause) and getattr(node,'is_literal',False):
            raise HTTPException(403,'Native HR home cannot execute literal projections')
        for child in node.get_children():visit(child)
    visit(statement)
