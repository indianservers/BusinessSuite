from datetime import timedelta
from uuid import uuid4
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from tests.test_whatsapp_workspace import workspace,incoming
from tests.test_communication_engagement import customer_thread
from tests.test_crm_associations_merge import offering,line
from test_identity_utils import own_workflow_records
from app.services import whatsapp_workspace as wa
from app.api.v1.whatsapp_cloud import SendInput
from app.shared.whatsapp_models import WhatsAppContact,WhatsAppMessage

BASE='/api/v1/integrations/whatsapp'
INBOX='/api/v1/communication/engagement/inbox'


def test_quoted_reply_is_native_and_idempotent(workspace,monkeypatch):
    db,user,companies,connections=workspace
    wa.ingest(db,incoming(connections[0]))
    original=db.query(WhatsAppMessage).one();calls=[]
    def send(*a,**k):calls.append(k);return 'accepted','wamid.quoted'
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',send)
    data=SendInput(requestId='quote-request-001',to='919876543210',body='Here is the answer',replyTo=original.id)
    row=wa.send_message(db,user,data)
    assert calls[0]['reply_to']==original.provider_message_id
    assert wa.message_data(row)['replyTo']['body']==original.body
    assert wa.send_message(db,user,data).id==row.id and len(calls)==1
    # Changing only the quoted target is still a different request payload.
    with pytest.raises(HTTPException) as error:wa.send_message(db,user,data.model_copy(update={'replyTo':row.id}))
    assert error.value.status_code==409


def test_quote_cannot_reference_another_conversation_or_unsent_message(workspace,monkeypatch):
    db,user,companies,connections=workspace
    wa.ingest(db,incoming(connections[0]))
    contact=db.query(WhatsAppContact).one()
    other=wa.contact_for(db,companies[0].id,'919876543211');db.flush()
    invalid=[WhatsAppMessage(organization_id=companies[0].id,connection_id=connections[0].id,contact_id=other.id,direction='inbound',kind='text',body='Private other customer',status='received',provider_message_id='wamid.other'),WhatsAppMessage(organization_id=companies[0].id,connection_id=connections[0].id,contact_id=contact.id,direction='outbound',kind='text',body='Not submitted',status='submitting')]
    db.add_all(invalid);db.commit()
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',lambda *a,**k:pytest.fail('Invalid reply must not reach provider'))
    for row in invalid:
        with pytest.raises(HTTPException) as error:wa.send_message(db,user,SendInput(requestId='invalid-quote-'+str(row.id),to=contact.recipient,body='Answer',replyTo=row.id))
        assert error.value.status_code==422
    contact.last_inbound_at=wa.now()-timedelta(hours=25);db.commit()
    original=db.query(WhatsAppMessage).filter_by(contact_id=contact.id,status='received').one()
    with pytest.raises(HTTPException) as error:wa.send_message(db,user,SendInput(requestId='closed-window-quote',to=contact.recipient,body='Answer',replyTo=original.id))
    assert error.value.status_code==409
    with pytest.raises(ValidationError):SendInput(requestId='template-quote-1',to=contact.recipient,replyTo=1,template={'name':'approved','language':{'code':'en'}})


def test_inbound_media_quote_preserves_context_and_webhook_dedup(workspace):
    db,user,companies,connections=workspace
    wa.ingest(db,incoming(connections[0]))
    original=db.query(WhatsAppMessage).one()
    event=incoming(connections[0],'wamid.quote-in')
    item=event['entry'][0]['changes'][0]['value']['messages'][0]
    item.update(context={'id':original.provider_message_id},type='image',image={'id':'778899','mime_type':'image/png','caption':'This one?'})
    wa.ingest(db,event);wa.ingest(db,event)
    row=db.query(WhatsAppMessage).filter_by(provider_message_id='wamid.quote-in').one()
    assert wa.message_data(row)['replyTo']['id']==original.id and wa.message_data(row)['media']['id']=='778899'
    assert db.query(WhatsAppMessage).count()==2


