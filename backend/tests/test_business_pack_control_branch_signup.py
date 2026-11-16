"""Real signup/approval/login controls with production publication still empty."""
from uuid import uuid4
from datetime import datetime,timezone
import pytest
from sqlalchemy import select,update
from app.models.company import Branch,Company
from tests.test_public_signup import platform_store,platform_headers,activate,login,PASSWORD
ROOT='/api/v1/access/settings/business-packs'

@pytest.fixture
def owner(client,db,platform_store,platform_headers,monkeypatch):
    from app.core.config import settings
    from app.db.init_db import init_db
    from app.platform_owner.models import PlatformSignupRequest
    monkeypatch.setattr(settings,'BOOTSTRAP_ADMIN_EMAIL','bootstrap-native@example.com')
    monkeypatch.setattr(settings,'BOOTSTRAP_ADMIN_PASSWORD',PASSWORD)
    init_db(db,seed_demo=False)
    email='clinic-owner-'+uuid4().hex[:8]+'@example.com'
    result=client.post('/api/v1/auth/signup',json={'applicant_type':'company','name':'Native Clinic Owner',
        'company_name':'Independent Clinic','email':email,'phone':'+919876543210','requested_modules':['hrms','srm'],'consent':True})
    assert result.status_code==202,result.text
    pending=client.post('/api/v1/auth/login',json={'email':email,'password':PASSWORD})
    assert pending.status_code==401 and 'access_token' not in pending.json(),pending.text
    row=platform_store.query(PlatformSignupRequest).filter_by(email=email).one()
    approved=client.post(f'/api/v1/platform/signups/{row.id}/review',headers=platform_headers,json={'decision':'approve',
        'reason':'Actual platform company approval','version':row.version,'modules':['hrms','srm'],
        'checklist':{'identity':True,'duplicates':True,'modules':True}})
    assert approved.status_code==200,approved.text
    activate(client,approved.json());headers=login(client,email)
    platform_store.refresh(row);headers['X-Suite-Organization']=str(row.company_id)
    branch=client.post('/api/v1/branches',headers=headers,json={'name':'Addressed new clinic','code':'NEWCLINIC','reason':'Create real company branch'})
    assert branch.status_code==201,branch.text
    native=db.connection().execute(select(Branch.company_id,Branch.is_active).where(Branch.id==branch.json()['id'])).one()
    assert tuple(native)==(row.company_id,True)
    headers['X-Suite-Branch']=str(branch.json()['id'])
    draft=client.post(ROOT+'/activations',headers=headers,json={'pack_key':'hospital','expected_revision':0,'reason':'Draft only; no publication bypass'})
    assert draft.status_code==201,draft.text
    return headers,row.company_id,branch.json()['id'],draft.json(),email

def draft_context(client,case,bid=None,headers=None):
    h,_,branch,a,_=case
    return client.post(ROOT+'/contexts',headers=headers or h,json={'activation_id':a['id'],
        'activation_revision':a['revision'],'branch_id':bid or branch,'expected_revision':0,'reason':'Address exact company-owned branch'})

def test_actual_native_signup_new_branch_can_create_draft_context(client,db,owner):
    result=draft_context(client,owner)
    assert result.status_code==201,result.text
    assert (result.json()['company_id'],result.json()['branch_id'])==(owner[1],owner[2])
    from app.business_packs.runtime import RUNTIME_SUPPORT
    assert not RUNTIME_SUPPORT  # Pure control fix is independent of pack publication.

@pytest.mark.parametrize('fault',['foreignbranch','foreigncompany','inactive','deleted','ordinary'])
def test_addressed_branch_control_does_not_broaden_native_authority(client,db,owner,fault):
    headers,company,bid,a,email=owner
    if fault=='foreigncompany':
        other=Company(name='Other company');db.add(other);db.commit()
        result=draft_context(client,owner,headers={**headers,'X-Suite-Organization':str(other.id)})
        assert result.status_code==403,result.text
    elif fault=='foreignbranch':
        other=Company(name='Other company');db.add(other);db.flush()
        branch=Branch(name='Foreign clinic',company_id=other.id,is_active=True);db.add(branch);db.commit()
        result=draft_context(client,owner,bid=branch.id)
        assert result.status_code==404,result.text
    elif fault=='inactive':
        db.connection().execute(update(Branch.__table__).where(Branch.id==bid).values(is_active=False));db.commit()
        result=draft_context(client,owner);assert result.status_code==404,result.text
    elif fault=='deleted':
        response=client.post(f'/api/v1/branches/{bid}/trash',headers=headers,json={'expected_version':0,'reason':'Retire empty native test branch'})
        assert response.status_code==200,response.text
        result=draft_context(client,owner);assert result.status_code==404,result.text
    else:
        from app.access.models import AccessMembership
        from app.models.user import User
        actor=db.query(User).filter_by(email=email).one()
        member=db.query(AccessMembership).filter_by(company_id=company,user_id=actor.id).one()
        member.is_admin=False;db.commit()
        result=draft_context(client,owner);assert result.status_code==403,result.text
    from app.business_packs.models import PackContext
    assert db.query(PackContext).count()==0
