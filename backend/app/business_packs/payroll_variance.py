"""Unpublished exact native variance projection/materialization.

Only server-computed PayrollVarianceItem rows may change. Payroll runs, records,
review audit history, salaries and banking records never gain a write lease.
"""
from types import MappingProxyType
from weakref import WeakKeyDictionary
from decimal import Decimal,InvalidOperation
from fastapi import HTTPException
from sqlalchemy import select,exists,and_,or_,inspect,cast,literal
from sqlalchemy.orm import object_session

PURPOSE='hrms.payroll_variance'
PATH='/api/v1/payroll/runs/{run_id}/variance'
_LEASES=WeakKeyDictionary()


def operations(operation):return MappingProxyType({})


def candidate_operations(operation):
    rows=frozenset({'payroll_variance_items'})
    return MappingProxyType({('GET',PATH):operation('view','payroll_view',rows,rows,rows,purpose=PURPOSE)})


def install(db,actor,scope):
    from .payroll_register import install as register_install
    return register_install(db,actor,scope)


def _reconcile():raise HTTPException(409,'Payroll variance source requires reconciliation')


def _row_values(row):
    from app.models.payroll import PayrollVarianceItem
    return {column.name:getattr(row,column.name) for column in PayrollVarianceItem.__table__.c if column.name not in {'id','created_at'}}


def _normalized(db,values):
    from app.models.payroll import PayrollVarianceItem
    result=dict(values)
    for column in PayrollVarianceItem.__table__.c:
        if column.name not in result or getattr(column.type,'scale',None) is None:continue
        value=Decimal(str(result[column.name]))
        if not value.is_finite():_reconcile()
        # Use the actual backend's native Numeric conversion, exactly as its
        # existing derivative row would be stored; never cap/reprice the result.
        maximum=Decimal(10)**(column.type.precision-column.type.scale)
        if abs(value)>=maximum:_reconcile()
        result[column.name]=db.connection().scalar(select(cast(literal(value),column.type)))
    return result


def _private_previous(db,scope,employees,month,year,present):
    if not present or not employees:return False
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    from .models import PackRecordOwnership
    from app.branches.catalog import key_expression
    runs,records,owner,private=PayrollRun.__table__,PayrollRecord.__table__,BranchOwnership.__table__,PackRecordOwnership.__table__
    owned=exists(select(1).where(owner.c.resource_table==runs.name,owner.c.resource_key==key_expression(runs),
        owner.c.company_id==scope.company_id,owner.c.branch_id.in_(scope.branch.allowed),
        owner.c.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id==scope.company_id))))
    hidden=or_(exists(select(1).where(private.c.resource_table==runs.name,private.c.resource_key==key_expression(runs))),
        exists(select(1).where(private.c.resource_table==records.name,private.c.resource_key==key_expression(records))))
    return db.connection().execute(select(records.c.id).join(runs,runs.c.id==records.c.payroll_run_id).where(
        records.c.employee_id.in_(employees),runs.c.month==month,runs.c.year==year,runs.c.deleted_at.is_(None),
        or_(runs.c.company_id==scope.company_id,runs.c.company_id.is_(None)),owned,hidden).limit(1)).first() is not None


def snapshot(db,run_id,scope,check,present):
    """Private readonly reader entry: original arithmetic, actual visible inputs."""
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.crud.crud_payroll import build_payroll_variance_item
    current=db.query(PayrollRun).filter(PayrollRun.id==run_id,PayrollRun.deleted_at.is_(None)).with_for_update().one_or_none()
    if current is None:raise HTTPException(404,'Payroll run not found')
    if type(current.month) is not int or not 1<=current.month<=12:_reconcile()
    month=12 if current.month==1 else current.month-1;year=current.year-1 if current.month==1 else current.year
    previous=db.query(PayrollRun).filter(PayrollRun.month==month,PayrollRun.year==year,PayrollRun.deleted_at.is_(None)).limit(2).all()
    if len(previous)>1:raise HTTPException(409,'Previous payroll period is ambiguous; reconcile its source')
    if previous:db.query(PayrollRun.id).filter_by(id=previous[0].id).with_for_update().one()
    records=db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id==run_id).order_by(PayrollRecord.id).all()
    employee_ids=[row.employee_id for row in records]
    if len(set(employee_ids))!=len(employee_ids):_reconcile()
    if _private_previous(db,scope,employee_ids,month,year,present):_reconcile()
    specs=[]
    for record in records:
        prior=[] if not previous else db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id==previous[0].id,
            PayrollRecord.employee_id==record.employee_id).limit(2).all()
        if len(prior)>1:_reconcile()
        before=prior[0] if prior else None
        for source in (record,before):
            if source is None:continue
            for name in ('gross_salary','net_salary','basic','hra','other_allowances','other_deductions','reimbursements','tds','lop_days'):
                if not Decimal(str(getattr(source,name) or 0)).is_finite():_reconcile()
            if any(not Decimal(str(component.amount or 0)).is_finite() for component in source.components):_reconcile()
        calculated=build_payroll_variance_item(run_id,record,before)
        specs.append({'values':_normalized(db,_row_values(calculated)),
            'previous_currency':calculated.previous_currency,'current_currency':calculated.current_currency})
    check()
    return {'run_id':run_id,'items':specs}


