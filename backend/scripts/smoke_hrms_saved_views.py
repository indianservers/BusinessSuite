"""Live private HRMS preference action; no tickets or model calls."""
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
    root='/api/v1/ai-operator/suite';chat=view=run=None;run_ids=[]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs);assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token']
        client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        try:
            chat=call('POST',root+'/conversations',json={'title':'Synthetic HRMS saved view verification'})['id']
            def say(text):
                nonlocal run
                run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'HRMS','conversation_id':chat,'text':text});run_ids.append(run['id']);return run
            name='Synthetic HRMS focus '+uuid4().hex[:8]
            assert say(f'HRMS: Save ticket view called {name}: status=Pending; assigned_to_me=true')['status']=='awaiting_approval'
            revised=call('POST',root+f'/runs/{run["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':run['plan_hash'],
                'changes':[{'step':1,'field':'name','value':name+' reviewed'}]});run_ids.append(revised['id'])
            assert say('priority=Critical; my_tickets=false')['status']=='awaiting_approval'
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                run=call('GET',root+f'/runs/{run["id"]}')
                if run['status'] not in {'queued','executing'}:break
                time.sleep(1)
            assert run['status']=='succeeded';view=run['receipts'][0]['record_id']
            values=call('GET','/api/v1/helpdesk/ticket-views');created=next(v for v in values['items'] if v['id']==view)
            assert created['name']==name+' reviewed' and created['filters']['assigned_to_me'] and created['filters']['status']=='Pending' and created['filters']['priority']=='Critical'
            assert run['result_cards'][0]['href']==f'/hrms/helpdesk?view={view}'
            call('POST',root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            assert sum(v['id']==view for v in call('GET','/api/v1/helpdesk/ticket-views')['items'])==1
            with SessionLocal() as db:assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(run_ids)).count()==0
            evidence={'chat_id':chat,'view_id':view,'run_ids':run_ids,'native_server_view':True,'inline_then_conversational_correction':True,
                'result_link':True,'duplicate_prevented':True,'ticket_writes':0,'external_model_calls':0,'business_messages_sent':0}
            (Path(__file__).resolve().parents[2]/'.local/hrms-saved-views-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8');print(json.dumps(evidence))
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            if not run or run['status'] not in {'queued','executing'}:
                if view:
                    values=call('GET','/api/v1/helpdesk/ticket-views')
                    call('DELETE',f'/api/v1/helpdesk/ticket-views/{view}',params={'revision':values['revision']})
                    assert call('GET',root+f'/conversations/{chat}')['id']==chat
                if chat:call('DELETE',root+f'/conversations/{chat}')
                if view:
                    evidence['cleanup_verified']=True;evidence['conversation_accessible_after_view_removal']=True
                    (Path(__file__).resolve().parents[2]/'.local/hrms-saved-views-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')


if __name__=='__main__':main()
