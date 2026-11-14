"""Native time operations can share an agent checkpoint transaction."""
from datetime import date
import pytest
from fastapi import HTTPException
from app.apps.project_management.api.router import (
    create_time_log_operation,update_time_log_operation,delete_time_log_operation,
)
from app.apps.project_management.models import PMSTimeLog,PMSActivity,PMSTimesheet
from app.apps.project_management.schemas import PMSTimeLogCreate,PMSTimeLogUpdate
from tests.test_suite_operator import setup_suite
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def entry(pid,task):
    return PMSTimeLogCreate(project_id=pid,task_id=task,log_date=date(2026,5,4),duration_minutes=45,
        description='Synthetic time operation',is_billable=False)


def test_time_log_and_native_activity_roll_back_together(client,db):
    h,user,pid,task=setup_suite(client,db)
    row=create_time_log_operation(entry(pid,task),db,user,commit=False);ident=row.id
    assert db.query(PMSActivity).filter_by(entity_type='time_log',entity_id=ident,action='time.logged').count()==1
    db.rollback()
    assert db.get(PMSTimeLog,ident) is None
    assert db.query(PMSActivity).filter_by(entity_type='time_log',entity_id=ident).count()==0


def test_native_time_edit_and_remove_respect_callers_transaction(client,db):
    h,user,pid,task=setup_suite(client,db)
    row=create_time_log_operation(entry(pid,task),db,user);ident=row.id
    update_time_log_operation(ident,PMSTimeLogUpdate(duration_minutes=70),db,user,commit=False)
    assert db.get(PMSTimeLog,ident).duration_minutes==70
    db.rollback()
    assert db.get(PMSTimeLog,ident).duration_minutes==45
    assert db.query(PMSActivity).filter_by(entity_type='time_log',entity_id=ident,action='time.updated').count()==0
    delete_time_log_operation(ident,db,user,commit=False)
    assert db.get(PMSTimeLog,ident) is None
    db.rollback()
    assert db.get(PMSTimeLog,ident).duration_minutes==45
    assert db.query(PMSActivity).filter_by(entity_type='time_log',entity_id=ident,action='time.deleted').count()==0
    delete_time_log_operation(ident,db,user)
    assert db.get(PMSTimeLog,ident) is None


@pytest.mark.parametrize('status',['submitted','approved'])
def test_atomic_time_operations_retain_submitted_timesheet_lock(client,db,status):
    h,user,pid,task=setup_suite(client,db)
    row=create_time_log_operation(entry(pid,task),db,user)
    sheet=PMSTimesheet(organization_id=1,user_id=user.id,week_start_date=date(2026,5,4),status=status)
    db.add(sheet);db.flush();row.timesheet_id=sheet.id;db.commit();ident=row.id
    for operation in (lambda:update_time_log_operation(ident,PMSTimeLogUpdate(duration_minutes=70),db,user,commit=False),
                      lambda:delete_time_log_operation(ident,db,user,commit=False)):
        with pytest.raises(HTTPException) as failure:operation()
        assert failure.value.status_code==400
        db.rollback()
    assert db.get(PMSTimeLog,ident).duration_minutes==45


def test_time_log_native_http_contract_and_task_override_preserved(client,db):
    h,user,pid,task=setup_suite(client,db)
    body=entry(pid,task).model_dump(mode='json')
    created=client.post('/api/v1/project-management/time-logs',headers=h,json=body)
    assert created.status_code==200,created.text
    ident=created.json()['id']
    task_entry=client.post(f'/api/v1/project-management/tasks/{task}/time-logs',headers=h,json={**body,'task_id':None})
    assert task_entry.status_code==201,task_entry.text
    assert task_entry.json()['task_id']==task
    updated=client.patch(f'/api/v1/project-management/time-logs/{ident}',headers=h,json={'duration_minutes':60})
    assert updated.status_code==200 and updated.json()['duration_minutes']==60
    removed=client.delete(f'/api/v1/project-management/time-logs/{ident}',headers=h)
    assert removed.status_code==200 and removed.json()=={'message':'Time log deleted'}


def test_shared_time_operations_do_not_grant_outsider_writes(client,db):
    from ai_test_utils import auth_headers
    from uuid import uuid4
    h,user,pid,task=setup_suite(client,db)
    row=create_time_log_operation(entry(pid,task),db,user);ident=row.id
    other,actor=auth_headers(client,db,email=f'time-outsider-{uuid4()}@example.com',permissions=['pms_view'])
    for operation in (lambda:create_time_log_operation(entry(pid,task),db,actor,commit=False),
                      lambda:update_time_log_operation(ident,PMSTimeLogUpdate(duration_minutes=70),db,actor,commit=False),
                      lambda:delete_time_log_operation(ident,db,actor,commit=False)):
        with pytest.raises(HTTPException) as failure:operation()
        assert failure.value.status_code in {403,404}
        db.rollback()
    assert db.get(PMSTimeLog,ident).duration_minutes==45
