"""Versioned synthetic message dialogue data and strict split isolation."""
from collections import Counter
from app.ai_operator.message_dialogue_corpus import turns,VERSION
from app.ai_operator.message_dialogue_holdout import cases
from app.ai_operator.dialogue_corpus import turns as all_turns,features
from app.ai_operator.dialogue_unseen import cases as original_probes


def normalized(value):return ' '.join(value.casefold().split()).strip('.!?')


def test_message_training_has_one_hundred_fifty_authored_turns_per_module():
    rows=turns()
    assert len(rows)==450 and Counter(r['module'] for r in rows)=={'CRM':150,'PMS':150,'HRMS':150}
    assert len({(r['module'],r['pending'],r['text']) for r in rows})==450
    assert all(r['split']=='train' and r['origin']==VERSION and r['pending'] in {'title','_approval'} for r in rows)
    assert {r['act'] for r in rows}=={'provide_value','clarify','cancel_action','unsafe_request','confirm_action','new_request'}
    assert all(r['intent']==('ticket.create' if r['module']=='HRMS' else 'tasks.create') for r in rows)


def test_new_and_original_wording_probes_never_enter_training_or_selection():
    from app.ai_operator.message_dialogue_validation import cases as fresh_cases
    rows=all_turns();probes=cases();old=original_probes();fresh=fresh_cases()
    assert len(fresh)==60
    assert len(probes)==60 and Counter(r['module'] for r in probes)=={'CRM':20,'PMS':20,'HRMS':20}
    assert Counter(r['act'] for r in probes)==dict.fromkeys(['provide_value','clarify','cancel_action','confirm_action','new_request','unsafe_request'],10)
    words={normalized(r['text']) for r in rows}
    assert not words&{normalized(r['text']) for r in [*probes,*old,*fresh]}
    keys={tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items())) for r in rows}
    assert all(tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items())) not in keys for r in [*probes,*fresh])
    train={tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items())) for r in rows if r['split']=='train'}
    assert not train&{tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items())) for r in rows if r['split']=='test'}