def _branch(db,row,scope,*,deleted_branch=None):
    from app.branches.models import BranchOwnership
    from app.branches.boundary import branch_for_row
    from app.branches.catalog import resource_key
    from app.db.base_class import Base
    table=row.__table__;values={column.name:getattr(row,column.name) for column in table.c}
    evidence=branch_for_row(db.connection(),table,values,scope.company_id,Base.metadata.tables)
    if len(evidence)!=1:raise HTTPException(409,'Payroll variance branch source requires reconciliation')
    branch=next(iter(evidence))
    if inspect(row).persistent:
        key=resource_key(table,{column.name:getattr(row,column.name) for column in table.primary_key})
        actual=db.connection().execute(select(BranchOwnership.company_id,BranchOwnership.branch_id).where(
            BranchOwnership.resource_table==table.name,BranchOwnership.resource_key==key).limit(2)).all()
        if actual!=[(scope.company_id,branch)]:
            cleaned=(not actual and db._flushing and row in db.deleted and deleted_branch==branch)
            if not cleaned:_reconcile()
    if branch not in scope.branch.allowed:raise HTTPException(403,'Payroll variance is outside the native branch scope')
    return branch


def validate_rows(db,actor,scope):
    """Called by the unchanged outer closed reader before any ORM flush."""
    changed=set(db.new)|set(db.dirty)|set(db.deleted)
    if not changed:return True
    from app.models.payroll import PayrollVarianceItem
    lease=_LEASES.get(db)
    if lease is None or lease['scope'] is not scope or lease['actor'] is not actor:
        raise HTTPException(403,'Native variance materialization lease required')
    lease['check']()
    for row in changed:
        if type(row) is not PayrollVarianceItem:raise HTTPException(403,'Variance view cannot mutate financial sources or history')
        if row in db.new:
            expected=lease['new'].get(row)
            if expected is None or row.id is not None or row.created_at is not None or _row_values(row)!=expected:
                raise HTTPException(403,'Variance row differs from its actual computed source')
        elif row in db.deleted:
            expected=lease['deleted'].get(row)
            if expected is None or (_row_values(row),row.id,row.created_at)!=expected:raise HTTPException(403,'Variance deletion is outside its verified source')
        else:raise HTTPException(403,'Variance reads cannot edit existing financial derivatives')
        destination=_branch(db,row,scope,deleted_branch=lease['branches'].get(row) if row in db.deleted else None)
        if destination not in scope.branch.writable:raise HTTPException(403,'Select a writable branch to refresh payroll variance')
    return True



def employee_fk_read(db,actor,scope,statement):
    """Only the native Own/Team flush existence check for a computed source."""
    from app.models.employee import Employee
    from sqlalchemy.sql import visitors,operators
    from sqlalchemy.sql.elements import BinaryExpression,BindParameter
    lease=_LEASES.get(db)
    if not db._flushing or lease is None or lease['actor'] is not actor or lease['scope'] is not scope:return False
    from sqlalchemy.sql.selectable import Join
    sources=statement.get_final_froms()
    if len(sources)!=1 or isinstance(sources[0],Join) or getattr(statement,'_setup_joins',()):return False
    descriptions=getattr(statement,'column_descriptions',())
    if len(descriptions)!=1 or descriptions[0].get('entity') is not Employee:return False
    expression=descriptions[0].get('expr')
    if not getattr(expression,'shares_lineage',lambda column:False)(Employee.__table__.c.id):return False
    valid=set()
    for row,values in lease['new'].items():
        if row.payroll_run_id!=values['payroll_run_id'] or _row_values(row)!=values:continue
        deleting=any(old in db.deleted and old.employee_id==row.employee_id and old.payroll_run_id==row.payroll_run_id
            and (_row_values(old),old.id,old.created_at)==snapshot for old,snapshot in lease['deleted'].items())
        if row in db.new or deleting:valid.add(row.employee_id)
    matches=[node.right.value for node in visitors.iterate(statement)
        if isinstance(node,BinaryExpression) and node.operator is operators.eq
        and getattr(node.left,'shares_lineage',lambda column:False)(Employee.__table__.c.id)
        and isinstance(node.right,BindParameter)]
    if len(matches)!=1 or matches[0] not in valid:return False
    allowed={'id','user_id','branch_id','department_id','reporting_manager_id','deleted_at'}
    for node in visitors.iterate(statement):
        mapper=node._annotations.get('parentmapper') or node._annotations.get('parententity')
        if getattr(mapper,'class_',None) is Employee and getattr(node,'table',None) is not None:
            if getattr(node,'key',None) not in allowed:return False
    lease['check']()
    return True


