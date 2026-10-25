from datetime import date
from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite, prepare, approve, tick, ROOT
from tests.test_ai_operator import isolate_generic_http_audit, mock_provider
from app.ai_operator.jobs import process_batch
from app.ai_operator.pms_agent import resolve_date
from app.apps.project_management.models import PMSTask, PMSChecklistItem


def task_plan(task):
    return {'summary':'Update delivery work','steps':[
        {'tool':'update_task','task_id':task,'changes':{'priority':'High','story_points':5,'estimated_hours':8}},
        {'tool':'add_checklist','task_id':task,'title':'Review QA'},
        {'tool':'add_comment','task_id':task,'body':'Ready for QA review'}]}


def complete(client,db,h,run):
    approve(client,h,run)
    tick(client,db)
    process_batch(db)
    tick(client,db)
    return client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()


def test_pms_agent_delegates_approved_tasks_and_receipts(client,db):
    h,_,p,t=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'pms.task_plan','record_id':p,'payload':{'plan':task_plan(t)}}],project_id=p,task_ids=[t],input_mode='voice')
    assert run['status']=='awaiting_approval',run
    assert run['pms_previews']['1']['impact']
    assert db.get(PMSTask,t).priority!='High'
    approve(client,h,run)
    tick(client,db)
    waiting=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert waiting['status']=='waiting_pms',waiting
    assert db.get(PMSTask,t).priority!='High'
    process_batch(db)
    tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    assert final['receipts'][0]['pms_run_id']
    assert len(final['receipts'][0]['task_receipts'])==3
    db.expire_all()
    assert db.get(PMSTask,t).priority=='High'
    assert db.query(PMSChecklistItem).filter_by(task_id=t).count()==1
    tick(client,db)
    assert db.query(PMSChecklistItem).filter_by(task_id=t).count()==1


def test_agent_memory_playbook_monitor_and_context(client,db,monkeypatch):
    h,_,p,t=setup_suite(client,db)
    run=prepare(client,h,[
        {'tool':'pms.remember','record_id':p,'payload':{'text':'Plan launches on weekdays'}},
        {'tool':'pms.save_playbook','record_id':p,'payload':{'title':'QA review','plan':task_plan(t)}},
        {'tool':'pms.watch','record_id':p,'payload':{'name':'Delivery watch'}}],project_id=p)
    assert run['status']=='awaiting_approval',run
    final=complete(client,db,h,run)
    assert final['status']=='succeeded',final
    calls=mock_provider(monkeypatch,{'summary':'Which sprint should I use?','question':'Which sprint?','steps':[]})
    response=client.post(ROOT+'/commands',headers=h,json={'text':'Move this task into a sprint','project_id':p,'task_ids':[t],'request_key':str(uuid4())})
    assert response.json()['status']=='needs_clarification',response.text
    assert b'Plan launches on weekdays' in calls[0].content
    assert b'QA review' in calls[0].content
    assert b'working_calendar' in calls[0].content
    parent=response.json()
    child=prepare(client,h,[],parent_run_id=parent['id'])
    assert child['result']['request']['project_id']==p
    assert child['result']['request']['task_ids']==[t]


def test_calendar_schedule_and_cancel_waiting(client,db):
    h,_,p,t=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'pms.schedule','record_id':p,'payload':{'task_ids':[t],'start_date':'next monday'}}],project_id=p,task_ids=[t])
    assert run['status']=='awaiting_approval',run
    assert run['plan']['steps'][0]['tool']=='pms.task_plan'
    approve(client,h,run)
    tick(client,db)
    cancelled=client.post(ROOT+f'/runs/{run["id"]}/cancel',headers=h)
    assert cancelled.status_code==200,cancelled.text
    process_batch(db)
    tick(client,db)
    assert client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()['status']=='cancelled'


def test_work_breakdown_reuses_atomic_setup(client,db):
    h,_,_,_=setup_suite(client,db)
    plan={'summary':'Launch delivery','name':'Agent launch','project_key':'AGENTQA',
        'milestones':[{'key':'release','name':'Release'}], 'tasks':[
            {'key':'design','title':'Design','milestone_key':'release'},
            {'key':'review','title':'Review design','parent_key':'design'},
            {'key':'ship','title':'Ship','blocked_by':['design']}]}
    run=prepare(client,h,[{'tool':'pms.kickoff','payload':{'plan':plan}}])
    assert run['status']=='awaiting_approval',run
    final=complete(client,db,h,run)
    assert final['status']=='succeeded',final
    tasks=db.query(PMSTask).filter_by(project_id=final['receipts'][0]['record_id']).all()
    assert len(tasks)==3
    assert next(t for t in tasks if t.title=='Review design').parent_task_id


