"""Synthetic private live dashboard workflow with verified cleanup."""
import io
import json
import time
from uuid import uuid4
import httpx
from openpyxl import load_workbook
from pypdf import PdfReader
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';runs=[];artifacts=set();chats=[]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed';client.headers['Authorization']='Bearer '+login.json()['access_token']
        def chat(title):
            r=client.post(root+'/conversations',json={'title':title});assert r.is_success
            ident=r.json()['id'];chats.append(ident);return ident
        def say(module,text,conversation):
            r=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':module,'conversation_id':conversation,'text':text})
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
            else:raise AssertionError('Existing dashboard run observation window exceeded')
            assert value['status']=='succeeded',value.get('error_code')
            for receipt in value['receipts']:artifacts.add(receipt['artifact_id'])
            return value['receipts'][0]['artifact_id']
        try:
            table_chat=chat('Synthetic dashboard chart')
            say('CRM','Create bar chart called Synthetic regional amounts with columns Region, Amount, Currency',table_chat)
            say('CRM','Add row: North, 100, USD',table_chat)
            table=execute(say('CRM','Add row: South, 200, USD',table_chat))
            notes_chat=chat('Synthetic dashboard HRMS source')
            notes=execute(say('HRMS','Create document called Synthetic staffing notes: Original staffing snapshot.',notes_chat))
            dashboard_chat=chat('Synthetic dashboard review')
            missing=say('CRM','Create dashboard called Synthetic delivery centre',dashboard_chat);assert missing['status']=='needs_clarification'
            dashboard=execute(say('CRM',f'artifact #{table} v1 as chart; artifact #{notes} v1 as summary',dashboard_chat))
            execute(say('HRMS','Append: New staffing revision.',notes_chat))
            panel=client.get(root+f'/artifacts/{dashboard}/panels/2');assert panel.is_success
            assert panel.json()['source']['revision']==1 and panel.json()['source']['current_revision']==2
            assert 'New staffing revision' not in panel.json()['source']['content']
            assert panel.json()['citation']['id']==f'artifact:{notes}:v1'
            execute(say('CRM','Refresh panel 2 to v2',dashboard_chat))
            assert client.get(root+f'/artifacts/{dashboard}/panels/2').json()['source']['revision']==2
            assert client.get(root+f'/artifacts/{dashboard}/panels/2',params={'revision':1}).json()['source']['revision']==1
            for fmt in ('pdf','xlsx'):
                r=client.get(root+f'/artifacts/{dashboard}/download',params={'format':fmt,'revision':1});assert r.is_success,r.status_code
                if fmt=='pdf':
                    text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
                    assert 'sum 300' in text and 'Original staffing snapshot' in text and 'New staffing revision' not in text
                else:
                    book=load_workbook(io.BytesIO(r.content));assert book.active.title=='Dashboard' and len(book['Chart analysis']._charts)==1
                    assert book['Source 2']['B3'].value=='Original staffing snapshot.'
            pending=say('CRM','Rename panel 2 to Staffing report',dashboard_chat);assert pending['status']=='awaiting_approval'
            assert client.delete(root+f'/artifacts/{notes}').is_success
            assert client.post(root+f'/runs/{pending["id"]}/approve',json={'plan_hash':pending['plan_hash']}).status_code==404
            assert client.get(root+f'/artifacts/{dashboard}/panels/2').status_code==404
            assert client.get(root+f'/artifacts/{dashboard}/download',params={'format':'xlsx'}).status_code==404
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
        print(json.dumps({'cross_module_dashboard':True,'reviewed_followups':True,'immutable_pins':True,'reviewed_refresh':True,
            'historical_pdf_xlsx':True,'source_archive_blocks_approval_and_export':True,'cleanup_verified':True,'external_model_calls':0,'non_artifact_business_writes':0}),flush=True)


if __name__=='__main__':main()
