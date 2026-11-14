import json
from uuid import uuid4
import pytest
from app.ai_operator import suite
from app.apps.project_management.models import PMSCalendarEvent,PMSProject
from tests.test_suite_operator import setup_suite,ROOT,approve,tick,prepare
from tests.test_suite_workspace import say
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from tests.rich_text_test_utils import organization_context


def setup(client,db):
    h,user,pid,_=setup_suite(client,db);wid=db.get(PMSProject,pid).workspace_id
    ident=client.post(ROOT+'/conversations',headers=h,json={'title':'Synthetic calendar actions','workspace_id':wid}).json()['id']
    return h,user,pid,wid,ident


def result(client,h,draft):return client.get(ROOT+f'/runs/{draft["id"]}',headers=h).json()


def params(**values):return {key:value for key,value in values.items() if value is not None}


def create(client,db,h,wid,chat):
    draft=say(client,h,chat,'PMS: Schedule meeting called Synthetic planning: start=2026-12-01T10:00+05:30; end=2026-12-01T11:00+05:30',module='PMS',workspace_id=wid)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    approve(client,h,draft);tick(client,db);done=result(client,h,draft)
    assert done['status']=='succeeded',done.get('error_code')
    return done,db.get(PMSCalendarEvent,done['receipts'][0]['record_id'])


def test_private_calendar_lifecycle_inline_and_natural_followups(client,db):
    h,user,pid,wid,chat=setup(client,db)
    missing=say(client,h,chat,'Schedule meeting called Synthetic planning',module='PMS',workspace_id=wid)
    assert missing['status']=='needs_clarification' and not db.query(PMSCalendarEvent).count()
    draft=say(client,h,chat,'start=2026-12-01T10:00+05:30; end=2026-12-01T11:00+05:30',module='PMS',workspace_id=wid)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    assert any(v['field']=='calendar_sync' for v in draft['result']['calendar_changes']['1']['changes'])
    inline=client.post(ROOT+f'/runs/{draft["id"]}/revise',headers=h,json={'request_key':str(uuid4()),'plan_hash':draft['plan_hash'],
        'changes':[{'step':1,'field':'title','value':'Inline planning'}]})
    assert inline.status_code==200,inline.text
    shortened=say(client,h,chat,'Make it 30 minutes',module='PMS',workspace_id=wid)
    assert shortened['plan']['steps'][0]['payload']['title']=='Inline planning'
    assert not db.query(PMSCalendarEvent).count()
    payload=shortened['plan']['steps'][0]['payload']
    assert client.post(ROOT+'/pms/calendar/create-approved',headers=h,json={**payload,'suite_run_id':shortened['id'],'suite_step':1}).status_code==403
    approve(client,h,shortened);tick(client,db);done=result(client,h,shortened)
    assert done['status']=='succeeded',done.get('error_code')
    row=db.get(PMSCalendarEvent,done['receipts'][0]['record_id'])
    assert row.owner_id==user.id and row.visibility=='private' and row.end_at-row.start_at==__import__('datetime').timedelta(minutes=30)
    assert done['result_cards'][0]['href'].startswith('/pms/calendar?date=2026-12-01&view=Week&q=')
    old=row.revision;approve(client,h,done);tick(client,db);db.refresh(row);assert row.revision==old
    edit=say(client,h,chat,'Edit that event: description=Synthetic agenda',module='PMS',workspace_id=wid)
    assert edit['status']=='awaiting_approval',edit.get('error_code')
    edit=say(client,h,chat,'Move it to 2026-12-01T12:00+05:30',module='PMS',workspace_id=wid)
    assert edit['status']=='awaiting_approval'
    approve(client,h,edit);tick(client,db);edited=result(client,h,edit)
    assert edited['status']=='succeeded',edited.get('error_code')
    db.refresh(row);assert row.description=='Synthetic agenda' and row.revision==2
    removal=say(client,h,chat,'Remove that event',module='PMS',workspace_id=wid)
    assert removal['status']=='awaiting_approval'
    approve(client,h,removal);tick(client,db);removed=result(client,h,removal)
    assert removed['status']=='succeeded',removed.get('error_code')
    assert db.get(PMSCalendarEvent,row.id) is None
    assert client.get(ROOT+f'/conversations/{chat}',headers=h).status_code==200


