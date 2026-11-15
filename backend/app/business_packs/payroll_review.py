"""Fixed readonly native Guided Payroll computation, never a generic data session.

The request session remains closed to payroll/salary/contact bodies. Only this
server-owned computation receives a short-lived native scoped reader; no caller
SQL, callback, mutable permission, or operational Pack realm is accepted.
"""
from contextlib import ExitStack
from copy import deepcopy
from types import MappingProxyType,SimpleNamespace
from weakref import WeakKeyDictionary
from fastapi import HTTPException
from sqlalchemy import and_,or_,event,exists,false,inspect,select
from sqlalchemy.orm import Session,with_loader_criteria,load_only,defaultload
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause

PURPOSE='hrms.payroll_review'
PATH='/api/v1/payroll/runs/{run_id}/guided'
_COMPUTATIONS=WeakKeyDictionary()
_NATIVE_READS=WeakKeyDictionary()


def operations(operation):return candidate_operations(operation)


def candidate_operations(operation):
    return MappingProxyType({('GET',PATH):operation('view','payroll_view',purpose=PURPOSE)})


def install(db,actor,scope):
    from .payroll_register import install as register_install
    return register_install(db,actor,scope)


class _Reader(Session):
    """ORM-only private computation session; no public raw connection handle."""
    def __init__(self,*args,**kwargs):
        self.__sealed=False;self.__executing=0;self.__closed=False
        super().__init__(*args,**kwargs)
    def _deny(self,*args,**kwargs):raise HTTPException(403,'Native computation is read-only and ORM-scoped')
    add=add_all=delete=flush=commit=rollback=merge=_deny
    bulk_save_objects=bulk_insert_mappings=bulk_update_mappings=_deny
    begin=begin_nested=get_transaction=get_nested_transaction=_deny
    invalidate=reset=bind_mapper=bind_table=_deny
    @property
    def bind(self):
        if self.__sealed and not self.__executing:self._deny()
        return self.__native_bind
    @bind.setter
    def bind(self,value):
        if self.__sealed:self._deny()
        self.__native_bind=value
    def get_bind(self,*args,**kwargs):
        if self.__sealed and not self.__executing:self._deny()
        return super().get_bind(*args,**kwargs)
    def connection(self,*args,**kwargs):
        if self.__closed:
            from sqlalchemy.exc import InvalidRequestError
            raise InvalidRequestError('This Session has been permanently closed and is unable to handle any more transaction requests.')
        if self.__sealed:self._deny()
        return super().connection(*args,**kwargs)
    def _execute_internal(self,*args,**kwargs):
        self.__executing+=1
        try:return super()._execute_internal(*args,**kwargs)
        finally:self.__executing-=1
    def _seal(self):
        self.__sealed=True
        # Native branch get/refresh visibility adapters use raw connections.
        # A fresh guarded ORM lookup applies those same installed predicates
        # without exporting a connection or returning a cached foreign object.
        self.get=self._scoped_get;self.refresh=self._deny
    def _scoped_get(self,model,identity,**kwargs):
        mapper=inspect(model,raiseerr=False)
        if mapper is None or not getattr(mapper,'is_mapper',False):self._deny()
        keys=mapper.primary_key
        values=[identity.get(key.key) for key in keys] if isinstance(identity,dict) else list(identity) if isinstance(identity,(tuple,list)) else [identity]
        if len(values)!=len(keys):self._deny()
        return self.query(model).filter(*(getattr(model,mapper.get_property_by_column(key).key)==value for key,value in zip(keys,values))).first()
    def close(self):
        try:return super().close()
        finally:self.__closed=True


