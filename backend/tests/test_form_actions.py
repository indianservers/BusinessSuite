from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite,approve,tick,ROOT,prepare
from tests.test_suite_workspace import chat,say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from app.forms.models import SuiteForm,FormReply
from app.ai_operator import suite
from ai_test_utils import auth_headers


@pytest.fixture(params=['CRM','PMS','HRMS'])
def form_case(request,client,db):
    h,user,project,_=setup_suite(client,db)
    return h,user,request.param,project,chat(client,h)


def result(client,h,run):return client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()


def create_draft(client,db,h,module,ident):
    draft=say(client,h,ident,f'{module}: Create form called Synthetic intake with fields Name:text required, Email:email, Category:select[Sales|Support]',module=module)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert db.query(SuiteForm).count()==0
    approve(client,h,draft);tick(client,db);done=result(client,h,draft)
    assert done['status']=='succeeded',done.get('error_code')
    return done,db.get(SuiteForm,done['receipts'][0]['record_id'])


def test_local_form_full_lifecycle_preserves_private_drafts_and_separate_publication(client,db,form_case):
    h,user,module,project,ident=form_case
    first=say(client,h,ident,f'{module}: Create form called Synthetic intake',module=module)
    assert first['status']=='needs_clarification'
    draft=say(client,h,ident,'fields=Name:text required, Email:email; public=true',module=module)
    assert draft['status']=='awaiting_approval' and not db.query(SuiteForm).count()
    revised=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'name','value':'Reviewed intake'}]})
    assert revised.status_code==200,revised.text
    final=say(client,h,ident,'add=Phone:phone; description=Synthetic details',module=module)
    assert final['plan']['steps'][0]['payload']['name']=='Reviewed intake'
    assert len(final['plan']['steps'][0]['payload']['fields'])==3
    payload=final['plan']['steps'][0]['payload']
    assert client.post(ROOT+f'/{module.lower()}/forms/create-approved',headers=h,json={**payload,'suite_run_id':final['id'],'suite_step':1}).status_code==403
    approve(client,h,final);tick(client,db);done=result(client,h,final)
    assert done['status']=='succeeded',done.get('error_code')
    row=db.get(SuiteForm,done['receipts'][0]['record_id'])
    assert row.module_key==module.lower() and row.owner_id==user.id and not row.open and row.published is None
    assert done['result_cards'][0]['href']==f'/{module.lower()}/forms/{row.id}/edit'
    assert client.get('/api/v1/forms/public/'+row.slug).status_code==404
    source=client.get(ROOT+f'/{module.lower()}/forms/records/{row.id}',headers=h)
    assert source.status_code==200 and 'slug' not in source.json() and 'responses' not in source.json()
    assert source.headers['cache-control']=='private, no-store'
    edit=say(client,h,ident,'Edit that form',module=module);assert edit['status']=='needs_clarification'
    edit=say(client,h,ident,'required=q2:true; label=q1:Full name',module=module);assert edit['status']=='awaiting_approval'
    assert edit['result']['form_reviews']['1']['operation']=='edit'
    approve(client,h,edit);tick(client,db);edited=result(client,h,edit);assert edited['status']=='succeeded',edited.get('error_code')
    db.refresh(row);assert row.draft['fields'][1]['required'] and row.draft['fields'][0]['label']=='Full name' and row.published is None
    publish=say(client,h,ident,'Publish that form',module=module)
    assert publish['status']=='awaiting_approval' and publish['result']['form_reviews']['1']['audience']=='Anyone with the public link'
    assert client.get('/api/v1/forms/public/'+row.slug).status_code==404
    approve(client,h,publish);tick(client,db);published=result(client,h,publish);assert published['status']=='succeeded',published.get('error_code')
    db.refresh(row);assert row.version==1 and row.open
    assert published['result_cards'][0]['href']=='/f/'+row.slug
    assert client.get('/api/v1/forms/public/'+row.slug).json()['definition']['fields'][0]['label']=='Full name'
    old_revision=row.revision;approve(client,h,published);tick(client,db);db.refresh(row);assert row.revision==old_revision
    close=say(client,h,ident,'Close that form',module=module);assert close['status']=='awaiting_approval'
    approve(client,h,close);tick(client,db);closed=result(client,h,close);assert closed['status']=='succeeded',closed.get('error_code')
    assert client.get('/api/v1/forms/public/'+row.slug).json()['open'] is False
    assert db.query(FormReply).count()==0


def test_form_selection_retains_changes_and_blocks_other_owners_and_modules(client,db,form_case):
    h,user,module,project,ident=form_case;done,row=create_draft(client,db,h,module,ident)
    other_chat=chat(client,h)
    pending=say(client,h,other_chat,'Edit form: name=Selected later',module=module);assert pending['status']=='needs_clarification'
    selected=say(client,h,other_chat,f'form={row.id}',module=module)
    assert selected['status']=='awaiting_approval' and selected['plan']['steps'][0]['payload']['name']=='Selected later'
    other,_=auth_headers(client,db,email=f'form-owner-{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/{module.lower()}/forms/records/{row.id}',headers=other).status_code==404
    wrong='crm' if module!='CRM' else 'hrms'
    assert client.get(ROOT+f'/{wrong}/forms/records/{row.id}',headers=h).status_code==404
    assert client.get(ROOT+f'/{module.lower()}/forms/records',headers=other).json()['items']==[]


