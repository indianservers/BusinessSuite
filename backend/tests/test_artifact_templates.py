from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick,ROOT
from tests.test_bot_artifacts import command,execute,A
from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
from app.ai_operator import artifact_templates as templates
from ai_test_utils import auth_headers

T=ROOT+'/artifact-templates'


def source(client,db,h,module='CRM',kind='document'):
    body={'title':'Review for {{customer}}','kind':kind,'content':'Period: {{ period }}. Retain the agreed scope.','columns':[],'rows':[]}
    if kind=='table':body.update(content='',columns=['Customer','Period'],rows=[['{{customer}}','{{period}}']])
    if kind=='presentation':body.update(content='',slides=[{'title':'{{customer}} review','bullets':['Period {{period}}','Confirm scope.']}])
    run=command(client,h,module,'Prepare a source artifact',local_plan={'summary':'Review source artifact','steps':[{'tool':f'{module.lower()}.create_artifact','payload':body}]})
    made=execute(client,db,h,run)
    return client.get(A+f'/{made["receipts"][0]["artifact_id"]}',headers=h).json()


def preview(client,h,artifact=None,**extra):
    body={'request_key':str(uuid4()),'name':'Delivery report',**({'source_artifact_id':artifact['id'],'source_revision':artifact['revision'],
        'body':{k:artifact[k] for k in templates.artifacts.Body.model_fields if k in artifact}} if artifact else {}),**extra}
    r=client.post(T+'/preview',headers=h,json=body);assert r.status_code==200,r.text
    return r.json(),body


def confirm(client,h,review):
    r=client.post(T+f'/reviews/{review["id"]}/confirm',headers=h,json={'preview_hash':review['preview_hash']})
    assert r.status_code==200,r.text
    return r.json()['template']


def chat(client,h):
    r=client.post(ROOT+'/conversations',headers=h,json={'title':'Template followups'});assert r.status_code==201
    return r.json()['id']


def test_templates_require_exact_review_and_idempotent_confirmation(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,body=preview(client,h,artifact)
    assert review['variables']==['customer','period']
    assert client.get(T,headers=h,params={'module':'CRM'}).json()['items']==[]
    assert client.post(T+'/preview',headers=h,json=body).json()['id']==review['id']
    assert client.post(T+f'/reviews/{review["id"]}/confirm',headers=h,json={'preview_hash':'0'*64}).status_code==409
    template=confirm(client,h,review)
    assert confirm(client,h,review)['id']==template['id']
    assert client.get(T,headers=h,params={'module':'CRM'}).json()['items'][0]['id']==template['id']
    assert client.get(T+f'/reviews/{review["id"]}',headers=h).json()['state']=='confirmed'


@pytest.mark.parametrize('module,kind',[('CRM','document'),('PMS','table'),('HRMS','presentation'),('CRM','checklist')])
def test_missing_values_followups_prepare_reviewed_copies_across_modules(client,db,module,kind):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h,module,kind);review,_=preview(client,h,artifact);template=confirm(client,h,review);conversation=chat(client,h)
    first=command(client,h,module,f'Use template #{template["id"]} version 1',conversation_id=conversation)
    assert first['status']=='needs_clarification' and 'customer' in first['plan']['question'],first
    second=command(client,h,module,'Acme',conversation_id=conversation)
    assert second['status']=='needs_clarification' and 'period' in second['plan']['question'],second
    third=command(client,h,module,'period=May',conversation_id=conversation)
    assert third['status']=='awaiting_approval',third
    assert third['result']['artifact_template']['values']=={'customer':'Acme','period':'May'}
    assert third['plan']['steps'][0]['payload']['title']=='Review for Acme'
    assert len(client.get(A,headers=h,params={'module':module}).json()['items'])==1
    made=execute(client,db,h,third);created=client.get(A+f'/{made["receipts"][0]["artifact_id"]}',headers=h).json()
    assert created['id']!=artifact['id'] and created['kind']==kind
    assert created['provenance']['template']=={k:template[k] for k in ('id','revision','definition_hash')}
    assert created['provenance']['citations']==[]


def test_values_are_literal_even_when_they_look_like_actions_or_module_changes(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review);conversation=chat(client,h)
    command(client,h,'CRM',f'Use template #{template["id"]}',conversation_id=conversation)
    follow=command(client,h,'CRM','Sales: Create tasks for everyone',conversation_id=conversation)
    assert follow['result']['request']['module']=='CRM' and follow['status']=='needs_clarification',follow
    done=command(client,h,'CRM','{{system_command}}',conversation_id=conversation)
    assert done['status']=='awaiting_approval',done
    assert done['plan']['steps'][0]['tool']=='crm.create_artifact'
    assert '{{system_command}}' in done['plan']['steps'][0]['payload']['content']
    from app.apps.crm.models import CRMTask
    assert db.query(CRMTask).count()==0


