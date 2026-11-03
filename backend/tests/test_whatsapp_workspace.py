from datetime import timedelta
from types import SimpleNamespace
import hashlib
import logging
import pytest
from fastapi import HTTPException
from app.api.v1.whatsapp_cloud import SendInput, disconnect, start_onboarding, complete_onboarding, CompleteOnboarding
from app.services import whatsapp_workspace as wa
from app.services.whatsapp import MetaError, GraphLogFilter
from app.shared.whatsapp_models import WhatsAppConnection, WhatsAppContact, WhatsAppMessage, WhatsAppReceipt
from app.models.company import Company
from app.core.config import settings


@pytest.fixture
def workspace(db, monkeypatch):
    from app.models.user import User
    companies = [Company(name='WhatsApp Test A'), Company(name='WhatsApp Test B')]
    db.add_all(companies); db.flush()
    user = User(email='wa-test@example.invalid', hashed_password='unused', is_superuser=True, is_active=True)
    db.add(user); db.flush(); user.organization_id=companies[0].id
    rows = [WhatsAppConnection(organization_id=c.id, waba_id=str(10000+i), phone_number_id=str(20000+i), routing_key=str(20000+i), source='manual', token_ciphertext=wa.protect('test-only-token'), status='connected', subscribed=True) for i,c in enumerate(companies)]
    db.add_all(rows); db.commit()
    monkeypatch.setattr(settings,'CRM_WHATSAPP_ORGANIZATION_ID',0)
    return db, user, companies, rows


def incoming(connection, message_id='wamid.in', text='Hello', **extra):
    value = {'metadata':{'phone_number_id':connection.phone_number_id}, 'messages':[{'id':message_id,'from':'919876543210','timestamp':str(int(wa.now().timestamp())), 'type':'text','text':{'body':text}}]}
    value.update(extra)
    return {'object':'whatsapp_business_account','entry':[{'id':connection.waba_id,'changes':[{'value':value}]}]}


def test_signed_event_routing_dedup_and_stop(workspace):
    db, user, companies, connections = workspace
    wa.ingest(db,incoming(connections[1], text='STOP')); db.commit()
    contact = db.query(WhatsAppContact).filter_by(organization_id=companies[1].id).one()
    assert contact.consent == 'opted_out' and wa.service_window(contact)
    assert db.query(WhatsAppContact).filter_by(organization_id=companies[0].id).count() == 0
    contact.consent = 'opted_in'; db.commit()
    wa.ingest(db,incoming(connections[1], text='STOP')); db.commit()
    assert contact.consent == 'opted_in'
    assert db.query(WhatsAppMessage).filter_by(connection_id=connections[1].id).count() == 1
    wrong = incoming(connections[1], 'wamid.wrong'); wrong['entry'][0]['id'] = connections[0].waba_id
    wa.ingest(db,wrong); db.commit()
    assert db.query(WhatsAppMessage).filter_by(provider_message_id='wamid.wrong').count() == 0
    with pytest.raises(HTTPException) as error: wa.contact_access(db,user,contact)
    assert error.value.status_code == 404


def test_existing_conversation_customer_mapping_is_branch_safe_and_idempotent(workspace):
    from app.models.company import Branch
    from app.apps.crm.models import CRMContact
    from app.branches.models import BranchOwnership
    from app.branches.service import BranchContext
    from app.branches.boundary import install
    from app.api.v1.whatsapp_cloud import match_customers
    db,user,companies,connections=workspace
    branch=Branch(name='Match branch',company_id=companies[0].id);db.add(branch);db.flush()
    record=CRMContact(organization_id=companies[0].id,branch_id=branch.id,first_name='Matched',full_name='Matched Customer',phone='9876543210',phone_country_code='91')
    db.add(record);db.flush()
    db.add(BranchOwnership(resource_table='crm_contacts',resource_key=str(record.id),company_id=companies[0].id,branch_id=branch.id,source='test'))
    connections[0].inbound_branch_id=branch.id;db.commit()
    wa.ingest(db,incoming(connections[0]));db.commit()
    contact=db.query(WhatsAppContact).filter_by(organization_id=companies[0].id).one()
    contact.entity_id=None;contact.entity_type=None;db.commit()
    company,branch_id=companies[0].id,branch.id
    cleanup=install(db,user,BranchContext(company,branch_id,frozenset({branch_id}),frozenset({branch_id}),True,True,True))
    try:
        result=match_customers(after=0,recipient_after=0,db=db,user=user)
        assert result['matched']==1 and result['nextAfter'] is None
        assert contact.entity_id==record.id
        assert match_customers(after=0,recipient_after=0,db=db,user=user)['matched']==0
    finally:cleanup()