@pytest.mark.parametrize('action',['create','edit','remove'])
def test_calendar_lost_receipt_recovery_does_not_repeat_native_mutation(client,db,monkeypatch,action):
    h,user,pid,wid,chat=setup(client,db)
    if action=='create':draft=say(client,h,chat,'Create event called Recovery: start=2026-12-01T10:00Z; end=2026-12-01T11:00Z',module='PMS',workspace_id=wid)
    else:
        done,row=create(client,db,h,wid,chat)
        draft=say(client,h,chat,'Edit that event: title=Recovered title' if action=='edit' else 'Remove that event',module='PMS',workspace_id=wid)
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    approve(client,h,draft);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost calendar receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);stopped=result(client,h,draft)
    assert stopped['status']=='needs_reconciliation' and stopped['can_resume'],stopped.get('error_code')
    monkeypatch.setattr(suite,'finish_step',original)
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='succeeded'
    assert db.query(PMSCalendarEvent).count()==(0 if action=='remove' else 1)


def test_calendar_sync_effects_are_reviewed_and_changed_connections_stale_the_draft(client,db):
    from app.apps.crm.models import CRMCalendarIntegration
    h,user,pid,wid,chat=setup(client,db)
    draft=say(client,h,chat,'Create event called Bound sync: start=2026-12-01T10:00Z; end=2026-12-01T11:00Z',module='PMS',workspace_id=wid)
    assert draft['status']=='awaiting_approval'
    row=CRMCalendarIntegration(organization_id=1,user_id=user.id,provider='google',access_token_encrypted='synthetic-encrypted-placeholder',is_active=True)
    db.add(row);db.commit()
    response=client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code in {403,409}
    assert not db.query(PMSCalendarEvent).count()
    fresh=say(client,h,chat,'title=Reviewed sync',module='PMS',workspace_id=wid)
    assert fresh['status']=='awaiting_approval',fresh.get('error_code')
    effects=fresh['result']['calendar_changes']['1']['changes']
    assert any(f'connection #{row.id}' in str(change['after']) for change in effects if change['field']=='calendar_sync')
    assert 'synthetic-encrypted-placeholder' not in json.dumps(fresh)


def test_calendar_sources_and_stale_native_revision_enforce_ownership(client,db):
    from ai_test_utils import auth_headers
    h,user,pid,wid,chat=setup(client,db);done,row=create(client,db,h,wid,chat)
    source=client.get(ROOT+'/pms/calendar/event',headers=h,params=params(event_id=row.id,workspace_id=wid))
    assert source.status_code==200,source.text
    assert source.headers['cache-control']=='private, no-store'
    assert source.json()['revision']==1 and len(source.json()['source_sha256'])==64
    other,_=auth_headers(client,db,email=f'calendar-outsider-{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+'/pms/calendar/event',headers=other,params={'event_id':row.id}).status_code in {403,404}
    draft=say(client,h,chat,'Edit that event: title=Old source',module='PMS',workspace_id=wid)
    row.title='External edit';row.revision+=1;db.commit()
    assert client.post(ROOT+f'/runs/{draft["id"]}/approve',headers=h,json={'plan_hash':draft['plan_hash']}).status_code==409


def test_cloud_calendar_policy_read_keeps_hash_and_requires_review(client,db,monkeypatch):
    h,user,pid,wid,chat=setup(client,db)
    value=client.get(ROOT+'/pms/calendar/policy',headers=h).json()
    payload={'title':'Synthetic cloud event','start_at':'2026-12-01T10:00Z','end_at':'2026-12-01T11:00Z','workspace_id':wid,'sync_policy_sha256':value['sha256']}
    calls=mock_provider(monkeypatch,{'summary':'Review a native private event','steps':[{'tool':'pms.create_calendar_event','payload':payload}]})
    response=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','module':'PMS','workspace_id':wid,
        'text':'Prepare a private event using the selected authorized sync policy','context':[{'tool':'pms.calendar_policy'}]})
    assert response.status_code==200,response.text
    draft=response.json();assert draft['status']=='awaiting_approval',draft.get('error_code')
    outbound=json.loads(json.loads(calls[0].content)['contents'][0]['parts'][0]['text'])
    assert next(p['records'] for p in outbound['authorized_context'] if p['tool']=='pms.calendar_policy')['sha256']==value['sha256']
    assert not db.query(PMSCalendarEvent).count()


