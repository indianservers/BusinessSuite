"""Live server scheduler smoke: synthetic private drafts, no business approvals."""
import json,time
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+login.json()['access_token']
        root='/api/v1/ai-operator/suite';agent_id=schedule_id=run_id=None
        try:
            response=client.post(root+'/agents',json={'name':'Synthetic scheduled-agent QA','instructions':'Prepare the requested CRM task for separate action review.','modules':['CRM'],'tools':['crm.create_task'],'provider':'local'})
            assert response.is_success,f'Agent HTTP {response.status_code}';agent_id=response.json()['id']
            first=datetime.now(timezone.utc)+timedelta(seconds=12)
            response=client.post(root+'/agents/schedules/preview',json={'request_key':str(uuid4()),'agent_id':agent_id,'prompt':'Create CRM task called Synthetic scheduled delivery review','scheduled_at':first.isoformat(),'expires_at':(first+timedelta(hours=1)).isoformat(),'frequency':'once'})
            assert response.is_success,f'Preview HTTP {response.status_code}';schedule=response.json();schedule_id=schedule['id']
            assert client.post(root+f'/agents/schedules/{schedule_id}/activate',json={'preview_hash':schedule['preview_hash']}).is_success
            deadline=time.monotonic()+50
            while time.monotonic()<deadline:
                values=client.get(root+'/agents/schedules');assert values.is_success
                schedule=next(s for s in values.json()['items'] if s['id']==schedule_id)
                if schedule['status']=='waiting':break
                assert schedule['status'] not in ('blocked','expired','cancelled'),schedule['status']
                time.sleep(.5)
            assert schedule['status']=='waiting','Scheduler did not prepare its occurrence'
            run_id=schedule['pending']['run_id'];response=client.get(root+f'/runs/{run_id}');assert response.is_success
            run=response.json()
            assert run['status']=='awaiting_approval' and not run.get('receipts')
            assert [s['tool'] for s in run['plan']['steps']]==['crm.create_task']
            again=client.get(root+'/agents/schedules').json()['items']
            assert next(s for s in again if s['id']==schedule_id)['pending']['run_id']==run_id
            print(json.dumps({'live_scheduled_agent':True,'persistent_conversation':bool(schedule['pending']['conversation_id']),'review_required':True,'business_writes':0}),flush=True)
        finally:
            if run_id:assert client.post(root+f'/runs/{run_id}/cancel').is_success
            if schedule_id:assert client.post(root+f'/agents/schedules/{schedule_id}/cancel').is_success
            if agent_id:assert client.delete(root+f'/agents/{agent_id}').is_success


if __name__=='__main__':main()
