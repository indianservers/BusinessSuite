"""Pack-local recipient ACL over genuine native queued task/assignment emails."""
from datetime import datetime, timezone
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import event, update, delete

from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSWorkspaceMember, PMSProjectMember, PMSTask, PMSTaskAssignee
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership
from app.business_packs.construction_definition import _DefinitionSession
from app.business_packs.construction_outbox import source_identity, source_access
from app.models.email_outbox import EmailOutbox
from tests.test_construction_definition import definition, post, project_body, task_body
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity


@pytest.fixture
def mail(client, db, definition, monkeypatch):
    from tests.test_business_pack_http_integration import native_actor, grant
    case = definition
    _, resource = native_actor(db, case['branch'])
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=resource.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True, 'permissions': ['pms_view'],
        'actions': ['view'], 'scope': 'organization'}}
    db.add(PMSWorkspaceMember(workspace_id=case['workspace'], user_id=resource.id, role='Member'))
    db.commit()
    _, user_grant = grant(db, resource, case['branch'], 'construction', 'site_engineer', db.get(PackContext, case['context']))
    case['resource'], case['grant'] = resource.id, user_grant.id
    case['project'] = post(client, case['headers'], '/site-projects', project_body(case))['id']
    captured = []
    original = _DefinitionSession.__init__
    def instrument(native, *args, **kwargs):
        original(native, *args, **kwargs)
        def pending(session, *_):
            for row in tuple(session.new):
                if type(row) is EmailOutbox:
                    scope = db.info['business_pack_scope']
                    captured.append({'identity': source_identity(native, row, scope), 'row': row, 'scope': scope})
        event.listen(native, 'before_flush', pending)
    monkeypatch.setattr(_DefinitionSession, '__init__', instrument)
    case['task'] = post(client, case['headers'], f'/projects/{case["project"]}/wbs-tasks',
        task_body(assignee_user_ids=[resource.id]))['id']
    case['mail'] = [entry for entry in captured if entry['row'].recipient_user_id == resource.id]
    assert {entry['identity']['source_table'] for entry in case['mail']} == {'pms_tasks', 'pms_task_assignees'}
    case['captured'] = captured
    return case


def allowed(db, case, entry):
    return source_access(db, company_id=1, branch_id=case['branch'], context_id=case['context'],
        recipient_user_id=case['resource'], **entry['identity'])


def test_current_engineer_task_and_assignment_native_sources_allowed_without_provider(db, mail, monkeypatch):
    from app.core import email
    monkeypatch.setattr(email, 'send_email', lambda *args, **kwargs: pytest.fail('Source ACL must not call provider'))
    before = dict(db.info)
    for entry in mail['mail']:
        assert allowed(db, mail, entry) is True
    assert db.info == before
    assert db.in_transaction()


@pytest.mark.parametrize('revocation', ['pack', 'native', 'branch', 'inactive', 'task_owner', 'project_owner', 'deleted', 'activation', 'context', 'company'])
def test_dispatch_source_fails_after_current_recipient_or_source_revocation(db, mail, revocation):
    from app.branches.models import BranchGrant
    from app.models.user import User
    case = mail
    if revocation == 'pack':
        db.get(PackUserGrant, case['grant']).active = False
    elif revocation == 'native':
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['resource']).one()
        policy.grants = {**policy.grants, 'project_management': {'enabled': False, 'actions': [], 'permissions': []}}
    elif revocation == 'branch':
        db.query(BranchGrant).filter_by(company_id=1, branch_id=case['branch'], user_id=case['resource']).delete()
    elif revocation == 'inactive':
        db.get(User, case['resource']).is_active = False
    elif revocation == 'activation':
        db.get(PackActivation, db.get(PackContext, case['context']).activation_id).state = 'suspended'
    elif revocation == 'context':
        db.get(PackContext, case['context']).state = 'suspended'
    elif revocation == 'company':
        from app.models.company import Company
        db.get(Company, 1).is_active = False
    elif revocation in {'task_owner', 'project_owner'}:
        table, key = ('pms_tasks', case['task']) if revocation == 'task_owner' else ('pms_projects', case['project'])
        db.connection().execute(delete(PackRecordOwnership.__table__).where(
            PackRecordOwnership.__table__.c.resource_table == table, PackRecordOwnership.__table__.c.resource_key == str(key)))
    else:
        db.get(PMSTask, case['task']).deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert all(allowed(db, case, entry) is False for entry in case['mail'])


