"""Live local + Gemini retrieval using synthetic private metadata only."""
import json
from uuid import uuid4
import httpx
from app.core.config import settings


def main():
    root='/api/v1/ai-operator/suite';conversations=[];files=[];agent=None
    with httpx.Client(base_url='http://127.0.0.1:1534',timeout=150) as client:
        r=client.post('/api/v1/auth/login',json={'email':settings.BOOTSTRAP_ADMIN_EMAIL,'password':settings.BOOTSTRAP_ADMIN_PASSWORD})
        assert r.is_success,'Login failed'
        client.headers['Authorization']='Bearer '+r.json()['access_token']
        try:
            r=client.post(root+'/agents',json={'name':'Synthetic retrieval smoke','instructions':'Read relevant uploaded policy excerpts before answering. Cite the exact source. Do not invent facts or execute actions.','modules':['CRM'],'tools':['crm.search_knowledge'],'provider':'gemini'})
            assert r.is_success;agent=r.json()['id']
            for provider in ('local','gemini'):
                r=client.post(root+'/conversations',json={'title':f'Synthetic {provider} cited knowledge'})
                assert r.is_success;conversation=r.json()['id'];conversations.append(conversation)
                r=client.post(root+f'/conversations/{conversation}/attachments',files={'file':('leave-policy.txt',b'Annual leave requests require approval from the reporting manager before absence.','text/plain')})
                assert r.is_success;file=r.json()['id'];files.append((conversation,file))
                text='Search knowledge for: vacation approval' if provider=='local' else 'Who approves annual leave according to the uploaded policy? Read the relevant file excerpts before answering and cite the source.'
                r=client.post(root+'/commands',json={'request_key':str(uuid4()),'module':'CRM','provider':provider,'conversation_id':conversation,'text':text,**({'agent_id':agent} if provider=='gemini' else {})})
                assert r.is_success,f'{provider} command HTTP {r.status_code}'
                run=r.json();assert run['status']=='answered',f'{provider} run {run["status"]} {run.get("error_code")}'
                assert any(s.get('file_id')==file for s in run['result']['citations']),f'{provider} omitted source citation'
                assert 'manager' in run['plan']['summary'].lower() and run['approval_id'] is None and not run['receipts']
                if provider=='gemini':assert run['result'].get('planning_rounds',0)>=2
                else:
                    r=client.post(root+'/commands',json={'request_key':str(uuid4()),'module':'CRM','provider':'local','conversation_id':conversation,'text':'What about annual leave requests?'})
                    assert r.is_success and r.json()['status']=='answered' and any(s.get('file_id')==file for s in r.json()['result']['citations'])
                print(json.dumps({'provider':provider,'cited_answer':True,'automatic_tool_retrieval':provider=='gemini','local_followup_checked':provider=='local','business_actions':0}),flush=True)
        finally:
            for conversation,file in files:assert client.delete(root+f'/conversations/{conversation}/attachments/{file}').is_success
            for conversation in conversations:assert client.delete(root+f'/conversations/{conversation}').is_success
            if agent:assert client.delete(root+f'/agents/{agent}').is_success


if __name__=='__main__':main()
