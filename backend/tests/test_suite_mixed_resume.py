"""Real native writes across module boundaries and uncertain delivery outcomes."""
from fastapi import HTTPException

from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite, prepare, approve, tick, ROOT
from app.ai_operator.jobs import process_batch
from app.apps.crm.models import CRMTask
from app.apps.project_management.models import PMSChecklistItem, PMSTask


def test_mixed_workflow_resumes_native_checkpoint_without_replaying_completed_crm(client,db,monkeypatch):
    from app.apps.project_management.api import router as pms
    h,_,pid,tid=setup_suite(client,db)
    run=prepare(client,h,[
        {'tool':'crm.create_task','payload':{'title':'Call customer after delivery review'}},
        {'tool':'pms.task_plan','record_id':pid,'depends_on':[1],'payload':{
            'mode':'checkpointed','plan':{'summary':'Review delivery readiness','steps':[
                {'tool':'update_task','task_id':tid,'changes':{'priority':'High'}},
                {'tool':'add_checklist','task_id':tid,'title':'Verify customer handover'}]}}},
        {'tool':'crm.update_task','record_id':{'$step':1,'field':'id'},'depends_on':[1,2],
            'payload':{'priority':'Urgent'}},
    ])
    assert run['status']=='awaiting_approval',run
    approve(client,h,run);tick(client,db)
    waiting=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert waiting['status']=='waiting_pms' and len(waiting['receipts'])==1,waiting
    ident=waiting['receipts'][0]['record_id']
    db.expire_all()
    assert db.query(CRMTask).count()==1 and db.get(CRMTask,ident).priority!='Urgent'
    child=run['pms_previews']['2']['id']
    process_batch(db,limit=1,run_ids=[child],include_schedulers=False)
    original=pms.create_task_checklist_operation
    def fail(*args,**kwargs):raise HTTPException(422,'Temporary native checklist rejection')
    monkeypatch.setattr(pms,'create_task_checklist_operation',fail)
    process_batch(db,limit=1,run_ids=[child],include_schedulers=False);tick(client,db)
    paused=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert paused['status']=='paused' and paused['can_resume'],paused
    assert len(paused['receipts'])==1
    assert len(paused['result']['pms_progress']['result']['receipts'])==1
    db.expire_all()
    assert db.query(CRMTask).count()==1 and db.get(CRMTask,ident).priority!='Urgent'
    assert db.get(PMSTask,tid).priority=='High'
    assert db.query(PMSChecklistItem).filter_by(task_id=tid).count()==0
    assert client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,
        json={'plan_hash':'0'*64}).status_code==409
    monkeypatch.setattr(pms,'create_task_checklist_operation',original)
    resumed=client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert resumed.status_code==200,resumed.text
    process_batch(db,run_ids=[child],include_schedulers=False);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==3,final
    db.expire_all()
    assert db.query(CRMTask).count()==1 and db.get(CRMTask,ident).priority=='Urgent'
    assert db.query(PMSChecklistItem).filter_by(task_id=tid).count()==1
    assert tick(client,db)==0


def test_committed_crm_write_with_lost_response_requires_reconciliation_without_replay(client,db,monkeypatch):
    from app.ai_operator import suite
    h,_,pid,tid=setup_suite(client,db)
    before=db.get(PMSTask,tid).priority
    run=prepare(client,h,[
        {'tool':'crm.create_task','payload':{'title':'Customer callback response lost'}},
        {'tool':'pms.task_plan','record_id':pid,'depends_on':[1],'payload':{'plan':{
            'summary':'Only after confirmed callback','steps':[
                {'tool':'update_task','task_id':tid,'changes':{'priority':'Urgent'}}]}}},
    ])
    assert run['status']=='awaiting_approval',run
    approve(client,h,run)
    original=suite.api_call
    async def lose_response(app,authorization,method,path,payload=None,**kwargs):
        result=await original(app,authorization,method,path,payload,**kwargs)
        if method=='POST' and path=='/crm/tasks':raise TimeoutError('Response lost after canonical commit')
        return result
    monkeypatch.setattr(suite,'api_call',lose_response)
    tick(client,db)
    current=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert current['status']=='needs_reconciliation',current
    assert not current['receipts'] and not current['can_resume']
    db.expire_all()
    assert db.query(CRMTask).count()==1
    assert db.get(PMSTask,tid).priority==before
    assert client.post(ROOT+f'/runs/{run["id"]}/resume',headers=h,
        json={'plan_hash':run['plan_hash']}).status_code==409
    assert tick(client,db)==0
    assert db.query(CRMTask).count()==1