def test_calendar_policy_is_checked_again_after_approval(client,db):
    from app.apps.crm.models import CRMCalendarIntegration
    h,user,pid,wid,chat=setup(client,db)
    draft=say(client,h,chat,'Create event called Dispatch policy: start=2026-12-01T10:00Z; end=2026-12-01T11:00Z',module='PMS',workspace_id=wid)
    approve(client,h,draft)
    db.add(CRMCalendarIntegration(organization_id=1,user_id=user.id,provider='outlook',access_token_encrypted='synthetic-placeholder',is_active=True));db.commit()
    tick(client,db);stopped=result(client,h,draft)
    assert stopped['status'] in {'failed','paused','needs_reconciliation'}
    assert not db.query(PMSCalendarEvent).count()


def test_changed_committed_calendar_event_blocks_receipt_recovery(client,db,monkeypatch):
    h,user,pid,wid,chat=setup(client,db)
    draft=say(client,h,chat,'Create event called Changed receipt: start=2026-12-01T10:00Z; end=2026-12-01T11:00Z',module='PMS',workspace_id=wid)
    approve(client,h,draft);original=suite.finish_step
    def lost(*args,**kwargs):raise RuntimeError('Synthetic lost receipt')
    monkeypatch.setattr(suite,'finish_step',lost);tick(client,db);monkeypatch.setattr(suite,'finish_step',original)
    row=db.query(PMSCalendarEvent).one();row.title='Native later edit';row.revision+=1;db.commit()
    response=client.post(ROOT+f'/runs/{draft["id"]}/resume',headers=h,json={'plan_hash':draft['plan_hash']})
    assert response.status_code==409
    assert db.query(PMSCalendarEvent).count()==1


def test_shared_events_are_not_offered_as_private_action_targets(client,db):
    h,user,pid,wid,chat=setup(client,db)
    wid=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Synthetic shared calendar workspace'}).json()['id']
    value=client.post('/api/v1/project-management/planner/events',headers=h,json={'title':'Native shared event','start_at':'2026-12-01T10:00Z',
        'end_at':'2026-12-01T11:00Z','visibility':'workspace','workspace_id':wid})
    assert value.status_code==201,value.text
    ident=value.json()['id']
    assert client.get(ROOT+'/pms/calendar/event',headers=h,params={'event_id':ident,'workspace_id':wid}).status_code==404
    listed=client.get(ROOT+'/pms/calendar/events',headers=h,params={'start':'2026-12-01T00:00Z','end':'2026-12-02T00:00Z','workspace_id':wid})
    assert listed.status_code==200 and listed.json()['items']==[]


def test_large_native_calendar_description_is_preserved_without_widening_generic_inputs(client,db):
    from app.ai_agents.security import strict_input
    from fastapi import HTTPException
    h,user,pid,wid,chat=setup(client,db)
    native=client.post('/api/v1/project-management/planner/events',headers=h,json={'title':'Large calendar definition','description':'x'*9000,
        'start_at':'2026-12-01T10:00Z','end_at':'2026-12-01T11:00Z','workspace_id':wid})
    assert native.status_code==201,native.text
    source=client.get(ROOT+'/pms/calendar/event',headers=h,params=params(event_id=native.json()['id'],workspace_id=wid)).json()
    from app.apps.project_management.calendar_settings import EventInput
    payload={key:source[key] for key in EventInput.model_fields};payload.update(event_id=source['id'],revision=source['revision'],source_sha256=source['source_sha256'],sync_policy_sha256=source['sync_policy_sha256'],title='Reviewed large calendar')
    with pytest.raises(HTTPException):strict_input({'properties':{key:{} for key in payload}},payload)
    draft=prepare(client,h,[{'tool':'pms.edit_calendar_event','payload':payload}],module='PMS',workspace_id=wid,provider='local')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    approve(client,h,draft);tick(client,db);done=result(client,h,draft)
    assert done['status']=='succeeded',done.get('error_code')
    db.expire_all();assert db.get(PMSCalendarEvent,source['id']).description=='x'*9000