def test_durable_send_idempotency_and_receipt_race(workspace, monkeypatch):
    db,user,companies,connections = workspace
    wa.ingest(db,incoming(connections[0])); db.commit()
    calls=[]
    def send(self, **kwargs):
        reserved=db.query(WhatsAppMessage).filter_by(idempotency_key='request-id-0001').one()
        assert reserved.status == 'submitting'
        calls.append(kwargs)
        db.add(WhatsAppReceipt(organization_id=companies[0].id,connection_id=connections[0].id,provider_message_id='wamid.out',status='delivered')); db.commit()
        return 'accepted','wamid.out'
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',send)
    data=SendInput(requestId='request-id-0001',to='919876543210',body='Reply')
    row=wa.send_message(db,user,data)
    assert row.status == 'delivered'
    assert wa.send_message(db,user,data).id == row.id and len(calls)==1
    with pytest.raises(HTTPException) as error: wa.send_message(db,user,data.model_copy(update={'body':'Different'}))
    assert error.value.status_code==409
    wa.update_status(db,row,'read'); wa.update_status(db,row,'sent'); wa.update_status(db,row,'failed','123')
    assert row.status=='read'


def test_uncertain_response_never_resends(workspace, monkeypatch):
    db,user,_,connections=workspace
    wa.ingest(db,incoming(connections[0])); db.commit()
    calls=[]
    def send(*args,**kwargs):
        calls.append(1); raise MetaError('timeout',uncertain=True)
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',send)
    data=SendInput(requestId='request-uncertain',to='919876543210',body='Reply')
    assert wa.send_message(db,user,data).status=='reconciliation_required'
    assert wa.send_message(db,user,data).status=='reconciliation_required' and len(calls)==1


def test_window_optout_and_template_consent_enforced(workspace, monkeypatch):
    db,user,companies,_=workspace
    contact=wa.contact_for(db,companies[0].id,'919876543210'); db.commit()
    data=SendInput(requestId='request-blocked',to=contact.recipient,body='Hello')
    with pytest.raises(HTTPException): wa.send_message(db,user,data)
    contact.last_inbound_at=wa.now()-timedelta(hours=25); db.commit()
    assert not wa.service_window(contact)
    data.template={'name':'hello_world','language':{'code':'en_US'}}
    with pytest.raises(HTTPException) as error: wa.send_message(db,user,data)
    assert 'opt-in' in error.value.detail
    contact.last_inbound_at=wa.now(); contact.consent='opted_out'; db.commit()
    with pytest.raises(HTTPException) as error: wa.send_message(db,user,data)
    assert 'opted out' in error.value.detail
    assert db.query(WhatsAppMessage).count()==0


def test_disconnect_never_unsubscribes_shared_waba(workspace, monkeypatch):
    db,user,_,connections=workspace
    def forbidden(*args,**kwargs): raise AssertionError('Must not remove a shared WABA subscription')
    monkeypatch.setattr(wa.WhatsAppGraph,'request',forbidden)
    result=disconnect(db,user)
    assert result['status']=='disconnected' and not result['providerUnsubscribed']
    assert connections[0].token_ciphertext is None and connections[0].routing_key is None
    wa.ingest(db,incoming(connections[0])); db.commit()
    assert db.query(WhatsAppMessage).count()==0
    with pytest.raises(HTTPException): wa.live_connection(db,user.organization_id)


