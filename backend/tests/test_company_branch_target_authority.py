"""Branch-definition authority follows the addressed branch, not a stale tab."""
from uuid import uuid4

import pytest

from app.branches.models import BranchGrant, BranchOwnership, BranchPolicy
from app.models.company import Branch
from tests.test_settings_hub import actor


@pytest.mark.parametrize('target_allowed', [False, True])
def test_branch_definition_write_uses_target_native_module_role(client, db, target_allowed):
    base = {'enabled': True, 'role': 'Native company writer',
            'permissions': ['company_manage'], 'actions': ['view', 'configure'],
            'scope': 'organization'}
    headers, user = actor(db, role='company-branch-' + uuid4().hex,
                          permissions=['company_manage'], grants={'hrms': base})
    branches = []
    for index, allowed in enumerate([not target_allowed, target_allowed]):
        branch = Branch(company_id=1, name='Definition branch ' + str(index), is_active=True)
        db.add(branch)
        db.flush()
        branches.append(branch.id)
        db.add(BranchOwnership(company_id=1, branch_id=branch.id, resource_table='branches',
                               resource_key=str(branch.id), source='definition-target-test'))
        db.add(BranchGrant(company_id=1, branch_id=branch.id, user_id=user.id, can_write=True,
                           module_grants={'hrms': {**base, 'actions': ['view', 'configure'] if allowed else ['view']}}))
    db.add(BranchPolicy(company_id=1, user_id=user.id, use_home_branch=False, manage_access=True))
    db.commit()
    response = client.put('/api/v1/company/branches/' + str(branches[1]),
                          headers={**headers, 'X-Suite-Branch': str(branches[0])},
                          json={'name': 'Authorized new branch name'})
    assert response.status_code == (200 if target_allowed else 403), response.text
    db.expire_all()
    assert db.get(Branch, branches[1]).name == (
        'Authorized new branch name' if target_allowed else 'Definition branch 1')
    assert db.get(Branch, branches[0]).name == 'Definition branch 0'