def test_provider_quoted_payload_and_plain_text_compatibility(monkeypatch):
    from app.services.whatsapp import MetaWhatsAppProvider,WhatsAppGraph
    payloads=[]
    monkeypatch.setattr(WhatsAppGraph,'request',lambda self,method,path,**kw:(payloads.append(kw['payload']) or {'messages':[{'id':'wamid.accepted'}]}))
    p=MetaWhatsAppProvider('test','12345')
    p.send(to='919876543210',body='Answer',reply_to='wamid.original')
    assert payloads[0]['context']=={'message_id':'wamid.original'}
    p.send(to='919876543210',body='Unquoted')
    assert 'context' not in payloads[1]


def test_tag_filter_scans_before_pagination_and_matches_whole_tags(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    record.tags_text='Enterprise, VIP Customer';db.flush()
    for index in range(205):
        row=WhatsAppContact(organization_id=1,recipient=str(919860000000+index),consent='unknown')
        db.add(row);own_workflow_records(db,row)
    db.commit()
    response=client.get(INBOX,headers=headers,params={'tag':'vip customer'})
    assert response.status_code==200,response.text
    assert [i['id'] for i in response.json()['items']]==[contact.id]
    assert response.json()['nextBefore'] is None
    assert client.get(INBOX,headers=headers,params={'tag':'vip'}).json()['items']==[]


def test_priority_uses_next_crm_followup_and_product_filters_use_canonical_links(client,db,customer_thread):
    from app.apps.crm.models import CRMActivity
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    p=offering(client,headers,'product','WHATSAPP-P1');s=offering(client,headers,'service','WHATSAPP-S1')
    response=client.patch(f'/api/v1/crm/contacts/{record.id}',headers=headers,json={'catalog_lines':[line(p),line(s)]})
    assert response.status_code==200,response.text
    for days,priority in [(1,'High'),(2,'Low')]:
        activity=CRMActivity(organization_id=1,branch_id=branch.id,entity_type='contact',entity_id=record.id,contact_id=record.id,subject='Next step',title='Next step',activity_type='whatsapp',status='Scheduled',priority=priority,due_date=wa.now()+timedelta(days=days))
        db.add(activity);own_workflow_records(db,activity)
    db.commit()
    selected=json.dumps([{'kind':'product','id':p['id']},{'kind':'service','id':s['id']}])
    result=client.get(INBOX,headers=headers,params={'priority':'High','offerings':selected})
    assert result.status_code==200,result.text
    assert [i['id'] for i in result.json()['items']]==[contact.id]
    assert client.get(INBOX,headers=headers,params={'priority':'Low'}).json()['items']==[]
    assert client.get(INBOX,headers=headers,params={'offerings':'malformed'}).status_code==422
    assert client.get(INBOX,headers=headers,params={'priority':'invented'}).status_code==422


def test_filters_do_not_expose_other_branches(client,db,customer_thread):
    from app.models.company import Branch
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    record.tags_text='VIP';db.add(Branch(company_id=1,name='Private filter branch',is_active=True));db.commit()
    other=db.query(Branch).filter_by(name='Private filter branch').one()
    result=client.get(INBOX,headers={**headers,'X-Suite-Branch':str(other.id)},params={'tag':'VIP'})
    assert result.status_code==200 and result.json()['items']==[]


def test_creation_uses_existing_canonical_apis_and_returns_inline_context(client,db,customer_thread,monkeypatch):
    from app.apps.crm.models import CRMCompany,CRMPipeline,CRMPipelineStage
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',lambda *a,**k:pytest.fail('Creating records must not send WhatsApp messages'))
    company=CRMCompany(organization_id=1,branch_id=branch.id,name='Chat account')
    pipe=CRMPipeline(organization_id=1,name='Chat pipeline');db.add_all([company,pipe]);own_workflow_records(db,company,pipe)
    stage=CRMPipelineStage(organization_id=1,pipeline_id=pipe.id,name='New');db.add(stage);own_workflow_records(db,stage)
    record.company_id=company.id;db.commit()
    response=client.post('/api/v1/crm/deals',headers=headers,json={'name':'Chat opportunity','contact_id':record.id,'company_id':company.id,'pipeline_id':pipe.id,'stage_id':stage.id,'currency':'INR','priority':'Critical'})
    assert response.status_code==201,response.text
    deal=response.json()
    deal_thread=WhatsAppContact(organization_id=1,recipient='919876543299',entity_type='deal',entity_id=deal['id'],consent='unknown',last_message_at=wa.now())
    db.add(deal_thread);own_workflow_records(db,deal_thread);db.commit()
    critical=client.get(INBOX,headers=headers,params={'priority':'Critical'})
    assert critical.status_code==200 and [row['id'] for row in critical.json()['items']]==[deal_thread.id]
    quote_data={'quote_number':'CHAT-Q-'+str(record.id),'issue_date':wa.now().date().isoformat(),'expiry_date':(wa.now()+timedelta(days=14)).date().isoformat(),'status':'Draft','deal_id':deal['id'],'contact_id':record.id,'company_id':company.id,'currency':'INR'}
    response=client.post('/api/v1/crm/quotations',headers=headers,json=quote_data)
    assert response.status_code==201,response.text
    quote=response.json()
    assert client.post('/api/v1/crm/quotations',headers=headers,json=quote_data).status_code in (409,422)
    invoice_data={'request_id':str(uuid4()),'customer_id':company.id,'contact_id':record.id,'currency':'INR','lines':[{'description':'Chat service','quantity':1,'unit_price':100,'tax_amount':0,'line_total':100}]}
    response=client.post('/api/v1/srm/invoices/manual',headers=headers,json=invoice_data)
    assert response.status_code==201,response.text
    invoice=response.json()
    assert client.post('/api/v1/srm/invoices/manual',headers=headers,json=invoice_data).json()['id']==invoice['id']
    data=client.get(BASE+f'/conversations/{contact.id}/context',headers=headers).json()
    assert data['creation']['canDeal'] and data['creation']['canQuotation'] and data['creation']['canInvoice']
    assert data['deals'][0]['id']==deal['id'] and data['quotations'][0]['id']==quote['id'] and data['invoices'][0]['id']==invoice['id']


def test_chat_creation_capabilities_never_grant_target_app_permissions(client,db,customer_thread):
    from tests.communication_test_utils import communication_headers
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    viewer=communication_headers(client,db,email='chat-create-viewer@example.com',permissions=['communication_view'],crm_access=True)
    viewer={**viewer,'X-Suite-Branch':str(branch.id)}
    response=client.get(BASE+f'/conversations/{contact.id}/context',headers=viewer)
    assert response.status_code==200,response.text
    creation=response.json()['creation']
    assert not any(creation[k] for k in ['canDeal','canQuotation','canInvoice','canTask'])
    assert client.post('/api/v1/crm/deals',headers=viewer,json={'name':'Unauthorized','pipeline_id':1,'stage_id':1}).status_code==403
    assert client.post('/api/v1/crm/quotations',headers=viewer,json={'quote_number':'NO','issue_date':'2026-11-04','expiry_date':'2026-11-18'}).status_code==403
    assert client.post('/api/v1/srm/invoices/manual',headers=viewer,json={'customer_id':1,'lines':[]}).status_code==403


def test_chat_task_capability_creation_retry_and_canonical_link(client,db,customer_thread):
    from app.apps.project_management.models import PMSProject
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    project=PMSProject(organization_id=1,project_key='WA-CHAT-PMS',name='Chat delivery')
    db.add(project);own_workflow_records(db,project);db.commit()
    context=client.get(BASE+f'/conversations/{contact.id}/context',headers=headers)
    assert context.status_code==200,context.text
    assert context.json()['creation']['canTask'] is True
    path=f'/api/v1/project-management/task-studio/projects/{project.id}/tasks'
    payload={'task':{'title':'Investigate customer inquiry','task_key':'WA-CHAT-TASK'},'assignment':{}}
    response=client.post(path,headers=headers,json=payload)
    assert response.status_code==201,response.text
    task=response.json()['task']
    assert client.post(path,headers=headers,json=payload).json()['task']['id']==task['id']
    link=f"/api/v1/project-management/task-workspace/tasks/{task['id']}/crm-links"
    data={'kind':'contact','record_id':record.id}
    response=client.post(link,headers=headers,json=data)
    assert response.status_code==200,response.text
    assert client.post(link,headers=headers,json=data).json()['id']==response.json()['id']
    work=client.get(f'/api/v1/record-360/contact/{record.id}/work',headers=headers)
    assert work.status_code==200,work.text
    assert any(row['source']=='pms_task' and row['source_id']==task['id'] for row in work.json()['items'])
