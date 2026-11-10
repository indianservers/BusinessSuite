from datetime import timedelta,datetime,timezone
from contextlib import nullcontext
import pytest
from app.core.config import settings
from app.platform_owner.models import PlatformRecord,PlatformAdmin,PlatformSignupRequest,PlatformEvent
from app.models.user import User
from app.models.email_outbox import EmailOutbox
from app.apps.saas.models import TenantSubscription,TenantSubscriptionPlan
from app.platform_owner import signup_journey as journey
from tests.test_public_signup import platform_store,platform_headers,submit,approve,PASSWORD,ROOT
from tests.test_intern_signup_settings import firebase_identity

def payload(row,**extra):
 return {'decision':'approve','reason':'Internal risk assessment stays private','version':row.version,'modules':['crm'],'checklist':{'identity':True,'duplicates':True,'modules':True},**extra}

def decide(client,headers,row,**extra):
 return client.post(f'/api/v1/platform/signups/{row.id}/review',headers=headers,json=payload(row,**extra))

def tracking(store,row):
 from app.access.applicant_login import status_link
 url=status_link(store,row);store.commit();return '/api/v1'+url[url.index('/platform/public/'):]

def test_receipts_and_reviewer_delivery_are_durable_and_idempotent(client,db,platform_store):
 row=submit(client,db,'receipt@example.com')
 messages=platform_store.query(PlatformRecord).filter_by(kind='signup_mail').all()
 assert any(m.data['event']==f'receipt:{row.id}' for m in messages)
 assert any(m.data['event'].startswith('reviewer:') for m in messages)
 assert not db.query(User).filter_by(email=row.email).first()
 journey.deliver(platform_store,db);count=db.query(EmailOutbox).count();assert count>=2
 journey.deliver(platform_store,db);assert db.query(EmailOutbox).count()==count
 out=db.query(EmailOutbox).filter(EmailOutbox.recipient==row.email).one();out.status='accepted';out.provider_message_id='provider-accepted';db.commit()
 journey.deliver(platform_store,db)
 mail=platform_store.query(PlatformRecord).filter_by(kind='signup_mail',signup_id=row.id).filter(PlatformRecord.title=='Your BestERP trial request was received').one()
 assert mail.state=='accepted' and mail.data['provider_message_id']=='provider-accepted'
 assert all('risk assessment' not in m.data['body'] for m in messages)

def test_verified_prefill_rejects_changed_email(client,db,firebase_identity,monkeypatch):
 monkeypatch.setattr(settings,'FIREBASE_PROJECT_ID','test-project')
 verified=client.post(ROOT+'/signup/identity',json={'token':firebase_identity(email='verified@example.com')})
 assert verified.status_code==200,verified.text
 proof=verified.json()['identity_proof']
 data={'applicant_type':'individual','name':'Verified Applicant','email':'changed@example.com','phone':'+919876543210','requested_modules':['crm'],'consent':True,'identity_proof':proof}
 assert client.post(ROOT+'/signup',json=data).status_code==422
 data['email']='verified@example.com'
 assert client.post(ROOT+'/signup',json=data).status_code==202
 row=db._platform_db.query(PlatformSignupRequest).filter_by(email=data['email']).one()
 assert row.workflow['email_verified'] is True
 assert 'identity_proof' not in row.workflow

def test_atomic_checklist_stale_version_preview_and_private_reason(client,db,platform_headers,platform_store):
 row=submit(client,db,'atomic@example.com');platform_store.query(PlatformRecord).filter_by(kind='settings').one().data={'require_checklist':True};platform_store.commit()
 missing=payload(row);missing.pop('version')
 assert client.post(f'/api/v1/platform/signups/{row.id}/review',headers=platform_headers,json=missing).status_code==422
 response=decide(client,platform_headers,row,version=row.version+1)
 assert response.status_code==409
 assert not db.query(User).filter_by(email=row.email).first()
 response=decide(client,platform_headers,row,applicant_message='Your requested CRM trial is ready.')
 assert response.status_code==200,response.text
 platform_store.refresh(row);assert row.status=='approved' and row.workflow['checklist']['identity']
 mail=db.query(EmailOutbox).filter_by(event_key=f'signup-approved:{row.id}').one()
 assert mail.status=='queued' and 'risk assessment' not in mail.body
 assert 'Internal' not in str(client.get(tracking(platform_store,row)).json())

