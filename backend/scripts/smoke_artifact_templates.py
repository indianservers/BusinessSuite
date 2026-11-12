"""Live local template review, follow-ups and independent artifact creation."""
import json
import time
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';conversations=[];runs=[];artifacts=set();reviews=[];template=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        login=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert login.is_success,'Login failed';client.headers['Authorization']='Bearer '+login.json()['access_token']
        def conversation(title):
            r=client.post(root+'/conversations',json={'title':title});assert r.is_success
            conversations.append(r.json()['id']);return r.json()['id']
        def say(ident,text):
            r=client.post(root+'/commands',json={'request_key':str(uuid4()),'provider':'local','module':'CRM','conversation_id':ident,'text':text});assert r.is_success
            value=r.json();runs.append(value['id']);return value
        def execute(run):
            assert run['status']=='awaiting_approval'
            assert all(step['tool'] in ('crm.create_artifact','crm.edit_artifact') for step in run['plan']['steps'])
            r=client.post(root+f'/runs/{run["id"]}/approve',json={'plan_hash':run['plan_hash']});assert r.is_success
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                r=client.get(root+f'/runs/{run["id"]}');assert r.is_success;value=r.json()
                if value['status'] in ('succeeded','failed','paused','cancelled','needs_reconciliation'):break
                time.sleep(1)
            else:raise AssertionError('Existing artifact run did not finish within the observation window')
            assert value['status']=='succeeded',value.get('error_code')
            for receipt in value['receipts']:artifacts.add(receipt['artifact_id'])
            return value['receipts'][0]['artifact_id']
        try:
            author=conversation('Synthetic template source')
            source=execute(say(author,'Create document called Review for {{customer}}: Period {{period}}. Synthetic example only.'))
            r=client.get(root+f'/artifacts/{source}');assert r.is_success;item=r.json()
            name='Synthetic reusable '+uuid4().hex[:8]
            r=client.post(root+'/artifact-templates/preview',json={'request_key':str(uuid4()),'name':name,
                'source_artifact_id':source,'source_revision':1,'body':{k:item[k] for k in ('title','kind','content','columns','rows')}});assert r.is_success
            review=r.json();reviews.append(review['id']);assert review['variables']==['customer','period']
            restored=client.get(root+f'/artifact-templates/reviews/{review["id"]}');assert restored.is_success and restored.json()['preview_hash']==review['preview_hash']
            body={'preview_hash':review['preview_hash']}
            r=client.post(root+f'/artifact-templates/reviews/{review["id"]}/confirm',json=body);assert r.is_success
            template=r.json()['template']
            again=client.post(root+f'/artifact-templates/reviews/{review["id"]}/confirm',json=body);assert again.is_success and again.json()['template']['id']==template['id']
            copied_chat=conversation('Synthetic template followups')
            first=say(copied_chat,f'Use template "{name}"');assert first['status']=='needs_clarification' and 'customer' in first['plan']['question']
            second=say(copied_chat,'Acme');assert second['status']=='needs_clarification' and 'period' in second['plan']['question']
            draft=say(copied_chat,'May');assert draft['status']=='awaiting_approval' and draft['receipts']==[]
            copied=execute(draft);assert copied!=source
            r=client.get(root+f'/artifacts/{copied}');assert r.is_success
            assert r.json()['title']=='Review for Acme' and r.json()['provenance']['template']['id']==template['id'] and r.json()['provenance']['citations']==[]
            pending=say(conversation('Synthetic template archive check'),f'Use template #{template["id"]}: customer=Acme; period=June')
            assert pending['status']=='awaiting_approval'
            assert client.delete(root+f'/artifact-templates/{template["id"]}').is_success
            assert client.post(root+f'/runs/{pending["id"]}/approve',json={'plan_hash':pending['plan_hash']}).status_code==404
            assert client.get(root+f'/artifacts/{copied}').is_success
        finally:
            for ident in runs:
                current=client.get(root+f'/runs/{ident}');assert current.is_success;value=current.json()
                for receipt in value.get('receipts',[]):
                    if receipt.get('artifact_id'):artifacts.add(receipt['artifact_id'])
                if value['status'] not in ('succeeded','cancelled','superseded'):assert client.post(root+f'/runs/{ident}/cancel').is_success
            if template:
                current=client.get(root+f'/artifact-templates/{template["id"]}')
                if current.is_success:assert client.delete(root+f'/artifact-templates/{template["id"]}').is_success
                assert client.get(root+f'/artifact-templates/{template["id"]}').status_code==404
            for ident in reviews:assert client.delete(root+f'/artifact-templates/reviews/{ident}').is_success
            for ident in artifacts:
                assert client.delete(root+f'/artifacts/{ident}').is_success
                assert client.get(root+f'/artifacts/{ident}').status_code==404
            for ident in conversations:
                assert client.delete(root+f'/conversations/{ident}').is_success
                assert client.get(root+f'/conversations/{ident}').status_code==404
        print(json.dumps({'private_template_review_restored':True,'idempotent_confirmation':True,'named_template_reuse':True,
            'multiple_missing_value_followups':True,'independent_reviewed_artifact':True,'archive_blocks_pending_approval':True,
            'cleanup_verified':True,'external_model_calls':0,'non_artifact_business_writes':0}),flush=True)


if __name__=='__main__':main()
