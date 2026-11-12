import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_saved_agents import profile,command
from tests.test_knowledge_search import chat
from tests.test_conversation_knowledge import upload,lexical_fixture
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/suite'


def source(client,h,conversation):
    ident=upload(client,h,conversation)
    result=client.get(ROOT+'/agents/knowledge/files',headers=h)
    assert result.status_code==200,result.text
    file=next(f for f in result.json()['items'] if f['attachment_id']==ident)
    return {k:file[k] for k in ('conversation_id','attachment_id','sha256')}


def search(client,h,conversation,agent,**extra):
    return client.post(ROOT+'/workspace/search',headers=h,json={'conversation_id':conversation,
        'agent_id':agent['id'],'query':'Escalation owners','mode':'lexical',**extra})


def test_private_files_reused_in_new_chats_with_citations_without_copying(client,db):
    from app.ai_operator.assistant_models import AssistantMessage
    h,_,_,_=setup_suite(client,db);original=chat(client,h);ref=source(client,h,original)
    agent=profile(client,h,tools=['crm.search_knowledge'],knowledge_files=[ref]);fresh=chat(client,h)
    found=search(client,h,fresh,agent);assert found.status_code==200,found.text
    item=found.json()['items'][0]
    assert item['id']==f'upload:{ref["attachment_id"]}:0' and item['agent_knowledge']
    assert f'/conversations/{original}/attachments/' in item['href']
    run=command(client,h,agent,'Search knowledge for: Escalation owners',conversation_id=fresh)
    assert run['status']=='answered' and 'Escalation owners' in run['plan']['summary'],run
    assert run['result']['citations'][0]['file_id']==ref['attachment_id']
    assert db.query(AssistantMessage).filter_by(tool='suite.attachment').count()==1
    plain=client.post(ROOT+'/workspace/search',headers=h,json={'conversation_id':fresh,'query':'Escalation owners','mode':'lexical'})
    assert plain.status_code==200 and plain.json()['items']==[]


def test_private_agent_documents_are_not_exposed_to_other_users(client,db):
    h,_,_,_=setup_suite(client,db);ref=source(client,h,chat(client,h))
    agent=profile(client,h,knowledge_files=[ref])
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    assert client.get(ROOT+'/agents/knowledge/files',headers=other).json()['items']==[]
    assert search(client,other,chat(client,other),agent).status_code==404
    r=client.post(ROOT+'/agents',headers=other,json={'name':'Foreign source','instructions':'Read source',
        'modules':['CRM'],'tools':['crm.tasks'],'knowledge_files':[ref]})
    assert r.status_code==404,r.text


def test_invalid_hash_duplicates_and_workspace_mismatch_rejected(client,db):
    from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
    h,user,_,_=setup_suite(client,db);ref=source(client,h,chat(client,h))
    base={'name':'Bound documents','instructions':'Read selected sources','modules':['CRM'],'tools':['crm.tasks']}
    for refs,code in [([{**ref,'sha256':'0'*64}],409),([ref,ref],422)]:
        r=client.post(ROOT+'/agents',headers=h,json={**base,'knowledge_files':refs});assert r.status_code==code,r.text
    workspace=PMSWorkspace(name='Separate knowledge workspace');db.add(workspace);db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Owner'));db.commit()
    r=client.post(ROOT+'/agents',headers=h,json={**base,'workspace_id':workspace.id,'knowledge_files':[ref]})
    assert r.status_code==403,r.text


@pytest.mark.parametrize('delete_source',['attachment','conversation'])
def test_deleted_source_blocks_approval_and_can_be_removed_from_agent(client,db,delete_source):
    h,_,_,_=setup_suite(client,db);original=chat(client,h);ref=source(client,h,original)
    agent=profile(client,h,knowledge_files=[ref]);run=command(client,h,agent)
    assert run['status']=='awaiting_approval',run
    path=f'/conversations/{original}'+(f'/attachments/{ref["attachment_id"]}' if delete_source=='attachment' else '')
    assert client.delete(ROOT+path,headers=h).status_code==200
    assert client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==404
    assert client.get(ROOT+'/agents',headers=h).json()['items'][0]['id']==agent['id']
    body={k:agent[k] for k in (
        'name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','mcp_ids','environment','revision')}
    fixed=client.put(ROOT+f'/agents/{agent["id"]}',headers=h,json={**body,'knowledge_files':[]})
    assert fixed.status_code==200,fixed.text
    assert not fixed.json().get('knowledge_files')


def test_worker_rechecks_deleted_documents_after_approval(client,db):
    from app.apps.crm.models import CRMTask
    h,_,_,_=setup_suite(client,db);original=chat(client,h);ref=source(client,h,original)
    agent=profile(client,h,knowledge_files=[ref]);run=command(client,h,agent);approve(client,h,run)
    assert client.delete(ROOT+f'/conversations/{original}/attachments/{ref["attachment_id"]}',headers=h).status_code==200
    tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']!='succeeded' and not final['receipts'],final
    assert db.query(CRMTask).count()==0


