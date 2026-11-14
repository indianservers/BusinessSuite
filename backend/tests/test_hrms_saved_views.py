from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite,approve,tick,ROOT
from tests.test_suite_workspace import chat,say
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from app.shared.models import ServicePolicy
from app.ai_operator import suite
from ai_test_utils import auth_headers

V='/api/v1/helpdesk/ticket-views'


def test_hrms_views_private_revisioned_strict_and_cannot_expand_native_access(client,db):
    h,user,_,_=setup_suite(client,db)
    before=client.get('/api/v1/helpdesk/tickets',headers=h).json()
    created=client.post(V,headers=h,json={'name':'Assigned urgent','filters':{'status':'Pending','priority':'Critical','assigned_to_me':True}})
    assert created.status_code==201,created.text
    value=created.json();view=value['items'][0]
    row=db.query(ServicePolicy).filter_by(kind='pipeline_ui').one()
    assert row.scope_key==f'pipeline-ui:1:hrms:helpdesk_tickets:{user.id}'
    other,_=auth_headers(client,db,email=f'private-{uuid4()}@example.com',permissions=[])
    response=client.get(V,headers=other);assert response.status_code==200,response.text
    assert response.json()['items']==[]
    assert client.get('/api/v1/helpdesk/tickets',headers=other).json()==[]
    assert client.put(V+'/'+view['id'],headers=other,json={'name':'Stolen','filters':{},'revision':value['revision']}).status_code==404
    edited=client.put(V+'/'+view['id'],headers=h,json={'name':'My followups','filters':{'status':'In Progress'},'revision':value['revision']})
    assert edited.status_code==200
    assert client.delete(V+'/'+view['id'],headers=h,params={'revision':value['revision']}).status_code==409
    assert client.delete(V+'/'+view['id'],headers=h,params={'revision':edited.json()['revision']}).status_code==200
    assert client.get('/api/v1/helpdesk/tickets',headers=h).json()==before
    for filters in ({'status':'Invented'},{'assigned_to_me':'false'},{'my_tickets':1},{'search':'unsupported'}):
        assert client.post(V,headers=h,json={'name':'Rejected','filters':filters}).status_code==422
    assert client.post(V,headers=h,json={'name':'No shared','filters':{},'shared':True}).status_code==422
    assert client.post(V,headers={**h,'X-Task-View-Company':'9999'},json={'name':'Wrong company','filters':{}}).status_code==409
    assert client.get(V,headers=h).headers['cache-control']=='private, no-store'


def test_bot_hrms_view_followups_inline_edit_review_and_native_result(client,db):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'HRMS: Save ticket view called Delivery: status=Open; assigned_to_me=true',module='HRMS')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert draft['plan']['steps'][0]['tool']=='hrms.create_saved_view'
    assert client.get(V,headers=h).json()['items']==[]
    corrected=say(client,h,ident,'priority=High; my_tickets=true',module='HRMS')
    assert corrected['status']=='awaiting_approval'
    payload=corrected['plan']['steps'][0]['payload']
    assert payload['filters']['status']=='Open' and payload['filters']['assigned_to_me'] is True
    assert client.post(ROOT+'/hrms/views/create-approved',headers=h,json={**payload,'suite_run_id':corrected['id'],'suite_step':1}).status_code==403
    revised=client.post(ROOT+f'/runs/{corrected["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':corrected['plan_hash'],
        'changes':[{'step':1,'field':'name','value':'Delivery focus'}]})
    assert revised.status_code==200,revised.text
    final_draft=say(client,h,ident,'status=Pending',module='HRMS');assert final_draft['status']=='awaiting_approval'
    assert final_draft['plan']['steps'][0]['payload']['name']=='Delivery focus'
    approve(client,h,final_draft);tick(client,db)
    finished=client.get(ROOT+f'/runs/{final_draft["id"]}',headers=h).json();assert finished['status']=='succeeded',finished.get('error_code')
    views=client.get(V,headers=h).json()['items'];assert len(views)==1 and views[0]['filters']['status']=='Pending'
    assert finished['result_cards'][0]['href']==f'/hrms/helpdesk?view={views[0]["id"]}'
    approve(client,h,finished);tick(client,db);assert len(client.get(V,headers=h).json()['items'])==1


def test_hrms_view_recovers_lost_outer_receipt_without_duplicate(client,db,monkeypatch):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Save ticket view called Recovery: status=Open',module='HRMS');approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost CRM view receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    stopped=client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume']
    resumed=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert resumed.status_code==200 and resumed.json()['status']=='succeeded',resumed.text
    assert len(client.get(V,headers=h).json()['items'])==1


@pytest.mark.parametrize('operation',['change','remove'])
def test_hrms_view_changed_after_commit_cannot_be_recreated_or_claimed_unchanged(client,db,monkeypatch,operation):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h)
    draft=say(client,h,ident,'Save ticket view called Stale: status=Open',module='HRMS');approve(client,h,draft)
    original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost outer receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    current=client.get(V,headers=h).json();view=current['items'][0]
    if operation=='change':response=client.put(V+'/'+view['id'],headers=h,json={'name':view['name'],'filters':{'status':'Closed'},'revision':current['revision']})
    else:response=client.delete(V+'/'+view['id'],headers=h,params={'revision':current['revision']})
    assert response.status_code==200
    resumed=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert resumed.status_code==409
    assert len(client.get(V,headers=h).json()['items'])==(1 if operation=='change' else 0)


def test_applied_view_uses_native_ticket_query_and_never_grants_access(client,db):
    from tests.test_ticket_actions import seed
    from app.models.helpdesk import HelpdeskTicket
    h,user,hidden=seed(client,db)
    other_h,other=auth_headers(client,db,email=f'assignee-{uuid4()}@example.com',permissions=[])
    created=client.post('/api/v1/helpdesk/tickets/json',headers=h,json={'subject':'Assigned synthetic ticket','description':'Visible only through native scope','priority':'Critical'})
    assert created.status_code==201,created.text
    ident=created.json()['id'];ticket=db.get(HelpdeskTicket,ident)
    ticket.status='Pending';ticket.assigned_to=other.id;db.commit()
    response=client.post(V,headers=other_h,json={'name':'Assigned critical','filters':{'status':'Pending','priority':'Critical','assigned_to_me':True}})
    assert response.status_code==201,response.text
    filters=response.json()['items'][0]['filters']
    visible=client.get('/api/v1/helpdesk/tickets',headers=other_h,params=filters)
    assert visible.status_code==200 and [row['id'] for row in visible.json()]==[ident]
    assert client.get(f'/api/v1/helpdesk/tickets/{hidden}',headers=other_h).status_code==404
    own=client.get('/api/v1/helpdesk/tickets',headers=other_h,params={**filters,'my_tickets':True})
    assert own.status_code==200 and own.json()==[]
    broad=client.get('/api/v1/helpdesk/tickets',headers=other_h)
    assert [row['id'] for row in broad.json()]==[ident]
