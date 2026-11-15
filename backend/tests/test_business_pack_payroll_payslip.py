"""Exact native payslips retain self/privacy/finalization semantics across packs."""
from types import MappingProxyType
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case
from tests.test_business_pack_payroll_register import register_case

@pytest.fixture(autouse=True)
def payslip_candidate(monkeypatch):
    from app.business_packs import common_core,payroll_payslip
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        **payroll_payslip.candidate_operations(common_core.CoreOperation)}))


def fetch(n,**params):
    return n.client.get('/api/v1/payroll/payslip',headers=n.headers,params={'month':n.run.month,'year':n.run.year,**params})


def test_native_payslip_minimal_own_money_never_reads_salary_bank(register_case):
    n=register_case;n.employee.account_number='9876543210123456';n.employee.pan_number='ABCDE1234F';n.db.commit();select_pack(n)
    result=fetch(n);assert result.status_code==200,result.text
    value=result.json();assert value['id']==n.records[0].id and value['employee_id']==n.employee.id
    assert value['gross_salary']==15000 and value['net_salary']==13500
    assert set(value['employee'])=={'id','employee_id','first_name','last_name'}
    assert not any(secret in result.text for secret in ('312000','9876543210123456','ABCDE1234F'))
    n.db.refresh(n.run);assert n.run.total_net==27000 and n.run.status=='calculated'


def test_native_readonly_branch_preserves_existing_payslip_read(register_case):
    from app.branches.models import BranchGrant
    n=register_case;n.db.query(BranchGrant).filter_by(user_id=n.user.id,branch_id=n.branch.id).one().can_write=False
    n.db.commit();select_pack(n)
    result=fetch(n);assert result.status_code==200,result.text
    assert result.json()['employee_id']==n.employee.id


def test_native_empty_employee_role_needs_finalized_own_record(register_case):
    from app.access.models import AccessPolicy
    n=register_case;n.user.role.name='employee';n.user.role.permissions=[]
    n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).delete();n.db.commit();select_pack(n)
    missing=fetch(n);assert missing.status_code==404,missing.text
    n.run.status='locked';n.db.commit()
    own=fetch(n);assert own.status_code==200,own.text
    assert own.json()['employee_id']==n.employee.id
    other=fetch(n,employee_id=n.manager.id);assert other.status_code==403,other.text


def test_native_payslip_descriptor_remains_unpublished():
    from app.business_packs import common_core,payroll_payslip
    assert not payroll_payslip.operations(common_core.CoreOperation)


def test_payslip_preserves_native_calendar_ytd_currency_and_minimal_department(register_case,monkeypatch):
    from decimal import Decimal
    from app.models.company import Department
    from app.models.payroll import PayrollDeliveryProfile,PayrollRun,PayrollRecord,PayrollComponent
    from app.branches.models import BranchOwnership
    n=register_case
    from app.access.models import AccessPolicy
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':'organization'}}
    department=Department(name='Canonical source department',branch_id=n.branch.id,organization_id=1,created_by=n.user.id)
    n.db.add(department);n.db.flush();n.employee.department_id=department.id
    previous=PayrollRun(company_id=1,branch_id=n.branch.id,month=1,year=n.run.year,status='locked')
    n.db.add(previous);n.db.flush()
    before=PayrollRecord(payroll_run_id=previous.id,employee_id=n.employee.id,gross_salary=12000,total_deductions=2000,net_salary=10000,
        pf_employer=1000,reimbursements=500,converted_currency='INR')
    n.db.add(before);n.db.flush()
    component=PayrollComponent(record_id=n.records[0].id,component_name='Canonical basic earnings',component_type='Earning',amount=15000)
    n.db.add(component);n.db.flush()
    for row in (department,previous,before,component):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,
        resource_table=row.__tablename__,resource_key=str(row.id),source='verified-payslip-source'))
    n.db.add(PayrollDeliveryProfile(company_id=1,ytd_basis='calendar',fy_start_month=1,payout_secret_encrypted='PRIVATE-PAYOUT-SECRET',branding={'private':'PRIVATE-BRANDING'}))
    n.db.commit()
    from app.business_packs import common_core
    from app.services import payroll_delivery
    original_ops=common_core.OPERATIONS
    with monkeypatch.context() as legacy_patch:
        legacy_patch.setattr(common_core,'OPERATIONS',MappingProxyType({key:op for key,op in original_ops.items() if op.purpose!='hrms.payroll_payslip'}))
        legacy=fetch(n)
    assert legacy.status_code==200,legacy.text
    assert legacy.json()['ytd_basis']=='calendar',legacy.text
    select_pack(n)
    result=fetch(n);assert result.status_code==200,result.text
    value=result.json();assert value['ytd_basis']=='calendar' and value['financial_year']==str(n.run.year)
    assert value['ytd_period_start']==f'{n.run.year}-01-01' and value['department']=='Canonical source department'
    assert value['ytd']['gross_salary']==27000 and value['ytd']['net_salary']==23500
    assert value['earnings']==[{'component_name':'Canonical basic earnings','component_type':'Earning','amount':15000}]
    assert 'PRIVATE-PAYOUT' not in result.text and 'PRIVATE-BRANDING' not in result.text


