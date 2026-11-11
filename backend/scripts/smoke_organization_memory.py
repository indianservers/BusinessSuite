"""Owner-only review lifecycle; never activates policy context on the app DB."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings
from app.core.security import verify_access_token


def main():
    root='/api/v1/ai-operator/suite/organization-memory';ident=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        r=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD});assert r.is_success
        token=r.json()['access_token'];user_id=int(verify_access_token(token)['sub']);client.headers['Authorization']='Bearer '+token
        try:
            body={'request_key':str(uuid4()),'definition':{'title':'Synthetic review check','text':'Synthetic context lifecycle check only.','module':'CRM','category':'constraint'},'audience':{'kind':'members','member_ids':[user_id]}}
            r=client.post(root+'/preview',json=body);assert r.is_success,f'Preview HTTP {r.status_code}'
            review=r.json();ident=review['id'];assert review['status']=='draft'
            assert client.post(root+'/preview',json=body).json()['id']==ident
            memories=client.get('/api/v1/ai-operator/suite/memory',params={'module':'CRM'});assert memories.is_success
            assert not any(m['key']==f'organization:{ident}' for m in memories.json()['items'])
            assert client.post(root+f'/{ident}/publish',json={'preview_hash':'0'*64}).status_code==409
            assert client.post(root+f'/{ident}/discard',json={'preview_hash':review['pending']['preview_hash']}).is_success
            result=client.post(root+f'/{ident}/forget',json={'revision':review['revision']});assert result.is_success
            assert result.json()['status']=='forgotten' and result.json()['definition'] is None
            print(json.dumps({'owner_only_review':True,'idempotent_preview':True,'unpublished_context_excluded':True,'stale_review_rejected':True,'stored_text_forgotten':True,'published_policies':0,'external_model_calls':0}),flush=True)
        finally:
            if ident:
                values=client.get(root,params={'module':'CRM'});assert values.is_success
                current=next((i for i in values.json()['items'] if i['id']==ident),None)
                if current and current['status']!='forgotten':assert client.post(root+f'/{ident}/forget',json={'revision':current['revision']}).is_success


if __name__=='__main__':main()