def test_assignment_removal_and_current_recipient_change_are_not_bypassed(db, mail):
    case = mail
    assignment = next(entry for entry in case['mail'] if entry['identity']['source_table'] == 'pms_task_assignees')
    task = next(entry for entry in case['mail'] if entry['identity']['source_table'] == 'pms_tasks')
    db.connection().execute(delete(PMSTaskAssignee.__table__).where(PMSTaskAssignee.__table__.c.task_id == case['task'],
        PMSTaskAssignee.__table__.c.user_id == case['resource']))
    db.commit()
    assert allowed(db, case, assignment) is False
    assert allowed(db, case, task) is True
    db.connection().execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == case['task']).values(assignee_user_id=None))
    db.commit()
    assert allowed(db, case, task) is False


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_other_pack_role_cannot_replace_recipient_own_construction_grant(db, mail, pack, role):
    from tests.test_business_pack_http_integration import grant
    from app.models.user import User
    case = mail
    grant(db, db.get(User, case['resource']), case['branch'], pack, role)
    db.get(PackUserGrant, case['grant']).active = False
    db.commit()
    assert all(allowed(db, case, entry) is False for entry in case['mail'])


def test_foreign_source_and_forged_composite_keys_denied(db, mail):
    entry = mail['mail'][0]
    assert source_access(db, company_id=1, branch_id=mail['branch'], context_id=mail['context'],
        recipient_user_id=mail['resource'], source_table='pms_tasks', source_key='999999') is False
    assert source_access(db, company_id=1, branch_id=mail['branch'], context_id=mail['context'],
        recipient_user_id=mail['resource'], source_table='pms_task_assignees', source_key=f'9:{mail["task"]}:9:{mail["resource"]}') is False
    assert source_access(db, company_id=1, branch_id=mail['branch'], context_id=mail['context']+9999,
        recipient_user_id=mail['resource'], **entry['identity']) is False


def test_actual_native_foreign_pack_project_is_denied_despite_native_collaboration(client, db, mail):
    from tests.test_business_pack_http_integration import grant
    case = mail
    foreign = post(client, case['headers'], '/site-projects', project_body(case))['id']
    task = post(client, case['headers'], f'/projects/{foreign}/wbs-tasks', task_body(assignee_user_ids=[case['resource']]))['id']
    entry = {'identity': {'source_table': 'pms_tasks', 'source_key': str(task)}}
    assert allowed(db, case, entry) is True
    context, _ = grant(db, case['actor'], case['branch'], 'hospital', 'doctor')
    owner = PackRecordOwnership.__table__
    db.connection().execute(update(owner).where(owner.c.resource_table == 'pms_projects', owner.c.resource_key == str(foreign)).values(context_id=context.id))
    db.commit()
    assert allowed(db, case, entry) is False


def test_current_owned_child_source_denied_when_its_actual_ancestor_loses_ownership(client, db, mail):
    case = mail
    child = post(client, case['headers'], f'/projects/{case["project"]}/wbs-tasks',
        task_body(parent_task_id=case['task'], assignee_user_ids=[case['resource']]))['id']
    entry = next(item for item in case['captured'] if item['identity'] == {'source_table': 'pms_tasks', 'source_key': str(child)}
        and item['row'].recipient_user_id == case['resource'])
    assert allowed(db, case, entry) is True
    owner = PackRecordOwnership.__table__
    db.connection().execute(delete(owner).where(owner.c.resource_table == 'pms_tasks', owner.c.resource_key == str(case['task'])))
    db.commit()
    assert db.get(PMSTask, child).parent_task_id == case['task']
    assert allowed(db, case, entry) is False


def test_native_own_scope_checks_actual_source_task_without_requiring_unrelated_task_visibility(client, db, mail):
    case = mail
    task = next(entry for entry in case['mail'] if entry['identity']['source_table'] == 'pms_tasks')
    unrelated = post(client, case['headers'], f'/projects/{case["project"]}/wbs-tasks', task_body())['id']
    owner = PackRecordOwnership.__table__
    db.connection().execute(delete(owner).where(owner.c.resource_table == 'pms_tasks', owner.c.resource_key == str(unrelated)))
    db.add(PMSProjectMember(project_id=case['project'], user_id=case['resource'], role='Contributor'))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['resource']).one()
    policy.grants = {**policy.grants, 'project_management': {**policy.grants['project_management'], 'scope': 'own'}}
    db.commit()
    assert allowed(db, case, task) is True, 'An unrelated unassigned task must not hide this assigned source'
    db.connection().execute(delete(PMSTaskAssignee.__table__).where(PMSTaskAssignee.__table__.c.task_id == case['task']))
    db.connection().execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == case['task']).values(
        assignee_user_id=None, reporter_user_id=case['resource']))
    db.commit()
    assert db.get(PMSTask, case['task']).reporter_user_id == case['resource'], 'The recipient still has a genuine source relationship'
    assert allowed(db, case, task) is False, 'Project collaboration cannot bypass the actual native own-task filter'


