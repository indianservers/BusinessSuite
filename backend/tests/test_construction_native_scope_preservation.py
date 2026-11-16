"""Ordinary native Owner keeps request authority through private core adapters."""
from uuid import uuid4
import sys

from sqlalchemy import inspect

from app.access.models import AccessPolicy
from app.models.user import User, Permission
from app.apps.project_management.models import PMSWorkspace, PMSProject, PMSTask
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_construction_workspace_members import person
from tests.test_construction_workspaces import post
from tests.test_construction_definition import project_body, task_body


def test_ordinary_native_owner_workspace_site_wbs_preserve_outer_request_scope(
        client, db, construction, monkeypatch):
    from app.access import scope as native_scope
    headers, owner = person(db, construction, role='project_manager',
        actions=('view', 'create', 'edit', 'approve'))
    owner_id = owner.id
    assert owner.is_superuser is False
    if db.query(Permission).filter_by(name='pms_manage_projects').first() is None:
        db.add(Permission(name='pms_manage_projects', module='project_management', description='Native project management'))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=owner_id).one()
    policy.grants = {**policy.grants, 'project_management': {
        **policy.grants['project_management'], 'permissions': ['pms_view', 'pms_manage_projects']}}
    db.commit()
    original = native_scope.install_scope
    observed = []
    fields = ('organization_id', '_suite_grants', '_suite_current_module',
        '_suite_scope_active', '_suite_original_organization', '_suite_permission_objects')

    def metadata():
        return {key: (key in owner.__dict__, owner.__dict__.get(key)) for key in fields}

    def install(native, user, company, grants):
        if native is db or user.id != owner_id:
            return original(native, user, company, grants)
        caller = sys._getframe(1)
        factory = caller.f_code.co_name == '_native' and caller.f_globals.get('__name__') in {
            'app.business_packs.construction_workspaces', 'app.business_packs.construction_definition'}
        if factory:
            assert type(user) is User and inspect(user).persistent
        before = metadata()
        private_principal = inspect(user).session is native if factory else None
        cleanup = original(native, user, company, grants)
        def clean():
            cleanup()
            assert metadata() == before, 'A private native scope cleanup changed the authenticated outer User'
            if factory:
                assert private_principal, 'Private native scope was installed on an outer-session actor'
                observed.append(caller.f_globals['__name__'])
        return clean

    monkeypatch.setattr(native_scope, 'install_scope', install)
    workspace = post(client, headers, '/workspace-definitions',
        {'request_id': str(uuid4()), 'name': 'Ordinary owner scope ' + uuid4().hex[:8]})
    assert observed
    count = len(observed)
    site = post(client, headers, '/site-projects', project_body({'workspace': workspace['id']}))
    assert len(observed) > count
    count = len(observed)
    task = post(client, headers, f'/projects/{site["id"]}/wbs-tasks', task_body())
    assert len(observed) > count
    assert db.get(PMSWorkspace, workspace['id']).organization_id == 1
    assert db.get(PMSProject, site['id']).workspace_id == workspace['id']
    assert db.get(PMSTask, task['id']).project_id == site['id']