def test_onboarding_state_bound_and_one_use(workspace, monkeypatch):
    db,user,companies,_=workspace
    monkeypatch.setattr(settings,'CRM_WHATSAPP_APP_ID','123456')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_EMBEDDED_CONFIG_ID','789012')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_APP_SECRET','test-secret')
    state=start_onboarding(db,user)['state']
    data=CompleteOnboarding(state=state,code='test-code',wabaId='10000',phoneNumberId='20000')
    other=SimpleNamespace(id=user.id,organization_id=companies[1].id,is_superuser=True)
    with pytest.raises(HTTPException) as error: complete_onboarding(data,db,other)
    assert error.value.status_code==409
    calls=[]
    def exchange(*args,**kwargs): calls.append(1); raise MetaError('exchange failed')
    monkeypatch.setattr(wa.WhatsAppGraph,'request',exchange)
    with pytest.raises(HTTPException): complete_onboarding(data,db,user)
    with pytest.raises(HTTPException) as error: complete_onboarding(data,db,user)
    assert error.value.status_code==409 and len(calls)==1


def test_credentials_not_serialized_or_logged(workspace):
    _,_,_,connections=workspace
    assert 'token' not in str(wa.connection_data(connections[0])).lower()
    record=logging.LogRecord('httpx',20,'',1,'HTTP %s %s',('GET','https://graph.facebook.com/v26.0/oauth/access_token?client_secret=secret&code=code'),None)
    GraphLogFilter().filter(record)
    assert 'secret' not in record.getMessage() and '?code' not in record.getMessage()


def test_linked_conversation_respects_crm_record_visibility(workspace):
    from app.apps.crm.models import CRMLead
    db,user,companies,_=workspace
    lead=CRMLead(organization_id=companies[0].id,first_name='Private lead',full_name='Private lead',owner_user_id=None,created_by_user_id=None)
    db.add(lead); db.flush()
    contact=wa.contact_for(db,companies[0].id,'919876543210')
    contact.entity_type,contact.entity_id='lead',lead.id
    db.commit()
    user.is_superuser=False
    with pytest.raises(HTTPException) as error: wa.contact_access(db,user,contact)
    assert error.value.status_code==403
    user.is_superuser=True
    wa.contact_access(db,user,contact)


def test_connection_credentials_cannot_fall_back_after_deployment_change(workspace,monkeypatch):
    _,_,companies,connections=workspace
    row=connections[0]; row.source='environment'
    monkeypatch.setattr(settings,'CRM_WHATSAPP_PROVIDER','meta')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_ORGANIZATION_ID',companies[0].id)
    monkeypatch.setattr(settings,'CRM_WHATSAPP_PHONE_NUMBER_ID','different')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_BUSINESS_ACCOUNT_ID',row.waba_id)
    monkeypatch.setattr(settings,'CRM_WHATSAPP_ACCESS_TOKEN','other-deployment-secret')
    with pytest.raises(HTTPException) as error: wa.connection_token(row)
    assert error.value.status_code==409


def test_account_api_auth_and_secret_serialization(workspace):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.deps import get_current_user,get_db
    from app.api.v1.whatsapp_cloud import router
    db,user,_,_=workspace
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    client=TestClient(app)
    assert client.get('/integrations/whatsapp/status').status_code==403
    app.dependency_overrides[get_current_user]=lambda:user
    result=client.get('/integrations/whatsapp/status')
    assert result.status_code==200 and result.json()['configured']
    assert 'token' not in result.text.lower() and 'ciphertext' not in result.text.lower()
    user.is_superuser=False
    assert client.post('/integrations/whatsapp/connection/check').status_code==403


