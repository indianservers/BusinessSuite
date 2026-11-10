from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_local_nlp_workflows import command
from app.ai_operator.action_repairs import cases
from app.ai_operator.dialogue_corpus import turns,features
from app.apps.crm.models import CRMTask
from collections import Counter
import pytest


def test_repair_cases_are_in_training_without_leaking_evaluation_features():
    rows=cases();assert len(rows)==144
    assert Counter(r['module'] for r in rows)=={'CRM':48,'PMS':48,'HRMS':48}
    assert len({r['id'] for r in rows})==144
    assert len({(r['module'],tuple(r['messages'])) for r in rows})==144
    all_rows=turns();trained={tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items())) for r in all_rows if r['split']=='train'}
    assert all(tuple(sorted(features(r['module'],r['intent'],r['pending'],r['text']).items())) not in trained for r in all_rows if r['split']=='test')


@pytest.mark.parametrize('answer',['yes','okay','no','what are my choices?','I do not know','explain this field','I don’t know','please explain this field'])
def test_ambiguous_or_help_reply_never_becomes_a_task_title(client,db,answer):
    h,user,project,task=setup_suite(client,db)
    initial=command(client,h,'CRM: create a task')
    help_reply=command(client,h,answer,parent_run_id=initial['id'])
    assert help_reply['status']=='needs_clarification',help_reply
    assert help_reply['result']['local_nlp']['intent']=='tasks.create'
    assert help_reply['result']['local_nlp']['slots']['_awaiting']=='title'
    assert 'title' not in help_reply['result']['local_nlp']['slots']
    assert not help_reply['plan']['steps']
    draft=command(client,h,'Review synthetic follow up',parent_run_id=help_reply['id'])
    assert draft['status']=='awaiting_approval'
    assert db.query(CRMTask).count()==0
    approve(client,h,draft);tick(client,db)
    assert db.query(CRMTask).one().title=='Review synthetic follow up'


def test_rename_and_negative_priority_correction_change_exact_plan_and_revoke_old_approval(client,db):
    h,user,project,task=setup_suite(client,db)
    first=command(client,h,'CRM: create task "Original title" high priority')
    renamed=command(client,h,'actually change title to Corrected title',parent_run_id=first['id'])
    revised=command(client,h,'not high, make it low',parent_run_id=renamed['id'])
    assert revised['status']=='awaiting_approval',revised
    assert revised['plan']['steps'][0]['payload']=={'title':'Corrected title','priority':'Low'}
    response=client.post(f'/api/v1/ai-operator/suite/runs/{first["id"]}/approve',headers=h,json={'plan_hash':first['plan_hash']})
    assert response.status_code==409
    approve(client,h,revised);tick(client,db)
    row=db.query(CRMTask).one();assert row.title=='Corrected title' and row.priority=='Low'


def test_date_answer_to_title_question_keeps_date_but_asks_for_title(client,db):
    h,user,project,task=setup_suite(client,db)
    initial=command(client,h,'CRM: create a task')
    date_only=command(client,h,'tomorrow',parent_run_id=initial['id'])
    assert date_only['status']=='needs_clarification'
    assert date_only['result']['local_nlp']['slots']['_awaiting']=='title'
    draft=command(client,h,'Call the synthetic account',parent_run_id=date_only['id'])
    assert draft['status']=='awaiting_approval'
    assert draft['plan']['steps'][0]['payload']['due_date']==date_only['result']['local_nlp']['slots']['due_date']
    assert draft['plan']['steps'][0]['payload']['title']=='Call the synthetic account'
    assert db.query(CRMTask).count()==0


def test_polite_cancel_revokes_a_pending_plan_without_creating_a_title(client,db):
    h,user,project,task=setup_suite(client,db)
    initial=command(client,h,'CRM: create task "Do not execute"')
    cancelled=command(client,h,'please cancel it',parent_run_id=initial['id'])
    assert cancelled['status']=='answered' and not cancelled['plan']['steps']
    response=client.post(f'/api/v1/ai-operator/suite/runs/{initial["id"]}/approve',headers=h,json={'plan_hash':initial['plan_hash']})
    assert response.status_code==409
    assert db.query(CRMTask).count()==0


def test_negated_priority_without_replacement_asks_instead_of_retaining_it(client,db):
    h,user,project,task=setup_suite(client,db)
    initial=command(client,h,'CRM: create task "Priority clarification" high priority')
    question=command(client,h,'not high',parent_run_id=initial['id'])
    assert question['status']=='needs_clarification'
    assert 'priority' not in question['result']['local_nlp']['slots']
    assert not question['plan']['steps']
    draft=command(client,h,'low',parent_run_id=question['id'])
    assert draft['status']=='awaiting_approval'
    assert draft['plan']['steps'][0]['payload']['priority']=='Low'


@pytest.mark.parametrize('module',['PMS','HRMS'])
def test_corrected_title_and_priority_execute_in_the_respective_module(client,db,module):
    from app.models.employee import Employee
    from app.models.helpdesk import HelpdeskTicket
    from app.apps.project_management.models import PMSTask
    from datetime import date
    h,user,project,task=setup_suite(client,db)
    if module=='HRMS':
        db.add(Employee(employee_id='REPAIR-HR',user_id=user.id,first_name='Synthetic',last_name='Repair',date_of_joining=date.today()))
        db.commit();db.expire_all()
    action='create a project task' if module=='PMS' else 'create an HR ticket'
    initial=command(client,h,f'{module}: {action} "Original module title" high priority',**({'project_id':project} if module=='PMS' else {}))
    renamed=command(client,h,'rename it to Corrected module title',parent_run_id=initial['id'])
    revised=command(client,h,'not high, use low priority',parent_run_id=renamed['id'])
    assert revised['status']=='awaiting_approval',revised
    approve(client,h,revised);tick(client,db)
    row=db.query(PMSTask).filter_by(title='Corrected module title').one() if module=='PMS' else db.query(HelpdeskTicket).filter_by(subject='Corrected module title').one()
    assert row.priority.casefold()=='low'
