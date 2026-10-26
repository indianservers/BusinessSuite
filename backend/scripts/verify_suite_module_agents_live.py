"""Opt-in metered QA: four module memories, approved execution and Gemini follow-up.

Uses the existing active session in .local/operator-live-qa/auth.json. No keys are
read or printed. Only labelled QA memories are written, then explicitly forgotten.
"""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx


def main():
    root=Path(__file__).resolve().parents[2]
    auth=json.loads((root/'.local/operator-live-qa/auth.json').read_text())
    out=root/'docs/qa/module-agents-2026-10-26'
    out.mkdir(parents=True,exist_ok=True)
    evidence={'checks':[],'provider':'gemini'}
    client=httpx.Client(base_url='http://127.0.0.1:1534/api/v1',headers={'Authorization':'Bearer '+auth['token']},timeout=120)
    def call(method,path,body=None):
        response=client.request(method,path,json=body)
        assert response.status_code in (200,201),f'{method} {path}: HTTP {response.status_code}'
        return response.json()
    def save(name,data):
        evidence['checks'].append({'name':name,'status':'passed','evidence':data})
        (out/'live-results.json').write_text(json.dumps(evidence,indent=2))
        print('PASS',name,flush=True)
    for _ in range(40):
        try:
            if client.get('/ai-operator/providers?workspace_id=1',timeout=2).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(1)
    providers=call('GET','/ai-operator/providers?workspace_id=1')['items']
    assert [p['provider'] for p in providers if p['enabled']]==['gemini']
    stamp=uuid4().hex[:7].upper()
    days={'HRMS':'Monday','CRM':'Tuesday','SRM':'Wednesday','FAM':'Thursday'}
    context=[{'tool':t} for t in ('hrms.leave_types','crm.tasks','srm.invoices','fam.cost_centers')]
    request={'request_key':str(uuid4()),'workspace_id':1,'module':'CRM','context':context,'provider':'gemini','text':
        f'Create exactly four private QA preference memories tagged {stamp}. '+
        ' '.join(f'For {m}, remember: "QA {stamp}: prefer {d} reviews".' for m,d in days.items())+
        ' Use each module remember tool once. These are private preferences, not organizational policy. No other actions.'}
    run=call('POST','/ai-operator/suite/commands',request)
    assert run['status']=='awaiting_approval',(run['id'],run['status'],run.get('error_code'))
    assert len(run['plan']['steps'])==4 and {s['tool'] for s in run['plan']['steps']}=={m.lower()+'.remember' for m in days}
    assert all(stamp in s['payload']['text'] for s in run['plan']['steps'])
    save('Real Gemini prepares four module memories without executing',{'run_id':run['id'],'tools':[s['tool'] for s in run['plan']['steps']]})
    call('POST',f'/ai-operator/suite/runs/{run["id"]}/approve',{'plan_hash':run['plan_hash']})
    for _ in range(40):
        final=call('GET',f'/ai-operator/suite/runs/{run["id"]}')
        if final['status']=='succeeded':break
        assert final['status'] not in ('paused','failed','needs_reconciliation'),(final['id'],final['status'])
        time.sleep(1)
    assert final['status']=='succeeded'
    save('Approved four-module execution returns canonical receipts',{'run_id':run['id'],'receipts':final['receipts']})
    memory_ids=[]
    try:
        for module in days:
            rows=call('GET',f'/ai-operator/suite/memories?workspace_id=1&module={module}')['items']
            matches=[r for r in rows if stamp in r['text']]
            assert len(matches)==1
            memory_ids.append(matches[0]['id'])
        answer=call('POST','/ai-operator/suite/commands',{'request_key':str(uuid4()),'workspace_id':1,'parent_run_id':run['id'],
            'mode':'summary','text':f'Using the saved QA {stamp} memories, list the review day for each of HRMS, CRM, SRM and FAM. No new actions.'})
        assert answer['status']=='answered' and not answer['plan']['steps'],(answer['id'],answer['status'])
        assert all(day.lower() in answer['plan']['summary'].lower() for day in days.values())
        assert answer['result']['request']['context']==final['result']['request']['context']
        save('Real Gemini follow-up recalls all four private module memories',{'run_id':answer['id'],'parent_run_id':run['id'],'summary':answer['plan']['summary']})
        logs=call('GET','/ai-operator/analytics?workspace_id=1')['logs']
        scoped=[l for l in logs if l.get('suite_run_id') in (run['id'],answer['id'])]
        assert len(scoped)==2 and all(l['status']=='success' and l['provider']=='gemini' and l['input_tokens'] for l in scoped)
        assert all(all(m in l['module'] for m in days) for l in scoped)
        save('Usage logs attribute both Gemini requests to all four modules',scoped)
    finally:
        for ident in memory_ids:call('DELETE',f'/ai-operator/suite/memories/{ident}')
    save('Only labelled QA memories were forgotten after verification',{'memory_ids':memory_ids})


if __name__=='__main__':main()
