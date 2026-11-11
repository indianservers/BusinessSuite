import copy
import hashlib
import hmac
import json
from types import SimpleNamespace
from urllib.parse import urlsplit
import pytest
from tests.test_power_apps import actors
from tests.test_marketplace_sync_workflows import native_actor,create_connection,fixture_page
from tests.test_marketplace_provider_authorization import CASES
from app.apps.power_apps.integrations import adapters
from app.apps.power_apps.integrations.marketplace_sync import dispatch_due
from app.shared.models import ServicePolicy
from app.shared.import_models import ImportBatch
from app.apps.crm.models import CRMLead,CRMActivity
from app.apps.crm.lead_models import CRMLeadOperatingState,CRMLeadManagementConfig
from app.apps.crm.lead_management import DEFAULTS

ROOT='/api/v1/power-apps/integrations/sync'
APP_SECRET='synthetic-meta-app-secret-for-tests'


@pytest.fixture
def configured(client,db,native_actor,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'BACKEND_PUBLIC_URL','https://crm.example.com')
    headers,user=native_actor
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='facebook_lead_ads'))
    made=client.post(ROOT+'/jobs',headers=headers,json={'connection_id':ident,'name':'Live Facebook form',
        'source':{'resource_id':'456'},'automatic':True,'apply_new_records':True})
    assert made.status_code==201,made.text
    job=made.json()
    setup=client.post(f"{ROOT}/jobs/{job['id']}/facebook-hook",headers=headers,
        json={'expected_version':job['version'],'page_id':'123','app_secret':APP_SECRET})
    assert setup.status_code==201,setup.text
    values=setup.json()
    assert APP_SECRET not in setup.text
    return headers,user,job['id'],values,urlsplit(values['callback_url']).path


def notification(page='123',form='456',lead='9876543210123456'):
    return {'object':'page','entry':[{'id':page,'changes':[{'field':'leadgen','value':{
        'page_id':page,'form_id':form,'leadgen_id':lead}}]}]}


def send(client,path,payload,secret=APP_SECRET):
    body=json.dumps(payload).encode()
    signature='sha256='+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return client.post(path,content=body,headers={'content-type':'application/json','x-hub-signature-256':signature})


