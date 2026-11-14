"""Synthetic-only training coverage and frozen probe isolation."""
from collections import Counter
from app.ai_operator.workplace_dialogue_corpus import turns,VERSION
from app.ai_operator.workplace_dialogue_validation import cases
from app.ai_operator.dialogue_corpus import turns as all_turns,features


def normalized(value):return ' '.join(value.casefold().split()).strip('.!?')


def test_workplace_training_has_150_turns_per_module_and_contextual_labels():
    rows=turns()
    assert len(rows)==450 and Counter(row['module'] for row in rows)=={'CRM':150,'PMS':150,'HRMS':150}
    assert len({(row['module'],row['pending'],row['text']) for row in rows})==450
    assert all(row['split']=='train' and row['origin']==VERSION for row in rows)
    for module in ('CRM','PMS','HRMS'):
        selected=[row for row in rows if row['module']==module]
        assert Counter(row['act'] for row in selected)=={'provide_value':50,'clarify':20,'cancel_action':20,'confirm_action':20,'new_request':20,'unsafe_request':20}
        assert all(row['pending']=='_approval' for row in selected if row['act']=='confirm_action')
        assert all(row['pending']=='title' for row in selected if row['act']=='clarify')


def test_workplace_probes_are_frozen_separate_wording_and_features():
    rows=all_turns();probes=cases()
    assert len(probes)==90 and Counter(row['module'] for row in probes)=={'CRM':30,'PMS':30,'HRMS':30}
    assert Counter(row['act'] for row in probes)==dict.fromkeys(['provide_value','clarify','cancel_action','confirm_action','new_request','unsafe_request'],15)
    assert not {normalized(row['text']) for row in rows}&{normalized(row['text']) for row in probes}
    keys={tuple(sorted(features(row['module'],row['intent'],row['pending'],row['text']).items())) for row in rows}
    assert all(tuple(sorted(features(row['module'],row['intent'],row['pending'],row['text']).items())) not in keys for row in probes)


def test_workplace_addition_does_not_leak_old_wording_probes_into_training():
    from app.ai_operator.dialogue_unseen import cases as original
    from app.ai_operator.message_dialogue_holdout import cases as message
    from app.ai_operator.message_dialogue_validation import cases as fresh
    training={normalized(row['text']) for row in turns()}
    assert not training&{normalized(row['text']) for row in [*original(),*message(),*fresh()]}



def test_learned_cancellation_discards_only_the_unexecuted_draft(monkeypatch):
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_nlp import Interpretation
    monkeypatch.setattr('app.ai_operator.dialogue_tensorflow.predict',lambda *args:{'act':'cancel_action','score':.99,'margin':.98})
    prior={'module':'CRM','intent':'tasks.create','slots':{'action_verb':'create','_awaiting':'title'}}
    result=continue_action(Interpretation('CRM','unsupported'),prior,'Please withdraw the unexecuted work item we are preparing','Asia/Kolkata')
    assert result.intent=='cancelled' and not result.slots
    # The same predicted act cannot discard a quoted title or an explicit new
    # create command; model output is not an authority over user content.
    result=continue_action(Interpretation('CRM','unsupported'),prior,'"Cancel the pending draft review"','Asia/Kolkata')
    assert result.intent!='cancelled' and result.slots['title']=='Cancel the pending draft review'
    result=continue_action(Interpretation('CRM','tasks.create',1,{'title':'Review pending draft','action_verb':'create'}),prior,'Create task called Review pending draft','Asia/Kolkata')
    assert result.intent!='cancelled'


def test_learned_new_conversation_request_keeps_pending_details_separate(monkeypatch):
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_nlp import Interpretation
    monkeypatch.setattr('app.ai_operator.dialogue_tensorflow.predict',lambda *args:{'act':'new_request','score':.99,'margin':.98})
    prior={'module':'CRM','intent':'tasks.create','slots':{'action_verb':'create','_awaiting':'title','priority':'High'}}
    result=continue_action(Interpretation('CRM','unsupported'),prior,'Open an independent discussion about a different work item','Asia/Kolkata')
    assert result.question and result.slots==prior['slots'] and 'title' not in result.slots



def test_learned_confirmation_cannot_fill_a_missing_field_or_override_labelled_title(monkeypatch):
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_nlp import Interpretation
    monkeypatch.setattr('app.ai_operator.dialogue_tensorflow.predict',lambda *args:{'act':'confirm_action','score':.99,'margin':.98})
    prior={'module':'CRM','intent':'tasks.create','slots':{'action_verb':'create','_awaiting':'title'}}
    text='I approve the current reviewed proposal'
    result=continue_action(Interpretation('CRM','unsupported'),prior,text,'Asia/Kolkata')
    assert result.question and 'title' not in result.slots
    result=continue_action(Interpretation('CRM','unsupported'),prior,'Title: '+text,'Asia/Kolkata')
    assert not result.question and result.slots['title']==text



def test_moderate_confidence_clear_acknowledgement_only_asks_for_missing_field(monkeypatch):
    from app.ai_operator.local_dialogue import continue_action
    from app.ai_operator.local_nlp import Interpretation
    monkeypatch.setattr('app.ai_operator.dialogue_tensorflow.predict',lambda *args:{'act':'clarify','score':.84,'margin':.72})
    prior={'module':'CRM','intent':'tasks.create','slots':{'action_verb':'create','_awaiting':'title'}}
    for text in ['Okay I am following the discussion so far','I approve the reviewed proposal']:
        result=continue_action(Interpretation('CRM','unsupported'),prior,text,'Asia/Kolkata')
        assert result.question and 'title' not in result.slots
