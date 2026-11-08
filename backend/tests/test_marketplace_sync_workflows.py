import json
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs
from datetime import timedelta
import pytest
from tests.test_power_apps import actors
from tests.test_marketplace_provider_authorization import CASES
from app.apps.power_apps.integrations import adapters
from app.apps.power_apps.integrations.models import Connection
from app.apps.power_apps.integrations.marketplace_sync import dispatch_due
from app.shared.models import ServicePolicy
from app.shared.import_models import ImportBatch
from app.apps.crm.models import CRMContact,CRMLead,CRMActivity
from app.models.user import User


def fixture_page(provider,ident='provider-1'):
    person={'id':ident,'first_name':'QA','last_name':'Person','name':'QA Person','email':provider+'@example.com'}
    if provider=='facebook_lead_ads':return {'data':[{'id':ident,'field_data':[{'name':'full_name','values':['QA Person']},{'name':'email','values':[person['email']]}]}]}
    if provider=='linkedin_lead_forms':return {'elements':[{'id':ident,'formResponse':{'answers':[{'questionId':1,'answerDetails':{'textQuestionAnswer':{'answer':'QA Person'}}},{'questionId':2,'answerDetails':{'textQuestionAnswer':{'answer':person['email']}}}]}}]}
    if provider=='mailchimp':return {'members':[{**person,'email_address':person['email'],'merge_fields':{'FNAME':'QA','LNAME':'Person'}}],'total_items':1}
    if provider=='docusign':return {'envelopes':[{'envelopeId':ident,'emailSubject':'QA agreement','status':'completed'}]}
    if provider=='trello':return [{'id':ident,'name':'QA imported task','desc':'Imported task description'}]
    if provider=='zendesk':return {'tickets':[{'id':ident,'subject':'QA ticket','description':'Support case'}]}
    if provider=='activecampaign':return {'contacts':[{**person,'firstName':'QA','lastName':'Person'}],'meta':{'total':1}}
    if provider=='klaviyo':return {'data':[{'id':ident,'attributes':person}],'links':{}}
    if provider=='surfe':return {'status':'COMPLETED','people':[{**person,'externalID':ident,'firstName':'QA','lastName':'Person'}]}
    if provider=='apollo':return {'contacts':[person],'pagination':{'total_pages':1}}
    return {'responseData':{'data':[{'Contact':{**person,'emails':[{'email':person['email']}]}}]}}


def stamp(db,row,branch_id):
    from app.branches.models import BranchOwnership
    db.flush()
    db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=1,branch_id=branch_id,source='test-fixture'))


def create_connection(client,headers,case,writes=False):
    from app.apps.power_apps.integrations.providers import PROFILES
    provider,config,_,_,_=case
    auth=PROFILES[provider]['auth'];secrets={'username':'qa-key','password':'qa-token'} if auth=='basic' else {'access_token':'qa-token'}
    response=client.post('/api/v1/power-apps/integrations/connections',headers=headers,json={'connector_id':provider,'name':'QA '+provider,'auth_type':auth,'config':config,'secrets':secrets,'scopes':[],'writes_enabled':writes})
    assert response.status_code==201,response.text
    return response.json()['id']


@pytest.fixture
def native_actor(db,actors):
    user=db.query(User).filter_by(email='power-0@example.com').one();user.is_superuser=True;db.commit()
    return actors[0],user


