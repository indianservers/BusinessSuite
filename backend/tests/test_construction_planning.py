"""Canonical PMS scheduler retained inside an explicitly owned Construction graph."""
from contextlib import contextmanager
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.apps.project_management.models import PMSProject, PMSWorkspace, PMSWorkspaceMember, PMSTask, PMSTaskDependency
from app.apps.project_management.scheduling import PlanInput, BaselineInput
from app.business_packs import construction_planning as planning
from app.business_packs.models import PackRecordOwnership
from app.branches.models import BranchOwnership
from app.branches.catalog import resource_key
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def own(db, case, row):
    _, branch, context_id, _ = case
    table = row.__table__
    key = resource_key(table, {column.name: getattr(row, column.name) for column in table.primary_key.columns})
    for model, extra in ((BranchOwnership, {}), (PackRecordOwnership, {'context_id': context_id})):
        if db.query(model).filter_by(resource_table=table.name, resource_key=key).first() is None:
            db.add(model(company_id=1, branch_id=branch, resource_table=table.name, resource_key=key, source='explicit-planning-test', **extra))


@pytest.fixture
def site_plan(db, construction):
    actor, _, _, project_id = construction
    workspace = PMSWorkspace(organization_id=1, name='Canonical construction plan')
    db.add(workspace); db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=actor.id, role='Owner'))
    db.get(PMSProject, project_id).workspace_id = workspace.id
    tasks = []
    for index in range(2):
        row = PMSTask(project_id=project_id, task_key='PLAN-'+uuid4().hex[:10], title=f'Native work package {index}',
            start_date=date(2026,11,16+index), due_date=date(2026,11,16+index), status='To Do', estimated_hours=8)
        db.add(row); db.flush(); own(db, construction, row); tasks.append(row)
    edge = PMSTaskDependency(task_id=tasks[1].id, depends_on_task_id=tasks[0].id, dependency_type='Finish To Start', lag_days=0)
    db.add(edge); db.flush(); own(db, construction, edge); db.commit()
    return construction, [row.id for row in tasks], edge.id


@contextmanager
def selected(db, case, actor=None):
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    owner, branch, context_id, _ = case
    actor = actor or owner
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            yield actor
        finally:
            cleanup()


def test_native_analysis_preview_apply_and_retained_baseline(db, site_plan):
    case, ids, _ = site_plan
    with selected(db, case) as actor:
        first = planning.analysis(db, actor, case[3])
        assert set(first['critical_task_ids']) == set(ids)
        baseline = planning.capture(db, actor, case[3], BaselineInput(name='Native baseline', expected_revision=first['revision']))
        source = planning.baseline_source(db, actor, case[3], baseline['id'])
        assert {task['id'] for task in source['tasks']} == set(ids)
        moved = PlanInput(task_id=ids[0], start_date='2026-11-19', due_date='2026-11-19')
        preview = planning.preview(db, actor, case[3], moved)
        assert {row['id'] for row in preview['changes']} == set(ids)
        assert planning.task_sources(db, actor, case[3])[0]['start_date'] == date(2026,11,16), 'Preview cannot mutate'
        result = planning.apply(db, actor, case[3], moved.model_copy(update={'expected_revision': preview['revision']}))
        assert result['updated'] == 2
        with pytest.raises(HTTPException) as stale:
            planning.apply(db, actor, case[3], moved.model_copy(update={'expected_revision': preview['revision']}))
        assert stale.value.status_code == 409
        after = planning.analysis(db, actor, case[3], baseline['id'])
        assert after['baselines'][0]['id'] == baseline['id']
        assert all(row['due_variance_days'] == 3 for row in after['variance'])
        assert b'Native baseline' in planning.export_variance(db, actor, case[3], baseline['id']).body
        assert planning.export_variance(db, actor, case[3], baseline['id'], 'xlsx').body.startswith(b'PK')


def test_unowned_actual_task_cannot_be_hidden_from_planning_or_handover(db, site_plan):
    case, _, _ = site_plan
    row = PMSTask(project_id=case[3], task_key='HIDDEN-'+uuid4().hex[:10], title='Unowned open work', status='To Do')
    db.add(row); db.commit()
    with selected(db, case) as actor:
        for operation in (planning.analysis, planning.task_sources):
            with pytest.raises(HTTPException) as denied:
                operation(db, actor, case[3])
            assert denied.value.status_code == 409


