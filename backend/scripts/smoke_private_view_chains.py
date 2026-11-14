"""Live reviewed private view chains/removal; synthetic metadata only."""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.ai_operator.models import OperatorApiLog


def main():
    root='/api/v1/ai-operator/suite';entries=[];run_ids=[];checks=[]
    evidence={'modules':checks,'task_or_ticket_writes':0,'business_messages_sent':0,'external_model_calls':0}
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token'];client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        try:
            for module,path in [('CRM','/api/v1/crm/task-views'),('HRMS','/api/v1/helpdesk/ticket-views')]:
                name='Synthetic view chain '+uuid4().hex[:8]
                created=call('POST',path,json={'name':name,'filters':{'priority':'High'}})
                view=next(v for v in created['items'] if v['name']==name)
                entry={'path':path,'view_id':view['id'],'chat_id':None,'run':None};entries.append(entry)
                ident=call('POST',root+'/conversations',json={'title':'Synthetic '+module+' view change QA'})['id'];entry['chat_id']=ident
                def say(text):
                    value=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':module,'conversation_id':ident,'text':text})
                    run_ids.append(value['id']);entry['run']=value;return value
                def execute(value):
                    call('POST',root+f'/runs/{value["id"]}/approve',json={'plan_hash':value['plan_hash']})
                    deadline=time.monotonic()+60
                    while time.monotonic()<deadline:
                        value=call('GET',root+f'/runs/{value["id"]}');entry['run']=value
                        if value['status'] not in {'queued','executing'}:break
                        time.sleep(1)
                    assert value['status']=='succeeded',value.get('error_code')
                    return value
                draft=say(f'Update saved view called {name}: priority=Low then rename that view to {name} final')
                assert draft['status']=='awaiting_approval' and len(draft['plan']['steps'])==2
                assert draft['result']['view_changes']['1']['changes']==[{'field':'priority','before':'High','after':'Low'}]
                revised=call('POST',root+f'/runs/{draft["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],'changes':[{'step':2,'field':'name','value':name+' reviewed'}]});run_ids.append(revised['id'])
                final=say('step=1; priority=Medium');assert final['status']=='awaiting_approval'
                done=execute(final)
                assert [receipt['view_revision'] for receipt in done['receipts']]==[created['revision']+1,created['revision']+2]
                assert all(step['payload']['filters']['priority']=='Medium' for step in final['plan']['steps'])
                current=call('GET',path);updated=next(v for v in current['items'] if v['id']==view['id'])
                assert updated['name']==name+' reviewed' and updated['filters']['priority']=='Medium'
                call('POST',root+f'/runs/{done["id"]}/approve',json={'plan_hash':done['plan_hash']})
                assert call('GET',path)['revision']==current['revision']
                removal=say('Remove that view');assert removal['status']=='awaiting_approval'
                removed=execute(removal)
                assert all(v['id']!=view['id'] for v in call('GET',path)['items'])
                assert '?view=' not in removed['result_cards'][0]['href']
                assert call('GET',root+f'/conversations/{ident}')['id']==ident
                checks.append({'module':module,'view_id':view['id'],'chat_id':ident,'before_after':True,'inline_then_followup':True,'reviewed_update':True,'chained_steps':2,'sequential_revision_receipts':True,'indexed_followup':True,'repeat_approval_no_mutation':True,'reviewed_remove':True,'history_preserved':True})
            with SessionLocal() as db:assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(run_ids)).count()==0
        finally:
            for entry in entries:
                run=entry['run']
                if run and run['status'] in {'awaiting_approval','needs_clarification'}:call('POST',root+f'/runs/{run["id"]}/cancel')
                assert not run or run['status'] not in {'queued','executing'},'Live synthetic action still running; retain its chat'
                current=call('GET',entry['path'])
                if any(v['id']==entry['view_id'] for v in current['items']):call('DELETE',entry['path']+'/'+entry['view_id'],params={'revision':current['revision']})
                if entry['chat_id']:call('DELETE',root+f'/conversations/{entry["chat_id"]}')
        evidence.update(run_ids=run_ids,cleanup_verified=True)
        (Path(__file__).resolve().parents[2]/'.local/private-view-chains-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print(json.dumps(evidence))


if __name__=='__main__':main()