def test_provider_receives_bound_documents_as_untrusted_cited_context(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);ref=source(client,h,chat(client,h));calls=[]
    agent=profile(client,h,provider='gemini',knowledge_files=[ref])
    def propose(*a,**kw):
        packet=json.loads(kw['prompt']);calls.append(packet)
        assert packet['uploaded_context'][0]['agent_knowledge']
        assert 'Escalation owners' in packet['uploaded_context'][0]['text']
        assert 'untrusted' in packet['upload_instructions']
        return {'summary':'The selected document says escalation owners review stalled commitments.',
            'steps':[],'source_ids':[f'upload:{ref["attachment_id"]}']}
    monkeypatch.setattr(suite,'generate_json',propose)
    run=command(client,h,agent,'Explain the escalation policy',conversation_id=chat(client,h))
    assert run['status']=='answered' and calls,run
    assert run['result']['citations'][0]['id']==f'upload:{ref["attachment_id"]}'


def test_search_agent_binding_cannot_broaden_native_tools_or_workspace(client,db):
    h,_,_,_=setup_suite(client,db);ref=source(client,h,chat(client,h))
    agent=profile(client,h,tools=['crm.search_knowledge'],knowledge_files=[ref]);fresh=chat(client,h)
    assert search(client,h,fresh,agent,tools=['crm.leads']).status_code==403
    excluded=search(client,h,fresh,agent,include_uploads=False)
    assert excluded.status_code==200 and excluded.json()['items']==[]


def test_same_chat_source_is_deduplicated_and_binding_count_is_bounded(client,db):
    from app.ai_operator.saved_agents import Config
    h,_,_,_=setup_suite(client,db);original=chat(client,h);ref=source(client,h,original)
    agent=profile(client,h,tools=['crm.search_knowledge'],knowledge_files=[ref])
    found=search(client,h,original,agent)
    assert found.status_code==200,found.text
    assert found.json()['files_searched']==1 and len(found.json()['items'])==1
    with pytest.raises(ValueError):Config(name='Too many files',instructions='Read files',modules=['CRM'],tools=['crm.tasks'],
        knowledge_files=[{**ref,'attachment_id':i} for i in range(1,6)])


def test_library_publication_excludes_private_knowledge_bindings(client,db):
    from tests.test_agent_library import proposal,publish,install,member
    h,_,_,_=setup_suite(client,db);ref=source(client,h,chat(client,h));agent=profile(client,h,knowledge_files=[ref])
    draft,_=proposal(client,h,agent)
    assert 'knowledge_files' not in draft['pending']['definition']
    assert draft['pending']['definition']['omitted']['private_knowledge_files']==1
    assert ref['sha256'] not in json.dumps(draft)
    publication=publish(client,h,draft);other,_=member(client,db);imported=install(client,other,publication)
    assert not imported.get('knowledge_files')


def test_file_picker_reads_metadata_without_loading_document_bodies(client,db):
    from sqlalchemy import event
    h,_,_,_=setup_suite(client,db);source(client,h,chat(client,h));statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
    event.listen(db.bind,'before_cursor_execute',capture)
    try:result=client.get(ROOT+'/agents/knowledge/files',headers=h)
    finally:event.remove(db.bind,'before_cursor_execute',capture)
    assert result.status_code==200 and result.json()['items'],result.text
    selected=[sql.split('FROM')[0] for sql in statements if sql.lstrip().upper().startswith('SELECT') and 'FROM pms_assistant_messages' in sql]
    assert selected and all('pms_assistant_messages.result' not in sql for sql in selected)
    assert 'excerpt' not in result.json()['items'][0]


def test_old_config_serialization_and_schedule_source_checks(client,db):
    from app.ai_operator.saved_agents import Config
    from app.ai_operator.agent_schedules import snapshot
    base=Config(name='Existing agent',instructions='Read tasks',modules=['CRM'],tools=['crm.tasks'])
    assert 'knowledge_files' not in base.model_dump()
    h,user,_,_=setup_suite(client,db);original=chat(client,h);ref=source(client,h,original)
    agent=profile(client,h,knowledge_files=[ref]);assert snapshot(db,user,agent['id'])['revision']==1
    client.delete(ROOT+f'/conversations/{original}/attachments/{ref["attachment_id"]}',headers=h)
    with pytest.raises(HTTPException) as exc:snapshot(db,user,agent['id'])
    assert exc.value.status_code==404


def test_scheduled_agent_retrieves_bound_document_in_its_new_conversation(client,db):
    import asyncio
    from datetime import datetime,timedelta,timezone
    from app.ai_operator.agent_schedules import dispatch
    from app.ai_operator.suite_models import SuiteRun
    h,_,_,_=setup_suite(client,db);ref=source(client,h,chat(client,h))
    agent=profile(client,h,tools=['crm.search_knowledge'],knowledge_files=[ref])
    first=datetime.now(timezone.utc)+timedelta(minutes=2)
    r=client.post(ROOT+'/agents/schedules/preview',headers=h,json={'request_key':str(uuid4()),'agent_id':agent['id'],
        'prompt':'Search knowledge for: Escalation owners','scheduled_at':first.isoformat(),
        'expires_at':(first+timedelta(hours=1)).isoformat(),'frequency':'once'})
    assert r.status_code==200,r.text
    preview=r.json()
    r=client.post(ROOT+f'/agents/schedules/{preview["id"]}/activate',headers=h,json={'preview_hash':preview['preview_hash']})
    assert r.status_code==200,r.text
    assert asyncio.run(dispatch(db,client.app,first+timedelta(seconds=1)))['processed']==1
    db.expire_all();run=db.query(SuiteRun).one()
    assert run.status=='answered',run.error_code
    assert run.result['citations'][0]['file_id']==ref['attachment_id']
    assert run.result['request']['conversation_id']!=ref['conversation_id']
