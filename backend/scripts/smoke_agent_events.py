"""Private event subscription review/cancellation; never activates real intake."""
import json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite/agents';agent=subscription=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD});assert response.is_success
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            response=client.post(root,json={'name':'Synthetic event intake review','instructions':'Read authorized CRM deals only.','modules':['CRM'],'tools':['crm.deals'],'provider':'local'});assert response.is_success;agent=response.json()['id']
            body={'request_key':str(uuid4()),'agent_id':agent,'event':'crm.deal_stage','prompt':'Show CRM deals','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'max_per_day':1}
            response=client.post(root+'/events/preview',json=body);assert response.is_success,f'Preview HTTP {response.status_code}'
            review=response.json();subscription=review['id'];assert review['state']=='preview' and review['deliveries']==[]
            assert client.post(root+'/events/preview',json=body).json()['id']==subscription
            assert client.post(root+f'/events/{subscription}/activate',json={'revision':review['revision'],'preview_hash':'0'*64}).status_code==409
            response=client.post(root+f'/events/{subscription}/cancel',json={'revision':review['revision']});assert response.is_success
            assert response.json()['state']=='cancelled' and response.json()['deliveries']==[]
            print(json.dumps({'private_event_preview':True,'idempotent_preview':True,'stale_activation_rejected':True,'cancel_verified':True,'intake_activated':False,'external_model_calls':0}),flush=True)
        finally:
            if subscription:
                response=client.get(root+'/events');assert response.is_success
                current=next((s for s in response.json()['items'] if s['id']==subscription),None)
                if current and current['state']!='cancelled':assert client.post(root+f'/events/{subscription}/cancel',json={'revision':current['revision']}).is_success
            if agent:assert client.delete(root+f'/{agent}').is_success


if __name__=='__main__':main()
