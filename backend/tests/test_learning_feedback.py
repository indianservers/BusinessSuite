from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from app.ai_operator.query_models import NlpQuery
from app.apps.crm.models import CRMTask
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/suite'

def test_feedback_is_private_redacted_idempotent_and_never_a_training_approval(client,db):
    h,user,_,_=setup_suite(client,db)
    response=client.post(ROOT+'/commands',headers=h,json={'text':'CRM: what are todays jobs','provider':'local','request_key':str(uuid4())})
    assert response.status_code==200,response.text
    ident=response.json()['id']
    payload={'request_key':str(uuid4()),'rating':'needs_correction','correction':'Contact me at private@example.com with Bearer abcdefghijk-secret','revision':0}
    saved=client.post(f'{ROOT}/runs/{ident}/feedback',headers=h,json=payload)
    assert saved.status_code==200,saved.text
    feedback=saved.json()['result']['feedback']
    assert feedback['training_approved'] is False and feedback['needs_review'] is True
    assert 'private@example.com' not in feedback['correction'] and 'abcdefghijk-secret' not in feedback['correction']
    retry=client.post(f'{ROOT}/runs/{ident}/feedback',headers=h,json=payload)
    assert retry.status_code==200 and retry.json()['result']['feedback']['revision']==1
    assert db.query(NlpQuery).filter_by(suite_run_id=ident).one().review_status=='pending'
    assert db.query(CRMTask).count()==0
    assert client.post(f'{ROOT}/runs/{ident}/feedback',headers=h,json={**payload,'request_key':str(uuid4())}).status_code==409
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.post(f'{ROOT}/runs/{ident}/feedback',headers=other,json=payload).status_code==404

def test_helpful_feedback_does_not_approve_a_pending_action(client,db):
    h,_,_,_=setup_suite(client,db)
    draft=client.post(ROOT+'/commands',headers=h,json={'text':'CRM: create task "Feedback test"','provider':'local','request_key':str(uuid4())}).json()
    saved=client.post(f'{ROOT}/runs/{draft["id"]}/feedback',headers=h,json={'request_key':str(uuid4()),'rating':'helpful','revision':0})
    assert saved.status_code==200 and saved.json()['status']=='awaiting_approval'
    assert db.query(CRMTask).count()==0
