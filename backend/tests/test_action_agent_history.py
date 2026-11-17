"""Owner-scoped history navigation and minimal confirmed execution exports."""
import asyncio
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite, approve, ROOT
from app.ai_operator.suite import process_suite_batch
from ai_test_utils import auth_headers


def create(client, headers, text, *, action=False, summary=None):
    response=client.post(ROOT+'/commands',headers=headers,json={
        'request_key':str(uuid4()),'provider':'local','text':text,
        'local_plan':{'summary':summary or text,'steps':[
            {'tool':'crm.create_task','payload':{'title':text,'description':'Private description must not appear in export'}}
        ] if action else []}})
    assert response.status_code==200,response.text
    return response.json()


def test_history_search_status_and_stable_cursor_do_not_cross_owners(client,db):
    headers,_,_,_=setup_suite(client,db)
    older=create(client,headers,'Customer review')
    draft=create(client,headers,'Customer callback',action=True)
    newest=create(client,headers,'Inventory review',summary='Stock overview')
    other,_=auth_headers(client,db,email=f'history-{uuid4().hex}@example.com',permissions=['ai_assistant'])
    foreign=create(client,other,'Customer review')
    first=client.get(ROOT+'/runs',headers=headers,params={'limit':2}).json()
    assert [row['id'] for row in first['items']]==[newest['id'],draft['id']]
    assert first['has_more'] and first['next_before_id']==draft['id']
    # A newer arrival cannot shift the cursor or duplicate the previous page.
    create(client,headers,'Arrived after first page')
    second=client.get(ROOT+'/runs',headers=headers,params={'limit':2,'before_id':first['next_before_id']}).json()
    assert [row['id'] for row in second['items']]==[older['id']]
    assert not second['has_more'] and second['next_before_id'] is None
    found=client.get(ROOT+'/runs',headers=headers,params={'search':'CUSTOMER','status':'awaiting_approval'}).json()
    assert [row['id'] for row in found['items']]==[draft['id']]
    for search,ident in [('stock overview',newest['id']),('#'+str(older['id']),older['id'])]:
        assert [row['id'] for row in client.get(ROOT+'/runs',headers=headers,params={'search':search}).json()['items']]==[ident]
    assert client.get(ROOT+'/runs',headers=headers,params={'search':'#'+str(foreign['id'])}).json()['items']==[]
    # Search metacharacters are literal, never wildcard matching.
    assert client.get(ROOT+'/runs',headers=headers,params={'search':'%'}).json()['items']==[]


@pytest.mark.parametrize('params',[{'limit':0},{'limit':51},{'before_id':0},{'status':'not-a-status'},{'search':'a'*201}])
def test_history_rejects_invalid_filters(client,db,params):
    headers,_,_,_=setup_suite(client,db)
    assert client.get(ROOT+'/runs',headers=headers,params=params).status_code==422


def test_receipt_exports_confirmed_metadata_and_rechecks_ownership(client,db):
    headers,_,_,_=setup_suite(client,db)
    run=create(client,headers,'Private synthetic task',action=True)
    url=ROOT+f'/runs/{run["id"]}/receipt'
    assert client.get(url,headers=headers).status_code==409
    approve(client,headers,run)
    asyncio.run(process_suite_batch(db,client.app))
    response=client.get(url,headers=headers)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['version']=='action-agent-receipt-v1' and result['status']=='succeeded'
    assert result['receipts'][0]['tool']=='crm.create_task'
    assert set(result['receipts'][0])=={'step','tool','record_id','status'}
    assert 'Private synthetic task' not in response.text and 'Private description' not in response.text
    assert not {'command','plan','security_context','result','snapshots','request_key'} & result.keys()
    assert 'no-store' in response.headers['cache-control']
    assert 'attachment;' in response.headers['content-disposition']
    other,_=auth_headers(client,db,email=f'receipt-{uuid4().hex}@example.com',permissions=['ai_assistant'])
    assert client.get(url,headers=other).status_code==404


def test_partial_execution_receipt_does_not_claim_unfinished_steps(client,db):
    headers,_,_,_=setup_suite(client,db)
    response=client.post(ROOT+'/commands',headers=headers,json={
        'request_key':str(uuid4()),'provider':'local','text':'Two reviewed actions',
        'local_plan':{'summary':'Two tasks','steps':[
            {'tool':'crm.create_task','payload':{'title':title}} for title in ['First','Second']]}})
    run=response.json();approve(client,headers,run)
    asyncio.run(process_suite_batch(db,client.app,limit=1))
    receipt=client.get(ROOT+f'/runs/{run["id"]}/receipt',headers=headers)
    assert receipt.status_code==200,receipt.text
    assert receipt.json()['status']=='queued' and len(receipt.json()['receipts'])==1
    assert receipt.json()['receipts'][0]['step']==1
