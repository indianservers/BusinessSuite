from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.test_communication_engagement import customer_thread
from tests.test_whatsapp_workspace import workspace, incoming
from app.api.v1.whatsapp_cloud import SendInput
from app.services import whatsapp_workspace as wa, whatsapp_media as media
from app.shared.whatsapp_models import WhatsAppContact, WhatsAppMessage, WhatsAppConnection

BASE='/api/v1/integrations/whatsapp'


def test_media_webhook_keeps_caption_and_deduplicates(workspace):
    db,user,companies,connections=workspace
    event=incoming(connections[0])
    message=event['entry'][0]['changes'][0]['value']['messages'][0]
    message.update(type='document',document={'id':'8877','mime_type':'application/pdf','filename':'quotation.pdf','caption':'Your quotation'})
    wa.ingest(db,event);wa.ingest(db,event)
    row=db.query(WhatsAppMessage).filter_by(provider_message_id='wamid.in').one()
    assert row.body=='Your quotation' and row.kind=='document'
    assert wa.message_data(row)['media']['filename']=='quotation.pdf'
    assert db.query(WhatsAppMessage).count()==1


def test_media_send_uses_existing_reservation_and_enforces_window(workspace,monkeypatch):
    db,user,companies,connections=workspace
    wa.ingest(db,incoming(connections[0]))
    contact=db.query(WhatsAppContact).filter_by(organization_id=companies[0].id).one()
    value={'id':'8877','kind':'document','mimeType':'application/pdf','filename':'quote.pdf','size':12}
    token=media.upload_token(user,contact,connections[0],value)
    calls=[]
    def send(*args,**kwargs):calls.append(kwargs);return 'accepted','wamid.media-out'
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',send)
    data=SendInput(requestId='media-request-001',to=contact.recipient,body='Quote',media=token)
    row=wa.send_message(db,user,data)
    assert row.kind=='document' and row.status=='accepted' and media.metadata(row)==value
    assert wa.send_message(db,user,data).id==row.id and len(calls)==1
    assert calls[0]['media']==value
    contact.last_inbound_at=wa.now()-timedelta(hours=25);db.commit()
    # A duplicate reconciliation remains safe even after the window closes.
    assert wa.send_message(db,user,data).id==row.id and len(calls)==1
    with pytest.raises(HTTPException) as error:
        wa.send_message(db,user,data.model_copy(update={'requestId':'media-request-002'}))
    assert error.value.status_code==409 and len(calls)==1


def test_upload_receipt_is_bound_to_actor_contact_and_connection(workspace):
    db,user,companies,connections=workspace
    contact=wa.contact_for(db,companies[0].id,'919876543210');db.flush()
    token=media.upload_token(user,contact,connections[0],{'id':'9911','kind':'image'})
    assert media.verify_upload(token,user,contact,connections[0])['id']=='9911'
    for actor,conversation,connection in [(SimpleNamespace(id=user.id+1),contact,connections[0]),(user,SimpleNamespace(id=contact.id+1,organization_id=companies[0].id),connections[0]),(user,contact,connections[1])]:
        with pytest.raises(HTTPException):media.verify_upload(token,actor,conversation,connection)
    with pytest.raises(HTTPException):media.verify_upload('tampered',user,contact,connections[0])


def test_upload_rejects_mime_spoofing_and_size_before_network(workspace,monkeypatch):
    _,_,_,connections=workspace
    monkeypatch.setattr(media.httpx,'post',lambda *a,**k:pytest.fail('Invalid uploads must not reach Meta'))
    for data,mime in [(b'<script>','text/html'),(b'not a pdf','application/pdf'),(b'0'*(5*1024*1024+1),'image/png')]:
        with pytest.raises(HTTPException):media.upload(connections[0],'test',data,mime,'file')


