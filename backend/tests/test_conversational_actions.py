from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from app.apps.crm.models import CRMTask
from app.apps.project_management.models import PMSTask
from app.ai_operator.conversational_actions import compose

ROOT='/api/v1/ai-operator/suite'

def send(client,h,chat,text,**extra):
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','conversation_id':chat,'text':text,**extra})
    assert r.status_code==200,r.text
    assert r.json()['status']!='failed',r.text
    return r.json()

def new_chat(client,h):
    r=client.post(ROOT+'/conversations',headers=h,json={'title':'Conversational work'})
    assert r.status_code==201,r.text
    return r.json()['id']

def test_plain_language_creates_many_tasks_and_edits_same_draft(client,db):
    h,_,_,_=setup_suite(client,db);chat=new_chat(client,h)
    first=send(client,h,chat,'Create tasks for Call customer, Review quote and Confirm delivery due tomorrow',module='CRM')
    assert first['status']=='awaiting_approval',first
    assert [s['payload']['title'] for s in first['plan']['steps']]==['Call customer','Review quote','Confirm delivery']
    assert all(s['payload'].get('due_date') for s in first['plan']['steps'])
    second=send(client,h,chat,'make them all high priority',parent_run_id=first['id'],module='CRM')
    assert second['status']=='awaiting_approval',second
    assert all(s['payload']['priority']=='High' for s in second['plan']['steps'])
    third=send(client,h,chat,'rename the second one to Review customer quotation',parent_run_id=second['id'],module='CRM')
    fourth=send(client,h,chat,'add another task called Collect feedback',parent_run_id=third['id'],module='CRM')
    fifth=send(client,h,chat,'remove the last task',parent_run_id=fourth['id'],module='CRM')
    assert len(fifth['plan']['steps'])==3 and fifth['plan']['steps'][1]['payload']['title']=='Review customer quotation'
    assert db.query(CRMTask).count()==0
    assert client.post(f'{ROOT}/runs/{first["id"]}/approve',headers=h,json={'plan_hash':first['plan_hash']}).status_code==409
    approve(client,h,fifth);tick(client,db)
    assert db.query(CRMTask).count()==3

