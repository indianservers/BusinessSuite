import json
from uuid import uuid4
import pytest
from app.apps.project_management.models import PMSSavedFilter
from tests.test_saved_view_actions import setup
from tests.test_pms_view_changes import native,done
from tests.test_suite_operator import ROOT,approve,tick
from tests.test_suite_workspace import say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def seed(client,db,h,pid,count):
    base=native(client,h,pid,'Synthetic page 000');sample=db.get(PMSSavedFilter,base['id'])
    for index in range(1,count):
        db.add(PMSSavedFilter(organization_id=sample.organization_id,user_id=sample.user_id,project_id=pid,
            name=f'Synthetic page {index:03}',view_type='task_list',entity_type='task',visibility='private',
            is_shared=False,is_default=False,query=sample.query,filters_json=sample.filters_json,
            sort_json=sample.sort_json,columns_json=sample.columns_json))
    db.commit()
    rows=db.query(PMSSavedFilter).filter_by(project_id=pid,user_id=sample.user_id).order_by(PMSSavedFilter.id).all()
    from app.ai_operator.pms_view_changes import typed
    assert len(rows)==count
    assert all(typed(row) is not None for row in rows),[(r.id,r.query,r.filters_json) for r in rows[:2]]
    return rows


def test_cursor_pages_reach_all_views_without_offset_skips_after_delete(client,db):
    h,user,pid,workspace,chat=setup(client,db);rows=seed(client,db,h,pid,111)
    path=ROOT+f'/pms/views/records/{pid}';page=client.get(path,headers=h).json()
    assert len(page['items'])==25 and page['has_more'] and page['next_after_id']==rows[24].id
    assert client.delete('/api/v1/project-management/saved-views/'+str(rows[0].id),headers=h).status_code==200
    found=[item['id'] for item in page['items']];cursor=page['next_after_id']
    while cursor is not None:
        page=client.get(path,headers=h,params={'after_id':cursor}).json()
        assert page['scanned_count']<=25 and len(page['items'])<=25
        found.extend(item['id'] for item in page['items']);cursor=page['next_after_id']
    assert found==[row.id for row in rows] and len(set(found))==111


def test_late_target_lookup_and_reviewed_edit_are_not_limited_to_first_page(client,db):
    h,user,pid,workspace,chat=setup(client,db);rows=seed(client,db,h,pid,111);target=rows[-1]
    path=ROOT+f'/pms/views/records/{pid}'
    for lookup in ({'view_id':target.id},{'name':target.name.upper()}):
        response=client.get(path,headers=h,params=lookup);assert response.status_code==200,response.text
        assert [v['id'] for v in response.json()['items']]==[target.id]
    draft=say(client,h,chat,f'PMS: Update view called {target.name}: priority=Low',module='PMS',workspace_id=workspace,project_id=pid)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert draft['plan']['steps'][0]['payload']['view_id']==target.id
    approve(client,h,draft);tick(client,db);assert done(client,h,draft)['status']=='succeeded'
    db.refresh(target);assert json.loads(target.filters_json)['priority']=='Low'
    remove=say(client,h,chat,'Remove that view',module='PMS',workspace_id=workspace)
    assert remove['status']=='awaiting_approval'
    assert remove['plan']['steps'][0]['payload']['view_id']==target.id


def test_unsupported_empty_page_has_a_safe_continuation_cursor(client,db):
    h,user,pid,workspace,chat=setup(client,db);rows=seed(client,db,h,pid,27)
    for row in rows[:25]:row.query='opaque native expression'
    db.commit();path=ROOT+f'/pms/views/records/{pid}'
    page=client.get(path,headers=h).json()
    assert page['items']==[] and page['unsupported_views']==25 and page['has_more']
    next_page=client.get(path,headers=h,params={'after_id':page['next_after_id']}).json()
    assert [v['id'] for v in next_page['items']]==[row.id for row in rows[25:]]
    assert not next_page['has_more'] and next_page['unsupported_views']==0


@pytest.mark.parametrize('query',[{'after_id':-1},{'view_id':0},{'view_id':1,'name':'Focus'},{'view_id':1,'after_id':1},{'name':' '},{'name':'x'*141}])
def test_invalid_read_selectors_are_rejected(client,db,query):
    h,user,pid,workspace,chat=setup(client,db)
    assert client.get(ROOT+f'/pms/views/records/{pid}',headers=h,params=query).status_code==422


def test_numeric_names_are_distinct_from_ids_and_wildcards_stay_literal(client,db):
    h,user,pid,workspace,chat=setup(client,db);base=native(client,h,pid)
    named=native(client,h,pid,str(base['id']));literal=native(client,h,pid,'Focus%_[]')
    draft=say(client,h,chat,f'Update view called {base["id"]}: priority=Low',module='PMS',workspace_id=workspace,project_id=pid)
    assert draft['status']=='awaiting_approval' and draft['plan']['steps'][0]['payload']['view_id']==named['id']
    exact=client.get(ROOT+f'/pms/views/records/{pid}',headers=h,params={'name':'Focus%_[]'}).json()
    assert [item['id'] for item in exact['items']]==[literal['id']]
    unicode_name=native(client,h,pid,'Ä నమూనా')
    exact=client.get(ROOT+f'/pms/views/records/{pid}',headers=h,params={'name':'Ä నమూనా'}).json()
    assert [item['id'] for item in exact['items']]==[unicode_name['id']]


def test_page_counts_and_lookup_do_not_disclose_other_owners_or_companies(client,db):
    h,user,pid,workspace,chat=setup(client,db);rows=seed(client,db,h,pid,3)
    rows[1].user_id=None;rows[2].organization_id=999999;db.commit()
    path=ROOT+f'/pms/views/records/{pid}'
    page=client.get(path,headers=h).json()
    assert len(page['items'])==1 and page['scanned_count']==1 and page['unsupported_views']==0
    assert client.get(path,headers=h,params={'view_id':rows[1].id}).json()['items']==[]
    assert client.get(path,headers=h,params={'name':rows[2].name}).json()['items']==[]


def test_cloud_context_marks_partial_pages_and_preserves_direct_target_hash(client,db,monkeypatch):
    from tests.test_ai_operator import mock_provider
    h,user,pid,workspace,chat=setup(client,db);rows=seed(client,db,h,pid,28)
    calls=mock_provider(monkeypatch,{'summary':'Choose the required view before an action','question':'Which view should change?','steps':[]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS',
        'workspace_id':workspace,'text':'Inspect authorized view pages before proposing a change',
        'context':[{'tool':'pms.saved_views','record_id':pid},{'tool':'pms.saved_views','record_id':pid,'payload':{'view_id':rows[-1].id}}]})
    assert response.status_code==200,response.text
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    observed=[v for v in outbound['authorized_context'] if v['tool']=='pms.saved_views']
    assert not observed[0]['complete'] and observed[0]['records']['has_more']
    assert len(observed[0]['records']['items'])==25
    assert observed[1]['complete'] and observed[1]['records']['items'][0]['id']==rows[-1].id
    assert len(observed[1]['records']['items'][0]['source_sha256'])==64
    from app.ai_operator.suite_tools import validate_payload,TOOLS
    from fastapi import HTTPException
    with pytest.raises(HTTPException):validate_payload(TOOLS['pms.saved_views'],{'view_id':True})
