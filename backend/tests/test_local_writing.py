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