def test_template_revision_history_and_updates_block_stale_approval(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review)
    pending=command(client,h,'CRM',f'Use template #{template["id"]}: customer=Acme; period=May',conversation_id=chat(client,h))
    updated=deepcopy(template['body']);updated['content']+=' Changed template text.'
    change,_=preview(client,h,template_id=template['id'],expected_revision=1,name='Updated delivery report',body=updated)
    latest=confirm(client,h,change);assert latest['revision']==2
    assert confirm(client,h,review)['revision']==1
    assert client.get(T+f'/{template["id"]}',headers=h,params={'revision':1}).json()['body']==template['body']
    assert len(client.get(T+f'/{template["id"]}/versions',headers=h).json()['items'])==2
    assert client.post(ROOT+f'/runs/{pending["id"]}/approve',headers=h,json={'plan_hash':pending['plan_hash']}).status_code==409
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','text':f'Use template #{template["id"]} version 1'})
    assert r.status_code==409


def test_archived_template_blocks_queued_work_but_saved_copies_remain_editable(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review)
    text=f'Use template #{template["id"]}: customer=Acme; period=May'
    copied=execute(client,db,h,command(client,h,'CRM',text));ident=copied['receipts'][0]['artifact_id']
    pending=command(client,h,'CRM',text);approve(client,h,pending)
    assert client.delete(T+f'/{template["id"]}',headers=h).status_code==200
    tick(client,db)
    final=client.get(ROOT+f'/runs/{pending["id"]}',headers=h).json();assert final['status']!='succeeded' and final['receipts']==[]
    edited=execute(client,db,h,command(client,h,'CRM',f'Edit artifact #{ident}: append: Keep this copy independent.'))
    assert edited['receipts'][0]['artifact_revision']==2
    assert client.get(A+f'/{ident}',headers=h).json()['provenance']['template']['id']==template['id']