def test_branch_guard_keeps_configuration_shared_and_conversations_private(workspace):
    from app.models.company import Branch
    from app.branches.service import BranchContext
    from app.branches.boundary import install
    db,user,companies,connections=workspace
    branches=[Branch(name='WhatsApp inbox A',company_id=companies[0].id),Branch(name='WhatsApp inbox B',company_id=companies[0].id)]
    db.add_all(branches);db.flush()
    connections[0].inbound_branch_id=branches[0].id;db.commit()
    wa.ingest(db,incoming(connections[0]));db.commit()
    contact=db.query(WhatsAppContact).one()
    assert wa.branch_ownership(db,contact)==branches[0].id
    message=db.query(WhatsAppMessage).one()
    assert wa.branch_ownership(db,message)==branches[0].id
    ids=[branch.id for branch in branches];company=companies[0].id
    for index,expected in [(1,0),(0,1)]:
        context=BranchContext(company,ids[index],frozenset(ids),frozenset(ids),True,True,True)
        cleanup=install(db,user,context)
        try:
            assert wa.connection_for(db,company) is not None
            assert db.query(WhatsAppContact).count()==expected
            assert db.query(WhatsAppMessage).count()==expected
            from app.api.v1.whatsapp_cloud import conversations
            result=conversations(before=None,limit=50,db=db,user=user,search='',linked=None)
            assert len(result['items'])==expected
            if expected: assert result['items'][0]['lastMessage']['body']=='Hello'
        finally:cleanup()


def test_account_bootstrap_does_not_require_a_sales_destination(workspace,monkeypatch):
    from app.branches.service import BranchContext
    from app.branches.boundary import install
    db,user,companies,connections=workspace
    db.delete(connections[0]);db.commit()
    monkeypatch.setattr(settings,'CRM_WHATSAPP_PROVIDER','meta')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_ORGANIZATION_ID',companies[0].id)
    monkeypatch.setattr(settings,'CRM_WHATSAPP_PHONE_NUMBER_ID','12345678')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_BUSINESS_ACCOUNT_ID','87654321')
    monkeypatch.setattr(settings,'CRM_WHATSAPP_ACCESS_TOKEN','test-only-token')
    cleanup=install(db,user,BranchContext(companies[0].id,None,frozenset(),frozenset(),True,True,True))
    try:
        assert wa.connection_for(db,companies[0].id,bootstrap=True).source=='environment'
        db.commit()
    finally:cleanup()


def test_linked_send_finishes_after_meta_acceptance_with_branch_guard(workspace,monkeypatch):
    from app.models.company import Branch
    from app.apps.crm.models import CRMLead,CRMMessage
    from app.branches.models import BranchOwnership
    from app.branches.service import BranchContext
    from app.branches.boundary import install
    db,user,companies,connections=workspace
    branch=Branch(name='Send regression',company_id=companies[0].id);db.add(branch);db.flush()
    lead=CRMLead(organization_id=companies[0].id,first_name='Test',full_name='Test',branch_id=branch.id)
    db.add(lead);db.flush()
    db.add(BranchOwnership(resource_table='crm_leads',resource_key=str(lead.id),company_id=companies[0].id,branch_id=branch.id,source='test'))
    connections[0].inbound_branch_id=branch.id;db.commit()
    wa.ingest(db,incoming(connections[0]));db.commit()
    contact=db.query(WhatsAppContact).one();contact.entity_type,contact.entity_id='lead',lead.id;db.commit()
    company,branch_id,lead_id=companies[0].id,branch.id,lead.id
    monkeypatch.setattr(wa.MetaWhatsAppProvider,'send',lambda *a,**kw:('accepted','wamid.branch-regression'))
    cleanup=install(db,user,BranchContext(company,branch_id,frozenset({branch_id}),frozenset({branch_id}),True,True,True))
    try:
        row=wa.send_message(db,user,SendInput(requestId='branch-send-regression',to='919876543210',body='Reply',entityType='lead',entityId=lead_id))
        assert row.status=='accepted' and row.provider_message_id=='wamid.branch-regression'
        assert db.get(CRMMessage,row.crm_message_id).status=='accepted'
        assert wa.branch_ownership(db,row)==branch_id
    finally:cleanup()


