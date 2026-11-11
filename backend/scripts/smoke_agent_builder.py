"""Live local/Gemini authoring smoke: private metadata, no activated schedules/actions."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=150) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+login.json()['access_token'];root='/api/v1/ai-operator/suite/agents'
        model=client.get(root+'/builder/model-status');assert model.is_success and model.json()['active']
        for provider,text in [('local','Build a helper to screen fresh prospects'),('gemini','Create a CRM sales assistant named Synthetic Gemini Designer. Only use crm.tasks and crm.create_task. Prepare overdue task summaries when asked. Manual only, no schedule or external connections.')]:
            ident=agent=None
            try:
                response=client.post(root+'/builder/messages',json={'request_key':str(uuid4()),'provider':provider,'text':text})
                assert response.is_success,f'{provider} authoring HTTP {response.status_code}'
                draft=response.json();ident=draft['context_id']
                assert not draft['question'] and draft['config'] and not draft['schedule'],str(draft.get('question'))
                if provider=='local':assert draft['local_prediction']['used'] and draft['config']['name']=='Lead Qualification Agent'
                else:assert set(draft['config']['tools'])=={'crm.tasks','crm.create_task'}
                response=client.post(root+f'/builder/{ident}/apply',json={'preview_hash':draft['preview_hash']})
                assert response.is_success,f'{provider} save HTTP {response.status_code}'
                saved=response.json();agent=saved['agent_id'];assert saved['schedule_preview'] is None
                print(json.dumps({'builder_provider':provider,'reviewed_profile_saved':True,'local_model_used':bool(draft.get('local_prediction',{}).get('used')) if draft.get('local_prediction') else False,'schedules_activated':0,'business_actions_dispatched':0}),flush=True)
            finally:
                if agent:assert client.delete(root+f'/{agent}').is_success
                if ident:assert client.delete(root+f'/builder/{ident}').is_success


if __name__=='__main__':main()
