from datetime import datetime,timedelta,timezone
import pytest
from app.models.company import Company,Branch
from app.models.user import User
from app.apps.crm.models import CRMContact
from app.branches.models import BranchOwnership
from app.shared.whatsapp_models import WhatsAppConnection,WhatsAppContact,WhatsAppMessage
from app.apps.communication.customer_models import CustomerRecipient,CustomerDelivery,CustomerEmailReply
from app.apps.communication.models import CommunicationEmailMessage
from app.apps.communication.engagement_models import ConversationReading,ConversationWorkflow
from test_identity_utils import attach_test_identity

BASE='/api/v1/communication/engagement'


@pytest.fixture
def customer_thread(client,db,superuser_headers):
    company=db.get(Company,1)
    if not company: company=Company(id=1,name='Engagement test');db.add(company);db.flush()
    branch=db.query(Branch).filter_by(company_id=1).first()
    if not branch: branch=Branch(company_id=1,name='Engagement Main',is_active=True);db.add(branch);db.flush()
    actor=db.query(User).filter_by(email='testadmin@test.com').one()
    attach_test_identity(db,actor,1)
    record=CRMContact(organization_id=1,branch_id=branch.id,first_name='Synthetic',full_name='Synthetic Customer',email='synthetic@example.invalid',phone='9876543210',phone_country_code='91')
    db.add(record);db.flush()
    connection=WhatsAppConnection(organization_id=1,waba_id='9001',phone_number_id='9002',routing_key='9002',status='connected',inbound_branch_id=branch.id)
    contact=WhatsAppContact(organization_id=1,recipient='919876543210',name='WA name',entity_type='contact',entity_id=record.id,consent='unknown',last_inbound_at=datetime.now(timezone.utc),last_message_at=datetime.now(timezone.utc))
    db.add_all([connection,contact]);db.flush()
    messages=[WhatsAppMessage(organization_id=1,connection_id=connection.id,contact_id=contact.id,direction='inbound',kind='text',body='First customer reply',status='received'),WhatsAppMessage(organization_id=1,connection_id=connection.id,contact_id=contact.id,direction='outbound',kind='text',body='Business response',status='read'),WhatsAppMessage(organization_id=1,connection_id=connection.id,contact_id=contact.id,direction='inbound',kind='text',body='Second customer reply',status='received')]
    recipient=CustomerRecipient(organization_id=1,branch_id=branch.id,crm_contact_id=record.id,name='Synthetic Customer',email=record.email,phone='+919876543210',created_by=actor.id,preferences={})
    db.add_all([*messages,recipient]);db.flush()
    delivery=CustomerDelivery(organization_id=1,branch_id=branch.id,recipient_id=recipient.id,event_key='engagement-test',source_type='contact',source_id=record.id,channel='email',purpose='transactional',subject='Service update',body='Email business response',status='accepted',due_at=datetime.now(timezone.utc),created_by=actor.id)
    db.add(delivery);db.flush()
    reply=CustomerEmailReply(organization_id=1,branch_id=branch.id,recipient_id=recipient.id,delivery_id=delivery.id,provider_event_id='engagement-reply',subject='Re: Service update',body='Customer email response')
    db.add(reply)
    for row in [record,contact,*messages,recipient,delivery,reply]:
        db.flush()
        db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch.id,source='test'))
    db.commit()
    headers={**superuser_headers,'X-Suite-Branch':str(branch.id)}
    return headers,actor,branch,record,contact,messages,recipient,reply


