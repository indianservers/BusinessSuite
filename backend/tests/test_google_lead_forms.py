from urllib.parse import urlsplit
import pytest
from tests.test_power_apps import actors
from tests.test_marketplace_sync_workflows import native_actor
from app.apps.power_apps.integrations.google_leads import dispatch_due
from app.apps.crm.models import CRMLead
from app.shared.models import ServicePolicy
from app.shared.import_models import ImportBatch

ROOT='/api/v1/power-apps/integrations/sync/lead-forms'


@pytest.fixture
def form(client,db,native_actor,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'BACKEND_PUBLIC_URL','https://crm.example.com')
    headers,user=native_actor
    response=client.post(ROOT,headers=headers,json={'name':'Google enquiries','form_id':'1234','apply_new_records':True})
    assert response.status_code==201,response.text
    data=response.json()
    return headers,user,data,urlsplit(data['callback_url']).path


def lead(key,**updates):
    return {'lead_id':'google-lead-123','form_id':1234,'campaign_id':9876543210123,'gcl_id':'click-abc','google_key':key,
        'user_column_data':[{'column_id':'FULL_NAME','string_value':'Asha Google'},
            {'column_id':'PHONE_NUMBER','string_value':'+919876543210'},
            {'column_id':'CUSTOM_QUESTION','string_value':'Needs CRM'}],**updates}


def test_key_form_binding_test_leads_and_duplicate_delivery(client,db,form):
    headers,_,data,path=form
    assert client.post(path,json=lead('bad-key')).status_code==401
    assert client.post(path,content=b'x'*262145,headers={'content-type':'application/octet-stream'}).status_code==413
    assert client.post(path,json=lead(data['google_key'],form_id=999)).status_code==422
    response=client.post(path,json=lead(data['google_key'],is_test=True))
    assert response.status_code==200 and response.json()['imported'] is False
    assert db.query(ServicePolicy).filter_by(kind='google_lead_submission').count()==0
    documented_test=lead(data['google_key'],is_test=True)
    documented_test['Google_key']=documented_test.pop('google_key')
    assert client.post(path,json=documented_test).json()['test'] is True
    assert client.post(path,json=lead(data['google_key'])).json()['queued'] is True
    assert client.post(path,json=lead(data['google_key'])).json()['duplicate'] is True
    queued=db.query(ServicePolicy).filter_by(kind='google_lead_submission').one()
    assert 'Asha Google' not in str(queued.values_json) and data['google_key'] not in str(queued.values_json)
    assert dispatch_due(db)=={'completed':1,'failed':0}
    row=db.query(CRMLead).filter_by(full_name='Asha Google').one()
    assert row.phone_country_code=='+91' and row.phone=='9876543210'
    assert '9876543210123' in row.notes and 'click-abc' in row.notes and 'Needs CRM' in row.notes
    db.refresh(queued)
    assert queued.values_json['encrypted_payload'] is None and queued.values_json['state']=='imported'
    listed=client.get(ROOT,headers=headers)
    assert listed.status_code==200,listed.text
    assert data['google_key'] not in listed.text and 'key_hash' not in listed.text
    assert listed.json()['items'][0]['recent'][0]['batch_id']


def test_bad_lead_is_staged_for_review_and_paused_source_rejects_delivery(client,db,form):
    headers,_,data,path=form
    response=client.post(path,json=lead(data['google_key'],user_column_data=[{'column_id':'FULL_NAME','string_value':'No contact details'}]))
    assert response.status_code==200,response.text
    assert dispatch_due(db)['completed']==1
    submission=db.query(ServicePolicy).filter_by(kind='google_lead_submission').one()
    assert submission.values_json['state']=='review'
    batch=db.get(ImportBatch,submission.values_json['batch_id'])
    assert batch.preview_json['can_import'] is False
    assert db.query(CRMLead).filter_by(full_name='No contact details').count()==0
    current=client.get(ROOT,headers=headers).json()['items'][0]
    paused=client.put(ROOT+'/'+str(data['id']),headers=headers,json={'expected_version':current['version'],'enabled':False})
    assert paused.status_code==200,paused.text
    assert client.post(path,json=lead(data['google_key'],lead_id='next')).status_code==404


def test_revoked_owner_stops_processing_and_explicit_retry_recovers(client,db,form):
    headers,user,data,path=form
    assert client.post(path,json=lead(data['google_key'])).status_code==200
    user.is_active=False;db.commit()
    assert dispatch_due(db)=={'completed':0,'failed':1}
    queued=db.query(ServicePolicy).filter_by(kind='google_lead_submission').one()
    assert queued.values_json['state']=='attention' and queued.values_json['encrypted_payload']
    user.is_active=True;db.commit()
    response=client.post(ROOT+'/'+str(data['id'])+'/retry',headers=headers)
    assert response.status_code==200 and response.json()['queued']==1
    assert dispatch_due(db)['completed']==1
    assert db.query(CRMLead).filter_by(full_name='Asha Google').count()==1


def test_configuration_and_management_require_permissions(client,form,actors):
    _,_,data,_=form
    assert client.get(ROOT).status_code in {401,403}
    assert client.post(ROOT,headers=actors[2],json={'name':'Denied','form_id':'123'}).status_code==403
    response=client.put(ROOT+'/'+str(data['id']),headers=actors[1],json={'expected_version':1,'enabled':False})
    assert response.status_code in {403,404}


def test_paused_source_backlog_does_not_starve_active_sources(client,db,form):
    _,user,data,path=form
    paused=ServicePolicy(scope_key='paused-google-source',organization_id=1,module_key='crm',kind='google_lead_form',updated_by=user.id,values_json={'enabled':False})
    db.add(paused);db.flush()
    db.add_all([ServicePolicy(scope_key='paused-google-submission:'+str(i),organization_id=1,module_key='crm',kind='google_lead_submission',updated_by=user.id,
        values_json={'form_config_id':paused.id,'state':'pending','next_at':'2020-01-01T00:00:00+00:00','encrypted_payload':'not-read'}) for i in range(101)])
    db.commit()
    assert client.post(path,json=lead(data['google_key'])).status_code==200
    assert dispatch_due(db)=={'completed':1,'failed':0}
    assert db.query(CRMLead).filter_by(full_name='Asha Google').count()==1