def test_workspace_calendar_target_scope_is_fixed_across_read_and_review(client,db):
    h,user,pid,wid,chat=setup(client,db)
    wid=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Synthetic event scope'}).json()['id']
    other=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Other event scope'}).json()['id']
    policy=client.get(ROOT+'/pms/calendar/policy',headers=h).json()
    payload={'title':'Workspace scoped private event','start_at':'2026-12-01T10:00Z','end_at':'2026-12-01T11:00Z','workspace_id':wid,'sync_policy_sha256':policy['sha256']}
    draft=prepare(client,h,[{'tool':'pms.create_calendar_event','payload':payload}],module='PMS',workspace_id=wid,provider='local')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    approve(client,h,draft);tick(client,db);done=result(client,h,draft);assert done['status']=='succeeded',done.get('error_code')
    ident=done['receipts'][0]['record_id']
    assert client.get(ROOT+'/pms/calendar/event',headers=h,params={'event_id':ident,'workspace_id':wid}).status_code==200
    assert client.get(ROOT+'/pms/calendar/event',headers=h,params={'event_id':ident,'workspace_id':other}).status_code==403
    denied=prepare(client,h,[{'tool':'pms.create_calendar_event','payload':payload}],module='PMS',workspace_id=other,provider='local')
    assert denied['status']!='awaiting_approval'


def test_calendar_same_target_and_unresolved_id_chains_fail_before_writes(client,db):
    h,user,pid,wid,chat=setup(client,db)
    value=client.get(ROOT+'/pms/calendar/policy',headers=h).json()
    payload={'title':'Created step','start_at':'2026-12-01T10:00Z','end_at':'2026-12-01T11:00Z','sync_policy_sha256':value['sha256']}
    removal={'event_id':{'$step':1,'field':'id'},'revision':1,'source_sha256':'a'*64,'sync_policy_sha256':value['sha256']}
    draft=prepare(client,h,[{'tool':'pms.create_calendar_event','payload':payload},{'tool':'pms.remove_calendar_event','payload':removal}],module='PMS',workspace_id=wid,provider='local')
    assert draft['status']!='awaiting_approval' and not db.query(PMSCalendarEvent).count()


def test_calendar_edit_cannot_silently_default_an_omitted_native_field(client,db):
    h,user,pid,wid,chat=setup(client,db);done,row=create(client,db,h,wid,chat)
    source=client.get(ROOT+'/pms/calendar/event',headers=h,params=params(event_id=row.id,workspace_id=wid)).json()
    from app.apps.project_management.calendar_settings import EventInput
    from app.ai_operator.suite_tools import payload_schema,TOOLS
    assert set(EventInput.model_fields).issubset(payload_schema(TOOLS['pms.edit_calendar_event'])['required'])
    payload={key:source[key] for key in EventInput.model_fields if key!='description'}
    payload.update(event_id=row.id,revision=source['revision'],source_sha256=source['source_sha256'],sync_policy_sha256=source['sync_policy_sha256'],title='Missing definition field')
    draft=prepare(client,h,[{'tool':'pms.edit_calendar_event','payload':payload}],module='PMS',workspace_id=wid,provider='local')
    assert draft['status']!='awaiting_approval'
    db.refresh(row);assert row.revision==1 and row.title=='Synthetic planning'


def test_natural_calendar_time_is_resolved_in_request_timezone_before_review(client,db):
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    h,user,pid,wid,chat=setup(client,db)
    draft=say(client,h,chat,'Schedule a meeting called Stand-up tomorrow at 10:30 am for 30 minutes',module='PMS',workspace_id=wid,timezone='Asia/Kolkata')
    assert draft['status']=='awaiting_approval',draft.get('error_code')
    payload=draft['plan']['steps'][0]['payload'];start=datetime.fromisoformat(payload['start_at']);end=datetime.fromisoformat(payload['end_at'])
    assert payload['title']=='Stand-up' and start.hour==10 and start.minute==30
    assert start.date()==datetime.now(ZoneInfo('Asia/Kolkata')).date()+timedelta(days=1)
    assert end-start==timedelta(minutes=30) and payload['timezone']=='Asia/Kolkata'
    assert not db.query(PMSCalendarEvent).count()


@pytest.mark.parametrize('day,clock',[('2027-03-14','2:30 am'),('2027-11-07','1:30 am')])
def test_ambiguous_or_nonexistent_local_calendar_times_require_clarification(client,db,day,clock):
    h,user,pid,wid,chat=setup(client,db)
    draft=say(client,h,chat,f'Schedule a meeting called Clock change {day} at {clock} for 30 minutes',module='PMS',workspace_id=wid,timezone='America/New_York')
    assert draft['status']=='needs_clarification'
    assert 'explicit' in draft['plan']['question'].lower() and not db.query(PMSCalendarEvent).count()
