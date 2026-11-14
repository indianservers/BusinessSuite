"""Live read-only workload/capacity checks; no tasks, HR mutations or cloud calls."""
import json
import argparse
from datetime import datetime,timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.apps.project_management.models import PMSProject,PMSProjectMember
from app.ai_operator.models import OperatorApiLog


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',action='store_true');args=parser.parse_args()
    scope='workspace' if args.workspace else 'project'
    root='/api/v1/ai-operator/suite';chat=run=None;runs=[]
    with SessionLocal() as db:
        project=db.query(PMSProject).join(PMSProjectMember,PMSProjectMember.project_id==PMSProject.id).filter(
            PMSProject.organization_id==settings.LOGIN_COMPANY_ID,PMSProject.name.like('Synthetic%'),
            PMSProject.deleted_at.is_(None),*( [PMSProject.workspace_id.isnot(None)] if args.workspace else [])).order_by(PMSProject.id).first()
        assert project,'An existing authorized synthetic project with members is required'
        pid,workspace=project.id,project.workspace_id
    today=datetime.now(ZoneInfo('Asia/Kolkata')).date();monday=today-timedelta(days=today.weekday())
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token'];client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        source=call('GET',root+f'/pms/workload/{pid}',params={'start':monday.isoformat(),'scope':scope})
        assert source['rows'] and source['scope']==('authorized_workspace_projects' if args.workspace else 'selected_project_only')
        native=call('GET','/api/v1/project-management/workload',params={**({'workspace_id':workspace} if args.workspace else {'projectId':pid}),'from':monday.isoformat(),'to':monday.isoformat(),'basis':'hours'})
        by_id={row['user_id']:row for row in native['rows']}
        for row in source['rows']:
            original=by_id[row['user_id']]
            assert row['planned_hours']==original['totals']['planned_hours'] and row['capacity_hours']==original['totals']['capacity_hours']
            assert '@' not in row['name']
        def keys(value):
            if isinstance(value,dict):return set(value)|set().union(*(keys(v) for v in value.values()))
            if isinstance(value,list):return set().union(*(keys(v) for v in value))
            return set()
        assert not keys(source).intersection({'email','reason','leave_type','leave_requests','employee_id'})
        assert client.get(root+f'/pms/workload/{pid}',params={'start':monday.isoformat(),'weeks':5}).status_code==422
        try:
            chat=call('POST',root+'/conversations',json={'workspace_id':workspace,'title':'Synthetic workload intelligence '+uuid4().hex[:8]})['id']
            def say(text):
                nonlocal run
                run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'auto','module':'PMS',
                    'workspace_id':workspace,'conversation_id':chat,'text':text,'timezone':'Asia/Kolkata'})
                runs.append(run['id']);return run
            assert say('PMS: Who is overloaded across projects?' if args.workspace else 'PMS: Show workload')['status']=='needs_clarification'
            answered=say(f'project={pid}')
            assert answered['status']=='answered',answered.get('error_code')
            assert answered['result']['intelligence']['provider']=='local'
            expected=f'/pms/workload?{"workspace_id="+str(workspace) if args.workspace else "projectId="+str(pid)}&from={monday.isoformat()}&to={(monday+timedelta(days=6)).isoformat()}&basis=hours'
            assert answered['result']['citations'][0]['href']==expected
            following=say('Next week');assert following['status']=='answered',following.get('error_code')
            assert following['result']['workload_request']['start']==(monday+timedelta(days=7)).isoformat()
            assert following['result']['workload_request']['scope']==scope
            assert not following['receipts'] and following['approval_id'] is None
            for ident in runs:
                value=call('GET',root+f'/runs/{ident}');assert not value['receipts'] and value['approval_id'] is None
            with SessionLocal() as db:assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
            evidence={'scope':scope,'project_count':source['project_count'],'project_id':pid,'workspace_id':workspace,'chat_id':chat,'run_ids':runs,
                'native_numbers_match':True,'no_hr_reasons_or_emails':True,'project_clarification':True,'period_followup':True,
                'cited_project_and_period':True,'auto_used_local_intelligence':True,'task_or_hr_writes':0,
                'business_messages_sent':0,'external_model_calls':0}
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            assert not run or run['status'] not in {'queued','executing'},'Retain active QA chat'
            if chat:call('DELETE',root+f'/conversations/{chat}')
    evidence['cleanup_complete']=True
    (Path(__file__).resolve().parents[2]/('.local/workspace-workload-live-result.json' if args.workspace else '.local/workload-intelligence-live-result.json')).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
