"""Unpublished native payslip read: fixed source identities, no salary/bank bodies."""
from types import MappingProxyType
from weakref import WeakKeyDictionary
from fastapi import HTTPException
from sqlalchemy import inspect,select,exists,and_
from sqlalchemy.orm import object_session
from sqlalchemy.sql import visitors,operators
from sqlalchemy.sql.elements import BinaryExpression,BindParameter,BooleanClauseList

PURPOSE='hrms.payroll_payslip'
PATH='/api/v1/payroll/payslip'
_PREFLIGHT=WeakKeyDictionary()


def operations(operation):return MappingProxyType({})

def candidate_operations(operation):return MappingProxyType({('GET',PATH):operation('view',None,purpose=PURPOSE)})

def native_self_request(db,actor,company,operation):
    return operation.purpose==PURPOSE and operation.module=='hrms' and operation.action=='view' and operation.permission is None

def install(db,actor,scope):
    from .payroll_register import install as register_install
    return register_install(db,actor,scope)


def _equal(statement,column,value):
    return any(isinstance(node,BinaryExpression) and node.operator is operators.eq
        and getattr(node.left,'shares_lineage',lambda other:False)(column)
        and isinstance(node.right,BindParameter) and node.right.value==value for node in visitors.iterate(statement))


def identity_read(db,actor,scope,statement):
    """Exact mapped scalar probes only while the real source is being selected."""
    from app.models.employee import Employee
    from app.models.payroll import PayrollRun,PayrollRecord
    lease=_PREFLIGHT.get(db)
    if lease is None or lease['scope'] is not scope or lease['actor'] is not actor:return False
    if any(isinstance(node,BooleanClauseList) and node.operator is operators.or_
            for clause in getattr(statement,'_where_criteria',()) for node in visitors.iterate(clause)):return False
    descriptions=getattr(statement,'column_descriptions',())
    phase=lease['phase']
    if phase in {'self','employee'}:
        columns=(Employee.__table__.c.id,)
        required=Employee.__table__.c.user_id if phase=='self' else Employee.__table__.c.id
        value=actor.id if phase=='self' else lease['employee_id']
        if getattr(statement,'_setup_joins',()):return False
    elif phase=='record':
        columns=(PayrollRecord.__table__.c.id,PayrollRecord.__table__.c.payroll_run_id,PayrollRecord.__table__.c.employee_id)
        required=PayrollRecord.__table__.c.employee_id;value=lease['employee_id']
        if not (_equal(statement,PayrollRun.__table__.c.month,lease['month']) and _equal(statement,PayrollRun.__table__.c.year,lease['year'])):return False
    elif phase=='fiscal':
        from app.models.payroll import PayrollDeliveryProfile
        if not lease.get('record_id') or not lease.get('run_id'):return False
        columns=tuple(PayrollDeliveryProfile.__table__.c[name] for name in ('id','ytd_basis','fy_start_month'))
        required=PayrollDeliveryProfile.__table__.c.company_id;value=scope.company_id
        if getattr(statement,'_setup_joins',()):return False
    elif phase=='reader':
        columns=tuple(PayrollRun.__table__.c[name] for name in ('id','month','year','company_id','branch_id','department_id','pay_group_id'))
        required=PayrollRun.__table__.c.id;value=lease['run_id']
        if getattr(statement,'_setup_joins',()):return False
    else:return False
    if len(descriptions)!=len(columns) or not _equal(statement,required,value):return False
    for item,column in zip(descriptions,columns):
        expression=item.get('expr')
        if not getattr(expression,'shares_lineage',lambda other:False)(column):return False
        if not getattr(expression,'_annotations',{}).get('parententity'):return False
    return True


def reader_proof(db,actor,scope,run_id):
    lease=_PREFLIGHT.get(db)
    if lease is None or lease['actor'] is not actor or lease['scope'] is not scope or lease['phase']!='reader' or lease.get('run_id')!=run_id:
        raise HTTPException(403,'Actual native payslip source proof required')
    return dict(lease)


