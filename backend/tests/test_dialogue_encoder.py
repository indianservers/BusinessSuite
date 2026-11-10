import json
import os
from pathlib import Path
import pytest
from app.ai_operator.dialogue_corpus import VERSION,LEGACY_VERSION,features,turns
from app.ai_operator.dialogue_unseen import cases
from app.ai_operator.dialogue_tensorflow import read


def test_new_encoder_has_reply_subword_features_and_explicit_context():
    value=features('CRM','tasks.create','title','Review onboarding')
    assert value['m:crm']==1 and value['i:tasks_create']==1 and value['p:title']==1
    assert value['w:onboarding']==1 and any(k.startswith('c:') for k in value)
    old=features('CRM','tasks.create','title','Review onboarding',LEGACY_VERSION)
    assert 'pending' in old and not any(k.startswith('c:') for k in old)


def test_future_platform_training_retains_module_baseline_without_merging_tenant_data():
    from app.ai_operator.expanded_corpus import with_platform_baseline
    from collections import Counter
    supplied=[{'module':'CRM','intent':'leads.list','text':'CRM: fetch prospect roster'}]
    combined=with_platform_baseline(supplied,{'platform':True})
    assert Counter(r['module'] for r in combined)=={'CRM':1201,'PMS':1200,'HRMS':1200}
    assert with_platform_baseline(supplied,{'company_id':1,'branch_id':1,'workspace_id':None})==supplied
    assert len(supplied)==1


def test_frozen_wording_is_separate_from_all_dialogue_training_and_selection_rows():
    def normalized(value):return ' '.join(value.casefold().split()).strip('.!?')
    seen={normalized(r['text']) for r in turns()}
    probes=cases()
    assert len(probes)==120 and len({normalized(r['text']) for r in probes})==120
    assert not seen&{normalized(r['text']) for r in probes}


def test_actual_new_dialogue_encoder_and_export_are_compatible(monkeypatch,tmp_path):
    folder=os.environ.get('ACTION_DIALOGUE_TEST_MODEL_DIR')
    if not folder:pytest.skip('Set ACTION_DIALOGUE_TEST_MODEL_DIR for real artifact validation')
    path=Path(folder)/'dialogue.json';stat=path.stat();value=read(str(path),stat.st_size,stat.st_mtime_ns)
    assert value['format']==VERSION
    from app.ai_operator.dialogue_tensorflow import predict
    monkeypatch.setenv('LOCAL_NLP_MODEL_DIR',folder);monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(tmp_path))
    result=predict('CRM','tasks.create','title','Review design and delivery')
    assert result['act']=='provide_value' and result['authorizes_execution'] is False


def test_existing_v1_exports_keep_their_original_feature_contract(monkeypatch,tmp_path):
    candidate=os.environ.get('ACTION_DIALOGUE_TEST_MODEL_DIR')
    if not candidate:pytest.skip('Set ACTION_DIALOGUE_TEST_MODEL_DIR for existing artifact checks')
    # Known previous release is optional outside this local workspace.
    older=Path(candidate).parents[1]/'216/model'
    if not (older/'dialogue.json').exists():pytest.skip('No previous local release available')
    monkeypatch.setenv('LOCAL_NLP_MODEL_DIR',str(older));monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(tmp_path))
    from app.ai_operator.dialogue_tensorflow import predict
    actual=predict('CRM','tasks.create','title','Review design and delivery')
    assert actual['engine']==LEGACY_VERSION and actual['act']=='provide_value'
