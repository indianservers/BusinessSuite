"""Local conversational event authoring; save inactive intake and cancel it."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite/agents';context=agent=subscription=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        r=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD});assert r.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+r.json()['access_token']
        try:
            r=client.post(root+'/builder/messages',json={'request_key':str(uuid4()),'provider':'local','execution_provider':'local','text':'Create a CRM sales assistant that reviews opportunities when a deal changes stage'});assert r.is_success
            first=r.json();context=first['context_id'];assert not first['question'] and first['event_trigger']['event']=='crm.deal_stage'
            r=client.post(root+'/builder/messages',json={'request_key':str(uuid4()),'provider':'local','context_id':context,'revision':first['revision'],'text':'At most 2 preparations per day, cooldown 5 minutes'});assert r.is_success
            final=r.json();assert not final['question'] and final['event_trigger']['max_per_day']==2 and final['event_trigger']['min_interval_minutes']==5
            r=client.post(root+f'/builder/{context}/apply',json={'preview_hash':final['preview_hash']});assert r.is_success
            result=r.json();agent=result['agent_id'];subscription=result['event_subscription_id'];assert result['event_preview']['state']=='preview' and result['event_preview']['deliveries']==[]
            again=client.post(root+f'/builder/{context}/apply',json={'preview_hash':final['preview_hash']});assert again.is_success
            assert again.json()['event_subscription_id']==subscription and again.json()['agent_id']==agent
            restored=client.get(root+f'/builder/{context}');assert restored.is_success and restored.json()['event_subscription_id']==subscription
        finally:
            if context:
                current=client.get(root+f'/builder/{context}')
                if current.is_success:
                    agent=agent or current.json().get('agent_id');subscription=subscription or current.json().get('event_subscription_id')
            if subscription:
                current=client.get(root+f'/events/{subscription}');assert current.is_success
                if current.json()['state']!='cancelled':assert client.post(root+f'/events/{subscription}/cancel',json={'revision':current.json()['revision']}).is_success
                cancelled=client.get(root+f'/events/{subscription}')
                assert cancelled.is_success and cancelled.json()['state']=='cancelled'
            if agent:assert client.delete(root+f'/{agent}').is_success
            if context:assert client.delete(root+f'/builder/{context}').is_success
            if agent:assert client.get(root+f'/{agent}/activity').status_code==404
            if context:assert client.get(root+f'/builder/{context}').status_code==404
        print(json.dumps({'local_conversational_event_authoring':True,'limits_followup_verified':True,'inactive_intake_saved':True,'idempotent_compound_save':True,'cleanup_verified':True,'intake_activated':False,'external_model_calls':0}),flush=True)


if __name__=='__main__':main()
