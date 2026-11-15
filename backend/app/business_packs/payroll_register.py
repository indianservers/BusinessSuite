"""Readonly native payroll register; salary/bank bodies are not this purpose."""
from types import MappingProxyType
from weakref import WeakKeyDictionary
from fastapi import HTTPException
from sqlalchemy import and_,event,exists,false,inspect,select,String,cast
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause

PURPOSE='hrms.payroll_register'
ROUTES=frozenset({
    '/api/v1/payroll/runs','/api/v1/payroll/last-run','/api/v1/payroll/runs/{run_id}',
    '/api/v1/payroll/setup/pay-groups','/api/v1/payroll/setup/periods',
    '/api/v1/reports/payroll-summary','/api/v1/payroll/inputs/leave-encashment-lines'})
_CHECKS=WeakKeyDictionary()
_COUNTS=WeakKeyDictionary()


def operations(operation):return candidate_operations(operation)


def candidate_operations(operation):
    return MappingProxyType({('GET',path):operation('view','payroll_view',purpose=PURPOSE) for path in ROUTES})


def install(db,actor,scope):
    from .common_core import deny,_native_authority,_native_operation_access
    from .common_binding import MARKER
    from .common_queries import assert_mapped_sources
    from .models import PackRecordOwnership
    from app.db.base_class import Base
    from app.models.employee import Employee
    from app.models.company import Branch,Department
    from app.models.payroll import PayrollRun,PayrollPeriod,PayrollPayGroup,PayrollRecord,LeaveEncashmentLine,PayrollVarianceItem,PayrollDeliveryProfile
    from app.models.user import User,Role,Permission,role_permissions
    from app.branches.models import BranchOwnership
    from app.branches.catalog import key_expression
    from app.branches.service import context as branch_context
    if scope.method!='GET' or scope.route not in (ROUTES if scope.operation.purpose==PURPOSE else {'/api/v1/payroll/runs/{run_id}/guided'} if scope.operation.purpose=='hrms.payroll_review' else {'/api/v1/payroll/runs/{run_id}/variance'} if scope.operation.purpose=='hrms.payroll_variance' else {'/api/v1/payroll/payslip'} if scope.operation.purpose=='hrms.payroll_payslip' else set()):deny('An exact native payroll register-hint request is required')
    previous=db.info.get('business_common_core_scope')
    if previous is not None:
        if previous!=scope:deny('Native payroll register hints cannot switch realms')
        return lambda:None
    if db.info.get('business_pack_policy') is not None or db.new or db.deleted or any(db.is_modified(row,include_collections=True) for row in db.dirty):
        deny('Native payroll register hints require a clean independent read request')
    owner=PackRecordOwnership.__table__;inspector=inspect(db.connection());present=inspector.has_table(owner.name)
    if present and not {'resource_table','resource_key','company_id','branch_id','context_id'}<={column['name'] for column in inspector.get_columns(owner.name)}:
        raise HTTPException(503,'Native payroll register-hint ownership exclusion is incomplete')
    def unowned(table):
        return ~exists(select(1).where(owner.c.resource_table==table.name,owner.c.resource_key==key_expression(table))).correlate(table) if present else ~false()
    native=BranchOwnership.__table__
    branches=Branch.__table__
    def owned(table):
        proof=and_(native.c.resource_table==table.name,native.c.resource_key==key_expression(table),
            native.c.company_id==scope.company_id,native.c.branch_id.in_(scope.branch.allowed),
            native.c.branch_id.in_(select(branches.c.id).where(branches.c.company_id==scope.company_id)))
        if 'branch_id' in table.c:
            from sqlalchemy import or_
            proof=and_(proof,or_(table.c.branch_id.is_(None),table.c.branch_id==native.c.branch_id))
        if 'company_id' in table.c:
            from sqlalchemy import or_
            proof=and_(proof,or_(table.c.company_id.is_(None),table.c.company_id==scope.company_id))
        return and_(exists(select(1).where(proof)).correlate(table),unowned(table))
    runs,people,periods=PayrollRun.__table__,Employee.__table__,PayrollPeriod.__table__
    conditions={PayrollRun:owned(runs),PayrollPayGroup:owned(PayrollPayGroup.__table__),
        PayrollPeriod:owned(periods),
        PayrollRecord:and_(owned(PayrollRecord.__table__),
            PayrollRecord.payroll_run_id.in_(select(runs.c.id).where(owned(runs))),
            PayrollRecord.employee_id.in_(select(people.c.id).where(owned(people),people.c.deleted_at.is_(None)))),
        User:User.id==actor.id,Role:Role.id==actor.role_id,
        Permission:Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id==actor.role_id))}
    if scope.route=='/api/v1/payroll/inputs/leave-encashment-lines':
        conditions[LeaveEncashmentLine]=and_(owned(LeaveEncashmentLine.__table__),
            LeaveEncashmentLine.employee_id.in_(select(people.c.id).where(owned(people),people.c.deleted_at.is_(None))),
            LeaveEncashmentLine.period_id.in_(select(periods.c.id).where(owned(periods))))
    if scope.operation.purpose=='hrms.payroll_variance':
        conditions[PayrollVarianceItem]=and_(owned(PayrollVarianceItem.__table__),
            PayrollVarianceItem.payroll_run_id.in_(select(runs.c.id).where(owned(runs))),
            PayrollVarianceItem.employee_id.in_(select(people.c.id).where(owned(people),people.c.deleted_at.is_(None))))
    if scope.operation.purpose=='hrms.payroll_payslip':
        conditions[PayrollDeliveryProfile]=and_(PayrollDeliveryProfile.company_id==scope.company_id,unowned(PayrollDeliveryProfile.__table__))
    reads=set(conditions)
    # Native permission predicates use these canonical parents internally. They
    # remain forbidden as direct sources, not false-poisoned inside native scope.
    options=tuple(with_loader_criteria(mapper.class_,conditions.get(mapper.class_,false()),include_aliases=True,
        propagate_to_loaders=False) for mapper in Base.registry.mappers if mapper.class_ not in {Branch,Department,Employee})
    checking=False;identity_load=False
    def fresh():
        nonlocal checking
        if checking:return
        checking=True
        try:
            if (actor.id!=scope.user_id or actor.organization_id!=scope.company_id or db.info.get(MARKER)!=scope.binding
                    or db.info.get('business_pack_scope') is not None or db.info.get('branch_context')!=scope.branch):deny('Native payroll register authority changed')
            selected=str(scope.branch.branch_id) if scope.branch.branch_id is not None else 'all' if scope.branch.all_branches else None
            if branch_context(db,actor,scope.company_id,selected)!=scope.branch:deny('Native payroll register branch authority changed')
            if _native_authority(db,actor,scope.company_id)!=scope.native_authority:deny('Native payroll register permissions changed')
            _native_operation_access(db,actor,scope.company_id,scope.operation)
        finally:checking=False
    def record_projection(statement,relationship_load):
        record_source=any(getattr(node._annotations.get('parentmapper') or node._annotations.get('parententity'),'class_',None) is PayrollRecord for node in visitors.iterate(statement))
        if record_source:
            from sqlalchemy.sql.functions import FunctionElement
            from sqlalchemy.sql.elements import BinaryExpression,BindParameter
            from sqlalchemy.sql import operators
            identity=_COUNTS.get(db)
            descriptions=getattr(statement,'column_descriptions',())
            expression=descriptions[0].get('expr') if len(descriptions)==1 else None
            arguments=list(expression.clauses) if isinstance(expression,FunctionElement) else []
            if (identity is None or not isinstance(expression,FunctionElement) or expression.name!='count'
                    or len(arguments)!=1 or not arguments[0].shares_lineage(PayrollRecord.__table__.c.id)):
                deny('Payroll record identities are internal count-only projections')
            exact_parent=any(isinstance(node,BinaryExpression) and node.operator is operators.eq
                and getattr(node.left,'shares_lineage',lambda other:False)(PayrollRecord.__table__.c.payroll_run_id)
                and isinstance(node.right,BindParameter) and node.right.value==identity
                for node in visitors.iterate(statement))
            if not exact_parent:deny('Payroll count requires its actual authorized run')
        if relationship_load:
            for item in getattr(statement,'column_descriptions',()):
                if getattr(item.get('entity'),'__mapper__',None) is inspect(PayrollRecord):
                    deny('Payroll register cannot load salary record bodies')
        for item in getattr(statement,'column_descriptions',()):
            expression=inspect(item.get('expr'),raiseerr=False)
            if expression is not None and (getattr(expression,'is_mapper',False) or getattr(expression,'is_aliased_class',False)):
                if getattr(expression,'class_',None) is PayrollRecord:
                    deny('Payroll register cannot load salary record entities')
        for option in getattr(statement,'_with_options',()):
            for part in getattr(getattr(option,'path',None),'path',()):
                if getattr(getattr(part,'mapper',part),'class_',None) is PayrollRecord:
                    deny('Payroll register cannot eager load salary records')
        for node in visitors.iterate(statement):
            mapper=node._annotations.get('parentmapper') or node._annotations.get('parententity')
            if getattr(mapper,'class_',None) is PayrollRecord and getattr(node,'table',None) is not None:
                if getattr(node,'key',None) not in {'id','payroll_run_id','employee_id'}:
                    deny('Payroll register allows only record identity counts')
    def restrict(execution):
        if checking:return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            deny('Native payroll register hints are mapped readonly projections')
        employee_certificate=False
        payslip_certificate=False
        if scope.operation.purpose=='hrms.payroll_payslip' and execution.bind_mapper is not None and execution.bind_mapper.class_ in {Employee,PayrollRun,PayrollRecord,PayrollDeliveryProfile}:
            from .payroll_payslip import identity_read
            payslip_certificate=identity_read(db,actor,scope,execution.statement)
            if not payslip_certificate:deny('Payslip sources require an exact native identity preflight')
            employee_certificate=execution.bind_mapper.class_ is Employee
        if scope.operation.purpose=='hrms.payroll_variance' and execution.bind_mapper is not None and execution.bind_mapper.class_ is Employee:
            from .payroll_variance import employee_fk_read
            employee_certificate=employee_fk_read(db,actor,scope,execution.statement)
        execution_reads=reads|{Employee} if employee_certificate else reads
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in execution_reads:deny('This model is outside native payroll register hints')
        assert_mapped_sources(execution.statement,execution_reads,trusted_identity=identity_load,allowed_associations=(role_permissions,))
        if not payslip_certificate:record_projection(execution.statement,execution.is_relationship_load)
        if not identity_load and not execution.is_column_load and not execution.is_relationship_load:
            for node in visitors.iterate(execution.statement):
                if isinstance(node,TextClause) or isinstance(node,ColumnClause) and (getattr(node,'is_literal',False) or
                        getattr(node,'table',None) is not None and not(node._annotations.get('parententity') or node._annotations.get('parentmapper'))):
                    deny('Native payroll register hints cannot run arbitrary SQL')
        inherited={id(option) for option in getattr(execution.statement,'_with_options',())}
        execution.statement=execution.statement.options(*(option for option in options if id(option) not in inherited))
        if employee_certificate:execution.statement=execution.statement.options(with_loader_criteria(Employee,owned(people),include_aliases=True,propagate_to_loaders=False))
        execution.update_execution_options(compiled_cache=None)
    def validate(session,*args):
        fresh()
        if scope.operation.purpose=='hrms.payroll_variance':
            from .payroll_variance import validate_rows
            return validate_rows(session,actor,scope)
        if session.new or session.deleted or any(session.is_modified(row,include_collections=True) for row in session.dirty):
            deny('Payroll register cannot mutate employment or business records')
    original_get,original_refresh=db.get,db.refresh
    def visible(model,identity):
        fresh();mapper=inspect(model,raiseerr=False);model=getattr(mapper,'class_',model)
        if model not in reads or model is PayrollRecord:return False
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
        if not visible(type(row),inspect(row).identity):deny('Cached identity is outside native payroll register authority')
        previous=identity_load;identity_load=True
        try:return original_refresh(row,*args,**kwargs)
        finally:identity_load=previous
    bulk={name:getattr(db,name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject(*args,**kwargs):deny('Native payroll register hints cannot perform bulk writes')
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
        db.info.pop('business_common_core_scope',None);_CHECKS.pop(db,None);_COUNTS.pop(db,None)
    return cleanup


def run_output(db,row):
    """Native Run DTO, replacing only the lazy full-record employee count."""
    from sqlalchemy import func
    from sqlalchemy.orm import object_session
    from .common_core import CommonCoreScope
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.schemas.payroll import PayrollRunSchema
    scope=db.info.get('business_common_core_scope')
    if not isinstance(scope,CommonCoreScope) or scope.operation.purpose!=PURPOSE:return row
    if row is None:return None
    proof=_CHECKS.get(db)
    if proof is None:raise HTTPException(403,'Verified native payroll register required')
    check,_=proof;check()
    state=inspect(row)
    if type(row) is not PayrollRun or object_session(row) is not db or not state.persistent or state.deleted:
        raise HTTPException(403,'Actual native payroll run required')
    if db.query(PayrollRun.id).filter(PayrollRun.id==row.id).first() is None:
        raise HTTPException(404,'Payroll run not found')
    previous=_COUNTS.get(db)
    _COUNTS[db]=row.id
    try:
        count=db.query(func.count(PayrollRecord.id)).filter(PayrollRecord.payroll_run_id==row.id).scalar()
    finally:
        if previous is None:_COUNTS.pop(db,None)
        else:_COUNTS[db]=previous
    result={key:getattr(row,key) for key in PayrollRunSchema.model_fields if key!='total_employees'}
    result['total_employees']=int(count or 0)
    check()
    return result
