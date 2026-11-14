from uuid import uuid4
from datetime import date
import pytest
from app.apps.project_management.models import PMSTimeLog
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_suite_workspace import say
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.rich_text_test_utils import organization_context


def seed(client,db):
    h,user,pid,task=setup_suite(client,db)
    rows=[PMSTimeLog(user_id=user.id,project_id=pid,task_id=task,log_date=date(2026,5,4),duration_minutes=10,
        description='Synthetic private description',is_billable=index%2==0,approval_status='Pending') for index in range(30)]
    rows.append(PMSTimeLog(user_id=user.id,project_id=pid,log_date=date(2026,6,1),duration_minutes=999,is_billable=True))
    db.add_all(rows);db.commit()
    return h,user,pid


def test_personal_time_totals_cover_all_rows_while_detail_is_paged(client,db):
    h,user,pid=seed(client,db);path=ROOT+f'/pms/time-summary/{pid}'
    response=client.get(path,headers=h,params={'start':'2026-05-04','end':'2026-05-10'})
    assert response.status_code==200,response.text
    value=response.json();assert value['entry_count']==30 and value['recorded_minutes']==300
    assert value['billable_minutes']==150 and value['nonbillable_minutes']==150
    assert value['has_more'] and len(value['rows'])==25
    assert 'Synthetic private description' not in response.text and 'user_id' not in response.text
    assert response.headers['cache-control']=='private, no-store'
    next_page=client.get(path,headers=h,params={'start':'2026-05-04','end':'2026-05-10','after_id':value['next_after_id']}).json()
    assert len(next_page['rows'])==5 and not next_page['has_more']
    assert next_page['recorded_minutes']==300 and next_page['entry_count']==30
    assert not set(row['id'] for row in value['rows'])&set(row['id'] for row in next_page['rows'])
    native=client.get('/api/v1/project-management/time-logs',headers=h,params={'project_id':pid,'user_id':user.id,'skip':1,'limit':3})
    assert native.status_code==200,native.text
    assert len(native.json())==3 and all(row['user_id']==user.id and row['project_id']==pid for row in native.json())


def test_time_summary_excludes_other_users_even_for_admin(client,db):
    from ai_test_utils import auth_headers
    h,user,pid=seed(client,db)
    _,other=auth_headers(client,db,email=f'time-summary-{uuid4()}@example.com',permissions=[])
    db.add(PMSTimeLog(user_id=other.id,project_id=pid,log_date=date(2026,5,4),duration_minutes=800,is_billable=True));db.commit()
    result=client.get(ROOT+f'/pms/time-summary/{pid}',headers=h,params={'start':'2026-05-04','end':'2026-05-10'})
    assert result.status_code==200 and result.json()['recorded_minutes']==300


def test_personal_time_summary_local_clarification_followup_and_citation(client,db):
    h,user,pid=seed(client,db)
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic recorded time'}).json()['id']
    initial=say(client,h,chat,'How much time did I log this week?',module='PMS')
    assert initial['status']=='needs_clarification'
    answered=say(client,h,chat,f'project={pid}; start=2026-05-04; end=2026-05-10',module='PMS')
    assert answered['status']=='answered',answered.get('error_code')
    assert '300 recorded minutes (5 hours)' in answered['plan']['summary']
    assert 'Totals cover all matching entries' in answered['plan']['summary']
    assert answered['result']['citations'][0]['href']==f'/pms/time-tracking?projectId={pid}'
    following=say(client,h,chat,'start=2026-06-01; end=2026-06-01',module='PMS')
    assert following['status']=='answered',following.get('error_code')
    assert '999 recorded minutes' in following['plan']['summary'] and not following['receipts']


@pytest.mark.parametrize('params',[{'start':'2026-05-10','end':'2026-05-04'},
    {'start':'2026-05-01','end':'2026-06-01'},{'start':'2026-05-04','end':'2026-05-04','after_id':-1}])
def test_time_summary_range_and_cursor_are_bounded(client,db,params):
    h,user,pid=seed(client,db)
    assert client.get(ROOT+f'/pms/time-summary/{pid}',headers=h,params=params).status_code==422


def test_time_summary_provider_context_is_minimized_and_totals_are_not_page_totals(client,db,monkeypatch):
    import json
    h,user,pid=seed(client,db)
    calls=mock_provider(monkeypatch,{'summary':'Your selected project recorded 300 minutes.','steps':[],'source_ids':[f's1:{pid}']})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS',
        'text':'Summarize my recorded time using this exact source','context':[{'tool':'pms.time_summary','record_id':pid,
            'payload':{'start':'2026-05-04','end':'2026-05-10'}}]})
    assert response.status_code==200,response.text
    assert response.json()['status']=='answered',response.json().get('error_code')
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    packet=next(row for row in outbound['authorized_context'] if row['tool']=='pms.time_summary')
    assert packet['records']['recorded_minutes']==300 and len(packet['records']['rows'])==25
    assert packet['records']['summary_scope']=='all_matching_entries' and packet['complete'] is False
    assert 'Synthetic private description' not in json.dumps(packet)


def test_time_summary_arguments_cannot_select_another_actor_and_outsider_is_denied(client,db):
    from ai_test_utils import auth_headers
    from app.ai_operator.suite_tools import validate_payload,TOOLS
    from fastapi import HTTPException
    h,user,pid=seed(client,db)
    outsider,_=auth_headers(client,db,email=f'summary-outsider-{uuid4()}@example.com',permissions=['ai_assistant'])
    response=client.get(ROOT+f'/pms/time-summary/{pid}',headers=outsider,params={'start':'2026-05-04','end':'2026-05-10'})
    assert response.status_code in {403,404}
    with pytest.raises(HTTPException):validate_payload(TOOLS['pms.time_summary'],{'start':'2026-05-04','end':'2026-05-10','user_id':user.id})
