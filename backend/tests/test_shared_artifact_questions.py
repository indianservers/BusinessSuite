import json
from uuid import uuid4
import pytest
from tests.test_artifact_shares import source,review,publish,S
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_bot_artifacts import command,execute,A
from tests.test_agent_library import member
from tests.test_saved_agents import profile
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


@pytest.mark.parametrize('kind',['document','checklist','table','presentation'])
def test_recipients_can_ask_local_questions_with_only_published_snapshot_citations(client,db,kind):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    ident=source(client,db,owner,kind);share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Shared questions'}).json()['id']
    answer=command(client,h,'CRM',f'Analyze shared artifact #{share["id"]}',conversation_id=chat)
    assert answer['status']=='answered',answer
    assert answer['result']['citations'][0]['id']==f'shared-artifact:{share["id"]}:e1'
    assert 'shared-artifact-' in answer['result']['citations'][0]['href'] and not answer['receipts'] and answer['approval_id'] is None
    assert client.get(A+f'/{ident}',headers=h).status_code==404
    if kind=='table':
        assert 'sum 300' in answer['plan']['summary'] and 'sum 50' in answer['plan']['summary']
        filtered=command(client,h,'CRM','Only North',conversation_id=chat)
        assert filtered['status']=='answered' and 'sum 100' in filtered['plan']['summary']
        assert client.post(ROOT+f'/conversations/{chat}/resume',headers=h).status_code==200
        reset=command(client,h,'CRM','Clear the filter',conversation_id=chat);assert 'sum 300' in reset['plan']['summary']
    forbidden=client.post(ROOT+'/commands',headers=owner,json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
        'text':f'Analyze shared artifact #{share["id"]}'})
    assert forbidden.status_code==200


def test_shared_followups_reject_revoked_or_stale_editions_and_allow_explicit_current_read(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner,'table')
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Edition follow-ups'}).json()['id']
    command(client,h,'CRM',f'Analyze shared artifact #{share["id"]}',conversation_id=chat)
    execute(client,db,owner,command(client,owner,'CRM',f'Edit artifact #{ident}: Replace row 2: South, 900, USD'))
    publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]},share_id=share['id'],revision=1,source_revision=2))
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':chat,'text':'Only North'})
    assert response.status_code==409,response.text
    fresh=command(client,h,'CRM',f'Analyze shared artifact #{share["id"]}',conversation_id=chat)
    assert fresh['status']=='answered' and 'sum 1000' in fresh['plan']['summary']
    assert client.post(S+f'/{share["id"]}/revoke',headers=owner,json={'revision':2}).status_code==200
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':chat,'text':'Only North'})
    assert response.status_code==404,response.text


def test_shared_citations_are_rechecked_before_reviewed_writes(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner)
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    plan={'summary':'Review independent sourced notes','source_ids':[f'shared-artifact:{share["id"]}:e1'],
        'steps':[{'tool':'crm.create_artifact','payload':{'title':'Sourced notes','content':'Approved public wording.'}}]}
    run=command(client,h,'CRM','Prepare sourced notes',context=[{'tool':'crm.shared_artifact','payload':{'share_id':share['id'],'edition':1}}],local_plan=plan)
    assert run['status']=='awaiting_approval',run
    client.post(S+f'/{share["id"]}/revoke',headers=owner,json={'revision':1})
    blocked=client.post(ROOT+f'/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    assert blocked.status_code==404,blocked.text


def test_shared_dashboard_answers_are_scoped_by_panel_and_agent_modules(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db)
    ident=source(client,db,owner,'table')
    dashboard=execute(client,db,owner,command(client,owner,'CRM',f'Create dashboard called Shared overview: artifact #{ident} v1 as chart'))['receipts'][0]['artifact_id']
    share=publish(client,owner,review(client,owner,dashboard,{'kind':'members','member_ids':[user.id]}))
    agent=profile(client,h,tools=['crm.shared_artifact'])
    answer=command(client,h,'CRM',f'Analyze panel 1 of shared artifact #{share["id"]}',agent_id=agent['id'])
    assert answer['status']=='answered' and 'sum 300' in answer['plan']['summary'],answer
    assert answer['result']['citations'][0]['id']==f'shared-artifact:{share["id"]}:e1:p1'
    blocked=profile(client,h,tools=['crm.create_task'])
    assert command(client,h,'CRM',f'Analyze shared artifact #{share["id"]}',agent_id=blocked['id'])['status']=='failed'


def test_gemini_shared_answer_uses_read_only_tools_and_omits_prior_assistant_assertions(client,db,monkeypatch):
    from app.ai_operator import suite
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner,'table')
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Provider shared sources'}).json()['id']
    command(client,h,'CRM',f'Analyze shared artifact #{share["id"]}',conversation_id=chat)
    def generated(db,user,config,**kwargs):
        prompt=json.loads(kwargs['prompt'])
        assert all(t['name'].endswith('.shared_artifact') and not t['approval_required'] for t in prompt['tools'])
        assert 'sum 300' not in str(prompt['conversation_newest_first'])
        packet=prompt['authorized_context'][0]['records'];assert packet['analysis']['panels'][0]['statistics']['sum']=='100'
        return {'summary':'The authorized shared USD snapshot totals 100 for North.','steps':[],'source_ids':[packet['source_citation']['id']]}
    monkeypatch.setattr(suite,'generate_json',generated)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','conversation_id':chat,'text':'Only North'})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='answered',run


