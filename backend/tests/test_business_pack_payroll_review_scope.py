"""Guided read privacy with real non-administrative Native Own/Team/Org grants."""
from datetime import date
from uuid import uuid4
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case
from tests.test_business_pack_payroll_register import register_case
from tests.payroll_review_test_utils import review_candidate


@pytest.mark.parametrize('mode,count',[('own',1),('team',2),('organization',3)])
def test_true_native_scope_excludes_unrelated_same_branch_employee(register_case,mode,count):
    from app.access.models import AccessPolicy,AccessMembership
    from app.models.employee import Employee
    from app.models.payroll import PayrollRecord
    from app.branches.models import BranchOwnership
    n=register_case
    assert not n.user.is_superuser and not n.db.query(AccessMembership).filter_by(user_id=n.user.id,company_id=1).one().is_admin
    n.employee.reporting_manager_id=None;n.manager.reporting_manager_id=n.employee.id
    unrelated=Employee(employee_id=uuid4().hex,first_name='Unrelated',last_name='Private employee',date_of_joining=date(2020,1,1),status='Active',branch_id=n.branch.id)
    n.db.add(unrelated);n.db.flush()
    record=PayrollRecord(payroll_run_id=n.run.id,employee_id=unrelated.id,gross_salary=15000,total_deductions=1500,net_salary=13500)
    n.db.add(record);n.db.flush()
    for row in (unrelated,record):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='verified-unrelated-payroll'))
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':mode}}
    n.run.total_gross=45000;n.run.total_deductions=4500;n.run.total_net=40500
    n.db.commit();select_pack(n)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert response.status_code==200,response.text
    body=response.json();assert len(body['records'])==count
    employee_ids={row['employee_id'] for row in body['records']}
    assert (unrelated.id in employee_ids)==(mode=='organization')
    if mode!='organization':assert 'Unrelated' not in response.text
    listing=n.client.get('/api/v1/payroll/runs',headers=n.headers)
    assert listing.status_code==200,listing.text
    assert listing.json()[0]['total_employees']==count


def test_reader_error_does_not_rollback_caller_before_http_error_handling(register_case,monkeypatch):
    from sqlalchemy import update,select
    from fastapi import HTTPException
    from fastapi.routing import iter_route_contexts
    from app.main import app
    from app.api.v1 import payroll_guided
    from app.models.company import Company
    from app.business_packs.payroll_review import compute,PATH
    n=register_case;select_pack(n)
    def denied(run_id,db,user):db.commit()
    monkeypatch.setattr(payroll_guided,'native_overview',denied)
    route=next(item for item in iter_route_contexts(app.router.routes) if item.path==PATH and 'GET' in (item.methods or ()))
    def caught(run_id,db,user):
        connection=db.connection();transaction=connection.get_transaction();nested=connection.get_nested_transaction()
        connection.execute(update(Company).where(Company.id==1).values(address='Caller work survives reader error'))
        with pytest.raises(HTTPException) as failure:compute(db,user,run_id)
        assert failure.value.status_code==403
        assert connection.get_transaction() is transaction and connection.get_nested_transaction() is nested
        assert connection.scalar(select(Company.address).where(Company.id==1))=='Caller work survives reader error'
        return {'guarded':True}
    monkeypatch.setattr(route.dependant,'call',caught)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert response.status_code==200,response.text
    assert response.json()=={'guarded':True}



@pytest.mark.parametrize('changed',[False,True])
def test_stored_native_policy_salary_hash_is_exact_and_never_exposes_ctc(register_case,changed):
    import calendar
    from app.schemas.payroll_policy import PayrollPolicyRules
    from app.services.payroll_policy import evaluate_days,calculation_signature
    n=register_case
    start=date(n.run.year,n.run.month,1);end=date(n.run.year,n.run.month,calendar.monthrange(n.run.year,n.run.month)[1])
    n.run.pay_period_start=start;n.run.pay_period_end=end;n.group.working_pattern='5_day';n.group.working_days_per_week=5
    n.db.commit()
    policy={'rules':PayrollPolicyRules().model_dump(),'pay_group_id':n.group.id,'version_id':None,'effective_from':start.isoformat()}
    checks=evaluate_days(n.db,n.employee,start,end,n.group,policy)
    expected=calculation_signature(n.db,n.employee,n.run,checks)
    n.run.policy_snapshot={'groups':{str(n.group.id):policy},'employee_groups':{str(n.employee.id):str(n.group.id)},
        'checks':{str(n.employee.id):expected},'components':{}}
    if changed:n.salary.ctc=315000
    n.db.commit();select_pack(n)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert result.status_code==200,result.text
    reasons=result.json()['blockers']
    assert any('earnings changed; regenerate payroll' in reason for reason in reasons)==changed
    assert '312000' not in result.text and '315000' not in result.text
    assert all(set(row)=={'id','employee_id','employee_name','gross','deductions','net','currency'} for row in result.json()['records'])