@pytest.mark.parametrize('case',CASES,ids=[c[0] for c in CASES])
def test_provider_pages_commit_native_records_reuse_receipts_and_do_not_duplicate(client,db,native_actor,monkeypatch,case):
    headers,user=native_actor;provider=case[0]
    class Transport:
        def request(self,method,url,**kwargs):return SimpleNamespace(status=200,headers={},body=json.dumps(fixture_page(provider)).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    ident=create_connection(client,headers,case,writes=provider=='surfe')
    fields={'resource_id':'qa-resource','cursor':'0','from_date':'2026-01-01','owner':'(organization:urn:li:organization:123)','lead_type':'SPONSORED'}
    from app.apps.power_apps.integrations.registry import REGISTRY
    action=next(a for a in REGISTRY[provider].actions if a.id=='sync_page')
    source={k:v for k,v in fields.items() if k in action.input_schema['properties'] and k!='cursor'}
    constants={}
    if provider=='trello':
        from app.apps.project_management.models import PMSWorkspace,PMSProject
        from app.models.company import Branch
        branch=db.query(Branch).filter_by(company_id=1).first()
        workspace=PMSWorkspace(organization_id=1,name='QA workspace');db.add(workspace);stamp(db,workspace,branch.id)
        project=PMSProject(organization_id=1,workspace_id=workspace.id,project_key='QA',name='QA project',owner_user_id=user.id);db.add(project);stamp(db,project,branch.id);db.commit();constants={'project_id':str(project.id)}
    body={'connection_id':ident,'name':'QA sync','source':source,'constants':constants,'apply_new_records':True,'allow_credit_usage':provider=='surfe','mapping':{'full_name':'1','email':'2'} if provider=='linkedin_lead_forms' else {}}
    root='/api/v1/power-apps/integrations/sync'
    made=client.post(root+'/jobs',headers=headers,json=body)
    assert made.status_code==201,made.text
    assert client.post(root+'/jobs',headers=headers,json=body).status_code==409
    job=made.json()['id']
    run=client.post(f'{root}/jobs/{job}/run',headers=headers,json={})
    assert run.status_code==200,run.text
    assert run.json()['state']=='idle' and run.json()['changed']==1
    batch=db.get(ImportBatch,run.json()['batches'][0]);assert batch.status=='imported',batch.preview_json
    counts=batch.changes_json
    assert counts
    repeated=client.post(f'{root}/jobs/{job}/run',headers=headers,json={})
    assert repeated.status_code==200,repeated.text
    assert repeated.json()['changed']==0 and len(repeated.json()['batches'])==1
    stale=client.put(f'{root}/jobs/{job}',headers=headers,json={'expected_version':1,'enabled':False,'automatic':False})
    assert stale.status_code==409
    paused=client.put(f'{root}/jobs/{job}',headers=headers,json={'expected_version':repeated.json()['version'],'enabled':False,'automatic':False})
    assert paused.status_code==200
    assert client.post(f'{root}/jobs/{job}/run',headers=headers,json={}).status_code==409


def test_contact_native_workflow_confirmation_snapshot_and_idempotence(client,db,native_actor,monkeypatch):
    headers,user=native_actor
    from app.models.company import Branch
    branch=db.query(Branch).filter_by(company_id=1).first()
    contact=CRMContact(organization_id=1,branch_id=branch.id,owner_user_id=user.id,first_name='QA',last_name='Person',full_name='QA Person',email='native@example.com')
    db.add(contact);stamp(db,contact,branch.id);db.commit()
    case=next(c for c in CASES if c[0]=='activecampaign');ident=create_connection(client,headers,case,True)
    calls=[]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append(json.loads(kwargs['body']));return SimpleNamespace(status=200,headers={},body=b'{"contact":{"id":"remote-123"}}')
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    root='/api/v1/power-apps/integrations/sync/workflow'
    data={'connection_id':ident,'action_id':'upsert_contact','source_kind':'contacts','source_id':contact.id,'settings':{},'request_id':'native-workflow-123'}
    assert client.post(root+'/execute',headers=headers,json=data).status_code==422 and not calls
    preview=client.post(root+'/preview',headers=headers,json=data)
    assert preview.status_code==200,preview.text
    payload={**data,'expected_hash':preview.json()['source_hash'],'confirmed':True}
    done=client.post(root+'/execute',headers=headers,json=payload)
    assert done.status_code==200,done.text
    assert client.post(root+'/execute',headers=headers,json=payload).status_code==200
    assert len(calls)==1 and calls[0]['contact']['email']=='native@example.com'
    contact.full_name='User edited contact';db.commit()
    assert client.post(root+'/execute',headers=headers,json={**payload,'request_id':'changed-source-123'}).status_code==409
    assert len(calls)==1


def test_scheduler_imports_new_records_preserves_native_edits_and_recovers_failure(client,db,native_actor,monkeypatch):
    headers,user=native_actor
    calls=[]
    fail=[False]
    class Transport:
        def request(self,method,url,**kwargs):
            calls.append(url)
            if fail[0]:return SimpleNamespace(status=503,headers={},body=b'{}')
            return SimpleNamespace(status=200,headers={},body=json.dumps(fixture_page('activecampaign')).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='activecampaign'))
    root='/api/v1/power-apps/integrations/sync'
    response=client.post(root+'/jobs',headers=headers,json={'connection_id':ident,'name':'Scheduled contacts','automatic':True,'apply_new_records':True})
    assert response.status_code==201,response.text
    job=db.get(ServicePolicy,response.json()['id'])
    result=dispatch_due(db)
    assert result=={'completed_pages':1,'failed_jobs':0},result
    db.expire_all()
    contact=db.query(CRMContact).filter_by(email='activecampaign@example.com').one()
    contact.full_name='Preserved user edit';db.commit()
    job.values_json={**job.values_json,'next_at':'2020-01-01T00:00:00+00:00'};db.commit()
    assert dispatch_due(db)['completed_pages']==1
    db.refresh(contact)
    assert contact.full_name=='Preserved user edit'
    job.values_json={**job.values_json,'next_at':'2020-01-01T00:00:00+00:00'};db.commit();fail[0]=True
    assert dispatch_due(db)['failed_jobs']==1
    db.refresh(job)
    assert job.values_json['state']=='error' and job.values_json['lease'] is None
    fail[0]=False
    retry=client.post(f"{root}/jobs/{job.id}/run",headers=headers,json={})
    assert retry.status_code==200,retry.text
    assert retry.json()['state']=='idle'


