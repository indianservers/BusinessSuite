from uuid import uuid4
import pytest
from app.ai_operator import suite
from app.apps.project_management.models import PMSRunningTimer,PMSTimeLog
from tests.test_suite_operator import setup_suite,prepare,approve,tick,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def source(client,h,pid):
    response=client.get(ROOT+f'/pms/timer/{pid}',headers=h)
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='private, no-store'
    return response.json()


def draft(client,h,pid,action,payload):
    return prepare(client,h,[{'tool':f'pms.{action}_timer','record_id':pid,'payload':payload}],module='PMS')


def result(client,h,run):
    response=client.get(ROOT+f'/runs/{run["id"]}',headers=h)
    assert response.status_code==200,response.text
    return response.json()


def start(client,db,h,pid,task=None):
    old=source(client,h,pid)
    pending=draft(client,h,pid,'start',{'source_sha256':old['source_sha256'],'session_key':str(uuid4()),
        'description':'Synthetic agent timer','task_id':task,'timezone':'UTC','is_billable':False})
    assert pending['status']=='awaiting_approval',pending.get('error_code')
    approve(client,h,pending);tick(client,db)
    done=result(client,h,pending);assert done['status']=='succeeded',done.get('error_code')
    return done


def test_reviewed_timer_start_stop_and_repeat_approval_use_native_log(client,db):
    h,user,pid,task=setup_suite(client,db)
    created=start(client,db,h,pid,task)
    assert created['result']['timer_changes']['1']['changes'][-1]['field']=='effect'
    assert created['receipts'][0]['timer_active'] is True
    assert created['result_cards'][0]['href']==f'/pms/time-tracking?projectId={pid}'
    old=source(client,h,pid);assert old['active'] and old['task_id']==task
    pending=draft(client,h,pid,'stop',{'source_sha256':old['source_sha256'],'session_key':old['session_key']})
    assert pending['status']=='awaiting_approval',pending.get('error_code')
    assert not db.query(PMSTimeLog).count()
    approve(client,h,pending);tick(client,db)
    stopped=result(client,h,pending);assert stopped['status']=='succeeded',stopped.get('error_code')
    assert stopped['receipts'][0]['duration_minutes']>=1 and stopped['receipts'][0]['timer_active'] is False
    assert 'as Pending time' in stopped['result_cards'][0]['body']
    row=db.query(PMSTimeLog).one();assert row.user_id==user.id and row.approval_status=='Pending' and not row.is_billable
    approve(client,h,stopped);tick(client,db);assert db.query(PMSTimeLog).count()==1


