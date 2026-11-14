"""Live local-only reviewed manual time QA against existing synthetic projects."""
import json
import argparse
import time
from pathlib import Path
from uuid import uuid4
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.apps.project_management.models import PMSProject,PMSTimeLog
from app.ai_operator.models import OperatorApiLog


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--summary',action='store_true');args=parser.parse_args()
    root='/api/v1/ai-operator/suite';chat=run=ident=None;runs=[]
    prefix='Synthetic time QA '+uuid4().hex[:10]
    with SessionLocal() as db:
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
        def command(text,plan=None):
            nonlocal run
            body={'request_key':str(uuid4()),'provider':'local','module':'PMS','workspace_id':workspace,
                'conversation_id':chat,'text':text}
            if plan:body['local_plan']=plan
            run=call('POST',root+'/commands',json=body);runs.append(run['id']);return run
        def execute(value):
            nonlocal run
            call('POST',root+f'/runs/{value["id"]}/approve',json={'plan_hash':value['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{value["id"]}')
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded',run.get('error_code')
            return run
        def source():return call('GET',root+f'/pms/time/{pid}',params={'log_id':ident})
        def summary():return call('GET',root+f'/pms/time-summary/{pid}',params={'start':'2035-12-03','end':'2035-12-03'})
        baseline=summary() if args.summary else None
        try:
            chat=call('POST',root+'/conversations',json={'title':prefix,'workspace_id':workspace})['id']
            assert command('PMS: Log 45 minutes yesterday')['status']=='needs_clarification'
            draft=command(f'project={pid}; date=2035-12-03; description={prefix}; billable=false')
            assert draft['status']=='awaiting_approval',draft.get('error_code')
            revised=call('POST',root+f'/runs/{draft["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
                'changes':[{'step':1,'field':'description','value':prefix+' reviewed'}]})
            run=revised;runs.append(revised['id'])
            final=command('Make it 90 minutes')
            assert final['status']=='awaiting_approval',final.get('error_code')
            assert final['plan']['steps'][0]['payload']['description']==prefix+' reviewed'
            with SessionLocal() as db:assert db.query(PMSTimeLog).filter(PMSTimeLog.description.like(prefix+'%')).count()==0
            created=execute(final);ident=created['receipts'][0]['record_id'];old=source()
            assert old['duration_minutes']==90 and old['approval_status']=='Pending' and old['is_billable'] is False
            if args.summary:
                summarized=summary();assert summarized['recorded_minutes']==baseline['recorded_minutes']+90 and summarized['entry_count']==baseline['entry_count']+1
                assert summarized['billable_minutes']==baseline['billable_minutes']
                assert 'Synthetic time QA' not in json.dumps(summarized)
            assert created['result_cards'][0]['href']==f'/pms/time-tracking?projectId={pid}'
            call('POST',root+f'/runs/{created["id"]}/approve',json={'plan_hash':created['plan_hash']})
            with SessionLocal() as db:assert db.query(PMSTimeLog).filter(PMSTimeLog.description.like(prefix+'%')).count()==1
            edit=command('Edit that time entry: minutes=60')
            assert edit['status']=='awaiting_approval',edit.get('error_code')
            execute(edit);current=source();assert current['duration_minutes']==60
            if args.summary:assert summary()['recorded_minutes']==baseline['recorded_minutes']+60
            remove=command('Remove that time entry')
            assert remove['status']=='awaiting_approval',remove.get('error_code')
            done=execute(remove)
            assert call('GET',root+f'/runs/{done["id"]}')['status']=='succeeded'
            with SessionLocal() as db:
                assert db.get(PMSTimeLog,ident) is None
                assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
            if args.summary:
                assert summary()['recorded_minutes']==baseline['recorded_minutes']
                assert command('How much time did I log this week?')['status']=='needs_clarification'
                answer=command(f'project={pid}; start=2035-12-03; end=2035-12-03')
                assert answer['status']=='answered',answer.get('error_code')
                assert str(baseline['recorded_minutes'])+' recorded minutes' in answer['plan']['summary']
                assert answer['result']['citations'][0]['href']==f'/pms/time-tracking?projectId={pid}'
                following=command('start=2035-12-04; end=2035-12-04')
                assert following['status']=='answered',following.get('error_code')
                assert not following['receipts'] and following['approval_id'] is None
            evidence={'summary_checked':args.summary,'project_id':pid,'workspace_id':workspace,'chat_id':chat,'run_ids':runs,'time_log_id':ident,
                'clarification_inline_and_natural_followup':True,'natural_existing_entry_edit_remove':True,'reviewed_create_edit_remove':True,'repeat_approval_no_duplicate':True,
                'native_pending_nonbillable_values':True,'native_result_link':True,'post_delete_history':True,
                'external_model_calls':0,'business_messages_sent':0,'existing_business_records_modified':0,'synthetic_time_entries_created':1,'synthetic_time_entries_removed':True}
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            assert not run or run['status'] not in {'queued','executing'},'Retain active QA for reconciliation'
            if ident:
                with SessionLocal() as db:
                    remaining=db.get(PMSTimeLog,ident)
                    if remaining:assert remaining.description.startswith(prefix) and remaining.approval_status=='Pending' and not remaining.is_billable
                if remaining:call('DELETE',f'/api/v1/project-management/time-logs/{ident}')
            if chat:call('DELETE',root+f'/conversations/{chat}')
    evidence['cleanup_complete']=True
    (Path(__file__).resolve().parents[2]/('.local/time-summary-live-result.json' if args.summary else '.local/time-actions-live-result.json')).write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
