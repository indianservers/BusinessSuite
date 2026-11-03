"""Disposable, provider-isolated fixtures for Communication Center browser QA."""
import os,sys,secrets,json,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
temporary=tempfile.TemporaryDirectory(prefix='businesssuite-center-qa-')
password=secrets.token_urlsafe(18)
os.environ.update(ENVIRONMENT='test',DATABASE_URL='sqlite:///'+str(Path(temporary.name)/'qa.db'),SECRET_KEY=secrets.token_urlsafe(48),REFRESH_SECRET_KEY=secrets.token_urlsafe(48),INSTALLED_APPS='hrms,crm,project_management,srm,fam',STORAGE_BACKEND='local',UPLOAD_DIR=str(Path(temporary.name)/'uploads'),OPENAI_API_KEY='',ANTHROPIC_API_KEY='',GEMINI_API_KEY='',MAIL_SERVER='',MAIL_USERNAME='',MAIL_PASSWORD='',SES_SMTP_USERNAME='',SES_SMTP_PASSWORD='',INTERN_HUB_SES_SMTP_USERNAME='',INTERN_HUB_SES_SMTP_PASSWORD='',INTERN_HUB_SES_ENABLED='false',CRM_WHATSAPP_ORGANIZATION_ID='0',CRM_WHATSAPP_ACCESS_TOKEN='',CRM_WHATSAPP_PHONE_NUMBER_ID='',CRM_WHATSAPP_BUSINESS_ACCOUNT_ID='',COMMUNICATION_EMAIL_PROVIDER='stub',EMAIL_PROVIDER='smtp')
from app.main import app
from app.db.base import Base
from app.db.session import engine,SessionLocal
from app.core.security import get_password_hash
from app.models.company import Company,Branch
from app.models.user import User,Role
from app.common.models import CommonPerson
from app.access.models import AccessMembership
from app.branches.models import BranchOwnership
from app.apps.crm.models import CRMContact,CRMLead
from app.shared.whatsapp_models import WhatsAppConnection,WhatsAppContact,WhatsAppMessage,WhatsAppReceipt
from app.services.whatsapp_workspace import protect
from app.services.whatsapp import WhatsAppGraph,MetaWhatsAppProvider
from app.apps.communication.models import CommunicationEmailTemplate,CommunicationEmailMessage,CommunicationEmailAttachment,CommunicationWebform,CommunicationCampaign,CommunicationConsent,CommunicationTimelineEvent
from app.apps.communication.customer_models import CustomerRecipient,CustomerDelivery,CustomerEmailReply
from uuid import uuid4
from sqlalchemy import event
@event.listens_for(engine,'connect')
def configure(connection,_):
    cursor=connection.cursor();cursor.execute('PRAGMA journal_mode=WAL');cursor.execute('PRAGMA busy_timeout=10000');cursor.close()
Base.metadata.create_all(engine)
templates=[{'id':'qa-template-1','name':'service_update','language':'en_US','status':'APPROVED','category':'UTILITY','components':[{'type':'BODY','text':'Hello {{1}}, your service request {{2}} is now {{3}}.'}]},{'id':'qa-template-2','name':'appointment_confirmation','language':'en_US','status':'APPROVED','category':'UTILITY','components':[{'type':'BODY','text':'Hello {{1}}, your appointment is confirmed for {{2}}.'}]},{'id':'qa-template-3','name':'offer_update','language':'en_US','status':'REJECTED','category':'MARKETING','components':[{'type':'BODY','text':'Our current offer is available.'}]}]
def graph_request(self,method,path,**kwargs):
    if path.endswith('/message_templates'):
        if method=='GET': return {'data':templates}
        row=kwargs.get('payload') or {};templates.append({**row,'id':'qa-'+uuid4().hex,'status':'PENDING'});return {'id':templates[-1]['id'],'status':'PENDING'}
    if path.endswith('/whatsapp_business_profile'): return {'data':[{'about':'Disposable QA account','description':'Local browser testing only','email':'qa@example.com','websites':[],'vertical':'PROF_SERVICES'}]}
    raise RuntimeError('Provider call disabled in local Communication Center QA')
