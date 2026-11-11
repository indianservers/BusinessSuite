import copy
from datetime import datetime,timezone
import pytest
from tests.test_power_apps import actors
from tests.test_marketplace_sync_workflows import native_actor
from app.apps.crm import lead_management as leads
from app.apps.crm.models import CRMLead
from app.apps.crm.lead_models import CRMLeadOperatingState
from app.models.user import User

ROOT='/api/v1/crm/lead-management'


def create(client,headers,index):
    response=client.post(ROOT+'/leads',headers=headers,json={'values':{'full_name':'Capacity lead '+str(index),'email':f'capacity-{index}@example.com','source':'facebook_lead_ads'}})
    assert response.status_code==201,response.text
    return response.json()['id']


def configuration(db,native_actor):
    headers,user=native_actor
    seller=db.query(User).filter_by(email='power-3@example.com').one();seller.is_superuser=True;db.commit()
    settings=copy.deepcopy(leads.DEFAULTS)
    policy={'ownerId':seller.id,'enabled':True,'timezone':'Asia/Kolkata','days':[2],'startMinute':540,'endMinute':1080,'maxActiveLeads':1}
    settings['assignment']={'mode':'round_robin','ownerIds':[seller.id],'rules':[],'availability':[policy]}
    return headers,user,seller,settings


def test_schedule_capacity_and_archive_release_are_applied_to_native_routing(client,db,native_actor,monkeypatch):
    headers,_,seller,settings=configuration(db,native_actor)
    clock=[datetime(2026,11,11,3,30,tzinfo=timezone.utc)] # Wednesday 09:00 India
    monkeypatch.setattr(leads,'now',lambda:clock[0])
    saved=client.put(ROOT+'/settings',headers=headers,json=settings)
    assert saved.status_code==200,saved.text
    first=create(client,headers,1)
    assert db.get(CRMLead,first).owner_user_id==seller.id
    second=create(client,headers,2)
    assert db.get(CRMLead,second).owner_user_id is None
    state=db.query(CRMLeadOperatingState).filter_by(lead_id=first).one()
    state.data_json={**state.data_json,'archived':True};db.commit()
    third=create(client,headers,3)
    assert db.get(CRMLead,third).owner_user_id==seller.id
    clock[0]=datetime(2026,11,11,12,30,tzinfo=timezone.utc) # Shift end is exclusive
    fourth=create(client,headers,4)
    assert db.get(CRMLead,fourth).owner_user_id is None


def test_unavailable_rule_owner_falls_back_to_eligible_distribution(client,db,native_actor):
    headers,user,seller,settings=configuration(db,native_actor)
    settings['assignment']['ownerIds']=[user.id]
    settings['assignment']['rules']=[{'field':'source','equals':'facebook_lead_ads','ownerId':seller.id}]
    settings['assignment']['availability'][0]['enabled']=False
    saved=client.put(ROOT+'/settings',headers=headers,json=settings)
    assert saved.status_code==200,saved.text
    ident=create(client,headers,'fallback')
    assert db.get(CRMLead,ident).owner_user_id==user.id


@pytest.mark.parametrize('patch',[{'timezone':'Not/AZone'},{'days':[9]},{'days':[2,2]},{'startMinute':1080,'endMinute':540},{'maxActiveLeads':0}])
def test_invalid_seller_policies_are_rejected(client,db,native_actor,patch):
    headers,_,_,settings=configuration(db,native_actor)
    settings['assignment']['availability'][0].update(patch)
    assert client.put(ROOT+'/settings',headers=headers,json=settings).status_code==422
