"""Original brief regressions, isolated DB and no external delivery."""
from datetime import timedelta
import json
from tests.test_communication_engagement import customer_thread
from tests.test_whatsapp_workspace import workspace,incoming
from app.services import whatsapp_workspace as wa
from app.shared.whatsapp_models import WhatsAppContact,WhatsAppMessage
from app.apps.crm.models import CRMActivity
from test_identity_utils import own_workflow_records

BASE='/api/v1/communication/engagement'
WA='/api/v1/integrations/whatsapp'

def test_message_search_and_literal_wildcards(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,*_=customer_thread
    messages[0].body='Unique proposal needle';db.commit()
    for term in ['proposal needle','synthetic@example.invalid','Synthetic Customer']:
        r=client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','search':term})
        assert r.status_code==200,r.text
        assert [i['id'] for i in r.json()['items']]==[contact.id]
    assert client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','search':'%'}).json()['items']==[]
    summary=client.get(BASE+'/health-summary',headers=headers)
    assert summary.status_code==200,summary.text
    assert summary.json()['conversationCount']==1
    # Shared deal capture loads these legacy adapters through the catalog service.
    for entity in ('products','services'):
        response=client.get('/api/v1/crm/'+entity,headers=headers)
        assert response.status_code==200,response.text
    assert client.get('/api/v1/catalog/items',headers=headers,params={'price_book_id':0}).status_code==422

def test_activity_cursor_keeps_recently_active_old_contact(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,*_=customer_thread
    contact.last_message_at=wa.now()
    for index in range(205):
        row=WhatsAppContact(organization_id=1,recipient=str(919860000000+index),last_message_at=wa.now()-timedelta(days=index+1),consent='unknown')
        db.add(row);own_workflow_records(db,row)
    db.commit()
    r=client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp'})
    assert r.status_code==200,r.text
    first=r.json();assert first['items'][0]['id']==contact.id
    assert len(first['items'])==200 and first['nextCursor']
    r=client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','cursor':first['nextCursor']})
    assert r.status_code==200,r.text
    assert len(r.json()['items'])==6
    assert not set(i['id'] for i in first['items']).intersection(i['id'] for i in r.json()['items'])
    assert client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','cursor':'bad'}).status_code==422

def test_pending_followups_and_history_are_distinct_from_snooze(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,*_=customer_thread
    path=BASE+f'/conversations/whatsapp/{contact.id}'
    r=client.put(path+'/workflow',headers=headers,json={'status':'pending','assignedUserId':actor.id,'handoverNote':'Finance review'})
    assert r.status_code==200,r.text
    def queue(value):
        r=client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','queue':value});assert r.status_code==200,r.text;return r.json()['items']
    assert len(queue('pending'))==1 and queue('followups')==[] and queue('snoozed')==[]
    activity=CRMActivity(organization_id=1,entity_type='contact',entity_id=record.id,contact_id=record.id,subject='Call back',activity_type='Call',status='Pending',due_date=wa.now()+timedelta(days=1))
    db.add(activity);own_workflow_records(db,activity);db.commit()
    assert len(queue('followups'))==1
    r=client.get(WA+f'/conversations/{contact.id}/context',headers=headers)
    assert r.status_code==200,r.text
    assert r.json()['history'][0]['previousStatus']=='open'
    assert r.json()['history'][0]['note']=='Finance review'
    assert r.json()['activity'][0]['title']=='Call back'

def test_notes_and_profile_use_canonical_crm(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,*_=customer_thread
    record.tags_text='Customer, VIP';db.commit()
    r=client.post('/api/v1/crm/notes',headers=headers,json={'body':'Internal preparation only','contactId':record.id,'isInternal':True})
    assert r.status_code in (200,201),r.text
    r=client.get(WA+f'/conversations/{contact.id}/context',headers=headers)
    assert r.status_code==200,r.text
    assert r.json()['notes'][0]['body']=='Internal preparation only'
    assert r.json()['profile']['tags']=='Customer, VIP'
    for kind,size in [('customer',1),('vendor',0)]:
        r=client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','contact_type':kind})
        assert r.status_code==200,r.text
        assert len(r.json()['items'])==size
    assert client.get(BASE+'/inbox',headers=headers,params={'channel':'whatsapp','since':(wa.now()+timedelta(days=1)).isoformat()}).json()['items']==[]

def test_interactive_choice_is_readable_and_deduplicated(workspace):
    db,user,companies,connections=workspace
    event=incoming(connections[0],'wamid.choice')
    message=event['entry'][0]['changes'][0]['value']['messages'][0]
    message.update(type='interactive',interactive={'type':'list_reply','list_reply':{'id':'plan-pro','title':'Pro plan','description':'Annual subscription'}})
    wa.ingest(db,event);wa.ingest(db,event)
    assert db.query(WhatsAppMessage).one().body=='Pro plan — Annual subscription'

def test_resolution_uses_proven_audit_cycles_and_excludes_legacy_guesses(client,db,customer_thread):
    from app.branches.models import BranchAudit
    headers,actor,branch,record,contact,messages,*_=customer_thread
    start=wa.now()-timedelta(hours=2);messages[0].created_at=start
    for minute,previous,status in [(30,'open','resolved'),(40,'resolved','open'),(50,'open','pending'),(60,'pending','resolved'),(70,None,'resolved')]:
        db.add(BranchAudit(company_id=1,actor_id=actor.id,operation='communication.handover',reason='Sandbox transition',created_at=start+timedelta(minutes=minute),details={'kind':'whatsapp','record_id':contact.id,'previous_status':previous,'status':status}))
    db.commit()
    r=client.get(WA+'/analytics',headers=headers,params={'from':(start-timedelta(minutes=1)).isoformat(),'until':wa.now().isoformat()})
    assert r.status_code==200,r.text
    assert r.json()['resolutionSamples']==2 and r.json()['resolutionSeconds']==1500

def test_stale_campaign_preview_cannot_launch_new_version(client,db,customer_thread):
    headers,*_=customer_thread
    base='/api/v1/communication/customers/automations'
    data={'name':'Sandbox version check','trigger':'campaign','purpose':'marketing','subject':'Hello','body':'Hello','status':'active'}
    r=client.post(base,headers=headers,json=data);assert r.status_code==201,r.text
    ident=r.json()['id'];assert client.put(base+f'/{ident}',headers=headers,json={**data,'body':'Updated content'}).status_code==200
    r=client.post(base+f'/{ident}/launch',headers=headers,json={'expected_version':1})
    assert r.status_code==409 and 'preview' in r.text.lower()

def test_shared_followup_returned_version_can_complete_and_stale_version_cannot(client,customer_thread):
    headers,actor,branch,record,*_=customer_thread
    base='/api/v1/crm/growth'
    data={'entity':'contacts','record_id':record.id,'title':'Browser round trip','channel':'whatsapp','due_at':(wa.now()+timedelta(days=1)).isoformat()}
    r=client.post(base+'/follow-up',headers=headers,json=data);assert r.status_code==200,r.text
    pending=client.get(base+f'/pending/contacts/{record.id}',headers=headers).json()['items'][0]
    assert pending['version'].endswith('Z') or pending['version'].endswith('+00:00')
    complete={**data,'action':'complete','due_at':None,'activity_id':pending['id'],'activity_version':pending['version'],'outcome':'Resolved'}
    assert client.post(base+'/follow-up',headers=headers,json={**complete,'activity_version':'2000-01-01T00:00:00Z'}).status_code==409
    r=client.post(base+'/follow-up',headers=headers,json=complete);assert r.status_code==200,r.text
    assert client.get(base+f'/pending/contacts/{record.id}',headers=headers).json()['items']==[]

def test_campaign_business_audience_reuses_canonical_crm_and_consent(client,db,customer_thread):
    from tests.test_crm_associations_merge import offering,line
    headers,actor,branch,record,contact,messages,recipient,*_=customer_thread
    record.tags_text='Customer, VIP';recipient.phone='+'+contact.recipient
    recipient.preferences={'whatsapp.marketing':True};db.commit()
    product=offering(client,headers,'product','WA-AUDIENCE')
    r=client.patch(f'/api/v1/crm/contacts/{record.id}',headers=headers,json={'catalog_lines':[line(product)]})
    assert r.status_code==200,r.text
    base='/api/v1/communication/customers/automations'
    r=client.post(base,headers=headers,json={'name':'Sandbox audience','trigger':'campaign','purpose':'marketing','channel':'whatsapp','subject':'Hello','body':'Hello {{name}}','status':'active','whatsapp_template':{'name':'approved_update','language':{'code':'en'},'components':[{'type':'body','parameters':[{'type':'text','text':'{{name}}'}]}]}})
    assert r.status_code==201,r.text
    ident=r.json()['id'];criteria={'recipient_ids':[recipient.id],'contact_type':'customer','tag':'vip','offerings':json.dumps([{'kind':'product','id':product['id']}])}
    r=client.post(base+f'/{ident}/preview',headers=headers,json=criteria)
    assert r.status_code==200,r.text
    assert r.json()['eligible']==1
    assert r.json()['sample']['template']['components'][0]['parameters'][0]['text']=='Synthetic Customer'
    assert client.post(base+f'/{ident}/preview',headers=headers,json={**criteria,'contact_type':'lead'}).json()['eligible']==0
    assert client.post(base+f'/{ident}/preview',headers=headers,json={**criteria,'tag':'not-vip'}).json()['eligible']==0
    assert client.post(base+f'/{ident}/preview',headers=headers,json={**criteria,'offerings':'not-json'}).status_code==422
    recipient.preferences={'whatsapp.marketing':False};db.commit()
    assert client.post(base+f'/{ident}/preview',headers=headers,json=criteria).json()['eligible']==0
