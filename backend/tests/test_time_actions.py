from uuid import uuid4
import pytest
from app.ai_operator import suite
from app.apps.project_management.models import PMSTimeLog
from tests.test_suite_operator import setup_suite,prepare,approve,tick,ROOT
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def fields(task=None):
    return {'log_date':'2026-05-04','duration_minutes':45,'description':'Synthetic manual work','is_billable':False,'task_id':task}


def draft(client,h,pid,action,payload):
    return prepare(client,h,[{'tool':f'pms.{action}_time_log','record_id':pid,'payload':payload}],module='PMS')


def result(client,h,run):return client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()


def source(client,h,pid,ident):
    response=client.get(ROOT+f'/pms/time/{pid}',headers=h,params={'log_id':ident})
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='private, no-store'
    return response.json()


def test_time_actions_create_edit_remove_use_native_pending_entries(client,db):
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',fields(task))
    assert pending['status']=='awaiting_approval',pending.get('error_code')
    assert pending['result']['time_changes']['1']['record_id']=='New'
    assert not db.query(PMSTimeLog).count()
    approve(client,h,pending);tick(client,db)
    done=result(client,h,pending);assert done['status']=='succeeded',done.get('error_code')
    ident=done['receipts'][0]['record_id'];row=db.get(PMSTimeLog,ident)
    assert row.user_id==user.id and row.duration_minutes==45 and row.approval_status=='Pending'
    approve(client,h,done);tick(client,db);assert db.query(PMSTimeLog).count()==1
    old=source(client,h,pid,ident)
    change=draft(client,h,pid,'edit',{**fields(task),'duration_minutes':60,'log_id':ident,'source_sha256':old['source_sha256']})
    assert change['status']=='awaiting_approval',change.get('error_code')
    approve(client,h,change);tick(client,db);assert result(client,h,change)['status']=='succeeded'
    db.expire_all();assert db.get(PMSTimeLog,ident).duration_minutes==60
    current=source(client,h,pid,ident)
    remove=draft(client,h,pid,'remove',{'log_id':ident,'source_sha256':current['source_sha256']})
    assert remove['status']=='awaiting_approval',remove.get('error_code')
    approve(client,h,remove);tick(client,db);assert result(client,h,remove)['status']=='succeeded'
    db.expire_all();assert db.get(PMSTimeLog,ident) is None


@pytest.mark.parametrize('changed',[False,True])
def test_committed_time_receipt_recovery_never_duplicates(client,db,monkeypatch,changed):
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',fields(task));approve(client,h,pending)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic receipt interruption')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    db.expire_all();assert db.query(PMSTimeLog).count()==1
    stalled=result(client,h,pending);assert stalled['status']=='needs_reconciliation',stalled.get('error_code')
    assert stalled['can_resume']
    if changed:
        row=db.query(PMSTimeLog).one();row.duration_minutes=99;db.commit()
    response=client.post(ROOT+f'/runs/{pending["id"]}/resume',headers=h,json={'plan_hash':pending['plan_hash']})
    assert response.status_code==(409 if changed else 200),response.text
    if not changed:assert response.json()['status']=='succeeded'
    assert db.query(PMSTimeLog).count()==1


def test_time_edits_recheck_source_at_approval_and_reject_incomplete_definition(client,db):
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',fields(task));approve(client,h,pending);tick(client,db)
    ident=result(client,h,pending)['receipts'][0]['record_id'];old=source(client,h,pid,ident)
    incomplete=draft(client,h,pid,'edit',{'log_id':ident,'source_sha256':old['source_sha256'],'log_date':'2026-05-04','duration_minutes':60})
    assert incomplete['status']=='failed'
    change=draft(client,h,pid,'edit',{**fields(task),'duration_minutes':60,'log_id':ident,'source_sha256':old['source_sha256']})
    assert change['status']=='awaiting_approval',change.get('error_code')
    db.get(PMSTimeLog,ident).description='Native edit after preview';db.commit()
    assert client.post(ROOT+f'/runs/{change["id"]}/approve',headers=h,json={'plan_hash':change['plan_hash']}).status_code==409


def test_time_adapter_cannot_be_called_without_reviewed_executor(client,db):
    h,user,pid,task=setup_suite(client,db)
    response=client.post(ROOT+f'/pms/time/{pid}/create-approved',headers=h,json={**fields(task),'suite_run_id':1,'suite_step':1})
    assert response.status_code in {403,409}
    assert not db.query(PMSTimeLog).count()


def test_time_local_followups_collect_project_and_revise_before_approval(client,db):
    from tests.test_suite_workspace import say
    h,user,pid,task=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic personal time'}).json()['id']
    pending=say(client,h,chat,'PMS: Log 45 minutes yesterday',module='PMS')
    assert pending['status']=='needs_clarification',pending.get('error_code')
    scoped=say(client,h,chat,f'project={pid}; task={task}; date=2026-05-04; description=Reviewed work',module='PMS')
    assert scoped['status']=='awaiting_approval',scoped.get('error_code')
    revised=say(client,h,chat,'Make it 90 minutes',module='PMS')
    assert revised['status']=='awaiting_approval',revised.get('error_code')
    assert revised['plan']['steps'][0]['payload']['duration_minutes']==90
    inline=client.post(ROOT+f'/runs/{revised["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':revised['plan_hash'],
        'changes':[{'step':1,'field':'description','value':'Inline reviewed work'}]})
    assert inline.status_code==200,inline.text
    revised=say(client,h,chat,'Make it 90 minutes',module='PMS')
    assert revised['status']=='awaiting_approval',revised.get('error_code')
    assert revised['plan']['steps'][0]['payload']['description']=='Inline reviewed work'
    assert not db.query(PMSTimeLog).count()
    approve(client,h,revised);tick(client,db)
    assert result(client,h,revised)['status']=='succeeded'
    assert db.query(PMSTimeLog).one().duration_minutes==90
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'conversation_id':chat,'text':'Make it 120 minutes'})
    assert response.status_code==409,response.text
    assert db.query(PMSTimeLog).count()==1


