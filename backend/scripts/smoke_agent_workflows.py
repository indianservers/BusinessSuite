"""Live orchestration smoke: reviewed synthetic private artifacts only."""
import json,time
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+login.json()['access_token']
        root='/api/v1/ai-operator/suite';agents=[];artifacts=[];flow_id=None
        def get_flow():
            r=client.get(root+f'/agents/workflows/{flow_id}');assert r.is_success,f'Workflow HTTP {r.status_code}';return r.json()
        def wait_step(index):
            deadline=time.monotonic()+50
            while time.monotonic()<deadline:
                flow=get_flow();assert flow['status'] not in ('blocked','paused','cancelled'),flow.get('error')
                if flow['nodes'][index].get('run_id'):return flow['nodes'][index]['run_id']
                time.sleep(.5)
            raise AssertionError('Agent preparation deadline exceeded')
        def execute_artifact(run_id,expected):
            run=client.get(root+f'/runs/{run_id}').json()
            assert run['status']=='awaiting_approval' and not run.get('receipts')
            assert [s['tool'] for s in run['plan']['steps']]==[expected],'Refusing non-artifact action'
            assert client.post(root+f'/runs/{run_id}/approve',json={'plan_hash':run['plan_hash']}).is_success
            deadline=time.monotonic()+50
            while time.monotonic()<deadline:
                done=client.get(root+f'/runs/{run_id}').json()
                if done['status']=='succeeded':return done
                assert done['status'] not in ('failed','paused','needs_reconciliation'),done.get('error_code')
                time.sleep(.5)
            raise AssertionError('Artifact execution deadline exceeded')
        try:
            for name,tools in [('Synthetic workflow writer',['crm.create_artifact']),('Synthetic workflow reviewer',['crm.artifact','crm.edit_artifact'])]:
                r=client.post(root+'/agents',json={'name':name,'instructions':'Prepare only the requested synthetic private artifact changes for separate review.','modules':['CRM'],'tools':tools,'provider':'local'})
                assert r.is_success,f'Agent HTTP {r.status_code}';agents.append(r.json()['id'])
            r=client.post(root+'/agents/workflows/preview',json={'request_key':str(uuid4()),'name':'Synthetic agent artifact handoff','nodes':[
                {'agent_id':agents[0],'instructions':'Create document called Synthetic agent handoff: Synthetic delivery review.'},
                {'agent_id':agents[1],'instructions':'Edit artifact #{{step.1.artifact_id}}: append: Synthetic second-agent review.','depends_on':[1]}]})
            assert r.is_success,f'Preview HTTP {r.status_code}';flow=r.json();flow_id=flow['id']
            assert client.post(root+f'/agents/workflows/{flow_id}/start',json={'preview_hash':flow['preview_hash']}).is_success
            first=wait_step(0);assert not get_flow()['nodes'][1].get('run_id')
            result=execute_artifact(first,'crm.create_artifact');ident=result['receipts'][0]['artifact_id'];artifacts.append(ident)
            second=wait_step(1);assert client.get(root+f'/artifacts/{ident}').json()['revision']==1
            execute_artifact(second,'crm.edit_artifact')
            latest=client.get(root+f'/artifacts/{ident}').json()
            assert latest['revision']==2 and 'Synthetic second-agent review.' in latest['content']
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if get_flow()['status']=='succeeded':break
                time.sleep(.5)
            assert get_flow()['status']=='succeeded'
            print(json.dumps({'live_multi_agent_workflow':True,'agents':2,'dependent_handoff':True,'reviewed_artifact_versions':2,'business_record_writes':0}),flush=True)
        finally:
            if flow_id:
                flow=get_flow()
                if flow['status']!='succeeded':client.post(root+f'/agents/workflows/{flow_id}/stop')
            for ident in artifacts:assert client.delete(root+f'/artifacts/{ident}').is_success
            for ident in agents:assert client.delete(root+f'/agents/{ident}').is_success


if __name__=='__main__':main()
