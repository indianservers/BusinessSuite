"""Exact source descriptors observed during genuine native Team births."""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.business_packs import construction_outbox as sources
from app.models.notification import Notification
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_construction_workspace_members import workspace, person, command
from tests.test_construction_workspaces import ROOT


def test_native_team_notice_and_email_have_exact_source_pointers(client, db, workspace, monkeypatch):
    _, target = person(db, workspace['case'])
    target_id = target.id
    seen = []
    original_notice = sources.notice_identity
    original_email = sources.notification_email_identity

    def notice(native, row, scope):
        expected = original_notice(native, row, scope)
        assert set(expected) == {'source_table', 'source_key'}
        assert expected == {'source_table': 'pms_workspace_members', 'source_key': str(native._member_plan.root.id)}
        member = row._suite_source_record
        row._suite_source_record = None
        try:
            with pytest.raises(HTTPException) as denied:
                original_notice(native, row, scope)
            assert denied.value.status_code == 403
        finally:
            row._suite_source_record = member
        title = row.title
        row.title = 'Unrelated notice'
        try:
            with pytest.raises(HTTPException):
                original_notice(native, row, scope)
        finally:
            row.title = title
        seen.append(('notice', expected))
        return expected

    def email(native, row, scope):
        expected = original_email(native, row, scope)
        assert expected == {'source_table': 'notifications', 'source_key': str(native._member_plan.notice.id)}
        pointer = row._suite_source_record
        row._suite_source_record = Notification()
        try:
            with pytest.raises(HTTPException) as denied:
                original_email(native, row, scope)
            assert denied.value.status_code == 403
        finally:
            row._suite_source_record = pointer
        recipient = row.recipient_user_id
        row.recipient_user_id = scope.user_id
        try:
            with pytest.raises(HTTPException):
                original_email(native, row, scope)
        finally:
            row.recipient_user_id = recipient
        seen.append(('email', expected))
        return expected

    monkeypatch.setattr(sources, 'notice_identity', notice)
    monkeypatch.setattr(sources, 'notification_email_identity', email)
    data = command(target_id)
    response = client.post(ROOT + f'/workspaces/{workspace["id"]}/member-definitions',
        headers=workspace['headers'], json=data)
    assert response.status_code == 201, response.text
    assert {kind for kind, _ in seen} == {'notice', 'email'}
    prior = list(seen)
    retry = client.post(ROOT + f'/workspaces/{workspace["id"]}/member-definitions',
        headers=workspace['headers'], json=data)
    assert retry.status_code == 201 and retry.json() == response.json()
    assert seen == prior


def test_source_descriptors_reject_detached_or_invented_notices():
    from types import SimpleNamespace
    from app.models.email_outbox import EmailOutbox
    for operation, row in ((sources.notice_identity, Notification()),
            (sources.notification_email_identity, EmailOutbox())):
        with pytest.raises(HTTPException) as denied:
            operation(SimpleNamespace(), row, SimpleNamespace())
        assert denied.value.status_code == 403


def test_emitter_verifier_wrapper_passes_exact_frame_positionally(monkeypatch):
    from app.business_packs import construction_emitter
    native, scope, parent, frame = object(), object(), object(), object()
    seen = []
    def verify(received_native, received_scope, *, parent, frame):
        seen.append((received_native, received_scope, parent, frame))
        return False
    monkeypatch.setattr(construction_emitter, 'verify_native_emitter', verify)
    assert sources.verify_native_emitter(native, scope, parent, frame) is False
    assert seen == [(native, scope, parent, frame)]


