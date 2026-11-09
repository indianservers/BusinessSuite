"""Executable coverage for POL-01..04 and NA-01..02 with explicit policy oracles."""
import calendar
from copy import deepcopy
from datetime import date,datetime,timezone
from decimal import Decimal as D,ROUND_HALF_EVEN
import pytest
from fastapi import HTTPException
from app.crud import crud_payroll
from app.models.employee import Employee
from app.models.user import User
from app.models.attendance import Attendance,Holiday
from app.models.leave import LeaveType,LeaveRequest
from app.models.payroll import EmployeeSalary,PayrollPolicyVersion,PayrollPayGroup,PayrollAttendanceInput,PayrollRecord,SalaryComponent,SalaryStructure,SalaryStructureComponent
from app.schemas.payroll_policy import PayrollPolicyRules,PayrollPolicyCreate
from app.services.payroll_policy import evaluate_days,active_policy,approval_blockers
from tests.payroll_test_utils import init_payroll_test_db,ensure_payroll_ready,commit_payroll_fixture


def fixture(db,month=5,year=2026,**changes):
    init_payroll_test_db(db)
    employee=db.query(Employee).filter_by(employee_id='DEMO-EMP-001').one();employee.date_of_joining=date(2020,1,1);employee.date_of_exit=None;employee.functional_area='QA-POLICY'
    for old in db.query(EmployeeSalary).filter_by(employee_id=employee.id).all():old.is_active=False;old.effective_to=date(2019,12,31)
    salary=EmployeeSalary(employee_id=employee.id,ctc=D(360000),basic=D(12000),hra=D(6000),effective_from=date(2020,1,1),is_active=True)
    db.add(salary);commit_payroll_fixture(db)
    period=ensure_payroll_ready(db,month,year,[employee]);period.status='Open'
    group=db.get(PayrollPayGroup,period.pay_group_id);group.working_pattern='5_day';group.working_days_per_week=5
    rules=PayrollPolicyRules().model_dump();rules.update(changes)
    actor=db.query(User).filter_by(email='admin@aihrms.com').one()
    row=PayrollPolicyVersion(pay_group_id=group.id,effective_from=date(year,month,1),rules=rules,reason='QA configured payroll policy',created_by=actor.id)
    db.add(row);commit_payroll_fixture(db)
    return employee,group,period,salary,actor,active_policy(db,group,period.period_start)


def leave(db,employee,start,end=None,paid=False,half=False,part='First Half'):
    code='QA-POL-PAID' if paid else 'QA-POL-LOP'
    kind=db.query(LeaveType).filter_by(code=code).first()
    if not kind:
        kind=LeaveType(code=code,name='QA Paid' if paid else 'QA Unpaid',days_allowed=40);db.add(kind);db.flush()
    row=LeaveRequest(employee_id=employee.id,leave_type_id=kind.id,from_date=start,to_date=end or start,days_count=D('.5') if half else D(((end or start)-start).days+1),is_half_day=half,half_day_period=part,status='Approved')
    db.add(row);db.flush();return row


def manual(db,employee,period,lop,work=None,note='QA HR attendance resolution'):
    work=work if work is not None else sum(date(period.year,period.month,day).weekday()<5 for day in range(1,calendar.monthrange(period.year,period.month)[1]+1))
    item=PayrollAttendanceInput(period_id=period.id,employee_id=employee.id,working_days=work,payable_days=D(work)-D(lop),present_days=D(work)-D(lop),lop_days=D(lop),source_status='Approved',locked_at=datetime.now(timezone.utc),policy_trace={'source':'manual','resolution_note':note})
    db.add(item);commit_payroll_fixture(db);return item


def generate(db,employee,group,period,actor):
    return crud_payroll.run_payroll(db,period.month,period.year,actor.id,force_run=True,pay_group_id=group.id,company_id=employee.branch.company_id,branch_id=employee.branch_id,employee_category='QA-POLICY')


@pytest.mark.parametrize('weekly',[False,True])
@pytest.mark.parametrize('holiday',[False,True])
@pytest.mark.parametrize('sandwich',[False,True])
def test_nonworking_and_sandwich_combinations(db,weekly,holiday,sandwich,record_property):
    employee,group,period,_,_,policy=fixture(db,charge_weekly_off=weekly,charge_holidays=holiday,sandwich_enabled=sandwich,missing_attendance='payable')
    db.add(Holiday(name='QA Monday holiday',holiday_date=date(2026,5,11),is_active=True))
    leave(db,employee,date(2026,5,8),date(2026,5,12));commit_payroll_fixture(db)
    actual=evaluate_days(db,employee,period.period_start,period.period_end,group,policy)
    expected=D(2)+(D(2) if weekly or sandwich else 0)+(D(1) if holiday or sandwich else 0)
    record_property('expected',str(expected));record_property('actual',str(actual['lop_days']))
    assert actual['lop_days']==expected


