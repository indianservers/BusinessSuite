"""Live local cursor/lookup and reviewed action QA using private synthetic views."""
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
    root='/api/v1/ai-operator/suite';entries=[];runs=[];chat=run=None
    with SessionLocal() as db:
        project=db.query(PMSProject).filter(PMSProject.organization_id==settings.LOGIN_COMPANY_ID,
            PMSProject.name.like('Synthetic%'),PMSProject.deleted_at.is_(None)).order_by(PMSProject.id).first()
        assert project,'An existing authorized synthetic project is required'
        pid,workspace=project.id,project.workspace_id
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token'];client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        path=root+f'/pms/views/records/{pid}';prefix='Synthetic discovery QA '+uuid4().hex[:10]
        assert call('GET',path).get('page_size')==25,'Reload the paginated API before creating QA metadata'
        try:
            for index in range(26):
                value=call('POST','/api/v1/project-management/saved-views',json={'project_id':pid,'name':prefix+f' {index:02}',
                    'view_type':'task_list','entity_type':'task','visibility':'private',
                    'filters':{'projectId':str(pid),'priority':'High'},'sort':{'field':'due_date'},'columns':{'name':True}})
                entries.append({'id':value['id'],'name':value['name'],'native_snapshot':value})
                source=call('GET',path,params={'view_id':value['id']})['items']
                assert len(source)==1
                entries[-1]={**source[0],'native_snapshot':value}
            first=call('GET',path,params={'after_id':entries[0]['id']-1})
            assert [v['id'] for v in first['items']]==[v['id'] for v in entries[:25]] and first['has_more']
            second=call('GET',path,params={'after_id':first['next_after_id']})
            target=entries[-1]
            assert [v['id'] for v in second['items']]==[target['id']] and not second['has_more']
            exact=call('GET',path,params={'name':target['name'].upper()})['items']
            assert len(exact)==1 and exact[0]['source_sha256']==target['source_sha256']
            chat=call('POST',root+'/conversations',json={'workspace_id':workspace,'title':prefix})['id']
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
            draft=say(f'Update saved view called {target["name"]}: priority=Low')
            assert draft['status']=='awaiting_approval' and draft['plan']['steps'][0]['payload']['view_id']==target['id']
            revised=call('POST',root+f'/runs/{draft["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
                'changes':[{'step':1,'field':'name','value':target['name']+' reviewed'}]});runs.append(revised['id']);run=revised
            final=say('Make it Medium');assert final['plan']['steps'][0]['payload']['name']==target['name']+' reviewed'
            updated=execute(final)
            current=call('GET',path,params={'view_id':target['id']})['items'][0]
            assert current['filters']['priority']=='Medium' and current['name']==target['name']+' reviewed'
            entries[-1]=current
            call('POST',root+f'/runs/{updated["id"]}/approve',json={'plan_hash':updated['plan_hash']})
            assert call('GET',path,params={'view_id':target['id']})['items'][0]['source_sha256']==current['source_sha256']
            removal=say('Remove that view');assert removal['status']=='awaiting_approval'
            execute(removal)
            assert call('GET',path,params={'view_id':target['id']})['items']==[]
            assert call('GET',root+f'/conversations/{chat}')['id']==chat
            with SessionLocal() as db:assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
            evidence={'project_id':pid,'workspace_id':workspace,'view_ids':[v['id'] for v in entries],'chat_id':chat,'run_ids':runs,
                'cursor_pages':True,'direct_name_and_id_lookup':True,'reviewed_late_target_update_remove':True,
                'inline_and_natural_followups':True,'repeat_approval_no_mutation':True,'history_preserved':True,
                'task_writes':0,'business_messages_sent':0,'external_model_calls':0}
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            assert not run or run['status'] not in {'queued','executing'},'Retain active QA chat'
            for entry in entries:
                with SessionLocal() as db:
                    row=db.get(PMSSavedFilter,entry['id'])
                    if not row:continue
                    from app.ai_operator.pms_view_changes import state
                    from app.ai_operator.service import digest
                    assert row.name.startswith(prefix) and row.project_id==pid and row.visibility=='private' and not row.is_shared
                    if entry.get('source_sha256'):
                        assert digest(state(row))==entry['source_sha256'],'Synthetic view changed externally; retain it for review'
                    else:
                        from app.apps.project_management.api.router import _saved_view_payload
                        from app.apps.project_management.schemas import PMSSavedFilterResponse
                        snapshot=PMSSavedFilterResponse.model_validate(_saved_view_payload(row)).model_dump(mode='json')
                        assert snapshot==entry['native_snapshot'],'Synthetic view changed before source read; retain it for review'
                call('DELETE',f'/api/v1/project-management/saved-views/{entry["id"]}')
            if chat:call('DELETE',root+f'/conversations/{chat}')
    evidence['cleanup_complete']=True
    (Path(__file__).resolve().parents[2]/'.local/pms-view-discovery-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
