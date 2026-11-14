"""Authenticated live guard preview/rejection without approving any valid action."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import httpx
from app.db.base import Base
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.user import User
from app.apps.project_management.models import PMSProject, PMSTask


def main():
    task_id=run_id=None
    marker='Synthetic workload guard QA '+uuid4().hex[:10]
    with SessionLocal() as db:
        actor=db.query(User).filter(User.email==settings.BOOTSTRAP_ADMIN_EMAIL).one()
        project=db.query(PMSProject).filter(PMSProject.organization_id==settings.LOGIN_COMPANY_ID,
            PMSProject.name.like('Synthetic%'),PMSProject.deleted_at.is_(None)).order_by(PMSProject.id).first()
        assert project,'Existing synthetic project required'
        pid,uid=project.id,actor.id
    monday=datetime.now(timezone.utc).date()
    monday-=timedelta(days=monday.weekday())
    with httpx.Client(base_url='http://127.0.0.1:1645',timeout=90) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json() if response.content else None
        login=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+login['access_token']
        client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        try:
            task=call('POST',f'/api/v1/project-management/projects/{pid}/tasks',json={
                'title':marker,'task_key':'WG-'+uuid4().hex[:10],'assignee_user_ids':[uid],
                'start_date':str(monday),'due_date':str(monday+timedelta(days=4)),'estimated_hours':1})
            task_id=task['id'];original_priority=task['priority']
            source=call('GET',f'/api/v1/ai-operator/suite/pms/workload/{pid}',params={'start':str(monday)})
            plan=call('POST','/api/v1/ai-operator/workbench/plans/preview',json={
                'project_id':pid,'request_key':str(uuid4()),'mode':'atomic','workload_guard':source['workload_guard'],
                'plan':{'summary':'Review synthetic priority change with workload precondition','steps':[
                    {'tool':'update_task','task_id':task_id,'changes':{'priority':'Urgent'}}]}})
            run_id=plan['id']
            assert plan['status']=='awaiting_approval'
            assert plan['workload_guard']==source['workload_guard']
            call('PATCH',f'/api/v1/project-management/tasks/{task_id}',json={'estimated_hours':2})
            response=client.post(f'/api/v1/ai-operator/runs/{run_id}/approve',json={'plan_hash':plan['plan_hash']})
            assert response.status_code==409,'Stale source must reject approval'
            current=call('GET',f'/api/v1/project-management/tasks/{task_id}')
            assert current['priority']==original_priority and current['assignee_user_ids']==[uid]
            evidence={'api_port':1645,'project_id':pid,'task_id':task_id,'native_run_id':run_id,
                'authenticated_preview':True,'source_guard_preserved':True,'stale_approval_status':409,
                'priority_unchanged':True,'assignment_unchanged':True,'valid_plans_approved':0,
                'scope':'Synthetic native task-plan guard only; not reassignment or live provider acceptance'}
        finally:
            if run_id:call('POST',f'/api/v1/ai-operator/runs/{run_id}/cancel')
            if task_id:
                with SessionLocal() as db:
                    saved=db.get(PMSTask,task_id)
                    assert saved and saved.project_id==pid and saved.title==marker,'Synthetic ownership changed; retain for reconciliation'
                call('DELETE',f'/api/v1/project-management/tasks/{task_id}')
    with SessionLocal() as db:
        assert db.get(PMSTask,task_id).deleted_at is not None
    evidence['synthetic_task_deleted']=True
    path=Path(__file__).resolve().parents[2]/'.local/workload-guard-live-preview.json'
    path.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