def test_cycles_and_foreign_project_sources_fail_closed(db, site_plan):
    case, ids, _ = site_plan
    edge = PMSTaskDependency(task_id=ids[0], depends_on_task_id=ids[1], dependency_type='Finish To Start', lag_days=0)
    db.add(edge); db.flush(); own(db, case, edge); db.commit()
    with selected(db, case) as actor:
        with pytest.raises(HTTPException) as cycle:
            planning.analysis(db, actor, case[3])
        assert cycle.value.status_code == 409
        with pytest.raises(HTTPException) as foreign:
            planning.analysis(db, actor, case[3]+99999)
        assert foreign.value.status_code == 404


def test_native_viewer_cannot_preview_or_apply_management_plan(db, site_plan):
    from tests.test_construction_site_workflows import native_member
    case, _, _ = site_plan
    _, actor = native_member(db, case[1], case[2], case[3], 'Viewer')
    with selected(db, case, actor):
        with pytest.raises(HTTPException) as denied:
            planning.preview(db, actor, case[3], PlanInput())
        assert denied.value.status_code == 403


def test_native_resource_leveling_reuses_assignees_capacity_and_stale_capacity_guard(db, site_plan):
    from app.apps.project_management.models import PMSUserCapacity
    case, ids, _ = site_plan
    actor = case[0]
    for ident in ids:
        task = db.get(PMSTask, ident)
        task.assignee_user_id = actor.id
        task.start_date = task.due_date = date(2026,11,16)
    db.commit()
    with selected(db, case):
        plan = planning.preview(db, actor, case[3], PlanInput(level_resources=True))
        assert sum(row['hours'] for row in plan['resource_allocations']) == 16
        assert {row['user_id'] for row in plan['resource_allocations']} == {actor.id}
    db.add(PMSUserCapacity(organization_id=1, user_id=actor.id, week_start_date=date(2026,11,16), capacity_hours=20))
    db.commit()
    with selected(db, case):
        with pytest.raises(HTTPException) as stale:
            planning.apply(db, actor, case[3], PlanInput(level_resources=True, expected_revision=plan['revision']))
        assert stale.value.status_code == 409


def test_retained_sources_reject_foreign_native_baseline_and_preserve_completed_state(db, site_plan):
    from datetime import datetime, timezone
    case, ids, _ = site_plan
    task = db.get(PMSTask, ids[0])
    task.status = 'Done'
    task.completed_at = datetime.now(timezone.utc)
    db.commit()
    with selected(db, case) as actor:
        sources = planning.task_sources(db, actor, case[3])
        assert sources[0]['status'] == 'Done' and sources[0]['completed_at'] is not None
        assert sources[1]['status'] == 'To Do' and sources[1]['completed_at'] is None
        with pytest.raises(HTTPException) as foreign:
            planning.baseline_source(db, actor, case[3], 'other-project-baseline')
        assert foreign.value.status_code == 404


def test_native_schedule_late_failure_rolls_back_then_same_preview_retries(db, site_plan, monkeypatch):
    from app.apps.project_management import scheduling
    case, ids, _ = site_plan
    actual = scheduling.apply_operation
    with selected(db, case) as actor:
        move = PlanInput(task_id=ids[0], start_date='2026-11-19', due_date='2026-11-19')
        preview = planning.preview(db, actor, case[3], move)
        command = move.model_copy(update={'expected_revision': preview['revision']})
        def fail_after_native_dates(*args, **kwargs):
            actual(*args, **kwargs)
            raise RuntimeError('Native schedule late failure')
        with monkeypatch.context() as fault:
            fault.setattr(scheduling, 'apply_operation', fail_after_native_dates)
            with pytest.raises(RuntimeError, match='Native schedule late failure'):
                planning.apply(db, actor, case[3], command)
        assert planning.task_sources(db, actor, case[3])[0]['start_date'] == date(2026,11,16)
        assert planning.apply(db, actor, case[3], command)['updated'] == 2


def test_native_planning_reader_cannot_query_unrelated_financial_sources(db, site_plan, monkeypatch):
    from app.apps.project_management import scheduling
    from app.apps.srm.models import SRMInvoice
    case, _, _ = site_plan
    def unreviewed(project_id, data, native, actor):
        return native.query(SRMInvoice).all()
    with selected(db, case) as actor, monkeypatch.context() as fault:
        fault.setattr(scheduling, 'preview', unreviewed)
        with pytest.raises(HTTPException) as denied:
            planning.preview(db, actor, case[3], PlanInput())
        assert denied.value.status_code == 403


