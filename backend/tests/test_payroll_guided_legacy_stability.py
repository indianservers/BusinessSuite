"""Unpublished candidate cannot alter native legacy Guided Payroll."""
from tests.test_business_pack_common_core import core_case
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_leave_encashment_core import encash_case
from tests.test_business_pack_payroll_register import register_case


def test_unselected_native_guided_retains_original_handler(register_case,monkeypatch):
    from app.api.v1 import payroll_guided
    from app.business_packs.common_core import OPERATIONS
    n=register_case
    assert ('GET','/api/v1/payroll/runs/{run_id}/guided') not in OPERATIONS
    original=payroll_guided.native_overview;calls=[]
    def observe(run_id,db,user):
        assert db.info.get('business_common_core_scope') is None
        calls.append(run_id)
        return original(run_id,db,user)
    monkeypatch.setattr(payroll_guided,'native_overview',observe)
    response=n.client.get(f'/api/v1/payroll/runs/{n.run.id}/guided',headers=n.admin_headers)
    assert response.status_code==200,response.text
    assert calls==[n.run.id]
    assert response.json()['id']==n.run.id and len(response.json()['records'])==2
