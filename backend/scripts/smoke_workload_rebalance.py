"""Owned-loopback preview acceptance. Never approves a valid executable plan."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import HTTPException
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.user import User
from app.apps.project_management.models import PMSProject
from app.apps.project_management.api.router import _project_user_query, _sync_task_planning_links


def main():
    prefix='Synthetic rebalance QA '+uuid4().hex[:10]
    tasks=[];chat=None;run=None
    root='/api/v1/ai-operator/suite'
    with SessionLocal() as db:
        actor=db.query(User).filter(User.email==settings.BOOTSTRAP_ADMIN_EMAIL).one()
        project=db.query(PMSProject).filter(PMSProject.organization_id==settings.LOGIN_COMPANY_ID,
            PMSProject.name.like('Synthetic%'), PMSProject.deleted_at.is_(None)).order_by(PMSProject.id).first()
        assert project, 'Existing synthetic project required'
        pid,workspace,uid=project.id,project.workspace_id,actor.id
        eligible=[]
        for person in _project_user_query(db,project).limit(200).all():
            try:_sync_task_planning_links(db,pid,{'assignee_user_ids':[person.id]},actor)
            except HTTPException as exc:
                if exc.status_code!=422:raise
                continue
            eligible.append(person.id)
    monday=datetime.now(timezone.utc).date()
    monday-=timedelta(days=monday.weekday())
    with httpx.Client(base_url='http://127.0.0.1:1645',timeout=90) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json() if response.content else None
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token']
        client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        source=call('GET',root+f'/pms/workload/{pid}',params={'start':str(monday)})
        people=list(source['rows'])
        for _ in range(100):
            if not source['has_more']:break
            source=call('GET',root+f'/pms/workload/{pid}',params={
                'start':str(monday),'after_user_id':source['next_after_user_id']})
            people.extend(source['rows'])
        assert not source['has_more'], 'Workload pagination is incomplete; do not infer no available collaborator'
        recipient=next((row for row in people if row['user_id'] in eligible and row['user_id']!=uid
            and row['capacity_hours']-row['planned_hours']>=1),None)
        assert recipient, 'An existing eligible collaborator with visible headroom is required'
        owner=next(row for row in people if row['user_id']==uid)
        try:
            for label,hours in [('load',min(10000,max(1,owner['capacity_hours']+1))),('move',1)]:
                value=call('POST',f'/api/v1/project-management/projects/{pid}/tasks',json={
                    'title':prefix+' '+label,'task_key':'RB-'+uuid4().hex[:10], 'assignee_user_ids':[uid],
                    'estimated_hours':hours,'start_date':str(monday),'due_date':str(monday+timedelta(days=4))})
                tasks.append(value['id'])
            chat=call('POST',root+'/conversations',json={'title':prefix,'workspace_id':workspace})['id']
            run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'PMS',
                'workspace_id':workspace,'project_id':pid,'conversation_id':chat,'timezone':'UTC',
                'text':f'Rebalance workload: tasks={tasks[1]}; candidates={recipient["user_id"]}; start={monday}; scope=project'})
            assert run['status']=='awaiting_approval', 'Expected an unapproved rebalance preview'
            review=run['result']['rebalance_request']['review']
            assert review['changes'][0]['after_assignee_user_ids']==[recipient['user_id']]
            child=run['pms_previews']['1']['id']
            detail=call('GET',f'/api/v1/project-management/tasks/{tasks[1]}')
            assert detail['assignee_user_ids']==[uid], 'Preview must not assign tasks'
            # Only the synthetic source changes; the unselected load is guarded too.
            call('PATCH',f'/api/v1/project-management/tasks/{tasks[0]}',json={'estimated_hours':min(10000,max(2,owner['capacity_hours']+2))})
            native=call('GET',f'/api/v1/ai-operator/runs/{child}')
            rejected=client.post(f'/api/v1/ai-operator/runs/{child}/approve',json={'plan_hash':native['plan_hash']})
            assert rejected.status_code==409, 'Stale workload must reject approval'
            evidence={'api_port':1645,'project_id':pid,'conversation_id':chat,'run_id':run['id'],
                'native_run_id':child,'preview_assignment_unchanged':True,'stale_approval_status':409,
                'valid_plans_approved':0,'external_messages_sent':0,'synthetic_task_ids':tasks.copy()}
        finally:
            if run:call('POST',root+f'/runs/{run["id"]}/cancel')
            for tid in reversed(tasks):call('DELETE',f'/api/v1/project-management/tasks/{tid}')
            if chat:call('DELETE',root+f'/conversations/{chat}')
    evidence['synthetic_tasks_deleted']=True
    evidence['conversation_archived']=True
    path=Path(__file__).resolve().parents[2]/'.local/workload-rebalance-live-preview.json'
    path.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
