"""Real CRM growth workflows with isolated delivery providers."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from tests.test_crm_associations_merge import superuser_headers, post, offering, line, contact
from app.apps.crm.models import CRMActivity, CRMContact

ROOT='/api/v1/crm/growth'


@pytest.fixture(autouse=True)
def growth_company_setup(db,superuser_headers):
    from app.models.company import Company
    company=db.get(Company,1)
    company.email=company.email or 'crm-growth-test@example.com'
    company.country=company.country or 'India'
    db.commit()


@pytest.mark.parametrize('format',['csv','clipboard','xlsx','pdf'])
def test_relationship_exports_are_real_files_and_authorized(client,superuser_headers,format):
    h=superuser_headers;c=contact(client,h,full_name='=Export fixture',email='export@example.com')
    payload={'format':format,'recipients':[{'entity':'contacts','id':c['id']}],'columns':['name','email','owner_id'],'summary':True}
    response=client.post(ROOT+'/export',headers=h,json=payload)
    assert response.status_code==200,response.text
    if format=='xlsx':
        from io import BytesIO
        from openpyxl import load_workbook
        sheet=load_workbook(BytesIO(response.content)).active
        assert sheet.cell(2,1).value=="'=Export fixture" and sheet.cell(2,1).data_type=='s'
    elif format=='pdf':assert response.content.startswith(b'%PDF')
    else:assert "'=Export fixture" in response.text and 'export@example.com' in response.text
    invalid=client.post(ROOT+'/export',headers=h,json={**payload,'recipients':[{'entity':'contacts','id':999999}]})
    assert invalid.status_code==404


def test_bulk_assignment_partial_results_and_new_payload(client,superuser_headers):
    h=superuser_headers
    a=contact(client,h,full_name='Bulk A',email='bulk-a@example.com')
    b=contact(client,h,full_name='Bulk B',email='bulk-b@example.com')
    due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    scheduled=post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':a['id'],'due_at':due})
    owner=get(client,h,f"/pending/contacts/{a['id']}")['items'][0]['owner_id']
    payload={'recipients':[{'entity':'contacts','id':a['id']},{'entity':'contacts','id':b['id']}],'action':'assign','owner_id':owner,'request_id':str(uuid4())}
    first=post(client,h,'crm/growth/follow-ups/bulk',payload)
    assert first['saved']==1 and not first['items'][1]['saved']
    retry=post(client,h,'crm/growth/follow-ups/bulk',payload)
    assert retry['saved']==1 and retry['items'][0]['replayed']
    assert get(client,h,f"/pending/contacts/{a['id']}")['items'][0]['id']==scheduled['activity_id']
    conflict=post(client,h,'crm/growth/follow-ups/bulk',{**payload,'action':'schedule','due_at':due})
    assert not conflict['items'][0]['saved'] and 'identifier' in conflict['items'][0]['message']


def test_local_reminder_dispatch_and_offset_normalization(client,db,superuser_headers):
    from app.apps.crm.growth import dispatch_relationship_reminders
    from app.models.notification import Notification
    h=superuser_headers;c=contact(client,h)
    at=datetime.now(timezone.utc)
    reminder=at+timedelta(hours=1)
    saved=post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':c['id'],'title':'x'*220,'due_at':(at+timedelta(hours=2)).isoformat(),'reminder_at':reminder.astimezone(timezone(timedelta(hours=5,minutes=30))).isoformat()})
    item=get(client,h,f"/pending/contacts/{c['id']}")['items'][0]
    assert datetime.fromisoformat(item['metadata']['reminder_at'])==reminder
    assert item['metadata']['reminder_at'].endswith('+00:00')
    assert dispatch_relationship_reminders(db)==0
    row=db.get(CRMActivity,saved['activity_id']);row.metadata_json={**row.metadata_json,'reminder_at':(at-timedelta(minutes=1)).isoformat()};db.commit()
    assert dispatch_relationship_reminders(db)==1
    assert dispatch_relationship_reminders(db)==0
    assert db.query(Notification).filter_by(event_type='relationship_follow_up_reminder',related_entity_id=c['id']).count()==1
    visible=client.get('/api/v1/notifications/',headers=h,params={'module':'crm'}).json()['items']
    assert any(item['event_type']=='relationship_follow_up_reminder' and item['related_entity_id']==c['id'] and f"record_id={c['id']}" in item['action_url'] for item in visible)


def test_relationship_grid_filters_sorting_and_stale_edits(client,superuser_headers):
    import json
    h=superuser_headers
    a=contact(client,h,full_name='Alpha grid',email='alpha-grid@example.com')
    contact(client,h,full_name='Zulu grid',email='zulu-grid@example.com')
    query={'search':'grid','filters':{'logic':'and','rules':[{'field':'email','operator':'contains','value':'alpha-grid'}]},'sorting':[{'id':'name','desc':True}],'page':1,'pageSize':25}
    result=get(client,h,'/records',entity='contacts',state=json.dumps(query))
    assert result['total']==1 and result['counts']['contacts']==1
    assert result['items'][0]['id']==a['id']
    query['sorting']=[{'id':'not-a-field','desc':False}]
    assert client.get(ROOT+'/records',headers=h,params={'state':json.dumps(query)}).status_code==422
    due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    first=post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':a['id'],'due_at':due,'priority':'High','next_action':'Review quote'})
    item=get(client,h,f"/pending/contacts/{a['id']}")['items'][0]
    assert item['priority']=='High' and item['metadata']['next_action']=='Review quote'
    stale=client.post(ROOT+'/follow-up',headers=h,json={'entity':'contacts','record_id':a['id'],'activity_id':first['activity_id'],'activity_version':'2000-01-01T00:00:00Z','due_at':due})
    assert stale.status_code==409


def test_bulk_schedule_retry_and_relationship_reminder(client,db,superuser_headers):
    from app.apps.crm.growth import scheduled_relationship_reminders
    from app.models.notification import Notification
    h=superuser_headers;c=contact(client,h)
    due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    payload={'recipients':[{'entity':'contacts','id':c['id']}],'action':'schedule','due_at':due,'request_id':str(uuid4())}
    first=post(client,h,'crm/growth/follow-ups/bulk',payload)
    retry=post(client,h,'crm/growth/follow-ups/bulk',payload)
    assert first['saved']==1 and retry['items'][0]['replayed']
    pending=get(client,h,f"/pending/contacts/{c['id']}")['items']
    assert len(pending)==1
    row=db.get(CRMActivity,pending[0]['id'])
    row.metadata_json={**(row.metadata_json or {}),'reminder_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}
    db.commit()
    assert scheduled_relationship_reminders(db,row.organization_id)==1
    db.commit()
    assert scheduled_relationship_reminders(db,row.organization_id)==0
    assert db.query(Notification).filter_by(event_type='relationship_follow_up_reminder',related_entity_id=c['id']).count()==1
    visible=client.get('/api/v1/notifications/',headers=h,params={'module':'crm'}).json()['items']
    assert any(item['event_type']=='relationship_follow_up_reminder' and item['related_entity_id']==c['id'] and f"record_id={c['id']}" in item['action_url'] for item in visible)


def get(client,h,path,**params):
    response=client.get(ROOT+path,headers=h,params=params)
    assert response.status_code==200,response.text
    return response.json()


def test_offering_audience_links_leads_customers_contacts_and_deals(client,db,superuser_headers):
    h=superuser_headers
    p=offering(client,h,'product','GROWTH-P');s=offering(client,h,'service','GROWTH-S')
    lead=post(client,h,'crm/leads',{'first_name':'Lead','full_name':'Product lead','catalog_lines':[line(p)]})
    company=post(client,h,'crm/companies',{'name':'Product company','catalog_lines':[line(p)]})
    person=contact(client,h,full_name='Deal contact',email='dealcontact@example.com',catalog_lines=[line(s)])
    contact(client,h,full_name='Unrelated',email='unrelated@example.com')
    pipeline=post(client,h,'crm/pipelines',{'name':'Growth'})
    stage=post(client,h,f"crm/pipelines/{pipeline['id']}/stages",{'name':'Discovery'})
    deal=post(client,h,'crm/deals',{'name':'Product deal','pipeline_id':pipeline['id'],'stage_id':stage['id'],'contact_id':person['id'],'company_id':company['id'],'catalog_items':[line(p)]})
    result=get(client,h,'/records',kind='product',item_id=p['id'])
    assert result['total']==4
    assert {r['key'] for r in result['items']}=={f"leads:{lead['id']}",f"contacts:{person['id']}",f"companies:{company['id']}",f"deals:{deal['id']}"}
    assert result['counts']=={'leads':1,'contacts':1,'companies':1,'deals':1}
    assert len(get(client,h,'/records',kind='product',item_id=p['id'],per_page=2,page=2)['items'])==2
    services=get(client,h,'/records',kind='service',item_id=s['id'])
    assert [r['key'] for r in services['items']]==[f"contacts:{person['id']}"]
    # Tenant rows without visibility can never enter an audience.
    db.add(CRMContact(organization_id=2,first_name='Hidden',full_name='Hidden',email='hidden@example.com'));db.commit()
    assert not any(r['name']=='Hidden' for r in get(client,h,'/records')['items'])


def test_follow_up_schedule_reschedule_complete_and_next_step(client,db,superuser_headers):
    h=superuser_headers;c=contact(client,h)
    due=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    first=post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':c['id'],'due_at':due,'title':'Discuss renewal','channel':'call'})
    assert get(client,h,'/records',entity='contacts',bucket='upcoming',active_only=True)['total']==1
    pending=get(client,h,f"/pending/contacts/{c['id']}")['items']
    assert len(pending)==1 and pending[0]['title']=='Discuss renewal'
    changed=post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':c['id'],'activity_id':first['activity_id'],'due_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'title':'Renewal callback'})
    assert changed['activity_id']==first['activity_id']
    post(client,h,'crm/growth/follow-up',{'entity':'contacts','record_id':c['id'],'action':'complete','activity_id':first['activity_id'],'outcome':'Connected','notes':'Customer confirmed renewal'})
    assert not get(client,h,f"/pending/contacts/{c['id']}")['items']
    assert get(client,h,'/records',entity='contacts',bucket='missing',active_only=True)['total']==1
    db.expire_all()
    assert db.get(CRMActivity,first['activity_id']).status=='Completed'
    stale=client.post(ROOT+'/follow-up',headers=h,json={'entity':'contacts','record_id':c['id'],'action':'complete','activity_id':first['activity_id'],'outcome':'Connected'})
    assert stale.status_code==409


def test_customer_follow_up_and_timezone_validation(client,superuser_headers):
    h=superuser_headers;company=post(client,h,'crm/companies',{'name':'Long term customer'})
    post(client,h,'crm/growth/follow-up',{'entity':'companies','record_id':company['id'],'due_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'title':'Customer care call'})
    rows=get(client,h,'/records',entity='companies',bucket='upcoming')['items']
    assert len(rows)==1 and rows[0]['due']
    assert len(get(client,h,f"/pending/companies/{company['id']}")['items'])==1
    assert client.get(ROOT+'/records',headers=h,params={'timezone_name':'invalid/zone'}).status_code==422
    invalid=client.post(ROOT+'/follow-up',headers=h,json={'entity':'companies','record_id':company['id'],'due_at':'2020-01-01T12:00:00'})
    assert invalid.status_code==422


def greeting(recipients,**kwargs):
    return {'recipients':[{'entity':'contacts','id':c['id']} for c in recipients],'channel':'email','occasion':'Birthday','subject':'Happy birthday {{name}}','body':'Hello {{name}}, best wishes from {{sender}}.',**kwargs}


def test_greeting_preview_personalizes_excludes_optouts_and_duplicates(client,superuser_headers):
    h=superuser_headers
    a=contact(client,h,full_name='Asha',email='asha@example.com')
    duplicate=contact(client,h,full_name='Duplicate Asha',email='asha@example.com',confirmShared=True,sharedReason='Explicit duplicate destination regression fixture')
    opted=contact(client,h,full_name='Opted out',email='no@example.com')
    missing=contact(client,h,full_name='Missing email',email=None)
    post(client,h,'communication/consents',{'email':'no@example.com','record_type':'contact','record_id':opted['id'],'consent_type':'email','status':'opted_out'})
    result=post(client,h,'crm/growth/greetings/preview',greeting([a,duplicate,opted,missing]))
    assert result['eligible']==1 and result['blocked']==3
    assert 'Hello Asha' in result['items'][0]['body']
    assert 'Duplicate destination' in result['items'][1]['reason']
    assert 'opted out' in result['items'][2]['reason']
    assert result['items'][3]['reason']=='No email address recorded'


def test_whatsapp_and_sms_are_explicit_external_drafts(client,superuser_headers):
    h=superuser_headers;c=contact(client,h,phone='9000012345',phone_country_code='+91')
    for channel,prefix in [('whatsapp','https://wa.me/919000012345?text='),('sms','sms:+919000012345?body=')]:
        payload=greeting([c],channel=channel)
        result=post(client,h,'crm/growth/greetings/preview',payload)
        assert result['can_send'] is False and result['eligible']==1
        assert result['items'][0]['compose_url'].startswith(prefix)
        response=client.post(ROOT+'/greetings/send',headers=h,json={**payload,'preview_token':result['preview_token'],'request_id':str(uuid4())})
        assert response.status_code==409


def test_reviewed_email_send_is_idempotent_and_rejects_content_changes(client,db,superuser_headers,monkeypatch):
    from app.core.config import settings
    from app.apps.communication.models import CommunicationEmailMessage
    monkeypatch.setattr(settings,'COMMUNICATION_EMAIL_PROVIDER','stub')
    h=superuser_headers;c=contact(client,h,full_name='Asha',email='asha@example.com')
    payload=greeting([c]);review=post(client,h,'crm/growth/greetings/preview',payload)
    assert review['can_send'] is True
    send={**payload,'preview_token':review['preview_token'],'request_id':str(uuid4())}
    stale=client.post(ROOT+'/greetings/send',headers=h,json={**send,'body':'Changed after review'})
    assert stale.status_code==409
    result=post(client,h,'crm/growth/greetings/send',send)
    assert result['results'][0]['status']=='sent' and result['replayed'] is False
    repeated=post(client,h,'crm/growth/greetings/send',send)
    assert repeated['replayed'] is True
    assert db.query(CommunicationEmailMessage).filter_by(to_email='asha@example.com').count()==1


def test_birthdays_and_anniversaries_are_filtered_by_local_date(client,superuser_headers):
    h=superuser_headers;today=datetime.now(timezone.utc).date().isoformat()
    contact(client,h,full_name='Birthday customer',email='birthday@example.com',date_of_birth=today,customer_since=today)
    contact(client,h,full_name='Other customer',email='other@example.com')
    assert get(client,h,'/records',entity='contacts',occasion='birthday',timezone_name='UTC')['total']==1
    assert get(client,h,'/records',entity='contacts',occasion='anniversary',timezone_name='UTC')['total']==1

def test_read_only_actor_cannot_schedule_or_send(client,db,superuser_headers,monkeypatch):
    from tests.test_shared_catalog import scoped_headers
    from app.models.user import User
    from app.branches.models import BranchGrant
    from app.core.config import settings
    h=superuser_headers;c=contact(client,h,full_name='Viewer customer',email='viewer-customer@example.com')
    viewer=scoped_headers(client,db,'growth_read_only',['crm_view'])
    actor=db.query(User).filter_by(email='growth_read_only@example.com').one()
    db.add(BranchGrant(user_id=actor.id,company_id=1,branch_id=int(h['X-Suite-Branch']),can_write=False))
    db.get(CRMContact,c['id']).owner_user_id=actor.id;db.commit()
    viewer['X-Suite-Branch']=h['X-Suite-Branch']
    listing=get(client,viewer,'/records',entity='contacts')
    assert listing['items'] and listing['items'][0]['can_edit'] is False
    denied=client.post(ROOT+'/follow-up',headers=viewer,json={'entity':'contacts','record_id':c['id'],'due_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    assert denied.status_code==403
    monkeypatch.setattr(settings,'COMMUNICATION_EMAIL_PROVIDER','stub')
    payload=greeting([c]);review=post(client,viewer,'crm/growth/greetings/preview',payload)
    assert review['can_send'] is False
    denied=client.post(ROOT+'/greetings/send',headers=viewer,json={**payload,'preview_token':review['preview_token'],'request_id':str(uuid4())})
    assert denied.status_code==403


def test_review_rechecks_changed_destination_and_rejects_unknown_variables(client,superuser_headers,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'COMMUNICATION_EMAIL_PROVIDER','stub')
    h=superuser_headers;c=contact(client,h,email='original@example.com')
    payload=greeting([c]);review=post(client,h,'crm/growth/greetings/preview',payload)
    changed=client.patch(f"/api/v1/crm/contacts/{c['id']}",headers=h,json={'email':'changed@example.com'})
    assert changed.status_code==200,changed.text
    response=client.post(ROOT+'/greetings/send',headers=h,json={**payload,'preview_token':review['preview_token'],'request_id':str(uuid4())})
    assert response.status_code==409
    unknown=client.post(ROOT+'/greetings/preview',headers=h,json={**payload,'body':'Hello {{unsupported.variable}}'})
    assert unknown.status_code==422
