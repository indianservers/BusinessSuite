from tests.rich_text_test_utils import organization_context
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from tests.test_settings_hub import actor
from app.models.company import Company, Branch, Department, WorkLocation
from app.models.employee import Employee, ProbationReview
from app.models.attendance import Attendance
from app.models.leave import LeaveType, LeaveBalance, LeaveRequest
from app.models.payroll import PayrollRun, PayrollRecord
from app.models.onboarding import EmployeeOnboarding, EmployeeOnboardingTask
from app.models.document import EmployeeCertificate
from app.models.exit import ExitRecord, ExitChecklistItem

BASE = "/api/v1/reports/hrms-dashboard"


@pytest.fixture
def dashboard_people(db):
    headers, user = actor(db, role="dashboard-admin", superuser=True)
    company=db.get(Company,1);company.default_currency="USD";company.default_timezone="Asia/Kolkata"
    db.add(Company(id=77,name="Foreign dashboard company"));db.flush()
    branch=Branch(company_id=1,name="Dashboard main",code="DASH-MAIN")
    foreign=Branch(company_id=77,name="Dashboard foreign",code="DASH-FOREIGN")
    db.add_all([branch,foreign]);db.flush()
    dep=Department(branch_id=branch.id,name="Engineering")
    loc=WorkLocation(company_id=1,name="HQ",code="DASH-HQ");db.add_all([dep,loc]);db.flush()
    today=datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date()
    people=[]
    for i in range(3):
        e=Employee(employee_id=f"DASH-{i}",first_name="Dashboard",last_name=str(i),date_of_joining=today-timedelta(days=40 if i<2 else 3),status="Probation" if i==1 else "Active",branch_id=branch.id,department_id=dep.id,location_id=loc.id,employment_type="Full-time",probation_end_date=today-timedelta(days=1) if i==1 else None)
        db.add(e);people.append(e)
    db.add(Employee(employee_id="DASH-FOREIGN",first_name="Foreign",last_name="Secret",date_of_joining=today,status="Active",branch_id=foreign.id))
    db.flush();db.commit()
    headers["X-Suite-Branch"] = str(branch.id)
    return headers,user,people,today,dep,loc


def test_context_scope_currency_filters_and_comparison(client,db,dashboard_people):
    headers,user,people,today,dep,loc=dashboard_people
    response=client.get(BASE+"/context",headers=headers);assert response.status_code==200,response.text
    ctx=response.json();assert ctx['currency']=='USD' and ctx['timezone']=='Asia/Kolkata'
    assert len(ctx['sections'])==8 and ctx['departments']==[{'id':dep.id,'name':'Engineering'}]
    result=client.get(BASE+'/workforce',headers=headers,params={'from_date':today-timedelta(days=10),'to_date':today}).json()
    assert result['metrics']['total']==3 and result['metrics']['headcount']==3 and result['metrics']['previous_headcount']==2
    assert all(row['name']!='Foreign Secret' for row in result['rows'])
    assert client.get(BASE+'/workforce',headers=headers,params={'department_id':99999}).json()['metrics']['total']==0
    assert client.get(BASE+'/workforce',headers=headers,params={'from_date':'2026-12-02','to_date':'2026-01-01'}).status_code==422


def test_attendance_deduplicates_and_explains_denominator(client,db,dashboard_people):
    h,u,people,today,*_=dashboard_people
    db.add_all([Attendance(employee_id=people[0].id,attendance_date=today,status='Absent'),Attendance(employee_id=people[0].id,attendance_date=today,status='WFH',total_hours=8),Attendance(employee_id=people[1].id,attendance_date=today,status='Half-day',total_hours=4),Attendance(employee_id=people[2].id,attendance_date=today,status='On Leave')]);db.commit()
    response=client.get(BASE+'/attendance',headers=h,params={'from_date':today,'to_date':today});assert response.status_code==200,response.text
    data=response.json();assert data['metrics']['rate']==75 and data['metrics']['denominator']==2
    assert data['metrics']['on_leave']==1 and data['metrics']['wfh']==1 and data['metrics']['absent']==0
    assert data['metrics']['week_hours']==12


def test_leave_queue_balance_and_handover(client,db,dashboard_people):
    h,u,people,today,*_=dashboard_people
    kind=LeaveType(name='Annual',code='DASH-ANNUAL',days_allowed=20);db.add(kind);db.flush()
    db.add(LeaveBalance(employee_id=people[0].id,leave_type_id=kind.id,year=today.year,allocated=20,carried_forward=2,used=5,pending=3))
    db.add_all([LeaveRequest(employee_id=people[0].id,leave_type_id=kind.id,from_date=today,to_date=today+timedelta(days=2),days_count=3,status='Pending',applied_at=datetime.now(timezone.utc)-timedelta(days=8)),LeaveRequest(employee_id=people[1].id,leave_type_id=kind.id,from_date=today,to_date=today,days_count=1,status='Approved')]);db.commit()
    data=client.get(BASE+'/leave',headers=h).json();assert data['metrics']['available_days']==14 and data['metrics']['pending']==1
    assert data['metrics']['oldest_days']>=7 and data['series'][0]['without_handover']==1