@pytest.fixture
def team_delivery(client, db, workspace):
    from app.access.models import AccessPolicy
    from app.models.user import Permission
    from app.models.email_outbox import EmailOutbox
    from app.business_packs.delivery_sources import delivery_allowed
    from app.business_packs.delivery_source_models import PackDeliverySource
    from tests.test_construction_workspaces import post
    # Use a real ordinary native Owner. The catalog's superuser would retain
    # legitimate native access after an AccessPolicy grant is disabled.
    owner_headers, owner = person(db, workspace['case'], role='project_manager',
        actions=('view', 'create', 'edit', 'approve'))
    assert owner.is_superuser is False
    owner_id = owner.id
    if db.query(Permission).filter_by(name='pms_manage_projects').first() is None:
        db.add(Permission(name='pms_manage_projects', module='project_management', description='Native project management'))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=owner_id).one()
    pms = policy.grants['project_management']
    policy.grants = {**policy.grants, 'project_management': {**pms,
        'permissions': ['pms_view', 'pms_manage_projects']}}
    db.commit()
    owned_workspace = post(client, owner_headers, '/workspace-definitions',
        {'request_id': str(uuid4()), 'name': 'Ordinary native Owner ' + uuid4().hex[:8]})
    workspace = {**workspace, 'id': owned_workspace['id'], 'headers': owner_headers,
        'case': (owner, *workspace['case'][1:])}
    _, target = person(db, workspace['case'])
    target_id = target.id
    data = command(target_id)
    member = post(client, workspace['headers'], f'/workspaces/{workspace["id"]}/member-definitions', data)
    notice = db.query(Notification).filter_by(user_id=target_id, event_type='workspace.member_added').one()
    email = db.query(EmailOutbox).filter_by(recipient_user_id=target_id, module='notifications').one()
    # Both channels must have genuine retained certificates; an unowned legacy
    # row's generic delivery fallback is not sufficient for this acceptance.
    certificates = db.query(PackDeliverySource).filter(
        (PackDeliverySource.notification_id == notice.id) | (PackDeliverySource.email_outbox_id == email.id)).all()
    assert len(certificates) == 2
    assert {(row.source_table, row.source_key) for row in certificates} == {
        ('pms_workspace_members', str(member['id'])), ('notifications', str(notice.id))}
    db.commit()
    assert delivery_allowed(db, notice) is True
    assert delivery_allowed(db, email) is True
    return {**workspace, 'target': target_id, 'member': member['id'], 'notice': notice.id, 'email': email.id}


@pytest.mark.parametrize('revocation', ['member_removed', 'workspace_archived', 'native_grant', 'pack_grant'])
def test_current_team_source_revocation_blocks_notice_and_email(db, team_delivery, revocation):
    from datetime import datetime, timezone
    from sqlalchemy import delete
    from app.access.models import AccessPolicy
    from app.apps.project_management.models import PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.business_packs.models import PackUserGrant
    from app.business_packs.delivery_sources import delivery_allowed
    from app.models.email_outbox import EmailOutbox
    case = team_delivery
    if revocation == 'member_removed':
        db.connection().execute(delete(PMSWorkspaceMember.__table__).where(PMSWorkspaceMember.__table__.c.id == case['member']))
    elif revocation == 'workspace_archived':
        db.add(WorkspaceArchive(workspace_id=case['id'], deleted_at=datetime.now(timezone.utc),
            deleted_by=case['case'][0].id, batch_key=uuid4().hex))
    elif revocation == 'native_grant':
        row = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['target']).one()
        row.grants = {**row.grants, 'project_management': {'enabled': False, 'actions': [], 'permissions': []}}
    else:
        row = db.query(PackUserGrant).filter_by(user_id=case['target'], context_id=case['case'][2]).one()
        row.active = False
    db.commit()
    assert delivery_allowed(db, db.get(Notification, case['notice'])) is False
    assert delivery_allowed(db, db.get(EmailOutbox, case['email'])) is False


