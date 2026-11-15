"""PROPOSAL tests: run only after approved workspace adapter/hooks are installed."""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSProject, PMSTask
from app.apps.srm.industry_models import IndustryRecord
from app.branches.models import BranchOwnership
from app.business_packs.models import PackRecordOwnership
from app.business_packs import construction_workspaces as setup
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_construction_planning import selected
from tests.test_construction_definition import project_body, task_body

ROOT = '/api/v1/srm/industry'


def post(client, headers, path, data, expected=201):
    response = client.post(ROOT + path, headers=headers, json=data)
    assert response.status_code == expected, response.text
    return response.json()


def test_first_authorized_workspace_to_site_task_and_native_actual_write(client, db, construction, catalog):
    actor, branch, context_id, _ = construction
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    request = {'request_id': str(uuid4()), 'name': 'Canonical Construction workspace ' + uuid4().hex[:8]}
    before = db.query(PMSWorkspace).count()
    created = post(client, headers, '/workspace-definitions', request)
    assert db.query(PMSWorkspace).count() == before + 1
    owner = db.query(PMSWorkspaceMember).filter_by(workspace_id=created['id'], user_id=actor.id).one()
    assert owner.role == 'Owner'
    for model, identity in ((PMSWorkspace, created['id']), (PMSWorkspaceMember, owner.id)):
        for table in (PackRecordOwnership, BranchOwnership):
            assert db.query(table).filter_by(resource_table=model.__tablename__, resource_key=str(identity),
                company_id=1, branch_id=branch).count() == 1
    provenance = db.query(IndustryRecord).filter_by(kind='workspace_definition', request_id=request['request_id']).one()
    assert provenance.project_id is None and provenance.data['workspace_id'] == created['id']
    assert post(client, headers, '/workspace-definitions', request) == created
    post(client, headers, '/workspace-definitions', {**request, 'name': 'Different details for reserved request'}, 409)
    choices = client.get(ROOT + '/definition-workspaces', headers=headers)
    assert choices.status_code == 200, choices.text
    assert created['id'] in {item['id'] for item in choices.json()['items']}
    site = post(client, headers, '/site-projects', project_body({'workspace': created['id']}))
    assert db.get(PMSProject, site['id']).workspace_id == created['id']
    task = post(client, headers, f'/projects/{site["id"]}/wbs-tasks', task_body())
    sources = client.get(ROOT + f'/projects/{site["id"]}/planning-tasks', headers=headers)
    assert sources.status_code == 200, sources.text
    source = next(row for row in sources.json()['items'] if row['id'] == task['id'])
    done = post(client, headers, f'/projects/{site["id"]}/task-actuals/{task["id"]}', {
        'request_id': str(uuid4()), 'expected_updated_at': source['updated_at'], 'status': 'Done', 'actual_hours': '8.00'}, 200)
    assert done['status'] == 'Done' and done['completed_at']
    assert db.get(PMSTask, task['id']).status == 'Done'


def test_workspace_setup_native_failure_rolls_back_and_same_request_retries(db, construction, monkeypatch):
    from app.apps.project_management import workspaces as native
    case = construction
    data = setup.WorkspaceInput(request_id=uuid4(), name='Retryable native workspace ' + uuid4().hex[:8])
    before_workspaces, before_members = db.query(PMSWorkspace).count(), db.query(PMSWorkspaceMember).count()
    original = native.create_workspace_operation
    def fail_late(*args, **kwargs):
        result = original(*args, **kwargs)
        assert kwargs['commit'] is False and type(result) is PMSWorkspace
        raise HTTPException(409, 'Native workspace failure after its genuine births')
    with selected(db, case) as actor:
        with monkeypatch.context() as fault:
            fault.setattr(native, 'create_workspace_operation', fail_late)
            with pytest.raises(HTTPException) as denied:
                setup.create(data, db, actor)
            assert denied.value.status_code == 409
        result = setup.create(data, db, actor)
        assert result['name'] == data.name
    assert db.query(PMSWorkspace).count() == before_workspaces + 1
    assert db.query(PMSWorkspaceMember).count() == before_members + 1
    assert db.query(IndustryRecord).filter_by(kind='workspace_definition').count() == 1


@pytest.mark.parametrize('pack,role', [('hospital','doctor'), ('restaurant','chef')])
def test_same_actor_specialist_cannot_create_construction_workspace(client, db, construction, catalog, pack, role):
    from tests.test_business_pack_http_integration import grant
    actor, branch, _, _ = construction
    context, _ = grant(db, actor, branch, pack, role)
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context.id)}
    before = db.query(PMSWorkspace).count()
    post(client, headers, '/workspace-definitions', {'request_id': str(uuid4()), 'name': 'Forbidden workspace'}, 403)
    assert db.query(PMSWorkspace).count() == before


def test_workspace_setup_requires_native_global_permission_not_just_pack_settings(db, construction):
    from tests.test_construction_site_workflows import native_member
    case = construction
    _, actor = native_member(db, case[1], case[2], case[3], 'Manager')
    with selected(db, case, actor), pytest.raises(HTTPException) as denied:
        setup.create(setup.WorkspaceInput(request_id=uuid4(), name='Native permission required'), db, actor)
    assert denied.value.status_code == 403


