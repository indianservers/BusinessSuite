"""Unpublished variance candidate uses actual canonical native requests."""
from types import MappingProxyType
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case
from tests.test_business_pack_payroll_register import register_case

@pytest.fixture(autouse=True)
def variance_candidate(monkeypatch):
    from app.business_packs import common_core,payroll_variance
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        **payroll_variance.candidate_operations(common_core.CoreOperation)}))


def test_variance_materializes_native_rows_without_changing_payroll(register_case):
    from app.models.payroll import PayrollRun,PayrollVarianceItem,PayrollRecord
    n=register_case;select_pack(n)
    before=[(r.id,r.gross_salary,r.net_salary) for r in n.db.query(PayrollRecord).order_by(PayrollRecord.id)]
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.admin_headers)
    assert response.status_code==200,response.text
    data=response.json();assert len(data)==2
    assert all(row['id']>0 and row['payroll_run_id']==n.run.id for row in data)
    assert n.db.query(PayrollVarianceItem).filter_by(payroll_run_id=n.run.id).count()==2
    assert [(r.id,r.gross_salary,r.net_salary) for r in n.db.query(PayrollRecord).order_by(PayrollRecord.id)]==before
    assert n.db.query(PayrollRun).filter_by(id=n.run.id).one().status==n.run.status


def test_variance_cannot_replace_native_permission_with_pack_role(core_case):
    n=core_case;select_pack(n)
    response=n.client.get('/api/v1/payroll/runs/1/variance',headers=n.headers)
    assert response.status_code==403,response.text


def test_variance_descriptor_remains_unpublished():
    from app.business_packs import payroll_variance,common_core
    assert not payroll_variance.operations(common_core.CoreOperation)

@pytest.mark.parametrize('mode,count',[('own',1),('team',2),('organization',2)])
def test_variance_preserves_native_employee_visibility(register_case,mode,count):
    from app.access.models import AccessPolicy
    n=register_case
    if mode=='team':
        n.employee.reporting_manager_id=None;n.manager.reporting_manager_id=n.employee.id
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':mode}};n.db.commit();select_pack(n)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.headers)
    assert response.status_code==200,response.text
    assert len(response.json())==count
    if mode=='own':assert response.json()[0]['employee_id']==n.employee.id


def test_variance_readonly_requires_fresh_actual_stored_derivatives(register_case):
    from app.branches.models import BranchGrant
    from app.models.payroll import PayrollVarianceItem,PayrollRecord
    n=register_case;select_pack(n);path=f'/api/v1/payroll/runs/{n.run.id}/variance'
    grant=n.db.query(BranchGrant).filter_by(user_id=n.user.id,branch_id=n.branch.id).one()
    grant.can_write=False;n.db.commit()
    missing=n.client.get(path,headers=n.headers)
    assert missing.status_code==409,missing.text
    assert n.db.query(PayrollVarianceItem).count()==0
    generated=n.client.get(path,headers=n.admin_headers);assert generated.status_code==200,generated.text
    ids=[row.id for row in n.db.query(PayrollVarianceItem).order_by(PayrollVarianceItem.id)]
    actual=n.client.get(path,headers=n.headers);assert actual.status_code==200,actual.text
    assert len(actual.json())==1 and actual.json()[0]['id'] in ids
    assert [row.id for row in n.db.query(PayrollVarianceItem).order_by(PayrollVarianceItem.id)]==ids
    n.db.query(PayrollRecord).filter_by(id=n.records[0].id).one().net_salary=12345;n.db.commit()
    stale=n.client.get(path,headers=n.headers);assert stale.status_code==409,stale.text
    assert [row.id for row in n.db.query(PayrollVarianceItem).order_by(PayrollVarianceItem.id)]==ids


