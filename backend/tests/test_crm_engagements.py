from datetime import datetime, timedelta, timezone

import pytest

from app.apps.crm.models import CRMMeeting

ROOT = '/api/v1/crm'


@pytest.fixture
def headers(db, superuser_headers):
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, db.query(User).filter_by(email='testadmin@test.com').one())
    db.commit()
    return superuser_headers


def meeting(client, headers, **changes):
    data = {'title':'Review customer outcomes','start_time':'2026-11-07T09:00:00Z','end_time':'2026-11-07T10:00:00Z', **changes}
    return client.post(ROOT+'/meetings',headers=headers,json=data)


def test_meeting_intervals_validated_on_create_and_partial_update(client, headers):
    assert meeting(client,headers,end_time='2026-11-07T08:00:00Z').status_code == 422
    assert meeting(client,headers,end_time='2026-11-07T09:00:00Z').status_code == 422
    saved = meeting(client,headers)
    assert saved.status_code == 201, saved.text
    identity = saved.json()['id']
    assert client.patch(f'{ROOT}/meetings/{identity}',headers=headers,json={'end_time':'2026-11-07T08:00:00Z'}).status_code == 422
    assert client.patch(f'{ROOT}/meetings/{identity}',headers=headers,json={'start_time':'2026-11-07T11:00:00Z'}).status_code == 422
    edited = client.patch(f'{ROOT}/meetings/{identity}',headers=headers,json={'outcome':'Scope confirmed','status':'Completed'})
    assert edited.status_code == 200, edited.text
    assert edited.json()['outcome'] == 'Scope confirmed'


def test_meeting_conflicts_observe_scope_and_half_open_intervals(client, db, headers):
    created = meeting(client,headers)
    assert created.status_code == 201, created.text
    ident = created.json()['id']
    endpoint = ROOT+'/engagements/availability'
    params = {'start':'2026-11-07T09:30:00Z','end':'2026-11-07T10:30:00Z'}
    overlaps = client.get(endpoint,headers=headers,params=params)
    assert overlaps.status_code == 200, overlaps.text
    assert overlaps.json()['total'] == 1
    assert client.get(endpoint,headers=headers,params={**params,'exclude_id':ident}).json()['total'] == 0
    assert client.get(endpoint,headers=headers,params={'start':'2026-11-07T10:00:00Z','end':'2026-11-07T11:00:00Z'}).json()['total'] == 0
    assert client.get(endpoint,headers=headers,params={**params,'end':'2026-11-07T09:00:00Z'}).status_code == 422
    row = db.get(CRMMeeting,ident)
    row.organization_id=987654
    db.commit()
    assert client.get(endpoint,headers=headers,params=params).json()['total'] == 0


def test_cancelled_and_other_owner_meetings_do_not_block_my_schedule(client,db,headers):
    from app.models.user import User
    from app.core.security import get_password_hash
    other=User(email='calendar-peer@example.test',hashed_password=get_password_hash('Test@123456'),is_active=True)
    db.add(other);db.flush()
    user=db.query(User).filter_by(email='testadmin@test.com').one()
    for owner,status in [(other.id,'Scheduled'),(user.id,'Cancelled')]:
        db.add(CRMMeeting(organization_id=1,owner_user_id=owner,title='Not my conflict',status=status,start_time=datetime(2026,11,7,9,tzinfo=timezone.utc),end_time=datetime(2026,11,7,10,tzinfo=timezone.utc)))
    db.commit()
    result=client.get(ROOT+'/engagements/availability',headers=headers,params={'start':'2026-11-07T09:15:00Z','end':'2026-11-07T09:45:00Z'})
    assert result.status_code==200,result.text
    assert result.json()['total']==0


