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
        catalog=client.get(root+'/events/catalog');assert catalog.is_success
        assert any(item['id']=='pms.message_received' for item in catalog.json()['items'])
        assert any(item['id']=='crm.customer_email_reply' for item in catalog.json()['items'])
        assert any(item['id']=='crm.whatsapp_message_received' for item in catalog.json()['items'])
        assert {name+'.webhook_received' for name in ('crm','pms','hrms','srm','fam')}<={item['id'] for item in catalog.json()['items']}
        hooks=client.get(root+'/events/webhooks',params={'module':'CRM'});assert hooks.is_success
        assert 'no-store' in hooks.headers.get('Cache-Control','')
        assert all(set(item)=={'id','name','module','entity','events'} for item in hooks.json()['items'])
        tools=client.get('/api/v1/ai-operator/suite/tools');assert tools.is_success
        names={item['name'] for item in tools.json()['tools']}
        assert {'crm.event_message','pms.event_message'}<=names
        workspaces=client.get('/api/v1/project-management/workspaces');assert workspaces.is_success
        picker_checked=False
        if workspaces.json():
            picker=client.get(root+'/events/chat-conversations',params={'workspace_id':workspaces.json()[0]['id']})
            assert picker.is_success,f'Conversation picker HTTP {picker.status_code}'
            assert all(set(item)=={'id','name','kind'} for item in picker.json()['items'])
            assert 'no-store' in picker.headers.get('Cache-Control','')
            picker_checked=True
        try:
            response=client.post(root,json={'name':'Synthetic event intake review','instructions':'Read authorized CRM deals only.','modules':['CRM'],'tools':['crm.deals'],'provider':'local'});assert response.is_success;agent=response.json()['id']
            body={'request_key':str(uuid4()),'agent_id':agent,'event':'crm.deal_stage','prompt':'Show CRM deals','expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'max_per_day':1}
            response=client.post(root+'/events/preview',json=body);assert response.is_success,f'Preview HTTP {response.status_code}'
            review=response.json();subscription=review['id'];assert review['state']=='preview' and review['deliveries']==[]
            assert client.post(root+'/events/preview',json=body).json()['id']==subscription
            assert client.post(root+f'/events/{subscription}/activate',json={'revision':review['revision'],'preview_hash':'0'*64}).status_code==409
            response=client.post(root+f'/events/{subscription}/cancel',json={'revision':review['revision']});assert response.is_success
            assert response.json()['state']=='cancelled' and response.json()['deliveries']==[]
            print(json.dumps({'message_trigger_catalog':True,'customer_email_reply_catalog':True,'whatsapp_trigger_catalog':True,'signed_webhook_catalog':True,'private_webhook_picker':True,'explicit_message_read_tools':True,'conversation_picker_read_checked':picker_checked,'private_event_preview':True,'idempotent_preview':True,'stale_activation_rejected':True,'cancel_verified':True,'intake_activated':False,'external_model_calls':0}),flush=True)
        finally:
            if subscription:
                response=client.get(root+'/events');assert response.is_success
                current=next((s for s in response.json()['items'] if s['id']==subscription),None)
                if current and current['state']!='cancelled':assert client.post(root+f'/events/{subscription}/cancel',json={'revision':current['revision']}).is_success
            if agent:assert client.delete(root+f'/{agent}').is_success


if __name__=='__main__':main()
