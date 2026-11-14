from uuid import uuid4
from app.apps.project_management.models import PMSRunningTimer,PMSTimeLog
from tests.test_suite_operator import setup_suite,approve,tick,ROOT
from tests.test_suite_workspace import say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def chat(client,h):return client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic timer dialogue'}).json()['id']


def result(client,h,run):return client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()


def test_timer_start_clarifies_project_preserves_nonce_and_inline_followup(client,db):
    h,user,pid,task=setup_suite(client,db);conversation=chat(client,h)
    question=say(client,h,conversation,'Start my timer',module='PMS')
    assert question['status']=='needs_clarification'
    nonce=question['result']['timer_draft']['session_key']
    draft=say(client,h,conversation,f'project={pid}; task={task}; description=Original intent',module='PMS')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert draft['plan']['steps'][0]['payload']['session_key']==nonce
    inline=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
        'changes':[{'step':1,'field':'description','value':'Inline timer intent'}]})
    assert inline.status_code==200,inline.text
    revised=say(client,h,conversation,'Make it billable',module='PMS')
    assert revised['status']=='awaiting_approval',revised.get('error_code')
    fields=revised['plan']['steps'][0]['payload']
    assert fields['description']=='Inline timer intent' and fields['is_billable'] is True and fields['session_key']==nonce
    assert not db.query(PMSRunningTimer).count()
    approve(client,h,revised);tick(client,db)
    assert result(client,h,revised)['status']=='succeeded'
    db.expire_all();assert db.get(PMSRunningTimer,user.id).active and db.get(PMSRunningTimer,user.id).is_billable


def test_timer_status_then_stop_uses_current_session_and_cites_native_page(client,db):
    h,user,pid,task=setup_suite(client,db);conversation=chat(client,h)
    pending=say(client,h,conversation,f'Start a timer for task {task}',module='PMS')
    assert pending['status']=='awaiting_approval',pending.get('error_code')
    approve(client,h,pending);tick(client,db)
    running=say(client,h,conversation,'Is my timer running?',module='PMS')
    assert running['status']=='answered',running.get('error_code')
    assert 'is running' in running['plan']['summary'] and not running['receipts']
    assert running['result']['citations'][0]['href']==f'/pms/time-tracking?projectId={pid}'
    stopped=say(client,h,conversation,'Stop my timer',module='PMS')
    assert stopped['status']=='awaiting_approval',stopped.get('error_code')
    approve(client,h,stopped);tick(client,db)
    assert result(client,h,stopped)['status']=='succeeded'
    db.expire_all();assert db.query(PMSTimeLog).count()==1 and not db.get(PMSRunningTimer,user.id).active
    inactive=say(client,h,conversation,'Check my timer',module='PMS')
    assert inactive['status']=='answered' and 'no active timer' in inactive['plan']['summary']


def test_timer_discard_and_post_execution_field_correction_cannot_restart(client,db):
    h,user,pid,task=setup_suite(client,db);conversation=chat(client,h)
    pending=say(client,h,conversation,f'Start timer: project={pid}',module='PMS');approve(client,h,pending);tick(client,db)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'conversation_id':conversation,'text':'description=Silent restart'})
    assert response.status_code==409,response.text
    discard=say(client,h,conversation,'Discard my timer',module='PMS')
    assert discard['status']=='awaiting_approval',discard.get('error_code')
    approve(client,h,discard);tick(client,db)
    assert result(client,h,discard)['status']=='succeeded'
    db.expire_all();assert not db.get(PMSRunningTimer,user.id).active and not db.query(PMSTimeLog).count()


def test_timer_pending_source_change_requires_fresh_review(client,db):
    from app.apps.project_management.timers import start_timer_operation,StartInput
    h,user,pid,task=setup_suite(client,db);conversation=chat(client,h)
    pending=say(client,h,conversation,f'Start timer: project={pid}',module='PMS')
    assert pending['status']=='awaiting_approval'
    start_timer_operation(StartInput(project_id=pid,session_key=uuid4()),db,user)
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'conversation_id':conversation,'text':'description=Must not rebase'})
    assert response.status_code==409,response.text
    assert db.query(PMSTimeLog).count()==0


def test_timer_status_clarification_and_refresh_do_not_reuse_stale_status(client,db):
    from app.apps.project_management.timers import start_timer_operation,StartInput
    h,user,pid,task=setup_suite(client,db);conversation=chat(client,h)
    question=say(client,h,conversation,'Is my timer running?',module='PMS')
    assert question['status']=='needs_clarification'
    inactive=say(client,h,conversation,f'project={pid}',module='PMS')
    assert inactive['status']=='answered',inactive.get('error_code')
    assert 'no active timer' in inactive['plan']['summary']
    start_timer_operation(StartInput(project_id=pid,session_key=uuid4()),db,user)
    refreshed=say(client,h,conversation,f'project={pid}',module='PMS')
    assert refreshed['status']=='answered',refreshed.get('error_code')
    assert 'is running' in refreshed['plan']['summary'] and not refreshed['receipts']
    assert not db.query(PMSTimeLog).count()


def test_timer_request_does_not_replace_unrelated_pending_approval(client,db):
    h,user,pid,task=setup_suite(client,db);conversation=chat(client,h)
    pending=say(client,h,conversation,'CRM: Create a task called Synthetic pending intent',module='CRM')
    assert pending['status']=='awaiting_approval',pending.get('error_code')
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'conversation_id':conversation,'text':f'Start timer: project={pid}'})
    assert response.status_code==409,response.text
    assert result(client,h,pending)['status']=='awaiting_approval'
    assert not db.query(PMSRunningTimer).count()