@pytest.mark.parametrize('attack',['actor','session','run'])
def test_review_requires_genuine_request_session_actor_and_run(register_case,monkeypatch,attack):
    from types import SimpleNamespace
    from sqlalchemy.orm import Session
    from fastapi import HTTPException
    from fastapi.routing import iter_route_contexts
    from app.main import app
    from app.business_packs.payroll_review import compute,PATH
    n=register_case;select_pack(n)
    route=next(item for item in iter_route_contexts(app.router.routes) if item.path==PATH and 'GET' in (item.methods or ()))
    def caught(run_id,db,user):
        if attack=='session':
            forged=Session(bind=db.connection(),join_transaction_mode='rollback_only')
            forged.info.update(db.info)
            try:
                with pytest.raises(HTTPException) as failure:compute(forged,user,run_id)
            finally:forged.close()
        elif attack=='actor':
            forged=SimpleNamespace(id=user.id,role_id=user.role_id,organization_id=1,is_active=True,is_superuser=True)
            with pytest.raises(HTTPException) as failure:compute(db,forged,run_id)
        else:
            with pytest.raises(HTTPException) as failure:compute(db,user,SimpleNamespace(id=run_id))
        assert failure.value.status_code in {403,404}
        return {'guarded':True}
    monkeypatch.setattr(route.dependant,'call',caught)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert result.status_code==200,result.text
    assert result.json()=={'guarded':True}


def test_readonly_branch_never_advertises_native_financial_writes(register_case):
    from app.models.user import Permission
    from app.access.models import AccessPolicy
    from app.branches.models import BranchGrant
    from app.models.payroll import PayrollRun
    n=register_case
    for name in ('payroll_run','payroll_approve'):
        permission=n.db.query(Permission).filter_by(name=name).first()
        if permission is None:
            permission=Permission(name=name,module='hrms',description=name);n.db.add(permission);n.db.flush()
        if permission not in n.user.role.permissions:n.user.role.permissions.append(permission)
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'permissions':[*policy.grants['hrms']['permissions'],'payroll_run','payroll_approve'],
        'actions':['view','create','edit','approve']}}
    grant=n.db.query(BranchGrant).filter_by(user_id=n.user.id,branch_id=n.branch.id).one();grant.can_write=False
    n.db.commit();before=n.db.query(PayrollRun).count()
    denied=n.client.post('/api/v1/payroll/run',headers=n.headers,json={'month':n.run.month,'year':n.run.year})
    assert denied.status_code==403,denied.text
    assert n.db.query(PayrollRun).count()==before
    select_pack(n)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert result.status_code==200,result.text
    assert all(result.json()[key] is False for key in ('can_process','can_review','can_approve'))


def test_private_reader_cannot_mutate_even_unflushed_financial_state(register_case,monkeypatch):
    from app.api.v1 import payroll_guided
    from app.models.payroll import PayrollRun
    n=register_case;select_pack(n);original=payroll_guided.native_overview
    def changed(run_id,db,user):
        row=db.query(PayrollRun).filter_by(id=run_id).one();row.total_net=1
        return original(run_id,db,user)
    monkeypatch.setattr(payroll_guided,'native_overview',changed)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert result.status_code==403,result.text
    n.db.refresh(n.run);assert n.run.total_net==27000

def test_private_reader_is_permanently_closed_after_computation(register_case,monkeypatch):
    from sqlalchemy.exc import InvalidRequestError
    from app.api.v1 import payroll_guided
    from app.models.payroll import PayrollRun
    n=register_case;select_pack(n);retained=[];original=payroll_guided.native_overview
    def observed(run_id,db,user):
        retained.append(db)
        return original(run_id,db,user)
    monkeypatch.setattr(payroll_guided,'native_overview',observed)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert response.status_code==200,response.text
    assert len(retained)==1
    reader=retained[0]
    with pytest.raises(InvalidRequestError,match='permanently closed'):
        reader.query(PayrollRun.id).all()
    with pytest.raises(InvalidRequestError,match='permanently closed'):
        reader.connection()
    assert n.db.query(PayrollRun).filter_by(id=n.run.id).one().total_net==27000


@pytest.mark.parametrize('raw_kind',['text','core','bind','get_bind','query_session','transaction','nested_transaction','invalidate','reset','bind_mapper','bind_table'])
def test_private_reader_cannot_obtain_raw_connection_during_lease(register_case,monkeypatch,raw_kind):
    from app.api.v1 import payroll_guided
    from app.models.payroll import EmployeeSalary,PayrollRun
    from sqlalchemy import select,text
    n=register_case;select_pack(n);original=payroll_guided.native_overview
    def attempted(run_id,db,user):
        statement=text('SELECT ctc FROM employee_salaries') if raw_kind=='text' else select(EmployeeSalary.__table__.c.ctc)
        if raw_kind=='invalidate':db.invalidate()
        elif raw_kind=='reset':db.reset()
        elif raw_kind=='bind_mapper':db.bind_mapper(EmployeeSalary,n.db.connection())
        elif raw_kind=='bind_table':db.bind_table(EmployeeSalary.__table__,n.db.connection())
        elif raw_kind=='bind':db.bind.execute(statement).all()
        elif raw_kind=='get_bind':db.get_bind().execute(statement).all()
        elif raw_kind=='query_session':db.query(EmployeeSalary.ctc).session.connection().execute(statement).all()
        elif raw_kind=='transaction':db.get_transaction().connection(None).execute(statement).all()
        elif raw_kind=='nested_transaction':db.get_nested_transaction().connection(None).execute(statement).all()
        else:db.connection().execute(statement).all()
        return original(run_id,db,user)
    monkeypatch.setattr(payroll_guided,'native_overview',attempted)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.headers)
    assert response.status_code==403,response.text
    assert n.db.query(PayrollRun).filter_by(id=n.run.id).one().total_net==27000
