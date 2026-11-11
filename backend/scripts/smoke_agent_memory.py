"""Synthetic server-memory smoke. No business actions are approved."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings
with httpx.Client(base_url='http://127.0.0.1:1534',timeout=150) as c:
    login=c.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
    assert login.is_success,'Login failed'
    c.headers['Authorization']='Bearer '+login.json()['access_token']
    root='/api/v1/ai-operator/suite'
    text='For synthetic Phase2 QA task drafts, use High priority unless my current request says otherwise.'
    made=c.post(root+'/memory',json={'level':'user','text':text})
    assert made.is_success,'Memory creation failed'
    memory=made.json(); ident=memory['id']
    try:
        recall=c.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','text':'What do you remember?'})
        assert recall.is_success
        result=recall.json()
        assert text in result['plan']['summary']
        print(json.dumps({'local_recall':result['status'],'memory_reference_visible':any(m['key']==memory['key'] for m in result['result']['memory_used'])}),flush=True)
        response=c.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'gemini','text':'Draft one CRM task titled Synthetic Phase2 QA review. Use my saved preferences. No existing source records or IDs are required; do not read records or execute actions.','context':[]})
        assert response.is_success
        run=response.json()
        steps=(run.get('plan') or {}).get('steps',[])
        print(json.dumps({'gemini_status':run['status'],'memory_reference_visible':any(m['key']==memory['key'] for m in run.get('result',{}).get('memory_used',[])),'draft_priority':steps[0]['payload'].get('priority') if steps else None,'receipts':len(run.get('receipts') or [])}),flush=True)
        if run['status']=='awaiting_approval':assert c.post(root+f'/runs/{run["id"]}/cancel').is_success
        changed=c.put(root+f'/memory/module/{ident}',json={'level':'user','text':'Synthetic Phase2 updated preference','revision':1})
        assert changed.is_success
        assert changed.json()['revision']==2
        print(json.dumps({'server_edit':True}),flush=True)
    finally:
        forgotten=c.delete(root+f'/memory/module/{ident}')
        assert forgotten.is_success,'Synthetic memory cleanup failed'
        assert not any(m['id']==ident and m['key'].startswith('module:') for m in c.get(root+'/memory').json()['items'])
        print(json.dumps({'synthetic_memory_forgotten':True}),flush=True)
