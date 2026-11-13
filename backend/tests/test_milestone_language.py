"""Unseen conversational milestone messages produce typed drafts, never approvals."""
import pytest
from app.ai_operator.milestone_actions import interpret

@pytest.mark.parametrize('message,field,value',[
 ('PMS: rename milestone #42 to "Client sign-off"','name','Client sign-off'),
 ('Please move milestone #42 to 2027-03-28','due_date','2027-03-28'),
 ('Reschedule milestone #42 2027-03-28','due_date','2027-03-28'),
 ('Mark milestone #42 as complete','status','Completed'),
 ('Assign milestone #42 to user #12','owner_user_id',12),
 ('Reopen milestone #42','status','In Progress'),
])
def test_realistic_milestone_messages_select_exact_record_and_proposed_fields(message,field,value):
    result=interpret(message)
    assert result.intent=='milestone.update' and result.slots['record_id']==42
    assert result.slots['values'][field]==value


def test_client_approval_is_clarified_instead_of_becoming_milestone_status():
    result=interpret('Update milestone #42 client approval: Approved')
    assert result.question and not result.slots['values']


@pytest.mark.parametrize('message,expected',[('Complete milestone #42 progress: 25',25),('Reopen milestone #42 progress: 75',75)])
def test_status_commands_preserve_explicit_progress_instead_of_overwriting_it(message,expected):
    assert interpret(message).slots['values']['progress_percent']==expected


def test_compound_rename_and_deadline_are_one_reviewed_patch():
    result=interpret('Rename milestone #42 to "Client sign-off" and move it to 2027-03-28')
    assert not result.question
    assert result.slots['values']=={'name':'Client sign-off','due_date':'2027-03-28'}

@pytest.mark.parametrize('message',[
 'Rename milestone #42 to "Release" and delete all leads',
 'Move milestone #42 to 2027-03-28 and complete milestone #43',
 'Move milestone #42 to 2027-03-28 then move it to 2027-04-01',
])
def test_compound_ambiguity_is_clarified_without_silently_dropping_a_clause(message):
    assert interpret(message).question

@pytest.mark.parametrize('title',['Research and create','Client approval checklist',"Client’s sign-off"])
def test_quoted_titles_remain_literal_data(title):
    result=interpret(f'Rename milestone #42 to "{title}"')
    assert not result.question and result.slots['values']['name']==title


def test_natural_followup_preserves_selected_id_and_previous_fields():
    from app.ai_operator.milestone_actions import followup
    from app.ai_operator.local_nlp import Interpretation
    prior={'intent':'milestone.update','slots':{'record_id':42,'values':{'due_date':'2027-03-28'}}}
    result=followup(Interpretation('PMS','unsupported'),prior,'Rename it to "Client sign-off"','Asia/Kolkata')
    assert result.slots['record_id']==42
    assert result.slots['values']=={'due_date':'2027-03-28','name':'Client sign-off'}


def test_compound_pronouns_inside_quoted_titles_are_not_rewritten():
    result=interpret('Move milestone #42 to 2027-03-28 and rename milestone #42 to "Ship it"')
    assert not result.question and result.slots['values']['name']=='Ship it'


def test_compound_missing_record_keeps_changes_for_record_clarification():
    result=interpret('Rename milestone to "Release" and move it to 2027-03-28')
    assert not result.question and 'record_id' not in result.slots
    assert result.slots['values']=={'name':'Release','due_date':'2027-03-28'}


def test_compound_missing_first_change_is_not_silently_dropped():
    assert interpret('Rename milestone #42 and move it to 2027-03-28').question


def test_field_labels_inside_a_quoted_name_remain_literal():
    title='Release, due date: 2027-04-01'
    result=interpret(f'Rename milestone #42 to "{title}"')
    assert not result.question and result.slots['values']=={'name':title}


def test_public_local_parser_accepts_validated_milestone_compound_before_generic_single_action_guard():
    from app.ai_operator.local_nlp import parse
    result=parse('PMS: rename milestone #42 to "Release" and move it to 2027-03-28')
    assert result.intent=='milestone.update' and not result.question
    assert result.slots['values']=={'name':'Release','due_date':'2027-03-28'}


@pytest.mark.parametrize('message',[
 'Update milestone #42 due date: 2027-03-28, due date: 2027-04-01',
 'Update milestone #42 owner user id: 12, owner user id: 13',
 'Complete milestone #42 status: In Progress',
 'Reopen milestone #42 status: Completed',
 'Mark milestone #42 as complete, status: In Progress',
])
def test_conflicting_fields_or_status_instructions_need_clarification(message):
    result=interpret(message)
    assert result.question and result.slots.get('record_id')==42
    assert not result.slots['values']


def test_duplicate_identical_fields_are_not_a_conflict():
    result=interpret('Update milestone #42 due date: 2027-03-28, due date: 2027-03-28')
    assert not result.question and result.slots['values']=={'due_date':'2027-03-28'}


def test_conflicting_labelled_followup_retains_previous_draft():
    from app.ai_operator.milestone_actions import followup
    from app.ai_operator.local_nlp import Interpretation
    prior={'intent':'milestone.update','slots':{'record_id':42,'values':{'name':'Reviewed title'}}}
    result=followup(Interpretation('PMS','unsupported'),prior,'due date: 2027-03-28, due date: 2027-04-01','Asia/Kolkata')
    assert result.question and result.slots['values']=={'name':'Reviewed title'}