def _actor(db,actor,company,present):
    """Fresh minimal native scope identity, without loading employment contacts."""
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.models.user import Role,Permission,role_permissions
    from app.common.models import CommonPerson
    from .models import PackRecordOwnership
    source=Employee.__table__;private=PackRecordOwnership.__table__
    from app.branches.catalog import key_expression
    unowned=~exists(select(1).where(private.c.resource_table==source.name,private.c.resource_key==key_expression(source))) if present else ~false()
    own=db.connection().execute(select(source.c.id,source.c.branch_id,source.c.department_id,source.c.reporting_manager_id,
        source.c.employment_type).where(source.c.user_id==actor.id,unowned).limit(2)).mappings().all()
    if len(own)>1:raise HTTPException(403,'Canonical payroll actor employment is ambiguous')
    employee=SimpleNamespace(**dict(own[0])) if own else None
    if employee:
        home=db.connection().scalar(select(Branch.__table__.c.company_id).where(Branch.__table__.c.id==employee.branch_id))
        employee.branch=SimpleNamespace(company_id=home) if home else None
    person=db.connection().scalar(select(CommonPerson.__table__.c.organization_id).where(CommonPerson.__table__.c.user_id==actor.id))
    permissions=[SimpleNamespace(**dict(row)) for row in db.connection().execute(select(Permission.__table__.c.id,
        Permission.__table__.c.name,Permission.__table__.c.module,Permission.__table__.c.description).join(role_permissions,
        role_permissions.c.permission_id==Permission.__table__.c.id).where(role_permissions.c.role_id==actor.role_id)).mappings()]
    name=db.connection().scalar(select(Role.__table__.c.name).where(Role.__table__.c.id==actor.role_id))
    view=SimpleNamespace(id=actor.id,role_id=actor.role_id,organization_id=company,is_active=actor.is_active,
        is_superuser=actor.is_superuser,employee=employee,person=SimpleNamespace(organization_id=person) if person else None,
        role=SimpleNamespace(id=actor.role_id,name=name,permissions=permissions) if name else None)
    for key in ('_suite_admin_read','_suite_current_module','_suite_policy_version','_suite_scope_active'):
        if hasattr(actor,key):setattr(view,key,getattr(actor,key))
    view._suite_grants=deepcopy(getattr(actor,'_suite_grants',None))
    from app.access.catalog import permission_objects
    view._suite_permission_objects=[SimpleNamespace(id=getattr(item,'id',None),name=item.name,module=getattr(item,'module',None)) for item in permission_objects(actor)]
    return view


def _models(mode="review"):
    from app.models import payroll as p
    from app.models.employee import Employee
    from app.models.company import Branch,Company
    from app.models.leave import LeaveRequest,LeaveType
    from app.models.attendance import Attendance,Holiday,Shift,ShiftWeeklyOff,ShiftRoster
    thin={
        p.PayrollRun:None,p.PayrollPayGroup:None,p.PayrollPeriod:None,
        p.PayrollRecord:('id','payroll_run_id','employee_id','salary_currency','gross_salary','net_salary','total_deductions','updated_at'),
        p.PayrollComponent:('id','record_id','amount'),
        p.PayrollRunAuditLog:('id','payroll_run_id','action','details'),
        p.PayrollPaymentBatch:('id','company_id','payroll_run_id','status','total_amount','generated_file_url'),
        p.PayrollPaymentLine:('id','batch_id','payroll_record_id','employee_id','payment_status','utr_number','failure_reason'),
        Employee:('id','user_id','first_name','last_name','status','deleted_at','branch_id','department_id','reporting_manager_id',
            'employment_type','worker_type','worker_category','functional_area','date_of_joining','date_of_exit','shift_id','account_number','ifsc_code','pan_number'),
        Branch:('id','company_id'),Company:('id','is_active','working_days_per_week'),
        p.PayrollAttendanceInput:('id','period_id','employee_id','source_status','locked_at','lop_days','policy_trace'),
        p.PayrollManualInput:('id','payroll_run_id','employee_id','status','input_type','component_name','amount'),
        p.LOPAdjustment:('id','period_id','employee_id','status','adjustment_days'),
        Attendance:('id','employee_id','attendance_date','status'),
        LeaveRequest:('id','company_id','employee_id','leave_type_id','from_date','to_date','days_count','is_half_day','half_day_period','status','deleted_at'),
        LeaveType:('id','name','code','is_active'),Holiday:('id','holiday_date','applicable_branches','is_active'),
        Shift:('id',),ShiftWeeklyOff:('id','shift_id','weekday','week_pattern','is_active'),
        ShiftRoster:('id','organization_id','employee_id','shift_id','roster_date','status'),
    }
    scalar={p.EmployeeSalary:{'employee_id'},p.SalaryRevisionRequest:{'employee_id'},
        p.Reimbursement:{'id','employee_id','status'},p.EmployeeTaxDeclaration:{'employee_id'}}
    if mode=='variance':
        keep={p.PayrollRun,p.PayrollPayGroup,p.PayrollRecord,p.PayrollComponent,Employee,Branch,Company}
        thin={model:columns for model,columns in thin.items() if model in keep}
        thin[p.PayrollRecord]=('id','payroll_run_id','employee_id','salary_currency','gross_salary','net_salary','basic','hra',
            'other_allowances','other_deductions','reimbursements','tds','lop_days','updated_at')
        thin[p.PayrollComponent]=('id','record_id','amount','source_type','component_name','is_manual')
        thin[Employee]=('id','user_id','branch_id','department_id','reporting_manager_id')
        scalar={}
    if mode=='payslip':
        from app.models.company import Department
        thin={p.PayrollRun:('id','company_id','branch_id','department_id','pay_group_id','month','year','status','deleted_at'),
            p.PayrollRecord:('id','payroll_run_id','employee_id','working_days','present_days','lop_days','paid_days','gross_salary',
                'total_deductions','net_salary','salary_currency','exchange_rate','converted_currency','status','is_anomaly','anomaly_reason',
                'payslip_pdf_url','basic','hra','other_allowances','pf_employee','esi_employee','professional_tax','tds','other_deductions',
                'pf_employer','esi_employer','reimbursements'),
            p.PayrollComponent:('id','record_id','component_name','component_type','amount'),
            Employee:('id','user_id','employee_id','first_name','last_name','branch_id','department_id','deleted_at'),
            Branch:('id','company_id'),Company:('id',),Department:('id','name','organization_id','branch_id'),
            p.PayrollDeliveryProfile:('id','company_id','ytd_basis','fy_start_month')}
        scalar={}
    return thin,scalar