def test_playbook_execution_undo_and_autonomy_boundaries(client,db):
    h,_,p,t=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'pms.save_playbook','record_id':p,'payload':{'title':'Priority','plan':{
        'summary':'Raise priority','steps':[{'tool':'update_task','task_id':t,'changes':{'priority':'High'}}]}}}])
    saved=complete(client,db,h,run)
    book=saved['receipts'][0]['record_id']
    rule=prepare(client,h,[{'tool':'pms.event_rule','record_id':p,'payload':{
        'title':'Overdue priority','playbook_id':book,'trigger':'overdue','autonomous':True}}])
    assert rule['status']=='failed',rule
    draft=prepare(client,h,[{'tool':'pms.run_playbook','record_id':p,'payload':{'playbook_id':book}}])
    assert draft['status']=='awaiting_approval',draft
    executed=complete(client,db,h,draft)
    assert executed['status']=='succeeded',executed
    inverse=prepare(client,h,[{'tool':'pms.undo','record_id':p,'payload':{'run_id':executed['receipts'][0]['pms_run_id']}}])
    assert inverse['status']=='awaiting_approval',inverse
    restored=complete(client,db,h,inverse)
    assert restored['status']=='succeeded',restored
    db.expire_all()
    assert db.get(PMSTask,t).priority!='High'


def test_selection_limit_retires_child_drafts(client,db):
    from app.ai_operator.models import OperatorRun
    h,_,p,t=setup_suite(client,db)
    second=client.post(f'/api/v1/project-management/projects/{p}/tasks',headers=h,json={'title':'Other','task_key':'OP-2'}).json()['id']
    run=prepare(client,h,[{'tool':'pms.task_plan','record_id':p,'payload':{'plan':task_plan(second)}}],project_id=p,task_ids=[t])
    assert run['status']=='failed',run
    assert db.query(OperatorRun).order_by(OperatorRun.id.desc()).first().status=='cancelled'


def test_parent_resumes_only_known_pms_checkpoint(client,db,monkeypatch):
    from fastapi import HTTPException
    from app.apps.project_management.api import router as pms
    h,_,p,t=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'pms.task_plan','record_id':p,'payload':{'plan':task_plan(t)}}])
    approve(client,h,run)
    tick(client,db)
    process_batch(db,limit=1)
    original=pms.create_task_checklist_operation
    def fail(*args,**kwargs):raise HTTPException(422,'Temporary domain failure')
    monkeypatch.setattr(pms,'create_task_checklist_operation',fail)
    process_batch(db,limit=1)
    tick(client,db)
    paused=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert paused['status']=='paused',paused
    assert len(paused['result']['pms_progress']['result']['receipts'])==1
    monkeypatch.setattr(pms,'create_task_checklist_operation',original)
    response=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert response.status_code==200,response.text
    process_batch(db)
    tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    assert db.query(PMSChecklistItem).filter_by(task_id=t).count()==1


def test_cancel_during_child_enqueue_never_reactivates_parent(client,db,monkeypatch):
    from app.ai_operator import suite
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.models import OperatorRun
    h,_,p,t=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'pms.task_plan','record_id':p,'payload':{'plan':task_plan(t)}}])
    approve(client,h,run)
    original=suite.api_call
    async def cancel_during_enqueue(*args,**kwargs):
        response=await original(*args,**kwargs)
        if args[3].endswith('/approve'):
            parent=db.get(SuiteRun,run['id']);parent.status='cancelling';db.commit()
        return response
    monkeypatch.setattr(suite,'api_call',cancel_during_enqueue)
    tick(client,db)
    db.expire_all()
    assert db.get(SuiteRun,run['id']).status=='cancelled'
    assert db.query(OperatorRun).order_by(OperatorRun.id.desc()).first().status=='cancelled'
    process_batch(db)
    assert db.get(PMSTask,t).priority!='High'


@pytest.mark.parametrize('text,expected',[('tomorrow','2026-10-25'),('next monday','2026-10-26'),('in 2 weeks','2026-11-07'),('end of month','2026-10-31')])
def test_relative_dates(text,expected):
    assert resolve_date(text,today=date(2026,10,24))==expected