def test_payroll_records_not_company_totals_and_bank_blockers(client,db,dashboard_people):
    h,u,people,today,*_=dashboard_people
    run=PayrollRun(company_id=1,year=today.year,month=today.month,status='locked',total_net=999999);db.add(run);db.flush()
    db.add(PayrollRecord(payroll_run_id=run.id,employee_id=people[0].id,gross_salary=1000,net_salary=900));db.commit()
    response=client.get(BASE+'/payroll',headers=h,params={'from_date':date(today.year,today.month,1),'to_date':today});assert response.status_code==200,response.text
    data=response.json();assert data['metrics']['net']==900 and data['metrics']['issue_count']==1
    assert 'Missing bank details' in data['rows'][0]['detail'] and data['rows'][0]['href'].endswith(str(people[0].id))


def test_operational_deadlines_and_exit_readiness(client,db,dashboard_people):
    h,u,people,today,*_=dashboard_people
    onboarding=EmployeeOnboarding(employee_id=people[0].id,status='in_progress');db.add(onboarding);db.flush()
    db.add(EmployeeOnboardingTask(employee_onboarding_id=onboarding.id,task_name='Return joining documents',category='documents',due_date=today-timedelta(days=2),status='pending'))
    db.add(EmployeeCertificate(employee_id=people[0].id,category='Professional',certificate_type='License',title='Safety license',file_url='/test',expiry_date=today-timedelta(days=1)))
    exit=ExitRecord(employee_id=people[2].id,status='Initiated',last_working_date=today);db.add(exit);db.flush();db.add(ExitChecklistItem(exit_record_id=exit.id,task_name='Handover',is_completed=False));db.commit()
    for section in ['onboarding','probation','compliance']:
        response=client.get(BASE+'/'+section,headers=h);assert response.status_code==200,response.text
        assert response.json()['metrics']['overdue']==1
    assert client.get(BASE+'/exits',headers=h).json()['metrics']['blocked']==1


def test_employee_never_gets_org_reports_or_payroll(client,db,dashboard_people):
    _,_,people,today,*_=dashboard_people
    headers,user=actor(db,role='employee',permissions=['attendance_view','leave_view','payroll_view','reports_view'])
    people[0].user_id=user.id;db.commit()
    headers["X-Suite-Branch"] = str(people[0].branch_id)
    db.add_all([Attendance(employee_id=people[0].id,attendance_date=today,status='Present'),Attendance(employee_id=people[1].id,attendance_date=today,status='Absent')]);db.commit()
    context=client.get(BASE+'/context',headers=headers);assert context.status_code==200,context.text
    assert context.json()['personal'] and 'payroll' not in context.json()['sections']
    for section in ['workforce','payroll','exits']:
        assert client.get(BASE+'/'+section,headers=headers).status_code==403
    result=client.get(BASE+'/attendance',headers=headers).json();assert len(result['rows'])==1 and all(r['employee_id']==people[0].id for r in result['rows'])


def test_drilldown_filters_before_record_limit(client,db,dashboard_people):
    headers,_,people,today,*_=dashboard_people
    for offset in range(130):
        for employee in people[:2]:
            db.add(Attendance(employee_id=employee.id,attendance_date=today-timedelta(days=offset),status='Present' if offset==0 and employee.id==people[0].id else 'Absent'))
    db.commit()
    response=client.get(BASE+'/attendance',headers=headers,params={'from_date':today-timedelta(days=129),'to_date':today,'record_status':'Present','record_date':today})
    assert response.status_code==200,response.text
    assert response.json()['total_rows']==1 and len(response.json()['rows'])==1


def test_manager_metrics_only_include_direct_reports(client,db,dashboard_people):
    _,_,people,today,*_=dashboard_people
    headers,user=actor(db,role='manager',permissions=['reports_view','attendance_view','leave_view','payroll_view'])
    people[0].user_id=user.id;people[1].reporting_manager_id=people[0].id;db.commit()
    headers['X-Suite-Branch']=str(people[0].branch_id)
    context=client.get(BASE+'/context',headers=headers).json()
    assert context['scope']=='My direct reports' and 'payroll' not in context['sections']
    response=client.get(BASE+'/workforce',headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['metrics']['total']==1


def test_business_midnight_uses_company_date(client,db,dashboard_people,monkeypatch):
    from app.api.v1 import hrms_dashboard
    from app.services.metrics.queries import business_context
    headers,_,people,_,*_=dashboard_people
    instant=datetime(2026,11,8,20,0,tzinfo=timezone.utc)
    monkeypatch.setattr(hrms_dashboard,'business_context',lambda session,user: business_context(session,user,now=instant))
    db.add_all([Attendance(employee_id=people[0].id,attendance_date=date(2026,11,8),status='Absent'),Attendance(employee_id=people[0].id,attendance_date=date(2026,11,9),status='Present')]);db.commit()
    response=client.get(BASE+'/attendance',headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['context']['business_date']=='2026-11-09'
    assert response.json()['metrics']['present']==1 and response.json()['metrics']['absent']==0