def fiscal_policy(db,company):
    """Existing company-wide FY settings, never presentation or delivery bodies."""
    from app.models.payroll import PayrollDeliveryProfile
    from .models import PackRecordOwnership
    table=PayrollDeliveryProfile.__table__
    if not inspect(db.connection()).has_table(table.name):raise HTTPException(503,'Native payslip fiscal settings are not installed')
    lease=_PREFLIGHT.get(db)
    if lease is None or lease['scope'].company_id!=company or not lease.get('record_id'):
        raise HTTPException(403,'Actual native payslip fiscal source required')
    from app.branches.catalog import key_expression
    if inspect(db.connection()).has_table(PackRecordOwnership.__tablename__):
        private=PackRecordOwnership.__table__
        if db.connection().scalar(select(exists(select(1).where(table.c.company_id==company,
                exists(select(1).where(private.c.resource_table==table.name,private.c.resource_key==key_expression(table))).correlate(table))))):
            raise HTTPException(503,'Native payslip fiscal settings require reconciliation')
    previous=lease['phase'];lease['phase']='fiscal'
    try:
        rows=db.query(PayrollDeliveryProfile.id,PayrollDeliveryProfile.ytd_basis,PayrollDeliveryProfile.fy_start_month).filter(
            PayrollDeliveryProfile.company_id==company).limit(2).all()
    finally:lease['phase']=previous
    if len(rows)>1:raise HTTPException(409,'Native payslip fiscal settings require reconciliation')
    if not rows:return (None,'financial',4)
    row=rows[0]
    if row.ytd_basis not in {'financial','calendar'} or type(row.fy_start_month) is not int or not 1<=row.fy_start_month<=12:
        raise HTTPException(409,'Native payslip fiscal settings require reconciliation')
    return tuple(row)


def _dto(value,employee_id):
    keys={'id','payroll_run_id','employee_id','employee','month','year','financial_year','ytd_basis','ytd_period_start','ytd_period_label',
        'department','working_days','present_days','lop_days','paid_days','gross_salary','total_deductions','net_salary','currency',
        'salary_currency','exchange_rate','converted_currency','currency_note','status','payroll_status','pdf_available','is_anomaly',
        'anomaly_reason','earnings','deductions','employer_contributions','reimbursements','ytd'}
    if not isinstance(value,dict) or set(value)!=keys or value['employee_id']!=employee_id:raise HTTPException(503,'Native payslip output changed')
    if value['employee'] is not None and (set(value['employee'])!={'id','employee_id','first_name','last_name'} or value['employee']['id']!=employee_id):
        raise HTTPException(503,'Native payslip employee output changed')
    for key in ('earnings','deductions','employer_contributions','reimbursements'):
        if not isinstance(value[key],list) or any(set(row)!={'component_name','component_type','amount'} for row in value[key]):raise HTTPException(503,'Native payslip breakdown changed')
    if set(value['ytd'])!={'gross_salary','total_deductions','net_salary','reimbursements','employer_contributions'}:raise HTTPException(503,'Native payslip year totals changed')
    return value


