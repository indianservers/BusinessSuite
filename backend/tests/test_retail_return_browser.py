"""Visible real POS refund, with an explicitly posted-source fixture precondition."""
import os,json
from decimal import Decimal
import pytest
from app.apps.srm.models import SRMInventoryBalance,SRMPOSReturn,SRMPOSCashMovement
from app.apps.fam.models import FAMVoucher
from app.business_packs.retail.models import RetailReturn
from tests.test_retail_return_http import retail_setup,post_original,scenario,catalog,directory_identity


@pytest.mark.skipif(os.getenv('RUN_RETAIL_RETURN_BROWSER')!='1',reason='Opt-in actual native Retail browser flow')
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('already_posted',[True,False])
def test_visible_retail_refund_with_explicit_accounting_posting_precondition(client,db,retail_setup,monkeypatch,already_posted,width):
    from tests.test_control_browser import test_control_center_real_browser
    headers,actor,branch,context,register,product,warehouse=retail_setup
    original=client.request
    observed=[]
    def forward(method,url,**kwargs):
        response=original(method,url,**kwargs)
        if str(method).upper()=='POST' and str(url).split('?')[0].endswith('/api/v1/srm/service-checkout') and response.status_code==201:
            # Explicit source setup, not an assertion that production POS
            # auto-posts. Forward the actual native response without alteration.
            before=(response.status_code,response.content,tuple(response.headers.items()))
            observed.append(response.json()['id'])
            if already_posted:
                post_original(db,(headers,actor,branch,context,response.json(),register,product,warehouse))
            assert before==(response.status_code,response.content,tuple(response.headers.items()))
        return response
    monkeypatch.setattr(client,'request',forward)
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','retail-return-live.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],
        'branch':str(branch),'context':str(context),'already_posted':already_posted,'width':width}))
    test_control_center_real_browser(client,db,None,headers)
    assert len(observed)==1
    assert db.query(SRMInventoryBalance).filter_by(product_id=product,warehouse_id=warehouse).one().quantity==(4 if already_posted else 3)
    assert db.query(RetailReturn).count()==db.query(SRMPOSReturn).count()==(1 if already_posted else 0)
    assert db.query(FAMVoucher).count()==(4 if already_posted else 0)
    assert db.query(SRMPOSCashMovement).filter_by(movement_type='cash_out').count()==(1 if already_posted else 0)