@pytest.mark.parametrize('enabled,half,expected',[(False,False,'2'),(True,False,'4'),(True,True,'1')])
def test_sandwich_inferred_only_between_full_unpaid_workdays(db,enabled,half,expected):
    employee,group,period,_,_,policy=fixture(db,sandwich_enabled=enabled,missing_attendance='payable')
    leave(db,employee,date(2026,5,8),half=half);leave(db,employee,date(2026,5,11),half=half);commit_payroll_fixture(db)
    assert evaluate_days(db,employee,period.period_start,period.period_end,group,policy)['lop_days']==D(expected)


def test_sandwich_crosses_month_boundary(db):
    employee,group,period,_,_,policy=fixture(db,sandwich_enabled=True,missing_attendance='payable')
    leave(db,employee,date(2026,5,29));leave(db,employee,date(2026,6,1));commit_payroll_fixture(db)
    assert evaluate_days(db,employee,period.period_start,period.period_end,group,policy)['lop_days']==3


@pytest.mark.parametrize('mode',['block','payable','lop'])
@pytest.mark.parametrize('half_present',[False,True])
def test_missing_attendance_policy(db,mode,half_present):
    employee,group,period,_,_,policy=fixture(db,missing_attendance=mode)
    if half_present:db.add(Attendance(employee_id=employee.id,attendance_date=date(2026,5,4),status='Half-day'));commit_payroll_fixture(db)
    result=evaluate_days(db,employee,period.period_start,period.period_end,group,policy)
    assert result['missing_days']==D('20.5') if half_present else result['missing_days']==D(21)
    assert bool(result['blockers'])==(mode=='block')
    assert bool(result['warnings'])==(mode=='payable')
    assert result['lop_days']==(result['missing_days'] if mode=='lop' else D(0))


@pytest.mark.parametrize('mode,expected,blocked',[('block','0',True),('paid_wins','0',False),('unpaid_wins','.5',False)])
def test_conflicting_paid_unpaid_half_day(db,mode,expected,blocked):
    employee,group,period,_,_,policy=fixture(db,missing_attendance='payable',leave_conflict=mode)
    leave(db,employee,date(2026,5,4),paid=True,half=True);leave(db,employee,date(2026,5,4),half=True);commit_payroll_fixture(db)
    result=evaluate_days(db,employee,period.period_start,period.period_end,group,policy)
    assert result['lop_days']==D(expected);assert bool(result['blockers'])==blocked


@pytest.mark.parametrize('paid,expected',[(True,'0'),(False,'.5')])
def test_half_leave_and_half_attendance_make_one_covered_day(db,paid,expected):
    employee,group,period,_,_,policy=fixture(db,missing_attendance='payable')
    db.add(Attendance(employee_id=employee.id,attendance_date=date(2026,5,4),status='Half-day'))
    leave(db,employee,date(2026,5,4),paid=paid,half=True);commit_payroll_fixture(db)
    result=evaluate_days(db,employee,period.period_start,period.period_end,group,policy)
    assert result['lop_days']==D(expected);assert not result['blockers']


@pytest.mark.parametrize('year,month',[(2025,2),(2024,2),(2026,4),(2026,5)])
@pytest.mark.parametrize('mode',['working_days','calendar_days','fixed_26','fixed_30'])
def test_divisor_calculation_with_independent_oracle(db,year,month,mode,record_property):
    employee,group,period,_,actor,_=fixture(db,month,year,lop_divisor=mode)
    length=calendar.monthrange(year,month)[1];work=sum(date(year,month,day).weekday()<5 for day in range(1,length+1))
    manual(db,employee,period,D('1.5'),work)
    run=generate(db,employee,group,period,actor)
    actual=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one().gross_salary
    denominator=D(26) if mode=='fixed_26' else D(30) if mode=='fixed_30' else D(length) if mode=='calendar_days' else D(work)
    # Three independently rounded component amounts (12k / 6k / 12k).
    expected=sum((max(D(0),base-base*D('1.5')/denominator).quantize(D('.01'),rounding=ROUND_HALF_EVEN) for base in (D(12000),D(6000),D(12000))),D(0))
    record_property('expected',str(expected));record_property('actual',str(actual))
    assert actual==expected