@pytest.mark.parametrize('field,value',[('approval_status','Approved'),('user_id',999),('duration_minutes',True),('duration_minutes',1441)])
def test_time_actions_refuse_approval_impersonation_and_invalid_duration(client,db,field,value):
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',{**fields(task),field:value})
    assert pending['status']=='failed',pending
    assert not db.query(PMSTimeLog).count()


def test_time_source_owner_change_still_revokes_old_history(client,db):
    from ai_test_utils import auth_headers
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',fields(task));approve(client,h,pending);tick(client,db)
    done=result(client,h,pending);ident=done['receipts'][0]['record_id']
    other,actor=auth_headers(client,db,email=f'time-owner-{uuid4()}@example.com',permissions=['ai_assistant','pms_view'])
    assert client.get(ROOT+f'/pms/time/{pid}',headers=other,params={'log_id':ident}).status_code in {403,404}
    db.get(PMSTimeLog,ident).user_id=actor.id;db.commit()
    assert client.get(ROOT+f'/runs/{pending["id"]}',headers=h).status_code in {403,404}


def test_time_edit_source_is_checked_again_at_dispatch(client,db):
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',fields(task));approve(client,h,pending);tick(client,db)
    ident=result(client,h,pending)['receipts'][0]['record_id'];old=source(client,h,pid,ident)
    change=draft(client,h,pid,'edit',{**fields(task),'duration_minutes':60,'log_id':ident,'source_sha256':old['source_sha256']})
    approve(client,h,change)
    db.get(PMSTimeLog,ident).duration_minutes=80;db.commit();tick(client,db)
    stopped=result(client,h,change)
    assert stopped['status'] in {'failed','paused','needs_reconciliation'}
    db.expire_all();assert db.get(PMSTimeLog,ident).duration_minutes==80


def test_local_time_edit_and_remove_follow_confirmed_entry_without_recreating_it(client,db):
    from tests.test_suite_workspace import say
    h,user,pid,task=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic time correction'}).json()['id']
    initial=say(client,h,chat,f'Log time: project={pid}; minutes=45; date=2026-05-04; description=Preserve me',module='PMS')
    approve(client,h,initial);tick(client,db)
    done=result(client,h,initial);ident=done['receipts'][0]['record_id']
    edit=say(client,h,chat,'Edit that time entry: minutes=60',module='PMS')
    assert edit['status']=='awaiting_approval',edit.get('error_code')
    assert edit['plan']['steps'][0]['payload']['log_id']==ident
    assert edit['plan']['steps'][0]['payload']['description']=='Preserve me'
    inline=client.post(ROOT+f'/runs/{edit["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':edit['plan_hash'],
        'changes':[{'step':1,'field':'description','value':'Inline correction'}]})
    assert inline.status_code==200,inline.text
    corrected=say(client,h,chat,'Make it 75 minutes',module='PMS')
    assert corrected['status']=='awaiting_approval',corrected.get('error_code')
    assert corrected['plan']['steps'][0]['tool']=='pms.edit_time_log'
    assert corrected['plan']['steps'][0]['payload']['description']=='Inline correction'
    approve(client,h,corrected);tick(client,db)
    assert result(client,h,corrected)['status']=='succeeded'
    db.expire_all();assert db.query(PMSTimeLog).count()==1 and db.get(PMSTimeLog,ident).duration_minutes==75
    remove=say(client,h,chat,'Remove that time entry',module='PMS')
    assert remove['status']=='awaiting_approval',remove.get('error_code')
    approve(client,h,remove);tick(client,db)
    assert result(client,h,remove)['status']=='succeeded'
    db.expire_all();assert db.get(PMSTimeLog,ident) is None


def test_local_time_target_clarification_and_stale_draft_do_not_guess(client,db):
    from tests.test_suite_workspace import say
    h,user,pid,task=setup_suite(client,db)
    pending=draft(client,h,pid,'create',fields(task));approve(client,h,pending);tick(client,db)
    ident=result(client,h,pending)['receipts'][0]['record_id']
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic explicit time target'}).json()['id']
    question=say(client,h,chat,'Edit time entry',module='PMS')
    assert question['status']=='needs_clarification'
    targeted=say(client,h,chat,f'log={ident}',module='PMS')
    assert targeted['status']=='needs_clarification'
    edit=say(client,h,chat,'minutes=60',module='PMS')
    assert edit['status']=='awaiting_approval',edit.get('error_code')
    db.get(PMSTimeLog,ident).duration_minutes=80;db.commit()
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
        'conversation_id':chat,'text':'Make it 90 minutes'})
    assert response.status_code==409,response.text
    db.expire_all();assert db.get(PMSTimeLog,ident).duration_minutes==80