def project(db,actor,month,year,employee_id=None):
    from .common_core import CommonCoreScope
    from .common_binding import MARKER
    from .payroll_register import _CHECKS
    from app.models.user import User
    from app.models.employee import Employee
    from app.models.payroll import PayrollRecord,PayrollRun
    from app.api.v1.payroll import _can_view_other_payslips
    scope=db.info.get('business_common_core_scope')
    if not isinstance(scope,CommonCoreScope):return None
    if type(actor) is not User or object_session(actor) is not db or not inspect(actor).persistent:
        raise HTTPException(403,'Actual native payslip actor required')
    if (scope.operation.purpose!=PURPOSE or scope.route!=PATH or scope.method!='GET' or scope.user_id!=actor.id
            or db.info.get(MARKER)!=scope.binding or scope.company_id!=actor.organization_id
            or scope.binding.company_id!=scope.company_id or scope.branch.company_id!=scope.company_id
            or db.info.get('branch_context')!=scope.branch or type(actor) is not User or object_session(actor) is not db or not inspect(actor).persistent):
        raise HTTPException(403,'Actual native payslip request required')
    proof=_CHECKS.get(db)
    if proof is None or db in _PREFLIGHT:raise HTTPException(403,'Native payslip guard required')
    if db.new or db.deleted or any(db.is_modified(row,include_collections=True) for row in db.dirty):raise HTTPException(403,'Native payslip requires unchanged source records')
    check,_=proof;check();can_other=_can_view_other_payslips(actor)
    lease={'scope':scope,'actor':actor,'phase':'self','month':month,'year':year}
    _PREFLIGHT[db]=lease
    try:
        own=db.query(Employee.id).filter(Employee.user_id==actor.id,Employee.deleted_at.is_(None)).limit(2).all()
        if len(own)>1:raise HTTPException(409,'Native employment identity requires reconciliation')
        own_id=own[0].id if own else None
        target=employee_id or own_id
        if not target:
            # Native auth knows its own employment identity even when the selected
            # branch hides it. Preserve the native denial without exposing its ID
            # or using that hidden identity to select any payroll record.
            from app.models.company import Branch
            from .models import PackRecordOwnership
            from app.branches.catalog import key_expression
            employee=Employee.__table__;branch=Branch.__table__;private=PackRecordOwnership.__table__
            unowned=~exists(select(1).where(private.c.resource_table==employee.name,
                private.c.resource_key==key_expression(employee))) if inspect(db.connection()).has_table(private.name) else True
            own_elsewhere=db.connection().scalar(select(exists(select(1).select_from(employee.join(branch,
                branch.c.id==employee.c.branch_id)).where(employee.c.user_id==actor.id,
                employee.c.deleted_at.is_(None),branch.c.company_id==scope.company_id,unowned))))
            if own_elsewhere:raise HTTPException(404,'Payslip not found for this period')
            raise HTTPException(400,'No employee profile')
        if employee_id and not can_other and target!=own_id:raise HTTPException(403,'Not authorized to view this payslip')
        lease.update(phase='employee',employee_id=target,own_id=own_id,can_other=can_other)
        if db.query(Employee.id).filter(Employee.id==target,Employee.deleted_at.is_(None)).first() is None:
            raise HTTPException(404,'Payslip not found for this period')
        lease['phase']='record'
        query=db.query(PayrollRecord.id,PayrollRecord.payroll_run_id,PayrollRecord.employee_id).join(PayrollRun).filter(
            PayrollRecord.employee_id==target,PayrollRun.month==month,PayrollRun.year==year,PayrollRun.deleted_at.is_(None))
        if not can_other:
            from sqlalchemy import func
            query=query.filter(func.lower(PayrollRun.status).in_(['locked','paid']))
        source=query.order_by(PayrollRun.id.desc(),PayrollRecord.id.desc()).first()
        if source is None:raise HTTPException(404,'Payslip not found for this period')
        lease.update(record_id=source.id,run_id=source.payroll_run_id)
        lease.update(phase='reader',fiscal=fiscal_policy(db,scope.company_id))
        from .payroll_review import read_payslip
        result=read_payslip(db,actor,source.payroll_run_id)
        check()
        if fiscal_policy(db,scope.company_id)!=lease['fiscal']:raise HTTPException(409,'Native payslip fiscal settings changed; reload')
        from app.services.payroll_delivery import year_window
        from datetime import date
        start,_,label=year_window(date(year,month,1),lease['fiscal'][1],lease['fiscal'][2])
        if (result.get('ytd_basis')!=lease['fiscal'][1] or result.get('ytd_period_start')!=start.isoformat() or result.get('financial_year')!=label):
            raise HTTPException(409,'Native payslip fiscal source changed; reload')
        return _dto(result,target)
    finally:_PREFLIGHT.pop(db,None)