@pytest.mark.parametrize('action',['start','stop','discard'])
def test_committed_timer_receipt_recovers_without_repeating_native_write(client,db,monkeypatch,action):
    h,user,pid,task=setup_suite(client,db)
    if action!='start':start(client,db,h,pid,task)
    old=source(client,h,pid)
    payload={'source_sha256':old['source_sha256'],'session_key':str(uuid4()) if action=='start' else old['session_key']}
    pending=draft(client,h,pid,action,payload);assert pending['status']=='awaiting_approval',pending.get('error_code')
    approve(client,h,pending);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic timer receipt interruption')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    stalled=result(client,h,pending);assert stalled['status']=='needs_reconciliation',stalled.get('error_code')
    assert stalled['can_resume']
    response=client.post(ROOT+f'/runs/{pending["id"]}/resume',headers=h,json={'plan_hash':pending['plan_hash']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='succeeded'
    db.expire_all();assert db.query(PMSRunningTimer).count()==1
    assert db.query(PMSTimeLog).count()==(1 if action=='stop' else 0)


def test_timer_staleness_is_checked_at_approval_and_dispatch(client,db):
    h,user,pid,task=setup_suite(client,db)
    start(client,db,h,pid,task);old=source(client,h,pid)
    pending=draft(client,h,pid,'stop',{'source_sha256':old['source_sha256'],'session_key':old['session_key']})
    db.get(PMSRunningTimer,user.id).description='Changed after preview';db.commit()
    assert client.post(ROOT+f'/runs/{pending["id"]}/approve',headers=h,json={'plan_hash':pending['plan_hash']}).status_code==409
    old=source(client,h,pid)
    next_draft=draft(client,h,pid,'discard',{'source_sha256':old['source_sha256'],'session_key':old['session_key']})
    approve(client,h,next_draft)
    db.get(PMSRunningTimer,user.id).description='Changed after approval';db.commit();tick(client,db)
    assert result(client,h,next_draft)['status'] in {'failed','paused','needs_reconciliation'}
    db.expire_all();assert db.get(PMSRunningTimer,user.id).active and not db.query(PMSTimeLog).count()


def test_timer_source_does_not_expose_another_users_timer_or_another_project(client,db):
    from ai_test_utils import auth_headers
    h,user,pid,task=setup_suite(client,db);start(client,db,h,pid,task)
    outsider,_=auth_headers(client,db,email=f'timer-outsider-{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/pms/timer/{pid}',headers=outsider).status_code in {403,404}
    project=client.post('/api/v1/project-management/projects',headers=h,json={'name':'Synthetic other timer scope','project_key':'TA-'+uuid4().hex[:8]}).json()['id']
    assert client.get(ROOT+f'/pms/timer/{project}',headers=h).status_code==409


def test_timer_direct_write_without_executor_and_multiple_timer_steps_are_refused(client,db):
    h,user,pid,task=setup_suite(client,db);old=source(client,h,pid)
    payload={'source_sha256':old['source_sha256'],'session_key':str(uuid4())}
    response=client.post(ROOT+f'/pms/timer/{pid}/start-approved',headers=h,json={**payload,'suite_run_id':1,'suite_step':1})
    assert response.status_code in {403,409}
    pending=prepare(client,h,[{'tool':'pms.start_timer','record_id':pid,'payload':payload}]*2,module='PMS')
    assert pending['status']=='failed' and not db.query(PMSRunningTimer).count()


def test_changed_stopped_log_blocks_timer_receipt_recovery(client,db,monkeypatch):
    h,user,pid,task=setup_suite(client,db);start(client,db,h,pid,task)
    old=source(client,h,pid);pending=draft(client,h,pid,'stop',{'source_sha256':old['source_sha256'],'session_key':old['session_key']})
    approve(client,h,pending);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic stopped log receipt interruption')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    db.expire_all();row=db.query(PMSTimeLog).one();row.description='Native later correction';db.commit()
    response=client.post(ROOT+f'/runs/{pending["id"]}/resume',headers=h,json={'plan_hash':pending['plan_hash']})
    assert response.status_code==409 and db.query(PMSTimeLog).count()==1


def test_timer_switch_to_authorized_project_preserves_history(client,db):
    h,user,pid,task=setup_suite(client,db);created=start(client,db,h,pid,task)
    old=source(client,h,pid)
    discarded=draft(client,h,pid,'discard',{'source_sha256':old['source_sha256'],'session_key':old['session_key']})
    approve(client,h,discarded);tick(client,db);assert result(client,h,discarded)['status']=='succeeded'
    other=client.post('/api/v1/project-management/projects',headers=h,json={'name':'Synthetic timer next project','project_key':'TX-'+uuid4().hex[:8]}).json()['id']
    next_timer=start(client,db,h,other)
    assert next_timer['status']=='succeeded' and result(client,h,created)['status']=='succeeded'
    assert not db.query(PMSTimeLog).count()


def test_authorized_project_peer_still_cannot_read_another_users_timer(client,db):
    from ai_test_utils import auth_headers
    h,user,pid,task=setup_suite(client,db);created=start(client,db,h,pid,task)
    peer,actor=auth_headers(client,db,email=f'timer-peer-{uuid4()}@example.com',permissions=['ai_assistant','pms_view'])
    private=source(client,peer,pid)
    assert private['active'] is False and 'description' not in private and 'session_key' not in private
    assert source(client,h,pid)['active'] is True
    db.get(PMSRunningTimer,user.id).user_id=actor.id;db.commit()
    assert client.get(ROOT+f'/runs/{created["id"]}',headers=h).status_code in {403,404}
