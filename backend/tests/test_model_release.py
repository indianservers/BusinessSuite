import json
import pytest
from app.ai_operator import model_release as release

@pytest.fixture
def candidate(tmp_path,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'PLATFORM_SECRET_KEY','release-test-key-that-is-at-least-32-characters')
    monkeypatch.setattr('app.ai_operator.local_tensorflow.validate',lambda value:{'training_scope':{'platform':True}})
    monkeypatch.setattr('app.ai_operator.dialogue_tensorflow.read',lambda *args:None)
    root=tmp_path/'platform';folder=root/'runs/1/model';folder.mkdir(parents=True)
    for name in release.FILES:(folder/name).write_text('{}' if name.endswith('.json') else 'synthetic test artifact')
    def write(name,value):(folder/name).write_text(json.dumps(value))
    write('evaluation.json',{'modules':{module:{'training_commands':1200,'training_accuracy':1.0,'internal_validation_accuracy':.95,'portable_max_error':1e-7} for module in ('CRM','PMS','HRMS')}})
    write('dialogue-evaluation.json',{'heldout_accuracy':.9,'portable_max_error':1e-7})
    write('conversation-evaluation.json',{'total':684,'passed':684,'failures':[]})
    write('unseen-dialogue-evaluation.json',{'total':120,'passed':96})
    write('action-release-evaluation.json',{'tests':26,'failures':0,'errors':0,'skipped':0,'model_sha256':release.file_hash(folder/'bundle.json'),'dialogue_sha256':release.file_hash(folder/'dialogue.json')})
    return root,folder,write

def test_signed_release_requires_all_checks_and_detects_tampered_artifacts(candidate):
    root,folder,write=candidate
    gate=release.seal(folder,1,'dataset-digest')
    assert gate['passed']
    assert release.verify(folder,1)['dataset_sha256']=='dataset-digest'
    release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==1
    write('dialogue.json',{'changed':True})
    with pytest.raises(ValueError):release.verify(folder,1)

def test_release_blocks_failed_safety_tests_and_weak_holdout_without_changing_pointer(candidate):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':99}))
    write('unseen-dialogue-evaluation.json',{'total':120,'passed':50})
    gate=release.seal(folder,1,'dataset-digest')
    assert not gate['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==99

def test_forged_gate_flags_and_skipped_tests_cannot_release(candidate):
    _,folder,write=candidate
    write('action-release-evaluation.json',{'tests':26,'failures':0,'errors':0,'skipped':1,'model_sha256':release.file_hash(folder/'bundle.json'),'dialogue_sha256':release.file_hash(folder/'dialogue.json')})
    assert not release.seal(folder,1,'dataset-digest')['passed']
    value=json.loads((folder/'release.json').read_text());value['gate']['passed']=True
    (folder/'release.json').write_text(json.dumps(value))
    with pytest.raises(ValueError):release.verify(folder,1)

def test_regression_gate_uses_separate_active_scores(candidate):
    _,folder,_=candidate
    gate=release.assess(folder,{'scores':{'dialogue_development':.96,'unseen_dialogue':.9}})
    assert not gate['passed'] and any(c['name'].startswith('Regression') and not c['passed'] for c in gate['checks'])

def test_release_binding_rejects_wrong_job_and_signature(candidate):
    _,folder,_=candidate
    release.seal(folder,1,'dataset-digest')
    with pytest.raises(ValueError):release.verify(folder,2)
    value=json.loads((folder/'release.json').read_text());value['signature']='0'*64
    (folder/'release.json').write_text(json.dumps(value))
    with pytest.raises(ValueError):release.verify(folder,1)
