"""Live reviewed view creation in a new synthetic project; no cloud calls."""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.ai_operator.models import OperatorApiLog
from app.ai_operator.suite_models import SuiteRun
from app.apps.project_management.models import PMSSavedFilter


def main():
    root='/api/v1/ai-operator/suite';chat=project=view=run=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs);assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD}).json()
        client.headers['Authorization']='Bearer '+auth['access_token']
        workspace=call('POST','/api/v1/project-management/workspaces',json={'name':'Synthetic saved view QA '+uuid4().hex[:8]}).json()['id']
        try:
            project=call('POST','/api/v1/project-management/projects',json={'name':'Synthetic saved view project','project_key':'SV'+uuid4().hex[:6].upper(),'workspace_id':workspace}).json()['id']
            chat=call('POST',root+'/conversations',json={'workspace_id':workspace,'title':'Synthetic saved view followups'}).json()['id']
            def say(text):
                nonlocal run
                run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'PMS','workspace_id':workspace,'conversation_id':chat,'text':text}).json()
                return run
            assert say('Save task view called Synthetic delivery focus: priority=High')['status']=='needs_clarification'
            assert say(f'project={project}; status=Blocked')['status']=='awaiting_approval'
            run=call('POST',root+f'/runs/{run["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':run['plan_hash'],
                'changes':[{'step':1,'field':'name','value':'Synthetic reviewed view'}]}).json()
            assert say('priority=Urgent')['status']=='awaiting_approval'
            assert run['plan']['steps'][0]['payload']['name']=='Synthetic reviewed view'
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{run["id"]}').json()
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded';view=run['receipts'][0]['record_id']
            assert run['result_cards'][0]['href']==f'/pms/tasks/advanced?view={view}'
            views=call('GET','/api/v1/project-management/saved-views',params={'entityType':'task'}).json()
            saved=next(item for item in views if item['id']==view)
            assert saved['visibility']=='private' and not saved['is_shared'] and not saved['is_default']
            assert saved['filters']['projectId']==str(project) and saved['filters']['priority']=='Urgent' and saved['filters']['status']=='Blocked'
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            with SessionLocal() as db:
                assert db.query(PMSSavedFilter).filter_by(project_id=project).count()==1
                ids=[row.id for row in db.query(SuiteRun).filter_by(workspace_id=workspace)]
                assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(ids)).count()==0
            created_view=view;call('DELETE',f'/api/v1/project-management/saved-views/{view}');view=None
            restored=call('GET',root+f'/conversations/{chat}').json()
            assert any(value['id']==run['id'] for value in restored['runs'])
            value={'workspace_id':workspace,'project_id':project,'suite_run_id':run['id'],'view_id':created_view,'chat_id':chat,'native_view_verified':True,
                'conversation_preserved_after_private_view_delete':True,'private_not_default':True,'followup_after_inline_revision':True,'duplicate_prevented':True,'external_model_calls':0,'business_messages_sent':0}
            (Path(__file__).resolve().parents[2]/'.local/saved-view-actions-live-result.json').write_text(json.dumps(value,indent=2));print(json.dumps(value))
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            if not run or run['status'] not in {'queued','executing'}:
                if chat:call('DELETE',root+f'/conversations/{chat}')
                if view:call('DELETE',f'/api/v1/project-management/saved-views/{view}')
                # Retain the synthetic project as an archived audit fixture.
                # A real project deletion intentionally revokes cached sources.
                if project:call('POST',f'/api/v1/project-management/projects/{project}/archive',params={'archive':True})


if __name__=='__main__':main()
