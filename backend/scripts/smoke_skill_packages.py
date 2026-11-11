"""Owner-private portable skill round trip, without model or business execution."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite/agents/catalog';ident=None
    package={'format':'businesssuite-agent-skill-v1','name':'Synthetic portable procedure','instructions':'Read authorized CRM task samples only.','tools':['crm.tasks']}
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            body={'request_key':str(uuid4()),'package':package}
            response=client.post(root+'/skill-imports/preview',json=body);assert response.is_success
            review=response.json();assert review['skill_id'] is None
            assert client.post(root+'/skill-imports/preview',json=body).json()['id']==review['id']
            path=root+f'/skill-imports/{review["id"]}/confirm'
            assert client.post(path,json={'preview_hash':'0'*64}).status_code==409
            response=client.post(path,json={'preview_hash':review['preview_hash']});assert response.is_success
            ident=response.json()['skill']['id']
            assert client.post(path,json={'preview_hash':review['preview_hash']}).json()['skill']['id']==ident
            assert client.get(root+f'/skills/{ident}/export').json()==package
            assert client.get(root+f'/skills/{ident}/versions').json()['items'][0]['revision']==1
            print(json.dumps({'server_validated_import':True,'exact_review':True,'idempotent_confirmation':True,'portable_export_verified':True,'business_actions':0,'external_model_calls':0}),flush=True)
        finally:
            if ident:assert client.delete(root+f'/skills/{ident}').is_success


if __name__=='__main__':main()
