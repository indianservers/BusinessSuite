"""Genuine native Construction Team UI and retained notification/email origins."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_
from app.models.user import User
from app.models.notification import Notification
from app.models.email_outbox import EmailOutbox
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSProject
from app.business_packs.delivery_source_models import PackDeliverySource
from app.business_packs.models import PackRecordOwnership
from app.branches.models import BranchOwnership
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_construction_workspace_members import person


def test_native_construction_team_member_ui_has_certified_delivery_chain(client, db, construction, catalog, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from app.business_packs.delivery_sources import delivery_allowed
    actor, branch, context_id, project_id = construction
    _, target = person(db, construction)
    target_id = target.id
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    before_users = db.query(User).count()
    before_workspaces = db.query(PMSWorkspace).count()
    before_projects = db.query(PMSProject).count()
    before_members = db.query(PMSWorkspaceMember).count()
    assert not db.query(Notification).filter_by(user_id=target_id, event_type='workspace.member_added').count()
    assert not db.query(EmailOutbox).filter_by(recipient_user_id=target_id, module='notifications').count()
    site_name, site_key = 'Team UI canonical site', 'TEAM-'+uuid4().hex[:10]
    identity = client.get('/api/v1/auth/me', headers=headers)
    access = client.get('/api/v1/access/me', headers=headers)
    assert identity.status_code == access.status_code == 200
    user = identity.json()
    primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
    user.update(role=primary, primary_role=primary, access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'construction-team-native.cjs')
    with tempfile.TemporaryDirectory(prefix='construction-team-browser-') as temporary:
        auth_file = Path(temporary) / 'identity.json'
        auth_file.write_text(json.dumps({'token': headers['Authorization'].split(' ', 1)[1], 'user': user,
            'branch': str(branch), 'context': str(context_id), 'project': project_id,
            'workspace_name': 'Native Team UI workspace', 'site_name': site_name,
            'site_key': site_key, 'target_id': target_id}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        test_control_center_real_browser(client, db, None, headers)
    db.expire_all()
    proof = json.loads((Path(__file__).resolve().parents[2] / '.local' / 'construction-team-browser-proof.json').read_text(encoding='utf-8'))
    assert proof['stage'] == 'complete' and proof['target_id'] == target_id
    assert db.query(User).count() == before_users
    assert db.query(PMSWorkspace).count() == before_workspaces + 1
    assert db.query(PMSProject).count() == before_projects + 1
    assert db.query(PMSWorkspaceMember).count() == before_members + 2
    workspace = db.get(PMSWorkspace, proof['workspace_id'])
    site = db.get(PMSProject, proof['site_id'])
    assert workspace.name == 'Native Team UI workspace'
    assert site.workspace_id == workspace.id and site.project_key == site_key.strip().upper()
    member = db.get(PMSWorkspaceMember, proof['member']['id'])
    assert (member.workspace_id, member.user_id, member.role) == (workspace.id, target_id, 'Member')
    assert db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace.id, user_id=target_id).count() == 1
    notice = db.query(Notification).filter_by(user_id=target_id, event_type='workspace.member_added').one()
    email = db.query(EmailOutbox).filter_by(recipient_user_id=target_id, module='notifications').one()
    assert notice.company_id == email.organization_id == 1
    assert notice.action_url == f'/pms/workspaces?workspace={workspace.id}'
    assert (notice.related_entity_type, notice.related_entity_id) == (None, None)
    assert email.status == 'queued' and email.attempts == 0
    certificates = db.query(PackDeliverySource).filter(or_(PackDeliverySource.notification_id == notice.id,
        PackDeliverySource.email_outbox_id == email.id)).all()
    assert len(certificates) == 2
    assert {(row.notification_id, row.email_outbox_id, row.source_table, row.source_key) for row in certificates} == {
        (notice.id, None, 'pms_workspace_members', str(member.id)),
        (None, email.id, 'notifications', str(notice.id))}
    for row in certificates:
        assert (row.company_id, row.branch_id, row.context_id, row.pack_key, row.recipient_user_id) == (1, branch, context_id, 'construction', target_id)
        assert len(row.payload_sha256) == 64
    for row in (workspace, member, notice, email):
        native = db.get(BranchOwnership, (row.__tablename__, str(row.id)))
        pack = db.query(PackRecordOwnership).filter_by(resource_table=row.__tablename__, resource_key=str(row.id)).one()
        assert (native.company_id, native.branch_id, pack.company_id, pack.branch_id, pack.context_id) == (1, branch, 1, branch, context_id)
    db.commit()
    assert delivery_allowed(db, notice) is True
    assert delivery_allowed(db, email) is True