@pytest.mark.parametrize('action',['create','edit','publish','close'])
def test_committed_form_action_recovers_lost_receipt_without_repeating(client,db,monkeypatch,form_case,action):
    h,user,module,project,ident=form_case
    if action=='create':draft=say(client,h,ident,'Create form called Recovery with fields Subject:text required',module=module)
    else:
        done,row=create_draft(client,db,h,module,ident)
        if action=='close':
            pub=say(client,h,ident,'Publish that form',module=module);approve(client,h,pub);tick(client,db)
        text={'edit':'Edit that form: description=Recovery edit','publish':'Publish that form','close':'Close that form'}[action]
        draft=say(client,h,ident,text,module=module)
    assert draft['status']=='awaiting_approval';approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost form receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    stopped=result(client,h,draft);assert stopped['status']=='needs_reconciliation' and stopped['can_resume'],stopped.get('error_code')
    row=db.query(SuiteForm).one();revision=row.revision
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==200 and response.json()['status']=='succeeded',response.text
    db.refresh(row);assert row.revision==revision and db.query(SuiteForm).count()==1


def test_stale_or_changed_form_cannot_publish_or_recover_as_unchanged(client,db,monkeypatch,form_case):
    h,user,module,project,ident=form_case;done,row=create_draft(client,db,h,module,ident)
    publish=say(client,h,ident,'Publish that form',module=module);assert publish['status']=='awaiting_approval'
    value=client.get('/api/v1/forms/'+str(row.id),headers=h).json();definition=value['draft'];definition['description']='Independent edit'
    assert client.put('/api/v1/forms/'+str(row.id),headers=h,json={'revision':value['revision'],'definition':definition}).status_code==200
    assert client.post(ROOT+f'/runs/{publish["id"]}/approve',headers=h,json={'plan_hash':publish['plan_hash']}).status_code==409
    db.refresh(row);assert not row.open and row.published is None


def test_schema_choices_conditions_and_publication_controls_cannot_be_injected(client,db,form_case):
    h,user,module,project,ident=form_case
    bad=prepare(client,h,[{'tool':module.lower()+'.create_form','payload':{'name':'Unsafe','fields':[{'id':'q1','type':'select','label':'Choice'}],'publish':True}}])
    assert bad['status']=='failed' and db.query(SuiteForm).count()==0
    good=prepare(client,h,[{'tool':module.lower()+'.create_form','payload':{'name':'Typed conditional form','fields':[{'id':'q1','type':'select','label':'Department','options':['Sales','Support'],'required':True},{'id':'q2','type':'textarea','label':'Details','condition':{'field':'q1','operator':'equals','value':'Support'}}],'settings':{'public':True,'columns':2}}}])
    assert good['status']=='awaiting_approval'
    approve(client,h,good);tick(client,db);done=result(client,h,good);assert done['status']=='succeeded',done.get('error_code')
    row=db.query(SuiteForm).one();assert not row.open and row.published is None and row.draft['fields'][1]['condition']['field']=='q1'


def test_pms_form_intake_uses_existing_transactional_task_workflow_and_request_id(client,db):
    from app.apps.project_management.models import PMSTask
    h,user,project,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'PMS: Create form called Task intake with fields Request title:text required',module='PMS')
    configured=say(client,h,ident,f'workflow=true; project={project}; task_title=q1; task_priority=High',module='PMS')
    assert configured['status']=='awaiting_approval',configured.get('error_code')
    approve(client,h,configured);tick(client,db);done=result(client,h,configured);assert done['status']=='succeeded',done.get('error_code')
    fid=done['receipts'][0]['record_id'];before=db.query(PMSTask).count()
    assert before==1
    published=say(client,h,ident,'Publish that form',module='PMS');approve(client,h,published);tick(client,db)
    assert result(client,h,published)['status']=='succeeded'
    body={'request_id':str(uuid4()),'version':1,'answers':{'q1':'Synthetic submitted task'}}
    first=client.post(f'/api/v1/forms/{fid}/internal/submit',headers=h,json=body)
    assert first.status_code==201,first.text
    second=client.post(f'/api/v1/forms/{fid}/internal/submit',headers=h,json=body)
    assert second.status_code==201,second.text
    assert db.query(PMSTask).count()==before+1 and db.query(FormReply).count()==1
    task=db.query(PMSTask).filter_by(title='Synthetic submitted task').one()
    assert task.project_id==project and task.priority=='High' and task.reporter_user_id==user.id