def test_forged_current_member_workspace_cannot_reuse_delivery_certificate(client, db, team_delivery):
    from sqlalchemy import update
    from app.apps.project_management.models import PMSWorkspaceMember
    from app.models.email_outbox import EmailOutbox
    from app.business_packs.delivery_sources import delivery_allowed
    from tests.test_construction_workspaces import post
    case = team_delivery
    other = post(client, case['headers'], '/workspace-definitions',
        {'request_id': str(uuid4()), 'name': 'Other genuine workspace ' + uuid4().hex[:8]})
    # Keep the same certified source identity and recipient, but forge its
    # canonical parent to a different genuinely owned workspace.
    db.connection().execute(update(PMSWorkspaceMember.__table__).where(
        PMSWorkspaceMember.__table__.c.id == case['member']).values(workspace_id=other['id']))
    db.commit()
    assert delivery_allowed(db, db.get(Notification, case['notice'])) is False
    assert delivery_allowed(db, db.get(EmailOutbox, case['email'])) is False


@pytest.mark.parametrize('revocation', ['workspace_management', 'native', 'pack'])
def test_issuer_revocation_blocks_both_channels_while_recipient_remains_authorized(db, team_delivery, revocation):
    from app.access.models import AccessPolicy
    from app.apps.project_management.models import PMSWorkspaceMember
    from app.business_packs.models import PackUserGrant
    from app.business_packs.delivery_source_models import PackDeliverySource
    from app.business_packs.delivery_sources import delivery_allowed, _reader
    from app.models.email_outbox import EmailOutbox
    case = team_delivery
    issuer_id = case['case'][0].id
    certificate = db.query(PackDeliverySource).filter_by(notification_id=case['notice']).one()
    assert certificate.actor_user_id == issuer_id and issuer_id != case['target']
    if revocation == 'workspace_management':
        db.query(PMSWorkspaceMember).filter_by(workspace_id=case['id'], user_id=issuer_id).one().role = 'Member'
    elif revocation == 'native':
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=issuer_id).one()
        policy.grants = {**policy.grants, 'project_management': {'enabled': False, 'actions': [], 'permissions': []}}
    else:
        db.query(PackUserGrant).filter_by(context_id=case['case'][2], user_id=issuer_id).one().active = False
    db.commit()
    # Exercise the real recipient predicate with its unchanged retained
    # certificate, not a fabricated issuer-as-recipient certificate.
    with _reader(db, case['target'], certificate, 'project_management') as (native, recipient, scope):
        assert sources.source_allowed(native, certificate, recipient, scope) is True
    assert delivery_allowed(db, db.get(Notification, case['notice'])) is False
    assert delivery_allowed(db, db.get(EmailOutbox, case['email'])) is False


def test_issuer_callback_rejects_nonpersistent_or_unbound_principals():
    from types import SimpleNamespace
    from app.models.user import User
    for actor in (SimpleNamespace(id=1), User(id=1, is_active=True)):
        assert sources.issuer_allowed(SimpleNamespace(), SimpleNamespace(), actor, SimpleNamespace()) is False


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
@pytest.mark.parametrize('dual', [False, True])
def test_selected_specialist_context_cannot_manage_team_even_with_construction_assignment(
        client, db, workspace, pack, role, dual):
    from tests.test_business_pack_http_integration import grant
    from tests.test_construction_workspaces import post
    if dual:
        construction_headers, actor = person(db, workspace['case'], role='project_manager', actions=('view','create','edit','approve'))
        actor_id = actor.id
        post(client, workspace['headers'], f'/workspaces/{workspace["id"]}/member-definitions', command(actor_id, 'Admin'))
        context, _ = grant(db, actor, workspace['case'][1], pack, role)
        headers = {**construction_headers, 'X-Suite-Pack-Context': str(context.id)}
        valid = client.get(ROOT + f'/workspaces/{workspace["id"]}/member-options', headers=construction_headers)
        assert valid.status_code == 200, valid.text
    else:
        headers, actor = person(db, workspace['case'], pack=pack, role=role)
    _, target = person(db, workspace['case'])
    response = client.post(ROOT + f'/workspaces/{workspace["id"]}/member-definitions',
        headers=headers, json=command(target.id))
    assert response.status_code == 403, response.text