@pytest.mark.parametrize('attack',['run','record','audit','unleased-variance','raw'])
def test_variance_materialization_is_not_generic_financial_write(register_case,monkeypatch,attack):
    from app.business_packs import payroll_review
    from app.models.payroll import PayrollRun,PayrollRecord,PayrollRunAuditLog,PayrollVarianceItem
    from sqlalchemy import select
    n=register_case;select_pack(n)
    def unsafe(db,actor,run_id):
        if attack=='run':db.query(PayrollRun).filter_by(id=run_id).one().total_net=1
        elif attack=='record':db.query(PayrollRecord).first()
        elif attack=='audit':db.query(PayrollRunAuditLog).all()
        elif attack=='raw':db.execute(select(PayrollVarianceItem.__table__.c.id)).all()
        else:db.add(PayrollVarianceItem(payroll_run_id=run_id,employee_id=n.employee.id))
        db.flush()
        return {'run_id':run_id,'items':[]}
    monkeypatch.setattr(payroll_review,'read_variance_snapshot',unsafe)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.admin_headers)
    assert response.status_code==403,response.text
    n.db.refresh(n.run);assert n.run.total_net==27000
    assert n.db.query(PayrollVarianceItem).count()==0


def test_variance_previous_period_ambiguity_has_no_derivative_effects(register_case):
    from app.models.payroll import PayrollRun,PayrollVarianceItem
    from app.branches.models import BranchOwnership
    n=register_case
    month=12 if n.run.month==1 else n.run.month-1;year=n.run.year-1 if n.run.month==1 else n.run.year
    for _ in range(2):
        run=PayrollRun(company_id=1,branch_id=n.branch.id,pay_group_id=n.group.id,month=month,year=year,status='calculated')
        n.db.add(run);n.db.flush();n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,
            resource_table=run.__tablename__,resource_key=str(run.id),source='variance-actual-native-fixture'))
    n.db.commit();select_pack(n)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.admin_headers)
    assert result.status_code==409,result.text
    assert n.db.query(PayrollVarianceItem).count()==0


def test_variance_prior_currency_and_actual_components_reuse_native_math(register_case):
    from app.models.payroll import PayrollRun,PayrollRecord,PayrollComponent
    from app.branches.models import BranchOwnership
    n=register_case
    month=12 if n.run.month==1 else n.run.month-1;year=n.run.year-1 if n.run.month==1 else n.run.year
    run=PayrollRun(company_id=1,branch_id=n.branch.id,pay_group_id=n.group.id,month=month,year=year,status='calculated')
    n.db.add(run);n.db.flush()
    previous=PayrollRecord(payroll_run_id=run.id,employee_id=n.employee.id,basic=10000,gross_salary=10000,net_salary=10000,salary_currency='USD')
    n.db.add(previous);n.db.flush()
    component=PayrollComponent(record_id=n.records[0].id,component_name='Overtime',component_type='earning',source_type='overtime',amount=500)
    n.db.add(component);n.db.flush()
    for row in (run,previous,component):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,
        resource_table=row.__tablename__,resource_key=str(row.id),source='variance-actual-native-fixture'))
    n.db.commit();select_pack(n)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.headers)
    assert result.status_code==200,result.text
    row=result.json()[0]
    assert row['previous_payroll_record_id']==previous.id
    assert row['previous_currency']=='USD' and row['current_currency']=='INR'
    assert 'Currency changed' in row['reason'] and 'Overtime' in row['reason']
    from decimal import Decimal
    assert Decimal(row['gross_delta'])==5000 and Decimal(row['gross_delta_percent'])==50


def test_employee_fk_certificate_is_exact_flush_only_and_expires(register_case,monkeypatch):
    from app.business_packs import payroll_variance
    from app.models.employee import Employee
    from app.models.user import User
    from sqlalchemy import select
    n=register_case;own_id=n.employee.id;other_id=n.manager.id;select_pack(n);observed=[]
    original=payroll_variance.employee_fk_read
    def check(db,actor,scope,statement):
        accepted=original(db,actor,scope,statement)
        if accepted:
            observed.append(True)
            assert not original(db,actor,scope,select(Employee.id).where(Employee.id==other_id))
            assert not original(db,actor,scope,select(Employee).where(Employee.id==own_id))
            assert not original(db,actor,scope,select(Employee.personal_email).where(Employee.id==own_id))
            assert not original(db,actor,scope,select(Employee.id).join(User,User.id==Employee.user_id).where(Employee.id==own_id))
            assert not original(db,actor,scope,select(Employee.__table__.c.id).where(Employee.__table__.c.id==own_id))
        return accepted
    monkeypatch.setattr(payroll_variance,'employee_fk_read',check)
    real_project=payroll_variance.project
    def project(db,actor,identity):
        scope=db.info['business_common_core_scope'];statement=select(Employee.id).where(Employee.id==own_id)
        before=db._flushing
        try:
            db._flushing=True
            assert not original(db,actor,scope,statement),'A forged flush flag is not a materialization lease'
        finally:db._flushing=before
        result=real_project(db,actor,identity)
        try:
            db._flushing=True
            assert not original(db,actor,scope,statement),'A completed lease cannot be reused'
        finally:db._flushing=before
        return result
    monkeypatch.setattr(payroll_variance,'project',project)
    result=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.headers)
    assert result.status_code==200,result.text
    assert observed and len(result.json())==1
    repeated=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/variance',headers=n.headers)
    assert repeated.status_code==200,repeated.text
    assert len(repeated.json())==1


