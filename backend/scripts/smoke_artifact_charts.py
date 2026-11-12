"""Private synthetic live chart conversation; no external calls or ERP writes."""
import io
import json
import time
from uuid import uuid4
import httpx
from openpyxl import load_workbook
from pypdf import PdfReader
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';runs=[];artifacts=set();chat=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+login.json()['access_token']
        def say(text):
            response=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':chat,'text':text})
            assert response.is_success,response.status_code
            run=response.json();runs.append(run['id']);return run
        def execute(run):
            assert run['status']=='awaiting_approval',run['status']
            assert all(s['tool'] in ('crm.create_artifact','crm.edit_artifact') for s in run['plan']['steps'])
            response=client.post(root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']})
            assert response.is_success,response.status_code
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                response=client.get(root+f'/runs/{run["id"]}');assert response.is_success
                current=response.json()
                if current['status'] in ('succeeded','failed','paused','cancelled','needs_reconciliation'):break
                time.sleep(1)
            else:raise AssertionError('Existing chart run observation window exceeded')
            assert current['status']=='succeeded',current.get('error_code')
            for receipt in current['receipts']:artifacts.add(receipt['artifact_id'])
            return current['receipts'][0]['artifact_id']
        try:
            response=client.post(root+'/conversations',json={'title':'Synthetic chart follow-ups'})
            assert response.is_success;chat=response.json()['id']
            first=say('Create bar chart called Synthetic regional amounts with columns Region, Amount, Currency')
            assert first['status']=='awaiting_approval'
            say('Add row: North, 100, USD')
            say('Add row: South, 200, USD')
            say('Add row: North, 50, INR')
            ident=execute(say('Add row: West, =1+1, USD'))
            answer=say('Analyze this table')
            assert answer['status']=='answered'
            assert answer['result']['citations'][0]['id']==f'artifact:{ident}:v1'
            response=client.get(root+f'/artifacts/{ident}/analysis');assert response.is_success
            analysis=response.json()
            assert {p['unit']:p['statistics']['sum'] for p in analysis['panels']}=={'USD':'300','INR':'50'}
            assert analysis['invalid_numeric_rows']==1
            filtered=client.get(root+f'/artifacts/{ident}/analysis',params={'category_query':'North'});assert filtered.is_success
            assert {p['unit']:p['statistics']['sum'] for p in filtered.json()['panels']}=={'USD':'100','INR':'50'}
            assert client.get(root+f'/artifacts/{ident}').json()['revision']==1
            execute(say('Change chart to line'))
            assert client.get(root+f'/artifacts/{ident}/analysis').json()['panels'][0]['kind']=='line'
            historical=client.get(root+f'/artifacts/{ident}/analysis',params={'revision':1})
            assert historical.is_success and historical.json()['panels'][0]['kind']=='bar'
            for fmt in ('pdf','xlsx'):
                exported=client.get(root+f'/artifacts/{ident}/download',params={'revision':1,'format':fmt});assert exported.is_success
                if fmt=='pdf':assert 'sum 300' in ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(exported.content)).pages)
                else:
                    book=load_workbook(io.BytesIO(exported.content));sheet=book['Chart analysis']
                    assert len(sheet._charts)==2 and len(sheet.row_breaks.brk)==2
                    assert book['Artifact']['B5'].value=='=1+1' and book['Artifact']['B5'].data_type=='s'
        finally:
            for run_id in runs:
                response=client.get(root+f'/runs/{run_id}');assert response.is_success
                current=response.json()
                for receipt in current.get('receipts',[]):
                    if receipt.get('artifact_id'):artifacts.add(receipt['artifact_id'])
                if current['status'] not in ('succeeded','answered','cancelled','superseded'):assert client.post(root+f'/runs/{run_id}/cancel').is_success
            for ident in artifacts:
                assert client.delete(root+f'/artifacts/{ident}').is_success
                assert client.get(root+f'/artifacts/{ident}').status_code==404
            if chat:
                assert client.delete(root+f'/conversations/{chat}').is_success
                assert client.get(root+f'/conversations/{chat}').status_code==404
        print(json.dumps({'reviewed_chart_followups':True,'cited_server_analysis':True,'separate_currencies':True,
            'read_only_filter':True,'historical_exports':True,'cleanup_verified':True,'external_model_calls':0,'non_artifact_business_writes':0}),flush=True)


if __name__=='__main__':main()
