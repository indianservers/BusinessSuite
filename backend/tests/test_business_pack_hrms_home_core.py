"""Unpublished native home parity: no operational pack authorization or bodies."""
from types import MappingProxyType
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from app.business_packs import hrms_home_core as home

@pytest.fixture(autouse=True)
def candidate(monkeypatch):
    from app.business_packs import common_core
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,**home.candidate_operations(common_core.CoreOperation)}))

@pytest.mark.parametrize('mode',['own','team','organization'])
@pytest.mark.parametrize('requested',['mine','team','organization'])
def test_native_home_exact_scope_counts_and_masked_summaries(leave_case,monkeypatch,mode,requested):
    from app.access.models import AccessPolicy
    from app.business_packs import common_core
    from datetime import date
    n=leave_case;actor=n.user if mode=='own' else n.admin;headers=n.headers if mode=='own' else n.admin_headers
    policy=n.db.query(AccessPolicy).filter_by(user_id=actor.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':mode}};policy.version+=1
    n.employee.date_of_joining=date.today();n.employee.personal_email='sensitive-native@example.com';n.employee.phone_number='9876543210';n.db.commit()
    with monkeypatch.context() as patch:
        patch.setattr(common_core,'OPERATIONS',MappingProxyType({key:op for key,op in common_core.OPERATIONS.items() if op.purpose!=home.PURPOSE}))
        legacy=n.client.get(home.PATH,headers=headers,params={'scope':requested})
    assert legacy.status_code==200,legacy.text
    select_pack(n)
    result=n.client.get(home.PATH,headers={**headers,'X-Suite-Pack-Context':'malformed'},params={'scope':requested})
    assert result.status_code==200,result.text
    a=result.json();b=legacy.json();a.pop('refreshed_at');b.pop('refreshed_at')
    assert a==b
    assert not any(key in result.text for key in ['ctc','bank_account','aadhaar','salary'])

def test_home_descriptor_remains_unpublished():
    from app.business_packs.common_core import CoreOperation
    assert not home.operations(CoreOperation)


def test_home_counts_genuine_native_submissions_without_loading_bodies(leave_case):
    from datetime import date,datetime,timezone
    from uuid import uuid4
    from app.models.attendance import Attendance,AttendanceRegularization
    from app.models.expense import ExpenseClaim
    from app.models.timesheet import Timesheet
    from app.branches.models import BranchOwnership
    from tests.test_business_pack_leave_core import apply
    n=leave_case
    created=apply(n);assert created.status_code==201,created.text
    attendance=Attendance(employee_id=n.employee.id,attendance_date=date.today(),check_in=datetime.now(timezone.utc))
    n.db.add(attendance);n.db.flush()
    rows=[attendance,AttendanceRegularization(attendance_id=attendance.id,employee_id=n.employee.id,status='Pending',reason='PRIVATE ATTENDANCE BODY'),
        ExpenseClaim(employee_id=n.employee.id,claim_number=uuid4().hex,claim_type='Travel',expense_date=date.today(),amount=15,
            description='PRIVATE EXPENSE BODY',status='submitted',submitted_by=n.user.id),
        Timesheet(employee_id=n.employee.id,project_id=n.own.id,period_start=date.today(),period_end=date.today(),status='Submitted')]
    n.db.add_all(rows);n.db.flush()
    for row in rows:n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='native-home-count-fixture'))
    n.db.commit();select_pack(n)
    result=n.client.get(home.PATH,headers=n.headers,params={'scope':'mine'})
    assert result.status_code==200,result.text
    body=result.json();assert body['pending_counts']=={'approvals':4,'leave':1,'expenses':1,'helpdesk':None}
    assert body['missing_punches']==1 and body['employee_count']==1
    assert 'PRIVATE' not in result.text


@pytest.mark.parametrize('attack',['salary','employee_bank','request_body','person_id','person_body','mixed_person','raw','raw_star','reused_star','write','revocation'])
def test_home_fixed_reader_never_exposes_bodies_or_borrows_existence_predicates(leave_case,monkeypatch,attack):
    from app.api.v1 import hr_workbench
    from app.models.payroll import EmployeeSalary
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest
    from app.common.models import CommonPerson
    from app.access.models import AccessPolicy
    from app.services.metrics.queries import employee_records
    from sqlalchemy import select,update
    n=leave_case;select_pack(n)
    def injected(scope,db,user):
        if attack=='salary':db.query(EmployeeSalary).all()
        elif attack=='employee_bank':db.query(Employee.account_number).all()
        elif attack=='request_body':db.query(LeaveRequest).all()
        elif attack in {'person_id','person_body','mixed_person'}:
            # Even a genuine certified tenancy predicate cannot bless a new
            # CommonPerson projection or another use of the same column.
            actual=employee_records(db,user)
            columns=[CommonPerson.id] if attack=='person_id' else [CommonPerson.first_name]
            if attack=='mixed_person':columns=[Employee.id,*columns]
            db.query(*columns).filter(*actual._where_criteria).all()
        elif attack=='raw':db.execute(select(Employee.__table__.c.id)).all()
        elif attack in {'raw_star','reused_star'}:
            from sqlalchemy import literal_column,func
            star=literal_column('*');columns=[star] if attack=='raw_star' else [func.count(star),star]
            db.query(*columns).select_from(Employee).all()
        elif attack=='write':
            row=db.query(Employee).first();row.first_name='forged';db.commit()
        else:
            n.db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id==n.user.id).values(status='revoked'))
            db.query(Employee.id).all()
        return {}
    monkeypatch.setattr(hr_workbench,'native_home',injected)
    denied=n.client.get(home.PATH,headers=n.headers)
    assert denied.status_code==403,denied.text


