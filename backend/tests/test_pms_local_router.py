"""Server-only advisory classification, integrity and authenticated API guards."""
import hashlib
import json
import struct
import pytest
from app.ai_operator import pms_local_router as router


@pytest.fixture
def numeric_model(tmp_path,monkeypatch):
    raw=json.dumps({'userDefinedMetadata':{'vocabulary':['set','priority','high'],
        'intents':['priority_high','fallback'],'trainingExamples':4,'threshold':.9,'margin':.35}}).encode()
    weights=struct.pack('<8f',0,0,0,0,5,0,0,0)
    for name,value in [('model.json',raw),('weights.bin',weights)]:
        (tmp_path/name).write_bytes(value)
    monkeypatch.setattr(router,'directory',lambda:tmp_path)
    monkeypatch.setattr(router,'HASHES',{'model.json':hashlib.sha256(raw).hexdigest(),'weights.bin':hashlib.sha256(weights).hexdigest()})
    return tmp_path


def test_numeric_forward_pass_and_unknown_word_abstention(numeric_model):
    result=router.classify(['set priority high','set priority high gibberish'])
    first,second=result['predictions']
    assert first['intent']=='priority_high' and first['accepted']
    assert first['confidence']==pytest.approx(.993307149,abs=1e-8)
    assert not second['accepted'] and result['cloud_calls']==0


def test_integrity_rechecked_after_a_cached_success(numeric_model):
    router.classify(['set priority high'])
    (numeric_model/'weights.bin').write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'):router.classify(['set priority high'])


@pytest.mark.parametrize('text,expected',[
    ('assign tasks to qa@example.test',['assign','tasks','to','slotuser']),
    ('key ABC-13',['key','slotkey']),
    ('set due date to 2030-12-25',['set','due','date','to','slotdate']),
    ('"cancel all drafts"',['slottext']),
    ('priority １２３',['priority']),
])
def test_tokens_preserve_tensorflow_js_contract(text,expected):
    assert router.tokens(text)==expected


def test_classifier_http_is_scoped_and_performs_no_action_or_cloud_call(client,db,monkeypatch,numeric_model):
    from tests.test_suite_operator import setup_suite
    from app.apps.project_management.models import PMSTask
    from app.ai_operator.models import OperatorApiLog
    h,_,_,_=setup_suite(client,db)
    def forbidden(*args,**kwargs):raise AssertionError('Classification must not invoke a provider')
    monkeypatch.setattr('app.ai_operator.providers.generate_json',forbidden)
    before=db.query(PMSTask).count()
    response=client.post('/api/v1/ai-operator/suite/pms-routing/classify',headers=h,json={'texts':['set priority high']})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['runtime']=='server' and result['predictions'][0]['accepted']
    assert 'vocabulary' not in response.text and 'weights' not in response.text
    assert db.query(PMSTask).count()==before and db.query(OperatorApiLog).count()==0
    (numeric_model/'weights.bin').write_bytes(b'changed')
    response=client.post('/api/v1/ai-operator/suite/pms-routing/classify',headers=h,json={'texts':['set priority high']})
    assert response.status_code==503,response.text
    assert 'no cloud request' in response.json()['detail']


@pytest.mark.parametrize('body',[{'texts':[]},{'texts':['x']*76},{'texts':[' ']},{'texts':['x'*4001]},{'texts':['x'*4000]*4},{'texts':['high'],'weights':[]},{'texts':[17]}])
def test_classifier_rejects_unbounded_and_untyped_input(body):
    from app.ai_operator.local_api import PmsClassifyInput
    with pytest.raises(ValueError):PmsClassifyInput.model_validate(body)


def test_classifier_requires_authentication_and_current_module_access(client,db):
    from ai_test_utils import auth_headers
    url='/api/v1/ai-operator/suite/pms-routing/classify'
    response=client.post(url,json={'texts':['set priority high']})
    assert response.status_code in {401,403}
    h,_=auth_headers(client,db,email='routing-restricted@example.com',permissions=['ai_assistant'])
    response=client.post(url,headers=h,json={'texts':['set priority high']})
    assert response.status_code==403,response.text
