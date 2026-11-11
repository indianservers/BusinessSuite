from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/suite'


def test_private_skill_history_survives_edits_and_requires_current_owner(client,db):
    h,_,_,_=setup_suite(client,db)
    body={'name':'Delivery review','instructions':'Check delivery evidence before drafting tasks.','tools':['crm.tasks','crm.create_task']}
    made=client.post(ROOT+'/agents/catalog/skills',headers=h,json=body);assert made.status_code==200,made.text
    skill=made.json();url=ROOT+f'/agents/catalog/skills/{skill["id"]}'
    updated=client.put(url,headers=h,json={**body,'instructions':'Check dates and owners before drafting tasks.','revision':1})
    assert updated.status_code==200,updated.text
    history=client.get(url+'/versions',headers=h);assert history.status_code==200,history.text
    versions=history.json()['items'];assert [v['revision'] for v in versions]==[2,1]
    assert versions[1]['instructions']==body['instructions']
    assert client.put(url,headers=h,json={**body,'revision':1}).status_code==409
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(url+'/versions',headers=other).status_code==404
    assert client.delete(url,headers=h).status_code==200
    assert client.get(url+'/versions',headers=h).status_code==404


def test_knowledge_search_reads_body_after_heading_and_returns_source_offsets(client,db):
    h,_,_,_=setup_suite(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Private policy sources'}).json()['id']
    text='Delivery policy: "Escalation owners must review stalled commitments."\nతెలుగు విధానం'
    response=client.post(ROOT+f'/conversations/{chat}/attachments',headers=h,files={'file':('policy.txt',text.encode('utf-8'),'text/plain')})
    assert response.status_code==201,response.text
    file=response.json()
    query={'conversation_id':chat,'query':'escalation stalled commitments'}
    assert client.post(ROOT+'/workspace/file-search',headers=h,json={**query,'query':'   '}).status_code==422
    found=client.post(ROOT+'/workspace/file-search',headers=h,json=query);assert found.status_code==200,found.text
    result=found.json();assert result['files_searched']==1 and result['items']
    source=result['items'][0];assert source['file_id']==file['id'] and 'Escalation owners' in source['excerpt']
    assert text[source['start']:source['end']]==source['excerpt']
    assert source['href']==f'#bot-attachment-{file["id"]}'
    unicode=client.post(ROOT+'/workspace/file-search',headers=h,json={**query,'query':'తెలుగు'})
    assert unicode.json()['items']
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.post(ROOT+'/workspace/file-search',headers=other,json=query).status_code==404
    assert client.delete(ROOT+f'/conversations/{chat}/attachments/{file["id"]}',headers=h).status_code==200
    assert client.post(ROOT+'/workspace/file-search',headers=h,json=query).json()['items']==[]
