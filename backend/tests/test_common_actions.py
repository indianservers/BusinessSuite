from collections import Counter
import pytest
from app.ai_operator.common_actions import catalog,examples,GROUPS
from app.ai_operator.common_actions_holdout import examples as heldout
from app.ai_operator.local_features import features
from app.ai_operator.local_corpus import FAMILIES


def test_catalog_covers_200_unique_requests_and_all_existing_intents_per_module():
    rows=catalog()
    assert Counter(r['module'] for r in rows)=={'PMS':200,'CRM':200,'HRMS':200}
    assert len({r['id'] for r in rows})==600
    for module,groups in GROUPS.items():
        assert set(groups)==set(FAMILIES[module])
        assert all(len(block.splitlines())==10 for block in groups.values())
        assert len({r['text'] for r in rows if r['module']==module})==200
    assert len(examples())==600


def test_frozen_probes_do_not_overlap_training_after_slot_normalization():
    from app.ai_operator.expanded_corpus import examples as baseline
    signature=lambda r:(r['module'],tuple(sorted(features(r['text']).items())))
    training={signature(r) for r in baseline(60)+examples()}
    assert len(heldout())==60
    assert not training&{signature(r) for r in heldout()}
    assert Counter(r['module'] for r in heldout())=={'PMS':20,'CRM':20,'HRMS':20}


def test_catalog_never_labels_native_only_hr_requests_as_executable():
    rows=[r for r in catalog() if r['module']=='HRMS' and r['intent'] in {'attendance','payroll','leave.approve'}]
    assert len(rows)==30 and all(r['behavior']=='native_handoff' for r in rows)
    assert all(r['behavior']=='needs_details' for r in catalog() if r['intent']=='leads.message')


@pytest.mark.parametrize('module,text,expected',[
    ('PMS','List high priority PMS assignments','tasks.high'),
    ('PMS','Find dependency blockers in this project','dependencies'),
    ('PMS','Show tasks assigned to me','tasks.mine'),
    ('PMS','List my project assignments','tasks.mine'),
    ('CRM','Show customer tasks assigned to me personally','tasks.mine'),
    ('CRM','Which CRM follow-up tasks are due today','tasks.today'),
    ('CRM','Bring up the lead records visible to my account','leads.list'),
    ('CRM','Show me lead records containing "Cedar"','leads.search'),
    ('HRMS','Give an overview of my employee support requests','summary'),
])
def test_specific_read_filters_win_without_spurious_personal_assignment(module,text,expected):
    from app.ai_operator.local_nlp import parse
    assert parse(f'{module}: {text}',module).intent==expected


def test_live_project_summary_and_supplied_writing_notes_have_separate_routes():
    from app.ai_operator.local_writing import chat_plan
    assert chat_plan("Summarize this project's progress") is None
    written=chat_plan("Summarize this project's progress: Migration review is due Friday.")
    assert written and not written['steps'] and 'Friday' in written['summary']
