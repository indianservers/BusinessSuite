"""A rolling candidate/native reader shares the real company writer lock."""
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from datetime import date
from threading import Event
from time import monotonic,sleep
from fastapi import Request
from sqlalchemy import text
from tests.test_pms_workflow_postgresql import live


def configured(live):
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.branches.models import BranchGrant
    from tests.rich_text_test_utils import workflow_seed_scope
    from tests.test_settings_hub import actor
    from uuid import uuid4
    with live.factory() as db:
        with workflow_seed_scope(db):
            branch=Branch(company_id=1,name='Native variance race');db.add(branch);db.flush()
            headers,user=actor(db,role='payroll_variance_'+uuid4().hex[:15],permissions=['payroll_view'],
                grants={'hrms':{'enabled':True,'permissions':['payroll_view'],'actions':['view'],'scope':'organization'}})
            db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=user.id,can_write=True))
            employee=Employee(employee_id=uuid4().hex,first_name='Native',last_name='Variance',branch_id=branch.id,
                date_of_joining=date(2020,1,1),status='Active')
            db.add(employee);db.flush()
            run=PayrollRun(company_id=1,branch_id=branch.id,month=10,year=2026,status='calculated')
            db.add(run);db.flush()
            db.add(PayrollRecord(payroll_run_id=run.id,employee_id=employee.id,gross_salary=10000,net_salary=9000))
            db.commit();identity=run.id;actor_id=user.id
            headers={**headers,'X-Suite-Organization':'1','X-Suite-Branch':str(branch.id)}
    return identity,headers,actor_id


def test_candidate_and_legacy_variance_cannot_duplicate_derivatives(live,monkeypatch):
    from app.main import app
    from app.core.deps import get_db
    from app.core import company_writer
    from app.business_packs import common_core,payroll_variance
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.models.payroll import PayrollRun,PayrollRecord,PayrollVarianceItem
    from app.branches.models import BranchGrant
    from tests.rich_text_test_utils import workflow_seed_scope
    from tests.test_settings_hub import actor
    from uuid import uuid4
    mode=ContextVar('variance_rollout_test',default=False)
    original_ops=common_core.OPERATIONS
    candidate=payroll_variance.candidate_operations(common_core.CoreOperation)
    class Rollout(Mapping):
        def __iter__(self):return iter(original_ops)
        def __len__(self):return len(original_ops)
        def __getitem__(self,key):
            if mode.get() and key in candidate:return candidate[key]
            return original_ops[key]
    monkeypatch.setattr(common_core,'OPERATIONS',Rollout())
    # Only descriptor rollout differs per request. Native login, permissions,
    # scopes, independent sessions and actual production endpoints are retained.
    async def sessions(request:Request):
        token=mode.set(request.headers.get('X-Test-Candidate')=='1')
        try:
            with live.factory() as db:
                try:yield db
                except BaseException:db.rollback();raise
        finally:mode.reset(token)
    app.dependency_overrides[get_db]=sessions
    identity,headers,actor_id=configured(live)
    acquired=Event();release=Event();legacy_entered=Event();original_lock=company_writer.lock_company_writer
    def lock(db,company):
        candidate_request=db.info.get('business_common_core_scope') is not None
        if not candidate_request:legacy_entered.set()
        original_lock(db,company)
        if candidate_request:
            acquired.set();assert release.wait(timeout=20)
    monkeypatch.setattr(company_writer,'lock_company_writer',lock)
    path=f'/api/v1/payroll/runs/{identity}/variance'
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(lambda:live.client.get(path,headers={**headers,'X-Test-Candidate':'1'}))
        try:
            assert acquired.wait(timeout=20),'Candidate did not acquire company writer'
            second=pool.submit(lambda:live.client.get(path,headers=headers))
            assert legacy_entered.wait(timeout=20),'Legacy did not reach same writer'
            blocked=False;deadline=monotonic()+10
            with live.factory() as observer:
                while monotonic()<deadline:
                    blocked=bool(observer.connection().scalar(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND wait_event='advisory')")))
                    if blocked:break
                    sleep(.01)
            assert blocked,'Legacy must really wait for candidate transaction'
        finally:release.set()
        results=[first.result(timeout=30),second.result(timeout=30)]
    assert [response.status_code for response in results]==[200,200],[r.text for r in results]
    assert all(len(response.json())==1 for response in results)
    with live.factory() as db:
        rows=db.query(PayrollVarianceItem).filter_by(payroll_run_id=identity).all()
        assert len(rows)==1 and rows[0].current_gross==10000 and rows[0].current_net==9000
        assert db.get(PayrollRun,identity).status=='calculated'


def test_legacy_variance_rechecks_native_governance_after_writer_wait(live,monkeypatch):
    from app.core import company_writer
    from app.shared.models import ServicePolicy
    from app.models.payroll import PayrollVarianceItem
    identity,headers,actor_id=configured(live)
    entered=Event();original=company_writer.lock_company_writer
    def observed(db,company):
        entered.set();return original(db,company)
    monkeypatch.setattr(company_writer,'lock_company_writer',observed)
    with live.factory() as blocker:
        original(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(lambda:live.client.get(f'/api/v1/payroll/runs/{identity}/variance',headers=headers))
            assert entered.wait(timeout=20)
            blocked=False;deadline=monotonic()+10
            while monotonic()<deadline and not pending.done():
                blocked=bool(blocker.connection().scalar(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND wait_event='advisory')")))
                if blocked:break
                sleep(.01)
            assert blocked,'Native request must really wait before revocation'
            blocker.connection().execute(ServicePolicy.__table__.insert().values(organization_id=1,
                scope_key='variance-native-governance-wait',module_key='hrms',kind='governance',version=1,
                updated_by=actor_id,values_json={'module':'hrms','classification':'restricted','allowedRoles':[]}))
            blocker.commit();response=pending.result(timeout=30)
    assert response.status_code==403,response.text
    with live.factory() as db:assert db.query(PayrollVarianceItem).count()==0