@pytest.mark.parametrize('mode',['working_days','calendar_days','fixed_26','fixed_30'])
@pytest.mark.parametrize('basis',['calendar_days','working_days'])
def test_joining_proration_divisor_and_basis(db,mode,basis):
    employee,group,period,_,actor,_=fixture(db,proration_divisor=mode,proration_basis=basis,missing_attendance='payable')
    employee.date_of_joining=date(2026,5,16);commit_payroll_fixture(db)
    run=generate(db,employee,group,period,actor)
    actual=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one().gross_salary
    denominator=D(26) if mode=='fixed_26' else D(30) if mode=='fixed_30' else D(31) if mode=='calendar_days' else D(21)
    factor=min(D(1),D(10 if basis=='working_days' else 16)/denominator)
    expected=sum(((value*factor).quantize(D('.01'),rounding=ROUND_HALF_EVEN) for value in (D(12000),D(6000),D(12000))),D(0))
    assert actual==expected


@pytest.mark.parametrize('prorate',[False,True])
@pytest.mark.parametrize('lop',[False,True])
def test_core_component_treatment(db,prorate,lop):
    rules=PayrollPolicyRules().model_dump();rules['components']['basic']={'prorate':prorate,'lop':lop}
    employee,group,period,_,actor,_=fixture(db,components=rules['components'])
    employee.date_of_joining=date(2026,5,16);commit_payroll_fixture(db);manual(db,employee,period,D('.5'),10)
    run=generate(db,employee,group,period,actor);record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    expected=(D(12000)*(D(16)/31 if prorate else 1)).quantize(D('.01'))
    if lop:expected=(expected*D('.95')).quantize(D('.01'))
    assert record.basic==expected


def test_assigned_component_flags_and_payslip_reconcile(db):
    employee,group,period,salary,actor,_=fixture(db)
    structure=SalaryStructure(name='QA policy structure');db.add(structure);db.flush()
    for code,amount,loss in [('BASIC',12000,True),('HRA',6000,False),('OTHER',12000,True)]:
        component=SalaryComponent(name=code,code='QA-'+code,component_type='Earning',pro_rata_rule='Calendar Days',lop_applicable=loss)
        db.add(component);db.flush();db.add(SalaryStructureComponent(structure_id=structure.id,component_id=component.id,amount=amount))
    salary.structure_id=structure.id;commit_payroll_fixture(db);manual(db,employee,period,1)
    run=generate(db,employee,group,period,actor);record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    expected=D(6000)+2*(D(12000)*D(20)/21).quantize(D('.01'))
    assert record.gross_salary==expected
    assert record.basic==(D(12000)*D(20)/21).quantize(D('.01'))
    assert record.hra==6000
    assert sum((line.amount for line in record.components if line.component_type=='Earning'),D(0))==record.gross_salary


def test_missing_component_configuration_blocks_even_force_approve(db):
    from app.api.v1.payroll import approve_payroll
    from app.schemas.payroll import PayrollRunApproval
    employee,group,period,salary,actor,_=fixture(db,missing_attendance='payable')
    structure=SalaryStructure(name='QA incomplete structure');db.add(structure);db.flush()
    component=SalaryComponent(name='Unknown',code='QA-UNKNOWN',component_type='Earning',pro_rata_rule='Unconfigured',lop_applicable=True)
    db.add(component);db.flush();db.add(SalaryStructureComponent(structure_id=structure.id,component_id=component.id,amount=30000));salary.structure_id=structure.id
    commit_payroll_fixture(db);manual(db,employee,period,0)
    run=generate(db,employee,group,period,actor)
    with pytest.raises(HTTPException) as error:approve_payroll(run.id,PayrollRunApproval(action='approve',force_approve=True),db,actor)
    assert error.value.status_code==400
    assert 'Missing proration' in str(error.value.detail)
    component.pro_rata_rule='Calendar Days';db.commit()
    generate(db,employee,group,period,actor)
    assert not approval_blockers(db,run)


def test_reconciled_missing_attendance_cannot_be_force_approved(db):
    from app.api.v1.payroll import reconcile_payroll_attendance_inputs,approve_payroll
    from app.schemas.payroll import PayrollAttendanceReconcileRequest,PayrollRunApproval
    employee,group,period,_,actor,_=fixture(db)
    reconcile_payroll_attendance_inputs(PayrollAttendanceReconcileRequest(period_id=period.id,employee_ids=[employee.id],approve_inputs=True),db,actor)
    run=generate(db,employee,group,period,actor)
    assert approval_blockers(db,run)
    with pytest.raises(HTTPException):approve_payroll(run.id,PayrollRunApproval(action='approve',force_approve=True),db,actor)