def test_native_guest_browse_can_receive_without_resource_assignment_eligibility(db, mail):
    case = mail
    db.query(PMSWorkspaceMember).filter_by(workspace_id=case['workspace'], user_id=case['resource']).one().role = 'Guest'
    db.commit()
    assert all(allowed(db, case, entry) is True for entry in case['mail'])


def test_single_native_source_read_has_no_planning_task_count_or_unrelated_ownership_ceiling(db, mail):
    case = mail
    db.connection().execute(PMSTask.__table__.insert(), [dict(project_id=case['project'], task_key=f'UNRELATED-{i}',
        title='Unrelated native task', status='To Do') for i in range(1001)])
    db.commit()
    assert all(allowed(db, case, entry) is True for entry in case['mail'])


@pytest.mark.parametrize('change', ['native', 'pack'])
def test_permission_revoked_during_native_source_check_is_not_recompiled_into_a_grant(db, mail, monkeypatch, change):
    from app.business_packs import construction_outbox as module
    original, calls = module._current_source, []
    def revoke_late(connection, scope, table, key, recipient):
        result = original(connection, scope, table, key, recipient)
        calls.append(True)
        if len(calls) == 2:
            if change == 'native':
                policy = AccessPolicy.__table__
                connection.execute(update(policy).where(policy.c.company_id == 1,
                    policy.c.user_id == mail['resource']).values(status='revoked', version=policy.c.version+1))
            else:
                grant = PackUserGrant.__table__
                connection.execute(update(grant).where(grant.c.id == mail['grant']).values(active=False, revision=grant.c.revision+1))
        return result
    monkeypatch.setattr(module, '_current_source', revoke_late)
    assert allowed(db, mail, mail['mail'][0]) is False
    assert len(calls) == 2


def test_loading_old_email_with_spoofed_source_pointer_cannot_be_adopted(client, db, mail, monkeypatch):
    old = mail['mail'][0]['row']
    original = _DefinitionSession.__init__
    rejected = []
    def instrument(native, *args, **kwargs):
        original(native, *args, **kwargs)
        def try_adopt(session, *_):
            pending = next((row for row in session.new if type(row) is EmailOutbox), None)
            if pending is None or rejected:
                return
            loaded = native.get(EmailOutbox, old.id)
            assert loaded is not None
            loaded._suite_source_record = pending._suite_source_record
            with pytest.raises(HTTPException) as denied:
                source_identity(native, loaded, db.info['business_pack_scope'])
            assert denied.value.status_code == 403
            rejected.append(True)
        event.listen(native, 'before_flush', try_adopt)
    monkeypatch.setattr(_DefinitionSession, '__init__', instrument)
    post(client, mail['headers'], f'/projects/{mail["project"]}/wbs-tasks', task_body(assignee_user_ids=[mail['resource']]))
    assert rejected


@pytest.mark.parametrize('table', ['pms_tasks', 'pms_task_assignees'])
def test_shared_callback_requires_exact_fresh_bound_recipient_scope(db, mail, table):
    from app.models.user import User
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.construction_outbox import source_allowed
    entry = next(item for item in mail['mail'] if item['identity']['source_table'] == table)
    recipient = db.get(User, mail['resource'])
    other_recipient_id = mail['actor'].id
    recipient.organization_id = 1  # The fixture has canonical active company membership.
    # Only callback binding is tested here. The common owner separately proves
    # certificate birth, immutable hash, ownership and legacy classification.
    certificate = SimpleNamespace(company_id=1, branch_id=mail['branch'], context_id=mail['context'],
        pack_key='construction', pack_version=1, recipient_user_id=recipient.id, module='pms', **entry['identity'])
    with native_writer(db, recipient, mail['branch']):
        scope = resolve_context(db, recipient, db.info['branch_context'], mail['context'])
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            assert source_allowed(db, certificate, recipient, scope) is True
            certificate.context_id += 1000
            assert source_allowed(db, certificate, recipient, scope) is False
            certificate.context_id = scope.context_id
            certificate.recipient_user_id = other_recipient_id
            assert source_allowed(db, certificate, recipient, scope) is False
        finally:
            cleanup()