def test_targeted_corrections_and_rejection_message(client,db,platform_headers,platform_store):
 row=submit(client,db,'correction@example.com')
 response=client.post(f'/api/v1/platform/signups/{row.id}/request-info',headers=platform_headers,json={'action':'request_info','reason':'Internal mismatch','values':{'fields':['name'],'instructions':{'name':'Use your full contact name'},'applicant_message':'Please confirm your contact name.'}})
 assert response.status_code==200,response.text
 url=response.json()['url'];path='/api/v1'+url[url.index('/platform/public/'):]
 data=client.get(path).json();assert list(data['fields'])==['name'] and 'Internal mismatch' not in str(data)
 assert data['instructions']['name']=='Use your full contact name'
 assert client.post(path,json={'action':'correct','values':{'email':'attacker@example.com'}}).status_code==422
 assert client.post(path,json={'action':'correct','values':{'name':'Corrected Owner'}}).status_code==200
 assert client.get(path).status_code==404
 platform_store.refresh(row)
 response=decide(client,platform_headers,row,decision='reject',applicant_message='This request needs an existing customer access review.')
 assert response.status_code==200,response.text
 page=client.get(tracking(platform_store,row)).json()
 assert 'existing customer' in page['message'] and 'risk assessment' not in str(page)
 assert platform_store.query(PlatformRecord).filter_by(kind='signup_mail',title='Your BestERP trial application decision').one().state=='pending'

def test_first_login_trial_starts_once_after_approval(client,db,platform_headers,platform_store):
 row=submit(client,db,'trialstart@example.com')
 response=decide(client,platform_headers,row,trial_start='first_login',trial_days=21,activation_days=5)
 assert response.status_code==200,response.text
 subscription=db.query(TenantSubscription).filter_by(company_id=row.company_id).one()
 assert subscription.config_json['pending_activation']
 user=db.get(User,row.user_id)
 journey.start_trial(db,user);db.commit();end=subscription.config_json['renewal_at']
 assert not subscription.config_json['pending_activation']
 assert datetime.fromisoformat(end)>datetime.now(timezone.utc)+timedelta(days=20)
 journey.start_trial(db,user);db.commit();assert subscription.config_json['renewal_at']==end

def test_expired_activation_is_not_silently_extended(client,db,platform_headers):
 row=submit(client,db,'deadline@example.com');assert decide(client,platform_headers,row,trial_start='first_login').status_code==200
 sub=db.query(TenantSubscription).filter_by(company_id=row.company_id).one();sub.config_json={**sub.config_json,'activation_deadline':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()};db.commit()
 from fastapi import HTTPException
 with pytest.raises(HTTPException,match='deadline'):journey.start_trial(db,db.get(User,row.user_id))

def test_routing_and_overdue_reminders_are_configurable_deduplicated(client,db,platform_headers,platform_store):
 reviewer=PlatformAdmin(email='reviewer@example.com',name='Reviewer',role='reviewer',hashed_password='unused');platform_store.add(reviewer);platform_store.commit()
 cfg={'auto_assign':True,'routing':{'crm':reviewer.id},'reviewer_email':True,'trial_start':'first_login','activation_days':7,'reminder_hours':24}
 r=client.put('/api/v1/platform/signup-journey/settings',headers=platform_headers,json=cfg);assert r.status_code==200,r.text
 row=submit(client,db,'routed@example.com');assert row.assigned_to==reviewer.id
 row.created_at=datetime.now(timezone.utc)-timedelta(days=7);platform_store.commit()
 journey.due_work(platform_store);count=platform_store.query(PlatformRecord).filter_by(kind='signup_mail').count();journey.due_work(platform_store)
 assert platform_store.query(PlatformRecord).filter_by(kind='signup_mail').count()==count
 assert any(m.data['event'].startswith('overdue:') for m in platform_store.query(PlatformRecord).filter_by(kind='signup_mail'))

def test_telemetry_is_opt_in_payload_deduplicated_without_form_data(client,platform_headers,platform_store):
 data={'session':'abcdef1234567890abcdef12','event':'started','source':'website'}
 assert client.post(ROOT+'/signup/telemetry',json=data).status_code==202
 assert client.post(ROOT+'/signup/telemetry',json=data).status_code==202
 assert platform_store.query(PlatformRecord).filter_by(kind='signup_metric').count()==1
 stored=platform_store.query(PlatformRecord).filter_by(kind='signup_metric').one();assert stored.data=={'source':'website'}
 response=client.get('/api/v1/platform/signup-journey/analytics/funnel',headers=platform_headers);assert response.status_code==200,response.text
 assert response.json()['form_events']['started']==1

def test_password_link_recovery_status_only_and_one_time_setup(client,db,platform_headers,platform_store):
 row=submit(client,db,'refresh-password@example.com');assert decide(client,platform_headers,row).status_code==200
 path=tracking(platform_store,row)
 assert client.post(path,json={'action':'password_link'}).status_code==200
 record=platform_store.query(PlatformRecord).filter_by(kind='signup_mail',title='Set your BestERP password').one()
 from urllib.parse import urlparse,parse_qs
 url=next(s for s in record.data['body'].splitlines() if '/invite-access?' in s);token=parse_qs(urlparse(url).query)['token'][0]
 preview=client.get(ROOT+'/signup/invitation',params={'token':token});assert preview.status_code==200 and preview.json()['email']==row.email
 assert client.post(ROOT+'/reset-password',json={'token':token,'new_password':PASSWORD}).status_code==200
 assert client.get(ROOT+'/signup/invitation',params={'token':token}).status_code==404
 assert client.get('/api/v1/auth/me').status_code in {401,403}

