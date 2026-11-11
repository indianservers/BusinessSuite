"""Real Gemini concurrency + dependency citations, using synthetic answers only.

Run with the standalone suite worker stopped for a controlled measurement. Each
canonical ASGI request uses the production DB/session dependencies. Only this
explicitly created workflow is dispatched; no other scheduled work is processed.
"""
import asyncio,time,json
from contextvars import ContextVar
from uuid import uuid4
import httpx
from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.ai_operator import suite,providers,agent_workflows


async def main():
    root='/api/v1/ai-operator/suite';agents=[];flow=None;children=[];spans=[]
    current=ContextVar('synthetic_parallel_run',default=None)
    original_generate=suite.generate_json;original_request=providers.request_json
    def generate(*args,**kwargs):
        token=current.set(kwargs.get('suite_run_id'))
        try:return original_generate(*args,**kwargs)
        finally:current.reset(token)
    def request(*args,**kwargs):
        start=time.monotonic()
        try:return original_request(*args,**kwargs)
        finally:spans.append({'run_id':current.get(),'start':start,'end':time.monotonic()})
    suite.generate_json=generate;providers.request_json=request
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://synthetic-parallel',timeout=150) as client:
        login=await client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+login.json()['access_token']
        try:
            for name in ('Synthetic Parallel A','Synthetic Parallel B','Synthetic Dependency Reporter'):
                r=await client.post(root+'/agents',json={'name':name,'instructions':'For this synthetic test return only the requested synthetic answer. Do not inspect business records, request additional context, prepare actions or send anything. Cite dependency answer IDs when they are supplied.','modules':['CRM'],'tools':['crm.search_knowledge'],'provider':'gemini'})
                assert r.is_success;agents.append(r.json()['id'])
            r=await client.post(root+'/agents/workflows/preview',json={'request_key':str(uuid4()),'name':'Synthetic Gemini parallel handoff test','parallel_limit':2,'nodes':[
                {'agent_id':agents[0],'instructions':'Answer with Synthetic marker A. Return steps=[], context_requests=[], source_ids=[]. No tools or actions.'},
                {'agent_id':agents[1],'instructions':'Answer with Synthetic marker B. Return steps=[], context_requests=[], source_ids=[]. No tools or actions.'},
                {'agent_id':agents[2],'instructions':'Summarize both dependency answers, retaining synthetic markers A and B. Cite both dependency agent_answer source IDs. Return steps=[] and no additional context requests.','depends_on':[1,2]}]})
            assert r.is_success;flow=r.json()['id'];hashed=r.json()['preview_hash']
            assert (await client.post(root+f'/agents/workflows/{flow}/start',json={'preview_hash':hashed})).is_success
            for _ in range(3):
                with SessionLocal() as db:await agent_workflows.dispatch(db,app,workflow_id=flow)
                r=await client.get(root+f'/agents/workflows/{flow}');assert r.is_success
                state=r.json();children=[n['conversation_id'] for n in state['nodes'] if n.get('conversation_id')]
                assert state['status'] not in ('blocked','paused'),f'Workflow {state["status"]} {state.get("error")}'
            assert state['status']=='succeeded'
            root_ids={n['run_id'] for n in state['nodes'][:2]}
            network=[s for s in spans if s['run_id'] in root_ids]
            overlap=max((min(a['end'],b['end'])-max(a['start'],b['start']) for a in network for b in network if a['run_id']!=b['run_id']),default=0)
            assert overlap>0,'Gemini network calls did not overlap'
            r=await client.get(root+f'/runs/{state["nodes"][2]["run_id"]}');assert r.is_success
            report=r.json();assert report['status']=='answered' and len(report['result']['handoffs'])==2
            assert len([s for s in report['result']['citations'] if s.get('kind')=='agent_answer'])==2
            assert not report['plan']['steps'] and not report['receipts']
            combined=await client.get(root+f'/agents/workflows/{flow}/results');assert combined.is_success and combined.json()['complete']
            print(json.dumps({'gemini_root_network_calls':len(network),'overlap_seconds':round(overlap,3),'cited_dependency_answers':2,'combined_complete':True,'business_actions':0}),flush=True)
        finally:
            suite.generate_json=original_generate;providers.request_json=original_request
            if flow:assert (await client.post(root+f'/agents/workflows/{flow}/stop')).is_success
            for ident in children:assert (await client.delete(root+f'/conversations/{ident}')).is_success
            for ident in agents:assert (await client.delete(root+f'/agents/{ident}')).is_success


if __name__=='__main__':asyncio.run(main())
