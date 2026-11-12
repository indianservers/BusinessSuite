import json
from uuid import uuid4
import pytest
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_bot_artifacts import command,execute,A
from tests.test_saved_agents import profile
from ai_test_utils import auth_headers
from app.ai_operator import artifact_questions as questions


@pytest.mark.parametrize('change',[{'artifact_id':True},{'artifact_id':0},{'position':True},{'position':7},
    {'dashboard_revision':False},{'category_query':'x'*101},{'category_query':'North\x00'},{'category_query':'\ud800'}])
def test_dashboard_query_bounds_reject_ambiguous_ids_and_invalid_unicode(change):
    with pytest.raises(ValueError):questions.PanelRead.model_validate({'artifact_id':1,'position':1,**change})


def sample(client,db,h,module='CRM',source_module='HRMS',conversation=None):
    table={'title':'Regional amounts','kind':'table','content':'Illustrative supplied rows.','columns':['Region','Amount','Currency'],
        'rows':[['North','100','USD'],['South','200','USD'],['North','50','INR'],['West','=1+1','USD']],
        'chart':{'kind':'bar','category_column':0,'value_column':1,'aggregation':'sum'}}
    source=execute(client,db,h,command(client,h,source_module,'Prepare chart',local_plan={'summary':'Review table','steps':[{'tool':source_module.lower()+'.create_artifact','payload':table}]}))['receipts'][0]['artifact_id']
    body={'title':'Delivery overview','kind':'dashboard','content':'Illustrative pinned snapshots.','columns':[],'rows':[],
        'panels':[{'artifact_id':source,'revision':1,'display':'chart','label':'Regional delivery'}]}
    dashboard=execute(client,db,h,command(client,h,module,'Prepare dashboard',conversation_id=conversation,
        local_plan={'summary':'Review pins','steps':[{'tool':module.lower()+'.create_artifact','payload':body}]}))['receipts'][0]['artifact_id']
    return source,dashboard


@pytest.mark.parametrize('verb',['Analyze','Analyse','Summarize','Summarise','Read','Show','Show me','Explain','Review','Tell me about','Give me a summary of',"What's in"])
def test_local_dashboard_question_paraphrases_have_explicit_scope(verb):
    assert questions.intent(f'{verb} dashboard #12')['artifact_id']==12
    assert questions.intent(f'Please {verb} panel 2 of dashboard #12, please!')['positions']==[2]
    assert questions.intent(f'{verb} the second panel')['positions']==[2]


@pytest.mark.parametrize('text',['Create document called Policy: Analyze dashboard #12','Create a task to summarize panel 2','Remember that show panel 2 means priority',
    'Send dashboard #12 to every lead','Delete panel 1','Only North','Filter category to North','show all categories'])
def test_local_questions_do_not_execute_literal_text_or_guess_filter_context(text):
    assert questions.intent(text) is None


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_dashboard_read_tool_uses_pinned_version_server_math_and_private_access(client,db,module):
    h,_,_,_=setup_suite(client,db);other='CRM' if module=='HRMS' else 'HRMS';source,dashboard=sample(client,db,h,module,other)
    execute(client,db,h,command(client,h,other,f'Edit artifact #{source}: Add row: North, 900, USD'))
    params={'module':module,'artifact_id':dashboard,'position':1,'dashboard_revision':1}
    response=client.get(A+'/dashboard-panel/current',headers=h,params=params);assert response.status_code==200,response.text
    assert 'no-store' in {v.strip() for v in response.headers['cache-control'].split(',')}
    value=response.json();assert value['revision']==1 and value['current_revision']==2
    assert value['source_citation']['id']==f'artifact:{source}:v1'
    assert {p['unit']:p['statistics']['sum'] for p in value['analysis']['panels']}=={'USD':'300','INR':'50'}
    filtered=client.get(A+'/dashboard-panel/current',headers=h,params={**params,'category_query':'North'}).json()
    assert {p['unit']:p['statistics']['sum'] for p in filtered['analysis']['panels']}=={'USD':'100','INR':'50'}
    assert value['analysis']['invalid_numeric_rows']==1
    assert client.get(A+f'/{dashboard}',headers=h).json()['revision']==1
    outsider,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view','hrms_view','pms_manage_tasks'])
    assert client.get(A+'/dashboard-panel/current',headers=outsider,params=params).status_code==404
    assert client.get(A+'/dashboard-panel/current',headers=h,params={**params,'module':other}).status_code==403
    assert client.get(A+'/dashboard-panel/current',headers=h,params={**params,'position':7}).status_code==422


