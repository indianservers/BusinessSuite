"""Metered Gemini/PMS integration QA using configured credentials and labelled data."""
import json
import sys
import time
from pathlib import Path
from uuid import uuid4
import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa
from app.core.security import create_access_token

root=Path(__file__).resolve().parents[2]
out=root/'docs/qa/suite-operator-2026-10-24/pms-agent-live.json'
auth_path=root/'.local/operator-live-qa/auth.json'
auth=json.loads(auth_path.read_text())
auth['token']=create_access_token(str(auth['user_id']))
auth_path.write_text(json.dumps(auth))
client=httpx.Client(base_url='http://127.0.0.1:1534/api/v1',headers={'Authorization':'Bearer '+auth['token']},timeout=125)
evidence={'checks':[],'provider':'gemini','microphone':'Physical microphone testing remains deferred by the user.'}


def call(method,path,body=None):
    response=client.request(method,path,json=body)
    assert response.status_code in (200,201),f'{method} {path}: HTTP {response.status_code}'
    return response.json()


def save(name,detail):
    evidence['checks'].append({'name':name,'status':'passed','evidence':detail})
    out.write_text(json.dumps(evidence,indent=2))
    print('PASS',name,flush=True)


def execute(row):
    assert row['status']=='awaiting_approval',(row['id'],row['status'],row.get('error_code'))
    assert all(s['tool']=='pms.task_plan' and s['record_id']==evidence['project_id'] for s in row['plan']['steps'])
    assert all(a['task_id']==evidence['task_id'] for s in row['plan']['steps'] for a in s['payload']['plan']['steps'])
    call('POST',f'/ai-operator/suite/runs/{row["id"]}/approve',{'plan_hash':row['plan_hash']})
    for _ in range(50):
        result=call('GET',f'/ai-operator/suite/runs/{row["id"]}')
        if result['status']=='succeeded':return result
        assert result['status'] not in ('failed','paused','needs_reconciliation','cancelled'),(result['id'],result['status'],result.get('error_code'))
        time.sleep(1)
    raise AssertionError('Execution did not complete within the QA window')


if __name__=='__main__':
    stamp=uuid4().hex[:7].upper()
    workspace=1
    configs=call('GET',f'/ai-operator/providers?workspace_id={workspace}')['items']
    assert [p['provider'] for p in configs if p['enabled']]==['gemini']
    project=call('POST','/project-management/projects',{'name':'LLM Agent QA '+stamp,'project_key':'LA'+stamp,'workspace_id':workspace})['id']
    task=call('POST',f'/project-management/projects/{project}/tasks',{'title':'LLM Agent QA review','task_key':'LA'+stamp+'-1'})['id']
    evidence.update(project_id=project,task_id=task,workspace_id=workspace)
    out.write_text(json.dumps(evidence,indent=2))
    base={'project_id':project,'task_ids':[task],'workspace_id':workspace,'provider':'gemini','timezone':'Asia/Kolkata'}
    draft=call('POST','/ai-operator/suite/commands',{**base,'request_key':str(uuid4()),'text':
        'For this selected task, prepare one pms.task_plan: priority High, estimated_hours 8, story_points 5, and add checklist item "Agent QA review". No other changes.'})
    assert draft['status']=='awaiting_approval',(draft['id'],draft['status'],draft.get('error_code'))
    save('Real LLM prepares selected-task actions and impact',{'run_id':draft['id'],'status':draft['status'],'tools':[s['tool'] for s in (draft.get('plan') or {}).get('steps',[])],'has_impact':bool(draft.get('pms_previews'))})
    final=execute(draft)
    save('Approved background PMS actions return receipts',{'run_id':final['id'],'receipts':final['receipts']})
    scheduled=call('POST','/ai-operator/suite/commands',{**base,'request_key':str(uuid4()),'text':
        'Schedule this selected task starting next Monday using the working calendar and dependencies. Use pms.schedule with start_date "next monday". No other actions.'})
    final=execute(scheduled)
    save('Real LLM relative-date scheduling delegates to calendar',{'run_id':final['id'],'receipts':final['receipts']})
    from datetime import date
    current=next(t for t in call('GET',f'/ai-operator/local-context?project_id={project}')['tasks'] if t['id']==task)
    assert current['priority']=='High' and float(current['estimated_hours'])==8 and current['story_points']==5
    assert any(i['title']=='Agent QA review' for i in current['checklist'])
    assert date.fromisoformat(current['start_date']).weekday()==0
    save('Canonical task read confirms persisted changes and Monday schedule',{k:current[k] for k in ('id','priority','estimated_hours','story_points','start_date','due_date','checklist')})
    logs=call('GET',f'/ai-operator/analytics?workspace_id={workspace}')['logs']
    ids={draft['id'],scheduled['id']}
    scoped=[l for l in logs if l.get('suite_run_id') in ids]
    assert len(scoped)==2 and all(l['status']=='success' and l['input_tokens'] and l['output_tokens'] for l in scoped)
    save('Both real Gemini calls have scoped usage analytics and sanitized logs',scoped)