@pytest.mark.parametrize('provider,action,kind,settings',[
 ('mailchimp','upsert_contact','contacts',{'list_id':'audience-1'}),
 ('activecampaign','upsert_contact','contacts',{}),
 ('klaviyo','upsert_contact','contacts',{}),
 ('apollo','upsert_contact','contacts',{}),
 ('cloudtalk','create_contact','contacts',{}),
 ('surfe','enrich_person','contacts',{'company_domain':'example.com'}),
 ('docusign','create_draft','contacts',{'account_id':'account-1','template_id':'template-1','role_name':'Signer'}),
 ('zendesk','create_ticket','activities',{}),
 ('trello','create_card','tasks',{'list_id':'list-1'}),
])
def test_all_supported_outgoing_native_workflows(client,db,native_actor,monkeypatch,provider,action,kind,settings):
    headers,user=native_actor
    from app.models.company import Branch
    branch=db.query(Branch).filter_by(company_id=1).first()
    if kind=='contacts':
        record=CRMContact(organization_id=1,branch_id=branch.id,owner_user_id=user.id,first_name='QA',last_name='Person',full_name='QA Person',email='workflow@example.com')
    elif kind=='activities':
        record=CRMActivity(organization_id=1,branch_id=branch.id,owner_user_id=user.id,subject='QA request',activity_type='Note',body='QA private request')
    else:
        from app.apps.project_management.models import PMSWorkspace,PMSProject,PMSTask
        workspace=PMSWorkspace(organization_id=1,name='QA workspace');db.add(workspace);stamp(db,workspace,branch.id)
        project=PMSProject(organization_id=1,workspace_id=workspace.id,project_key='WRITE',name='QA project',owner_user_id=user.id);db.add(project);stamp(db,project,branch.id)
        record=PMSTask(project_id=project.id,task_key='WRITE-1',title='QA native task',description='QA task body')
    db.add(record);stamp(db,record,branch.id);db.commit()
    ident=create_connection(client,headers,next(c for c in CASES if c[0]==provider),True)
    sent=[]
    class Transport:
        def request(self,method,url,**kwargs):
            sent.append((method,url,json.loads(kwargs['body'])))
            return SimpleNamespace(status=200,headers={},body=b'{"id":"remote-created"}')
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    root='/api/v1/power-apps/integrations/sync/workflow'
    data={'connection_id':ident,'action_id':action,'source_kind':kind,'source_id':record.id,'settings':settings,'request_id':'native-'+provider+'-123'}
    preview=client.post(root+'/preview',headers=headers,json=data)
    assert preview.status_code==200,preview.text
    payload={**data,'expected_hash':preview.json()['source_hash'],'confirmed':True}
    done=client.post(root+'/execute',headers=headers,json=payload)
    assert done.status_code==200,done.text
    assert client.post(root+'/execute',headers=headers,json=payload).status_code==200
    assert len(sent)==1 and sent[0][0] in {'POST','PUT'}
    if provider=='mailchimp':assert sent[0][2]['status_if_new']=='unsubscribed'
    if provider=='docusign':assert sent[0][2]['status']=='created'
    if provider=='zendesk':assert sent[0][2]['ticket']['comment']['public'] is False


