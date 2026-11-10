from tests.rich_text_test_utils import organization_context
from uuid import uuid4
import pytest
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare
from app.ai_operator.query_models import NlpQuery

ROOT='/api/v1/ai-operator/suite'


def submit(client,h,text='CRM: show all leads',**extra):
    body={'request_key':str(uuid4()),'provider':'local','text':text,**extra}
    response=client.post(ROOT+'/commands',headers=h,json=body)
    assert response.status_code==200,response.text
    return body,response.json()


def test_capture_redaction_voice_idempotency_and_conflicts(client,db):
    h,user,_,_=setup_suite(client,db)
    secret='sk-'+('z'*40)
    body,result=submit(client,h,f'CRM: search leads for private@example.com api_key={secret}',input_mode='voice')
    row=db.query(NlpQuery).one()
    assert 'private@example.com' not in row.query_text and secret not in row.query_text
    assert row.input_mode=='voice' and row.suite_run_id==result['id'] and row.review_status=='pending'
    assert client.post(ROOT+'/commands',headers=h,json=body).status_code==200
    assert db.query(NlpQuery).count()==1
    assert client.post(ROOT+'/commands',headers=h,json={**body,'text':'CRM: show deals'}).status_code==409
    assert db.query(NlpQuery).one().outcome==result['status']


def test_customer_admin_cannot_review_or_export_training_queries(client,db):
    h,user,_,_=setup_suite(client,db)
    submit(client,h)
    row=db.query(NlpQuery).one()
    for path in ['/nlp-queries','/nlp-queries/training/export']:
        assert client.get(ROOT+path,headers=h).status_code==403
    assert client.put(ROOT+f'/nlp-queries/{row.id}',headers=h,json={'revision':1,'decision':'approved'}).status_code==403
    assert client.delete(ROOT+f'/nlp-queries/{row.id}',headers=h).status_code==403
    db.refresh(row)
    assert row.review_status=='pending' and row.training_text is None


def test_rejected_provider_requests_are_captured_but_structured_forms_are_not(client,db):
    h,user,_,_=setup_suite(client,db)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'openai','text':'CRM: show leads','module':'CRM'})
    assert response.status_code==409,response.text
    row=db.query(NlpQuery).one();assert row.outcome=='rejected' and row.error_code=='HTTP_409' and row.suite_run_id is None
    prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Structured form'}}])
    assert db.query(NlpQuery).count()==1


def test_other_user_cannot_read_review_or_export_private_query(client,db):
    from ai_test_utils import auth_headers
    h,_,_,_=setup_suite(client,db);submit(client,h)
    row=db.query(NlpQuery).one()
    other,_=auth_headers(client,db,email=f'nlp-other-{uuid4()}@example.com',permissions=['ai_assistant'])
    listing=client.get(ROOT+'/nlp-queries',headers=other)
    assert listing.status_code==403,listing.text
    assert client.get(ROOT+'/nlp-queries/training/export',headers=other).status_code==403
    assert client.put(ROOT+f'/nlp-queries/{row.id}',headers=other,json={'revision':1,'decision':'rejected'}).status_code==403


@pytest.mark.parametrize('value,absent',[
 ('email user@example.com password=longSecret','longSecret'),
 ('CRM: create task "Customer Alice salary 12345"','Customer Alice'),
 ('CRM: add note to lead #54: private note','private note'),
])
def test_training_sanitizer_removes_payloads_and_obvious_private_values(value,absent):
    from app.ai_operator.query_memory import sanitize
    assert absent not in sanitize(value)
