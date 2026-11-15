"""Actual canonical dependency/resource creation through selected public APIs."""
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from sqlalchemy import event, select, update, delete
from app.apps.project_management.models import PMSTask, PMSTaskDependency, PMSTaskAssignee, PMSWorkspaceMember
from app.apps.srm.industry_models import IndustryRecord
from app.business_packs.models import PackContext, PackRecordOwnership, PackUserGrant
from app.models.email_outbox import EmailOutbox
from app.shared.models import ServiceEvent
from app.apps.project_management.models import PMSActivity
from tests.test_construction_definition import definition, project_body, task_body, post, ROOT
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity


@pytest.fixture
def site(client, db, definition):
    case = definition
    case['project'] = post(client, case['headers'], '/site-projects', project_body(case))['id']
    case['tasks'] = [post(client, case['headers'], f'/projects/{case["project"]}/wbs-tasks', task_body())['id'] for _ in range(5)]
    return case


def body(case, source=0, target=1, **values):
    return {'request_id': str(uuid4()), 'source_task_id': case['tasks'][source],
        'target_task_id': case['tasks'][target], 'dependency_type': 'FS', 'lag_days': 0, **values}


def test_actual_native_dependency_types_cycle_duplicate_retry_and_level_preview(client, db, site):
    case = site
    path = f'/projects/{case["project"]}/task-dependencies'
    first = body(case)
    result = post(client, case['headers'], path, first)
    assert result['dependency_type'] == 'Finish To Start'
    assert post(client, case['headers'], path, first) == result
    post(client, case['headers'], path, {**first, 'lag_days': 1}, 409)
    post(client, case['headers'], path, body(case), 400)
    for i, (kind, expected) in enumerate([('SS','Start To Start'),('FF','Finish To Finish'),('SF','Start To Finish')], start=1):
        value = post(client, case['headers'], path, body(case, i, i+1, dependency_type=kind, lag_days=i))
        assert value['dependency_type'] == expected and value['lag_days'] == i
    post(client, case['headers'], path, body(case, 4, 0), 400)
    post(client, case['headers'], path, body(case, 0, 0), 400)
    assert db.query(PMSTaskDependency).count() == 4
    assert db.query(IndustryRecord).filter_by(kind='dependency_definition').count() == 4
    for edge in db.query(PMSTaskDependency):
        assert db.query(PackRecordOwnership).filter_by(resource_table=edge.__tablename__, resource_key=str(edge.id),
            context_id=case['context']).count() == 1


def test_native_dependency_late_failure_is_atomic_and_same_request_retries(client, db, site, monkeypatch):
    from app.apps.project_management.api import router as pms
    case = site
    original = pms.create_task_dependency_operation
    request = body(case)
    path = f'/projects/{case["project"]}/task-dependencies'
    def fail_late(*args, **kwargs):
        original(*args, **kwargs)
        assert kwargs['commit'] is False
        raise RuntimeError('Native dependency late failure')
    with monkeypatch.context() as fault:
        fault.setattr(pms, 'create_task_dependency_operation', fail_late)
        with pytest.raises(RuntimeError, match='Native dependency late failure'):
            post(client, case['headers'], path, request)
    assert db.query(PMSTaskDependency).count() == 0
    assert db.query(IndustryRecord).filter_by(kind='dependency_definition').count() == 0
    assert not db.get(PMSTask, request['source_task_id']).is_blocking
    post(client, case['headers'], path, request)


@pytest.mark.parametrize('revocation', ['native', 'ownership', 'endpoint'])
def test_dependency_release_time_revocation_rolls_back_native_birth_and_retries(client, db, site, revocation):
    from app.access.models import AccessPolicy
    case = site
    request, fired = body(case), []
    models = (PMSTaskDependency, PMSActivity, ServiceEvent, IndustryRecord, PackRecordOwnership)
    counts = {model: db.query(model).count() for model in models}
    connection = db.connection()
    def revoke(session, transaction):
        if fired or not transaction.nested or transaction.parent.nested:
            return
        fired.append(True)
        if revocation == 'native':
            table = AccessPolicy.__table__
            policy = connection.execute(select(table).where(table.c.user_id == case['actor'].id, table.c.company_id == 1)).one_or_none()
            if policy is None:
                connection.execute(table.insert().values(user_id=case['actor'].id, company_id=1,
                    grants={}, status='revoked', version=1))
            else:
                connection.execute(update(table).where(table.c.id == policy.id).values(status='revoked', version=policy.version+1))
        elif revocation == 'ownership':
            table = PackRecordOwnership.__table__
            connection.execute(delete(table).where(table.c.resource_table == 'pms_tasks',
                table.c.resource_key == str(request['target_task_id'])))
        else:
            connection.execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == request['target_task_id']).values(deleted_at=datetime.now(timezone.utc)))
    event.listen(db, 'after_transaction_end', revoke)
    try:
        response = client.post(ROOT + f'/projects/{case["project"]}/task-dependencies', headers=case['headers'], json=request)
        assert response.status_code in {403, 404, 409}, response.text
    finally:
        event.remove(db, 'after_transaction_end', revoke)
    assert fired
    db.expire_all()
    assert {model: db.query(model).count() for model in models} == counts
    assert not db.get(PMSTask, request['source_task_id']).is_blocking
    assert db.get(PMSTask, request['target_task_id']).deleted_at is None
    post(client, case['headers'], f'/projects/{case["project"]}/task-dependencies', request)


