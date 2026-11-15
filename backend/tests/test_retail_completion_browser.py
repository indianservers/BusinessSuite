"""Existing React stock/POS/report routes against unchanged native API responses."""
import json,os
from decimal import Decimal
import pytest
from app.apps.srm.models import SRMGoodsReceipt,SRMInvoice,SRMReceipt,SRMInventoryBalance
from tests.test_retail_return_http import retail_setup,scenario,catalog,directory_identity

@pytest.mark.skipif(os.getenv('RUN_RETAIL_COMPLETION_BROWSER')!='1',reason='Opt-in real Retail desktop/mobile screens')
@pytest.mark.parametrize('implicit',[False,True])
def test_existing_retail_stock_pos_reports_desktop_mobile(client,db,retail_setup,monkeypatch,implicit):
    from tests.test_control_browser import test_control_center_real_browser
    headers,actor,branch,context,register,product,warehouse=retail_setup
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','retail-completion.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],
        'branch':str(branch),'context':str(context),'product':product,'warehouse':warehouse,'implicit':implicit}))
    test_control_center_real_browser(client,db,None,headers)
    db.expire_all()
    assert db.query(SRMGoodsReceipt).count()==2
    assert db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==2
    assert db.query(SRMInventoryBalance).filter_by(product_id=product,warehouse_id=warehouse).one().quantity==Decimal('6.75')



@pytest.mark.skipif(os.getenv('RUN_RETAIL_COMPLETION_BROWSER')!='1',reason='Opt-in real legacy screen boundary')
def test_legacy_profitability_all_branch_fallback(client,db,scenario,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from tests.test_business_pack_http_integration import native_actor
    from app.models.user import Permission
    from app.access.models import AccessPolicy
    from app.branches.models import BranchPolicy
    headers,actor=native_actor(db,scenario[1])
    permission=db.query(Permission).filter_by(name='srm_profitability_view').one_or_none()
    if permission is None:permission=Permission(name='srm_profitability_view',description='Native profitability viewer');db.add(permission);db.flush()
    actor.role.permissions=[item for item in actor.role.permissions if item.name=='reports_view']+[permission]
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=actor.id).one()
    policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'permissions':['srm_profitability_view'],'actions':['view']}}
    db.add(BranchPolicy(company_id=1,user_id=actor.id,all_branches=True))
    db.commit()
    access=client.get('/api/v1/access/me',headers={**headers,'X-Suite-Branch':'all','X-Suite-Organization':'1'})
    assert access.status_code==200,access.text
    denied=client.get('/api/v1/srm/industry/capabilities',headers=headers)
    assert denied.status_code==403,denied.text
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','retail-completion.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],'branch':'all','legacy':True,'implicit':True}))
    test_control_center_real_browser(client,db,None,headers)