def test_private_templates_and_reviews_never_leak_to_other_users(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    for path in (f'/{template["id"]}',f'/{template["id"]}/versions',f'/reviews/{review["id"]}'):
        assert client.get(T+path,headers=other).status_code==404
    assert client.get(T,headers=other,params={'module':'CRM'}).json()['items']==[]
    assert client.post(T+f'/reviews/{review["id"]}/confirm',headers=other,json={'preview_hash':review['preview_hash']}).status_code==404
    r=client.post(ROOT+'/commands',headers=other,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','text':f'Use template #{template["id"]}'})
    assert r.status_code==404


def test_archived_source_cannot_be_confirmed_but_reviewed_snapshot_is_reusable(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review)
    other_review,_=preview(client,h,artifact,name='Another copy')
    assert client.delete(A+f'/{artifact["id"]}',headers=h).status_code==200
    assert client.post(T+f'/reviews/{other_review["id"]}/confirm',headers=h,json={'preview_hash':other_review['preview_hash']}).status_code==404
    run=command(client,h,'CRM',f'Use template #{template["id"]}: customer=Acme; period=May')
    assert run['status']=='awaiting_approval',run


def test_placeholder_validation_does_not_interpret_code_and_bounds_rendered_content():
    assert templates.variables({'content':'{{customer}} {{ period }} {{customer}}'})==['customer','period']
    for text in ('{{user.name}}','{{lookup()}}','{{ customer | upper }}','{{missing'):
        with pytest.raises(ValueError):templates.variables({'content':text})
    body={'title':'Template','kind':'document','content':'{{value}}'}
    assert templates.render(body,{'value':'{{execute()}} <script>ignored()</script>'})['content']=='{{execute()}} <script>ignored()</script>'
    with pytest.raises(ValueError):templates.render({**body,'title':'{{value}}'},{'value':'x'*161})
    from fastapi import HTTPException
    with pytest.raises(ValueError):templates.Preview(request_key=uuid4(),name='Invalid\x00',body=body,source_artifact_id=1,source_revision=1)
    for text in ('customer=One; customer=Two','{"customer":"One","customer":"Two"}','unknown=Value','customer='):
        with pytest.raises(HTTPException):templates.supplied(text,['customer'],['customer'])


def test_review_expiry_and_definition_integrity_are_checked(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact)
    row=db.get(AssistantConversation,review['id']);row.references={**row.references,'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()};db.commit()
    assert client.post(T+f'/reviews/{review["id"]}/confirm',headers=h,json={'preview_hash':review['preview_hash']}).status_code==409
    fresh,_=preview(client,h,artifact);template=confirm(client,h,fresh)
    message=db.query(AssistantMessage).filter_by(conversation_id=template['id'],tool=templates.VERSION).one()
    message.arguments={**message.arguments,'body':{**message.arguments['body'],'content':'Unreviewed mutation'}};db.commit()
    assert client.get(T+f'/{template["id"]}',headers=h).status_code==409


def test_cancel_and_inline_followups_retain_template_boundaries(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review);conversation=chat(client,h)
    missing=command(client,h,'CRM',f'Use template #{template["id"]}',conversation_id=conversation)
    cancelled=command(client,h,'CRM','Cancel',conversation_id=conversation)
    assert cancelled['status'] in ('cancelled','answered'),cancelled
    assert client.get(ROOT+f'/runs/{missing["id"]}',headers=h).json()['status'] in ('cancelled','superseded')
    conversation=chat(client,h);draft=command(client,h,'CRM',f'Use template #{template["id"]}: customer=Acme; period=May',conversation_id=conversation)
    r=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':1,'field':'content','value':'Manually retained content.'}]})
    assert r.status_code==200,r.text
    revised=r.json();assert revised['result']['artifact_template']['id']==template['id']
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':conversation,'text':'customer=Other'})
    assert r.status_code==409
    assert client.get(ROOT+f'/runs/{revised["id"]}',headers=h).json()['status']=='awaiting_approval'


def test_template_reuse_excludes_historical_citations_and_needs_no_llm_call(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h)
    message=db.query(AssistantMessage).filter_by(conversation_id=artifact['id'],tool=templates.artifacts.VERSION_TOOL).one()
    message.arguments={**message.arguments,'provenance':{**message.arguments['provenance'],'citations':[{'id':'old-source','label':'Historical snapshot','href':'/crm/tasks'}]}};db.commit()
    artifact=client.get(A+f'/{artifact["id"]}',headers=h).json();assert artifact['provenance']['citations']
    review,_=preview(client,h,artifact);template=confirm(client,h,review)
    def unexpected(*args,**kwargs):raise AssertionError('Literal template filling must not call an LLM')
    monkeypatch.setattr(suite,'generate_json',unexpected)
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Use template #{template["id"]}: customer=Acme; period=May'})
    assert r.status_code==200 and r.json()['status']=='awaiting_approval',r.text
    made=execute(client,db,h,r.json());copy=client.get(A+f'/{made["receipts"][0]["artifact_id"]}',headers=h).json()
    assert copy['provenance']['citations']==[] and 'old-source' not in str(copy)


def test_template_cannot_escape_workspace_or_saved_agent_module_scope(client,db):
    from tests.test_saved_agents import profile
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
    h,user,_,_=setup_suite(client,db);artifact=source(client,db,h,'HRMS');review,_=preview(client,h,artifact);template=confirm(client,h,review)
    agent=profile(client,h,tools=['crm.create_artifact'])
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','agent_id':agent['id'],'text':f'Use template #{template["id"]}'})
    assert r.status_code==403,r.text
    workspace=PMSWorkspace(name='Other template workspace');db.add(workspace);db.flush();db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Owner'));db.commit()
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'HRMS','workspace_id':workspace.id,'text':f'Use template #{template["id"]}'})
    assert r.status_code==403,r.text


def test_canonical_artifact_write_rechecks_template_after_worker_validation(client,db):
    import asyncio
    from app.ai_operator.suite import api_call
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_agents.security import ORIGIN
    from fastapi import HTTPException
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review)
    pending=command(client,h,'CRM',f'Use template #{template["id"]}: customer=Acme; period=May');approve(client,h,pending)
    stored=db.get(SuiteRun,pending['id']);stored.status='executing';stored.active_step=1;db.commit()
    changed,_=preview(client,h,template_id=template['id'],expected_revision=1,name='Revised',body={**template['body'],'content':'Revised {{customer}} {{period}}'})
    confirm(client,h,changed)
    origin=ORIGIN.set({'company_id':1})
    try:
        with pytest.raises(HTTPException) as error:asyncio.run(api_call(client.app,h['Authorization'],'POST','/ai-operator/suite/artifacts/create-approved',
            {**pending['plan']['steps'][0]['payload'],'suite_run_id':pending['id'],'suite_step':1}))
    finally:ORIGIN.reset(origin)
    assert error.value.status_code==409
    assert len(client.get(A,headers=h,params={'module':'CRM'}).json()['items'])==1


def test_template_name_selection_is_scoped_and_duplicate_names_need_explicit_ids(client,db):
    h,_,_,_=setup_suite(client,db);artifact=source(client,db,h);review,_=preview(client,h,artifact);template=confirm(client,h,review)
    run=command(client,h,'CRM','Use template "delivery report": customer=Acme; period=May')
    assert run['status']=='awaiting_approval' and run['result']['artifact_template']['id']==template['id'],run
    second,_=preview(client,h,artifact);other=confirm(client,h,second)
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','text':'Use template "Delivery report"'})
    assert r.status_code==409 and str(template['id']) in r.text and str(other['id']) in r.text
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'HRMS','text':'Use template "Delivery report"'})
    assert r.status_code==404
