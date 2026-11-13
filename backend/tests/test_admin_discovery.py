import pytest
from app.core.security import create_access_token
from app.models.company import Company, Branch
from app.models.user import User
from app.access.models import AccessMembership
from app.shared.models import ServicePolicy
from app.apps.project_management.models import PMSWorkspace
from tests.tenant_test_utils import assign_company
from tests.test_pms_workspaces import middleware_database


@pytest.fixture
def directory(db, middleware_database):
    if not db.get(Company, 1):
        db.add(Company(id=1, name='First company', is_active=True))
    second = Company(name='Other company', is_active=True)
    db.add(second); db.flush()
    first_branch = Branch(company_id=1, name='First branch', is_active=True)
    second_branch = Branch(company_id=second.id, name='Foreign branch', is_active=True)
    db.add_all([first_branch, second_branch]); db.flush()
    platform = User(email='platform-discovery@example.test', hashed_password='unused', is_superuser=True, is_active=True)
    admin = User(email='company-discovery@example.test', hashed_password='unused', is_active=True)
    regular = User(email='regular-discovery@example.test', hashed_password='unused', is_active=True)
    db.add_all([platform, admin, regular]); db.flush()
    for user in [platform, admin, regular]:
        assign_company(db, user, 1)
    membership = db.query(AccessMembership).filter_by(user_id=admin.id, company_id=1).first()
    if membership is None:
        membership = AccessMembership(user_id=admin.id, company_id=1, active=True)
        db.add(membership)
    membership.is_admin = True
    for company, branch, ref, name, status in [(1, first_branch.id, 'local', 'Private local space', 'Archived'),
            (second.id, second_branch.id, 'foreign', 'Private foreign space', 'Active')]:
        db.add(ServicePolicy(organization_id=company, scope_key=f'workspace:hrms:{company}:{branch}:{ref}',
            kind='module_workspace', module_key='hrms', updated_by=regular.id, values_json={'name':name, 'status':status, 'visibility':'private', 'owner_id':regular.id}))
    native = PMSWorkspace(name='Native foreign project workspace', organization_id=second.id)
    db.add(native); db.commit()
    return platform, admin, regular, first_branch, second_branch, native


def headers(user):
    return {'Authorization':'Bearer '+create_access_token(user.id), 'X-Suite-Organization':'1', 'X-Suite-Branch':'all'}


def test_platform_branch_options_span_companies_without_widening_business_context(client, directory):
    platform, _, _, local, foreign, _ = directory
    response = client.get('/api/v1/branches/context', headers=headers(platform))
    assert response.status_code == 200, response.text
    data = response.json()
    assert {local.id, foreign.id} <= {b['id'] for b in data['platform_branches']}
    assert foreign.id not in {b['id'] for b in data['branches']}
    foreign_choice = next(b for b in data['platform_branches'] if b['id'] == foreign.id)
    assert foreign_choice['company_id'] == foreign.company_id
    assert foreign_choice['company_name'] == 'Other company'
    switched = client.get('/api/v1/access/me', headers={**headers(platform), 'X-Suite-Organization':str(foreign.company_id), 'X-Suite-Branch':str(foreign.id)})
    assert switched.status_code == 200, switched.text
    assert switched.json()['companyId'] == foreign.company_id


def test_platform_workspace_discovery_includes_private_archived_and_native_foreign_workspaces(client, directory):
    platform, _, _, _, foreign, native = directory
    response = client.get('/api/v1/branches/workspaces', headers=headers(platform))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['all_companies']
    assert {'Private local space', 'Private foreign space', native.name} <= {w['name'] for w in data['items']}
    row = next(w for w in data['items'] if w['name'] == 'Private foreign space')
    assert row['branch_id'] == foreign.id and row['company_id'] == foreign.company_id
    assert not any('members' in row or 'values_json' in row for row in data['items'])


def test_company_admin_sees_only_own_company_and_cannot_switch_to_foreign_branch(client, directory):
    _, admin, _, local, foreign, _ = directory
    response = client.get('/api/v1/branches/workspaces', headers=headers(admin))
    assert response.status_code == 200, response.text
    assert not response.json()['all_companies']
    assert {w['company_id'] for w in response.json()['items']} == {1}
    assert any(w['name'] == 'Private local space' for w in response.json()['items'])
    choices = client.get('/api/v1/branches/context', headers=headers(admin)).json()
    assert 'platform_branches' not in choices
    assert local.id in {b['id'] for b in choices['branches']}
    assert foreign.id not in {b['id'] for b in choices['branches']}
    denied = client.get('/api/v1/access/me', headers={**headers(admin), 'X-Suite-Organization':str(foreign.company_id), 'X-Suite-Branch':str(foreign.id)})
    assert denied.status_code == 403


def test_regular_user_cannot_use_admin_workspace_discovery(client, directory):
    assert client.get('/api/v1/branches/workspaces', headers=headers(directory[2])).status_code == 403