def test_onboarding_is_account_scoped_and_first_value_is_explicit(client,db,platform_headers,platform_store):
 row=submit(client,db,'welcome@example.com');response=decide(client,platform_headers,row);assert response.status_code==200,response.text
 from tests.test_public_signup import activate,login
 activate(client,response.json());headers=login(client,row.email)
 response=client.get('/api/v1/access/onboarding',headers=headers);assert response.status_code==200 and response.json()['available']
 assert [m['key'] for m in response.json()['modules']]==['crm']
 assert client.post('/api/v1/access/onboarding',headers=headers,json={'step':'first_action','complete':True}).status_code==200
 journey.synchronize_logins(platform_store,db)
 assert platform_store.query(PlatformEvent).filter_by(action='signup.first_value',entity_id=row.id).count()==1
 journey.synchronize_logins(platform_store,db)
 assert platform_store.query(PlatformEvent).filter_by(action='signup.first_value',entity_id=row.id).count()==1

def test_matched_duplicate_blocks_duplicate_company_provisioning(client,db,platform_headers,platform_store):
 a=submit(client,db,'duplicate-a@example.com');b=submit(client,db,'duplicate-b@example.com')
 r=client.post(f'/api/v1/platform/signup-journey/{b.id}/duplicate',headers=platform_headers,json={'version':b.version,'other_id':a.id,'decision':'match','reason':'Same contact and business'})
 assert r.status_code==200,r.text
 platform_store.refresh(b);assert decide(client,platform_headers,b).status_code==409
 assert not db.query(User).filter_by(email=b.email).first()


def test_dedicated_discovery_is_bound_to_verified_email_and_selection(db,platform_store,monkeypatch):
 from app.access import workspace_login
 from app.platform_owner.models import PlatformDatabaseServer,PlatformTenantDatabase
 from app.api.v1 import auth
 from types import SimpleNamespace
 from fastapi import HTTPException
 server=PlatformDatabaseServer(code='test',name='Test',host='localhost',port=5432,provisioning_env='TEST',template_database='empty',active=True,max_databases=5)
 platform_store.add(server);platform_store.flush()
 for i in [1,2]:
  signup=PlatformSignupRequest(email='workspace@example.com' if i==1 else 'other@example.com',name='Workspace Owner',applicant_type='individual',phone='+919876543210',phone_country_code='+91',requested_modules=['crm'],status='approved')
  platform_store.add(signup);platform_store.flush()
  platform_store.add(PlatformTenantDatabase(signup_id=signup.id,tenant_uuid=f'uuid-{i}',workspace_code=f'company-{i}',company_id=i,server_id=server.id,database_name=f'tenant_{i}',runtime_role=f'role_{i}',encrypted_password='not-used',status='ready',routing_version=1,schema_version='test'))
 platform_store.commit()
 monkeypatch.setattr(workspace_login,'platform_factory',lambda:lambda:nullcontext(platform_store))
 calls=[]
 monkeypatch.setattr(workspace_login,'lookup_route',lambda w:(calls.append(w) or SimpleNamespace(workspace_code=w,tenant_uuid='qa-tenant')))
 monkeypatch.setattr(workspace_login,'tenant_session',lambda r:nullcontext(db))
 monkeypatch.setattr(auth,'firebase_login',lambda *args:{'access_token':'scoped-test-result'})
 result=workspace_login.discover({'email':'workspace@example.com'},SimpleNamespace(workspace=None,model_copy=lambda **kw:SimpleNamespace(workspace=None)),None)
 assert result['workspace']=='company-1' and calls==['company-1']
 with pytest.raises(HTTPException):workspace_login.discover({'email':'workspace@example.com'},SimpleNamespace(workspace='company-2'),None)
 assert calls==['company-1']


def test_access_recovery_preserves_intentional_restrictions(client,db,platform_headers,platform_store):
 row=submit(client,db,'restricted@example.com');assert decide(client,platform_headers,row).status_code==200
 user=db.get(User,row.user_id);user.is_active=False;db.commit()
 response=client.post(f'/api/v1/platform/signup-journey/{row.id}/recover',headers=platform_headers,json={'version':row.version,'reason':'Check incomplete steps'})
 assert response.status_code==200,response.text
 assert response.json()['activation_completed'] and response.json()['account_restricted'] and not response.json()['signin_ready']
 db.refresh(user);assert not user.is_active
