"""Actor17 integration probes; execute only after the coherent common candidate.

Every source is created through real Construction/native APIs. No provider is
called and no assignment/notice birth is fabricated to satisfy a certificate.
"""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSTask, PMSTaskAssignee
from app.business_packs.models import PackUserGrant
from app.business_packs.delivery_source_models import PackDeliverySource
from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_construction_workspace_members import workspace, person, command
from tests.test_construction_workspaces import post, ROOT
from tests.test_construction_definition import project_body, task_body


@pytest.fixture
def three_subjects(client, db, workspace):
    case, owner_headers, wid = workspace['case'], workspace['headers'], workspace['id']
    manager_headers, manager = person(db, case, role='project_manager', actions=('view', 'create', 'edit', 'approve'))
    _, engineer = person(db, case)
    owner_id, manager_id, engineer_id = case[0].id, manager.id, engineer.id
    assert len({owner_id, manager_id, engineer_id}) == 3
    post(client, owner_headers, f'/workspaces/{wid}/member-definitions', command(manager_id, 'Admin'))
    post(client, owner_headers, f'/workspaces/{wid}/member-definitions', command(engineer_id))
    site = post(client, owner_headers, '/site-projects', project_body({'workspace': wid}))
    task = post(client, owner_headers, f'/projects/{site["id"]}/wbs-tasks', task_body(assignee_user_ids=[engineer_id]))
    row = db.get(PMSTask, task['id'])
    assert row.reporter_user_id == owner_id and row.assignee_user_id == engineer_id
    assert manager_id not in {row.reporter_user_id, row.assignee_user_id}
    db.commit()  # Complete successful request/audit work before baseline snapshots.
    return {'case': case, 'headers': owner_headers, 'manager_headers': manager_headers, 'workspace': wid,
        'owner': owner_id, 'manager': manager_id, 'engineer': engineer_id, 'site': site['id'], 'task': task['id']}


def actual_source(client, case):
    response = client.get(ROOT + f'/projects/{case["site"]}/planning-tasks', headers=case['manager_headers'])
    assert response.status_code == 200, response.text
    return next(row for row in response.json()['items'] if row['id'] == case['task'])


@pytest.mark.parametrize('revocation', ['pack', 'native'])
def test_mutating_manager_is_immutable_issuer_not_task_creator_or_recipient(client, db, three_subjects, revocation):
    from app.business_packs.delivery_sources import delivery_allowed
    case = three_subjects
    # A genuine notice by Manager2 to Engineer3, in another Owner1 workspace.
    # The main workspace already has Engineer3, so no duplicate membership is
    # manufactured merely to produce a second notification.
    second = post(client, case['headers'], '/workspace-definitions',
        {'request_id': str(uuid4()), 'name': 'Issuer regression ' + uuid4().hex[:8]})['id']
    post(client, case['headers'], f'/workspaces/{second}/member-definitions', command(case['manager'], 'Admin'))
    post(client, case['manager_headers'], f'/workspaces/{second}/member-definitions', command(case['engineer']))
    notice = db.query(Notification).filter_by(user_id=case['engineer'], event_type='workspace.member_added',
        action_url=f'/pms/workspaces?workspace={second}').one()
    notice_certificate = db.query(PackDeliverySource).filter_by(notification_id=notice.id).one()
    assert notice_certificate.actor_user_id == case['manager']
    notice_email_certificates = db.query(PackDeliverySource).filter_by(source_table='notifications', source_key=str(notice.id)).all()
    assert notice_email_certificates
    assert all(row.actor_user_id == case['manager'] for row in notice_email_certificates)

    assignment = PMSTaskAssignee.__table__
    assignment_before = tuple(db.connection().execute(select(assignment).where(assignment.c.task_id == case['task'])))
    prior_certificates = {row.id for row in db.query(PackDeliverySource)}
    retained_assignment = db.query(PackDeliverySource).filter_by(source_table='pms_task_assignees',
        actor_user_id=case['owner'], recipient_user_id=case['engineer']).all()
    assert retained_assignment, 'The actual assignment creation was authored by Owner1'
    source = actual_source(client, case)
    result = post(client, case['manager_headers'], f'/projects/{case["site"]}/task-actuals/{case["task"]}',
        {'request_id': str(uuid4()), 'expected_updated_at': source['updated_at'],
            'status': 'In Progress', 'actual_hours': '4.00'}, 200)
    assert result['status'] == 'In Progress'
    db.expire_all()
    assert tuple(db.connection().execute(select(assignment).where(assignment.c.task_id == case['task']))) == assignment_before
    new_certificates = db.query(PackDeliverySource).filter(PackDeliverySource.id.notin_(prior_certificates)).all()
    task_certificates = [row for row in new_certificates if row.source_table == 'pms_tasks' and row.source_key == str(case['task'])]
    assert {row.recipient_user_id for row in task_certificates} == {case['owner'], case['engineer']}
    assert all(row.actor_user_id == case['manager'] for row in task_certificates)
    assert not any(row.source_table == 'pms_task_assignees' for row in new_certificates), (
        'Status/hours actuals do not mutate native assignments; never fabricate an assignment birth')
    emails = [db.get(EmailOutbox, row.email_outbox_id) for row in [*task_certificates, *notice_email_certificates]]
    assert all(type(row) is EmailOutbox and delivery_allowed(db, row) is True for row in emails)
    assert delivery_allowed(db, notice) is True

    if revocation == 'pack':
        grant = db.query(PackUserGrant).filter_by(context_id=case['case'][2], user_id=case['manager']).one()
        grant.active = False
    else:
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['manager']).one()
        policy.grants = {**policy.grants, 'project_management': {'enabled': False, 'permissions': [], 'actions': []}}
        policy.version += 1
    db.commit()
    assert db.query(PackUserGrant).filter_by(context_id=case['case'][2], user_id=case['owner'], active=True).count() == 1
    assert db.query(PackUserGrant).filter_by(context_id=case['case'][2], user_id=case['engineer'], active=True).count() == 1
    assert delivery_allowed(db, notice) is False
    assert all(delivery_allowed(db, row) is False for row in emails)
    # Creator1/recipient3 remain valid. Historical genuine assignment messages
    # use their real Owner1 issuer, not the later unrelated task updater.
    assert all(delivery_allowed(db, db.get(EmailOutbox, row.email_outbox_id)) is True for row in retained_assignment)