def test_natural_followups_and_pending_draft_publication_are_reviewed_separately(client,db,form_case):
    h,user,module,project,ident=form_case
    missing=say(client,h,ident,'Create form called Plain language intake',module=module);assert missing['status']=='needs_clarification'
    ready=say(client,h,ident,'Name:text required, Email:email',module=module);assert ready['status']=='awaiting_approval'
    for message in ['Make Email required','Add an email field called Backup email','Rename the form to Natural intake','Make it public']:
        ready=say(client,h,ident,message,module=module)
        assert ready['status']=='awaiting_approval',ready.get('error_code')
    payload=ready['plan']['steps'][0]['payload']
    assert payload['name']=='Natural intake' and payload['fields'][1]['required'] and payload['settings']['public'] and len(payload['fields'])==3
    pending_publication=say(client,h,ident,'Publish that form',module=module)
    assert pending_publication['status']=='awaiting_approval' and pending_publication['plan']['steps'][0]['tool']==module.lower()+'.create_form'
    assert db.query(SuiteForm).count()==0
    approve(client,h,pending_publication);tick(client,db);created=result(client,h,pending_publication)
    assert created['status']=='succeeded' and db.query(SuiteForm).one().published is None


def test_named_numeric_form_and_close_preview_use_the_correct_native_definition(client,db,form_case):
    h,user,module,project,ident=form_case;done,row=create_draft(client,db,h,module,ident)
    source=client.get('/api/v1/forms/'+str(row.id),headers=h).json();definition=source['draft'];definition['name']='2026';definition['settings']['public']=True
    assert client.put('/api/v1/forms/'+str(row.id),headers=h,json={'revision':source['revision'],'definition':definition,'publish':True}).status_code==200
    selected=say(client,h,ident,'Edit form called 2026: name=Private next draft; public=false',module=module)
    assert selected['status']=='awaiting_approval' and selected['plan']['steps'][0]['payload']['form_id']==row.id
    approve(client,h,selected);tick(client,db);assert result(client,h,selected)['status']=='succeeded'
    close=say(client,h,ident,'Close that form',module=module)
    assert close['status']=='awaiting_approval'
    review=close['result']['form_reviews']['1']
    assert review['definition']['name']=='2026' and review['audience']=='Anyone with the public link'
    assert review['definition']['settings']['public'] is True


def test_cloud_form_read_preserves_all_sixty_questions_without_expanding_other_sources(client,db,monkeypatch):
    import json
    from tests.test_ai_operator import mock_provider
    from app.ai_agents.security import redact
    h,user,project,_=setup_suite(client,db)
    definition={'name':'Synthetic sixty question form','fields':[{'id':f'q{index}','type':'text','label':f'Question {index}'} for index in range(1,61)]}
    created=client.post('/api/v1/forms',headers=h,json={'module_key':'crm','definition':definition});assert created.status_code==201,created.text
    value=created.json();source=client.get(ROOT+f'/crm/forms/records/{value["id"]}',headers=h).json()
    payload={**source['definition'],'name':'Reviewed sixty question form','form_id':value['id'],'expected_revision':source['revision'],'source_sha256':source['source_sha256']}
    calls=mock_provider(monkeypatch,{'summary':'Review a form title change','steps':[{'tool':'crm.edit_form','payload':payload}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':'Prepare a native form title revision using the complete authorized definition','context':[{'tool':'crm.form','record_id':value['id']}]})
    assert response.status_code==200,response.text
    draft=response.json();assert draft['status']=='awaiting_approval',draft.get('error_code')
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    observed=next(item['records'] for item in outbound['authorized_context'] if item['tool']=='crm.form')
    assert len(observed['definition']['fields'])==60 and observed['source_sha256']==source['source_sha256']
    assert 'slug' not in observed and 'responses' not in observed
    assert len(redact(list(range(60))))==50
    approve(client,h,draft);tick(client,db);done=result(client,h,draft);assert done['status']=='succeeded',done.get('error_code')
    assert len(db.get(SuiteForm,value['id']).draft['fields'])==60


def test_large_native_definition_can_be_edited_locally_without_relaxing_generic_inputs(client,db):
    from fastapi import HTTPException
    from app.ai_agents.security import strict_input
    h,user,project,_=setup_suite(client,db)
    definition={'name':'Synthetic large form','fields':[{'id':f'q{index}','type':'text','label':f'Question {index}','help':'Synthetic guidance. '*20} for index in range(1,61)]}
    created=client.post('/api/v1/forms',headers=h,json={'module_key':'crm','definition':definition});assert created.status_code==201,created.text
    fid=created.json()['id'];ident=chat(client,h)
    draft=say(client,h,ident,f'CRM: Edit form #{fid}: name=Reviewed large form',module='CRM')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    payload=draft['plan']['steps'][0]['payload']
    with pytest.raises(HTTPException):strict_input({'properties':{key:{} for key in payload}},payload)
    approve(client,h,draft);tick(client,db);done=result(client,h,draft);assert done['status']=='succeeded',done.get('error_code')
    stored=db.get(SuiteForm,fid).draft
    assert len(stored['fields'])==60 and stored['fields'][-1]['help']==definition['fields'][-1]['help']
