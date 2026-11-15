"""Selected Construction creates actual canonical PMS project/WBS masters once."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event, delete

from app.apps.project_management.models import (PMSWorkspace, PMSWorkspaceMember, PMSProject,
    PMSTask, PMSProjectMember, PMSBoard, PMSBoardColumn)
from app.apps.project_management.recovery_models import RecoveryChange
from app.apps.srm.industry_models import IndustryRecord
from app.branches.models import BranchOwnership
from app.business_packs.models import PackRecordOwnership
from app.models.email_outbox import EmailOutbox
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity

ROOT = '/api/v1/srm/industry'


def post(client, headers, path, body, expected=201):
    response = client.post(ROOT + path, headers=headers, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def own(db, case, row):
    table, key = row.__tablename__, str(row.id)
    db.add(PackRecordOwnership(company_id=1, branch_id=case['branch'], context_id=case['context'],
        resource_table=table, resource_key=key, source='explicit-test-enrollment'))
    if db.get(BranchOwnership, (table, key)) is None:
        db.add(BranchOwnership(company_id=1, branch_id=case['branch'], resource_table=table,
            resource_key=key, source='explicit-test-enrollment'))


@pytest.fixture
def definition(db, construction, catalog):
    actor, branch, context, _ = construction
    case = {'actor': actor, 'branch': branch, 'context': context,
        'headers': {**catalog[0], 'X-Suite-Pack-Context': str(context)}}
    workspace = PMSWorkspace(organization_id=1, name='Canonical Construction delivery workspace')
    db.add(workspace); db.flush(); own(db, case, workspace)
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=actor.id, role='Owner'))
    db.commit()
    case['workspace'] = workspace.id
    return case


def project_body(case, **values):
    return {'request_id': str(uuid4()), 'workspace_id': case['workspace'], 'name': 'New canonical Construction site',
        'project_key': 'SITE-' + uuid4().hex[:10], 'start_date': '2026-11-16', 'due_date': '2026-12-16',
        'estimated_cost': '1200', 'estimated_hours': '32', **values}


def task_body(**values):
    return {'request_id': str(uuid4()), 'title': 'Canonical WBS package', 'task_key': 'WBS-' + uuid4().hex[:12],
        'start_date': '2026-11-16', 'due_date': '2026-11-17', 'estimated_hours': '16', **values}


def test_canonical_project_and_wbs_birth_replay_then_native_schedule_apply(client, db, definition):
    case = definition
    before_projects, before_tasks = db.query(PMSProject).count(), db.query(PMSTask).count()
    body = project_body(case)
    project = post(client, case['headers'], '/site-projects', body)
    assert db.query(PMSProject).count() == before_projects + 1
    native = db.get(PMSProject, project['id'])
    assert native.workspace_id == case['workspace'] and native.branch_id == case['branch']
    assert native.owner_user_id == native.manager_user_id == case['actor'].id
    assert native.estimated_cost == Decimal('1200')
    assert post(client, case['headers'], '/site-projects', body) == project
    post(client, case['headers'], '/site-projects', {**body, 'name': 'Changed retry'}, 409)
    post(client, case['headers'], '/site-projects', {**body, 'request_id': str(uuid4())}, 409)
    parent_body = task_body(title='Actual WBS parent')
    parent = post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', parent_body)
    child_body = task_body(title='Actual WBS child', parent_task_id=parent['id'])
    child = post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', child_body)
    assert post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', child_body) == child
    assert db.query(PMSTask).count() == before_tasks + 2
    assert db.get(PMSTask, child['id']).parent_task_id == parent['id']
    assert db.get(PMSTask, child['id']).work_type == 'Sub-task'
    assert db.query(PMSBoard).filter_by(project_id=project['id']).count() == 1
    assert db.query(PMSBoardColumn).count() == 5
    assert db.query(RecoveryChange).filter(RecoveryChange.task_id.in_([parent['id'], child['id']])).count() == 2
    outbox = db.query(EmailOutbox).filter_by(module='pms', recipient_user_id=case['actor'].id).all()
    assert len(outbox) == 2
    assert all(row.status == 'queued' and row.organization_id == 1 for row in outbox)
    for row in outbox:
        assert db.query(PackRecordOwnership).filter_by(resource_table='email_outbox', resource_key=str(row.id),
            context_id=case['context'], branch_id=case['branch'], company_id=1).count() == 1
        assert db.get(BranchOwnership, ('email_outbox', str(row.id))).branch_id == case['branch']
    for model, ident in ((PMSProject, project['id']), (PMSTask, parent['id']), (PMSTask, child['id'])):
        owner = db.query(PackRecordOwnership).filter_by(resource_table=model.__tablename__, resource_key=str(ident)).one()
        assert (owner.company_id, owner.branch_id, owner.context_id) == (1, case['branch'], case['context'])
    analysis = client.get(f'/api/v1/project-management/projects/{project["id"]}/schedule-analysis', headers=case['headers'])
    assert analysis.status_code == 200, analysis.text
    apply = client.post(f'/api/v1/project-management/projects/{project["id"]}/schedule-apply', headers=case['headers'],
        json={'expected_revision': analysis.json()['revision'], 'task_id': child['id'],
            'start_date': '2026-11-18', 'due_date': '2026-11-19'})
    assert apply.status_code == 200, apply.text
    db.expire_all()
    assert db.get(PMSTask, child['id']).start_date == date(2026, 11, 18)
    assert db.query(PMSProject).count() == before_projects + 1 and db.query(PMSTask).count() == before_tasks + 2


def test_native_project_failure_does_not_leave_masters_provenance_or_consume_retry(client, db, definition, monkeypatch):
    from app.apps.project_management.api import router as pms
    case = definition
    original = pms.create_project_operation
    before = db.query(PMSProject).count()
    body = project_body(case)
    def fail_after_native(*args, **kwargs):
        result = original(*args, **kwargs)
        assert kwargs['commit'] is False and result.id
        raise RuntimeError('Native Construction definition late failure')
    with monkeypatch.context() as fault:
        fault.setattr(pms, 'create_project_operation', fail_after_native)
        with pytest.raises(RuntimeError, match='Native Construction definition late failure'):
            post(client, case['headers'], '/site-projects', body)
    assert db.query(PMSProject).count() == before
    assert db.query(IndustryRecord).filter_by(kind='project_definition').count() == 0
    created = post(client, case['headers'], '/site-projects', body)
    assert post(client, case['headers'], '/site-projects', body)['id'] == created['id']
    assert db.query(PMSProject).count() == before + 1


def test_native_task_failure_rolls_back_task_board_history_email_and_retries(client, db, definition, monkeypatch):
    from app.apps.project_management.api import router as pms
    case = definition
    project = post(client, case['headers'], '/site-projects', project_body(case))
    body = task_body()
    models = (PMSTask, PMSBoard, PMSBoardColumn, RecoveryChange, EmailOutbox, IndustryRecord,
              PackRecordOwnership)
    counts = {model: db.query(model).count() for model in models}
    before_branch = {(row.resource_table, row.resource_key, row.source) for row in db.query(BranchOwnership)}
    original = pms.create_task_operation
    def fail_after_native(*args, **kwargs):
        value = original(*args, **kwargs)
        assert kwargs['commit'] is False and value.id
        raise RuntimeError('Native task late failure')
    with monkeypatch.context() as fault:
        fault.setattr(pms, 'create_task_operation', fail_after_native)
        with pytest.raises(RuntimeError, match='Native task late failure'):
            post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', body)
    assert {model: db.query(model).count() for model in models} == counts
    after_branch = {(row.resource_table, row.resource_key, row.source) for row in db.query(BranchOwnership)}
    assert before_branch <= after_branch
    # Request-level failed-task auditing intentionally survives the business
    # savepoint; every actual task/business ownership birth must roll back.
    assert {(table, source) for table, key, source in after_branch - before_branch} == {
        ('audit_log_tasks', 'request-audit')}
    created = post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', body)
    assert post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', body) == created
    assert db.query(PMSTask).count() == counts[PMSTask] + 1
    assert db.query(EmailOutbox).count() == counts[EmailOutbox] + 1


def test_wbs_parent_ownership_revoked_at_release_rolls_back_birth_and_retries(client, db, definition):
    from app.apps.project_management.models import PMSActivity
    from app.shared.models import ServiceEvent
    case = definition
    project = post(client, case['headers'], '/site-projects', project_body(case))
    path = f'/projects/{project["id"]}/wbs-tasks'
    parent = post(client, case['headers'], path, task_body())
    body = task_body(parent_task_id=parent['id'])
    models = (PMSTask, IndustryRecord, PMSActivity, EmailOutbox, ServiceEvent, PackRecordOwnership)
    counts = {model: db.query(model).count() for model in models}
    fired = []
    connection = db.connection()
    def revoke(session, transaction):
        if fired or not transaction.nested or transaction.parent.nested:
            return
        fired.append(True)
        table = PackRecordOwnership.__table__
        connection.execute(delete(table).where(table.c.resource_table == 'pms_tasks',
            table.c.resource_key == str(parent['id'])))
    event.listen(db, 'after_transaction_end', revoke)
    try:
        post(client, case['headers'], path, body, 404)
    finally:
        event.remove(db, 'after_transaction_end', revoke)
    assert fired
    db.expire_all()
    assert {model: db.query(model).count() for model in models} == counts
    child = post(client, case['headers'], path, body)
    assert child['parent_task_id'] == parent['id']
    assert post(client, case['headers'], path, body) == child


def test_task_foreign_project_parent_and_native_workspace_creation_denied(client, db, definition):
    from tests.test_business_pack_http_integration import native_actor, grant
    from app.access.models import AccessPolicy
    from app.business_packs.models import PackContext
    case = definition
    project = post(client, case['headers'], '/site-projects', project_body(case))
    other = post(client, case['headers'], '/site-projects', project_body(case))
    foreign = post(client, case['headers'], f'/projects/{other["id"]}/wbs-tasks', task_body())
    post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', task_body(parent_task_id=foreign['id']), 404)
    headers, actor = native_actor(db, case['branch'])
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True, 'permissions': ['pms_view'],
        'actions': ['view', 'create'], 'scope': 'organization'}}
    db.add(PMSWorkspaceMember(workspace_id=case['workspace'], user_id=actor.id, role='Member'))
    db.commit()
    grant(db, actor, case['branch'], 'construction', 'project_manager', db.get(PackContext, case['context']))
    denied = post(client, {**headers, 'X-Suite-Pack-Context': str(case['context'])}, '/site-projects', project_body(case), 403)
    assert 'workspace' in str(denied).lower()
    foreign_workspace = PMSWorkspace(organization_id=1, name='Unenrolled native workspace')
    db.add(foreign_workspace); db.commit()
    post(client, case['headers'], '/site-projects', project_body(case, workspace_id=foreign_workspace.id), 404)


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_specialists_cannot_define_construction_projects_or_wbs(client, db, definition, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = definition
    context, _ = grant(db, case['actor'], case['branch'], pack, role)
    headers = {**case['headers'], 'X-Suite-Pack-Context': str(context.id)}
    post(client, headers, '/site-projects', project_body(case), 403)
    post(client, headers, '/projects/1/wbs-tasks', task_body(), 403)