def test_workspace_setup_cannot_adopt_or_overwrite_existing_workspace(client, db, construction, catalog):
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(construction[2])}
    legacy = PMSWorkspace(organization_id=1, name='Existing canonical workspace')
    db.add(legacy); db.commit()
    before = db.query(PMSWorkspace).count()
    body = {'request_id': str(uuid4()), 'name': 'Explicit new canonical root', 'workspace_id': legacy.id}
    post(client, headers, '/workspace-definitions', body, 422)
    assert db.query(PMSWorkspace).count() == before
    assert db.query(PackRecordOwnership).filter_by(resource_table='pms_workspaces', resource_key=str(legacy.id)).count() == 0


def test_workspace_setup_provenance_is_immutable(db, construction):
    with selected(db, construction) as actor:
        created = setup.create(setup.WorkspaceInput(request_id=uuid4(), name='Retained native provenance'), db, actor)
        row = db.query(IndustryRecord).filter_by(kind='workspace_definition').one()
        row.data = {**row.data, 'workspace_id': created['id'] + 1}
        with pytest.raises(HTTPException) as denied:
            db.flush()
        assert denied.value.status_code == 403
        db.rollback()


def test_workspace_setup_rechecks_native_authority_after_outer_release(db, construction):
    from sqlalchemy import event, update
    from app.models.user import User
    case = construction
    before = db.query(PMSWorkspace).count(), db.query(PMSWorkspaceMember).count()
    connection, revoked = db.connection(), []
    def after_commit(session):
        if session is db and session.in_nested_transaction() and not revoked:
            revoked.append(True)
            connection.execute(update(User.__table__).where(User.__table__.c.id == case[0].id).values(is_active=False))
    event.listen(db, 'after_commit', after_commit)
    try:
        with selected(db, case) as actor, pytest.raises(HTTPException) as denied:
            setup.create(setup.WorkspaceInput(request_id=uuid4(), name='Revoked native setup'), db, actor)
        assert denied.value.status_code == 403
    finally:
        event.remove(db, 'after_commit', after_commit)
    assert revoked
    assert (db.query(PMSWorkspace).count(), db.query(PMSWorkspaceMember).count()) == before
    assert db.query(IndustryRecord).filter_by(kind='workspace_definition').count() == 0


def test_workspace_native_resource_cannot_query_existing_projects(db, construction, monkeypatch):
    from app.apps.project_management import workspaces as native
    original = native.create_workspace_operation
    def unreviewed(data, reader, principal, **kwargs):
        reader.query(PMSProject).all()
        return original(data, reader, principal, **kwargs)
    with selected(db, construction) as actor, monkeypatch.context() as fault:
        fault.setattr(native, 'create_workspace_operation', unreviewed)
        with pytest.raises(HTTPException) as denied:
            setup.create(setup.WorkspaceInput(request_id=uuid4(), name='Unreviewed source rejected'), db, actor)
        assert denied.value.status_code == 403


def test_workspace_provenance_cannot_be_forged_outside_native_birth_lease(db, construction):
    with selected(db, construction):
        row = IndustryRecord(organization_id=1, branch_id=construction[1], project_id=None,
            kind='workspace_definition', title='Forged setup provenance', status='created', revision=1,
            request_id=str(uuid4()), created_by=construction[0].id,
            data={'workspace_id': 1, '_request_digest': 'forged', 'native_result': {'id': 1, 'role': 'Owner'}})
        db.add(row)
        with pytest.raises(HTTPException) as denied:
            db.flush()
        assert denied.value.status_code == 403
        db.rollback()


@pytest.mark.parametrize('attack', ['native_result', 'foreign_link', 'title', 'request_id', 'stored_payload'])
def test_workspace_provenance_forgery_inside_actual_lease_is_rejected(db, construction, monkeypatch, attack):
    import json
    from sqlalchemy import update
    from app.apps.srm import industry_api
    original = industry_api.audit
    before = db.query(PMSWorkspace).count(), db.query(PMSWorkspaceMember).count()
    def forged_audit(session, actor, row, action):
        original(session, actor, row, action)
        if row.kind != 'workspace_definition':
            return
        if attack == 'native_result':
            row.data = {**row.data, 'native_result': {'id': row.data['workspace_id'] + 1, 'name': 'Forged', 'role': 'Owner'}}
        elif attack == 'foreign_link':
            row.customer_id = 101
        elif attack == 'title':
            row.title = 'Forged source title'
        elif attack == 'request_id':
            row.request_id = str(uuid4())
        else:
            payload = {**row.data, 'native_result': {'id': row.data['workspace_id'] + 1, 'role': 'Owner'}}
            session.connection().execute(update(IndustryRecord.__table__).where(IndustryRecord.__table__.c.id == row.id).values(data=payload))
    with selected(db, construction) as actor, monkeypatch.context() as fault:
        fault.setattr(industry_api, 'audit', forged_audit)
        with pytest.raises(HTTPException) as denied:
            setup.create(setup.WorkspaceInput(request_id=uuid4(), name='Actual workspace with rejected forgery'), db, actor)
        assert denied.value.status_code == 403
    assert (db.query(PMSWorkspace).count(), db.query(PMSWorkspaceMember).count()) == before
    assert db.query(IndustryRecord).filter_by(kind='workspace_definition').count() == 0
