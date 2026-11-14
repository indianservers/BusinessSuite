"""Competing recovery requests against committed, isolated PostgreSQL state."""
from threading import Barrier
from uuid import uuid4

from tests.test_pms_workflow_postgresql import live, race
from tests.test_ai_operator import isolate_generic_http_audit


def test_competing_remaining_reviews_leave_one_executable_replacement(live, monkeypatch):
    from ai_test_utils import auth_headers
    from tests.test_workload_intelligence import setup_load, task
    from tests.test_suite_operator import prepare, approve, tick
    from app.ai_operator.jobs import process_batch
    from app.ai_operator.models import OperatorRun, OperatorJob
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_agents.models import AiActionApproval
    from app.apps.project_management.models import PMSProjectMember, PMSTask
    from app.ai_operator import remaining_tasks
    from tests.rich_text_test_utils import workflow_seed_scope

    client=live.client
    with live.factory() as db:
        with workflow_seed_scope(db):
            h,user,pid,workspace,_,tid=setup_load(client,db)
        _,recipient=auth_headers(client,db,email=f'remaining-race-{uuid4()}@example.com',permissions=['pms_view'])
        with workflow_seed_scope(db):
            db.add(PMSProjectMember(project_id=pid,user_id=recipient.id,role='Member'));db.commit()
        second=task(client,h,pid,user.id,'Never dispatched priority change',1)
        value=client.get(f'/api/v1/ai-operator/suite/pms/workload/{pid}/rebalance',headers=h,
            params={'start':'2026-05-04','task_ids':[tid],'candidate_user_ids':[recipient.id]})
        assert value.status_code==200,value.text
        value=value.json()
        assert value.get('plan'),value
        source=prepare(client,h,[{'tool':'pms.task_plan','record_id':pid,'payload':{
            'plan':value['plan'],'mode':'atomic','workload_guard':value['workload_guard']}},
            {'tool':'pms.task_plan','record_id':pid,'depends_on':[1],'payload':{'plan':{
                'summary':'Remaining priority','steps':[{'tool':'update_task','task_id':second,
                    'changes':{'priority':'Urgent'}}]},'mode':'atomic'}}],
            project_id=pid,task_ids=[tid,second],workspace_id=workspace)
        assert source['status']=='awaiting_approval',{'error':source.get('error_code'),'issue':source.get('result',{}).get('planning_issue')}
        approve(client,h,source);tick(client,db)
        child=source['pms_previews']['1']['id'];pending=source['pms_previews']['2']['id']
        process_batch(db,run_ids=[child],include_schedulers=False);tick(client,db)
        db.expire_all()
        assert db.get(SuiteRun,source['id']).status=='paused'
        priority=db.get(PMSTask,second).priority
        recipient_id=recipient.id

    # Both independent HTTP request sessions finish reading the same source
    # before either is allowed to prepare/reserve its replacement.
    ready=Barrier(2)
    original=remaining_tasks.prepare
    def competing_prepare(*args,**kwargs):
        result=original(*args,**kwargs)
        # Native preview already releases the parent's project lock before
        # invoking its separate ASGI session. Release it before this test's
        # barrier too, so the other reader can reach the same checkpoint.
        args[0].commit()
        ready.wait(timeout=10)
        return result
    monkeypatch.setattr(remaining_tasks,'prepare',competing_prepare)
    def request():
        return client.post('/api/v1/ai-operator/suite/commands',headers=h,json={
            'request_key':str(uuid4()),'provider':'local','module':'PMS','workspace_id':workspace,
            'project_id':pid,'text':f'Review remaining PMS workflow #{source["id"]}'})
    responses=race(request,request)
    assert [r.status_code for r in responses]==[200,200],[r.text for r in responses]
    results=[r.json() for r in responses]
    assert sorted(r['status'] for r in results)==['awaiting_approval','failed'],results
    winner=next(r for r in results if r['status']=='awaiting_approval')
    loser=next(r for r in results if r['status']=='failed')
    assert loser['error_code']=='AI_POLICY_HTTP_409'
    with live.factory() as db:
        original_source=db.get(SuiteRun,source['id'])
        assert original_source.status=='superseded'
        assert original_source.result['remaining_review_id']==winner['id']
        assert db.get(OperatorRun,pending).status=='cancelled'
        assert db.get(PMSTask,second).priority==priority
        assert db.get(PMSTask,tid).assignee_user_ids==[recipient_id]
        for result in results:
            approval=db.get(AiActionApproval,result['approval_id'])
            assert approval.status==('pending' if result is winner else 'cancelled')
            for preview in result['pms_previews'].values():
                native=db.get(OperatorRun,preview['id'])
                assert native.status==('awaiting_approval' if result is winner else 'cancelled')
                assert db.query(OperatorJob).filter_by(run_id=native.id,kind='execute').count()==0