@pytest.mark.parametrize('attack',['salary','bank','pan','profile-secret','raw','unknown','write','merge'])
def test_private_payslip_reader_rejects_unaudited_sources(register_case,monkeypatch,attack):
    from app.api.v1 import payroll
    from app.models.payroll import EmployeeSalary,PayrollDeliveryProfile,PayrollRun
    from app.models.employee import Employee
    from app.apps.srm.models import SRMInvoice
    from sqlalchemy import select
    n=register_case;identity=n.run.id;select_pack(n)
    def unsafe(month,year,employee_id,db,user):
        if attack=='salary':db.query(EmployeeSalary).all()
        elif attack=='bank':db.query(Employee.account_number).all()
        elif attack=='pan':db.query(Employee.pan_number).all()
        elif attack=='profile-secret':db.query(PayrollDeliveryProfile.payout_secret_encrypted).all()
        elif attack=='raw':db.execute(select(Employee.__table__.c.first_name)).all()
        elif attack=='unknown':db.query(SRMInvoice).all()
        elif attack=='merge':db.merge(PayrollRun(id=identity))
        else:db.query(PayrollRun).delete()
        return {}
    monkeypatch.setattr(payroll,'native_payslip',unsafe)
    denied=fetch(n);assert denied.status_code==403,denied.text
    n.db.refresh(n.run);assert n.run.total_net==27000


@pytest.mark.parametrize('source',['employee','record','fiscal'])
def test_pack_private_source_cannot_be_adopted_for_common_payslip(register_case,source):
    from app.business_packs.models import PackRecordOwnership
    from app.models.payroll import PayrollDeliveryProfile
    n=register_case;context=select_pack(n)
    row=n.employee if source=='employee' else n.records[0]
    if source=='fiscal':
        row=PayrollDeliveryProfile(company_id=1,ytd_basis='calendar',fy_start_month=1);n.db.add(row);n.db.flush()
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.branch.id,context_id=context.id,resource_table=row.__tablename__,resource_key=str(row.id)))
    n.db.commit();denied=fetch(n)
    assert denied.status_code=={'employee':400,'record':404,'fiscal':503}[source],denied.text
    assert 'Canonical Specialist' not in denied.text


def test_explicit_disabled_native_module_is_not_a_self_payslip_grant(register_case):
    from app.access.models import AccessPolicy
    n=register_case;n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one().grants={'hrms':{'enabled':False}}
    n.db.commit();select_pack(n)
    denied=fetch(n);assert denied.status_code==403,denied.text


def test_native_own_fiscal_visibility_matches_unchanged_legacy(register_case,monkeypatch):
    from app.models.payroll import PayrollDeliveryProfile
    from app.business_packs import common_core
    n=register_case;n.db.add(PayrollDeliveryProfile(company_id=1,ytd_basis='calendar',fy_start_month=1,
        payout_secret_encrypted='INVISIBLE-SOURCE-SECRET'));n.db.commit()
    original=common_core.OPERATIONS
    with monkeypatch.context() as patch:
        patch.setattr(common_core,'OPERATIONS',MappingProxyType({key:op for key,op in original.items() if op.purpose!='hrms.payroll_payslip'}))
        legacy=fetch(n)
    assert legacy.status_code==200,legacy.text
    assert legacy.json()['ytd_basis']=='financial'
    select_pack(n);candidate=fetch(n)
    assert candidate.status_code==200,candidate.text
    assert candidate.json()==legacy.json()
    assert 'INVISIBLE-SOURCE-SECRET' not in candidate.text


