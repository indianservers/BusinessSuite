"""Default published descriptors; no registration monkeypatch or API mock."""
import pytest
from copy import deepcopy
from tests.test_business_pack_common_core import core_case

@pytest.mark.parametrize('name',['hrms_home_core','payroll_review','payroll_variance','payroll_payslip'])
def test_default_descriptor_is_exact_candidate_readonly(name):
    import importlib
    from app.business_packs.common_core import CoreOperation, OPERATIONS
    module=importlib.import_module('app.business_packs.'+name)
    expected=module.candidate_operations(CoreOperation)
    assert expected and module.operations(CoreOperation)==expected
    for key,value in expected.items():
        assert key[0]=='GET' and OPERATIONS[key]==value
        allowed=frozenset({"payroll_variance_items"}) if name=="payroll_variance" else frozenset()
        assert value.writes==value.creates==value.deletes==allowed

@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')])
def test_specialist_pack_role_never_grants_native_payroll(core_case,pack,role):
    from app.business_packs.models import PackActivation,PackContext,PackUserGrant
    from app.access.models import AccessPolicy
    n=core_case
    activation=PackActivation(company_id=1,pack_key=pack,pack_version=1,state='active')
    n.db.add(activation);n.db.flush()
    context=PackContext(company_id=1,branch_id=n.branch.id,activation_id=activation.id,pack_key=pack,pack_version=1,state='active')
    n.db.add(context);n.db.flush()
    n.db.add(PackUserGrant(company_id=1,branch_id=n.branch.id,context_id=context.id,user_id=n.user.id,role=role));n.db.commit()
    policy=n.db.query(AccessPolicy).filter_by(company_id=1,user_id=n.user.id).one()
    before=(policy.version,deepcopy(policy.grants),tuple(sorted(permission.name for permission in n.user.role.permissions)))
    headers={**n.headers,'X-Suite-Pack-Context':str(context.id)}
    for suffix in ('guided','variance'):
        response=n.client.get('/api/v1/payroll/runs/1/'+suffix,headers=headers)
        assert response.status_code==403,response.text
        assert not any(secret in response.text for secret in ('gross_salary','net_salary','account_number','records'))
    n.db.refresh(policy);n.db.refresh(n.user.role)
    after=(policy.version,deepcopy(policy.grants),tuple(sorted(permission.name for permission in n.user.role.permissions)))
    assert after==before
