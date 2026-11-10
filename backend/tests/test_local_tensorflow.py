import json
import math
import os
from pathlib import Path

import pytest
from app.ai_operator.local_corpus import examples
from app.ai_operator import local_tensorflow as neural


@pytest.fixture(autouse=True)
def isolate_platform_activation(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(tmp_path/'training'))


def test_portable_dense_relu_softmax_math():
    value=neural.forward({0:1},{'w1':[[1,-1]],'b1':[0,0],'w2':[[1,0],[0,1]],'b2':[0,0]})
    assert value[0]==pytest.approx(math.e/(1+math.e))
    assert sum(value)==pytest.approx(1)


@pytest.mark.parametrize('body',[[],None,{'models':[]},{'models':{},'format':'wrong'}])
def test_incompatible_artifacts_fail_closed(body):
    with pytest.raises(ValueError):neural.validate(body)


def test_missing_and_malformed_artifacts_use_explicit_fallback(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCAL_NLP_MODEL_DIR',str(tmp_path))
    assert neural.load() is None and neural.status()['engine']=='retrieval-rules-fallback'
    (tmp_path/'bundle.json').write_text('[1,2,3]')
    assert neural.load() is None
    from app.ai_operator.local_nlp import parse
    assert parse('CRM: what are todays jobs').intent=='jobs.today'


def require_model():
    value=neural.load()
    if value is None:
        if os.environ.get('LOCAL_NLP_REQUIRE_MODEL')=='1':pytest.fail('Train the TensorFlow artifacts before the required-model suite')
        pytest.skip('Run train_tensorflow_local_nlp.py for trained artifact checks')
    return value


def test_actual_trained_models_fit_all_480_examples_and_are_current():
    value=require_model()
    assert value['training_commands']=={'CRM':120,'PMS':120,'Sales':120,'HRMS':120}
    assert neural.status()['active'] is True
    for row in examples():
        prediction=neural.predict(row['text'],row['module'])
        assert prediction['intent']==row['intent'],row


def test_neural_model_actually_selects_unseen_intents_and_rules_correct_filter_errors():
    require_model()
    from app.ai_operator.local_nlp import parse
    value=parse('CRM: show the lead records')
    assert value.intent=='leads.list' and value.neural['used'] is True
    value=parse('Sales: list outstanding customer invoices')
    assert value.intent=='invoices.unpaid'
    assert value.neural['used'] is False  # Explicit unpaid filter wins over raw model preference.


def test_corrupt_shapes_nonfinite_weights_and_stale_corpus_are_rejected():
    value=require_model()
    for mutation in ('corpus','shape','nan'):
        copy=json.loads(json.dumps(value))
        if mutation=='corpus':copy['corpus_sha256']='obsolete'
        elif mutation=='shape':copy['models']['CRM']['w1']=[]
        else:copy['models']['CRM']['w1'][0][0]=float('nan')
        with pytest.raises(ValueError):neural.validate(copy)