def test_native_resource_plan_retains_hr_holiday_and_approved_half_day_leave(db, site_plan):
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest, LeaveType
    from app.models.attendance import Holiday
    case, ids, _ = site_plan
    actor = case[0]
    employee = db.query(Employee).filter_by(branch_id=case[1]).first()
    employee.user_id = actor.id
    category = LeaveType(name='Native plan leave', code='PLAN-'+uuid4().hex[:8], days_allowed=10)
    db.add(category); db.flush()
    db.add(LeaveRequest(company_id=1, employee_id=employee.id, leave_type_id=category.id,
        from_date=date(2026,11,17), to_date=date(2026,11,17), days_count='0.5', is_half_day=True, status='Approved'))
    db.add(Holiday(name='Site closure', holiday_date=date(2026,11,16), applicable_branches=str(case[1]), is_active=True))
    for ident in ids:
        db.get(PMSTask, ident).assignee_user_id = actor.id
    db.commit(); db.expire(actor, ['employee'])
    with selected(db, case):
        plan = planning.preview(db, actor, case[3], PlanInput(level_resources=True))
        assert all(row['date'] != '2026-11-16' for row in plan['resource_allocations'])
        assert sum(row['hours'] for row in plan['resource_allocations'] if row['date'] == '2026-11-17') == 4
        assert sum(row['hours'] for row in plan['resource_allocations']) == 16


def test_foreign_work_package_parent_cannot_enter_the_owned_task_source(db, site_plan):
    case, ids, _ = site_plan
    foreign = PMSProject(organization_id=1, branch_id=case[1], name='Other canonical project', project_key=uuid4().hex[:14], manager_user_id=case[0].id)
    db.add(foreign); db.flush()
    parent = PMSTask(project_id=foreign.id, task_key='OTHER-'+uuid4().hex[:8], title='Foreign WBS parent')
    db.add(parent); db.flush()
    db.get(PMSTask, ids[0]).parent_task_id = parent.id
    db.commit()
    with selected(db, case) as actor, pytest.raises(HTTPException, match='work-package parents') as denied:
        planning.task_sources(db, actor, case[3])
    assert denied.value.status_code == 409


def test_native_project_manager_membership_cannot_replace_module_create_action(db, site_plan):
    from tests.test_construction_site_workflows import native_member
    from app.access.models import AccessPolicy
    case, _, _ = site_plan
    _, actor = native_member(db, case[1], case[2], case[3], 'Manager')
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'project_management': {**policy.grants['project_management'], 'actions': ['view']}}
    db.commit()
    with selected(db, case, actor), pytest.raises(HTTPException, match='native PMS module action') as denied:
        planning.preview(db, actor, case[3], PlanInput())
    assert denied.value.status_code == 403


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_same_native_actor_cannot_borrow_construction_plan_from_specialist_context(db, site_plan, pack, role):
    from tests.test_business_pack_http_integration import grant
    case, _, _ = site_plan
    context, _ = grant(db, case[0], case[1], pack, role)
    foreign_case = (case[0], case[1], context.id, case[3])
    with selected(db, foreign_case) as actor, pytest.raises(HTTPException) as denied:
        planning.analysis(db, actor, case[3])
    assert denied.value.status_code == 403


def test_noncommitting_native_baseline_stays_atomic_with_outer_control_record(db, site_plan):
    case, _, _ = site_plan
    with selected(db, case) as actor:
        before = planning.analysis(db, actor, case[3])
        data = BaselineInput(name='Prepared native baseline', expected_revision=before['revision'])
        captured = planning.capture(db, actor, case[3], data, commit=False)
        assert planning.baseline_source(db, actor, case[3], captured['id'])['id'] == captured['id']
        db.rollback()
        with pytest.raises(HTTPException) as absent:
            planning.baseline_source(db, actor, case[3], captured['id'])
        assert absent.value.status_code == 404
        retry = planning.capture(db, actor, case[3], data)
        assert retry['id'] != captured['id']


