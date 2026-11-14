from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.apps.project_management.timers import (
    StartInput,StopInput,start_timer_operation,stop_timer_operation,discard_timer_operation,
)
from app.apps.project_management.models import PMSRunningTimer,PMSTimeLog,PMSActivity,PMSTask
from tests.test_suite_operator import setup_suite
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def test_native_timer_start_stop_and_activity_obey_shared_transaction(client,db):
    h,user,pid,task=setup_suite(client,db);uid=user.id
    data=StartInput(project_id=pid,task_id=task,session_key=uuid4(),description='Synthetic timer')
    start_timer_operation(data,db,user,commit=False)
    assert db.get(PMSRunningTimer,uid).active
    db.rollback();assert db.get(PMSRunningTimer,uid) is None
    start_timer_operation(data,db,user)
    stopped=stop_timer_operation(StopInput(session_key=data.session_key),db,user,commit=False);ident=stopped['log_id']
    assert not db.get(PMSRunningTimer,uid).active and db.get(PMSTimeLog,ident).approval_status=='Pending'
    assert db.query(PMSActivity).filter_by(action='time.logged',entity_id=ident,entity_type='time_log').count()==1
    db.rollback()
    assert db.get(PMSRunningTimer,uid).active and db.get(PMSTimeLog,ident) is None
    assert db.query(PMSActivity).filter_by(action='time.logged',entity_id=ident,entity_type='time_log').count()==0
    final=stop_timer_operation(StopInput(session_key=data.session_key),db,user)
    replay=stop_timer_operation(StopInput(session_key=data.session_key),db,user)
    assert final['log_id']==replay['log_id'] and db.query(PMSTimeLog).count()==1


@pytest.mark.parametrize('change',[{'description':'Different intent'},{'is_billable':True},{'task_id':None},{'timezone':'Asia/Kolkata'}])
def test_timer_session_key_is_bound_to_original_inputs(client,db,change):
    h,user,pid,task=setup_suite(client,db)
    data=StartInput(project_id=pid,task_id=task,session_key=uuid4(),description='Synthetic timer')
    first=start_timer_operation(data,db,user)
    assert start_timer_operation(data,db,user)['session_key']==first['session_key']
    with pytest.raises(HTTPException) as failure:start_timer_operation(data.model_copy(update=change),db,user)
    assert failure.value.status_code==409
    assert db.query(PMSTimeLog).count()==0


def test_discard_rollback_and_stop_do_not_invent_a_recorded_entry(client,db):
    h,user,pid,task=setup_suite(client,db)
    data=StartInput(project_id=pid,session_key=uuid4());start_timer_operation(data,db,user)
    discard_timer_operation(StopInput(session_key=data.session_key),db,user,commit=False)
    db.rollback();assert db.get(PMSRunningTimer,user.id).active
    discard_timer_operation(StopInput(session_key=data.session_key),db,user)
    with pytest.raises(HTTPException) as failure:stop_timer_operation(StopInput(session_key=data.session_key),db,user)
    assert failure.value.status_code==409 and db.query(PMSTimeLog).count()==0


def test_timer_task_reparenting_cannot_create_mismatched_time_log(client,db):
    h,user,pid,task=setup_suite(client,db)
    data=StartInput(project_id=pid,task_id=task,session_key=uuid4());start_timer_operation(data,db,user)
    created=client.post('/api/v1/project-management/projects',headers=h,json={'name':'Synthetic timer destination','project_key':'TM-'+uuid4().hex[:8]})
    assert created.status_code==200,created.text
    db.get(PMSTask,task).project_id=created.json()['id'];db.commit()
    with pytest.raises(HTTPException) as failure:stop_timer_operation(StopInput(session_key=data.session_key),db,user)
    assert failure.value.status_code==409 and db.query(PMSTimeLog).count()==0