def test_media_provider_payload_uses_media_id(monkeypatch):
    from app.services.whatsapp import MetaWhatsAppProvider,WhatsAppGraph
    calls=[]
    def request(self,method,path,**kwargs):calls.append(kwargs['payload']);return {'messages':[{'id':'wamid.accepted'}]}
    monkeypatch.setattr(WhatsAppGraph,'request',request)
    provider=MetaWhatsAppProvider('test','12345')
    assert provider.send(to='919876543210',body='Caption',media={'id':'8877','kind':'document','filename':'quote.pdf'})==('accepted','wamid.accepted')
    assert calls[0]['document']=={'id':'8877','caption':'Caption','filename':'quote.pdf'}
    provider.send(to='919876543210',body='Existing text behavior')
    assert calls[1]['type']=='text' and calls[1]['text']['preview_url'] is False


def test_media_upload_download_permissions_and_private_response(client,db,customer_thread,monkeypatch):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    connection=db.get(WhatsAppConnection,messages[0].connection_id)
    connection.token_ciphertext=wa.protect('test-only-token');db.commit()
    uploaded={'id':'8877','kind':'document','mimeType':'application/pdf','filename':'quote.pdf','size':12}
    monkeypatch.setattr(media,'upload',lambda *args:uploaded)
    response=client.post(BASE+f'/conversations/{contact.id}/media',headers=headers,files={'file':('quote.pdf',b'%PDF-test','application/pdf')})
    assert response.status_code==200,response.text
    assert response.json()['token']
    messages[0].kind='document';messages[0].template_json={'media':uploaded};db.commit()
    calls=[]
    monkeypatch.setattr(media,'download',lambda *args:(calls.append(1) or b'%PDF-test','application/pdf'))
    response=client.get(BASE+f'/messages/{messages[0].id}/media',headers=headers)
    assert response.status_code==200 and response.content==b'%PDF-test'
    assert response.headers['cache-control']=='private, no-store'
    from app.models.company import Branch
    other=Branch(company_id=1,name='Media other branch',is_active=True);db.add(other);db.commit()
    assert client.get(BASE+f'/messages/{messages[0].id}/media',headers={**headers,'X-Suite-Branch':str(other.id)}).status_code==404
    assert calls==[1]
    contact.last_inbound_at=wa.now()-timedelta(hours=25);db.commit()
    assert client.post(BASE+f'/conversations/{contact.id}/media',headers=headers,files={'file':('quote.pdf',b'%PDF-test','application/pdf')}).status_code==409


def test_download_rejects_non_meta_url_before_fetch(workspace,monkeypatch):
    from app.services.whatsapp import WhatsAppGraph,MetaError
    _,_,_,connections=workspace
    monkeypatch.setattr(WhatsAppGraph,'request',lambda *a,**k:{'url':'https://attacker.example/file','mime_type':'application/pdf'})
    monkeypatch.setattr(media.httpx,'stream',lambda *a,**k:pytest.fail('Do not forward credentials to arbitrary URLs'))
    with pytest.raises(MetaError):media.download(connections[0],'secret',{'id':'8877'})