@pytest.mark.parametrize('provider', [c[0] for c in CASES])
def test_sync_rejects_unrecognized_provider_response(provider):
    from app.apps.power_apps.integrations.marketplace_actions import page_result
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    with pytest.raises(IntegrationFailure):
        page_result(SimpleNamespace(connector_id=provider),{'cursor':'0'},{'unexpected':'collection'})


def test_sync_pagination_rejects_stalled_and_foreign_cursors():
    from app.apps.power_apps.integrations.marketplace_actions import page_result
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    with pytest.raises(IntegrationFailure):
        page_result(SimpleNamespace(connector_id='klaviyo'),{'cursor':'0'},{'data':[], 'links':{'next':'https://attacker.example/api/profiles?page[cursor]=next'}})
    with pytest.raises(IntegrationFailure):
        page_result(SimpleNamespace(connector_id='mailchimp'),{'cursor':'0'},{'members':[], 'total_items':1})


def test_surfe_failed_credit_request_requires_explicit_review_before_new_attempt(client,db,native_actor,monkeypatch):
    headers,user=native_actor
    attempts=[]
    ready=[False]
    class Transport:
        def request(self,method,url,**kwargs):
            attempts.append(url)
            result=fixture_page('surfe') if ready[0] else {'status':'IN_PROGRESS'}
            return SimpleNamespace(status=200,headers={},body=json.dumps(result).encode())
    monkeypatch.setattr(adapters,'HTTP_FACTORY',lambda policy:Transport())
    ident=create_connection(client,headers,next(c for c in CASES if c[0]=='surfe'),True)
    root='/api/v1/power-apps/integrations/sync'
    created=client.post(root+'/jobs',headers=headers,json={'connection_id':ident,'name':'Enrichment results','source':{'resource_id':'enrichment-1'},'allow_credit_usage':True,'apply_new_records':True})
    assert created.status_code==201,created.text
    job=created.json()['id']
    failed=client.post(f'{root}/jobs/{job}/run',headers=headers,json={})
    assert failed.status_code>=400
    state=client.get(root+'/jobs',headers=headers).json()['items'][0]
    assert state['state']=='error' and len(attempts)==1
    assert client.post(f'{root}/jobs/{job}/run',headers=headers,json={}).status_code>=400
    assert len(attempts)==1
    state=client.get(root+'/jobs',headers=headers).json()['items'][0]
    assert client.post(f'{root}/jobs/{job}/reviewed-retry',headers=headers,json={'expected_version':state['version'],'confirmed':False}).status_code==422
    ready[0]=True
    retried=client.post(f'{root}/jobs/{job}/reviewed-retry',headers=headers,json={'expected_version':state['version'],'confirmed':True})
    assert retried.status_code==200,retried.text
    assert retried.json()['state']=='idle' and len(attempts)==2
