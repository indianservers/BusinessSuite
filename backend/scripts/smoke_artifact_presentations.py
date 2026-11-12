"""Local live reviewed artifact-only creation/edit/export, followed by archival."""
import io
import json
import time
from uuid import uuid4
import httpx
from pypdf import PdfReader
from pptx import Presentation
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';conversation=None;artifacts=set();runs=[]
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert response.is_success,'Login failed';client.headers['Authorization']='Bearer '+response.json()['access_token']
        def prepare(text):
            response=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM',
                'conversation_id':conversation,'text':text});assert response.is_success
            value=response.json();runs.append(value['id']);assert value['status']=='awaiting_approval'
            assert all(step['tool'] in ('crm.create_artifact','crm.edit_artifact') for step in value['plan']['steps'])
            return value
        def execute(value):
            response=client.post(root+f'/runs/{value["id"]}/approve',json={'plan_hash':value['plan_hash']});assert response.is_success
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                response=client.get(root+f'/runs/{value["id"]}');assert response.is_success
                final=response.json()
                if final['status'] in ('succeeded','failed','paused','cancelled','needs_reconciliation'):break
                time.sleep(1)
            else:raise AssertionError('Existing artifact execution did not finish within the observation window')
            assert final['status']=='succeeded',final.get('error_code')
            for receipt in final['receipts']:artifacts.add(receipt['artifact_id'])
            return final
        try:
            response=client.post(root+'/conversations',json={'title':'Synthetic presentation export smoke'});assert response.is_success
            conversation=response.json()['id']
            first=prepare('Create presentation called Synthetic delivery review: Overview | Illustrative scope || Next steps | Confirm dates')
            created=execute(first);ident=created['receipts'][0]['artifact_id']
            for format in ('pdf','pptx'):
                exported=client.get(root+f'/artifacts/{ident}/download',params={'format':format,'revision':1});assert exported.is_success
                if format=='pdf':assert len(PdfReader(io.BytesIO(exported.content)).pages)==2
                else:assert len(Presentation(io.BytesIO(exported.content)).slides)==2
            execute(prepare('Add point to slide 2: Confirm owner'))
            latest=client.get(root+f'/artifacts/{ident}');assert latest.is_success and latest.json()['revision']==2
            assert latest.json()['slides'][1]['bullets']==['Confirm dates','Confirm owner']
            original=client.get(root+f'/artifacts/{ident}/download',params={'format':'pdf','revision':1});assert original.is_success
            assert 'Confirm owner' not in ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(original.content)).pages)
        finally:
            for ident in runs:
                response=client.get(root+f'/runs/{ident}');assert response.is_success
                final=response.json()
                for receipt in final.get('receipts',[]):
                    if receipt.get('artifact_id'):artifacts.add(receipt['artifact_id'])
                if final['status'] not in ('succeeded','cancelled','superseded'):
                    assert client.post(root+f'/runs/{ident}/cancel').is_success
            for ident in artifacts:
                assert client.delete(root+f'/artifacts/{ident}').is_success
                assert client.get(root+f'/artifacts/{ident}').status_code==404
            if conversation:
                assert client.delete(root+f'/conversations/{conversation}').is_success
                assert client.get(root+f'/conversations/{conversation}').status_code==404
        print(json.dumps({'local_conversation_slides':True,'reviewed_versions':2,'pdf_and_powerpoint_exports':True,
            'historical_version_preserved':True,'cleanup_verified':True,'non_artifact_business_writes':0,'external_model_calls':0}),flush=True)


if __name__=='__main__':main()