def serialize_legacy(db,actor,run_id):
    """Same native calculation, with shared serialization before its row locks."""
    from app.models.payroll import PayrollRun
    from .common_core import _native_authority,_native_operation_access,CoreOperation
    company=getattr(actor,'organization_id',None)
    if type(company) is not int or db.info.get('shared_actor')!=(actor.id,company):
        raise HTTPException(403,'Verified native variance actor required')
    before=_native_authority(db,actor,company)
    run=db.query(PayrollRun.id).filter(PayrollRun.id==run_id,PayrollRun.deleted_at.is_(None)).first()
    if run is None:raise ValueError('Payroll run not found')
    context=db.info.get('branch_context')
    if context is not None and context.writable:
        from app.core.company_writer import lock_company_writer
        lock_company_writer(db,company)
        if _native_authority(db,actor,company)!=before:raise HTTPException(403,'Native payroll variance authority changed')
        _native_operation_access(db,actor,company,CoreOperation('view','payroll_view',purpose=PURPOSE))
        if db.query(PayrollRun.id).filter(PayrollRun.id==run_id,PayrollRun.deleted_at.is_(None)).with_for_update().first() is None:
            raise ValueError('Payroll run not found')


def project(db,actor,run_id):
    from .common_core import CommonCoreScope
    from .payroll_register import _CHECKS
    from .common_binding import MARKER
    from app.models.payroll import PayrollRun,PayrollVarianceItem
    from app.branches.models import BranchOwnership
    scope=db.info.get('business_common_core_scope')
    if not isinstance(scope,CommonCoreScope):return None
    if (scope.operation.purpose!=PURPOSE or scope.route!=PATH or scope.method!='GET'
            or db.info.get(MARKER)!=scope.binding or scope.user_id!=actor.id):
        raise HTTPException(403,'Actual native variance request required')
    proof=_CHECKS.get(db)
    if proof is None:raise HTTPException(403,'Native variance guard required')
    check,_=proof;check()
    if type(run_id) is not int or run_id<=0:raise HTTPException(404,'Payroll run not found')
    source=db.query(PayrollRun.id).filter(PayrollRun.id==run_id,PayrollRun.deleted_at.is_(None)).first()
    if source is None:raise HTTPException(404,'Payroll run not found')
    branch=db.connection().scalar(select(BranchOwnership.branch_id).where(BranchOwnership.resource_table=='payroll_runs',
        BranchOwnership.resource_key==str(run_id),BranchOwnership.company_id==scope.company_id))
    possible_write=branch in scope.branch.writable
    if possible_write:
        from app.core.company_writer import lock_company_writer
        lock_company_writer(db,scope.company_id);check()
    from .payroll_review import read_variance_snapshot
    plan=read_variance_snapshot(db,actor,run_id)
    if not isinstance(plan,dict) or plan.get('run_id')!=run_id:_reconcile()
    existing=db.query(PayrollVarianceItem).filter(PayrollVarianceItem.payroll_run_id==run_id).order_by(PayrollVarianceItem.id).all()
    deleted_branches={row:_branch(db,row,scope) for row in existing}
    expected={spec['values']['employee_id']:spec for spec in plan['items']}
    same=len(existing)==len(expected) and len({row.employee_id for row in existing})==len(existing)
    if same:same=all(row.employee_id in expected and _row_values(row)==expected[row.employee_id]['values'] for row in existing)
    if not possible_write:
        if not same:raise HTTPException(409,'Payroll variance is stale or missing; select a writable branch to refresh it')
        check()
        return [{**{'id':row.id},**_row_values(row),
            'previous_currency':expected[row.employee_id]['previous_currency'],'current_currency':expected[row.employee_id]['current_currency']} for row in existing]
    if any(row.employee_id not in expected for row in existing):_reconcile()
    created=[PayrollVarianceItem(**spec['values']) for spec in plan['items']]
    lease={'scope':scope,'actor':actor,'check':check,'new':{row:_row_values(row) for row in created},
        'deleted':{row:(_row_values(row),row.id,row.created_at) for row in existing},'branches':deleted_branches}
    from app.branches.derived import payroll_read_derivatives
    if db in _LEASES:raise HTTPException(403,'Nested variance materialization is not allowed')
    _LEASES[db]=lease
    try:
        with payroll_read_derivatives(db,run_id,variance=True):
            for row in existing:db.delete(row)
            db.flush()
            for row in created:db.add(row)
            db.flush();check()
            result=[{'id':row.id,**_row_values(row),'previous_currency':spec['previous_currency'],'current_currency':spec['current_currency']}
                for row,spec in zip(created,plan['items'])]
            db.commit()
            return result
    finally:_LEASES.pop(db,None)
