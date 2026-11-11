"""Synthetic private skill test; verifies writes cannot be approved."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';skill=conversation=latest=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=60) as client:
        r=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD});assert r.is_success
        client.headers['Authorization']='Bearer '+r.json()['access_token']
        try:
            r=client.post(root+'/agents/catalog/skills',json={'name':'Synthetic skill test','instructions':'Prepare CRM task drafts only.','tools':['crm.create_task']});assert r.is_success;skill=r.json()['id']
            r=client.post(root+'/conversations',json={'title':'Synthetic skill testing check'});assert r.is_success;conversation=r.json()['id']
            r=client.post(root+'/commands',json={'request_key':str(uuid4()),'text':'Create CRM task called Synthetic skill testing','provider':'local','conversation_id':conversation,'test_skill_id':skill,'test_skill_revision':1});assert r.is_success
            result=r.json();latest=result['id'];assert result['status']=='awaiting_approval' and result['receipts']==[]
            assert client.post(root+f'/runs/{latest}/approve',json={'plan_hash':result['plan_hash']}).status_code==409
            r=client.post(root+'/commands',json={'request_key':str(uuid4()),'text':'Make it high priority','provider':'local','conversation_id':conversation});assert r.is_success
            result=r.json();latest=result['id'];assert result['result']['request']['test_skill_id']==skill and result['status']=='awaiting_approval'
            assert client.post(root+f'/runs/{latest}/approve',json={'plan_hash':result['plan_hash']}).status_code==409
            print(json.dumps({'canonical_skill_test':True,'followup_binding_verified':True,'write_approval_rejected':True,'business_actions':0,'external_model_calls':0}),flush=True)
        finally:
            if latest:
                current=client.get(root+f'/runs/{latest}');assert current.is_success
                if current.json()['status']=='awaiting_approval':assert client.post(root+f'/runs/{latest}/cancel').is_success
            if conversation:assert client.delete(root+f'/conversations/{conversation}').is_success
            if skill:assert client.delete(root+f'/agents/catalog/skills/{skill}').is_success


if __name__=='__main__':main()
