"""Live local model check using private drafts only. Never approves an action."""
import argparse
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected-release',type=int,required=True);args=parser.parse_args()
    root='/api/v1/ai-operator/suite';chat=current=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=90) as client:
        response=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD});assert response.is_success,'Local login failed'
        client.headers['Authorization']='Bearer '+response.json()['access_token']
        try:
            response=client.post(root+'/conversations',json={'title':'Synthetic local dialogue release verification'});assert response.status_code==201
            chat=response.json()['id']
            def say(text):
                nonlocal current
                response=client.post(root+'/commands',json={'request_key':str(uuid4()),'conversation_id':chat,'provider':'local','module':'CRM','text':text})
                assert response.is_success,f'Command HTTP {response.status_code}'
                current=response.json();assert not current['receipts']
                return current
            first=say('CRM: create a task');assert first['status']=='needs_clarification',first.get('error_code')
            observed=first['result']['local_nlp']['release'];assert observed['job_id']==args.expected_release,observed
            learned=say('Yes please continue with the message followup');assert learned['status']=='needs_clarification',learned.get('error_code')
            assert learned['result']['local_nlp']['neural_prediction']['dialogue_act']['act']=='clarify'
            quoted=say('"Yes please continue with the message followup"');assert quoted['status']=='awaiting_approval',quoted.get('error_code')
            assert quoted['plan']['steps'][0]['payload']['title']=='Yes please continue with the message followup'
            response=client.post(root+f'/runs/{quoted["id"]}/cancel');assert response.is_success
            current=response.json();assert current['status']=='cancelled' and not current['receipts']
            print(json.dumps({'active_release':observed['job_id'],'scope':observed['scope'],'initial_title_question':True,'learned_acknowledgement_clarifies':True,'quoted_title_draft':True,'draft_cancelled':True,'approval_submitted':False,'external_model_calls':0}),flush=True)
        finally:
            if current and current['status'] in {'needs_clarification','awaiting_approval'}:assert client.post(root+f'/runs/{current["id"]}/cancel').is_success
            if chat:assert client.delete(root+f'/conversations/{chat}').is_success


if __name__=='__main__':main()
