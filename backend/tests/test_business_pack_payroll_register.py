"""Native payroll register/counts without exposing payroll record bodies."""
from datetime import date
from decimal import Decimal
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case,request,ROOT


@pytest.fixture
def register_case(encash_case):
    from app.models.user import Permission
    from app.access.models import AccessPolicy
    from app.models.payroll import PayrollRun,PayrollRecord,PayrollPeriod,PayrollPayGroup
    from app.branches.models import BranchOwnership
    n=encash_case
    permission=n.db.query(Permission).filter_by(name='payroll_view').first()
    if permission is None:permission=Permission(name='payroll_view',module='hrms');n.db.add(permission);n.db.flush()
    for user in (n.user,n.admin):
        if permission not in user.role.permissions:user.role.permissions.append(permission)
        policy=n.db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
        policy.grants={'hrms':{**policy.grants['hrms'],'permissions':[*policy.grants['hrms']['permissions'],'payroll_view']}}
    n.db.commit()
    created=request(n);assert created.status_code==201,created.text
    approved=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=n.admin_headers,json={'remarks':'Canonical payroll input'})
    assert approved.status_code==200,approved.text
    n.period=n.db.query(PayrollPeriod).one();n.group=n.db.query(PayrollPayGroup).one()
    run=PayrollRun(company_id=1,branch_id=n.branch.id,pay_group_id=n.group.id,month=date.today().month,year=date.today().year,
        status='calculated',total_gross=30000,total_deductions=3000,total_net=27000)
    n.db.add(run);n.db.flush()
    rows=[PayrollRecord(payroll_run_id=run.id,employee_id=person.id,gross_salary=15000,total_deductions=1500,net_salary=13500) for person in (n.employee,n.manager)]
    n.db.add_all(rows);n.db.flush()
    for row in [run,*rows]:n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='canonical-payroll-fixture'))
    n.db.commit();n.run=run;n.records=rows
    return n


@pytest.mark.parametrize('mode,count',[('own',1),('team',2),('organization',2)])
def test_register_uses_exact_native_record_count_without_body(register_case,mode,count):
    from app.access.models import AccessPolicy
    n=register_case;user=n.user if mode=='own' else n.admin;headers=n.headers if mode=='own' else n.admin_headers
    policy=n.db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':mode}};n.db.commit();select_pack(n)
    for path in ['/api/v1/payroll/runs','/api/v1/payroll/last-run',f'/api/v1/payroll/runs/{n.run.id}']:
        response=n.client.get(path,headers={**headers,'X-Suite-Pack-Context':'bad'})
        assert response.status_code==200,response.text
        result=response.json()[0] if isinstance(response.json(),list) else response.json()
        assert result['id']==n.run.id and result['total_employees']==count
        assert not {'records','basic','salary_currency','employee_id'} & set(result)
    for path in ['/api/v1/payroll/setup/pay-groups','/api/v1/payroll/setup/periods','/api/v1/reports/payroll-summary','/api/v1/payroll/inputs/leave-encashment-lines']:
        response=n.client.get(path,headers=headers)
        assert response.status_code==200,response.text
        assert response.json()


def replace_call(monkeypatch,callback):
    from app.main import app
    from fastapi.routing import iter_route_contexts
    route=next(item for item in iter_route_contexts(app.router.routes) if item.path=='/api/v1/payroll/runs' and 'GET' in (item.methods or ()))
    def injected(db,current_user):return callback(db,current_user)
    monkeypatch.setattr(route.dependant,'call',injected)


@pytest.mark.parametrize('attack',['record','record_id','employee_id','get','refresh','salary','salary_column','raw','mixed','eager','write'])
def test_register_cannot_borrow_record_id_permission_for_bodies(register_case,monkeypatch,attack):
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.payroll import PayrollRecord,PayrollRun,EmployeeSalary
    n=register_case;identity=n.records[0].id;cached=n.records[0];select_pack(n)
    def callback(db,user):
        if attack=='record':db.query(PayrollRecord).all()
        elif attack=='record_id':db.query(PayrollRecord.id).all()
        elif attack=='employee_id':db.query(PayrollRecord.employee_id).all()
        elif attack=='get':assert db.get(PayrollRecord,identity) is None;return []
        elif attack=='refresh':db.refresh(cached)
        elif attack=='salary':db.query(EmployeeSalary).all()
        elif attack=='salary_column':db.query(PayrollRecord.gross_salary).all()
        elif attack=='raw':db.execute(select(PayrollRecord.__table__.c.id)).all()
        elif attack=='mixed':db.query(PayrollRecord.id,EmployeeSalary.basic).all()
        elif attack=='eager':db.query(PayrollRun).options(joinedload(PayrollRun.records)).all()
        else:
            row=db.query(PayrollRun).first();row.total_net=1;db.commit()
        return []
    replace_call(monkeypatch,callback)
    response=n.client.get('/api/v1/payroll/runs',headers=n.admin_headers)
    assert response.status_code==(200 if attack=='get' else 403),response.text



def test_pack_role_never_grants_native_payroll_view(core_case):
    n=core_case;select_pack(n)
    for path in ['/api/v1/payroll/runs','/api/v1/payroll/setup/periods','/api/v1/reports/payroll-summary']:
        response=n.client.get(path,headers=n.headers)
        assert response.status_code==403,response.text


def test_register_rechecks_midrequest_native_revocation(register_case,monkeypatch):
    from sqlalchemy import update
    from app.access.models import AccessPolicy
    from app.models.payroll import PayrollRun
    n=register_case;select_pack(n)
    def callback(db,user):
        db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id==user.id).values(status='revoked'))
        db.query(PayrollRun).all()
        return []
    replace_call(monkeypatch,callback)
    response=n.client.get('/api/v1/payroll/runs',headers=n.admin_headers)
    assert response.status_code==403,response.text



def test_register_branch_and_private_sources_do_not_affect_counts(register_case):
    from uuid import uuid4
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    n=register_case
    other=Branch(company_id=1,name='Invisible payroll branch');n.db.add(other);n.db.flush()
    person=Employee(employee_id=uuid4().hex,first_name='Unrelated',last_name='Payroll',branch_id=other.id,date_of_joining=date(2020,1,1),status='Active')
    n.db.add(person);n.db.flush()
    other_run=PayrollRun(company_id=1,branch_id=other.id,month=1,year=2025,status='calculated',total_gross=999999,total_net=999999)
    n.db.add(other_run);n.db.flush()
    record=PayrollRecord(payroll_run_id=other_run.id,employee_id=person.id,gross_salary=999999,net_salary=999999)
    n.db.add(record);n.db.flush()
    for row in (person,other_run,record):n.db.add(BranchOwnership(company_id=1,branch_id=other.id,resource_table=row.__tablename__,resource_key=str(row.id),source='unrelated-native-payroll'))
    n.db.commit();ctx=select_pack(n)
    response=n.client.get('/api/v1/payroll/runs',headers=n.admin_headers)
    assert response.status_code==200,response.text
    assert [(item['id'],item['total_employees']) for item in response.json()]==[(n.run.id,2)]
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.branch.id,context_id=ctx.id,resource_table='payroll_records',resource_key=str(n.records[1].id)))
    n.db.commit()
    response=n.client.get('/api/v1/payroll/runs',headers=n.admin_headers)
    assert response.status_code==200,response.text
    assert response.json()[0]['total_employees']==1
    assert '999999' not in response.text