def test_native_project_manager_cannot_export_without_native_export_action(db, site_plan):
    from tests.test_construction_site_workflows import native_member
    case, _, _ = site_plan
    _, actor = native_member(db, case[1], case[2], case[3], 'Manager')
    with selected(db, case, actor), pytest.raises(HTTPException, match='native PMS export action') as denied:
        planning.export_variance(db, actor, case[3], 'unavailable-baseline')
    assert denied.value.status_code == 403


def test_native_public_http_schedule_roundtrip_and_specialist_denial(client, db, site_plan, catalog):
    from tests.test_business_pack_http_integration import grant
    case, ids, _ = site_plan
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(case[2])}
    path = f'/api/v1/project-management/projects/{case[3]}'
    analysis = client.get(path + '/schedule-analysis', headers=headers)
    assert analysis.status_code == 200, analysis.text
    assert set(analysis.json()['critical_task_ids']) == set(ids)
    baseline = client.post(path + '/schedule-baselines', headers=headers,
        json={'name': 'HTTP retained baseline', 'expected_revision': analysis.json()['revision']})
    assert baseline.status_code == 201, baseline.text
    exported = client.get(path + '/schedule-variance/export', headers=headers,
        params={'baseline_id': baseline.json()['id'], 'format': 'csv'})
    assert exported.status_code == 200 and b'HTTP retained baseline' in exported.content, exported.text
    move = {'task_id': ids[0], 'start_date': '2026-11-19', 'due_date': '2026-11-19'}
    preview = client.post(path + '/schedule-preview', headers=headers, json=move)
    assert preview.status_code == 200, preview.text
    command = {**move, 'expected_revision': preview.json()['revision']}
    applied = client.post(path + '/schedule-apply', headers=headers, json=command)
    assert applied.status_code == 200 and applied.json()['updated'] == 2, applied.text
    assert client.post(path + '/schedule-apply', headers=headers, json=command).status_code == 409
    for pack, role in (('hospital', 'doctor'), ('restaurant', 'chef')):
        context, _ = grant(db, case[0], case[1], pack, role)
        specialist = {**headers, 'X-Suite-Pack-Context': str(context.id)}
        denied = client.get(path + '/schedule-analysis', headers=specialist)
        assert denied.status_code == 403, denied.text
        denied = client.post(path + '/schedule-preview', headers=specialist, json=move)
        assert denied.status_code == 403, denied.text


@pytest.mark.parametrize('operation,revocation', [('apply', 'module'), ('capture', 'module'), ('apply', 'dependency'),
    ('apply', 'dependency_lag'), ('apply', 'task_date'), ('apply', 'calendar_body'), ('capture', 'calendar_body')])
def test_outer_release_rechecks_exact_native_planning_lease(db, site_plan, operation, revocation):
    import json
    from sqlalchemy import delete, event, select, update
    from app.apps.business_os.models import BOSEnabledModule
    from app.apps.project_management.models import PMSWorkspaceEntry
    case, ids, dependency_id = site_plan
    workspace_id = db.get(PMSProject, case[3]).workspace_id
    if revocation == 'module':
        configured = db.query(BOSEnabledModule).filter_by(company_id=1, module_key='project_management').first()
        if configured is None:
            db.add(BOSEnabledModule(company_id=1, module_key='project_management', display_name='Project Management', enabled=True))
        else:
            configured.enabled = True
        db.commit()
    connection, revoked = db.connection(), []
    def after_commit(session):
        if session is db and session.in_nested_transaction() and not revoked:
            revoked.append(True)
            if revocation == 'module':
                table = BOSEnabledModule.__table__
                connection.execute(update(table).where(table.c.company_id == 1, table.c.module_key == 'project_management').values(enabled=False))
            elif revocation == 'dependency':
                table = PMSTaskDependency.__table__
                connection.execute(delete(table).where(table.c.id == dependency_id))
            elif revocation == 'dependency_lag':
                table = PMSTaskDependency.__table__
                connection.execute(update(table).where(table.c.id == dependency_id).values(lag_days=7))
            elif revocation == 'task_date':
                table = PMSTask.__table__
                connection.execute(update(table).where(table.c.id == ids[0]).values(due_date=date(2026,11,25)))
            else:
                table = PMSWorkspaceEntry.__table__
                retained = connection.execute(select(table.c.id, table.c.body).where(table.c.workspace_id == workspace_id,
                    table.c.kind == f'sc{case[3]:x}')).one()
                body = json.loads(retained.body)
                body['calendar'] = {**body.get('calendar', {}), 'weekdays': [0]}
                connection.execute(update(table).where(table.c.id == retained.id).values(body=json.dumps(body)))
    with selected(db, case) as actor:
        before = planning.analysis(db, actor, case[3])
        event.listen(db, 'after_commit', after_commit)
        try:
            with pytest.raises(HTTPException) as denied:
                if operation == 'capture':
                    planning.capture(db, actor, case[3], BaselineInput(name='Revoked capture', expected_revision=before['revision']))
                else:
                    data = PlanInput(task_id=ids[0], start_date='2026-11-19', due_date='2026-11-19')
                    preview = planning.preview(db, actor, case[3], data)
                    planning.apply(db, actor, case[3], data.model_copy(update={'expected_revision': preview['revision']}))
            assert denied.value.status_code == (403 if revocation == 'module' else 409)
        finally:
            event.remove(db, 'after_commit', after_commit)
    assert revoked and db.get(PMSTask, ids[0]).start_date == date(2026,11,16)