def test_inline_context_links_canonical_records_and_followup_roundtrip(client,db,customer_thread):
    from app.apps.crm.models import CRMPipeline,CRMPipelineStage,CRMDeal,CRMQuotation
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.commercial_models import InvoiceContext
    from app.branches.models import BranchOwnership
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    pipeline=CRMPipeline(organization_id=1,name='Hub pipeline');db.add(pipeline);db.flush()
    stage=CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name='Qualified');db.add(stage);db.flush()
    deal=CRMDeal(organization_id=1,branch_id=branch.id,contact_id=record.id,pipeline_id=pipeline.id,stage_id=stage.id,name='Canonical deal',amount=300,currency='INR')
    db.add(deal);db.flush()
    quote=CRMQuotation(organization_id=1,branch_id=branch.id,contact_id=record.id,deal_id=deal.id,quote_number='HUB-Q1',issue_date=wa.now().date(),expiry_date=(wa.now()+timedelta(days=7)).date(),total_amount=300)
    invoice=SRMInvoice(organization_id=1,invoice_number='HUB-I1',total_amount=300,balance_amount=120,currency='INR',created_by=actor.id)
    db.add_all([quote,invoice]);db.flush()
    invoice_context=InvoiceContext(invoice_id=invoice.id,seller_id=1,contact_id=record.id,request_id='hub-invoice-test',origin='srm')
    db.add(invoice_context)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,invoice_context)
    for row in [pipeline,stage,deal,quote,invoice]:db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch.id,source='test'))
    db.commit()
    response=client.post('/api/v1/crm/growth/follow-up',headers=headers,json={'entity':'contacts','record_id':record.id,'title':'Review quotation in WhatsApp','channel':'whatsapp','due_at':(wa.now()+timedelta(days=2)).isoformat()})
    assert response.status_code==200,response.text
    activity=response.json()['activity_id']
    response=client.get(BASE+f'/conversations/{contact.id}/context',headers=headers)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['deals'][0]['id']==deal.id and data['quotations'][0]['id']==quote.id
    assert data['invoices'][0]['id']==invoice.id and float(data['invoices'][0]['balance'])==120
    assert data['followUps'][0]['id']==activity
    response=client.post('/api/v1/crm/growth/follow-up',headers=headers,json={'entity':'contacts','record_id':record.id,'action':'complete','activity_id':activity,'title':'Review quotation in WhatsApp','channel':'whatsapp','outcome':'Connected'})
    assert response.status_code==200,response.text
    assert client.get(BASE+f'/conversations/{contact.id}/context',headers=headers).json()['followUps']==[]


def test_analytics_is_whatsapp_only_and_uses_confirmed_states(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    at=wa.now()-timedelta(hours=2)
    for index,m in enumerate(messages):m.created_at=at+timedelta(minutes=index*5)
    db.commit()
    response=client.get(BASE+'/analytics',headers=headers,params={'from':(at-timedelta(days=1)).isoformat(),'until':wa.now().isoformat()})
    assert response.status_code==200,response.text
    data=response.json();totals=data['totals']
    assert totals['conversations']==1 and totals['messages']==3 and totals['outbound']==1
    assert totals['read']==totals['delivered']==totals['sent']==1
    assert data['firstResponseSeconds']==300 and data['resolutionSeconds'] is None
    assert client.get(BASE+'/analytics',headers=headers,params={'from':'2026-01-01T00:00:00','until':'2026-01-02T00:00:00Z'}).status_code==422
    from app.models.company import Branch
    other=Branch(company_id=1,name='Analytics other branch',is_active=True);db.add(other);db.commit()
    hidden=client.get(BASE+'/analytics',headers={**headers,'X-Suite-Branch':str(other.id)})
    assert hidden.status_code==200
    assert hidden.json()['totals']['outbound']==0 and hidden.json()['totals']['conversations']==0


def test_analytics_counts_beyond_inbox_page_and_deduplicates_followups(client,db,customer_thread):
    from app.branches.models import BranchOwnership
    from app.apps.crm.models import CRMActivity
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    for index in range(260):
        c=WhatsAppContact(organization_id=1,recipient=str(919870000000+index),entity_type='contact',entity_id=record.id,consent='unknown')
        db.add(c);db.flush()
        m=WhatsAppMessage(organization_id=1,contact_id=c.id,connection_id=messages[0].connection_id,direction='outbound',kind='template',body='test',status='failed',template_json={'name':'follow_up','language':{'code':'en'}})
        db.add(m);db.flush()
        for row in [c,m]:db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch.id,source='test'))
    activity=CRMActivity(organization_id=1,branch_id=branch.id,entity_type='contact',entity_id=record.id,contact_id=record.id,activity_type='whatsapp',subject='Shared next step',title='Shared next step',due_date=wa.now()+timedelta(days=1),status='Scheduled')
    db.add(activity)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,activity)
    db.commit()
    response=client.get(BASE+'/analytics',headers=headers)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['totals']['conversations']==261 and data['totals']['failed']==260
    assert data['totals']['pendingFollowUps']==1
    assert data['templates'][0]['statuses']['failed']==260


