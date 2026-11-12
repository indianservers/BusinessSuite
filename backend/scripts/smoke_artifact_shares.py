"""Live reviewed self-audience publication of synthetic content; no messages."""
import io
import json
import time
from uuid import uuid4
import httpx
from openpyxl import load_workbook
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';runs=[];artifacts=set();shares=set();chat=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed';client.headers['Authorization']='Bearer '+login.json()['access_token']
        me=client.get('/api/v1/auth/me');assert me.is_success;user_id=me.json()['id']
        def say(text):
            response=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':chat,'text':text})
            assert response.is_success,response.status_code
            value=response.json();runs.append(value['id']);return value
        def execute(run):
            assert run['status']=='awaiting_approval',run['status']
            assert all(s['tool'].endswith(('.create_artifact','.edit_artifact')) for s in run['plan']['steps'])
            response=client.post(root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']});assert response.is_success
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                response=client.get(root+f'/runs/{run["id"]}');assert response.is_success;value=response.json()
                if value['status'] in ('succeeded','failed','paused','cancelled','needs_reconciliation'):break
                time.sleep(1)
            else:raise AssertionError('Existing artifact execution observation window exceeded')
            assert value['status']=='succeeded',value.get('error_code')
            for receipt in value['receipts']:artifacts.add(receipt['artifact_id'])
            return value['receipts'][0]['artifact_id']
        def preview(ident,revision,previous=None):
            response=client.post(root+'/artifact-shares/preview',json={'request_key':str(uuid4()),'source_id':ident,'source_revision':revision,
                'audience':{'kind':'members','member_ids':[user_id]},'share_id':previous['id'] if previous else None,'revision':previous['revision'] if previous else None})
            assert response.is_success,response.status_code
            value=response.json();shares.add(value['id']);assert 'grant' not in value['pending'];return value
        def publish(draft):
            response=client.post(root+f'/artifact-shares/{draft["id"]}/publish',json={'preview_hash':draft['pending']['preview_hash']})
            assert response.is_success,response.status_code;return response.json()
        try:
            response=client.post(root+'/conversations',json={'title':'Synthetic artifact sharing review'});assert response.is_success;chat=response.json()['id']
            say('Create bar chart called Synthetic sharing amounts with columns Region, Amount, Currency')
            say('Add row: North, 100, USD');say('Add row: South, 200, USD');say('Add row: North, 50, INR')
            ident=execute(say('Add row: West, =1+1, USD'))
            draft=preview(ident,1)
            assert client.get(root+f'/artifact-shares/{draft["id"]}/content').status_code==404
            restored=client.get(root+f'/artifact-shares/source/{ident}');assert restored.is_success
            assert restored.json()['items'][0]['pending']['preview_hash']==draft['pending']['preview_hash']
            shared=publish(draft);assert publish(draft)['revision']==shared['revision']
            response=client.get(root+f'/artifact-shares/{shared["id"]}/content',params={'revision':1});assert response.is_success
            item=response.json()['item'];assert item['provenance']['citations']==[] and 'conversation_id' not in item and item['id']==f'share-{shared["id"]}'
            response=client.get(root+f'/artifact-shares/{shared["id"]}/analysis',params={'revision':1,'category_query':'North'});assert response.is_success
            assert {p['unit']:p['statistics']['sum'] for p in response.json()['panels']}=={'USD':'100','INR':'50'}
            response=client.get(root+f'/artifact-shares/{shared["id"]}/download',params={'revision':1,'format':'xlsx'});assert response.is_success
            book=load_workbook(io.BytesIO(response.content));assert len(book['Chart analysis']._charts)==2
            assert book['Artifact']['B5'].value=='=1+1' and book['Artifact']['B5'].data_type=='s'
            execute(say(f'Edit artifact #{ident}: Replace row 2: South, 250, USD'))
            unchanged=client.get(root+f'/artifact-shares/{shared["id"]}/analysis').json()
            assert unchanged['panels'][0]['statistics']['sum']=='300'
            next_review=preview(ident,2,shared)
            assert client.get(root+f'/artifact-shares/{shared["id"]}/analysis').json()['panels'][0]['statistics']['sum']=='300'
            updated=publish(next_review);assert updated['revision']==2
            assert client.get(root+f'/artifact-shares/{shared["id"]}/content',params={'revision':1}).status_code==409
            assert client.get(root+f'/artifact-shares/{shared["id"]}/analysis').json()['panels'][0]['statistics']['sum']=='350'
            revoked=client.post(root+f'/artifact-shares/{shared["id"]}/revoke',json={'revision':updated['revision']});assert revoked.is_success
            assert client.post(root+f'/artifact-shares/{shared["id"]}/revoke',json={'revision':updated['revision']}).json()['revision']==revoked.json()['revision']
            assert client.get(root+f'/artifact-shares/{shared["id"]}/download',params={'format':'pdf'}).status_code==404
            pending=preview(ident,2)
            assert client.delete(root+f'/artifacts/{ident}').is_success
            assert client.post(root+f'/artifact-shares/{pending["id"]}/publish',json={'preview_hash':pending['pending']['preview_hash']}).status_code==409
            assert client.get(root+f'/artifact-shares/{pending["id"]}/content').status_code==404
        finally:
            for run_id in runs:
                response=client.get(root+f'/runs/{run_id}');assert response.is_success;value=response.json()
                for receipt in value.get('receipts',[]):
                    if receipt.get('artifact_id'):artifacts.add(receipt['artifact_id'])
                if value['status'] in ('needs_clarification','awaiting_approval','queued','executing','waiting_pms','paused'):
                    assert client.post(root+f'/runs/{run_id}/cancel').is_success
            for ident in artifacts:
                current=client.get(root+f'/artifacts/{ident}')
                if current.is_success:
                    managed=client.get(root+f'/artifact-shares/source/{ident}');assert managed.is_success
                    for share in managed.json()['items']:
                        if share['id'] in shares and share['status']!='revoked':assert client.post(root+f'/artifact-shares/{share["id"]}/revoke',json={'revision':share['revision']}).is_success
                    assert client.delete(root+f'/artifacts/{ident}').is_success
                assert client.get(root+f'/artifacts/{ident}').status_code==404
            for ident in shares:assert client.get(root+f'/artifact-shares/{ident}/content').status_code==404
            if chat:
                assert client.delete(root+f'/conversations/{chat}').is_success
                assert client.get(root+f'/conversations/{chat}').status_code==404
        print(json.dumps({'reviewed_self_audience_only':True,'restored_exact_preview':True,'idempotent_publication':True,'sanitized_snapshot':True,
            'server_analysis_and_excel':True,'source_edits_do_not_change_share':True,'reviewed_edition_update':True,'revoke_is_idempotent':True,
            'source_archive_cancels_share':True,'cleanup_verified':True,'external_model_calls':0,'outbound_messages':0,'non_artifact_business_writes':0}),flush=True)


if __name__=='__main__':main()
