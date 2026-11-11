from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from ai_test_utils import auth_headers
from app.ai_operator.workspace_search import rank_chunks

ROOT='/api/v1/ai-operator/suite'


def chat(client,h,workspace_id=None):
    r=client.post(ROOT+'/conversations',headers=h,json={'title':'Authorized knowledge','workspace_id':workspace_id})
    assert r.status_code==201,r.text
    return r.json()['id']


def test_search_uses_native_records_and_never_changes_them(client,db):
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h)
    r=client.post('/api/v1/crm/tasks',headers=h,json={'title':'Escalate overdue onboarding commitments','description':'Private note not in the minimized knowledge response'})
    assert r.status_code==200,r.text
    ident=r.json()['id']
    spec={'conversation_id':conversation,'query':'overdue onboarding','mode':'lexical','tools':['crm.tasks'],'include_uploads':False}
    found=client.post(ROOT+'/workspace/search',headers=h,json=spec)
    assert found.status_code==200,found.text
    result=found.json();assert result['semantic_used'] is False
    item=next(s for s in result['items'] if s['record_id']==ident)
    assert item['tool']=='crm.tasks' and item['kind']=='record' and item['href']=='/crm/tasks'
    assert 'Private note' not in found.text
    assert client.get('/api/v1/crm/tasks/'+str(ident),headers=h).json()['title']=='Escalate overdue onboarding commitments'
    assert client.post(ROOT+'/workspace/search',headers=h,json={**spec,'tools':['crm.create_task']}).status_code==422
    assert client.post(ROOT+'/workspace/search',headers=h,json={**spec,'tools':['http.get']}).status_code==422


def test_search_reauthorizes_conversation_and_module_before_embedding(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h)
    other,user=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    calls=[]
    from app.ai_operator import local_embeddings
    monkeypatch.setattr(local_embeddings,'encode',lambda texts:calls.append(texts))
    body={'conversation_id':conversation,'query':'confidential','tools':['fam.vouchers']}
    assert client.post(ROOT+'/workspace/search',headers=other,json=body).status_code==404
    own=chat(client,other)
    assert client.post(ROOT+'/workspace/search',headers=other,json={**body,'conversation_id':own}).status_code==403
    assert calls==[]


def test_search_project_must_match_conversation_workspace(client,db):
    from app.apps.project_management.models import PMSProject
    h,_,project,_=setup_suite(client,db);conversation=chat(client,h)
    r=client.post(ROOT+'/workspace/search',headers=h,json={'conversation_id':conversation,'query':'Review','tools':['pms.tasks'],'project_id':project,'mode':'lexical'})
    assert r.status_code==422,r.text
    workspace=db.get(PMSProject,project).workspace_id
    scoped=chat(client,h,workspace)
    r=client.post(ROOT+'/workspace/search',headers=h,json={'conversation_id':scoped,'query':'Review','tools':['pms.tasks'],'project_id':project,'mode':'lexical'})
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['tool']=='pms.tasks'
    assert r.json()['items'][0]['href'].startswith('/pms/tasks/')


def test_hybrid_retrieval_returns_semantic_matches_and_reports_fallback(monkeypatch):
    from app.ai_operator import local_embeddings
    chunks=[{'text':'Customers must settle outstanding invoices.','source':{'id':'invoice'}},
        {'text':'New starters receive a laptop.','source':{'id':'onboarding'}}]
    monkeypatch.setattr(local_embeddings,'encode',lambda _: [[1.,0.],[.9,.1],[0.,1.]])
    result,engine=rank_chunks(chunks,'Which bills have not been paid?','hybrid')
    assert result[0]['id']=='invoice' and result[0]['semantic_score']==.9
    assert engine['semantic_used'] and engine['method']=='local-minilm-tfidf-hybrid'
    def unavailable(_):raise ValueError('runtime missing')
    monkeypatch.setattr(local_embeddings,'encode',unavailable)
    result,engine=rank_chunks(chunks,'invoices','hybrid')
    assert result[0]['id']=='invoice' and engine['semantic_used'] is False and engine['notice']
    with pytest.raises(HTTPException) as error:rank_chunks(chunks,'bills','semantic')
    assert error.value.status_code==503


def test_search_removed_uploads_and_other_users_are_not_retrieved(client,db):
    h,_,_,_=setup_suite(client,db);conversation=chat(client,h)
    r=client.post(ROOT+f'/conversations/{conversation}/attachments',headers=h,files={'file':('policy.txt',b'Escalation owners review all stalled commitments.','text/plain')})
    assert r.status_code==201,r.text
    ident=r.json()['id'];body={'conversation_id':conversation,'query':'Escalation','mode':'lexical'}
    found=client.post(ROOT+'/workspace/search',headers=h,json=body)
    assert found.status_code==200,found.text
    assert found.json()['items'][0]['file_id']==ident
    assert client.delete(ROOT+f'/conversations/{conversation}/attachments/{ident}',headers=h).status_code==200
    assert client.post(ROOT+'/workspace/search',headers=h,json=body).json()['items']==[]


def test_embedding_process_never_receives_credentials_or_query_in_arguments(monkeypatch):
    from types import SimpleNamespace
    from app.ai_operator import local_embeddings as model
    monkeypatch.setenv('GEMINI_API_KEY','secret-do-not-send')
    monkeypatch.setenv('DATABASE_URL','secret-database')
    calls=[]
    def process(args,**kwargs):
        calls.append((args,kwargs));return SimpleNamespace(returncode=0,stdout=__import__('json').dumps({'vectors':[[1.]+[0.]*383]}))
    monkeypatch.setattr(model.subprocess,'run',process)
    assert len(model.encode(['private query'])[0])==384
    args,kwargs=calls[0]
    assert 'private query' not in str(args) and 'private query' in kwargs['input']
    assert 'GEMINI_API_KEY' not in kwargs['env'] and 'DATABASE_URL' not in kwargs['env']
    assert kwargs['env']['HF_HUB_OFFLINE']=='1'
    with pytest.raises(ValueError):model.encode(['x'*1601])