def test_challenge_signature_binding_deduplication_and_worker(client,db,configured,monkeypatch):
    headers,user,ident,setup,path=configured
    assert client.get(path,params={'hub.mode':'subscribe','hub.verify_token':'wrong','hub.challenge':'42'}).status_code==401
    response=client.get(path,params={'hub.mode':'subscribe','hub.verify_token':setup['verify_token'],'hub.challenge':'42'})
    assert response.status_code==200 and response.text=='42'
    assert send(client,path,notification(),secret='wrong').status_code==401
    raw=json.dumps(notification()).encode()
    signature='sha256='+hmac.new(APP_SECRET.encode(),raw,hashlib.sha256).hexdigest()
    assert client.post(path,content=raw+b' ',headers={'content-type':'application/json','x-hub-signature-256':signature}).status_code==401
    assert client.post(path,content=b'x'*262145,headers={'content-type':'application/octet-stream'}).status_code==413
    assert send(client,path,notification(page='999')).json()['new_notifications']==0
    assert send(client,path,notification(form='999')).json()['new_notifications']==0
    job=db.get(ServicePolicy,ident)
    job.values_json={**job.values_json,'next_at':'2099-01-01T00:00:00+00:00'};db.commit()
    first=send(client,path,notification())
    assert first.status_code==200 and first.json()['new_notifications']==1
    assert send(client,path,notification()).json()['new_notifications']==0
    assert db.query(ServicePolicy).filter_by(kind='lead_wake').count()==1
    class Transport:
        def request(self,method,url,**kwargs):
            return SimpleNamespace(status=200,headers={},body=json.dumps(fixture_page('facebook_lead_ads')).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    assert dispatch_due(db)=={'completed_pages':1,'failed_jobs':0}
    assert db.query(CRMLead).filter_by(email='facebook_lead_ads@example.com').count()==1
    listing=client.get(ROOT+'/jobs',headers=headers)
    assert APP_SECRET not in listing.text and setup['verify_token'] not in listing.text


def test_rotation_rejects_old_endpoint_and_disable_rejects_delivery(client,db,configured):
    headers,_,ident,setup,path=configured
    job=client.get(ROOT+'/jobs',headers=headers).json()['items'][0]
    rotated=client.post(f'{ROOT}/jobs/{ident}/facebook-hook',headers=headers,json={
        'expected_version':job['version'],'page_id':'123','app_secret':APP_SECRET})
    assert rotated.status_code==201,rotated.text
    assert send(client,path,notification()).status_code==404
    newpath=urlsplit(rotated.json()['callback_url']).path
    stale=client.delete(f'{ROOT}/jobs/{ident}/facebook-hook',headers=headers,params={'expected_version':job['version']})
    assert stale.status_code==409
    disabled=client.delete(f'{ROOT}/jobs/{ident}/facebook-hook',headers=headers,params={'expected_version':rotated.json()['version']})
    assert disabled.status_code==200,disabled.text
    assert send(client,newpath,notification()).status_code==404


def test_notifications_during_read_schedule_another_pass(client,db,configured,monkeypatch):
    _,_,ident,_,_=configured
    class Transport:
        def request(self,method,url,**kwargs):
            job=db.get(ServicePolicy,ident)
            job.values_json={**job.values_json,'wake_sequence':1};job.version+=1;db.commit()
            return SimpleNamespace(status=200,headers={},body=b'{"data":[]}')
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    assert dispatch_due(db)['completed_pages']==1
    from app.apps.power_apps.runtime import now
    from datetime import datetime
    db.expire_all();job=db.get(ServicePolicy,ident)
    assert datetime.fromisoformat(job.values_json['next_at'])<=now()


def test_import_runs_native_creation_workflow_once_and_revoke_removes_side_effects(client,db,configured,monkeypatch):
    headers,user,ident,_,_=configured
    settings=copy.deepcopy(DEFAULTS)
    from app.models.user import User
    assignee=db.query(User).filter_by(email='power-3@example.com').one()
    assignee.is_superuser=True
    assignee.is_active=True
    settings['assignment']['rules']=[{'field':'source','equals':'facebook_lead_ads','ownerId':assignee.id}]
    settings['workflows']=[{'name':'Call new enquiries','enabled':True,'trigger':'created','stage':'','action':'task','title':'Call imported lead','delayHours':1}]
    db.add(CRMLeadManagementConfig(organization_id=1,settings_json=settings,updated_by=user.id));db.commit()
    class Transport:
        def request(self,method,url,**kwargs):
            return SimpleNamespace(status=200,headers={},body=json.dumps(fixture_page('facebook_lead_ads')).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    first=client.post(f'{ROOT}/jobs/{ident}/run',headers=headers,json={})
    assert first.status_code==200,first.text
    lead=db.query(CRMLead).filter_by(email='facebook_lead_ads@example.com').one()
    state=db.query(CRMLeadOperatingState).filter_by(lead_id=lead.id).one()
    assert state.data_json['enquiryInbox'] is True
    assert lead.owner_user_id==assignee.id
    assert db.query(CRMActivity).filter_by(lead_id=lead.id,subject='Call imported lead').one().owner_user_id==assignee.id
    assert db.query(CRMActivity).filter_by(lead_id=lead.id,subject='Call imported lead').count()==1
    assert client.post(f'{ROOT}/jobs/{ident}/run',headers=headers,json={}).status_code==200
    assert db.query(CRMActivity).filter_by(lead_id=lead.id,subject='Call imported lead').count()==1
    batch=db.get(ImportBatch,first.json()['batches'][0])
    from app.shared.import_service import revoke
    revoke(db,batch);db.commit()
    assert db.query(CRMLead).filter_by(email='facebook_lead_ads@example.com').count()==0
    assert db.query(CRMActivity).filter_by(subject='Call imported lead').count()==0


def test_imported_lead_enters_scheduled_response_sla(client,db,configured,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from app.apps.crm.lead_management import scheduled_lead_alerts
    from app.models.notification import Notification
    headers,_,ident,_,_=configured
    class Transport:
        def request(self,method,url,**kwargs):
            return SimpleNamespace(status=200,headers={},body=json.dumps(fixture_page('facebook_lead_ads')).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    assert client.post(f'{ROOT}/jobs/{ident}/run',headers=headers,json={}).status_code==200
    lead=db.query(CRMLead).filter_by(email='facebook_lead_ads@example.com').one()
    lead.created_at=datetime.now(timezone.utc)-timedelta(days=2);db.commit()
    assert scheduled_lead_alerts(db)['leadsEscalated']==1
    assert scheduled_lead_alerts(db)['leadsEscalated']==0
    assert db.query(Notification).filter_by(event_type='lead_sla').count()==1
