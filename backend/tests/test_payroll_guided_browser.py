"""Untouched production Payroll App, candidate backend descriptors only."""
import json
import re
from types import MappingProxyType
import pytest
from tests.test_business_pack_common_core import core_case,select_pack
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case
from tests.test_business_pack_payroll_register import register_case

@pytest.fixture(autouse=True)
def payroll_browser_candidates(monkeypatch):
    from app.business_packs import common_core,payroll_review,payroll_variance,payroll_payslip
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,
        **payroll_review.candidate_operations(common_core.CoreOperation),
        **payroll_variance.candidate_operations(common_core.CoreOperation),
        **payroll_payslip.candidate_operations(common_core.CoreOperation)}))



def prepared(n,mode):
    from datetime import date
    from uuid import uuid4
    from app.access.models import AccessPolicy,AccessMembership
    from app.models.employee import Employee
    from app.models.payroll import PayrollRecord,PayrollVarianceItem
    from app.models.user import Permission
    from app.branches.models import BranchOwnership,BranchGrant
    assert not n.user.is_superuser and not n.db.query(AccessMembership).filter_by(user_id=n.user.id,company_id=1).one().is_admin
    n.employee.reporting_manager_id=None;n.manager.reporting_manager_id=n.employee.id
    n.employee.account_number='9876543210123456';n.employee.ifsc_code='DEMO0000001';n.employee.pan_number='ABCDE1234F'
    unrelated=Employee(employee_id=uuid4().hex,first_name='Unrelated',last_name='Private employee',date_of_joining=date(2020,1,1),status='Active',branch_id=n.branch.id)
    n.db.add(unrelated);n.db.flush()
    record=PayrollRecord(payroll_run_id=n.run.id,employee_id=unrelated.id,gross_salary=15000,total_deductions=1500,net_salary=13500)
    n.db.add(record);n.db.flush()
    for row in (unrelated,record):n.db.add(BranchOwnership(company_id=1,branch_id=n.branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='native-browser-payroll-source'))
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    grant={**policy.grants['hrms'],'scope':'own' if mode=='readonly' else mode}
    if mode in {'organization','readonly'}:
        for name in ('payroll_run','payroll_approve'):
            permission=n.db.query(Permission).filter_by(name=name).first()
            if permission is None:permission=Permission(name=name,module='hrms');n.db.add(permission);n.db.flush()
            if permission not in n.user.role.permissions:n.user.role.permissions.append(permission)
        grant={**grant,'permissions':[*grant['permissions'],'payroll_run','payroll_approve'],'actions':['view','create','edit','approve']}
    policy.grants={'hrms':grant}
    n.run.total_gross=45000;n.run.total_deductions=4500;n.run.total_net=40500
    n.db.commit();context=select_pack(n)
    if mode=='readonly':
        n.db.query(BranchGrant).filter_by(user_id=n.user.id,branch_id=n.branch.id).one().can_write=False;n.db.commit()

    return context

@pytest.mark.parametrize('mode,count',[('own',1),('team',2),('organization',3),('readonly',1)])
def test_existing_default_guided_payroll_production_app(register_case,monkeypatch,mode,count):
    from tests.test_control_browser import test_control_center_real_browser
    from app.models.payroll import PayrollRecord,PayrollVarianceItem
    n=register_case;context=prepared(n,mode)
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    identity=n.client.get('/api/v1/auth/me',headers=headers)
    access=n.client.get('/api/v1/access/me',headers=headers)
    assert identity.status_code==access.status_code==200,(identity.text,access.text)
    user=identity.json();role=user['role'] if isinstance(user['role'],str) else user['role']['name']
    user.update(role=role,primary_role=role,access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','payroll-guided-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],
        'user':user,'branch':str(n.branch.id),'context':str(context.id),'count':count,'mode':mode,'run':n.run.id,'employee':n.employee.id}))
    try:
        test_control_center_real_browser(n.client,n.db,None,headers)
    except AssertionError as error:
        message=re.sub(r"Bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED]", str(error))
        message=re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED-JWT]", message)
        raise AssertionError(message) from None
    n.db.refresh(n.run);assert n.run.total_net==40500 and n.run.status=='calculated'
    assert n.db.query(PayrollRecord).filter_by(payroll_run_id=n.run.id).count()==3
    assert n.db.query(PayrollVarianceItem).filter_by(payroll_run_id=n.run.id).count()==(0 if mode=='readonly' else count)


def test_actual_same_mounted_native_downgrade_drops_private_guided_state(register_case,monkeypatch):
    from app.access.models import AccessPolicy
    from app.core.security import get_password_hash
    from tests.test_control_browser import test_control_center_real_browser
    n=register_case;context=prepared(n,'organization')
    for permission in n.user.role.permissions:
        if permission not in n.admin.role.permissions:n.admin.role.permissions.append(permission)
    admin_policy=n.db.query(AccessPolicy).filter_by(user_id=n.admin.id,company_id=1).one()
    admin_policy.grants={'hrms':{**admin_policy.grants['hrms'],
        'permissions':sorted({p.name for p in n.admin.role.permissions}),'actions':['view','create','edit','approve','delete'],'scope':'organization'}}
    password='Isolated-Payroll-Access-2026!';n.admin.hashed_password=get_password_hash(password);n.db.commit()
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    identity=n.client.get('/api/v1/auth/me',headers=headers);access=n.client.get('/api/v1/access/me',headers=headers)
    assert identity.status_code==access.status_code==200,(identity.text,access.text)
    user=identity.json();role=user['role'] if isinstance(user['role'],str) else user['role']['name']
    user.update(role=role,primary_role=role,access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','payroll-guided-downgrade-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],
        'user':user,'branch':str(n.branch.id),'context':str(context.id),'run':n.run.id,
        'adminToken':n.admin_headers['Authorization'].split(' ',1)[1],'adminPassword':password}))
    try:
        test_control_center_real_browser(n.client,n.db,None,headers)
    except AssertionError as error:
        message=re.sub(r"Bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED]", str(error))
        message=re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED-JWT]", message)
        raise AssertionError(message) from None
