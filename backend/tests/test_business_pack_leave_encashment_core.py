"""Real native leave encashment; selected pack roles confer no payroll rights."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_common_core import core_case, select_pack

ROOT = '/api/v1/hrms/leave-encashment'


@pytest.fixture
def encash_case(leave_case):
    from app.models.payroll import EmployeeSalary
    from app.branches.models import BranchOwnership
    n = leave_case
    n.kind.encashable = True
    salary = EmployeeSalary(employee_id=n.employee.id, ctc=Decimal('312000'), basic=Decimal('13000'),
        hra=Decimal('6500'), effective_from=date(2020,1,1), is_active=True)
    n.db.add(salary); n.db.flush()
    n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table='employee_salaries',
        resource_key=str(salary.id),source='verified-canonical-employee-salary-fixture'))
    n.db.commit()
    allocated = n.client.post('/api/v1/leave/balance/allocate',headers=n.admin_headers,params={
        'employee_id':n.manager.id,'leave_type_id':n.kind.id,'year':date.today().year,'days':20})
    assert allocated.status_code == 200, allocated.text
    n.salary = salary
    assert 'payroll_view' not in {permission.name for permission in n.user.role.permissions}
    return n


def request(n, headers=None, days=2, **extra):
    return n.client.post(ROOT+'/request',headers=headers or n.headers,json={
        'leaveTypeId':n.kind.id,'daysToEncash':days,'remarks':'Native encashment request',**extra})


@pytest.mark.parametrize('pack',['hospital','salon'])
def test_native_own_encashment_approval_reuses_one_payroll_line_and_balance(encash_case, pack):
    from app.models.payroll import LeaveEncashmentRequest, LeaveEncashmentLine, PayrollRun, PayrollPeriod, PayrollPayGroup
    from app.models.leave import LeaveBalanceLedger
    n = encash_case
    context = select_pack(n,pack)
    headers = {**n.headers,'X-Suite-Pack-Context':str(context.id)}
    before = n.client.get(ROOT,headers=headers)
    assert before.status_code == 200, before.text
    assert before.json() == []
    created = request(n,headers)
    assert created.status_code == 201, created.text
    row = created.json()
    assert (row['employeeId'],row['daysToEncash'],row['encashmentRate'],row['amount'],row['status']) == (
        n.employee.id,2,500,1000,'submitted')
    assert not {'ctc','basic','hra','structure_id'} & set(row)
    for selector in (str(context.id),'invalid-selector','9999999'):
        response=n.client.get(ROOT,headers={**n.headers,'X-Suite-Pack-Context':selector})
        assert response.status_code == 200, response.text
        assert [item['id'] for item in response.json()] == [row['id']]
    approved=n.client.post(ROOT+f"/{row['id']}/approve",headers=n.admin_headers,json={'remarks':'Native reviewed'})
    assert approved.status_code == 200, approved.text
    n.db.expire_all()
    stored=n.db.get(LeaveEncashmentRequest,row['id'])
    line=n.db.get(LeaveEncashmentLine,stored.leave_encashment_line_id)
    assert (stored.status,stored.approved_by,stored.remarks)==('approved',n.admin.id,'Native reviewed')
    assert (line.employee_id,line.days,line.rate_per_day,line.amount,line.approved_by)==(n.employee.id,2,500,1000,n.admin.id)
    assert n.db.get(type(n.balance),n.balance.id).used==2
    ledger=n.db.query(LeaveBalanceLedger).filter_by(employee_id=n.employee.id,transaction_type='encashment').one()
    assert (ledger.amount,ledger.balance_after,ledger.leave_balance_id,ledger.created_by)==(-2,18,n.balance.id,n.admin.id)
    assert n.db.query(PayrollPeriod).count()==n.db.query(PayrollPayGroup).count()==1
    assert n.db.query(PayrollRun).count()==0
    retry=n.client.post(ROOT+f"/{row['id']}/approve",headers=n.admin_headers,json={'remarks':'Duplicate'})
    assert retry.status_code==400,retry.text
    assert n.db.query(LeaveEncashmentLine).count()==1
    assert n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==1


def test_native_rejection_keeps_payroll_and_balance_unchanged(encash_case):
    from app.models.payroll import LeaveEncashmentLine,PayrollPeriod,PayrollPayGroup
    from app.models.leave import LeaveBalanceLedger
    n=encash_case;select_pack(n)
    created=request(n,days=1)
    assert created.status_code==201,created.text
    identity=created.json()['id']
    denied=n.client.post(ROOT+f'/{identity}/approve',headers=n.headers,json={})
    assert denied.status_code==403,denied.text
    rejected=n.client.post(ROOT+f'/{identity}/reject',headers=n.admin_headers,json={'remarks':'Native rejected'})
    assert rejected.status_code==200,rejected.text
    assert (rejected.json()['status'],rejected.json()['approvedBy'],rejected.json()['remarks'])==('rejected',n.admin.id,'Native rejected')
    n.db.expire_all()
    assert n.db.get(type(n.balance),n.balance.id).used==0
    assert n.db.query(LeaveEncashmentLine).count()==n.db.query(PayrollPeriod).count()==n.db.query(PayrollPayGroup).count()==0
    assert n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==0
    cancel=n.client.post(ROOT+f'/{identity}/cancel',headers=n.headers,json={})
    assert cancel.status_code==404,cancel.text


def test_own_list_does_not_query_salary_or_return_other_employee(encash_case):
    from sqlalchemy import event
    n=encash_case
    own=request(n)
    assert own.status_code==201,own.text
    other=request(n,n.admin_headers,employeeId=n.manager.id)
    assert other.status_code==201,other.text
    select_pack(n,'salon')
    statements=[]
    def trace(conn,cursor,statement,parameters,context,executemany):
        if 'employee_salaries' in statement: statements.append(statement)
    connection=n.db.get_bind();event.listen(connection,'before_cursor_execute',trace)
    try:response=n.client.get(ROOT,headers=n.headers,params={'employeeId':n.manager.id})
    finally:event.remove(connection,'before_cursor_execute',trace)
    assert response.status_code==200,response.text
    assert [item['id'] for item in response.json()]==[own.json()['id']]
    assert statements==[]


@pytest.mark.parametrize('denial',['policy','branch','legacy-branch','revoked'])
def test_encashment_cannot_override_native_write_denials(encash_case,denial):
    from app.access.models import AccessPolicy
    from app.branches.models import BranchGrant
    from app.models.payroll import LeaveEncashmentRequest
    n=encash_case;select_pack(n)
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    if denial=='policy':policy.grants={'hrms':{**policy.grants['hrms'],'actions':['view']}}
    elif denial in {'branch','legacy-branch'}:
        if denial=='legacy-branch':n.db.delete(policy);n.user.role.permissions=[]
        n.db.query(BranchGrant).filter_by(user_id=n.user.id,branch_id=n.branch.id).one().can_write=False
    else:policy.status='suspended'
    n.db.commit()
    response=request(n)
    assert response.status_code==403,response.text
    assert n.db.query(LeaveEncashmentRequest).count()==0


def test_private_salary_is_not_adopted_and_own_list_still_needs_no_salary(encash_case):
    from app.business_packs.models import PackRecordOwnership
    from app.models.payroll import LeaveEncashmentRequest
    n=encash_case;context=select_pack(n)
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.branch.id,context_id=context.id,
        resource_table='employee_salaries',resource_key=str(n.salary.id)))
    n.db.commit()
    response=request(n)
    assert response.status_code==503,response.text
    assert n.db.query(LeaveEncashmentRequest).count()==0
    response=n.client.get(ROOT,headers=n.headers)
    assert response.status_code==200,response.text
    assert response.json()==[]


def test_cached_private_employee_is_not_an_encashment_profile(encash_case):
    from app.business_packs.models import PackRecordOwnership
    from app.models.payroll import LeaveEncashmentRequest
    n=encash_case;context=select_pack(n)
    # Load the real relationship before binding the independent native purpose.
    assert n.user.employee.id==n.employee.id
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.branch.id,context_id=context.id,
        resource_table='employees',resource_key=str(n.employee.id)))
    n.db.commit()
    listed=n.client.get(ROOT,headers=n.headers)
    assert listed.status_code==400,listed.text
    assert listed.json()['detail']=='No employee profile is linked to this account'
    created=request(n)
    assert created.status_code==400,created.text
    assert n.db.query(LeaveEncashmentRequest).count()==0


def test_forged_payroll_output_rolls_back_period_group_line_and_debit(encash_case,monkeypatch):
    from app.api.v1 import leave_payroll
    from app.models.payroll import LeaveEncashmentRequest,LeaveEncashmentLine,PayrollPeriod,PayrollPayGroup
    from app.models.leave import LeaveBalanceLedger
    n=encash_case;select_pack(n)
    created=request(n)
    assert created.status_code==201,created.text
    original=leave_payroll.LeaveEncashmentLine
    def corrupt(**values):
        values['amount']+=1
        return original(**values)
    monkeypatch.setattr(leave_payroll,'LeaveEncashmentLine',corrupt)
    response=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=n.admin_headers,json={})
    assert response.status_code==403,response.text
    n.db.expire_all()
    assert n.db.get(LeaveEncashmentRequest,created.json()['id']).status=='submitted'
    assert n.db.get(type(n.balance),n.balance.id).used==0
    assert n.db.query(LeaveEncashmentLine).count()==n.db.query(PayrollPeriod).count()==n.db.query(PayrollPayGroup).count()==0
    assert n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==0


@pytest.mark.parametrize('status',['Locked','Closed'])
def test_closed_native_payroll_period_rejects_before_any_financial_effect(encash_case,status):
    from app.models.payroll import PayrollPayGroup,PayrollPeriod,LeaveEncashmentLine,LeaveEncashmentRequest
    from app.models.leave import LeaveBalanceLedger
    from app.branches.models import BranchOwnership
    from app.api.v1.leave_payroll import _month_bounds
    n=encash_case;select_pack(n)
    group=PayrollPayGroup(name=uuid4().hex,code=uuid4().hex[:12],branch_id=n.branch.id,is_active=True,is_default=True)
    n.db.add(group);n.db.flush()
    today=date.today();start,end=_month_bounds(f'{today.year}-{today.month:02d}')
    period=PayrollPeriod(pay_group_id=group.id,month=today.month,year=today.year,
        financial_year=f'{today.year}-{str(today.year+1)[-2:]}',period_start=start,period_end=end,payroll_date=end,status=status)
    n.db.add(period);n.db.flush()
    for row in (group,period):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,
        resource_table=row.__tablename__,resource_key=str(row.id),source='verified-native-payroll-fixture'))
    n.db.commit()
    created=request(n)
    assert created.status_code==201,created.text
    response=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=n.admin_headers,json={})
    assert response.status_code==409,response.text
    n.db.expire_all()
    assert n.db.get(LeaveEncashmentRequest,created.json()['id']).status=='submitted'
    assert n.db.get(type(n.balance),n.balance.id).used==0
    assert n.db.query(LeaveEncashmentLine).count()==0
    assert n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==0


@pytest.mark.parametrize('source',['salary','payroll','raw','bulk'])
def test_encashment_does_not_grant_payroll_or_generic_sql_access(encash_case,monkeypatch,source):
    from app.api.v1 import leave_payroll
    from app.models.payroll import EmployeeSalary,PayrollRun,LeaveEncashmentRequest
    from sqlalchemy import text
    n=encash_case;select_pack(n)
    original=leave_payroll._can_manage_leave_payroll
    def attack(actor):
        if 'business_common_core_scope' not in n.db.info:return original(actor)
        if source=='salary':n.db.query(EmployeeSalary).all()
        elif source=='payroll':n.db.query(PayrollRun).all()
        elif source=='raw':n.db.execute(text('SELECT 1')).all()
        else:n.db.query(LeaveEncashmentRequest).delete()
        return False
    monkeypatch.setattr(leave_payroll,'_can_manage_leave_payroll',attack)
    response=n.client.get(ROOT,headers=n.headers)
    assert response.status_code==403,response.text


@pytest.mark.parametrize('scope',['companywide','other-branch','foreign-company','foreign-legacy','private-companywide'])
def test_blind_payroll_lock_respects_native_company_scope(encash_case,scope):
    from app.models.payroll import PayrollRun,LeaveEncashmentLine,LeaveEncashmentRequest
    from app.models.company import Branch,Company
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackActivation,PackContext,PackRecordOwnership
    n=encash_case;select_pack(n)
    other=Branch(company_id=1,name='Different native anchor branch');n.db.add(other);n.db.flush()
    company=1
    if scope in {'foreign-company','foreign-legacy'}:
        n.db.add(Company(id=77,name='Foreign payroll company'));n.db.flush()
        other=Branch(company_id=77,name='Foreign payroll branch');n.db.add(other);n.db.flush();company=77
    run=PayrollRun(company_id=None if scope=='foreign-legacy' else company,branch_id=other.id if scope=='other-branch' else None,
        month=date.today().month,year=date.today().year,status='Locked')
    n.db.add(run);n.db.flush()
    n.db.add(BranchOwnership(company_id=company,branch_id=other.id,resource_table='payroll_runs',
        resource_key=str(run.id),source='verified-native-payroll-scope'))
    if scope=='private-companywide':
        activation=n.db.query(PackActivation).filter_by(company_id=1,pack_key='hospital').one()
        context=PackContext(company_id=1,branch_id=other.id,activation_id=activation.id,
            pack_key='hospital',pack_version=1,state='active')
        n.db.add(context);n.db.flush()
        n.db.add(PackRecordOwnership(company_id=1,branch_id=other.id,context_id=context.id,
            resource_table='payroll_runs',resource_key=str(run.id)))
    n.db.commit()
    created=request(n)
    assert created.status_code==201,created.text
    response=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=n.admin_headers,json={})
    expected=503 if scope=='private-companywide' else 409 if scope=='companywide' else 200
    assert response.status_code==expected,response.text
    assert str(run.id) not in response.json().get('detail','') if response.status_code>=400 else True
    n.db.expire_all()
    assert n.db.get(LeaveEncashmentRequest,created.json()['id']).status==('approved' if expected==200 else 'submitted')
    assert n.db.query(LeaveEncashmentLine).count()==(1 if expected==200 else 0)
    assert n.db.get(type(n.balance),n.balance.id).used==(2 if expected==200 else 0)


def test_raw_all_alias_writes_only_the_verified_concrete_native_destination(encash_case):
    from app.models.payroll import LeaveEncashmentRequest,LeaveEncashmentLine,PayrollPayGroup,PayrollPeriod
    from app.models.leave import LeaveBalanceLedger
    from app.branches.models import BranchOwnership
    n=encash_case;select_pack(n)
    created=request(n)
    assert created.status_code==201,created.text
    headers={**n.admin_headers,'X-Suite-Branch':'all'}
    listed=n.client.get(ROOT,headers=headers)
    assert listed.status_code==200,listed.text
    assert created.json()['id'] in {item['id'] for item in listed.json()}
    # Native branch context deliberately normalizes the retired raw All write
    # selector to the actor's concrete verified home/writable destination.
    response=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=headers,json={})
    assert response.status_code==200,response.text
    second=request(n,headers,employeeId=n.employee.id)
    assert second.status_code==201,second.text
    assert n.db.query(LeaveEncashmentRequest).count()==2
    assert n.db.query(LeaveEncashmentLine).count()==n.db.query(PayrollPayGroup).count()==n.db.query(PayrollPeriod).count()==1
    owned=[('leave_encashment_requests',created.json()['id']),('leave_encashment_requests',second.json()['id']),
        ('leave_encashment_lines',n.db.query(LeaveEncashmentLine).one().id),
        ('payroll_pay_groups',n.db.query(PayrollPayGroup).one().id),('payroll_periods',n.db.query(PayrollPeriod).one().id),
        ('leave_balance_ledger',n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').one().id)]
    for table,identity in owned:
        owner=n.db.query(BranchOwnership).filter_by(resource_table=table,resource_key=str(identity)).one()
        assert (owner.company_id,owner.branch_id)==(1,n.branch.id)
    rejected=n.client.post(ROOT+f"/{second.json()['id']}/reject",headers=headers,json={'remarks':'Native alias review'})
    assert rejected.status_code==200,rejected.text
    assert rejected.json()['status']=='rejected'


def test_foreign_default_group_collision_is_honest_and_never_adopted(encash_case):
    from app.models.company import Company,Branch
    from app.models.payroll import PayrollPayGroup,PayrollPeriod,LeaveEncashmentLine,LeaveEncashmentRequest
    from app.branches.models import BranchOwnership
    n=encash_case;select_pack(n)
    n.db.add(Company(id=77,name='Other payroll configuration'));n.db.flush()
    branch=Branch(company_id=77,name='Other payroll branch');n.db.add(branch);n.db.flush()
    group=PayrollPayGroup(branch_id=branch.id,name='Default Payroll Group',code='DEFAULT',is_active=True,is_default=True)
    n.db.add(group);n.db.flush()
    n.db.add(BranchOwnership(company_id=77,branch_id=branch.id,resource_table='payroll_pay_groups',
        resource_key=str(group.id),source='verified-native-foreign-definition'))
    n.db.commit()
    created=request(n)
    assert created.status_code==201,created.text
    response=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=n.admin_headers,json={})
    assert response.status_code==409,response.text
    assert response.json()['detail']=='Configure an authorized payroll group for the selected branch'
    n.db.expire_all()
    assert n.db.get(LeaveEncashmentRequest,created.json()['id']).status=='submitted'
    assert n.db.query(PayrollPayGroup).count()==1
    assert n.db.query(PayrollPeriod).count()==n.db.query(LeaveEncashmentLine).count()==0


def test_corrupt_stored_amount_cannot_pay_but_can_be_rejected(encash_case):
    from sqlalchemy import update
    from app.models.payroll import LeaveEncashmentRequest,LeaveEncashmentLine,PayrollPayGroup,PayrollPeriod
    from app.models.leave import LeaveBalanceLedger
    n=encash_case;select_pack(n)
    created=request(n)
    assert created.status_code==201,created.text
    identity=created.json()['id']
    # Trusted corruption setup, not an API override or new price from the client.
    n.db.connection().execute(update(LeaveEncashmentRequest).where(LeaveEncashmentRequest.id==identity).values(amount=Decimal('999')))
    n.db.commit()
    response=n.client.post(ROOT+f'/{identity}/approve',headers=n.admin_headers,json={})
    assert response.status_code==409,response.text
    assert response.json()['detail']=='Native encashment source requires reconciliation'
    n.db.expire_all()
    assert n.db.get(LeaveEncashmentRequest,identity).status=='submitted'
    assert n.db.get(type(n.balance),n.balance.id).used==0
    assert n.db.query(LeaveEncashmentLine).count()==n.db.query(PayrollPayGroup).count()==n.db.query(PayrollPeriod).count()==0
    assert n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==0
    rejected=n.client.post(ROOT+f'/{identity}/reject',headers=n.admin_headers,json={'remarks':'Resolve inconsistent historical request'})
    assert rejected.status_code==200,rejected.text
    assert rejected.json()['status']=='rejected'
    assert rejected.json()['amount']==999


def test_salary_revision_does_not_reprice_a_valid_stored_encashment(encash_case):
    from app.models.payroll import LeaveEncashmentLine
    n=encash_case;select_pack(n)
    created=request(n)
    assert created.status_code==201,created.text
    n.salary.basic=Decimal('26000');n.salary.ctc=Decimal('624000');n.db.commit()
    response=n.client.post(ROOT+f"/{created.json()['id']}/approve",headers=n.admin_headers,json={})
    assert response.status_code==200,response.text
    line=n.db.query(LeaveEncashmentLine).one()
    assert (line.rate_per_day,line.amount)==(Decimal('500'),Decimal('1000'))


@pytest.mark.parametrize('days',['0.001','1.001','1.25','10000'])
def test_unrepresentable_days_fail_before_native_encashment_writes(encash_case,days):
    from app.models.payroll import LeaveEncashmentRequest,LeaveEncashmentLine,PayrollPayGroup,PayrollPeriod
    from app.models.leave import LeaveBalanceLedger
    n=encash_case;select_pack(n)
    before=n.db.query(LeaveBalanceLedger).count()
    response=request(n,days=days)
    assert response.status_code==422,response.text
    assert n.db.query(LeaveEncashmentRequest).count()==n.db.query(LeaveEncashmentLine).count()==0
    assert n.db.query(PayrollPayGroup).count()==n.db.query(PayrollPeriod).count()==0
    assert n.db.query(LeaveBalanceLedger).count()==before
    n.db.expire_all()
    assert n.db.get(type(n.balance),n.balance.id).used==0


@pytest.mark.parametrize('quantity,expected_days,expected_money',[('0.5','0.5','250'),('1.20','1.2','600')])
def test_representable_days_keep_exact_native_persisted_money_and_balance(encash_case,quantity,expected_days,expected_money):
    from app.models.payroll import LeaveEncashmentRequest
    n=encash_case;select_pack(n)
    response=request(n,days=quantity)
    assert response.status_code==201,response.text
    stored=n.db.get(LeaveEncashmentRequest,response.json()['id'])
    assert (stored.days_to_encash,stored.encashment_rate,stored.amount)==(Decimal(expected_days),Decimal('500'),Decimal(expected_money))
    approved=n.client.post(ROOT+f"/{stored.id}/approve",headers=n.admin_headers,json={})
    assert approved.status_code==200,approved.text
    n.db.expire_all()
    assert n.db.get(type(n.balance),n.balance.id).used==Decimal(expected_days)
    from app.models.leave import LeaveBalanceLedger
    ledger=n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').one()
    assert ledger.amount==-Decimal(expected_days)
    assert ledger.balance_after==Decimal('20')-Decimal(expected_days)


def test_historical_unrepresentable_quantity_cannot_pay_but_can_be_rejected(encash_case):
    from sqlalchemy import update
    from app.models.payroll import LeaveEncashmentRequest,LeaveEncashmentLine,PayrollPayGroup,PayrollPeriod
    from app.models.leave import LeaveBalanceLedger
    n=encash_case;select_pack(n)
    created=request(n)
    assert created.status_code==201,created.text
    identity=created.json()['id']
    n.db.connection().execute(update(LeaveEncashmentRequest).where(LeaveEncashmentRequest.id==identity).values(
        days_to_encash=Decimal('1.25'),amount=Decimal('625')))
    n.db.commit()
    response=n.client.post(ROOT+f'/{identity}/approve',headers=n.admin_headers,json={})
    assert response.status_code==409,response.text
    n.db.expire_all()
    assert n.db.get(LeaveEncashmentRequest,identity).status=='submitted'
    assert n.db.get(type(n.balance),n.balance.id).used==0
    assert n.db.query(LeaveEncashmentLine).count()==n.db.query(PayrollPayGroup).count()==n.db.query(PayrollPeriod).count()==0
    assert n.db.query(LeaveBalanceLedger).filter_by(transaction_type='encashment').count()==0
    response=n.client.post(ROOT+f'/{identity}/reject',headers=n.admin_headers,json={})
    assert response.status_code==200,response.text
    assert response.json()['status']=='rejected'


def test_actual_production_binding_carries_only_native_encashment_authority(encash_case,monkeypatch):
    from app.business_packs.common_core import OPERATIONS,CommonCoreScope
    from app.business_packs.common_binding import CoreRequestBinding
    from app.api.v1 import leave_payroll
    n=encash_case;select_pack(n,'salon')
    observed=[];original=leave_payroll._encashment_rate
    def inspect_binding(db,employee_id):
        scope=db.info.get('business_common_core_scope')
        assert isinstance(scope,CommonCoreScope)
        assert isinstance(scope.binding,CoreRequestBinding)
        assert scope.operation is OPERATIONS[('POST',ROOT+'/request')]
        assert scope.binding.purpose=='hrms.leave_encashment'
        assert (scope.user_id,scope.company_id,scope.branch.branch_id)==(n.user.id,1,n.branch.id)
        assert db.info.get('business_pack_scope') is None
        observed.append(scope.binding.route)
        return original(db,employee_id)
    monkeypatch.setattr(leave_payroll,'_encashment_rate',inspect_binding)
    response=request(n,{**n.headers,'X-Suite-Pack-Context':'untrusted-does-not-grant-payroll'})
    assert response.status_code==201,response.text
    assert observed==[ROOT+'/request']
    assert 'payroll_view' not in {permission.name for permission in n.user.role.permissions}