def test_engagement_views_filter_before_pagination_in_local_timezone(client,headers):
    for title,start,end in [('Before local day','2026-11-06T18:00:00Z','2026-11-06T18:29:00Z'),('Local day start','2026-11-06T18:30:00Z','2026-11-06T19:00:00Z'),('Local day end','2026-11-07T18:00:00Z','2026-11-07T18:29:00Z')]:
        response=meeting(client,headers,title=title,start_time=start,end_time=end)
        assert response.status_code==201,response.text
    # Freeze the helper clock without modifying the actual calendar or database.
    from app.apps.crm.engagements import apply_engagement_view
    from unittest.mock import patch
    at=datetime(2026,11,7,12,tzinfo=timezone.utc)
    with patch('app.apps.crm.engagements.apply_engagement_view',side_effect=lambda q,m,v,z:apply_engagement_view(q,m,v,z,now=at)):
        result=client.get(ROOT+'/meetings',headers=headers,params={'activity_view':'today','timezone':'Asia/Kolkata','per_page':1})
    assert result.status_code==200,result.text
    assert result.json()['total']==2 and result.json()['pages']==2
    assert client.get(ROOT+'/meetings',headers=headers,params={'activity_view':'bad'}).status_code==422
    assert client.get(ROOT+'/calls',headers=headers,params={'timezone':'Invalid/Zone'}).status_code==422


def test_call_duration_validation_and_permissions(client,headers):
    data={'direction':'Outbound','phone_number':'9876543210','phone_number_country_code':'+91','call_time':'2026-11-07T10:00:00Z','duration_seconds':-1}
    assert client.post(ROOT+'/calls',headers=headers,json=data).status_code==422
    saved=client.post(ROOT+'/calls',headers=headers,json={**data,'duration_seconds':180,'outcome':'Qualified'})
    assert saved.status_code==201,saved.text
    assert saved.json()['duration_seconds']==180
    assert client.patch(f'{ROOT}/calls/{saved.json()["id"]}',headers=headers,json={'duration_seconds':-2}).status_code==422
    result=client.get(ROOT+'/engagements/permissions',headers=headers)
    assert result.status_code==200,result.text
    assert result.json()['meetings']['manage'] and result.json()['calls']['view']
    assert client.get(ROOT+'/engagements/availability',params={'start':data['call_time'],'end':'2026-11-07T11:00:00Z'}).status_code in {401,403}


def test_activity_viewer_can_read_but_cannot_modify_meetings(client, db, headers):
    from tests.test_crm_sales_performance_rbac import _headers_for_permissions
    readonly = _headers_for_permissions(client, db, 'meeting-reader@example.com', ['crm_activities_view'])
    result = client.get(ROOT+'/engagements/permissions',headers=readonly)
    assert result.status_code == 200, result.text
    assert result.json()['meetings'] == {'view':True,'manage':False}
    assert result.json()['calls'] == {'view':True,'manage':False}
    assert client.get(ROOT+'/meetings',headers=readonly).status_code == 200
    assert meeting(client,readonly).status_code == 403
    none = _headers_for_permissions(client, db, 'no-activity-access@example.com', [])
    assert client.get(ROOT+'/engagements/permissions',headers=none).status_code == 403


def test_conversation_follow_up_is_retry_safe_and_reuses_task_permissions(client, db, headers):
    from app.apps.crm.models import CRMTask
    contact = client.post(ROOT+'/contacts',headers=headers,json={'first_name':'Follow-up','last_name':'Customer','full_name':'Follow-up customer','email':'followup-customer@example.com'})
    assert contact.status_code == 201,contact.text
    contact_id = contact.json()['id']
    created = meeting(client,headers,contact_id=contact_id)
    assert created.status_code == 201,created.text
    ident = created.json()['id']
    endpoint = f'{ROOT}/engagements/meetings/{ident}/follow-up'
    payload = {'title':'Send agreed proposal','due':'2026-11-10T09:00:00Z'}
    first = client.post(endpoint,headers=headers,json=payload)
    assert first.status_code == 201,first.text
    second = client.post(endpoint,headers=headers,json=payload)
    assert second.status_code == 201,second.text
    assert first.json()['id'] == second.json()['id']
    assert db.query(CRMTask).filter_by(title='Send agreed proposal').count() == 1
    assert first.json()['task_details']['sourceId'] == ident
    assert first.json()['contactId'] == contact_id
    equivalent = client.post(endpoint,headers=headers,json={**payload,'due':'2026-11-10T14:30:00+05:30'})
    assert equivalent.status_code == 201,equivalent.text
    assert equivalent.json()['id'] == first.json()['id']
    row = db.get(CRMMeeting,ident)
    row.organization_id = 987654
    db.commit()
    assert client.post(endpoint,headers=headers,json={**payload,'title':'Should not be created'}).status_code == 404