def test_shared_lineage_is_retained_in_prefixed_and_delegated_evidence(client,db):
    from app.ai_operator.shared_artifact_questions import lineage,revalidate
    from fastapi import HTTPException
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner)
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    canonical=f'shared-artifact:{share["id"]}:e1'
    sources=[{'id':'w8:step1:answer','shared_sources':[canonical]},{'id':'w8:step2:'+canonical}]
    assert lineage(sources)==[canonical]
    revalidate(db,user,sources)
    client.post(S+f'/{share["id"]}/revoke',headers=owner,json={'revision':1})
    with pytest.raises(HTTPException):revalidate(db,user,sources)


def test_revocation_during_provider_generation_blocks_the_stale_answer(client,db,monkeypatch):
    from app.ai_operator import suite,artifact_shares
    from app.shared.models import ServicePolicy
    owner,_,_,_=setup_suite(client,db);ident=source(client,db,owner,'table')
    share=publish(client,owner,review(client,owner,ident,{'kind':'organization'}))
    def generated(db,user,config,**kwargs):
        row=db.get(ServicePolicy,share['id']);row.values_json={**row.values_json,'status':'revoked','definition':None,'pending':None}
        row.version+=1;artifact_shares.sign(row);db.commit()
        return {'summary':'Old total 300 must not escape after revocation.','steps':[],'source_ids':[f'shared-artifact:{share["id"]}:e1']}
    monkeypatch.setattr(suite,'generate_json',generated)
    response=client.post(ROOT+'/commands',headers=owner,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Analyze shared artifact #{share["id"]}'})
    assert response.status_code==200,response.text
    run=response.json();assert run['status']=='failed' and 'Old total' not in str(run.get('plan'))


def test_missing_shared_id_collects_one_followup_without_reading_private_sources(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner,'table')
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Choose publication'}).json()['id']
    question=command(client,h,'CRM','Analyze shared artifact',conversation_id=chat)
    assert question['status']=='needs_clarification' and question['result']['shared_query']['awaiting_share']
    answer=command(client,h,'CRM',str(share['id']),conversation_id=chat)
    assert answer['status']=='answered' and 'sum 300' in answer['plan']['summary'],answer


def test_model_read_rounds_cannot_switch_to_a_different_shared_publication(client,db,monkeypatch):
    from app.ai_operator import suite
    owner,_,_,_=setup_suite(client,db);ident=source(client,db,owner,'table')
    first=publish(client,owner,review(client,owner,ident,{'kind':'organization'}))
    other=publish(client,owner,review(client,owner,ident,{'kind':'organization'}))
    calls=[]
    def generated(*args,**kwargs):
        calls.append(1)
        return {'summary':'Try an unrelated publication','steps':[],'context_requests':[{'tool':'crm.shared_artifact','payload':{'share_id':other['id']}}]}
    monkeypatch.setattr(suite,'generate_json',generated)
    response=client.post(ROOT+'/commands',headers=owner,json={'request_key':str(uuid4()),'provider':'gemini','module':'CRM','text':f'Analyze shared artifact #{first["id"]}'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='failed' and len(calls)==1


def test_shared_title_resolves_only_authorized_publications(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);outside,_=member(client,db)
    ident=source(client,db,owner,'table')
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    answer=command(client,h,'CRM','Analyze shared report called "regional amounts"')
    assert answer['status']=='answered' and 'sum 300' in answer['plan']['summary'],answer
    assert answer['result']['citations'][0]['id']==f'shared-artifact:{share["id"]}:e1'
    hidden=command(client,outside,'CRM','Analyze shared report called Regional amounts')
    assert hidden['status']=='needs_clarification' and not hidden['result']['shared_query']['choices']
    assert str(share['id']) not in str(hidden['plan']['question'])


def test_ambiguous_shared_title_uses_persistent_ordinal_and_rechecks_revocation(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner,'table')
    first=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    second=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Choose report by title'}).json()['id']
    question=command(client,h,'CRM','Summarize shared artifact named Regional',conversation_id=chat)
    assert question['status']=='needs_clarification' and question['result']['shared_query']['choices']==[second['id'],first['id']],question
    assert client.post(ROOT+f'/conversations/{chat}/resume',headers=h).status_code==200
    answer=command(client,h,'CRM','the second one',conversation_id=chat)
    assert answer['status']=='answered' and answer['result']['citations'][0]['id']==f'shared-artifact:{first["id"]}:e1'
    command(client,h,'CRM','Analyze shared report named Regional',conversation_id=chat)
    client.post(S+f'/{second["id"]}/revoke',headers=owner,json={'revision':1})
    denied=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':chat,'text':'first'})
    assert denied.status_code==404,denied.text


def test_title_discovery_respects_agent_tools_before_disclosing_choices(client,db):
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner,'table')
    publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    blocked=profile(client,h,tools=['crm.create_task'])
    question=command(client,h,'CRM','Analyze shared report named Regional',agent_id=blocked['id'])
    assert question['status']=='needs_clarification' and question['result']['shared_query']['choices']==[],question
    agent=profile(client,h,tools=['crm.shared_artifact'])
    answer=command(client,h,'CRM','Analyze shared report named Regional',agent_id=agent['id'])
    assert answer['status']=='answered',answer


def test_title_discovery_does_not_replace_a_pending_action_draft(client,db):
    owner,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=owner,json={'title':'Pending draft'}).json()['id']
    pending=command(client,owner,'CRM','Create document called Draft: Review before publishing.',conversation_id=chat)
    assert pending['status']=='awaiting_approval'
    response=client.post(ROOT+'/commands',headers=owner,json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
        'conversation_id':chat,'text':'Analyze shared report named Regional'})
    assert response.status_code==409,response.text
    assert client.get(ROOT+f'/runs/{pending["id"]}',headers=owner).json()['status']=='awaiting_approval'


def test_title_search_reaches_older_pages_and_prefers_exact_authorized_match(client,db):
    from copy import deepcopy
    from app.shared.models import ServicePolicy
    from app.ai_operator import artifact_shares
    owner,_,_,_=setup_suite(client,db);h,user=member(client,db);ident=source(client,db,owner,'table')
    old=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    template=db.get(ServicePolicy,old['id'])
    for index in range(201):
        values=deepcopy(template.values_json)
        values['definition']['root']['body']['title']='Regional amounts draft'
        if index!=200:values['audience']={'kind':'members','member_ids':[template.updated_by],'team_ids':[]}
        row=ServicePolicy(scope_key='test-old-share:'+str(uuid4()),organization_id=template.organization_id,
            module_key=template.module_key,kind=template.kind,version=1,updated_by=template.updated_by,values_json=values)
        db.add(row);db.flush();artifact_shares.sign(row)
    db.commit()
    listed=client.get(S,headers=h).json()['items']
    assert all(v['id']!=old['id'] for v in listed)
    answer=command(client,h,'CRM','Analyze shared report named Regional amounts')
    assert answer['status']=='answered',answer
    assert answer['result']['citations'][0]['id']==f'shared-artifact:{old["id"]}:e1'