def _dto(result):
    keys={'id','currency','status','reviewed','blocked','issues','blockers','can_process','can_review','can_approve','records','batches'}
    if not isinstance(result,dict) or set(result)!=keys:raise HTTPException(503,'Native payroll review projection changed')
    for row in result['records']:
        if set(row)!={'id','employee_id','employee_name','gross','deductions','net','currency'}:
            raise HTTPException(503,'Native payroll employee projection changed')
    for batch in result['batches']:
        if set(batch)!={'id','status','total','file_url','lines'}:raise HTTPException(503,'Native payroll batch projection changed')
        for line in batch['lines']:
            if set(line)!={'employee_id','payroll_record_id','status','utr','failure_reason'}:
                raise HTTPException(503,'Native payroll payment projection changed')
    return result


def compute(db,actor,run_id):
    return _compute(db,actor,run_id,'review')


def read_variance_snapshot(db,actor,run_id):
    return _compute(db,actor,run_id,'variance')


def read_payslip(db,actor,run_id):
    return _compute(db,actor,run_id,'payslip')


def _compute(db,actor,run_id,mode):
    from .common_core import CommonCoreScope
    from sqlalchemy.orm import object_session
    from app.models.user import User
    from .common_binding import MARKER
    from .payroll_register import _CHECKS
    from app.models import payroll as p
    from app.models.employee import Employee
    from app.models.company import Branch,Company,Department
    from .models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    from app.models.security_boundary import SecurityResourceOwnership
    from app.branches.catalog import key_expression,SHARED
    from .common_queries import assert_mapped_sources
    scope=db.info.get('business_common_core_scope')
    if not isinstance(scope,CommonCoreScope):return None
    purposes={'review':(PURPOSE,PATH),'variance':('hrms.payroll_variance','/api/v1/payroll/runs/{run_id}/variance'),'payslip':('hrms.payroll_payslip','/api/v1/payroll/payslip')}
    if mode not in purposes:raise HTTPException(403,'Unknown native payroll computation')
    expected_purpose,expected_route=purposes[mode]
    if scope.operation.purpose!=expected_purpose:raise HTTPException(403,'Native payroll computation purpose mismatch')
    proof=_CHECKS.get(db)
    if (proof is None or type(actor) is not User or object_session(actor) is not db or not inspect(actor).persistent
            or scope.route!=expected_route or scope.method!='GET' or scope.user_id!=actor.id or db.info.get(MARKER)!=scope.binding):
        raise HTTPException(403,'Actual native payroll review binding required')
    if (scope.company_id!=actor.organization_id or scope.binding.company_id!=scope.company_id or scope.binding.user_id!=scope.user_id
            or scope.branch.company_id!=scope.company_id or db.info.get('branch_context')!=scope.branch):
        raise HTTPException(403,'Native payroll computation scope identity changed')
    check,present=proof;check()
    if type(run_id) is not int or run_id<=0:raise HTTPException(404,'Payroll run not found')
    payslip=None
    if mode=='payslip':
        from .payroll_payslip import reader_proof
        payslip=reader_proof(db,actor,scope,run_id)
        original=db.query(p.PayrollRun.id,p.PayrollRun.month,p.PayrollRun.year,p.PayrollRun.company_id,p.PayrollRun.branch_id,
            p.PayrollRun.department_id,p.PayrollRun.pay_group_id).filter(p.PayrollRun.id==run_id,p.PayrollRun.deleted_at.is_(None)).first()
        if original is None:raise HTTPException(404,'Payroll run not found')
        identity=tuple(original)
    else:
        original=db.query(p.PayrollRun).filter(p.PayrollRun.id==run_id,p.PayrollRun.deleted_at.is_(None)).first()
        if original is None:raise HTTPException(404,'Payroll run not found')
        identity=(original.id,original.month,original.year,original.company_id,original.branch_id,original.department_id,original.pay_group_id)
    view=_actor(db,actor,scope.company_id,present)
    thin,scalar=_models(mode);reads=set(thin)|set(scalar)
    connection=db.connection();transaction=connection.get_transaction();nested=connection.get_nested_transaction()
    reader=_Reader(bind=connection,autoflush=False,expire_on_commit=False,join_transaction_mode='rollback_only',close_resets_only=False)
    reader.info[MARKER]=scope.binding;reader.info['business_pack_scope']=None
    reader.info['security_write_request']=False
    private=PackRecordOwnership.__table__;native=BranchOwnership.__table__;branches=Branch.__table__;security=SecurityResourceOwnership.__table__
    def unowned(table):return ~exists(select(1).where(private.c.resource_table==table.name,private.c.resource_key==key_expression(table))).correlate(table) if present else ~false()
    def owned(table):
        anchor=and_(native.c.resource_table==table.name,native.c.resource_key==key_expression(table),native.c.company_id==scope.company_id,
            native.c.branch_id.in_(scope.branch.allowed),native.c.branch_id.in_(select(branches.c.id).where(branches.c.company_id==scope.company_id)))
        if 'branch_id' in table.c:anchor=and_(anchor,or_(table.c.branch_id.is_(None),table.c.branch_id==native.c.branch_id))
        if 'company_id' in table.c:anchor=and_(anchor,or_(table.c.company_id.is_(None),table.c.company_id==scope.company_id))
        if 'organization_id' in table.c:anchor=and_(anchor,or_(table.c.organization_id.is_(None),table.c.organization_id==scope.company_id))
        return and_(exists(select(1).where(anchor)).correlate(table),unowned(table))
    fiscal_start=None
    if mode=='payslip':
        from app.services.payroll_delivery import year_window
        from datetime import date
        fiscal_start,_,_=year_window(date(identity[2],identity[1],1),payslip['fiscal'][1],payslip['fiscal'][2])
    conditions={}
    for model in reads:
        table=model.__table__
        if model is Company:criterion=and_(Company.id==scope.company_id,unowned(table))
        elif model is Branch:criterion=and_(Branch.company_id==scope.company_id,Branch.id.in_(scope.branch.allowed),unowned(table))
        elif mode=='payslip' and model is p.PayrollDeliveryProfile:criterion=and_(model.company_id==scope.company_id,unowned(table))
        elif table.name in SHARED:
            criterion=and_(model.id.in_(select(security.c.resource_id).where(security.c.resource_table==table.name,security.c.company_id==scope.company_id)),unowned(table))
        else:criterion=owned(table)
        if ('employee_id' in table.c and any(fk.column.table is Employee.__table__ and fk.column.name=='id'
                for fk in table.c.employee_id.foreign_keys)):
            people=Employee.__table__
            criterion=and_(criterion,table.c.employee_id.in_(select(people.c.id).where(owned(people))))
        if mode=='payslip' and model is Employee:criterion=and_(criterion,Employee.id.in_([x for x in {payslip['employee_id'],payslip['own_id']} if x is not None]))
        if mode=='payslip' and model is p.PayrollRecord:criterion=and_(criterion,p.PayrollRecord.employee_id==payslip['employee_id'])
        if mode=='payslip' and model is Department:
            people=Employee.__table__
            criterion=and_(criterion,Department.id.in_(select(people.c.department_id).where(people.c.id==payslip['employee_id'],owned(people))))
        if mode=='payslip' and model is p.PayrollRun:
            records=p.PayrollRecord.__table__
            criterion=and_(criterion,p.PayrollRun.id.in_(select(records.c.payroll_run_id).where(records.c.employee_id==payslip['employee_id'],owned(records))))
        if 'payroll_run_id' in table.c and model is not p.PayrollRecord:criterion=and_(criterion,table.c.payroll_run_id==run_id)
        if model in {p.PayrollRun,p.PayrollRecord}:
            runs=p.PayrollRun.__table__
            window=and_(runs.c.month==identity[1],runs.c.year==identity[2])
            if mode=='payslip':
                window=and_(or_(runs.c.year>fiscal_start.year,and_(runs.c.year==fiscal_start.year,runs.c.month>=fiscal_start.month)),
                    or_(runs.c.year<identity[2],and_(runs.c.year==identity[2],runs.c.month<=identity[1])))
            if mode=='variance':
                prior_month=12 if identity[1]==1 else identity[1]-1
                prior_year=identity[2]-1 if identity[1]==1 else identity[2]
                window=or_(window,and_(runs.c.month==prior_month,runs.c.year==prior_year))
            if model is p.PayrollRecord:criterion=and_(criterion,p.PayrollRecord.payroll_run_id.in_(select(runs.c.id).where(owned(runs),window)))
            else:criterion=and_(criterion,window)
        if model is p.PayrollPeriod:criterion=and_(criterion,p.PayrollPeriod.month==identity[1],p.PayrollPeriod.year==identity[2])
        conditions[model]=criterion
    options=tuple(with_loader_criteria(model,criterion,include_aliases=True,propagate_to_loaders=False) for model,criterion in conditions.items())
    def entity_model(expression):
        mapper=inspect(expression,raiseerr=False)
        return getattr(mapper,'class_',None) if mapper is not None and (getattr(mapper,'is_mapper',False) or getattr(mapper,'is_aliased_class',False)) else None
    def restrict(execution):
        check()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            raise HTTPException(403,'Payroll review computation accepts only native mapped reads')
        assert_mapped_sources(execution.statement,reads)
        selections=getattr(execution.statement,'column_descriptions',())
        for item in selections:
            model=entity_model(item.get('expr'))
            if model in scalar:raise HTTPException(403,'Payroll review cannot load salary or claim bodies')
        for node in visitors.iterate(execution.statement):
            mapper=node._annotations.get('parentmapper') or node._annotations.get('parententity')
            model=getattr(mapper,'class_',None)
            if (isinstance(node,TextClause) or isinstance(node,ColumnClause)
                    and not execution.is_relationship_load and not execution.is_column_load
                    and (getattr(node,'is_literal',False) or getattr(node,'table',None) is not None and mapper is None)):
                raise HTTPException(403,'Payroll review cannot execute arbitrary SQL')
        # Effective-date/status filters remain native; result projections are
        # limited independently, including SQLAlchemy's generated relationship loads.
        for item in selections:
            expression=item.get('expr')
            if entity_model(expression) is not None:continue
            expression=expression.__clause_element__() if hasattr(expression,'__clause_element__') else expression
            for node in visitors.iterate(expression):
                mapper=node._annotations.get('parentmapper') or node._annotations.get('parententity')
                model=getattr(mapper,'class_',None)
                allowed=scalar.get(model) if model in scalar else set(thin[model]) if model in thin and thin[model] is not None else None
                if allowed is not None and getattr(node,'table',None) is not None and node.key not in allowed:
                    raise HTTPException(403,'Payroll review scalar projection is outside native metadata')
        added=list(options)
        for item in selections:
            model=entity_model(item.get('expr'))
            if model in thin and thin[model] is not None:
                added.append(load_only(*(getattr(item['entity'],key) for key in thin[model]),raiseload=True))
                if model is p.PayrollRecord:
                    added.append(defaultload(p.PayrollRecord.employee).load_only(*(getattr(Employee,key) for key in thin[Employee]),raiseload=True))
                    added.append(defaultload(p.PayrollRecord.components).load_only(*(getattr(p.PayrollComponent,key) for key in thin[p.PayrollComponent]),raiseload=True))
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
            reader._seal()
            _NATIVE_READS[reader]=(db,actor,scope,run_id,mode,check,present)
            stack.callback(lambda:_NATIVE_READS.pop(reader,None))
            event.listen(reader,'do_orm_execute',restrict)
            stack.callback(lambda:event.remove(reader,'do_orm_execute',restrict))
            if mode=='review':
                _COMPUTATIONS[reader]=(db,actor,scope,run_id,check,present)
                stack.callback(lambda:_COMPUTATIONS.pop(reader,None))
                from app.api.v1 import payroll_guided as native_guided
                result=native_guided.native_overview(run_id,reader,view)
            elif mode=='variance':
                from .payroll_variance import snapshot
                result=snapshot(reader,run_id,scope,check,present)
            else:
                from app.api.v1.payroll import native_payslip,_can_view_other_payslips
                if ((payslip['own_id'] is not None and getattr(view.employee,'id',None)!=payslip['own_id']) or _can_view_other_payslips(view)!=payslip['can_other']):
                    raise HTTPException(403,'Native payslip authority changed')
                result=native_payslip(payslip['month'],payslip['year'],payslip['employee_id'],reader,view)
                if result.get('id')!=payslip['record_id'] or result.get('payroll_run_id')!=run_id:
                    raise HTTPException(409,'Native payslip source changed; reload')

            current=reader.query(p.PayrollRun).filter(p.PayrollRun.id==run_id).one_or_none()
            if current is None or (current.id,current.month,current.year,current.company_id,current.branch_id,current.department_id,current.pay_group_id)!=identity:
                raise HTTPException(409,'Payroll source changed during review; reload')
            if reader.new or reader.deleted or any(reader.is_modified(row,include_collections=True) for row in reader.dirty):
                raise HTTPException(403,'Payroll review computation cannot modify its source')
            check()
            if mode=='review':result=_dto(result)
            if mode=='review' and (scope.branch.branch_id is None or scope.branch.branch_id not in scope.branch.writable):
                for key in ('can_process','can_review','can_approve'):result[key]=False
            return result
    finally:
        reader.close()
        if connection.get_transaction() is not transaction or connection.get_nested_transaction() is not nested:
            raise HTTPException(503,'Payroll review must retain its native transaction')


