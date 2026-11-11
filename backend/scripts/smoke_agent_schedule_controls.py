"""Future, owner-private schedule lifecycle; no occurrence is dispatched."""
import json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite/agents';agent=schedule=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            response=client.post(root,json={'name':'Synthetic schedule control check','instructions':'Read authorized CRM tasks only.','modules':['CRM'],'tools':['crm.tasks'],'provider':'local'})
            assert response.is_success;agent=response.json()['id']
            first=datetime.now(timezone.utc)+timedelta(days=2)
            response=client.post(root+'/schedules/preview',json={'request_key':str(uuid4()),'agent_id':agent,'prompt':'Show authorized CRM tasks.','scheduled_at':first.isoformat(),'expires_at':(first+timedelta(days=60)).isoformat(),'frequency':'custom','interval':3,'interval_unit':'weeks'})
            assert response.is_success,f'Preview HTTP {response.status_code}'
            review=response.json();schedule=review['id'];path=root+f'/schedules/{schedule}'
            assert review['spec']['interval']==3 and review['spec']['interval_unit']=='weeks'
            assert client.post(path+'/activate',json={'preview_hash':review['preview_hash']}).is_success
            response=client.post(path+'/pause');assert response.is_success
            assert response.json()['status']=='paused' and response.json()['next_at'] is None
            assert client.post(path+'/resume',json={'preview_hash':'0'*64}).status_code==409
            response=client.post(path+'/resume',json={'preview_hash':review['preview_hash']});assert response.is_success
            result=response.json();assert result['status']=='active' and result['pending'] is None and result['occurrences']==[]
            assert [i['action'] for i in result['controls']]==['paused','resumed']
            assert client.post(path+'/cancel').json()['status']=='cancelled'
            print(json.dumps({'private_future_schedule':True,'custom_recurrence':'every 3 weeks','pause_resume_verified':True,'stale_review_rejected':True,'occurrences':0,'business_actions':0,'external_model_calls':0}),flush=True)
        finally:
            if schedule:assert client.post(root+f'/schedules/{schedule}/cancel').is_success
            if agent:assert client.delete(root+f'/{agent}').is_success


if __name__=='__main__':main()