def test_planning_commit_false_retains_actual_manager_issuer_until_root_commit(client, db, three_subjects, monkeypatch):
    from app.business_packs import construction_emitter as emitter, delivery_sources as common, construction_planning as planning
    from app.apps.project_management.scheduling import PlanInput
    from app.models.user import User
    from tests.test_construction_planning import selected
    case = three_subjects
    manager = db.get(User, case['manager'])
    manager.organization_id = 1
    captured = []
    original = common.bind_native_emitter
    def bound(native, scope, *, parent, frame):
        assert scope.user_id == case['manager']
        assert emitter.verify_native_emitter(native, scope, parent=parent, frame=frame) is True
        cleanup = original(native, scope, parent=parent, frame=frame)
        captured.append((native, scope, parent, frame))
        return cleanup
    monkeypatch.setattr(common, 'bind_native_emitter', bound)
    native_case = (manager, case['case'][1], case['case'][2], case['site'])
    with selected(db, native_case) as actor:
        transaction = db.get_transaction()
        analysis = planning.analysis(db, actor, case['site'])
        before = tuple(db.connection().execute(select(PMSTask.__table__.c.start_date, PMSTask.__table__.c.due_date).where(PMSTask.__table__.c.id == case['task'])).one())
        planning.apply(db, actor, case['site'], PlanInput(task_id=case['task'], start_date='2026-11-18',
            due_date='2026-11-19', expected_revision=analysis['revision']), commit=False)
        assert db.get_transaction() is transaction and transaction.is_active
        native, scope, parent, frame = captured[-1]
        assert frame in emitter._RETAINED.get(db, ())
        assert emitter.verify_native_emitter(native, scope, parent=parent, frame=frame) is False
        with pytest.raises(HTTPException):
            original(native, scope, parent=parent, frame=frame)
        grant = PackUserGrant.__table__
        db.connection().execute(update(grant).where(grant.c.id == scope.grant_id).values(active=False, revision=grant.c.revision+1))
        with pytest.raises(HTTPException):
            db.commit()
        db.rollback()
        assert frame not in emitter._ISSUED and not emitter._RETAINED.get(db)
        assert tuple(db.connection().execute(select(PMSTask.__table__.c.start_date, PMSTask.__table__.c.due_date).where(PMSTask.__table__.c.id == case['task'])).one()) == before
    # Starting another transaction on the same parent must never revive a token.
    db.connection()
    assert emitter.verify_native_emitter(native, scope, parent=parent, frame=frame) is False


def test_planning_class_stamp_ignores_forged_session_info_without_private_witness():
    from app.business_packs import construction_planning as planning
    called = []
    class Fake:
        pass
    session = Fake()
    session.info = {'shared_actor': (1, 1), 'business_pack_scope': object(),
        'stamp_births': lambda *args: called.append(True)}
    planning._stamp_planning_births(session, object())
    assert not called and session not in planning._PLAN_STAMPS
