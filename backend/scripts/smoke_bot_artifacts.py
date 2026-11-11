"""Live synthetic artifact test. Saves private artifacts only; cleans up afterwards."""
import json,time
from uuid import uuid4
from io import BytesIO
import httpx
from app.core.config import settings
with httpx.Client(base_url='http://127.0.0.1:1534',timeout=150) as c:
    for startup in range(20):
        try:
            if c.get('/health',timeout=3).is_success:break
        except httpx.RequestError:pass
        time.sleep(1)
    login=c.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
    assert login.is_success,'Login failed'
    c.headers['Authorization']='Bearer '+login.json()['access_token']
    root='/api/v1/ai-operator/suite';ids=[]
    def prepare(text,provider='local',module=None):
        r=c.post(root+'/commands',json={'request_key':str(uuid4()),'provider':provider,'module':module,'text':text,'context':[]})
        assert r.is_success,f'Planning HTTP {r.status_code}'
        run=r.json();print(json.dumps({'planning_status':run['status'],'provider':provider,'tools':[s['tool'] for s in (run.get('plan') or {}).get('steps',[])]}),flush=True)
        assert run['status']=='awaiting_approval',str({'error_code':run.get('error_code'),'artifact_repair':run.get('result',{}).get('artifact_repair')})
        steps=run['plan']['steps']
        assert len(steps)==1 and steps[0]['tool'] in {'crm.create_artifact','crm.edit_artifact','pms.create_artifact','hrms.create_artifact'}, 'Refusing non-artifact actions in the synthetic smoke test'
        return run
    def execute(run):
        r=c.post(root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']});assert r.is_success
        for _ in range(30):
            current=c.get(root+f'/runs/{run["id"]}').json()
            if current['status']=='succeeded':return current
            if current['status'] not in ('queued','executing'):raise AssertionError('Artifact execution '+current['status']+' '+str(current.get('error_code')))
            time.sleep(1)
        raise AssertionError('Artifact worker deadline')
    try:
        run=prepare('Create a private CRM document artifact titled Phase3 synthetic delivery brief. Use crm.create_artifact. Content: Synthetic goals and review steps only. Do not read records, create business tasks or send anything.','gemini')
        result=execute(run);ident=result['receipts'][0]['artifact_id'];ids.append(ident)
        original=c.get(root+f'/artifacts/{ident}').json();assert original['revision']==1
        edited=prepare(f'Edit artifact #{ident}: append the exact sentence Synthetic QA review is required. Preserve all existing content exactly. Use crm.edit_artifact with the current revision; no business record reads are required.','gemini')
        result2=execute(edited)
        latest=c.get(root+f'/artifacts/{ident}').json();assert latest['revision']==2
        assert original['content'] in latest['content'] and 'Synthetic QA review is required.' in latest['content']
        old=c.get(root+f'/artifacts/{ident}',params={'revision':1}).json();assert old['content']==original['content']
        word=c.get(root+f'/artifacts/{ident}/download',params={'format':'docx'});assert word.is_success
        from docx import Document
        assert 'Synthetic QA review is required.' in '\n'.join(p.text for p in Document(BytesIO(word.content)).paragraphs)
        print(json.dumps({'live_artifact_versions':2,'word_export':word.status_code,'historical_content_preserved':True}),flush=True)
        for module in ('PMS','HRMS'):
            r=execute(prepare('Create checklist called Phase3 synthetic QA checklist',module=module));ids.append(r['receipts'][0]['artifact_id'])
            print(json.dumps({'module':module,'private_checklist_saved':True}),flush=True)
    finally:
        for ident in ids:
            removed=c.delete(root+f'/artifacts/{ident}');assert removed.is_success,'Synthetic artifact cleanup failed'
        print(json.dumps({'synthetic_artifacts_archived':len(ids)}),flush=True)