def test_policy_snapshot_and_regeneration_requirement(db):
    employee,group,period,_,actor,_=fixture(db,missing_attendance='payable')
    item=manual(db,employee,period,1)
    run=generate(db,employee,group,period,actor);original=deepcopy(run.policy_snapshot)
    rules=PayrollPolicyRules(lop_divisor='fixed_30',missing_attendance='lop').model_dump()
    db.add(PayrollPolicyVersion(pay_group_id=group.id,effective_from=date(2026,6,1),rules=rules,reason='Future test version',created_by=actor.id));db.commit()
    item.lop_days=D(2);db.commit()
    assert any('regenerate' in value for value in approval_blockers(db,run))
    generate(db,employee,group,period,actor)
    assert run.policy_snapshot['groups']==original['groups']
    assert not approval_blockers(db,run)


@pytest.mark.parametrize('field,value',[('missing_attendance','guess'),('leave_conflict','latest'),('lop_divisor','fixed_31'),('proration_divisor','zero'),('components',{})])
def test_invalid_policy_options_rejected(field,value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):PayrollPolicyRules(**{field:value})


def test_policy_api_permissions_versioning_and_history(client,db):
    init_payroll_test_db(db)
    actor=db.query(User).filter_by(email='admin@aihrms.com').one()
    employee=db.query(Employee).filter_by(employee_id='DEMO-EMP-001').one()
    login=client.post('/api/v1/auth/login',json={'email':actor.email,'password':'Admin@123456'}).json()
    headers={'Authorization':'Bearer '+login['access_token'],'X-Suite-Organization':str(employee.branch.company_id),'X-Suite-Branch':str(employee.branch_id)}
    group=client.post('/api/v1/payroll/setup/pay-groups',json={'name':'QA policy API','code':'QA-POLICY-API'},headers=headers)
    assert group.status_code==201,group.text
    url=f"/api/v1/payroll/setup/pay-groups/{group.json()['id']}/policies"
    payload={'effective_from':'2027-01-01','reason':'Approved recommended defaults','rules':PayrollPolicyRules().model_dump()}
    created=client.post(url,json=payload,headers=headers);assert created.status_code==201,created.text
    assert client.post(url,json=payload,headers=headers).status_code==409
    payload['effective_from']='2027-02-15';assert client.post(url,json=payload,headers=headers).status_code==422
    user=client.post('/api/v1/auth/login',json={'email':'employee@aihrms.com','password':'Employee@123456'}).json()
    assert client.post(url,json={**payload,'effective_from':'2027-02-01'},headers={**headers,'Authorization':'Bearer '+user['access_token']}).status_code==403
    history=client.get(url,headers=headers);assert history.status_code==200
    assert len(history.json()['versions'])==1
    assert history.json()['versions'][0]['rules']['missing_attendance']=='block'


@pytest.mark.parametrize('pattern,days_per_week,expected',[('5_day',5,'2'),('6_day',6,'3'),('company',7,'4')])
def test_policy_uses_configured_working_calendar(db,pattern,days_per_week,expected):
    employee,group,period,_,_,policy=fixture(db,missing_attendance='payable')
    group.working_pattern=pattern;group.working_days_per_week=days_per_week
    leave(db,employee,date(2026,5,8),date(2026,5,11));commit_payroll_fixture(db)
    assert evaluate_days(db,employee,period.period_start,period.period_end,group,policy)['lop_days']==D(expected)


def test_sandwich_crosses_year_and_holiday(db):
    employee,group,period,_,_,policy=fixture(db,1,2027,sandwich_enabled=True,missing_attendance='payable')
    db.add(Holiday(name='QA New Year',holiday_date=date(2027,1,1),is_active=True))
    leave(db,employee,date(2026,12,31));leave(db,employee,date(2027,1,4));commit_payroll_fixture(db)
    assert evaluate_days(db,employee,period.period_start,period.period_end,group,policy)['lop_days']==4


