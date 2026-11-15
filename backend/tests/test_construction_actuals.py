"""Genuine native Construction completion and dated project actual costs."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.business_packs import construction_actuals as actuals
from app.apps.project_management.models import (PMSProject, PMSTask, PMSWorkspace,
    PMSChecklistItem, PMSTaskUpdateEntry, PMSBoard, PMSBoardColumn, PMSWorkspaceEntry)
from app.apps.srm.industry_models import IndustryRecord
from tests.test_construction_planning import site_plan, selected, own
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_construction_controls import controls


@pytest.fixture
def actual_site(db, site_plan):
    case, ids, edge = site_plan
    workspace = db.get(PMSWorkspace, db.get(PMSProject, case[3]).workspace_id)
    own(db, case, workspace); db.commit()
    return case, ids


def task_input(db, task_id, **values):
    return actuals.TaskActualInput(request_id=uuid4(), expected_updated_at=db.get(PMSTask, task_id).updated_at, **values)


def test_native_complete_hours_retry_and_stale(db, actual_site):
    case, ids = actual_site
    data = task_input(db, ids[0], status='Done', actual_hours=Decimal('9.5'))
    with selected(db, case) as actor:
        result = actuals.task_actual(case[3], ids[0], data, db, actor)
        assert result['status'] == 'Done' and result['completed_at']
        assert float(result['actual_hours']) == 9.5
        assert actuals.task_actual(case[3], ids[0], data, db, actor) == result
        with pytest.raises(HTTPException) as stale:
            actuals.task_actual(case[3], ids[0], data.model_copy(update={'request_id': uuid4()}), db, actor)
        assert stale.value.status_code == 409
    assert db.get(PMSTask, ids[0]).status == 'Done'
    assert db.query(IndustryRecord).filter_by(kind='task_actual', project_id=case[3]).count() == 1


def test_native_completion_blocks_checklists_and_open_children(db, actual_site):
    case, ids = actual_site
    db.get(PMSTask, ids[1]).parent_task_id = ids[0]
    check = PMSChecklistItem(task_id=ids[0], title='Required inspection', is_completed=False)
    db.add(check); db.flush(); own(db, case, check); db.commit()
    data = task_input(db, ids[0], status='Done')
    with selected(db, case) as actor:
        with pytest.raises(HTTPException) as incomplete:
            actuals.task_actual(case[3], ids[0], data, db, actor)
        assert incomplete.value.status_code == 409
        assert 'checklist' in incomplete.value.detail.lower()
    assert db.get(PMSTask, ids[0]).status == 'To Do'


def test_cost_dates_currency_partial_revisions_and_no_ledger(db, actual_site):
    case, _ = actual_site
    make = lambda **values: actuals.CostActualInput(request_id=uuid4(), expected_actual_cost=None,
        cumulative_actual_cost=125, currency='INR', as_of=date.today()-timedelta(days=1), reason='Certified supplier and labour costs', **values)
    data = make()
    with selected(db, case) as actor:
        result = actuals.cost_actual(case[3], data, db, actor)
        assert float(result['actual_cost']) == 125
        assert actuals.cost_actual(case[3], data, db, actor) == result
        for changed in ({'currency': 'USD'}, {'as_of': data.as_of}, {'expected_actual_cost': 0}):
            payload = data.model_copy(update={'request_id': uuid4(), 'expected_actual_cost': Decimal(125),
                'cumulative_actual_cost': Decimal(200), 'as_of': date.today(), **changed})
            with pytest.raises(HTTPException) as denied:
                actuals.cost_actual(case[3], payload, db, actor)
            assert denied.value.status_code == 409
        final = actuals.cost_actual(case[3], data.model_copy(update={'request_id': uuid4(), 'expected_actual_cost': Decimal(125),
            'cumulative_actual_cost': Decimal(200), 'as_of': date.today()}), db, actor)
        assert float(final['actual_cost']) == 200
    rows = db.query(IndustryRecord).filter_by(project_id=case[3], kind='cost_actual').all()
    assert len(rows) == 2 and rows[0].data['source_before'] is None


def test_native_manual_progress_evidence_revision_failure_and_retry(db, actual_site):
    from app.business_packs.construction_planning import task_sources
    case, ids = actual_site
    data = task_input(db, ids[0], progress=35, progress_revision=0, progress_note='Foundation work inspected on site')
    with selected(db, case) as actor:
        first = actuals.task_actual(case[3], ids[0], data, db, actor)
        assert first['progress'] == 35 and first['progress_revision'] == 1
        source = next(row for row in task_sources(db, actor, case[3]) if row['id'] == ids[0])
        assert source['progress_percent'] == 35 and source['progress_revision'] == 1
        stale = data.model_copy(update={'request_id': uuid4(), 'expected_updated_at': source['updated_at'], 'progress': 60})
        with pytest.raises(HTTPException) as denied:
            actuals.task_actual(case[3], ids[0], stale, db, actor)
        assert denied.value.status_code == 409
        retry = stale.model_copy(update={'progress_revision': 1})
        assert actuals.task_actual(case[3], ids[0], retry, db, actor)['progress_revision'] == 2
    evidence = db.query(PMSTaskUpdateEntry).filter_by(task_id=ids[0], kind='update').all()
    assert len(evidence) == 2 and all(row.body and row.progress for row in evidence)


def test_actuals_public_http_and_specialist_denial(client, db, actual_site, catalog):
    from tests.test_business_pack_http_integration import grant
    from fastapi.encoders import jsonable_encoder
    case, ids = actual_site
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(case[2])}
    path = f'/api/v1/srm/industry/projects/{case[3]}'
    payload = jsonable_encoder(task_input(db, ids[0], status='Done', actual_hours=Decimal(8)))
    done = client.post(path + f'/task-actuals/{ids[0]}', headers=headers, json=payload)
    assert done.status_code == 200, done.text
    assert done.json()['completed_at']
    for pack, role in (('hospital', 'doctor'), ('restaurant', 'chef')):
        context, _ = grant(db, case[0], case[1], pack, role)
        specialist = {**headers, 'X-Suite-Pack-Context': str(context.id)}
        denied = client.post(path + f'/task-actuals/{ids[1]}', headers=specialist, json=payload)
        assert denied.status_code == 403, denied.text


def test_native_workflow_and_capacity_are_retained(db, actual_site):
    import json
    case, ids = actual_site
    project = db.get(PMSProject, case[3])
    board = PMSBoard(project_id=case[3], name='Site board', board_type='Kanban')
    db.add(board); db.flush(); own(db, case, board)
    column = PMSBoardColumn(board_id=board.id, name='Done', status_key='DONE', wip_limit=1, position=0)
    db.add(column); db.flush(); own(db, case, column)
    db.get(PMSTask, ids[1]).status = 'Done'
    config = PMSWorkspaceEntry(workspace_id=project.workspace_id, author_id=case[0].id, kind=f'wf{case[3]:x}',
        body=json.dumps({'revision':1,'enabled':True,'transitions':[{'source':'To Do','target':'In Progress','required_fields':[],'approval_user_ids':[]}]}))
    db.add(config); db.flush(); own(db, case, config); db.commit()
    data = task_input(db, ids[0], status='Done')
    with selected(db, case) as actor, pytest.raises(HTTPException) as workflow:
        actuals.task_actual(case[3], ids[0], data, db, actor)
    assert workflow.value.status_code == 409 and 'workflow' in workflow.value.detail
    config.body = json.dumps({'revision':2,'enabled':False,'transitions':[]})
    db.commit()
    with selected(db, case) as actor, pytest.raises(HTTPException) as capacity:
        actuals.task_actual(case[3], ids[0], data, db, actor)
    assert capacity.value.status_code == 409 and 'capacity' in capacity.value.detail
    assert db.get(PMSTask, ids[0]).status == 'To Do'


def test_native_late_failure_rolls_back_then_same_command_retries(db, actual_site, monkeypatch):
    from app.apps.project_management.api import router as native
    case, ids = actual_site
    data = task_input(db, ids[0], status='Done')
    original = native.update_task_operation
    def fail_after_native(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(409, 'Native completion failed before commit')
    with selected(db, case) as actor:
        with monkeypatch.context() as patch:
            patch.setattr(native, 'update_task_operation', fail_after_native)
            with pytest.raises(HTTPException) as failed:
                actuals.task_actual(case[3], ids[0], data, db, actor)
            assert failed.value.status_code == 409
        assert actuals.task_actual(case[3], ids[0], data, db, actor)['status'] == 'Done'
    assert db.query(IndustryRecord).filter_by(project_id=case[3], kind='task_actual').count() == 1


def test_project_membership_cannot_replace_fresh_native_edit_and_sales_write(db, actual_site):
    from tests.test_construction_site_workflows import native_member
    case, ids = actual_site
    _, manager = native_member(db, case[1], case[2], case[3], 'Manager')
    data = task_input(db, ids[0], status='Done')
    with selected(db, case, manager), pytest.raises(HTTPException) as denied:
        actuals.task_actual(case[3], ids[0], data, db, manager)
    assert denied.value.status_code == 403
    assert db.get(PMSTask, ids[0]).status == 'To Do'


def test_cost_budget_exact_token_replay_stale_and_native_failure_retry(db, actual_site, monkeypatch):
    from app.apps.project_management.api import router as native
    case, _ = actual_site
    source = db.get(PMSProject, case[3])
    old_actual, old_estimated = source.actual_cost, source.estimated_cost
    data = actuals.CostBudgetInput(request_id=uuid4(), expected_estimated_cost=old_estimated,
        estimated_cost=1200, reason='Approved additional concrete scope cost estimate')
    original = native.update_project_operation
    def fail_after_native(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(409, 'Native budget activity failed before commit')
    with selected(db, case) as actor:
        with monkeypatch.context() as patch:
            patch.setattr(native, 'update_project_operation', fail_after_native)
            with pytest.raises(HTTPException) as failed:
                actuals.cost_budget(case[3], data, db, actor)
            assert failed.value.status_code == 409
        result = actuals.cost_budget(case[3], data, db, actor)
        assert Decimal(str(result['estimated_cost'])) == 1200
        assert actuals.cost_budget(case[3], data, db, actor) == result
        with pytest.raises(HTTPException) as stale:
            actuals.cost_budget(case[3], data.model_copy(update={'request_id': uuid4(), 'estimated_cost': Decimal(1400)}), db, actor)
        assert stale.value.status_code == 409
    db.expire_all()
    assert db.get(PMSProject, case[3]).actual_cost == old_actual
    history = db.query(IndustryRecord).filter_by(project_id=case[3], kind='cost_budget').all()
    assert len(history) == 1 and Decimal(history[0].data['source_after']) == 1200
    assert history[0].data['reason'] == data.reason


def test_budget_change_keeps_old_baseline_and_requires_new_allocations_approval(client, db, controls):
    from tests.test_construction_controls import prepare, approve, ROOT
    case = controls
    project = db.get(PMSProject, case['case'][3])
    own(db, case['case'], db.get(PMSWorkspace, project.workspace_id)); db.commit()
    baseline = approve(client, case, prepare(client, case))
    path = ROOT + f'/projects/{project.id}'
    change = client.post(path + '/cost-budget', headers=case['headers'], json={
        'request_id': str(uuid4()), 'expected_estimated_cost': '1000', 'estimated_cost': '1200',
        'reason': 'Additional approved work increases actual cost budget'})
    assert change.status_code == 200, change.text
    stale = client.get(path + '/performance', headers=case['headers'], params={'baseline_id': baseline['id'], 'as_of': date.today().isoformat()})
    assert stale.status_code == 409, stale.text
    unchanged = db.get(IndustryRecord, baseline['id'])
    assert Decimal(unchanged.data['budget_at_completion']) == 1000
    assert unchanged.status == 'approved'
    mismatch = client.post(ROOT + '/planning-baselines', headers=case['headers'], json={
        'request_id': str(uuid4()), 'title': 'New budget requires allocations', 'project_id': project.id,
        'native_baseline_id': case['native_baseline']['id']})
    assert mismatch.status_code == 409, mismatch.text


def test_cost_budget_public_specialists_denied_and_nonmoney_fields_rejected(client, db, actual_site, catalog):
    from tests.test_business_pack_http_integration import grant
    from pydantic import ValidationError
    case, _ = actual_site
    payload = {'request_id': str(uuid4()), 'expected_estimated_cost': None, 'estimated_cost': '1200', 'reason': 'Revised site cost budget'}
    for pack, role in (('hospital', 'doctor'), ('restaurant', 'chef')):
        context, _ = grant(db, case[0], case[1], pack, role)
        headers = {**catalog[0], 'X-Suite-Pack-Context': str(context.id)}
        response = client.post(f'/api/v1/srm/industry/projects/{case[3]}/cost-budget', headers=headers, json=payload)
        assert response.status_code == 403, response.text
    with pytest.raises(ValidationError):
        actuals.CostBudgetInput(**payload, budget_amount=1200)
    with pytest.raises(ValidationError):
        actuals.CostBudgetInput(**{**payload, 'estimated_cost': 0})


def test_planning_cost_budget_does_not_require_invoice_money_permission(db, actual_site):
    from app.access.models import AccessPolicy
    from app.models.user import Permission
    from app.apps.project_management.models import PMSWorkspaceMember
    from tests.test_construction_site_workflows import native_member
    case, _ = actual_site
    _, manager = native_member(db, case[1], case[2], case[3], 'Manager')
    project = db.get(PMSProject, case[3])
    db.add(PMSWorkspaceMember(workspace_id=project.workspace_id, user_id=manager.id, role='Admin'))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=manager.id).one()
    policy.grants = {**policy.grants, 'srm': {'enabled':True,'permissions':['srm_manage'],
        'actions':['view','create','edit'],'scope':'organization'}}
    if db.query(Permission).filter_by(name='srm_manage').first() is None:
        db.add(Permission(name='srm_manage', module='srm', description='Native Sales management'))
    db.commit()
    budget = actuals.CostBudgetInput(request_id=uuid4(), expected_estimated_cost=project.estimated_cost,
        estimated_cost=1200, reason='Planning estimate revised by site project manager')
    with selected(db, case, manager):
        assert Decimal(str(actuals.cost_budget(case[3], budget, db, manager)['estimated_cost'])) == 1200
        with pytest.raises(HTTPException) as financial:
            actuals.cost_actual(case[3], actuals.CostActualInput(request_id=uuid4(), expected_actual_cost=None,
                cumulative_actual_cost=100, currency='INR', as_of=date.today(), reason='Financial actual'), db, manager)
        assert financial.value.status_code == 403


@pytest.mark.parametrize('revocation', ['workspace', 'completion_config'])
def test_outer_release_rechecks_actual_workspace_and_completion_lease(db, actual_site, revocation):
    from sqlalchemy import delete, event, update
    from app.branches.models import BranchOwnership
    case, ids = actual_site
    row = PMSChecklistItem(task_id=ids[0], title='Inspected checklist', is_completed=True)
    db.add(row); db.flush(); own(db, case, row); db.commit()
    checklist_id = row.id
    workspace_id = db.get(PMSProject, case[3]).workspace_id
    data = task_input(db, ids[0], status='Done')
    connection, revoked = db.connection(), []
    def after_commit(session):
        if session is db and session.in_nested_transaction() and not revoked:
            revoked.append(True)
            if revocation == 'workspace':
                table = BranchOwnership.__table__
                connection.execute(delete(table).where(table.c.resource_table == 'pms_workspaces', table.c.resource_key == str(workspace_id)))
            else:
                table = PMSChecklistItem.__table__
                connection.execute(update(table).where(table.c.id == checklist_id).values(is_completed=False))
    event.listen(db, 'after_commit', after_commit)
    try:
        with selected(db, case) as actor, pytest.raises(HTTPException) as denied:
            actuals.task_actual(case[3], ids[0], data, db, actor)
        assert denied.value.status_code == (404 if revocation == 'workspace' else 409)
    finally:
        event.remove(db, 'after_commit', after_commit)
    assert revoked and db.get(PMSTask, ids[0]).status == 'To Do'
    assert db.query(IndustryRecord).filter_by(project_id=case[3], kind='task_actual').count() == 0