@pytest.mark.parametrize('operation,failure', [('apply','stale'), ('apply','late'), ('capture','stale'), ('capture','late'), ('apply','proof'), ('capture','proof')])
def test_noncommitting_failure_preserves_caller_outer_marker(db, site_plan, monkeypatch, operation, failure):
    from contextlib import contextmanager
    from sqlalchemy import event, update
    from app.apps.project_management import scheduling
    from app.apps.business_os.models import BOSEnabledModule
    from app.apps.srm.industry_models import IndustryRecord
    case, ids, _ = site_plan
    actor, branch, _, pid = case
    if failure == 'proof' and db.query(BOSEnabledModule).filter_by(company_id=1, module_key='project_management').first() is None:
        db.add(BOSEnabledModule(company_id=1, module_key='project_management', display_name='Project Management', enabled=True))
        db.commit()
    with selected(db, case):
        current = planning.analysis(db, actor, pid)
        marker = IndustryRecord(organization_id=1, branch_id=branch, project_id=pid, kind='site_diary',
            title='Caller-owned pending work', request_id=str(uuid4()), status='recorded', created_by=actor.id,
            data={'entry_date': date.today().isoformat(), 'work_done': 'Caller work before the planning operation', 'workforce': 1})
        db.add(marker)
        name = 'apply_operation' if operation == 'apply' else 'capture_baseline_operation'
        original = getattr(scheduling, name)
        connection, revoked = db.connection(), []
        def after_commit(session):
            if session is db and session.in_nested_transaction() and not revoked:
                revoked.append(True)
                table = BOSEnabledModule.__table__
                connection.execute(update(table).where(table.c.company_id == 1, table.c.module_key == 'project_management').values(enabled=False))
        @contextmanager
        def revoke_at_release():
            if failure == 'proof':
                event.listen(db, 'after_commit', after_commit)
            try:
                yield
            finally:
                if failure == 'proof':
                    event.remove(db, 'after_commit', after_commit)
        def fail_late(*args, **kwargs):
            original(*args, **kwargs)
            raise HTTPException(409, 'Native planning failed after its own writes')
        with monkeypatch.context() as fault, revoke_at_release():
            if failure == 'late':
                fault.setattr(scheduling, name, fail_late)
            with pytest.raises(HTTPException) as denied:
                if operation == 'apply':
                    data = PlanInput(task_id=ids[0], start_date='2026-11-19', due_date='2026-11-19',
                        expected_revision='0'*64 if failure == 'stale' else current['revision'])
                    planning.apply(db, actor, pid, data, commit=False)
                else:
                    planning.capture(db, actor, pid, BaselineInput(name='Failed caller-owned capture',
                        expected_revision='0'*64 if failure == 'stale' else current['revision']), commit=False)
            assert denied.value.status_code == (403 if failure == 'proof' else 409)
        if failure == 'proof':
            assert revoked
        assert db.in_transaction() and db.get(IndustryRecord, marker.id).title == 'Caller-owned pending work'
        assert not planning.analysis(db, actor, pid)['baselines']
        assert planning.task_sources(db, actor, pid)[0]['start_date'] == date(2026,11,16)
        db.commit()
    assert db.get(IndustryRecord, marker.id).title == 'Caller-owned pending work'
