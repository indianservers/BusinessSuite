"""Legacy FAM-only inventory does not require the new Pharma SRM scope probe."""
import json
from app.access.models import AccessPolicy
from app.branches.models import BranchGrant
from tests.test_settings_hub import actor
from tests.test_service_checkout import scenario,catalog,directory_identity


def test_native_fam_only_inventory_keeps_its_existing_view_without_srm_probe(client,db,scenario,monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    _,branch,_,_=scenario
    headers,user=actor(db,role='legacy-fam-reader',permissions=['fam_view'])
    user.organization_id=1
    db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={'fam':{'enabled':True,'permissions':['fam_view'],'actions':['view'],'scope':'organization'}}))
    db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=branch,can_write=False));db.commit()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','pharma-fam-legacy.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':headers['Authorization'].split(' ',1)[1],'branch':str(branch),'context':'','implicit':True}))
    test_control_center_real_browser(client,db,None,headers)
