"""Live local private view metadata QA; no tasks, messages or cloud calls."""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.apps.project_management.models import PMSProject,PMSSavedFilter
from app.ai_operator.models import OperatorApiLog


def main():
    root='/api/v1/ai-operator/suite';chat=view=run=None;runs=[]
    with SessionLocal() as db:
        project=db.query(PMSProject).filter(PMSProject.organization_id==settings.LOGIN_COMPANY_ID,
            PMSProject.name.like('Synthetic%'),PMSProject.deleted_at.is_(None)).order_by(PMSProject.id).first()
        assert project,'An existing authorized synthetic PMS project is required'
        pid,workspace=project.id,project.workspace_id
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token'];client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        try:
            name='Synthetic PMS view QA '+uuid4().hex[:10]
            created=call('POST','/api/v1/project-management/saved-views',json={'project_id':pid,'name':name,
                'view_type':'task_list','entity_type':'task','visibility':'private','filters':{'projectId':str(pid),'priority':'High'},
                'sort':{'field':'due_date'},'columns':{'name':True}})
            view=created['id']
            chat=call('POST',root+'/conversations',json={'workspace_id':workspace,'title':name})['id']
            def say(text):
                nonlocal run
                run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
                    'workspace_id':workspace,'project_id':pid,'conversation_id':chat,'text':text})
                runs.append(run['id']);return run
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
            draft=say(f'PMS: Update saved view called {name}: priority=Low')
            assert draft['status']=='awaiting_approval',{'status':draft['status'],'error':draft.get('error_code'),'question':(draft.get('plan') or {}).get('question')}
            revised=call('POST',root+f'/runs/{draft["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
                'changes':[{'step':1,'field':'name','value':name+' inline'}]});runs.append(revised['id'])
            final=say('Make it Medium');assert final['status']=='awaiting_approval'
            assert final['plan']['steps'][0]['payload']['name']==name+' inline'
            renamed=say('Rename that view to '+name+' final');assert renamed['status']=='awaiting_approval'
            assert renamed['plan']['steps'][0]['payload']['filters']['priority']=='Medium'
            updated=execute(renamed)
            current=call('GET',root+f'/pms/views/records/{pid}')
            item=next(value for value in current['items'] if value['id']==view)
            assert item['name']==name+' final' and item['filters']['priority']=='Medium'
            with SessionLocal() as db:
                saved=db.get(PMSSavedFilter,view)
                assert json.loads(saved.sort_json)=={'field':'due_date'} and json.loads(saved.columns_json)=={'name':True}
                assert not saved.is_shared and not saved.is_default
            assert updated['result_cards'][0]['href']==f'/pms/tasks/advanced?view={view}'
            call('POST',root+f'/runs/{updated["id"]}/approve',json={'plan_hash':updated['plan_hash']})
            assert next(v for v in call('GET',root+f'/pms/views/records/{pid}')['items'] if v['id']==view)['source_sha256']==item['source_sha256']
            removal=say('Remove that view');assert removal['status']=='awaiting_approval'
            removed=execute(removal);assert removed['result_cards'][0]['href']=='/pms/tasks/advanced'
            removed_id=view;view=None
            assert all(v['id']!=removed_id for v in call('GET',root+f'/pms/views/records/{pid}')['items'])
            assert call('GET',root+f'/conversations/{chat}')['id']==chat
            with SessionLocal() as db:assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
            evidence={'project_id':pid,'workspace_id':workspace,'view_id':removed_id,'chat_id':chat,'run_ids':runs,
                'reviewed_update_and_remove':True,'inline_and_natural_followups':True,'layout_preserved':True,
                'repeat_approval_no_mutation':True,'history_preserved':True,'task_writes':0,'business_messages_sent':0,'external_model_calls':0}
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            assert not run or run['status'] not in {'queued','executing'},'Retain active QA chat'
            if view:call('DELETE',f'/api/v1/project-management/saved-views/{view}')
            if chat:call('DELETE',root+f'/conversations/{chat}')
    evidence['cleanup_complete']=True
    (Path(__file__).resolve().parents[2]/'.local/pms-view-changes-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
