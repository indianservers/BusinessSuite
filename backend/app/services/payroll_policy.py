"""Effective-dated payroll policy evaluation shared by engine, feeds and approval."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
from sqlalchemy import func
from app.models.payroll import PayrollPolicyVersion, PayrollRun, PayrollRecord, EmployeeSalary
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.services.payroll_leave_intervals import add_leave_intervals

D=Decimal


def money(value):
    return D(value).quantize(D('.01'),rounding=ROUND_HALF_EVEN)


def active_policy(db, group, start):
    if group is None:return None
    row=db.query(PayrollPolicyVersion).filter(PayrollPolicyVersion.pay_group_id==group.id,PayrollPolicyVersion.effective_from<=start).order_by(PayrollPolicyVersion.effective_from.desc(),PayrollPolicyVersion.id.desc()).first()
    return {'version_id':row.id,'pay_group_id':group.id,'effective_from':row.effective_from.isoformat(),'rules':deepcopy(row.rules)} if row else None


def run_policy(db,run,group,start):
    from app.models.payroll import PayrollPayGroup
    if group is not None:db.query(PayrollPayGroup).filter_by(id=group.id).with_for_update().one()
    snapshot=deepcopy(run.policy_snapshot) if run.policy_snapshot is not None else {'schema':1,'groups':{},'components':{}}
    key=str(group.id if group else 0)
    if key not in snapshot['groups']:
        snapshot['groups'][key]=active_policy(db,group,start)
        run.policy_snapshot=snapshot
    return snapshot['groups'][key]


def _unpaid(leave):
    kind=leave.leave_type
    marker=f'{kind.name if kind else ""} {kind.code if kind else ""}'.lower()
    return any(part in marker for part in ('lop','lwp','loss of pay','unpaid','without pay'))


def evaluate_days(db,employee,start,end,group,policy,attendance_input=None,include_absence=True):
    from app.crud.crud_payroll import _holiday_dates_for_employee,_is_weekly_off,_attendance_day_value
    rules=policy['rules']
    start=max(start,employee.date_of_joining or start);end=min(end,employee.date_of_exit or end)
    if end<start:return dict(working_days=D(0),scheduled_days=D(0),present_days=D(0),paid_leave_days=D(0),unpaid_leave_days=D(0),lop_days=D(0),payable_days=D(0),missing_days=D(0),conflict_days=D(0),blockers=[],sandwich_days=D(0))
    look_start=start-timedelta(days=31);look_end=end+timedelta(days=31)
    holidays=_holiday_dates_for_employee(db,employee,look_start,look_end)
    paid,unpaid={},{}
    for leave in db.query(LeaveRequest).filter(LeaveRequest.employee_id==employee.id,LeaveRequest.status=='Approved',LeaveRequest.deleted_at.is_(None),LeaveRequest.from_date<=look_end,LeaveRequest.to_date>=look_start).all():
        add_leave_intervals(unpaid if _unpaid(leave) else paid,leave,look_start,look_end)
    present,absent={},set()
    for row in db.query(Attendance).filter(Attendance.employee_id==employee.id,Attendance.attendance_date>=start,Attendance.attendance_date<=end).all():
        present[row.attendance_date]=max(present.get(row.attendance_date,D(0)),_attendance_day_value(row.status))
        if row.status in {'Absent','LWP','Leave Without Pay'}:absent.add(row.attendance_date)
    def scheduled(day):return day not in holidays and not _is_weekly_off(db,employee,day,group)
    def full_unpaid(day):return len(unpaid.get(day,set())-(set() if rules['leave_conflict']=='unpaid_wins' else paid.get(day,set())))==2
    def bridge(day):
        if not rules['sandwich_enabled'] or scheduled(day):return False
        before,after=day,day
        for _ in range(32):
            before-=timedelta(days=1)
            if scheduled(before):break
        for _ in range(32):
            after+=timedelta(days=1)
            if scheduled(after):break
        return (not employee.date_of_joining or before>=employee.date_of_joining) and (not employee.date_of_exit or after<=employee.date_of_exit) and scheduled(before) and scheduled(after) and full_unpaid(before) and full_unpaid(after)
    totals={key:D(0) for key in ('working_days','scheduled_days','scheduled_lop_days','scheduled_payable_days','present_days','paid_leave_days','unpaid_leave_days','lop_days','payable_days','missing_days','conflict_days','sandwich_days')}
    day=start
    while day<=end:
        work=scheduled(day)
        if work:totals['scheduled_days']+=1
        is_bridge=bridge(day)
        eligible=work or (day in holidays and rules['charge_holidays']) or (day not in holidays and rules['charge_weekly_off'] and _is_weekly_off(db,employee,day,group)) or is_bridge
        if eligible:
            totals['working_days']+=1
            p,u=paid.get(day,set()),unpaid.get(day,set())
            conflict=D(len(p & u))/2
            if rules['leave_conflict']=='unpaid_wins':p=p-u
            else:u=u-p
            p_days,u_days=D(len(p))/2,D(len(u))/2
            presence=present.get(day,D(0))
            # Approved unpaid leave with excess present attendance is also a conflict.
            conflict=max(conflict,min(u_days,max(D(0),presence+p_days+u_days-1)))
            if rules['leave_conflict']=='paid_wins':u_days=max(D(0),min(u_days,1-presence-p_days))
            explicit_absence=max(D(0),1-p_days-u_days-presence) if day in absent and include_absence else D(0)
            missing=max(D(0),1-min(D(1),presence+p_days+u_days+explicit_absence)) if work else D(0)
            loss=u_days+explicit_absence+(missing if rules['missing_attendance']=='lop' else D(0))
            if is_bridge:
                loss=D(1);totals['sandwich_days']+=1
            totals['present_days']+=presence
            totals['paid_leave_days']+=p_days
            totals['unpaid_leave_days']+=u_days
            totals['lop_days']+=min(D(1),loss)
            if work:totals['scheduled_lop_days']+=min(D(1),loss)
            totals['missing_days']+=missing
            totals['conflict_days']+=conflict
        day+=timedelta(days=1)
    # An explicitly approved manual payroll input with an audited resolution
    # note is an HR resolution of missing attendance, never of conflicting leave.
    trace=getattr(attendance_input,'policy_trace',None) or {}
    manual_resolution=attendance_input is not None and trace.get('source')=='manual' and trace.get('resolution_note') and attendance_input.source_status in {'Approved','Locked'}
    if manual_resolution:
        totals['lop_days']=min(totals['working_days'],D(attendance_input.lop_days or 0))
        totals['scheduled_lop_days']=min(totals['scheduled_days'],D(attendance_input.lop_days or 0))
        totals['missing_days']=D(0)
    from app.models.payroll import LOPAdjustment,PayrollPeriod
    adjustments=db.query(LOPAdjustment).join(PayrollPeriod).filter(PayrollPeriod.month==start.month,PayrollPeriod.year==start.year,LOPAdjustment.employee_id==employee.id,LOPAdjustment.status=='Approved')
    if group is not None:adjustments=adjustments.filter(PayrollPeriod.pay_group_id==group.id)
    manual=D(0) if manual_resolution else sum((D(row.adjustment_days or 0) for row in adjustments.all()),D(0))
    totals['lop_days']=min(totals['working_days'],max(D(0),totals['lop_days']+manual))
    totals['payable_days']=max(D(0),totals['working_days']-totals['lop_days'])
    totals['scheduled_lop_days']=min(totals['scheduled_days'],max(D(0),totals['scheduled_lop_days']+manual))
    totals['scheduled_payable_days']=totals['scheduled_days']-totals['scheduled_lop_days']
    totals['present_days']=min(totals['present_days'],totals['working_days'])
    blockers=[]
    warnings=[]
    if rules['missing_attendance']=='block' and totals['missing_days']>0:blockers.append(f"Unresolved attendance: {totals['missing_days']} day(s)")
    if rules['leave_conflict']=='block' and totals['conflict_days']>0:blockers.append(f"Conflicting leave/attendance: {totals['conflict_days']} day(s)")
    if rules['missing_attendance']=='payable' and totals['missing_days']>0:warnings.append(f"Missing attendance remains payable under policy: {totals['missing_days']} day(s)")
    if rules['leave_conflict']!='block' and totals['conflict_days']>0:warnings.append(f"Conflicting intervals resolved by {rules['leave_conflict']}: {totals['conflict_days']} day(s)")
    totals['blockers']=blockers
    totals['warnings']=warnings
    return totals


def calculation_signature(db,employee,run,checks):
    from app.models.payroll import PayrollManualInput
    manual=db.query(PayrollManualInput).filter_by(payroll_run_id=run.id,employee_id=employee.id,status='Approved').order_by(PayrollManualInput.id).all()
    salaries=db.query(EmployeeSalary).filter(EmployeeSalary.employee_id==employee.id,EmployeeSalary.effective_from<=run.pay_period_end,(EmployeeSalary.effective_to.is_(None)) | (EmployeeSalary.effective_to>=run.pay_period_start)).order_by(EmployeeSalary.id).all()
    payload={'checks':checks,'manual':[(row.id,row.input_type,row.component_name,str(row.amount)) for row in manual],
        'salaries':[(row.id,str(row.ctc),str(row.basic),str(row.hra),row.payroll_type,str(row.wage_rate),str(row.default_units),str(row.effective_from),str(row.effective_to)) for row in salaries]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def divisor(mode,calendar_days,working_days):
    return D(26) if mode=='fixed_26' else D(30) if mode=='fixed_30' else D(calendar_days) if mode=='calendar_days' else D(working_days)


def proration_factor(rules,calendar_days,employed_days,working_days,employed_working_days,basis=None):
    if D(employed_days)>=D(calendar_days):return D(1)
    basis=basis or rules['proration_basis']
    mode=rules['proration_divisor']
    # Component calendar/working metadata applies unless a fixed group divisor overrides it.
    if mode not in {'fixed_26','fixed_30'} and basis!=rules['proration_basis']:mode=basis
    denominator=divisor(mode,calendar_days,working_days)
    numerator=D(employed_working_days) if basis=='working_days' else D(employed_days)
    return min(D(1),max(D(0),numerator/denominator)) if denominator else D(0)


def component_templates(db,salary,policy):
    from app.models.payroll import SalaryStructure
    from app.services.payroll_component_engine import _ordered_structure_components
    rules=policy['rules'];errors=[];templates=[]
    structure=db.get(SalaryStructure,salary.structure_id) if salary.structure_id else None
    if structure:
        try:items,_=_ordered_structure_components(structure)
        except Exception as error:return [],[f'Invalid salary component dependencies: {error}']
        for item in items:
            component=item.component
            if component.component_type!='Earning':continue
            key=component.code.lower()
            treatment=rules['components'].get(key)
            if rules['use_component_flags']:
                raw=(component.pro_rata_rule or '').strip().lower()
                if raw in {'calendar days','working days'}:treatment={'prorate':True,'lop':component.lop_applicable,'basis':raw.replace(' ','_')}
                elif raw in {'none','no proration','never','fixed'}:treatment={'prorate':False,'lop':component.lop_applicable}
                else:treatment=None
                if component.lop_applicable is None:treatment=None
            if treatment is None:errors.append(f'Missing proration/LOP configuration for component {component.code}');continue
            templates.append({'key':key,'name':component.name,'component_id':component.id,**dict(treatment)})
    else:
        templates=[{'key':key,'name':name,**rules['components'][key]} for key,name in [('basic','Basic'),('hra','House Rent Allowance'),('other_allowances','Other Allowances')]]
    return templates,errors


def monthly_components(db,salary,policy,templates,monthly,basic,hra,factor,lop_ratio,context):
    from app.models.payroll import SalaryStructure
    from app.services.payroll_component_engine import _ordered_structure_components,_component_monthly_amount
    amounts={'basic':basic,'hra':hra,'other_allowances':monthly-basic-hra}
    if salary.structure_id:
        structure=db.get(SalaryStructure,salary.structure_id)
        items,_=_ordered_structure_components(structure)
        amounts={};variables={'basic':basic,'gross':monthly}
        for item in items:
            if item.component.component_type!='Earning':continue
            amount=_component_monthly_amount(item,monthly,variables)
            amounts[item.component.code.lower()]=amount;variables[item.component.code]=amount
        residual=monthly-sum(amounts.values(),D(0))
        if residual>0:
            amounts['__residual']=residual
            templates=[*templates,{'key':'__residual','name':'Other Allowances',**policy['rules']['components']['other_allowances']}]
    before=[];after=[]
    for template in templates:
        value=amounts.get(template['key'],D(0))
        ratio=proration_factor(policy['rules'],**context,basis=template.get('basis')) if template['prorate'] else D(1)
        prorated=money(value*ratio)
        loss_base=prorated if policy['rules']['lop_divisor']=='working_days' else value
        earned=money(max(D(0),prorated-loss_base*lop_ratio)) if template['lop'] else prorated
        before.append(prorated);after.append((template['name'],earned,template['key']))
    return after,sum(before,D(0))-sum((line[1] for line in after),D(0))


def approval_blockers(db,run):
    from app.crud.crud_payroll import _active_pay_group
    from app.models.payroll import PayrollAttendanceInput,PayrollPeriod,PayrollPayGroup
    snapshot=run.policy_snapshot or {};result=[]
    for record in db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id==run.id).all():
        employee=db.get(Employee,record.employee_id)
        group=_active_pay_group(db,run.pay_group_id,employee)
        group_key=snapshot.get('employee_groups',{}).get(str(employee.id))
        if group_key and group_key!='0':group=db.get(PayrollPayGroup,int(group_key))
        policy=snapshot.get('groups',{}).get(str(group.id if group else 0))
        if not policy:continue
        start,end=run.pay_period_start,run.pay_period_end
        input_query=db.query(PayrollAttendanceInput).join(PayrollPeriod).filter(PayrollPeriod.month==run.month,PayrollPeriod.year==run.year,PayrollAttendanceInput.employee_id==employee.id)
        if group is not None:input_query=input_query.filter(PayrollPeriod.pay_group_id==group.id)
        item=input_query.order_by(PayrollAttendanceInput.id.desc()).first()
        checks=evaluate_days(db,employee,start,end,group,policy,item)
        errors=snapshot.get('components',{}).get(str(employee.id),{}).get('errors',[])
        result += [f'Employee {employee.id}: {message}' for message in checks['blockers']+errors]
        prior=snapshot.get('checks',{}).get(str(employee.id))
        if prior and prior!=calculation_signature(db,employee,run,checks):result.append(f'Employee {employee.id}: attendance, leave or approved earnings changed; regenerate payroll')
    return result
