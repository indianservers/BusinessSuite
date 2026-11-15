"""Independent committed PostgreSQL transactions exercise native writer order."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from time import monotonic,sleep
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select,text

from tests.test_pms_workflow_postgresql import live, race

ROOT='/api/v1/hrms/leave-encashment'


def configured(live, monkeypatch):
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.models.leave import LeaveType,LeaveBalance
    from app.models.payroll import EmployeeSalary,PayrollPeriod,PayrollPayGroup
    from app.branches.models import BranchGrant
    from tests.test_settings_hub import actor
    from tests.rich_text_test_utils import workflow_seed_scope
    with live.factory() as db:
        with workflow_seed_scope(db):
            branch=Branch(company_id=1,name='Canonical encashment race');db.add(branch);db.flush()
            manager_headers,manager=actor(db,role='leave_review_'+uuid4().hex[:20],
                permissions=['leave_manage','leave_approve','employee_view'],grants={'hrms':{'enabled':True,
                    'permissions':['leave_manage','leave_approve','employee_view'],
                    'actions':['view','create','edit','approve'],'scope':'organization'}})
            db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=manager.id,can_write=True))
            headers=[];employees=[]
            for index in range(2):
                h,user=actor(db,role='leave_self_'+uuid4().hex[:20],permissions=['leave_apply'],
                    grants={'hrms':{'enabled':True,'permissions':['leave_apply'],
                        'actions':['view','create','edit'],'scope':'own'}})
                db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=user.id,can_write=True))
                employee=Employee(employee_id=uuid4().hex,first_name='Canonical',last_name=f'Race {index}',
                    user_id=user.id,branch_id=branch.id,date_of_joining=date(2020,1,1),status='Active')
                db.add(employee);db.flush()
                db.add(EmployeeSalary(employee_id=employee.id,ctc=Decimal('312000'),basic=Decimal('13000'),
                    effective_from=date(2020,1,1),is_active=True))
                headers.append({**h,'X-Suite-Organization':'1','X-Suite-Branch':str(branch.id)})
                employees.append(employee.id)
            kind=LeaveType(name='Canonical encashable leave',code=uuid4().hex[:18],days_allowed=20,encashable=True)
            db.add(kind);db.flush()
            for employee in employees:db.add(LeaveBalance(employee_id=employee,leave_type_id=kind.id,
                year=date.today().year,allocated=20,used=0,pending=0,carried_forward=0))
            db.commit()
            assert db.query(PayrollPayGroup).count()==db.query(PayrollPeriod).count()==0
            result=SimpleNamespace(manager_headers={**manager_headers,'X-Suite-Organization':'1','X-Suite-Branch':str(branch.id)},
                manager_id=manager.id,headers=headers,employees=employees,kind=kind.id,branch=branch.id)
    return result


def submit(live,n,index=0):
    response=live.client.post(ROOT+'/request',headers=n.headers[index],json={'leaveTypeId':n.kind,'daysToEncash':2})
    assert response.status_code==201,response.text
    return response.json()['id']


def assert_outputs(live, *, lines,used):
    from app.models.payroll import LeaveEncashmentLine,PayrollPayGroup,PayrollPeriod
    from app.models.leave import LeaveBalance,LeaveBalanceLedger
    with live.factory() as db:
        assert db.query(LeaveEncashmentLine).count()==lines
        assert db.query(PayrollPayGroup).count()==db.query(PayrollPeriod).count()==1
        assert sum(row.used for row in db.query(LeaveBalance))==used
        assert db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==lines


def test_same_native_request_cannot_debit_twice(live,monkeypatch):
    n=configured(live,monkeypatch);identity=submit(live,n)
    call=lambda:live.client.post(ROOT+f'/{identity}/approve',headers=n.manager_headers,json={})
    results=race(call,call)
    assert sorted(response.status_code for response in results)==[200,400],[response.text for response in results]
    assert_outputs(live,lines=1,used=2)


def test_two_employees_initialize_exactly_one_group_and_period(live,monkeypatch):
    n=configured(live,monkeypatch);first=submit(live,n,0);second=submit(live,n,1)
    results=race(*(lambda identity=identity:live.client.post(ROOT+f'/{identity}/approve',headers=n.manager_headers,json={})
        for identity in (first,second)))
    assert [response.status_code for response in results]==[200,200],[response.text for response in results]
    assert_outputs(live,lines=2,used=4)


def test_competing_requests_recheck_same_remaining_balance(live,monkeypatch):
    n=configured(live,monkeypatch);first=submit(live,n);second=submit(live,n)
    allocate=live.client.post('/api/v1/leave/balance/allocate',headers=n.manager_headers,params={
        'employee_id':n.employees[0],'leave_type_id':n.kind,'year':date.today().year,'days':2})
    assert allocate.status_code==200,allocate.text
    results=race(*(lambda identity=identity:live.client.post(ROOT+f'/{identity}/approve',headers=n.manager_headers,json={})
        for identity in (first,second)))
    assert sorted(response.status_code for response in results)==[200,400],[response.text for response in results]
    assert_outputs(live,lines=1,used=2)


def test_native_rights_are_rechecked_after_real_company_writer_wait(live,monkeypatch):
    from app.business_packs import leave_encashment_core
    from app.core.company_writer import lock_company_writer
    from app.access.models import AccessPolicy
    from app.models.payroll import LeaveEncashmentRequest,LeaveEncashmentLine,PayrollPayGroup,PayrollPeriod
    n=configured(live,monkeypatch);identity=submit(live,n)
    waiting=Event();original=leave_encashment_core.lock_tenant
    def observed(db,actor,scope):
        waiting.set()
        return original(db,actor,scope)
    monkeypatch.setattr(leave_encashment_core,'lock_tenant',observed)
    with live.factory() as blocker:
        lock_company_writer(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(lambda:live.client.post(ROOT+f'/{identity}/approve',headers=n.manager_headers,json={}))
            assert waiting.wait(timeout=20),'Native approval never reached the company writer lock'
            blocked=False;deadline=monotonic()+10
            while monotonic()<deadline and not pending.done():
                blocked=bool(blocker.connection().scalar(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND wait_event='advisory')")))
                if blocked:break
                sleep(.01)
            assert blocked,'Approval did not actually wait on the native PostgreSQL company advisory lock'
            table=AccessPolicy.__table__
            policy=blocker.connection().execute(select(table.c.id,table.c.grants).where(
                table.c.user_id==n.manager_id,table.c.company_id==1)).mappings().one()
            grants={'hrms':{**policy['grants']['hrms'],'actions':['view']}}
            blocker.connection().execute(table.update().where(table.c.id==policy['id']).values(grants=grants,version=table.c.version+1))
            blocker.commit()
            response=pending.result(timeout=30)
    assert response.status_code==403,response.text
    with live.factory() as db:
        assert db.get(LeaveEncashmentRequest,identity).status=='submitted'
        assert db.query(LeaveEncashmentLine).count()==db.query(PayrollPayGroup).count()==db.query(PayrollPeriod).count()==0