@pytest.mark.parametrize('prorate',[False,True])
@pytest.mark.parametrize('lop',[False,True])
def test_incentive_and_reimbursement_treatment(db,prorate,lop):
    from app.models.payroll import PayrollManualInput,Reimbursement
    config=PayrollPolicyRules().model_dump();config['components']['incentives']={'prorate':prorate,'lop':lop};config['components']['reimbursements']={'prorate':prorate,'lop':lop}
    employee,group,period,_,actor,_=fixture(db,components=config['components'])
    employee.date_of_joining=date(2026,5,16);commit_payroll_fixture(db);manual(db,employee,period,1,10)
    run=generate(db,employee,group,period,actor)
    db.add(PayrollManualInput(payroll_run_id=run.id,employee_id=employee.id,input_type='Bonus',component_name='QA incentive',amount=3100,status='Approved'))
    db.add(Reimbursement(employee_id=employee.id,category='QA reimbursement',amount=775,date=date(2026,5,20),status='Approved'))
    commit_payroll_fixture(db);generate(db,employee,group,period,actor)
    record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    factor=D(16)/31 if prorate else D(1)
    expected_bonus=(D(3100)*factor).quantize(D('.01'))
    expected_reimbursement=(D(775)*factor).quantize(D('.01'))
    if lop:expected_bonus=(expected_bonus*D('.9')).quantize(D('.01'));expected_reimbursement=(expected_reimbursement*D('.9')).quantize(D('.01'))
    assert record.bonus==expected_bonus
    assert record.reimbursements==expected_reimbursement
    assert record.net_salary==record.gross_salary-record.total_deductions+expected_reimbursement


def test_component_mapping_override_and_snapshot(db):
    config=PayrollPolicyRules(use_component_flags=False).model_dump();config['components']['qa_custom']={'prorate':False,'lop':False}
    employee,group,period,salary,actor,_=fixture(db,**config)
    structure=SalaryStructure(name='QA mapped structure');db.add(structure);db.flush()
    component=SalaryComponent(name='QA custom',code='QA_CUSTOM',component_type='Earning',pro_rata_rule='Unknown',lop_applicable=True)
    db.add(component);db.flush();db.add(SalaryStructureComponent(structure_id=structure.id,component_id=component.id,amount=30000));salary.structure_id=structure.id
    commit_payroll_fixture(db);manual(db,employee,period,1)
    run=generate(db,employee,group,period,actor)
    record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one();assert record.gross_salary==30000
    component.lop_applicable=False;component.pro_rata_rule='No Proration';db.commit();generate(db,employee,group,period,actor)
    assert not approval_blockers(db,run)


def test_policy_read_and_publish_cannot_cross_company(client,db):
    from app.models.company import Company,Branch
    employee,group,period,_,_,_=fixture(db)
    from test_identity_utils import attach_test_identity,attach_workflow_branch
    from app.models.user import Role
    from app.core.security import get_password_hash
    company=Company(name='QA other policy company');db.add(company);db.flush()
    branch=Branch(company_id=company.id,name='QA other branch');role=Role(name='qa_policy_outsider')
    db.add_all([branch,role]);db.flush()
    outsider=User(email='qa-policy-outside@example.com',hashed_password=get_password_hash('QApolicy@12345'),is_active=True,is_superuser=True,role_id=role.id)
    db.add(outsider);attach_test_identity(db,outsider,company_id=company.id);db.flush()
    from app.branches.models import BranchGrant
    db.add(BranchGrant(company_id=company.id,user_id=outsider.id,branch_id=branch.id,can_write=True));db.commit()
    login=client.post('/api/v1/auth/login',json={'email':outsider.email,'password':'QApolicy@12345'}).json()
    headers={'Authorization':'Bearer '+login['access_token'],'X-Suite-Organization':str(company.id),'X-Suite-Branch':str(branch.id)}
    url=f'/api/v1/payroll/setup/pay-groups/{group.id}/policies'
    assert client.get(url,headers=headers).status_code in {403,404}
    assert client.post(url,json={'effective_from':'2027-01-01','reason':'Must not cross companies','rules':PayrollPolicyRules().model_dump()},headers=headers).status_code in {403,404}


@pytest.mark.parametrize('mode,unpaid_day,expected',[('daily',None,'21000'),('daily',date(2026,5,4),'20000'),('daily',date(2026,5,9),'21000'),('hourly',None,'2000')])
def test_monthly_nonworking_policy_does_not_invent_wage_units(db,mode,unpaid_day,expected):
    employee,group,period,salary,actor,_=fixture(db,charge_weekly_off=True,charge_holidays=True,missing_attendance='payable')
    salary.payroll_type=mode;salary.wage_rate=1000;salary.default_units=2
    if unpaid_day:leave(db,employee,unpaid_day)
    commit_payroll_fixture(db)
    run=generate(db,employee,group,period,actor)
    record=db.query(PayrollRecord).filter_by(payroll_run_id=run.id,employee_id=employee.id).one()
    assert record.gross_salary==D(expected)
    assert record.working_days==21