def salary_signature_rows(db,employee,run):
    """Fixed hash inputs only, never an ORM salary body or client data source."""
    lease=_COMPUTATIONS.get(db)
    if lease is None:return None
    outer,actor,scope,identity,check,present=lease;check()
    from app.models.payroll import EmployeeSalary,PayrollRun
    from app.models.employee import Employee
    from .models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    from app.branches.catalog import key_expression
    if (type(employee) is not Employee or type(run) is not PayrollRun or inspect(employee).session is not db
            or inspect(run).session is not db or run.id!=identity or not inspect(employee).persistent or not inspect(run).persistent
            or db.is_modified(employee,include_collections=True) or db.is_modified(run,include_collections=True)
            or db.query(Employee.id).filter(Employee.id==employee.id).first() is None
            or db.query(PayrollRun.id).filter(PayrollRun.id==run.id).first() is None):
        raise HTTPException(403,'Actual native payroll signature source required')
    if run.pay_period_start is None or run.pay_period_end is None:
        raise HTTPException(409,'Payroll signature period requires reconciliation')
    table=EmployeeSalary.__table__;owner=BranchOwnership.__table__;private=PackRecordOwnership.__table__
    unowned=~exists(select(1).where(private.c.resource_table==table.name,private.c.resource_key==key_expression(table))) if present else ~false()
    rows=outer.connection().execute(select(table.c.id,table.c.ctc,table.c.basic,table.c.hra,table.c.payroll_type,table.c.wage_rate,
        table.c.default_units,table.c.effective_from,table.c.effective_to).where(table.c.employee_id==employee.id,
        table.c.effective_from<=run.pay_period_end,or_(table.c.effective_to.is_(None),table.c.effective_to>=run.pay_period_start),
        exists(select(1).where(owner.c.resource_table==table.name,owner.c.resource_key==key_expression(table),owner.c.company_id==scope.company_id,
            owner.c.branch_id.in_(scope.branch.allowed))),
        unowned).order_by(table.c.id)).all()
    check()
    return [(row.id,str(row.ctc),str(row.basic),str(row.hra),row.payroll_type,str(row.wage_rate),str(row.default_units),str(row.effective_from),str(row.effective_to)) for row in rows]


