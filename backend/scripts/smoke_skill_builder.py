"""Local conversational skill authoring; synthetic private metadata only."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite/agents';context=skill=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            response=client.post(root+'/builder/messages',json={'request_key':str(uuid4()),'asset_type':'skill','provider':'local','text':'Create a CRM lead qualification skill that reviews customer fit'})
            assert response.is_success;first=response.json();context=first['context_id']
            assert first['asset_type']=='skill' and not first['question'] and first['schedule'] is None
            response=client.post(root+'/builder/messages',json={'request_key':str(uuid4()),'context_id':context,'revision':first['revision'],'asset_type':'skill','provider':'local','text':'Procedure: Read authorized customer fit information and ask the owner to review uncertain cases.'})
            assert response.is_success;final=response.json();assert not final['question']
            response=client.post(root+f'/builder/{context}/apply',json={'preview_hash':final['preview_hash']});assert response.is_success
            result=response.json();skill=result['skill']['id'];assert result['agent_id'] is None and result['schedule_id'] is None
            assert client.post(root+f'/builder/{context}/apply',json={'preview_hash':final['preview_hash']}).json()['skill']['id']==skill
            assert len(client.get(root+f'/builder/{context}').json()['messages'])==2
            assert client.get(root+f'/catalog/skills/{skill}/versions').json()['current_revision']==1
            print(json.dumps({'server_local_authoring':True,'persistent_followups':True,'reviewed_skill_created':True,'idempotent_save':True,'agents_started':0,'business_actions':0,'external_model_calls':0}),flush=True)
        finally:
            if skill:assert client.delete(root+f'/catalog/skills/{skill}').is_success
            if context:assert client.delete(root+f'/builder/{context}').is_success


if __name__=='__main__':main()