def test_home_private_reader_cannot_reopen_after_lease(leave_case,monkeypatch):
    from app.api.v1 import hr_workbench
    from app.models.employee import Employee
    from sqlalchemy.exc import InvalidRequestError
    n=leave_case;select_pack(n);seen=[];original=hr_workbench.native_home
    def observed(scope,db,user):seen.append(db);return original(scope,db,user)
    monkeypatch.setattr(hr_workbench,'native_home',observed)
    response=n.client.get(home.PATH,headers=n.headers)
    assert response.status_code==200,response.text
    assert len(seen)==1 and seen[0] not in home._READERS
    with pytest.raises(InvalidRequestError,match='permanently closed'):seen[0].query(Employee.id).all()


@pytest.mark.skipif(__import__('os').getenv('RUN_CONTROL_BROWSER')!='1',reason='Opt-in original App browser')
def test_actual_original_home_app_desktop_mobile(leave_case,monkeypatch):
    import json,re
    from datetime import date
    from tests.test_control_browser import test_control_center_real_browser
    n=leave_case;n.employee.date_of_joining=date.today();n.employee.account_number='9876543210123456';n.employee.ifsc_code='DEMO0000001';n.employee.pan_number='ABCDE1234F';n.db.commit()
    context=select_pack(n);headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    identity=n.client.get('/api/v1/auth/me',headers=headers);access=n.client.get('/api/v1/access/me',headers=headers)
    assert identity.status_code==access.status_code==200,(identity.text,access.text)
    user=identity.json();role=user['role'] if isinstance(user['role'],str) else user['role']['name'];user.update(role=role,primary_role=role,access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','hrms-home-native.cjs');monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],'user':user,'branch':str(n.branch.id),'context':str(context.id)}))
    try:test_control_center_real_browser(n.client,n.db,None,headers)
    except AssertionError as error:
        message=re.sub(r'Bearer\s+[A-Za-z0-9_.-]+','Bearer [REDACTED]',str(error));message=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED-JWT]',message)
        raise AssertionError(message) from None


def test_native_optional_exit_preview_and_helpdesk_count_keep_body_private(leave_case,monkeypatch):
    from datetime import date
    from uuid import uuid4
    from app.models.user import Permission
    from app.access.models import AccessPolicy
    from app.models.exit import ExitRecord
    from app.models.helpdesk import HelpdeskTicket
    from app.branches.models import BranchOwnership
    from app.business_packs import common_core
    n=leave_case
    for name in ['exit_view','helpdesk_view']:
        permission=n.db.query(Permission).filter_by(name=name).first()
        if permission is None:permission=Permission(name=name,module='hrms');n.db.add(permission);n.db.flush()
        n.user.role.permissions.append(permission)
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'permissions':[*policy.grants['hrms']['permissions'],'exit_view','helpdesk_view']}};policy.version+=1
    rows=[ExitRecord(employee_id=n.employee.id,status='Initiated',last_working_date=date.today(),reason='PRIVATE EXIT REASON',final_settlement_amount=999999),
        HelpdeskTicket(organization_id=1,employee_id=n.employee.id,ticket_number=uuid4().hex[:25],subject='PRIVATE TICKET SUBJECT',description='PRIVATE TICKET BODY',status='Open')]
    n.db.add_all(rows);n.db.flush()
    for row in rows:n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='native-home-optional-fixture'))
    n.db.commit()
    with monkeypatch.context() as patch:
        patch.setattr(common_core,'OPERATIONS',MappingProxyType({key:op for key,op in common_core.OPERATIONS.items() if op.purpose!=home.PURPOSE}))
        legacy=n.client.get(home.PATH,headers=n.headers)
    assert legacy.status_code==200,legacy.text
    select_pack(n);result=n.client.get(home.PATH,headers=n.headers)
    assert result.status_code==200,result.text
    a=result.json();b=legacy.json();a.pop('refreshed_at');b.pop('refreshed_at');assert a==b
    assert a['exit_count']==1 and len(a['exits'])==1 and a['pending_counts']['helpdesk']==1
    assert all(value not in result.text for value in ['PRIVATE EXIT','PRIVATE TICKET','999999'])