def _variance_read_proof(db):
    lease=_NATIVE_READS.get(db)
    if lease is None:raise HTTPException(403,'Actual native variance reader required')
    outer,actor,scope,run_id,mode,check,present=lease;check()
    if mode!='variance' or scope.operation.purpose!='hrms.payroll_variance' or inspect(actor).session is not outer:
        raise HTTPException(403,'Actual native variance computation required')
    return lease


def variance_numeric_value(db,column,value):
    """Fixed backend Numeric cast only; never caller SQL or a connection."""
    from decimal import Decimal
    from sqlalchemy import cast,literal
    from app.models.payroll import PayrollVarianceItem
    outer,actor,scope,run_id,mode,check,present=_variance_read_proof(db)
    if (not any(column is item for item in PayrollVarianceItem.__table__.c)
            or getattr(column.type,'scale',None) is None or not isinstance(value,Decimal)
            or not value.is_finite() or abs(value)>=Decimal(10)**(column.type.precision-column.type.scale)):
        raise HTTPException(409,'Native variance numeric source requires reconciliation')
    result=outer.connection().scalar(select(cast(literal(value),column.type)))
    check();return result


def variance_private_previous_exists(db):
    """One blind existence bit for the actual reader's visible current run."""
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    from app.branches.catalog import key_expression
    from .models import PackRecordOwnership
    outer,actor,scope,run_id,mode,check,present=_variance_read_proof(db)
    current=db.query(PayrollRun).filter(PayrollRun.id==run_id,PayrollRun.deleted_at.is_(None)).one_or_none()
    if current is None:raise HTTPException(404,'Payroll run not found')
    employees=[row.employee_id for row in db.query(PayrollRecord.employee_id).filter(PayrollRecord.payroll_run_id==run_id).order_by(PayrollRecord.id)]
    if not present or not employees:return False
    month=12 if current.month==1 else current.month-1;year=current.year-1 if current.month==1 else current.year
    runs,records,owner,private=PayrollRun.__table__,PayrollRecord.__table__,BranchOwnership.__table__,PackRecordOwnership.__table__
    owned=exists(select(1).where(owner.c.resource_table==runs.name,owner.c.resource_key==key_expression(runs),
        owner.c.company_id==scope.company_id,owner.c.branch_id.in_(scope.branch.allowed),
        owner.c.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id==scope.company_id))))
    hidden=or_(exists(select(1).where(private.c.resource_table==runs.name,private.c.resource_key==key_expression(runs))),
        exists(select(1).where(private.c.resource_table==records.name,private.c.resource_key==key_expression(records))))
    result=outer.connection().execute(select(records.c.id).join(runs,runs.c.id==records.c.payroll_run_id).where(
        records.c.employee_id.in_(employees),runs.c.month==month,runs.c.year==year,runs.c.deleted_at.is_(None),
        or_(runs.c.company_id==scope.company_id,runs.c.company_id.is_(None)),owned,hidden).limit(1)).first() is not None
    check();return result
