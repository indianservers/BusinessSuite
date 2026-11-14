"""Capacity changes must invalidate reviewed plans, including after approval."""
from datetime import date
from uuid import uuid4

import pytest
from app.ai_operator.jobs import process_batch
from app.ai_operator.models import OperatorRun
from app.apps.project_management.models import PMSUserCapacity, PMSTask
from tests.test_workload_intelligence import setup_load
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context

ROOT = '/api/v1/ai-operator'


def prepare(client, db):
    h, user, pid, _, _, task = setup_load(client, db)
    source = client.get(ROOT+f'/suite/pms/workload/{pid}', headers=h,
                        params={'start': '2026-05-04'}).json()
    payload = {'project_id': pid, 'request_key': str(uuid4()),
               'workload_guard': source['workload_guard'],
               'plan': {'summary': 'Review capacity before raising priority', 'steps': [
                   {'tool': 'update_task', 'task_id': task, 'changes': {'priority': 'Urgent'}}]}}
    response = client.post(ROOT+'/workbench/plans/preview', headers=h, json=payload)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run['workload_guard'] == source['workload_guard']
    return h, user, task, run


def approve(client, h, run):
    return client.post(ROOT+f'/runs/{run["id"]}/approve', headers=h,
                       json={'plan_hash': run['plan_hash']})


def change_capacity(db, user):
    capacity = db.query(PMSUserCapacity).filter_by(user_id=user.id,
        week_start_date=date(2026, 5, 4)).one()
    capacity.capacity_hours = 5
    db.commit()


def test_guarded_plan_executes_and_replays_without_duplicate_writes(client, db):
    h, user, task, run = prepare(client, db)
    response = approve(client, h, run)
    assert response.status_code == 200, response.text
    process_batch(db, run_ids=[run['id']], include_schedulers=False)
    db.expire_all()
    assert db.get(OperatorRun, run['id']).status == 'succeeded'
    assert db.get(PMSTask, task).priority == 'Urgent'
    change_capacity(db, user)
    assert approve(client, h, run).status_code == 200


@pytest.mark.parametrize('after_approval', [False, True])
def test_capacity_change_blocks_stale_plan_without_task_writes(client, db, after_approval):
    h, user, task, run = prepare(client, db)
    original = db.get(PMSTask, task).priority
    if after_approval:
        response = approve(client, h, run)
        assert response.status_code == 200, response.text
    change_capacity(db, user)
    if after_approval:
        process_batch(db, run_ids=[run['id']], include_schedulers=False)
        db.expire_all()
        row = db.get(OperatorRun, run['id'])
        assert row.status == 'paused' and row.error_code == 'STALE_PLAN'
        resumed = client.post(ROOT+f'/runs/{run["id"]}/resume', headers=h,
            json={'plan_hash': run['plan_hash']})
        assert resumed.status_code == 409, resumed.text
    else:
        response = approve(client, h, run)
        assert response.status_code == 409, response.text
    db.expire_all()
    assert db.get(PMSTask, task).priority == original


def test_removed_guard_cannot_bypass_sealed_approval(client, db):
    h, _, task, run = prepare(client, db)
    row = db.get(OperatorRun, run['id'])
    row.snapshots = {k: v for k, v in row.snapshots.items() if k != '__workload_guard__'}
    db.commit()
    response = approve(client, h, run)
    assert response.status_code == 409, response.text


def test_guard_covers_unselected_work_and_is_independent_of_detail_paging(client, db):
    from tests.test_workload_intelligence import task as create_task
    h, user, task, run = prepare(client, db)
    pid = db.get(OperatorRun, run['id']).project_id
    # The guard represents the full source even when no people remain on this page.
    empty = client.get(ROOT+f'/suite/pms/workload/{pid}', headers=h,
        params={'start': '2026-05-04', 'after_user_id': 9223372036854775807})
    assert empty.status_code == 200, empty.text
    assert empty.json()['rows'] == []
    assert empty.json()['workload_guard'] == run['workload_guard']
    original = db.get(PMSTask, task).priority
    create_task(client, h, pid, user.id, 'Unselected additional load', 8)
    response = approve(client, h, run)
    assert response.status_code == 409, response.text
    db.expire_all()
    assert db.get(PMSTask, task).priority == original