WhatsAppGraph.request=graph_request
MetaWhatsAppProvider.send=lambda self,**kwargs:('accepted','wamid.qa.'+uuid4().hex)
now=datetime.now(timezone.utc)
with SessionLocal() as db:
    company=Company(name='Communication Center QA',is_active=True);db.add(company);db.flush()
    branch=Branch(company_id=company.id,name='QA Main',code='QA',is_active=True);db.add(branch);db.flush()
    role=Role(name='super_admin',description='Local QA only',is_system=True);db.add(role);db.flush()
    users=[User(email=f'center-qa{i}@example.com',hashed_password=get_password_hash(password),is_superuser=True,is_active=True,role_id=role.id) for i in range(2)]
    db.add_all(users);db.flush()
    for i,user in enumerate(users):
        db.add(CommonPerson(user_id=user.id,primary_email=user.email,display_name=['QA Operator','QA Colleague'][i],organization_id=company.id))
        db.add(AccessMembership(user_id=user.id,company_id=company.id,active=True,is_admin=True))
    record=CRMContact(organization_id=company.id,branch_id=branch.id,first_name='Asha',last_name='Rao',full_name='Asha Rao',company_name='Sample Customer Ltd',email='asha@example.com',phone='9876543210',phone_country_code='91',owner_user_id=users[0].id)
    lead=CRMLead(organization_id=company.id,branch_id=branch.id,first_name='Demo',full_name='Demo Lead',email='demo@example.com',phone='9876543211',phone_country_code='91')
    duplicate=CRMContact(organization_id=company.id,branch_id=branch.id,first_name='Duplicate',full_name='Duplicate Customer',phone='9876543211',phone_country_code='91')
    db.add_all([record,lead,duplicate]);db.flush()
    connection=WhatsAppConnection(organization_id=company.id,waba_id='99001',phone_number_id='99002',routing_key='99002',inbound_branch_id=branch.id,display_number='+91 90000 00000',business_name='Communication Center QA',token_ciphertext=protect('local-qa-only'),source='manual',status='connected',subscribed=True)
    contacts=[WhatsAppContact(organization_id=company.id,recipient='919876543210',name='Asha on WhatsApp',entity_type='contact',entity_id=record.id,consent='opted_in',consent_source='Synthetic QA consent',last_inbound_at=now-timedelta(minutes=15),last_message_at=now),WhatsAppContact(organization_id=company.id,recipient='919876543211',name='Duplicate number review',consent='unknown',last_inbound_at=now-timedelta(minutes=20),last_message_at=now-timedelta(minutes=20)),WhatsAppContact(organization_id=company.id,recipient='919876543212',name='New customer',consent='unknown',last_inbound_at=now-timedelta(minutes=30),last_message_at=now-timedelta(minutes=30))]
    db.add_all([connection,*contacts]);db.flush()
    messages=[]
    for index,(direction,body,minutes) in enumerate([('inbound','Hi, can you share the status of service request QA-104?',25),('outbound','Hello Asha, your service request is in progress. We will update you here.',21),('inbound','Thank you. Please also email the update to me.',15)]):
        message=WhatsAppMessage(organization_id=company.id,connection_id=connection.id,contact_id=contacts[0].id,direction=direction,kind='text',body=body,status='read' if direction=='outbound' else 'received',provider_message_id=f'wamid.qa.seed.{index}',created_at=now-timedelta(minutes=minutes));db.add(message);messages.append(message)
    for contact in contacts[1:]:
        incoming=WhatsAppMessage(organization_id=company.id,connection_id=connection.id,contact_id=contact.id,direction='inbound',kind='text',body='Hello, I would like to ask about your services.',status='received',created_at=contact.last_inbound_at)
        db.add(incoming);messages.append(incoming)
    for status,minutes in [('sent',20),('delivered',19),('read',18)]: db.add(WhatsAppReceipt(organization_id=company.id,connection_id=connection.id,provider_message_id='wamid.qa.seed.1',status=status,created_at=now-timedelta(minutes=minutes)))
    recipient=CustomerRecipient(organization_id=company.id,branch_id=branch.id,crm_contact_id=record.id,name='Asha Rao',email=record.email,phone='+919876543210',preferences={'email.transactional':True},created_by=users[0].id)
    template=CommunicationEmailTemplate(organization_id=company.id,name='Service request update',subject='Update for {{name}}',body_text='Hello {{name}}, your request is being reviewed by our team.',module_name='contact',active=True,created_by=users[0].id)
    db.add_all([recipient,template]);db.flush()
    delivery=CustomerDelivery(organization_id=company.id,branch_id=branch.id,recipient_id=recipient.id,event_key='qa-event',source_type='contact',source_id=record.id,channel='email',purpose='transactional',subject='Your service update',body='Hello Asha, the requested update is ready.',status='accepted',due_at=now-timedelta(minutes=10),created_at=now-timedelta(minutes=10),created_by=users[0].id)
    db.add(delivery);db.flush()
    reply=CustomerEmailReply(organization_id=company.id,branch_id=branch.id,recipient_id=recipient.id,delivery_id=delivery.id,provider_event_id='qa-reply',subject='Re: Your service update',body='Thanks for the email. Please let me know when the request is complete.',received_at=now-timedelta(minutes=4))
    campaign=CommunicationCampaign(organization_id=company.id,name='QA Service Follow-up',type='email',template_id=template.id,segment_json={'source':'contact','limit':10},status='draft',created_by=users[0].id)
    email=CommunicationEmailMessage(organization_id=company.id,related_record_type='contact',related_record_id=record.id,to_email=record.email,subject='Service request QA-104',body='Your service request is in progress.',status='sent',sent_by=users[0].id,created_at=now-timedelta(minutes=10))
    form=CommunicationWebform(organization_id=company.id,name='QA Customer enquiry',target_module='lead',public_slug='qa-customer-enquiry',fields_json=[{'key':'first_name','label':'First name','type':'text','required':True},{'key':'email','label':'Email','type':'email','required':True}],mapping_json={'first_name':'first_name','email':'email'},active=True)
    db.add_all([reply,campaign,email,form]);db.flush()
    db.add(CommunicationEmailAttachment(organization_id=company.id,message_id=email.id,file_name='QA_Service_Guide.pdf',mime_type='application/pdf',size_bytes=2048))
    db.add(CommunicationTimelineEvent(organization_id=company.id,record_type='contact',record_id=record.id,channel='email',event_type='sent',subject=email.subject,summary='Synthetic service update email recorded',actor_user_id=users[0].id))
    for row in [record,lead,duplicate,*contacts,*messages,recipient,delivery,reply,template,campaign,email,form]:
        db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=company.id,branch_id=branch.id,source='local-qa'))
    from app.models.security_boundary import SecurityResourceOwnership
    db.add(SecurityResourceOwnership(resource_table=campaign.__tablename__,resource_id=campaign.id,company_id=company.id))
    qa_session={'url':'http://127.0.0.1:5199','email':users[0].email,'password':password,'contactId':contacts[0].id,'crmContactId':record.id,'campaignId':campaign.id}
    db.commit()
(root/'.local').mkdir(exist_ok=True)
(root/'.local/communication-center-qa-session.json').write_text(json.dumps(qa_session),encoding='utf8')
print('Provider-isolated Communication Center QA API ready on port 1548',flush=True)
import uvicorn
uvicorn.run(app,host='127.0.0.1',port=1548,log_level='warning')