def test_direct_helper_respects_native_sales_create_action_floor(db, definition):
    from fastapi import HTTPException
    from app.access.models import AccessPolicy
    from tests.test_business_pack_http_integration import native_actor, grant
    from app.access.service import background_scope
    from app.branches.service import context as branch_context
    from app.branches.boundary import install as install_branch
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.construction_definition import _access
    case = definition
    _, actor = native_actor(db, case['branch'], actions=('view',))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True, 'actions': ['view', 'create'],
        'permissions': ['pms_view'], 'scope': 'organization'}}
    db.add(PMSWorkspaceMember(workspace_id=case['workspace'], user_id=actor.id, role='Owner'))
    db.commit()
    grant(db, actor, case['branch'], 'construction', 'project_manager', db.get(PackContext, case['context']))
    cleanup_branch = install_branch(db, actor, branch_context(db, actor, 1, str(case['branch'])))
    try:
        with background_scope(db, actor, 'srm', 'view', branch_id=case['branch']):
            scope = resolve_context(db, actor, db.info['branch_context'], case['context'])
            cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
            try:
                with pytest.raises(HTTPException) as denied:
                    _access(db, actor)
                assert denied.value.status_code == 403
            finally:
                cleanup()
    finally:
        cleanup_branch()


def test_resource_own_construction_grant_and_native_membership_required_then_native_assignment(client, db, definition):
    from tests.test_business_pack_http_integration import native_actor, grant
    from app.access.models import AccessPolicy
    case = definition
    case['project'] = post(client, case['headers'], '/site-projects', project_body(case))['id']
    headers, resource = native_actor(db, case['branch'])
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=resource.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True, 'permissions': ['pms_view'],
        'actions': ['view'], 'scope': 'organization'}}
    db.add(PMSWorkspaceMember(workspace_id=case['workspace'], user_id=resource.id, role='Member'))
    db.commit()
    # An active native project collaborator with only Doctor/Chef is ineligible.
    grant(db, resource, case['branch'], 'hospital', 'doctor')
    grant(db, resource, case['branch'], 'restaurant', 'chef')
    path = f'/projects/{case["project"]}'
    options = client.get(ROOT + path + '/resource-options', headers=case['headers'])
    assert options.status_code == 200, options.text
    assert resource.id not in {item['id'] for item in options.json()['items']}
    task = task_body(assignee_user_ids=[resource.id])
    post(client, case['headers'], path + '/wbs-tasks', task, 404)
    grant(db, resource, case['branch'], 'construction', 'site_engineer', db.get(PackContext, case['context']))
    options = client.get(ROOT + path + '/resource-options', headers=case['headers'])
    assert options.status_code == 200, options.text
    assert resource.id in {item['id'] for item in options.json()['items']}
    created = post(client, case['headers'], path + '/wbs-tasks', task)
    assert db.get(PMSTask, created['id']).assignee_user_id == resource.id
    assert db.get(PMSTaskAssignee, (created['id'], resource.id)) is not None
    from app.branches.catalog import resource_key
    assignment_key = resource_key(PMSTaskAssignee.__table__, {'task_id': created['id'], 'user_id': resource.id})
    assert db.query(PackRecordOwnership).filter_by(resource_table='pms_task_assignees',
        resource_key=assignment_key, context_id=case['context']).count() == 1
    assert {row.subject for row in db.query(EmailOutbox).filter_by(recipient_user_id=resource.id, module='pms')} == {
        'Task: To Do', 'Assigned task: To Do'}
    preview = client.post(f'/api/v1/project-management/projects/{case["project"]}/schedule-preview',
        headers=case['headers'], json={'level_resources': True})
    assert preview.status_code == 200, preview.text
    assert resource.id in {item['user_id'] for item in preview.json()['resource_allocations']}
    applied = client.post(f'/api/v1/project-management/projects/{case["project"]}/schedule-apply',
        headers=case['headers'], json={'level_resources': True, 'expected_revision': preview.json()['revision']})
    assert applied.status_code == 200, applied.text
    tasks = client.get(ROOT + path + '/planning-tasks', headers=case['headers'])
    assert tasks.status_code == 200, tasks.text
    actual = next(item for item in tasks.json()['items'] if item['id'] == created['id'])
    closed = post(client, case['headers'], path + f'/task-actuals/{created["id"]}',
        {'request_id': str(uuid4()), 'expected_updated_at': actual['updated_at'], 'status': 'Done', 'actual_hours': '8.00'}, 200)
    assert closed['status'] == 'Done' and closed['completed_at']


@pytest.mark.parametrize('pack,role', [('hospital','doctor'),('restaurant','chef')])
def test_specialist_context_and_foreign_project_denied(client, db, site, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = site
    context, _ = grant(db, case['actor'], case['branch'], pack, role)
    headers = {**case['headers'], 'X-Suite-Pack-Context': str(context.id)}
    post(client, headers, f'/projects/{case["project"]}/task-dependencies', body(case), 403)
    assert client.get(ROOT + f'/projects/{case["project"]}/resource-options', headers=headers).status_code == 403
    post(client, case['headers'], '/projects/999999/task-dependencies', body(case), 404)
