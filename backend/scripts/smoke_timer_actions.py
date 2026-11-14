"""Live synthetic timers, preserving any original inactive owner cursor."""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.user import User
from app.apps.project_management.models import PMSProject,PMSRunningTimer,PMSTimeLog
from app.ai_operator.models import OperatorApiLog
from app.ai_operator.service import digest
from app.ai_operator.timer_actions import state


def values(row):return {column.name:getattr(row,column.name) for column in PMSRunningTimer.__table__.columns} if row else None


def main():
    root='/api/v1/ai-operator/suite';chat=run=None;runs=[];keys=set();log_id=None;expected=None;cleaned=False
    prefix='Synthetic timer QA '+uuid4().hex[:10]
    with SessionLocal() as db:
        actor=db.query(User).filter(User.email==settings.BOOTSTRAP_ADMIN_EMAIL).one();uid=actor.id
        timer=db.get(PMSRunningTimer,uid)
        assert not timer or not timer.active,'Existing active timer must not be interrupted'
        original=values(timer)
        original_source=digest(state(timer))
        project=db.query(PMSProject).filter(PMSProject.organization_id==settings.LOGIN_COMPANY_ID,
            PMSProject.name.like('Synthetic%'),PMSProject.deleted_at.is_(None)).order_by(PMSProject.id).first()
        assert project,'An existing synthetic project is required'
        pid,workspace=project.id,project.workspace_id
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json() if response.content else None
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token'];client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        def say(text):
            nonlocal run
            run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
                'workspace_id':workspace,'conversation_id':chat,'text':text})
            runs.append(run['id']);return run
        def execute(value):
            nonlocal run,expected
            call('POST',root+f'/runs/{value["id"]}/approve',json={'plan_hash':value['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{value["id"]}')
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded',run.get('error_code')
            expected=run['result']['timer_checkpoint']['state_hash']
            return run
        try:
            # Recheck immediately before proposals; an existing user clock wins.
            assert call('GET','/api/v1/project-management/timer') is None,'Existing active timer must not be interrupted'
            chat=call('POST',root+'/conversations',json={'title':prefix,'workspace_id':workspace})['id']
            question=say('Start my timer');assert question['status']=='needs_clarification'
            nonce=question['result']['timer_draft']['session_key'];keys.add(nonce)
            pending=say(f'project={pid}; description={prefix}; billable=false')
            assert pending['status']=='awaiting_approval',pending.get('error_code')
            revised=call('POST',root+f'/runs/{pending["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':pending['plan_hash'],
                'changes':[{'step':1,'field':'description','value':prefix+' reviewed'}]});run=revised;runs.append(revised['id'])
            final=say('Make it nonbillable')
            assert final['status']=='awaiting_approval',final.get('error_code')
            payload=final['plan']['steps'][0]['payload']
            assert payload['session_key']==nonce and payload['description']==prefix+' reviewed' and payload['is_billable'] is False
            assert payload['source_sha256']==original_source,'Original inactive timer changed; do not overwrite it'
            created=execute(final)
            assert created['receipts'][0]['timer_active'] is True
            native=call('GET','/api/v1/project-management/timer')
            assert native['session_key']==nonce and native['description']==prefix+' reviewed'
            call('POST',root+f'/runs/{created["id"]}/approve',json={'plan_hash':created['plan_hash']})
            assert call('GET','/api/v1/project-management/timer')['session_key']==nonce
            running=say('Is my timer running?')
            assert running['status']=='answered' and 'is running' in running['plan']['summary']
            assert running['result']['citations'][0]['href']==f'/pms/time-tracking?projectId={pid}'
            pending_stop=say('Stop my timer');assert pending_stop['status']=='awaiting_approval',pending_stop.get('error_code')
            stopped=execute(pending_stop);log_id=stopped['receipts'][0]['record_id']
            with SessionLocal() as db:
                log=db.get(PMSTimeLog,log_id)
                assert log.user_id==uid and log.description.startswith(prefix) and log.approval_status=='Pending' and not log.is_billable
                assert log.duration_minutes==stopped['receipts'][0]['duration_minutes'] and log.duration_minutes>=1
            call('POST',root+f'/runs/{stopped["id"]}/approve',json={'plan_hash':stopped['plan_hash']})
            assert call('GET','/api/v1/project-management/timer') is None
            inactive=say('Check my timer');assert inactive['status']=='answered' and 'no active timer' in inactive['plan']['summary']
            again=say(f'Start timer: project={pid}; description={prefix} discard; billable=false')
            assert again['status']=='awaiting_approval',again.get('error_code')
            next_key=again['plan']['steps'][0]['payload']['session_key'];assert next_key!=nonce;keys.add(next_key)
            execute(again)
            discard=say('Discard my timer');assert discard['status']=='awaiting_approval',discard.get('error_code')
            discarded=execute(discard);assert discarded['receipts'][0]['timer_active'] is False
            assert call('GET','/api/v1/project-management/timer') is None
            with SessionLocal() as db:
                assert db.query(PMSTimeLog).filter(PMSTimeLog.user_id==uid,PMSTimeLog.description.like(prefix+'%')).count()==1
                assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
            evidence={'project_id':pid,'workspace_id':workspace,'chat_id':chat,'run_ids':runs,'time_log_id':log_id,
                'reviewed_start_stop_discard':True,'server_nonce_and_inline_followup':True,'cited_status_running_and_inactive':True,
                'repeat_approval_no_duplicate':True,'native_duration_matches_receipt':True,'discard_created_no_entry':True,
                'existing_active_timers_interrupted':0,'external_model_calls':0,'business_messages_sent':0}
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            assert not run or run['status'] not in {'queued','executing','waiting_pms'},'Retain active QA for reconciliation'
            # Never restore over an unknown/new timer, including a concurrent
            # user change to the QA cursor. Check exact committed state first.
            with SessionLocal() as db:
                row=db.query(PMSRunningTimer).filter_by(user_id=uid).with_for_update().first()
                if row and row.session_key in keys:
                    assert expected and digest(state(row))==expected,'Timer changed; retain it for reconciliation'
                    assert not row.active and row.project_id==pid and row.description.startswith(prefix),'Retain active or changed QA timer'
                    if original is None:db.delete(row)
                    else:
                        for key,value in original.items():setattr(row,key,value)
                    db.commit()
                else:
                    assert digest(values(row))==digest(original),'Unknown timer state; do not overwrite it'
                assert digest(values(db.get(PMSRunningTimer,uid)))==digest(original)
            if log_id:
                with SessionLocal() as db:
                    log=db.get(PMSTimeLog,log_id)
                    assert log and log.user_id==uid and log.project_id==pid and log.description.startswith(prefix)
                    assert log.approval_status=='Pending' and not log.is_billable and not log.timesheet_id
                call('DELETE',f'/api/v1/project-management/time-logs/{log_id}')
            if chat:call('DELETE',root+f'/conversations/{chat}')
            cleaned=True
    evidence.update(cleanup_complete=cleaned,original_inactive_timer_restored=True,existing_business_records_modified=0)
    (Path(__file__).resolve().parents[2]/'.local/timer-actions-live-result.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
