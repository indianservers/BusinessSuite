from datetime import datetime, timedelta, timezone
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE
from app.apps.project_management.models import PMSCalendarEvent


def event_payload(wid=None):
    return {'title':'Team sync','start_at':'2026-11-02T09:00:00+04:00','end_at':'2026-11-02T10:00:00+04:00','timezone':'Asia/Dubai','visibility':'workspace' if wid else 'private','workspace_id':wid,'meeting_url':'https://meet.example.com/room'}


def test_calendar_preferences_roundtrip_validation_and_user_isolation(client,db):
    wid,pid,owner,oh,ah,member,mh,guest,gh=setup_workspace(client,db)
    path=BASE+'/planner/preferences'
    first=client.get(path,headers=oh).json()
    assert first['revision']==0
    p=first['preferences'];p.update(timezone='Asia/Kolkata',week_start=1,grid_size='xl',default_project=pid)
    result=client.put(path,headers=oh,json={'revision':0,'preferences':p})
    assert result.status_code==200,result.text
    assert result.json()['revision']==1 and result.json()['preferences']['week_start']==1
    assert client.get(path,headers=mh).json()['revision']==0
    assert client.put(path,headers=oh,json={'revision':0,'preferences':p}).status_code==409
    for patch in [{'timezone':'Invalid/Zone'},{'duration':0},{'week_start':7},{'workdays':[p['workdays'][0]]*7},{'sections':[p['sections'][0]]*2}]:
        assert client.put(path,headers=oh,json={'revision':1,'preferences':{**p,**patch}}).status_code==422
    assert client.get(path).status_code in [401,403]


def test_calendar_event_visibility_owner_permissions_and_revision(client,db):
    wid,pid,owner,oh,ah,member,mh,guest,gh=setup_workspace(client,db)
    path=BASE+'/planner/events'
    personal=client.post(path,headers=oh,json=event_payload())
    assert personal.status_code==201,personal.text
    private=personal.json()
    assert private['start_at']=='2026-11-02T05:00:00+00:00'
    shared=client.post(path,headers=oh,json=event_payload(wid)).json()
    params={'start':'2026-11-01T00:00:00Z','end':'2026-11-04T00:00:00Z'}
    visible=client.get(path,headers=mh,params=params).json()
    assert [e['id'] for e in visible]==[shared['id']]
    assert not visible[0]['can_edit']
    assert client.put(path+f"/{shared['id']}",headers=mh,json={**event_payload(wid),'revision':1}).status_code==404
    assert client.delete(path+f"/{private['id']}?revision=1",headers=mh).status_code==404
    updated=client.put(path+f"/{private['id']}",headers=oh,json={**event_payload(),'revision':1,'title':'Updated'})
    assert updated.status_code==200 and updated.json()['revision']==2
    assert client.delete(path+f"/{private['id']}?revision=1",headers=oh).status_code==409
    assert client.delete(path+f"/{private['id']}?revision=2",headers=oh).status_code==204
    assert client.post(path,headers=gh,json=event_payload(wid)).status_code==403
    other=client.post(BASE+'/workspaces',headers=oh,json={'name':'Other calendar'}).json()['id']
    assert client.post(path,headers=mh,json=event_payload(other)).status_code==404
    assert len(client.get(path,headers=oh,params=params).json())==1


def test_calendar_event_validation_and_free_slots_exclude_busy(client,db):
    wid,pid,owner,oh,ah,member,mh,guest,gh=setup_workspace(client,db)
    path=BASE+'/planner/events'
    for patch in [{'title':' '},{'meeting_url':'javascript:alert(1)'},{'meeting_url':'https://user:secret@example.com/'},{'start_at':'2026-11-02T09:00:00'},{'end_at':'2026-11-02T08:00:00+04:00'},{'visibility':'workspace'},{'timezone':'bad'}]:
        assert client.post(path,headers=oh,json={**event_payload(),**patch}).status_code==422
    assert db.query(PMSCalendarEvent).count()==0
    p=client.get(BASE+'/planner/preferences',headers=oh).json()['preferences']
    p['timezone']='UTC'
    for w in p['workdays']:w['enabled']=True
    client.put(BASE+'/planner/preferences',headers=oh,json={'revision':0,'preferences':p})
    day=(datetime.now(timezone.utc)+timedelta(days=10)).date().isoformat()
    response=client.post(path,headers=oh,json={'title':'Busy','start_at':day+'T09:00:00Z','end_at':day+'T10:00:00Z'})
    assert response.status_code==201,response.text
    slots=client.get(BASE+'/planner/free-slots',headers=oh,params={'day':day,'minutes':60}).json()
    assert slots and slots[0]['start_at']==day+'T10:00:00+00:00'
    assert client.get(path,headers=oh,params={'start':'2026-01-01','end':'2026-12-01'}).status_code==422


def test_calendar_migrations_repeat_safe():
    from pathlib import Path
    from importlib.util import spec_from_file_location,module_from_spec
    from sqlalchemy import create_engine,inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        for table in ['users','pms_workspaces','pms_tasks']:connection.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
        for folder,prefix in [('alembic',''),('alembic_postgresql','pg_')]:
            file=Path(__file__).parents[1]/folder/'versions'/f'{prefix}20261024_004_planner_calendar.py'
            spec=spec_from_file_location('calendar_migration_'+prefix,file);module=module_from_spec(spec);spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):module.upgrade();module.upgrade()
        assert inspect(connection).has_table('pms_planner_preferences')
        assert inspect(connection).has_table('pms_calendar_events')
