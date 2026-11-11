"""Synthetic live planning smoke. Never approves business actions."""
import json
import httpx
from uuid import uuid4
from app.core.config import settings
with httpx.Client(base_url='http://127.0.0.1:1534',timeout=150) as client:
    assert client.get('/health').is_success
    login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
    if not login.is_success:
        print(json.dumps({'login_status':login.status_code}));raise SystemExit(1)
    client.headers['Authorization']='Bearer '+login.json()['access_token']
    root='/api/v1/ai-operator'
    info=client.get(root+'/suite/intelligence');assert info.is_success
    print(json.dumps({'default_provider':info.json()['selected_provider'],'model':info.json()['model']}),flush=True)
    check=client.post(root+'/providers/gemini/test')
    print(json.dumps({'connectivity_http':check.status_code,'success':check.is_success}),flush=True)
    response=client.post(root+'/suite/commands',json={'request_key':str(uuid4()),'provider':'preferred','text':'Prepare two separate CRM task drafts with titles Phase1 synthetic contract check and Phase1 synthetic delivery check. No source reads or existing records are needed. Do not execute anything.','context':[]})
    assert response.is_success
    data=response.json()
    print(json.dumps({'planning_status':data['status'],'step_count':len((data.get('plan') or {}).get('steps',[])),'intelligence':data.get('result',{}).get('intelligence'),'failure':data.get('result',{}).get('planning_failure'),'receipts':len(data.get('receipts') or [])}),flush=True)
    if data['status']=='awaiting_approval':
        assert client.post(root+f'/suite/runs/{data["id"]}/cancel').is_success
        print(json.dumps({'synthetic_draft_cancelled':True}),flush=True)
    health=client.get(root+'/suite/intelligence').json()
    print(json.dumps({'health':[{'provider':p['provider'],'connectivity':p['connectivity']['status'],'planning':p['planning']['status'],'error_code':p['planning'].get('error_code')} for p in health['items']]}),flush=True)
