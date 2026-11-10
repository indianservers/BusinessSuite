"""Conversation isolation and trained next-turn inference, without real sends."""
from collections import Counter
import json
import os
from pathlib import Path
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_local_nlp_workflows import command
from app.ai_operator.dialogue_corpus import turns,conversations,features
from app.ai_operator.expanded_corpus import examples
from app.apps.crm.models import CRMTask


@pytest.mark.parametrize('text,intent',[
    ('PMS: give me a view of PMS tasks without assignees','tasks.unassigned'),
    ('PMS: set a start date for task #1 starting tomorrow','tasks.schedule'),
    ('PMS: prepare dates for task record #1 starting tomorrow','tasks.schedule'),
    ('PMS: set a start date for assigned task #1 starting tomorrow','tasks.schedule'),
    ('PMS: show me project tasks awaiting assignment','tasks.unassigned'),
    ('PMS: make PMS task record #1 priority to high','tasks.priority'),
    ('PMS: make PMS task item #1 status to done','tasks.status'),
    ('CRM: make CRM task record #1 priority to high','tasks.priority'),
    ('CRM: make CRM task item #1 status to done','tasks.status'),
    ('CRM: add a follow up note for lead #1: Customer requested a callback','note.create'),
])
def test_scheduling_and_negative_assignment_filters_do_not_become_other_actions(text,intent):
    from app.ai_operator.local_nlp import parse
    value=parse(text)
    assert value.intent==intent
    if intent=='tasks.schedule':assert value.slots['record_id']==1


def test_v2_counts_labels_and_evaluation_features_are_disjoint():
    rows=examples(60)
    assert Counter(r['module'] for r in rows)=={'PMS':1200,'CRM':1200,'HRMS':1200}
    assert set(Counter((r['module'],r['intent']) for r in rows).values())=={60}
    assert len({r['text'].casefold() for r in rows})==3600
    rows=turns();training=[r for r in rows if r['split']=='train']
    assert all(n>=1000 for n in Counter(r['module'] for r in training).values())
    def signature(r):return tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items()))
    trained={signature(r) for r in training}
    assert not any(signature(r) in trained for r in rows if r['split']=='test')
    assert Counter(r['kind'] for r in conversations())=={'single_request':180,'multiple_turns':180,'independent_conversations':180}


def test_interleaved_conversations_keep_slots_and_approvals_independent(client,db):
    h,user,project,task=setup_suite(client,db)
    first=command(client,h,'CRM: create a task')
    second=command(client,h,'CRM: create a task')
    a=command(client,h,'Call synthetic customer',parent_run_id=first['id'])
    b=command(client,h,'Review synthetic response',parent_run_id=second['id'])
    a2=command(client,h,'tomorrow',parent_run_id=a['id'])
    assert a2['plan']['steps'][0]['payload']['title']=='Call synthetic customer'
    assert b['plan']['steps'][0]['payload']['title']=='Review synthetic response'
    assert 'due_date' not in b['plan']['steps'][0]['payload']
    # A separate one-shot request does not inherit either pending title or date.
    fresh=command(client,h,'CRM: create task "Independent task"')
    assert fresh['plan']['steps'][0]['payload']=={'title':'Independent task'}
    approve(client,h,b);tick(client,db)
    assert db.query(CRMTask).one().title=='Review synthetic response'
    assert db.query(CRMTask).filter_by(title='Call synthetic customer').count()==0
    approve(client,h,a2);tick(client,db)
    assert db.query(CRMTask).count()==2


def test_invalid_followup_keeps_question_and_cancel_only_affects_that_chat(client,db):
    h,user,project,task=setup_suite(client,db)
    a=command(client,h,'CRM: create a task')
    b=command(client,h,'CRM: create task "Keep this draft"')
    cancelled=command(client,h,'do not proceed',parent_run_id=a['id'])
    assert cancelled['status']=='answered' and not cancelled['plan']['steps']
    approve(client,h,b);tick(client,db)
    assert db.query(CRMTask).one().title=='Keep this draft'


def candidate(monkeypatch,tmp_path):
    folder=os.environ.get('ACTION_DIALOGUE_TEST_MODEL_DIR')
    if not folder:pytest.skip('Set ACTION_DIALOGUE_TEST_MODEL_DIR to validate real trained artifacts')
    monkeypatch.setenv('LOCAL_NLP_MODEL_DIR',folder)
    monkeypatch.setenv('LOCAL_NLP_TRAINING_DIR',str(tmp_path/'training'))
    return Path(folder)


def test_real_trained_dialogue_model_parity_report_and_fail_closed(monkeypatch,tmp_path):
    folder=candidate(monkeypatch,tmp_path)
    from app.ai_operator.dialogue_tensorflow import load,predict
    report=json.loads((folder/'dialogue-evaluation.json').read_text())
    assert report['training_turns']>=3000 and report['heldout_turns']>=800
    assert report['training_accuracy']>=.98 and report['portable_max_error']<1e-5
    assert report['keras_reload_max_error']<1e-6
    value=predict('CRM','tasks.create','title','Review design and delivery')
    assert value['act']=='provide_value' and value['score']>.9 and value['authorizes_execution'] is False
    assert load()
    monkeypatch.setenv('LOCAL_NLP_MODEL_DIR',str(tmp_path/'missing'))
    assert predict('CRM','tasks.create','title','Test') is None


def test_trained_followup_treats_title_conjunction_as_data_not_a_second_action(client,db,monkeypatch,tmp_path):
    candidate(monkeypatch,tmp_path)
    h,user,project,task=setup_suite(client,db)
    initial=command(client,h,'CRM: create a task')
    reply=command(client,h,'Review design and delivery',parent_run_id=initial['id'])
    assert reply['status']=='awaiting_approval',reply
    assert reply['plan']['steps']==[{'tool':'crm.create_task','payload':{'title':'Review design and delivery'}}]
    assert reply['result']['local_nlp']['neural_prediction']['dialogue_act']['authorizes_execution'] is False
    assert db.query(CRMTask).count()==0
    approve(client,h,reply);tick(client,db)
    assert db.query(CRMTask).one().title=='Review design and delivery'
