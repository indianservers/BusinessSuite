from types import SimpleNamespace

import pytest

from app.ai_operator.local_writing import classify, draft, chat_plan, model
from app.ai_operator.writing_corpus import SKILLS, examples


@pytest.mark.parametrize('skill', list(SKILLS))
def test_every_direct_skill_preserves_source_and_never_claims_execution(skill):
    source = 'Review renewal R-742. Amount INR 12750 is pending. Maya will confirm delivery by 2030-06-20.'
    result = draft(skill, source, recipient='Asha', title='Renewal R-742')
    assert result['cloud_calls'] == 0
    assert result['action'] == skill
    assert result['text'].strip()
    if skill != 'action_items':
        assert '12750' in result['text']
    assert '2030-06-20' in result['text']
    assert result['source_characters'] == len(source)


def test_training_fit_and_existing_action_corpus_remain_separate():
    assert len(model()['examples']) == 102
    for row in examples():
        assert classify(row['text']) == row['intent'], row
    from app.ai_operator.local_corpus import examples as action_examples
    assert not [(r['text'], classify(r['text'])) for r in action_examples() if classify(r['text'])]
    for command in ['Draft invoice for Acme', 'Draft task named Review terms', 'Write note for lead #1', 'Create a task checklist', 'Send invoice email']:
        assert classify(command) is None, command


@pytest.mark.parametrize('command,skill', [
    ('Please draft a client email','client_email'),
    ('Write a follow up email to the customer','follow_up'),
    ('Prepare an invoice covering email','invoice_email'),
    ('Summarise these meeting notes','meeting_summary'),
    ('Write a supplier enquiry','supplier_enquiry'),
    ('Draft a welcome message for a new employee','onboarding'),
])
def test_held_out_writing_phrases(command, skill):
    assert classify(command) == skill


@pytest.mark.parametrize('naming',['called','named','titled'])
def test_named_customer_follow_up_routes_to_record_creation(naming):
    from app.ai_operator.workflows import local_plan
    title='Review the distributor renewal'
    text=f'Prepare a fresh customer follow-up {naming} {title}'
    assert classify(text) is None
    assert chat_plan(text) is None
    data=SimpleNamespace(text=text,module='CRM',project_id=None,
        request_key='named-follow-up-regression',timezone='Asia/Kolkata')
    plan,_=local_plan(data,None,None)
    assert not plan.get('question')
    assert len(plan['steps'])==1
    assert plan['steps'][0]['tool']=='crm.create_task'
    assert plan['steps'][0]['payload']['title']==title


def test_customer_follow_up_email_still_routes_to_writing():
    text='Prepare a customer follow-up email'
    assert classify(text)=='follow_up'
    plan=chat_plan(text+': Renewal review is due Friday.')
    assert not plan.get('question') and not plan['steps']
    assert 'Friday' in plan['summary']


def test_writing_chat_skill_is_read_only_and_leaves_pending_workflow_unchanged():
    from app.ai_operator.workflows import local_plan
    source='Draft client email: Renewal R-742 is pending review Friday.'
    data=SimpleNamespace(text=source,module='CRM',timezone='Asia/Kolkata')
    plan,state=local_plan(data,None,None)
    assert not plan['steps'] and state is None
    assert 'R-742' in plan['summary']
    assert chat_plan('Draft client email')['question']


def test_missing_facts_and_translation_are_explicit():
    result=draft('payment_reminder')
    assert len(result['missing_details']) == 2
    assert '[invoice reference]' in result['text']
    result=draft('translate','Hello Asha',language='Hindi')
    assert result['text'] == 'Hello Asha'
    assert 'no translation was produced' in result['missing_details'][0]


def test_writing_endpoint_authorization_validation_and_zero_business_writes(client,db):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator import isolate_generic_http_audit
    from app.apps.crm.models import CRMTask
    from app.ai_operator.models import OperatorApiLog
    h,user,_,_=setup_suite(client,db)
    before=db.query(CRMTask).count()
    url='/api/v1/ai-operator/writing/draft'
    payload={'module':'CRM','action':'client_email','text':'Renewal R-742 pending Friday.','recipient':'Asha'}
    response=client.post(url,headers=h,json=payload)
    assert response.status_code == 200,response.text
    assert 'Hello Asha' in response.json()['text']
    assert 'R-742' in response.json()['text']
    assert client.post(url,headers={'Authorization':'Bearer invalid'},json=payload).status_code in {401,403}
    assert client.post(url,headers=h,json={**payload,'action':'send_email'}).status_code == 422
    assert client.post(url,headers=h,json={**payload,'text':'x'*16001}).status_code == 422
    assert client.post(url,headers=h,json={**payload,'organization_id':999}).status_code == 422
    assert db.query(CRMTask).count() == before
    assert db.query(OperatorApiLog).count() == 0


