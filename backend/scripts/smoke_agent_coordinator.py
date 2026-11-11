"""Live synthetic coordinator design and read-only workflow; no business writes."""
import json,time
from uuid import uuid4
import httpx
from app.core.config import settings


def main(local_only=False):
    root='/api/v1/ai-operator/suite';agents=[];designs=[];flows=[];children=[]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=120) as client:
        r=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert r.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+r.json()['access_token']
        try:
            for name,module,tool in [('Synthetic CRM Reader','CRM','crm.tasks'),('Synthetic Project Reader','PMS','pms.projects')]:
                r=client.post(root+'/agents',json={'name':name,'instructions':'Read authorized source snapshots only. Do not prepare mutations. State bounded coverage.','modules':[module],'tools':[tool],'provider':'local'})
                assert r.is_success;agents.append(r.json()['id'])
            for provider,text in [('gemini','Use only Synthetic CRM Reader and Synthetic Project Reader for two independent read-only reviews. The exact first instructions must be Show CRM tasks. The exact second instructions must be List PMS projects. No changes, schedules, connectors or outgoing messages.'),('local','Synthetic CRM Reader: Show CRM tasks; Synthetic Project Reader: List PMS projects')]:
                if local_only and provider!='local':continue
                r=client.post(root+'/agents/coordinator/messages',json={'request_key':str(uuid4()),'provider':provider,'text':text})
                assert r.is_success,f'{provider} coordinator HTTP {r.status_code}'
                draft=r.json();designs.append(draft['context_id'])
                assert not draft['draft']['question'] and len(draft['draft']['nodes'])==2
                assert {n['agent_id'] for n in draft['draft']['nodes']}==set(agents)
                assert all(not n['depends_on'] for n in draft['draft']['nodes'])
                r=client.post(root+f'/agents/coordinator/{draft["context_id"]}/apply',json={'preview_hash':draft['preview_hash']})
                assert r.is_success;flow=r.json()['workflow_preview'];flows.append(flow['id']);assert flow['status']=='preview'
                if provider=='gemini':
                    assert client.post(root+f'/agents/workflows/{flow["id"]}/stop').is_success
                    print(json.dumps({'provider':'gemini','two_existing_agents_selected':True,'reviewed_preview_created':True,'started':False}),flush=True)
                    continue
                assert client.post(root+f'/agents/workflows/{flow["id"]}/start',json={'preview_hash':flow['preview_hash']}).is_success
                for _ in range(45):
                    r=client.get(root+f'/agents/workflows/{flow["id"]}');assert r.is_success
                    state=r.json();children=[n['conversation_id'] for n in state['nodes'] if n.get('conversation_id')]
                    if state['status']=='succeeded':break
                    assert state['status'] not in ('blocked','paused','cancelled'),f'Workflow {state["status"]}: {state.get("error")}'
                    time.sleep(1)
                result=client.get(root+f'/agents/workflows/{flow["id"]}/results');assert result.is_success
                combined=result.json();assert combined['complete'] and len(combined['items'])==2
                assert all(i['status']=='answered' and not i['receipts'] for i in combined['items'])
                print(json.dumps({'provider':'local','specialist_answers':2,'combined_results_verified':True,'business_actions':0}),flush=True)
        finally:
            for ident in flows:assert client.post(root+f'/agents/workflows/{ident}/stop').is_success
            for ident in children:assert client.delete(root+f'/conversations/{ident}').is_success
            for ident in designs:assert client.delete(root+f'/agents/coordinator/{ident}').is_success
            for ident in agents:assert client.delete(root+f'/agents/{ident}').is_success


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--local-only',action='store_true')
    main(local_only=parser.parse_args().local_only)