def test_native_timer_http_contract_and_invalid_task_ids(client,db):
    h,user,pid,task=setup_suite(client,db);key=str(uuid4())
    body={'project_id':pid,'task_id':task,'session_key':key,'description':'Synthetic native timer','is_billable':False}
    started=client.post('/api/v1/project-management/timer/start',headers=h,json=body)
    assert started.status_code==200 and started.json()['active'] is True
    assert client.get('/api/v1/project-management/timer',headers=h).json()['session_key']==key
    stopped=client.post('/api/v1/project-management/timer/stop',headers=h,json={'session_key':key})
    assert stopped.status_code==200 and stopped.json()['log_id'] and stopped.json()['duration_minutes']>=1
    assert client.get('/api/v1/project-management/timer',headers=h).json() is None
    invalid=client.post('/api/v1/project-management/timer/start',headers=h,json={**body,'session_key':str(uuid4()),'task_id':0})
    assert invalid.status_code==422


def test_timer_stop_refreshes_stale_session_state_before_creating_a_log(client,db):
    from sqlalchemy.orm import Session
    h,user,pid,task=setup_suite(client,db)
    data=StartInput(project_id=pid,session_key=uuid4());start_timer_operation(data,db,user)
    cached=db.get(PMSRunningTimer,user.id);assert cached.active
    with Session(bind=db.get_bind()) as other_db:
        stopped=stop_timer_operation(StopInput(session_key=data.session_key),other_db,user)
    assert cached.active  # The first Session still holds the pre-stop ORM object.
    replay=stop_timer_operation(StopInput(session_key=data.session_key),db,user)
    assert replay['log_id']==stopped['log_id'] and db.query(PMSTimeLog).count()==1


def test_inactive_owner_timer_in_another_company_can_be_reused_without_pk_conflict(client,db):
    from datetime import datetime,timezone
    from app.models.company import Company
    from app.apps.project_management.models import PMSProject
    from app.ai_operator.timer_actions import state
    from app.ai_operator.service import digest
    h,user,pid,task=setup_suite(client,db)
    company=Company(name='Synthetic other timer company');db.add(company);db.flush()
    foreign=PMSProject(name='Synthetic old timer scope',project_key='OLD-'+uuid4().hex[:8],organization_id=company.id)
    db.add(foreign);db.flush()
    old=PMSRunningTimer(user_id=user.id,project_id=foreign.id,session_key=str(uuid4()),active=False,started_at=datetime.now(timezone.utc))
    db.add(old);db.commit();original_hash=digest(state(old))
    source=client.get('/api/v1/ai-operator/suite/pms/timer/'+str(pid),headers=h)
    assert source.status_code==200,source.text
    assert source.json()['source_sha256']==original_hash and source.json()['active'] is False
    assert 'Synthetic old timer scope' not in source.text
    response=client.post('/api/v1/project-management/timer/start',headers=h,json={'project_id':pid,'session_key':str(uuid4())})
    assert response.status_code==200,response.text
    db.expire_all();assert db.query(PMSRunningTimer).count()==1 and db.get(PMSRunningTimer,user.id).project_id==pid


def test_active_owner_timer_outside_company_is_not_disclosed_or_recorded(client,db):
    from datetime import datetime,timezone
    from app.models.company import Company
    from app.apps.project_management.models import PMSProject
    h,user,pid,task=setup_suite(client,db)
    company=Company(name='Synthetic foreign active timer company');db.add(company);db.flush()
    foreign=PMSProject(name='Synthetic inaccessible active timer',project_key='FA-'+uuid4().hex[:8],organization_id=company.id)
    db.add(foreign);db.flush();key=str(uuid4())
    db.add(PMSRunningTimer(user_id=user.id,project_id=foreign.id,session_key=key,active=True,description='Must stay private to authorized scope',started_at=datetime.now(timezone.utc)));db.commit()
    response=client.get('/api/v1/project-management/timer',headers=h)
    assert response.status_code in {403,404}
    assert 'Must stay private' not in response.text
    for action in ('stop','discard'):
        response=client.post('/api/v1/project-management/timer/'+action,headers=h,json={'session_key':key})
        assert response.status_code in {403,404},response.text
    source=client.get('/api/v1/ai-operator/suite/pms/timer/'+str(pid),headers=h)
    assert source.status_code==409 and 'Must stay private' not in source.text
    db.expire_all();assert db.get(PMSRunningTimer,user.id).active and not db.query(PMSTimeLog).count()