def test_combined_history_and_customer_context(client,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    response=client.get(BASE+f'/conversations/whatsapp/{contact.id}',headers=headers)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['conversation']['name']=='Synthetic Customer'
    assert data['conversation']['entityId']==record.id
    assert {e['channel'] for e in data['events']}=={'whatsapp','email'}
    assert any(e['body']=='Customer email response' for e in data['events'])
    assert [e['createdAt'] for e in data['events']]==sorted(e['createdAt'] for e in data['events'])
    rows=client.get(BASE+'/inbox',headers=headers).json()['items']
    assert next(r for r in rows if r['kind']=='whatsapp')['unread']==3
    assert len(rows)==1  # Email and WhatsApp for a linked customer share one thread.


def test_read_positions_snoozing_and_ownership_are_persisted(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    path=BASE+f'/conversations/whatsapp/{contact.id}'
    result=client.post(path+'/read',headers=headers,json={'whatsappReadId':messages[-1].id,'emailReadId':reply.id})
    assert result.status_code==200,result.text
    assert client.post(path+'/read',headers=headers,json={'whatsappReadId':messages[0].id}).status_code==200
    row=db.query(ConversationReading).filter_by(user_id=actor.id,kind='whatsapp',record_id=contact.id).one()
    assert row.whatsapp_read_id==messages[-1].id
    until=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
    assert client.post(path+'/snooze',headers=headers,json={'until':until}).status_code==200
    assert client.get(path,headers=headers).json()['conversation']['snoozedUntil']
    assert client.post(path+'/snooze',headers=headers,json={'until':None}).status_code==200
    result=client.put(path+'/workflow',headers=headers,json={'assignedUserId':actor.id,'handoverNote':'Synthetic handover','status':'resolved'})
    assert result.status_code==200,result.text
    workflow=db.query(ConversationWorkflow).one()
    assert workflow.assigned_user_id==actor.id and workflow.status=='resolved'


def test_reading_and_snooze_validation(client,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    path=BASE+f'/conversations/whatsapp/{contact.id}'
    assert client.post(path+'/read',headers=headers,json={'whatsappReadId':999999}).status_code==422
    assert client.post(path+'/snooze',headers=headers,json={'until':'2020-01-01T10:00:00Z'}).status_code==422
    assert client.post(path+'/snooze',headers=headers,json={'until':'2030-01-01T10:00:00'}).status_code==422
    assert client.put(path+'/workflow',headers=headers,json={'assignedUserId':999999}).status_code==403


def test_other_branch_and_company_cannot_leak_customer_history(client,db,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    other=Branch(company_id=1,name='Other engagement branch',is_active=True);db.add(other);db.commit()
    other_headers={**headers,'X-Suite-Branch':str(other.id)}
    assert client.get(BASE+f'/conversations/whatsapp/{contact.id}',headers=other_headers).status_code==404
    assert client.get(BASE+'/inbox',headers=other_headers).json()['items']==[]
    company=Company(name='Other engagement company');db.add(company);db.flush()
    foreign=WhatsAppContact(organization_id=company.id,recipient='919876543211',name='Private foreign customer',consent='unknown');db.add(foreign);db.commit()
    assert client.get(BASE+f'/conversations/whatsapp/{foreign.id}',headers=headers).status_code==404


def test_search_record_picker_and_delivery_evidence(client,customer_thread):
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    result=client.get(BASE+'/records',headers=headers,params={'kind':'contact','search':'Synthetic'})
    assert result.status_code==200,result.text
    assert result.json()['items'][0]['id']==record.id
    assert client.get(BASE+'/inbox',headers=headers,params={'search':'does-not-exist'}).json()['items']==[]
    result=client.get(BASE+f'/delivery/whatsapp/{messages[1].id}',headers=headers)
    assert result.status_code==200 and result.json()['canRetry'] is False
    assert result.json()['events'][0]['status']=='recorded'


def test_email_only_viewer_cannot_read_whatsapp_or_manage_ownership(client,db,customer_thread):
    from tests.communication_test_utils import communication_headers
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    viewer=communication_headers(client,db,email='engagement-viewer@example.com',permissions=['communication_view'])
    viewer={**viewer,'X-Suite-Branch':str(branch.id)}
    result=client.get(BASE+f'/conversations/customer/{recipient.id}',headers=viewer)
    assert result.status_code==200,result.text
    assert {event['channel'] for event in result.json()['events']}=={'email'}
    assert client.get(BASE+f'/conversations/whatsapp/{contact.id}',headers=viewer).status_code==403
    assert client.put(BASE+f'/conversations/customer/{recipient.id}/workflow',headers=viewer,json={'status':'resolved'}).status_code==403


def test_guided_webform_mapping_uses_customer_field_keys(client,db,customer_thread):
    headers=customer_thread[0]
    response=client.post('/api/v1/communication/webforms',headers=headers,json={'name':'Mapped customer enquiry','target_module':'lead','public_slug':'engagement-map-test','fields_json':[{'key':'person_name','label':'Your name','type':'text','required':True},{'key':'business','label':'Company','type':'text'},{'key':'enquiry','label':'Message','type':'textarea'}],'mapping_json':{'first_name':'person_name','company_name':'business','message':'enquiry'}})
    assert response.status_code==201,response.text
    response=client.post('/api/v1/public/webforms/engagement-map-test/submit',json={'values':{'person_name':'Synthetic','business':'Sample Company','enquiry':'Please contact me about a service.'}})
    assert response.status_code==201,response.text
    from app.apps.crm.models import CRMLead
    row=db.get(CRMLead,response.json()['created_record_id'])
    assert row.first_name=='Synthetic' and row.company_name=='Sample Company'
    assert row.notes=='Please contact me about a service.'


def test_campaign_channel_and_schedule_are_explicit(client,db,customer_thread,monkeypatch):
    from app.apps.communication.models import CommunicationEmailTemplate
    from unittest.mock import Mock
    headers,actor,branch,record,contact,messages,recipient,reply=customer_thread
    template=client.post('/api/v1/communication/email-templates',headers=headers,json={'name':'Schedule template','subject':'Hi {{name}}','body_text':'Hello {{name}}','module_name':'contact','active':True}).json()
    created=client.post('/api/v1/communication/campaigns',headers=headers,json={'name':'Explicit channel campaign','type':'whatsapp','template_id':template['id'],'segment_json':{'source':'contact','limit':1}})
    assert created.status_code==201,created.text
    identity=created.json()['id']
    send=Mock();monkeypatch.setattr('app.apps.communication.api.router.deliver_email',send)
    assert client.post(f'/api/v1/communication/campaigns/{identity}/send',headers=headers).status_code==409
    send.assert_not_called()
    assert client.post(f'/api/v1/communication/campaigns/{identity}/schedule',headers=headers,json={'scheduled_at':'2020-01-01T10:00:00Z'}).status_code==422
    assert client.post(f'/api/v1/communication/campaigns/{identity}/schedule',headers=headers,json={'scheduled_at':'2030-01-01T10:00:00'}).status_code==422