def test_writing_endpoint_requires_current_module_access(client,db):
    from ai_test_utils import auth_headers
    headers,_=auth_headers(client,db,email='writing-restricted@example.com',permissions=['ai_assistant'])
    response=client.post('/api/v1/ai-operator/writing/draft',headers=headers,json={'module':'CRM','action':'client_email','text':'Hello'})
    assert response.status_code == 403,response.text


@pytest.mark.parametrize('provider',['gemini','openai','claude'])
def test_cloud_writing_uses_existing_scoped_gateway_and_stays_a_draft(client,db,monkeypatch,provider):
    import json
    from tests.test_ai_operator import setup_operator,mock_provider
    from app.ai_operator.models import OperatorApiLog
    from app.apps.crm.models import CRMTask
    h,user,_,_=setup_operator(client,db,provider=provider)
    user.is_superuser=True;db.commit()
    calls=mock_provider(monkeypatch,{'text':'Review R-742 on Friday.','subject':'R-742','missing_details':[]})
    before=db.query(CRMTask).count()
    response=client.post('/api/v1/ai-operator/writing/draft',headers=h,json={
        'module':'CRM','action':'improve','provider':provider,'text':'Review R-742 on Friday.'})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['method']=='server-language-model' and result['cloud_calls']==1
    assert result['text']=='Review R-742 on Friday.'
    assert len(calls)==1 and 'R-742' in json.dumps(json.loads(calls[0].content))
    log=db.query(OperatorApiLog).filter_by(user_id=user.id,purpose='writing').one()
    assert log.provider==provider and log.module=='CRM' and log.status=='success'
    assert db.query(CRMTask).count()==before
    assert 'unit-test-secret-key' not in response.text


def test_local_writing_never_falls_back_to_a_connected_cloud_provider(client,db,monkeypatch):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator import mock_provider
    h,_,_,_=setup_suite(client,db)
    calls=mock_provider(monkeypatch,{})
    response=client.post('/api/v1/ai-operator/writing/draft',headers=h,json={
        'module':'CRM','action':'translate','text':'Hello Asha','language':'Hindi'})
    assert response.status_code==200,response.text
    assert response.json()['cloud_calls']==0 and response.json()['missing_details']
    assert not calls


@pytest.mark.parametrize('output',[{'text':'Sent to everyone','subject':'Done','missing_details':[],'tools':['send']}, {'text':'','subject':'','missing_details':[]}])
def test_cloud_writing_rejects_invalid_output_without_using_local_fallback(client,db,monkeypatch,output):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator import mock_provider
    from app.ai_operator.models import OperatorApiLog
    h,user,_,_=setup_suite(client,db)
    calls=mock_provider(monkeypatch,output)
    response=client.post('/api/v1/ai-operator/writing/draft',headers=h,json={
        'module':'CRM','action':'improve','provider':'gemini','text':'Review R-742.'})
    assert response.status_code==502,response.text
    assert len(calls)==1
    assert db.query(OperatorApiLog).filter_by(user_id=user.id,purpose='writing').one().status=='failed'


def test_writing_provider_scope_cannot_fall_back_from_a_disabled_workspace_override(client,db,monkeypatch):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator import mock_provider
    from app.ai_operator.models import OperatorProvider
    h,user,_,_=setup_suite(client,db)
    created=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Writing override QA'})
    assert created.status_code==201,created.text
    workspace=created.json()['id']
    db.add(OperatorProvider(scope_key=f'workspace:{workspace}',provider='gemini',model='blocked',encrypted_key='unused',enabled=False,data_sharing_allowed=False,updated_by=user.id));db.commit()
    calls=mock_provider(monkeypatch,{})
    response=client.post('/api/v1/ai-operator/writing/draft',headers=h,json={
        'module':'PMS','workspace_id':workspace,'action':'improve','provider':'gemini','text':'Review R-742.'})
    assert response.status_code==409,response.text
    assert not calls


def test_writing_provider_failure_has_one_attempt_and_no_silent_fallback(client,db,monkeypatch):
    from tests.test_suite_operator import setup_suite
    from tests.test_ai_operator import mock_provider
    h,_,_,_=setup_suite(client,db)
    calls=mock_provider(monkeypatch,{},status=429)
    response=client.post('/api/v1/ai-operator/writing/draft',headers=h,json={
        'module':'CRM','action':'improve','provider':'gemini','text':'Review R-742.'})
    assert response.status_code==502,response.text
    assert response.json()['detail']=='PROVIDER_HTTP_429'
    assert len(calls)==1
    assert 'unit-test-secret-key' not in response.text