def test_variance_deleted_source_cannot_change_inside_lease(register_case,monkeypatch):
    from app.business_packs import payroll_variance
    from app.models.payroll import PayrollVarianceItem
    n=register_case;select_pack(n);path=f'/api/v1/payroll/runs/{n.run.id}/variance'
    initial=n.client.get(path,headers=n.headers);assert initial.status_code==200,initial.text
    identity=initial.json()[0]['id'];reason=initial.json()[0]['reason']
    original=payroll_variance.employee_fk_read
    def tampered(db,actor,scope,statement):
        lease=payroll_variance._LEASES.get(db)
        if lease:
            for row in lease['deleted']:
                if row in db.deleted:row.reason='Unvalidated historical mutation'
        return original(db,actor,scope,statement)
    monkeypatch.setattr(payroll_variance,'employee_fk_read',tampered)
    denied=n.client.get(path,headers=n.headers)
    assert denied.status_code==403,denied.text
    row=n.db.query(PayrollVarianceItem).filter_by(id=identity).one()
    assert row.reason==reason


def test_variance_old_only_source_requires_reconciliation(register_case):
    from app.models.payroll import PayrollVarianceItem,PayrollRecord
    n=register_case;select_pack(n);path=f'/api/v1/payroll/runs/{n.run.id}/variance'
    initial=n.client.get(path,headers=n.headers);assert initial.status_code==200,initial.text
    identity=initial.json()[0]['id']
    n.db.delete(n.db.query(PayrollRecord).filter_by(id=n.records[0].id).one());n.db.commit()
    denied=n.client.get(path,headers=n.headers)
    assert denied.status_code==409,denied.text
    assert n.db.query(PayrollVarianceItem).filter_by(id=identity).count()==1


def test_variance_present_changed_sidecar_is_not_native_cleanup(register_case,monkeypatch):
    from app.business_packs import payroll_variance
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    from app.models.payroll import PayrollVarianceItem
    n=register_case
    other=Branch(company_id=1,name='Variance foreign destination');n.db.add(other);n.db.commit();other_id=other.id
    select_pack(n);path=f'/api/v1/payroll/runs/{n.run.id}/variance'
    initial=n.client.get(path,headers=n.headers);assert initial.status_code==200,initial.text
    identity=initial.json()[0]['id'];original=payroll_variance.validate_rows;injected=[]
    def changed(db,actor,scope):
        lease=payroll_variance._LEASES.get(db)
        if lease and db.deleted and not injected:
            db.connection().execute(BranchOwnership.__table__.insert().values(company_id=1,branch_id=other_id,
                resource_table='payroll_variance_items',resource_key=str(identity),source='trusted-corruption-fixture'))
            injected.append(True)
        return original(db,actor,scope)
    monkeypatch.setattr(payroll_variance,'validate_rows',changed)
    denied=n.client.get(path,headers=n.headers)
    assert denied.status_code==409,denied.text
    assert injected and n.db.query(PayrollVarianceItem).filter_by(id=identity).count()==1
    owner=n.db.query(BranchOwnership).filter_by(resource_table='payroll_variance_items',resource_key=str(identity)).one()
    assert owner.branch_id==n.branch.id
