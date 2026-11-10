from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pytest
from app.ai_operator.local_nlp import parse,Interpretation
from app.ai_operator.local_dialogue import continue_action,reference
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_local_nlp_workflows import command


@pytest.mark.parametrize('text,expected',[
    ('project #12','project'),('the project is numbered 12','project'),('choose the project with ID 12','project'),
    ('use project number 12 please','project'),('the requested ID is 12','task'),('use record number 12','task'),
    ('select the task numbered 12','task'),('the record is number 12','lead'),('leave type #12','type'),
])
def test_reference_wording_resolves_one_explicit_positive_id(text,expected):
    assert reference(text,expected)==(12,False)


@pytest.mark.parametrize('text',['0','-1','project 1 and 2','delete task 12','do not use task 12','task 12 or 13'])
def test_ambiguous_or_negative_id_is_not_guessed(text):
    assert reference(text,'task')[0] is None


def test_wrong_entity_is_rejected_and_original_pending_field_retained():
    prior={'module':'PMS','intent':'tasks.create','slots':{'action_verb':'create','_awaiting':'project_id'}}
    result=continue_action(parse('task #12','PMS'),prior,'task #12','Asia/Kolkata')
    assert result.question and result.slots==prior['slots']
    assert 'project_id' not in result.slots


@pytest.mark.parametrize('text,days',[('in two days',2),('in one week',7),('the day after tomorrow',2),('in fourteen days',14)])
def test_word_dates_are_resolved_with_the_selected_timezone(text,days):
    instant=datetime(2026,11,10,12,tzinfo=ZoneInfo('Asia/Kolkata'))
    value=parse('CRM: create task "Synthetic task" due '+text,'CRM',instant=instant)
    assert value.slots['due_date']==(instant.date()+timedelta(days=days)).isoformat()


@pytest.mark.parametrize('answer,expected',[('noon','12:00'),('at midnight','00:00'),('3 pm','15:00'),('09:30','09:30')])
def test_time_replies_are_exact_and_never_approximate(answer,expected):
    prior={'module':'CRM','intent':'reminders.create','slots':{'action_verb':'create','_awaiting':'time'}}
    value=continue_action(parse(answer,'CRM'),prior,answer,'Asia/Kolkata')
    assert value.slots['time']==expected


def test_uncertain_time_still_requests_a_precise_value():
    prior={'module':'CRM','intent':'reminders.create','slots':{'action_verb':'create','_awaiting':'time'}}
    value=continue_action(parse('around 3 pm','CRM'),prior,'around 3 pm','Asia/Kolkata')
    assert 'time' not in value.slots and value.slots['_awaiting']=='time'


@pytest.mark.parametrize('answer,period',[('first half','First Half'),('second half','Second Half')])
def test_half_day_period_replies_keep_the_action(answer,period):
    prior={'module':'HRMS','intent':'leave.create','slots':{'action_verb':'apply','_awaiting':'half_day_period','is_half_day':True}}
    value=continue_action(parse(answer,'HRMS'),prior,answer,'Asia/Kolkata')
    assert value.intent=='leave.create' and value.slots['half_day_period']==period


def test_spoken_project_reference_produces_a_native_reviewed_action(client,db):
    from app.apps.project_management.models import PMSTask
    h,user,project,task=setup_suite(client,db)
    first=command(client,h,'PMS: create a project task')
    selected=command(client,h,f'choose the project with ID {project}',parent_run_id=first['id'])
    assert selected['result']['local_nlp']['slots']['_awaiting']=='title',selected
    draft=command(client,h,'Review the language test',parent_run_id=selected['id'])
    assert draft['status']=='awaiting_approval'
    approve(client,h,draft);tick(client,db)
    assert db.query(PMSTask).filter_by(title='Review the language test').count()==1


def test_negating_a_due_date_asks_for_replacement_before_any_action(client,db):
    h,user,project,task=setup_suite(client,db)
    first=command(client,h,'CRM: create task "Date correction" due tomorrow')
    question=command(client,h,'not tomorrow',parent_run_id=first['id'])
    assert question['status']=='needs_clarification' and not question['plan']['steps']
    assert 'due_date' not in question['result']['local_nlp']['slots']
    corrected=command(client,h,'in two days',parent_run_id=question['id'])
    assert corrected['status']=='awaiting_approval'
    assert corrected['plan']['steps'][0]['payload']['due_date']!=first['plan']['steps'][0]['payload']['due_date']


def test_new_conversation_command_does_not_inherit_or_cancel_another_draft(client,db):
    from app.apps.crm.models import CRMTask
    h,user,project,task=setup_suite(client,db)
    first=command(client,h,'CRM: create task "Retain independent draft"')
    reset=command(client,h,'start a new conversation',parent_run_id=first['id'],local_plan={'summary':'Must not execute','steps':[{'tool':'crm.create_task','payload':{'title':'Unwanted reset plan'}}]})
    assert reset['status']=='answered' and not reset['plan']['steps']
    assert reset['result']['request']['parent_run_id'] is None
    assert not reset['result']['local_nlp']['slots']
    approve(client,h,first);tick(client,db)
    assert db.query(CRMTask).one().title=='Retain independent draft'
