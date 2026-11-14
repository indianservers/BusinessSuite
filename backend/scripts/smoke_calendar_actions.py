"""Live private native calendar QA. Existing sync accounts receive previews only."""
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.apps.project_management.models import PMSCalendarEvent
from app.ai_operator.models import OperatorApiLog


def main():
    root='/api/v1/ai-operator/suite';chat=run=event=None;runs=[]
    prefix='Synthetic calendar QA '+uuid4().hex[:10]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.is_success,f'{method} {path}: HTTP {response.status_code}'
            return None if response.status_code==204 else response.json()
        auth=call('POST','/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        client.headers['Authorization']='Bearer '+auth['access_token'];client.headers['X-Company-ID']=str(settings.LOGIN_COMPANY_ID)
        policy=call('GET',root+'/pms/calendar/policy')
        try:
            chat=call('POST',root+'/conversations',json={'title':prefix})['id']
            def say(text):
                nonlocal run
                run=call('POST',root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'PMS','conversation_id':chat,'text':text})
                runs.append(run['id']);return run
            def execute(value):
                nonlocal run
                call('POST',root+f'/runs/{value["id"]}/approve',json={'plan_hash':value['plan_hash']})
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    run=call('GET',root+f'/runs/{value["id"]}')
                    if run['status'] not in {'queued','executing'}:break
                    time.sleep(1)
                assert run['status']=='succeeded',run.get('error_code')
                return run
            assert say('PMS: Schedule meeting called '+prefix)['status']=='needs_clarification'
            draft=say('start=2035-12-03T10:00+05:30; end=2035-12-03T11:00+05:30')
            assert draft['status']=='awaiting_approval',draft.get('error_code')
            revised=call('POST',root+f'/runs/{draft["id"]}/revise',json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
                'changes':[{'step':1,'field':'title','value':prefix+' reviewed'}]});runs.append(revised['id']);run=revised
            final=say('Make it 30 minutes')
            assert final['status']=='awaiting_approval' and final['plan']['steps'][0]['payload']['title']==prefix+' reviewed'
            assert any(change['field']=='calendar_sync' for change in final['result']['calendar_changes']['1']['changes'])
            with SessionLocal() as db:assert db.query(PMSCalendarEvent).filter(PMSCalendarEvent.title.like(prefix+'%')).count()==0
            evidence={'chat_id':chat,'run_ids':runs,'reviewed_sync_effects':True,'inline_and_natural_followups':True,
                'preview_only_due_to_existing_sync':bool(policy['connections']),'business_messages_sent':0,'external_model_calls':0}
            if not policy['connections']:
                created=execute(final);event=created['receipts'][0]['record_id'];evidence['event_id']=event
                source=call('GET',root+'/pms/calendar/event',params={'event_id':event})
                assert source['revision']==1 and source['visibility']=='private' and source['start_at']=='2035-12-03T04:30:00+00:00'
                assert source['end_at']=='2035-12-03T05:00:00+00:00'
                assert created['result_cards'][0]['href'].startswith('/pms/calendar?date=2035-12-03&view=Week&q=')
                edit=say('Edit that event: description=Synthetic reviewed agenda')
                assert edit['status']=='awaiting_approval';edited=execute(edit)
                current=call('GET',root+'/pms/calendar/event',params={'event_id':event});assert current['revision']==2
                call('POST',root+f'/runs/{edited["id"]}/approve',json={'plan_hash':edited['plan_hash']})
                assert call('GET',root+'/pms/calendar/event',params={'event_id':event})['revision']==2
                listed=call('GET',root+'/pms/calendar/events',params={'start':'2035-12-03T00:00Z','end':'2035-12-04T00:00Z'})
                assert any(value['id']==event for value in listed['items'])
                slots=call('GET',root+'/pms/calendar/slots',params={'day':'2035-12-03','minutes':30,'timezone_name':'Asia/Kolkata'})
                assert 'Not a reservation' in slots['limitations']
                removal=say('Remove that event');assert removal['status']=='awaiting_approval';execute(removal)
                with SessionLocal() as db:assert db.get(PMSCalendarEvent,event) is None
                assert call('GET',root+f'/conversations/{chat}')['id']==chat
                evidence.update(reviewed_create_edit_remove=True,repeat_approval_no_mutation=True,history_preserved=True,native_reads_and_slots=True)
                event=None
            with SessionLocal() as db:assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count()==0
        finally:
            if run and run['status'] in {'needs_clarification','awaiting_approval'}:call('POST',root+f'/runs/{run["id"]}/cancel')
            assert not run or run['status'] not in {'queued','executing'},'Retain active calendar QA chat'
            if event:
                value=call('GET',root+'/pms/calendar/event',params={'event_id':event})
                assert value['title'].startswith(prefix) and value['visibility']=='private'
                call('DELETE',f'/api/v1/project-management/planner/events/{event}',params={'revision':value['revision']})
            if chat:call('DELETE',root+f'/conversations/{chat}')
    evidence['cleanup_complete']=True
    (Path(__file__).resolve().parents[2]/'.local/calendar-actions-live-result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__':main()