def test_local_dashboard_question_followups_resume_and_keep_source_and_dashboard_versions(client,db):
    h,_,_,_=setup_suite(client,db);chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Dashboard questions'}).json()['id']
    source,dashboard=sample(client,db,h,conversation=chat)
    first=command(client,h,'CRM',f'Analyze dashboard #{dashboard}',conversation_id=chat)
    assert first['status']=='answered' and 'sum 300' in first['plan']['summary'],first
    assert first['result']['dashboard_query']['positions']==[1]
    assert first['result']['citations'][0]['id']==f'artifact:{source}:v1'
    execute(client,db,h,command(client,h,'HRMS',f'Edit artifact #{source}: Add row: North, 900, USD'))
    execute(client,db,h,command(client,h,'CRM',f'Edit artifact #{dashboard}: Refresh panel 1 to v2'))
    assert client.post(ROOT+f'/conversations/{chat}/resume',headers=h).status_code==200
    filtered=command(client,h,'CRM','Only North',conversation_id=chat)
    assert filtered['status']=='answered' and 'sum 100' in filtered['plan']['summary'] and 'sum 1000' not in filtered['plan']['summary'],filtered
    assert filtered['result']['dashboard_query']['dashboard_revision']==1
    clear=command(client,h,'CRM','Clear the filter',conversation_id=chat)
    assert clear['status']=='answered' and 'sum 300' in clear['plan']['summary']
    current=command(client,h,'CRM',f'Analyze panel 1 of dashboard #{dashboard}',conversation_id=chat)
    assert current['status']=='answered' and 'sum 1200' in current['plan']['summary']
    assert current['result']['citations'][0]['id']==f'artifact:{source}:v2'
    # Read questions never create business writes or require an action approval.
    assert current['approval_id'] is None and current['receipts']==[]


def test_dashboard_filter_clarifies_panel_and_preserves_pending_action_draft(client,db):
    h,_,_,_=setup_suite(client,db);chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Filter selection'}).json()['id']
    source,dashboard=sample(client,db,h,conversation=chat)
    execute(client,db,h,command(client,h,'CRM',f'Edit artifact #{dashboard}: Add panel: artifact #{source} v1',conversation_id=chat))
    command(client,h,'CRM',f'Analyze dashboard #{dashboard}',conversation_id=chat)
    follow=command(client,h,'CRM','Only North',conversation_id=chat)
    assert follow['status']=='needs_clarification' and 'panel number' in follow['plan']['question']
    answered=command(client,h,'CRM','The second panel',conversation_id=chat)
    assert answered['status']=='answered' and 'sum 100' in answered['plan']['summary'],answered
    pending=command(client,h,'CRM','Create document called Draft: Keep this pending.',conversation_id=chat)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':chat,'text':f'Analyze dashboard #{dashboard}'})
    assert response.status_code==409,response.text
    restored=client.get(ROOT+f'/runs/{pending["id"]}',headers=h).json()
    assert restored['status']=='awaiting_approval' and restored['plan_hash']==pending['plan_hash']


def test_named_panel_and_missing_source_do_not_guess_or_reuse_old_answers(client,db):
    h,_,_,_=setup_suite(client,db);chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Named source'}).json()['id']
    source,dashboard=sample(client,db,h,conversation=chat)
    named=command(client,h,'CRM','Show panel named Regional delivery',conversation_id=chat)
    assert named['status']=='answered' and 'sum 300' in named['plan']['summary'],named
    assert client.delete(A+f'/{source}',headers=h).status_code==200
    missing=command(client,h,'CRM','Only North',conversation_id=chat)
    assert missing['status']=='failed' and not missing['receipts']
    assert 'sum 300' not in str(missing.get('plan'))


