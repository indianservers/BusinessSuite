"""Private synthetic grounded questions; optional one live Gemini answer."""
import argparse
import json
import re
import time
from uuid import uuid4
import httpx
from app.core.config import settings


def main(gemini=False):
    root='/api/v1/ai-operator/suite';runs=[];artifacts=set();chats=[];cloud=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=150) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed';client.headers['Authorization']='Bearer '+login.json()['access_token']
        def chat(title):
            r=client.post(root+'/conversations',json={'title':title});assert r.is_success
            ident=r.json()['id'];chats.append(ident);return ident
        def say(module,text,conversation,provider='local'):
            r=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':provider,'module':module,'conversation_id':conversation,'text':text})
            assert r.is_success,r.status_code
            value=r.json();runs.append(value['id']);return value
        def execute(run):
            assert run['status']=='awaiting_approval',run['status']
            assert all(s['tool'].endswith(('.create_artifact','.edit_artifact')) for s in run['plan']['steps'])
            r=client.post(root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']});assert r.is_success,r.status_code
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                r=client.get(root+f'/runs/{run["id"]}');assert r.is_success;value=r.json()
                if value['status'] in ('succeeded','failed','paused','cancelled','needs_reconciliation'):break
                time.sleep(1)
            else:raise AssertionError('Existing artifact run observation window exceeded')
            assert value['status']=='succeeded',value.get('error_code')
            for receipt in value['receipts']:artifacts.add(receipt['artifact_id'])
            return value['receipts'][0]['artifact_id']
        try:
            source_chat=chat('Synthetic pinned HRMS chart')
            say('HRMS','Create bar chart called Synthetic regional amounts with columns Region, Amount, Currency',source_chat)
            say('HRMS','Add row: North, 100, USD',source_chat);say('HRMS','Add row: South, 200, USD',source_chat)
            table=execute(say('HRMS','Add row: North, 50, INR',source_chat))
            dashboard_chat=chat('Synthetic grounded dashboard questions')
            dashboard=execute(say('CRM',f'Create dashboard called Synthetic delivery centre: artifact #{table} v1 as chart',dashboard_chat))
            first=say('CRM',f'Analyze dashboard #{dashboard}',dashboard_chat)
            assert first['status']=='answered' and 'sum 300' in first['plan']['summary']
            assert first['result']['citations'][0]['id']==f'artifact:{table}:v1'
            execute(say('HRMS',f'Edit artifact #{table}: Add row: North, 900, USD',source_chat))
            edit_chat=chat('Synthetic independent dashboard edit')
            execute(say('CRM',f'Edit artifact #{dashboard}: Refresh panel 1 to v2',edit_chat))
            assert client.post(root+f'/conversations/{dashboard_chat}/resume').is_success
            filtered=say('CRM','Only North',dashboard_chat)
            assert filtered['status']=='answered' and 'sum 100' in filtered['plan']['summary']
            assert filtered['result']['dashboard_query']['dashboard_revision']==1
            cleared=say('CRM','Clear the filter',dashboard_chat)
            assert cleared['status']=='answered' and 'sum 300' in cleared['plan']['summary']
            latest=say('CRM',f'Analyze panel 1 of dashboard #{dashboard}',dashboard_chat)
            assert latest['status']=='answered' and 'sum 1200' in latest['plan']['summary']
            assert latest['result']['citations'][0]['id']==f'artifact:{table}:v2'
            assert latest['approval_id'] is None and not latest['receipts']
            if gemini:
                cloud=say('CRM',f'Analyze panel 1 of dashboard #{dashboard}',chat('Synthetic Gemini pinned answer'),'gemini')
                assert cloud['status']=='answered',{'status':cloud['status'],'error_code':cloud.get('error_code')}
                assert cloud['result']['intelligence']['engine']=='provider'
                assert any(s['id']==f'artifact:{table}:v2' for s in cloud['result']['citations'])
                assert '1200' in re.sub(r'[,\s]','',cloud['plan']['summary'])
                assert not cloud['receipts'] and cloud['approval_id'] is None
            assert client.delete(root+f'/artifacts/{table}').is_success
            missing=say('CRM','Only North',dashboard_chat)
            assert missing['status']=='failed' and not missing['receipts'] and 'sum 1200' not in str(missing.get('plan'))
        finally:
            for ident in runs:
                r=client.get(root+f'/runs/{ident}');assert r.is_success;value=r.json()
                for receipt in value.get('receipts',[]):
                    if receipt.get('artifact_id'):artifacts.add(receipt['artifact_id'])
                if value['status'] in ('needs_clarification','awaiting_approval','queued','executing','waiting_pms','paused'):
                    assert client.post(root+f'/runs/{ident}/cancel').is_success
            for ident in artifacts:
                r=client.get(root+f'/artifacts/{ident}')
                if r.is_success:assert client.delete(root+f'/artifacts/{ident}').is_success
                assert client.get(root+f'/artifacts/{ident}').status_code==404
            for ident in chats:
                assert client.delete(root+f'/conversations/{ident}').is_success
                assert client.get(root+f'/conversations/{ident}').status_code==404
        print(json.dumps({'pinned_cited_answers':True,'server_currency_totals':True,'persistent_filter_followups':True,
            'dashboard_and_source_versions_retained':True,'explicit_reread_uses_current_dashboard_pin':True,'missing_source_not_reused':True,
            'gemini_answer_verified':bool(cloud),'gemini_intelligence':cloud['result']['intelligence'] if cloud else None,
            'cleanup_verified':True,'external_model_commands':1 if gemini else 0,'non_artifact_business_writes':0}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--gemini',action='store_true');args=parser.parse_args();main(args.gemini)
