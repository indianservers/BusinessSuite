"""Live private-session generation; no task approval, business save or cloud call."""
import json
import time
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    with httpx.Client(base_url='http://127.0.0.1:1534/api/v1',timeout=65) as client:
        for attempt in range(20):
            try:
                if client.get('/auth/me',timeout=.5).status_code in {401,403}:break
            except httpx.RequestError:pass
            time.sleep(.5)
        else:raise RuntimeError('The current local API has not become ready')
        response=client.post('/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Application login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        response=client.get('/project-management/projects');assert response.is_success,'Project lookup failed'
        rows=response.json();rows=rows if isinstance(rows,list) else rows.get('items',[])
        assert rows,'No authorized project for a private generation check'
        project=rows[0]['id']
        response=client.post('/ai-operator/brain/sessions',json={'project_id':project});assert response.is_success,'Private session creation failed'
        chat=response.json()
        try:
            response=client.get('/ai-operator/brain/local-runtime',params={'project_id':project})
            assert response.is_success and response.json()['installed'],'Server model unavailable'
            response=client.post(f'/ai-operator/brain/sessions/{chat["id"]}/local',json={'text':'Help me prepare a project plan. Ask one question about the missing deadline.','timezone':'Asia/Kolkata'})
            assert response.is_success,f'Local generation HTTP {response.status_code}'
            reply=response.json();assert reply['kind']=='ask' and reply.get('question'),'Expected a clarification, not actions'
            response=client.post(f'/ai-operator/brain/sessions/{chat["id"]}/turns',json={'request_key':str(uuid4()),'revision':chat['revision'],'text':'Synthetic local generation verification','reply':reply,'runtime':'server','model':'SmolLM2-135M-Instruct-server'})
            assert response.is_success,'Private turn persistence failed'
            assert response.json()['turns'][-1]['runtime']=='server'
            print(json.dumps({'server_local_generation':True,'reply_kind':'ask','private_turn_persisted':True,'cloud_calls':0,'business_actions_submitted':0,'new_training':False}))
        finally:
            response=client.delete(f'/ai-operator/brain/sessions/{chat["id"]}/memory');assert response.is_success,'Private smoke memory cleanup failed'
            response=client.delete(f'/ai-operator/assistant/conversations/{chat["id"]}');assert response.is_success,'Private smoke conversation archive failed'


if __name__=='__main__':main()