@pytest.mark.parametrize('attack',['outside','or','join','secret','entity'])
def test_fiscal_preflight_is_scalar_exact_and_lease_owned(register_case,monkeypatch,attack):
    from app.business_packs import payroll_payslip
    from app.models.payroll import PayrollDeliveryProfile
    from app.models.company import Company
    from sqlalchemy import select,or_
    n=register_case;select_pack(n);original=payroll_payslip.fiscal_policy;observed=[]
    def checked(db,company):
        lease=payroll_payslip._PREFLIGHT[db];scope=lease['scope'];actor=lease['actor'];before=lease['phase']
        lease['phase']='fiscal'
        try:
            columns=(PayrollDeliveryProfile.id,PayrollDeliveryProfile.ytd_basis,PayrollDeliveryProfile.fy_start_month)
            statement=select(*columns).where(PayrollDeliveryProfile.company_id==company)
            assert payroll_payslip.identity_read(db,actor,scope,statement)
            if attack=='or':statement=select(*columns).where(or_(PayrollDeliveryProfile.company_id==company,PayrollDeliveryProfile.company_id==77))
            elif attack=='join':statement=statement.join(Company,Company.id==PayrollDeliveryProfile.company_id)
            elif attack=='secret':statement=select(PayrollDeliveryProfile.payout_secret_encrypted).where(PayrollDeliveryProfile.company_id==company)
            elif attack=='entity':statement=select(PayrollDeliveryProfile).where(PayrollDeliveryProfile.company_id==company)
            else:
                payroll_payslip._PREFLIGHT.pop(db)
                try:assert not payroll_payslip.identity_read(db,actor,scope,statement)
                finally:payroll_payslip._PREFLIGHT[db]=lease
            if attack!='outside':assert not payroll_payslip.identity_read(db,actor,scope,statement)
            observed.append(True)
        finally:lease['phase']=before
        return original(db,company)
    monkeypatch.setattr(payroll_payslip,'fiscal_policy',checked)
    result=fetch(n);assert result.status_code==200,result.text
    assert observed


@pytest.mark.parametrize('owned_branch_definition',[True,False])
@pytest.mark.parametrize('explicit_other',[True,False])
def test_explicit_native_other_branch_payslip_matches_legacy_without_home_branch_body(register_case,monkeypatch,owned_branch_definition,explicit_other):
    from datetime import date
    from uuid import uuid4
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.models.payroll import PayrollRun,PayrollRecord
    from app.branches.models import BranchGrant,BranchOwnership
    from app.access.models import AccessPolicy
    from app.business_packs import common_core
    n=register_case
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':'organization'}};policy.version+=1
    branch=Branch(company_id=1,name='Authorized other payroll branch');n.db.add(branch);n.db.flush()
    n.db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=n.user.id,can_write=True))
    person=Employee(employee_id=uuid4().hex,first_name='Authorized',last_name='Other branch',branch_id=branch.id,
        date_of_joining=date(2020,1,1),status='Active');n.db.add(person);n.db.flush()
    run=PayrollRun(company_id=1,branch_id=branch.id,month=n.run.month,year=n.run.year,status='calculated');n.db.add(run);n.db.flush()
    record=PayrollRecord(payroll_run_id=run.id,employee_id=person.id,gross_salary=20000,net_salary=18000);n.db.add(record);n.db.flush()
    for row in ((branch,person,run,record) if owned_branch_definition else (person,run,record)):n.db.add(BranchOwnership(company_id=1,branch_id=branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='actual-other-branch-payslip'))
    n.db.commit();headers={**n.headers,'X-Suite-Branch':str(branch.id)}
    params={'month':run.month,'year':run.year}
    if explicit_other:params['employee_id']=person.id
    with monkeypatch.context() as patch:
        patch.setattr(common_core,'OPERATIONS',MappingProxyType({key:op for key,op in common_core.OPERATIONS.items() if op.purpose!='hrms.payroll_payslip'}))
        legacy=n.client.get('/api/v1/payroll/payslip',headers=headers,params=params)
    if explicit_other:assert legacy.status_code==(200 if owned_branch_definition else 404),legacy.text
    context=select_pack(n)
    candidate=n.client.get('/api/v1/payroll/payslip',headers={**headers,'X-Suite-Pack-Context':str(context.id)},params=params)
    assert candidate.status_code==legacy.status_code,(candidate.text,legacy.text)
    assert candidate.json()==legacy.json()
    if candidate.status_code==200:assert candidate.json()['employee_id']==person.id
    else:assert 'Authorized Other branch' not in candidate.text
