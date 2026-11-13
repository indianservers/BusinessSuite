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


def test_fresh_workplace_failure_blocks_activation_and_keeps_previous_release(candidate):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':226}))
    write('conversation-evaluation.json',{'total':684,'passed':684,'failures':[],
        'workplace_actions_v2':{'total':150,'passed':149,'failures':[{'id':'workplace-v2-CRM-0-0'}]}})
    assert not release.seal(folder,1,'dataset-digest')['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==226


@pytest.mark.parametrize('common',[
    {'total':600,'passed':599,'by_module':{'PMS':199,'CRM':200,'HRMS':200},'failures':[{'id':'PMS-068'}]},
    {'total':600,'passed':600,'by_module':{'PMS':200,'CRM':200},'failures':[]},
])
def test_common_catalog_failure_or_missing_module_blocks_release(candidate,common):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':237}))
    write('conversation-evaluation.json',{'total':684,'passed':684,'failures':[],'common_actions':common})
    assert not release.seal(folder,1,'dataset-digest')['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==237


@pytest.mark.parametrize('scenario_passed,fit_passed',[(269,270),(270,269)])
def test_third_batch_cannot_activate_with_failed_scenario_or_training_draft(candidate,scenario_passed,fit_passed):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':230}))
    write('conversation-evaluation.json',{'total':684,'passed':684,'failures':[],
        'workplace_actions_v3':{'total':270,'passed':scenario_passed,'failures':[] if scenario_passed==270 else ['failed scenario'],
            'training_fit':{'total':270,'passed':fit_passed,'failures':[] if fit_passed==270 else ['wrong draft']}}})
    assert not release.seal(folder,1,'dataset-digest')['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==230


def test_fourth_batch_requires_every_new_training_draft_to_pass(candidate):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':233}))
    write('conversation-evaluation.json',{'total':684,'passed':684,'failures':[],
        'workplace_actions_v4':{'total':150,'passed':150,'failures':[],
            'training_fit':{'total':150,'passed':149,'failures':['wrong date direction']}}})
    assert not release.seal(folder,1,'dataset-digest')['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==233


def test_fifth_batch_failed_title_reference_blocks_activation(candidate):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':235}))
    write('conversation-evaluation.json',{'total':684,'passed':684,'failures':[],
        'workplace_actions_v5':{'total':150,'passed':149,'failures':['ambiguous title selected'],
            'training_fit':{'total':150,'passed':150,'failures':[]}}})
    assert not release.seal(folder,1,'dataset-digest')['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==235


@pytest.mark.parametrize('change',[None,{'database':'sqlite'},{'tests':57},{'failures':1},{'skipped':1},{'dialogue_sha256':'wrong'}])
def test_message_candidates_require_exact_postgres_execution_evidence(candidate,change):
    root,folder,write=candidate
    (root/'active.json').write_text(json.dumps({'job_id':239}))
    write('dialogue-evaluation.json',{'heldout_accuracy':.9,'portable_max_error':1e-7,'message_dialogue_version':'message-action-followups-v1','message_training_turns':300,'message_training_sha256':'a'*64})
    write('unseen-dialogue-evaluation.json',{'total':120,'passed':96,'message_followups':{'version':'message-action-probes-v1','total':60,'passed':54}})
    native=json.loads((folder/'action-release-evaluation.json').read_text())
    if change is not None:
        from scripts.evaluate_message_action_release import TESTS
        native['message_actions']={'format':'message-action-postgres-v1','database':'postgresql','test_files':list(TESTS),'tests':64,'failures':0,'errors':0,'skipped':0,
            'model_sha256':release.file_hash(folder/'bundle.json'),'dialogue_sha256':release.file_hash(folder/'dialogue.json'),**change}
    write('action-release-evaluation.json',native)
    assert not release.seal(folder,1,'dataset-digest')['passed']
    with pytest.raises(ValueError):release.pointer(root,1)
    assert json.loads((root/'active.json').read_text())['job_id']==239


def test_valid_message_candidate_seals_both_wording_and_postgres_evidence(candidate):
    root,folder,write=candidate
    from scripts.evaluate_message_action_release import TESTS
    write('dialogue-evaluation.json',{'heldout_accuracy':.9,'portable_max_error':1e-7,'message_dialogue_version':'message-action-followups-v1','message_training_turns':300,'message_training_sha256':'a'*64})
    write('unseen-dialogue-evaluation.json',{'total':120,'passed':96,'message_followups':{'version':'message-action-probes-v1','total':60,'passed':54}})
    native=json.loads((folder/'action-release-evaluation.json').read_text())
    native['message_actions']={'format':'message-action-postgres-v1','database':'postgresql','test_files':list(TESTS),'tests':64,'failures':0,'errors':0,'skipped':0,
        'model_sha256':release.file_hash(folder/'bundle.json'),'dialogue_sha256':release.file_hash(folder/'dialogue.json')}
    write('action-release-evaluation.json',native)
    assert release.seal(folder,1,'dataset-digest')['passed']
    release.pointer(root,1)
    native['message_actions']['skipped']=1;write('action-release-evaluation.json',native)
    with pytest.raises(ValueError):release.verify(folder,1)


@pytest.mark.parametrize('fresh_passed,allowed',[(None,False),(50,False),(54,True)])
def test_v2_message_models_require_the_fresh_wording_gate(candidate,fresh_passed,allowed):
    _,folder,write=candidate
    from scripts.evaluate_message_action_release import TESTS
    write('dialogue-evaluation.json',{'heldout_accuracy':.9,'portable_max_error':1e-7,'message_dialogue_version':'message-action-followups-v2','message_training_turns':450,'message_training_sha256':'a'*64})
    unseen={'total':120,'passed':96,'message_followups':{'version':'message-action-probes-v1','total':60,'passed':54}}
    if fresh_passed is not None:unseen['message_followups_validation']={'version':'message-action-probes-v2','total':60,'passed':fresh_passed}
    write('unseen-dialogue-evaluation.json',unseen)
    native=json.loads((folder/'action-release-evaluation.json').read_text())
    native['message_actions']={'format':'message-action-postgres-v1','database':'postgresql','test_files':list(TESTS),'tests':64,'failures':0,'errors':0,'skipped':0,
        'model_sha256':release.file_hash(folder/'bundle.json'),'dialogue_sha256':release.file_hash(folder/'dialogue.json')}
    write('action-release-evaluation.json',native)
    assert release.seal(folder,1,'dataset-digest')['passed'] is allowed



def test_existing_message_release_with_original_core_evidence_remains_compatible(candidate):
    _,folder,write=candidate
    write('dialogue-evaluation.json',{'heldout_accuracy':.9,'portable_max_error':1e-7,'message_dialogue_version':'message-action-followups-v1','message_training_turns':300,'message_training_sha256':'a'*64})
    write('unseen-dialogue-evaluation.json',{'total':120,'passed':96,'message_followups':{'version':'message-action-probes-v1','total':60,'passed':54}})
    native=json.loads((folder/'action-release-evaluation.json').read_text())
    native['message_actions']={'format':'message-action-postgres-v1','database':'postgresql','test_files':['tests/test_event_message_evidence.py','tests/test_suite_operator.py','tests/test_suite_conversations.py','tests/test_local_action_dialogue.py'],
        'tests':58,'failures':0,'errors':0,'skipped':0,'model_sha256':release.file_hash(folder/'bundle.json'),'dialogue_sha256':release.file_hash(folder/'dialogue.json')}
    write('action-release-evaluation.json',native)
    assert release.seal(folder,1,'dataset-digest')['passed']
    assert release.verify(folder,1)['gate']['passed']