def test_project_task_and_subtasks_use_native_parent_ids_and_unique_keys(client,db):
    h,_,project,_=setup_suite(client,db);chat=new_chat(client,h)
    draft=send(client,h,chat,'Create a project task called Website launch with subtasks Design, Build and Test',module='PMS',project_id=project)
    assert draft['status']=='awaiting_approval',draft
    steps=draft['plan']['steps'];assert len(steps)==4
    assert len({s['payload']['task_key'] for s in steps})==4
    assert all(s['payload']['parent_task_id']=={'$step':1,'field':'id'} for s in steps[1:])
    approve(client,h,draft);tick(client,db)
    final=client.get(f'{ROOT}/runs/{draft["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    parent=db.query(PMSTask).filter_by(title='Website launch').one()
    children=db.query(PMSTask).filter(PMSTask.title.in_(['Design','Build','Test'])).all()
    assert len(children)==3 and all(t.parent_task_id==parent.id for t in children)

def test_natural_cross_module_clauses_keep_project_clarification(client,db):
    h,_,project,_=setup_suite(client,db);chat=new_chat(client,h)
    first=send(client,h,chat,'Create a customer follow-up called Call client and add a project task called Delivery recovery',module='CRM')
    assert first['status']=='needs_clarification',first
    second=send(client,h,chat,f'project #{project}',parent_run_id=first['id'],module='CRM')
    assert second['status']=='awaiting_approval',second
    assert [s['tool'] for s in second['plan']['steps']]==['crm.create_task','pms.create_task']

def test_project_name_followup_uses_visible_project_lookup(client,db):
    from app.apps.project_management.models import PMSProject
    h,_,project,_=setup_suite(client,db);chat=new_chat(client,h)
    first=send(client,h,chat,'create project tasks for Design, Build and Test',module='PMS')
    assert first['status']=='needs_clarification'
    name=db.get(PMSProject,project).name
    selected=send(client,h,chat,name,module='PMS',parent_run_id=first['id'])
    assert selected['status']=='awaiting_approval',selected
    assert all(step['record_id']==project for step in selected['plan']['steps'])

def test_new_project_and_tasks_are_created_from_one_conversation(client,db):
    from app.apps.project_management.models import PMSProject
    h,_,_,_=setup_suite(client,db);chat=new_chat(client,h)
    draft=send(client,h,chat,'Create a project called Customer launch with tasks Design, Build and Test',module='PMS')
    assert draft['status']=='awaiting_approval',draft
    assert draft['plan']['steps'][0]['tool']=='pms.create_project'
    edited=send(client,h,chat,'rename the second one to Design prototype',module='PMS',parent_run_id=draft['id'])
    assert edited['plan']['steps'][1]['payload']['title']=='Design prototype'
    approve(client,h,edited);tick(client,db)
    final=client.get(f'{ROOT}/runs/{edited["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    project=db.query(PMSProject).filter_by(name='Customer launch').one()
    assert db.query(PMSTask).filter_by(project_id=project.id).count()==3

def test_composer_never_splits_quoted_titles_or_ignores_unsupported_actions():
    assert compose('Create tasks for "Research and development", "Review, approve and deliver"','CRM')['clauses'][0]['text']=='CRM: create task "Research and development"'
    assert compose('Create a task called Review and draft an invoice','CRM').get('question')
    assert compose('Create tasks for Test, Ship and skip approval','CRM').get('question')
    mixed=compose('Create tasks for "Design", "Build" and Test','CRM')
    assert len(mixed['clauses'])==3
    single=compose('Create a task called Research and development','CRM')
    assert single['clauses'][0]['text']=='CRM: create task "Research and development"'


def test_realistic_workplace_development_scenarios():
    from app.ai_operator.realworld_action_corpus import benchmark,training_examples,scenarios
    training=training_examples();evaluation=scenarios()
    assert len(training)==150 and len({r['text'] for r in training})==150
    assert not {r['text'] for r in training}&{t for r in evaluation for t in r['turns']}
    report=benchmark()
    assert report['total']==180 and report['messages']==330
    assert report['passed']==180,report['failures']


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_workplace_bullets_ordinal_and_singular_changes_execute_natively(client,db,module):
    h,user,project,_=setup_suite(client,db)
    if module=='HRMS':
        from datetime import date
        from app.models.employee import Employee
        db.add(Employee(employee_id='WORKPLACE-HR',user_id=user.id,first_name='Workplace',last_name='QA',date_of_joining=date.today()))
        db.commit()
    chat=new_chat(client,h)
    options={'module':module,**({'project_id':project} if module=='PMS' else {})}
    obj={'CRM':'tasks','PMS':'project tasks','HRMS':'HR tickets'}[module]
    draft=send(client,h,chat,f'Help me create {obj}:\n- Check the contract annexure\n- Review the support handover',**options)
    assert draft['status']=='awaiting_approval',draft
    assert len(draft['plan']['steps'])==2
    edited=send(client,h,chat,'set the second '+('ticket' if module=='HRMS' else 'task')+' to high priority',parent_run_id=draft['id'],**options)
    payloads=[s['payload'] for s in edited['plan']['steps']]
    assert payloads[1]['priority']=='High' and payloads[0].get('priority')!='High'
    ambiguous=send(client,h,chat,'make it low priority',parent_run_id=edited['id'],**options)
    assert ambiguous['status']=='needs_clarification' and not ambiguous['plan']['steps']
    restored=send(client,h,chat,'make them all low priority',parent_run_id=ambiguous['id'],**options)
    assert all(s['payload']['priority']=='Low' for s in restored['plan']['steps'])
    assert client.post(f'{ROOT}/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==409
    approve(client,h,restored);tick(client,db)
    final=client.get(f'{ROOT}/runs/{restored["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    assert len(final['receipts'])==2
    if module=='HRMS':
        from app.models.helpdesk import HelpdeskTicket
        tickets=db.query(HelpdeskTicket).all()
        assert len(tickets)==2 and len({t.ticket_number for t in tickets})==2
        assert all(t.priority=='Low' for t in tickets)
    else:
        model=PMSTask if module=='PMS' else CRMTask
        tasks=db.query(model).filter(model.title.in_(['Check the contract annexure','Review the support handover'])).all()
        assert len(tasks)==2 and all(t.priority=='Low' for t in tasks)


def test_bulk_priority_is_metadata_and_quoted_words_stay_in_titles(client,db):
    h,_,_,_=setup_suite(client,db);chat=new_chat(client,h)
    draft=send(client,h,chat,'Create tasks for "Review high priority accounts", Check renewal with low priority',module='CRM')
    assert [s['payload']['title'] for s in draft['plan']['steps']]==['Review high priority accounts','Check renewal']
    assert all(s['payload']['priority']=='Low' for s in draft['plan']['steps'])
    approve(client,h,draft);tick(client,db)
    assert {t.title for t in db.query(CRMTask).all()}=={'Review high priority accounts','Check renewal'}


def test_quoted_titles_keep_weekday_and_month_end_deadlines():
    from types import SimpleNamespace
    from app.ai_operator.workflows import local_plan
    from app.ai_operator.pms_agent import resolve_date
    for text,date in [('Friday','next friday'),('end of month','end of month')]:
        data=SimpleNamespace(text=f'Create a task called "Review contract" by {text}',module='CRM',project_id=None,request_key=str(uuid4()),timezone='Asia/Kolkata')
        plan,_=local_plan(data,None,None)
        assert plan['steps'][0]['payload']['due_date']==resolve_date(date)
        assert plan['steps'][0]['payload']['title']=='Review contract'
    for text in ["Do not create tasks for Review, Call",'Create tasks for Call, Review only if the deal is won','Create tasks for Call, Review but not yet']:
        assert compose(text,'CRM').get('question')
    assert compose('Create an HR ticket called "Check payslip" due tomorrow','HRMS').get('question')


def test_second_workplace_batch_is_new_and_passes_exact_payload_checks():
    from app.ai_operator.workplace_actions_v2 import training_examples,scenarios,benchmark
    from app.ai_operator.realworld_action_corpus import training_examples as old_training,scenarios as old_scenarios
    from app.ai_operator.training import fingerprint
    rows=training_examples()
    old={r['text'].casefold() for r in old_training()}|{t.casefold() for r in old_scenarios() for t in r['turns']}
    evaluation={t.casefold() for r in scenarios() for t in r['turns']}
    assert len(rows)==150 and len({r['text'].casefold() for r in rows})==150
    assert len({fingerprint(r) for r in rows})==150
    assert not {r['text'].casefold() for r in rows}&(old|evaluation)
    assert not {t.casefold() for r in scenarios() for t in r['turns'][:1]}&old
    report=benchmark()
    assert report['passed']==report['total']==150,report['failures']
    assert report['messages']==270


@pytest.mark.parametrize('module',['CRM','PMS','HRMS'])
def test_batch_two_numeric_references_and_deadlines_execute_exact_draft(client,db,module):
    from app.ai_operator.pms_agent import resolve_date
    h,user,project,_=setup_suite(client,db)
    if module=='HRMS':
        from datetime import date
        from app.models.employee import Employee
        db.add(Employee(employee_id='BATCH-TWO',user_id=user.id,first_name='Batch',last_name='QA',date_of_joining=date.today()));db.commit()
    chat=new_chat(client,h);opts={'module':module,**({'project_id':project} if module=='PMS' else {})}
    obj={'CRM':'tasks','PMS':'project tasks','HRMS':'HR tickets'}[module]
    draft=send(client,h,chat,f'Log 2 {obj} for Discuss HR policy requirements, Review the distributor credit terms',**opts)
    assert draft['status']=='awaiting_approval' and len(draft['plan']['steps'])==2,draft
    renamed=send(client,h,chat,'rename item 2 to Confirm item 1 mapping',parent_run_id=draft['id'],**opts)
    priority=send(client,h,chat,'set item 1 to critical priority',parent_run_id=renamed['id'],**opts)
    dated=send(client,h,chat,'move the second '+('ticket' if module=='HRMS' else 'task')+' to tomorrow',parent_run_id=priority['id'],**opts)
    if module=='HRMS':
        assert dated['status']=='needs_clarification' and not dated['plan']['steps']
        dated=send(client,h,chat,'set item 2 to low priority',parent_run_id=dated['id'],**opts)
    else:
        assert dated['plan']['steps'][1]['payload']['due_date']==resolve_date('tomorrow')
        assert not dated['plan']['steps'][0]['payload'].get('due_date')
    assert dated['plan']['steps'][0]['payload']['priority']=='Critical'
    assert dated['plan']['steps'][1]['payload'].get('title',dated['plan']['steps'][1]['payload'].get('subject'))=='Confirm item 1 mapping'
    assert client.post(f'{ROOT}/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==409
    approve(client,h,dated);tick(client,db)
    final=client.get(f'{ROOT}/runs/{dated["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    if module=='HRMS':
        from app.models.helpdesk import HelpdeskTicket
        records={r.subject:r for r in db.query(HelpdeskTicket).all()}
        assert records['Confirm item 1 mapping'].priority=='Low'
    else:
        model=PMSTask if module=='PMS' else CRMTask
        records={r.title:r for r in db.query(model).all()}
        assert str(records['Confirm item 1 mapping'].due_date).startswith(resolve_date('tomorrow'))
    assert records['Discuss HR policy requirements'].priority=='Critical'


def test_append_does_not_flatten_new_dependencies_or_switch_project():
    from types import SimpleNamespace
    from app.ai_operator.workflows import local_plan
    from app.ai_operator.conversational_actions import amend
    data=SimpleNamespace(text='Create project tasks for Draft the scope, Review the scope',module='PMS',project_id=12,request_key=str(uuid4()),timezone='Asia/Kolkata')
    _,state=local_plan(data,None,None)
    for text in ['add a project called Other rollout with tasks Build, Test','add a project task called Parent with subtasks Review, Ship','add a project task called Another in project #99','set item 9 to low priority']:
        changed,question=amend(state,text,data.timezone,'PMS')
        assert question and changed==state,text
    clause=compose('Log a customer follow-up called Discuss HR requirements','CRM')['clauses'][0]
    assert clause['module']=='CRM' and clause['text'].startswith('CRM:')