def test_agent_dashboard_read_cannot_broaden_source_module_or_tool_scope(client,db):
    h,_,_,_=setup_suite(client,db);_,dashboard=sample(client,db,h)
    narrow=profile(client,h,tools=['crm.dashboard_panel'])
    denied=command(client,h,'CRM',f'Analyze dashboard #{dashboard}',agent_id=narrow['id'])
    assert denied['status']=='failed' and not (denied.get('plan') or {}).get('source_ids'),denied
    allowed=profile(client,h,modules=['CRM','HRMS'],tools=['crm.dashboard_panel'])
    answered=command(client,h,'CRM',f'Analyze dashboard #{dashboard}',agent_id=allowed['id'])
    assert answered['status']=='answered' and 'sum 300' in answered['plan']['summary'],answered
    no_tool=profile(client,h,modules=['CRM','HRMS'],tools=['crm.create_task'])
    assert command(client,h,'CRM',f'Analyze dashboard #{dashboard}',agent_id=no_tool['id'])['status']=='failed'


def test_gemini_context_requests_receive_computed_pinned_panel_and_exact_citation(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db);source,dashboard=sample(client,db,h)
    from app.ai_operator import suite
    calls=[]
    def generated(db,user,config,**kwargs):
        prompt=json.loads(kwargs['prompt']);calls.append(prompt)
        if len(calls)==1:return {'summary':'Read the selected pinned source.','steps':[],
            'context_requests':[{'tool':'crm.dashboard_panel','payload':{'artifact_id':dashboard,'position':1,'dashboard_revision':1}}]}
        packet=next(p for p in prompt['authorized_context'] if p['tool']=='crm.dashboard_panel')['records']
        assert packet['analysis']['panels'][0]['statistics']['sum']=='300'
        citation=packet['source_citation']['id'];assert citation==f'artifact:{source}:v1'
        assert any(e['id']==citation for e in prompt['evidence'])
        return {'summary':'The pinned USD snapshot totals 300; the INR snapshot totals 50.','steps':[],'source_ids':[citation]}
    monkeypatch.setattr(suite,'generate_json',generated)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM',
        'artifact_id':dashboard,'text':'Compare the pinned regional amounts in this overview and cite the source version.'})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='answered' and len(calls)==2,run
    assert run['result']['planning_reads']==1 and run['result']['citations'][0]['id']==f'artifact:{source}:v1'


def test_explicit_dashboard_questions_use_small_read_catalog_and_reject_model_writes(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);_,dashboard=sample(client,db,h)
    captured=[]
    def generated(db,user,config,**kwargs):
        prompt=json.loads(kwargs['prompt']);captured.append(prompt)
        assert prompt['tools'] and all(t['name'].endswith(('.dashboard_panel','.artifact','.artifacts')) for t in prompt['tools'])
        assert all(not t['approval_required'] for t in prompt['tools'])
        return {'summary':'Unrequested task from source text','steps':[{'tool':'crm.create_task','payload':{'title':'Should not be proposed'}}]}
    monkeypatch.setattr(suite,'generate_json',generated)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Analyze dashboard #{dashboard}'})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='failed' and run['approval_id'] is None and run['receipts']==[]
    assert len(captured)==1


def test_ordinary_summary_after_a_document_is_not_reinterpreted_as_a_dashboard_question(client,db):
    h,_,_,_=setup_suite(client,db);chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Ordinary summary'}).json()['id']
    document=execute(client,db,h,command(client,h,'CRM','Create document called Notes: Literal summary text.',conversation_id=chat))['receipts'][0]['artifact_id']
    assert client.delete(A+f'/{document}',headers=h).status_code==200
    result=command(client,h,'CRM','Summary',conversation_id=chat)
    assert not result['result'].get('dashboard_query') and 'Choose a saved dashboard' not in str(result.get('plan'))


def test_model_dashboard_answer_cannot_drop_pinned_source_citations(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,_,_=setup_suite(client,db);_,dashboard=sample(client,db,h)
    monkeypatch.setattr(suite,'generate_json',lambda *args,**kwargs:{'summary':'USD total 300 without source support','steps':[]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Analyze dashboard #{dashboard}'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='failed' and not response.json()['result'].get('citations')