def test_send_lookup_and_history_never_cross_company(workspace):
    from app.api.v1.whatsapp_cloud import message_by_request,outbound_messages
    db,user,companies,connections=workspace
    wa.ingest(db,incoming(connections[0]));db.commit()
    contact=db.query(WhatsAppContact).one()
    row=WhatsAppMessage(organization_id=companies[0].id,connection_id=connections[0].id,contact_id=contact.id,direction='outbound',body='Test',status='accepted',idempotency_key='lookup-test-request')
    db.add(row);db.commit()
    assert message_by_request('lookup-test-request',db,user)['status']=='accepted'
    assert len(outbound_messages(None,50,db,user)['items'])==1
    other=SimpleNamespace(id=user.id,organization_id=companies[1].id,is_superuser=True)
    with pytest.raises(HTTPException) as error:message_by_request('lookup-test-request',db,other)
    assert error.value.status_code==404
    assert outbound_messages(None,50,db,other)['items']==[]


def test_profile_photo_validates_before_meta_and_returns_provider_profile(workspace,monkeypatch):
    from io import BytesIO
    from PIL import Image
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.deps import get_current_user,get_db
    from app.api.v1.whatsapp_cloud import router
    db,user,_,_=workspace
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:user
    client=TestClient(app);calls=[]
    monkeypatch.setattr(wa.WhatsAppGraph,'upload_profile_jpeg',lambda self,data:calls.append('upload') or 'private-handle')
    def graph(self,method,path,**kwargs):
        calls.append(method)
        return {'success':True} if method=='POST' else {'data':[{'profile_picture_url':'https://example.invalid/photo.jpg'}]}
    monkeypatch.setattr(wa.WhatsAppGraph,'request',graph)
    response=client.post('/integrations/whatsapp/profile/picture',files={'file':('fake.jpg',b'not-an-image','image/jpeg')})
    assert response.status_code==422 and not calls
    photo=BytesIO();Image.new('RGB',(192,192),'white').save(photo,format='JPEG')
    response=client.post('/integrations/whatsapp/profile/picture',files={'file':('photo.jpg',photo.getvalue(),'image/jpeg')})
    assert response.status_code==200 and response.json()['profile_picture_url'].endswith('photo.jpg')
    assert calls==['upload','POST','GET'] and 'private-handle' not in response.text


def test_upload_session_cannot_redirect_credentials(monkeypatch):
    from app.services.whatsapp import WhatsAppGraph
    monkeypatch.setattr(settings,'CRM_WHATSAPP_APP_ID','123456')
    monkeypatch.setattr(WhatsAppGraph,'request',lambda *a,**kw:{'id':'https://evil.invalid/steal'})
    with pytest.raises(MetaError):WhatsAppGraph('secret-token').upload_profile_jpeg(b'jpeg')


def test_conversation_search_and_previews_respect_company_and_link_filter(workspace):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.deps import get_current_user,get_db
    from app.api.v1.whatsapp_cloud import router
    db,user,companies,connections=workspace
    wa.ingest(db,incoming(connections[0],text='Latest customer message'))
    wa.ingest(db,incoming(connections[1],message_id='other-company',text='Private other company'))
    db.flush()
    own=db.query(WhatsAppContact).filter_by(organization_id=companies[0].id).one();own.name='Alice Operations'
    other=db.query(WhatsAppContact).filter_by(organization_id=companies[1].id).one();other.name='Alice Private'
    db.add(WhatsAppContact(organization_id=companies[0].id,recipient='918888888888',name='Bob',consent='unknown'))
    db.commit()
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:user
    client=TestClient(app)
    result=client.get('/integrations/whatsapp/conversations',params={'search':'Alice','linked':'false'}).json()
    assert len(result['items'])==1
    assert result['items'][0]['name']=='Alice Operations'
    assert result['items'][0]['lastMessage']['body']=='Latest customer message'
    assert result['items'][0]['lastMessage']['direction']=='inbound'
    assert not client.get('/integrations/whatsapp/conversations',params={'search':'%'}).json()['items']
    assert len(client.get('/integrations/whatsapp/conversations',params={'search':'+91 9876543210'}).json()['items'])==1
    assert not client.get('/integrations/whatsapp/conversations',params={'linked':'true'}).json()['items']