def test_context_and_analytics_do_not_grant_finance_or_cross_tenant_access(client,db,customer_thread):
    from tests.communication_test_utils import communication_headers
    from app.models.company import Branch,Company
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    viewer=communication_headers(client,db,email='hub-crm-viewer@example.com',permissions=['communication_view'],crm_access=True)
    viewer={**viewer,'X-Suite-Branch':str(branch.id)}
    response=client.get(BASE+f'/conversations/{contact.id}/context',headers=viewer)
    assert response.status_code==200,response.text
    assert response.json()['canViewFinance'] is False and response.json()['invoices']==[]
    assert response.json()['canFollowUp'] is False
    # No arbitrary owner/team identifiers may broaden report access.
    for filter in ({'employee':999999},{'team':999999}):
        assert client.get(BASE+'/analytics',headers=viewer,params=filter).status_code==403
    company=Company(name='Private foreign hub');db.add(company);db.flush()
    foreign=WhatsAppContact(organization_id=company.id,recipient='919876543222',consent='unknown');db.add(foreign);db.commit()
    assert client.get(BASE+f'/conversations/{foreign.id}/context',headers=headers).status_code==404
    other=Branch(company_id=1,name='Private hub branch',is_active=True);db.add(other);db.commit()
    assert client.get(BASE+f'/conversations/{contact.id}/context',headers={**headers,'X-Suite-Branch':str(other.id)}).status_code==404


def test_analytics_owner_team_filters_and_campaign_attribution(client,db,customer_thread):
    from app.apps.crm.models import CRMTeam
    from app.apps.communication.engagement_models import ConversationWorkflow
    from app.apps.communication.customer_models import CustomerAutomation,CustomerDelivery
    from test_identity_utils import own_workflow_records
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    team=CRMTeam(organization_id=1,name='Hub sales team');db.add(team);db.flush()
    record.assigned_team_id=team.id
    workflow=ConversationWorkflow(organization_id=1,branch_id=branch.id,kind='whatsapp',record_id=contact.id,assigned_user_id=actor.id,status='open',handover_note='',updated_by=actor.id)
    campaign=CustomerAutomation(organization_id=1,branch_id=branch.id,name='Canonical campaign',trigger='campaign',purpose='marketing',channel='whatsapp',subject='Campaign',body='Campaign',created_by=actor.id)
    db.add(campaign);db.flush()
    delivery=CustomerDelivery(organization_id=1,branch_id=branch.id,automation_id=campaign.id,recipient_id=recipient.id,event_key='hub-campaign',source_type='contact',source_id=record.id,purpose='marketing',channel='whatsapp',subject='Campaign',body='Original campaign message',status='accepted',due_at=wa.now(),created_by=actor.id,whatsapp_message_id=messages[1].id)
    db.add_all([workflow,delivery]);own_workflow_records(db,team,workflow,delivery,campaign);db.commit()
    response=client.get(BASE+'/analytics',headers=headers,params={'employee':actor.id,'team':team.id})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['totals']['outbound']==1 and data['workload'][0]['employeeId']==actor.id
    # Read evidence comes from the original message, not the campaign's accepted flag.
    assert data['campaigns']==[{'automationId':str(campaign.id),'statuses':{'read':1}}]
    assert any(t['id']==team.id for t in data['teams'])
    campaign.trigger='invoice.due';db.commit()
    # Transactional automations are not relabeled as campaigns.
    report=client.get(BASE+'/analytics',headers=headers).json()
    assert report['campaigns']==[] and report['totals']['outbound']==1


def test_media_upload_uses_server_only_credentials(workspace,monkeypatch):
    _,_,_,connections=workspace
    calls=[]
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(is_error=False,json=lambda:{'id':'998877'})
    monkeypatch.setattr(media.httpx,'post',post)
    result=media.upload(connections[0],'server-only-secret',b'%PDF-synthetic','application/pdf','../quote.pdf')
    assert result['id']=='998877' and result['filename']=='quote.pdf'
    url,kwargs=calls[0]
    assert url.endswith('/'+connections[0].phone_number_id+'/media')
    assert kwargs['headers']=={'Authorization':'Bearer server-only-secret'}
    assert kwargs['data']['messaging_product']=='whatsapp'
    assert 'server-only-secret' not in str(result)
