import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.business_packs.discovery import discover_contexts
from app.business_packs.models import PackUserGrant
from app.branches.models import BranchGrant
from app.core.deps import get_current_user, get_db
from app.access.api import router
from tests.test_business_pack_access import packs
from tests.test_business_pack_request_scope import request


@pytest.fixture
def discovery(packs):
    p = packs
    for actor, branch in [('doctor', 'a'), ('chef', 'a'), ('builder', 'b')]:
        p.db.add(BranchGrant(company_id=1, branch_id=p.branches[branch].id, user_id=p.users[actor].id, can_write=True))
    for user in p.users.values(): user._suite_grants = None
    p.db.commit()
    app = FastAPI(); app.include_router(router, prefix='/api/v1')
    app.dependency_overrides[get_db] = lambda: p.db
    p.selected_actor = p.users['doctor']
    app.dependency_overrides[get_current_user] = lambda: p.selected_actor
    with TestClient(app) as client:
        p.client = client
        yield p


@pytest.mark.parametrize('actor,key', [('doctor', 'hospital'), ('chef', 'restaurant'), ('builder', 'construction')])
def test_real_access_me_returns_only_verified_exact_pairs(discovery, actor, key):
    p = discovery; p.selected_actor = p.users[actor]
    response = p.client.get('/api/v1/access/me')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['companyId'] == 1 and 'grants' in data and 'permissions' in data
    choices = data['businessPacks']
    assert [row['packKey'] for row in choices['contexts']] == [key]
    assert choices['contexts'][0]['contextId'] == p.contexts[actor].id
    assert choices['contexts'][0]['branchId'] == p.contexts[actor].branch_id
    assert choices['selectedContextId'] is None and choices['selectorRequired'] is True


def test_multiple_grants_remain_pairs_not_cartesian_products(discovery):
    p = discovery; actor = p.users['doctor']
    p.db.add(PackUserGrant(company_id=1, branch_id=p.branches['a'].id, context_id=p.contexts['chef'].id, user_id=actor.id, role='chef'))
    p.db.commit()
    data = p.client.get('/api/v1/access/me').json()['businessPacks']
    assert {(row['branchId'], row['packKey']) for row in data['contexts']} == {(p.branches['a'].id, 'hospital'), (p.branches['a'].id, 'restaurant')}
    bounded = discover_contexts(p.db, actor, request(), limit=1)
    assert len(bounded['contexts']) == 1 and bounded['hasMore'] is True


def test_unconfigured_branch_does_not_require_another_branch_pack(discovery):
    p = discovery
    p.db.add(BranchGrant(company_id=1, branch_id=p.branches['unconfigured'].id,
                        user_id=p.users['doctor'].id, can_write=True))
    p.db.commit()
    headers = {'X-Suite-Branch': str(p.branches['unconfigured'].id)}
    data = p.client.get('/api/v1/access/me', headers=headers).json()['businessPacks']
    assert data['selectorRequired'] is False and data['selectionState'] == 'none'
    assert [row['contextId'] for row in data['contexts']] == [p.contexts['doctor'].id]
    p.db.query(BranchGrant).filter_by(user_id=p.users['doctor'].id,
                                     branch_id=p.branches['a'].id).delete()
    p.db.commit()
    data = p.client.get('/api/v1/access/me', headers=headers).json()['businessPacks']
    assert data['selectorRequired'] is False and data['contexts'] == []


@pytest.mark.parametrize('selected', ['invalid', '', '0', '999999'])
def test_invalid_or_stale_header_never_traps_native_control_identity(discovery, selected):
    p = discovery
    response = p.client.get('/api/v1/access/me', headers={'X-Suite-Pack-Context': selected, 'X-Suite-Branch': str(p.branches['a'].id)})
    assert response.status_code == 200
    data = response.json()['businessPacks']
    assert data['selectedContextId'] is None and data['selectionState'] == 'invalid'
    assert [row['packKey'] for row in data['contexts']] == ['hospital']


def test_selected_id_requires_fresh_exact_branch_authority(discovery):
    p = discovery
    headers = {'X-Suite-Pack-Context': str(p.contexts['doctor'].id), 'X-Suite-Branch': str(p.branches['a'].id)}
    data = p.client.get('/api/v1/access/me', headers=headers).json()['businessPacks']
    assert data['selectedContextId'] == p.contexts['doctor'].id and data['selectionState'] == 'verified'
    headers['X-Suite-Branch'] = str(p.branches['foreign'].id)
    data = p.client.get('/api/v1/access/me', headers=headers).json()['businessPacks']
    assert data['selectedContextId'] is None and len(data['contexts']) == 1
    p.grants['doctor'].active = False; p.db.commit()
    assert p.client.get('/api/v1/access/me').json()['businessPacks']['contexts'] == []


def test_company_admin_has_no_implicit_operational_context(discovery):
    p = discovery; p.selected_actor = p.users['admin']
    response = p.client.get('/api/v1/access/me')
    assert response.status_code == 200
    assert response.json()['isAccessAdmin'] is True
    assert response.json()['businessPacks']['contexts'] == []


def test_partial_schema_keeps_native_identity_but_never_returns_operational_permit(discovery, monkeypatch):
    p = discovery
    def partial(db): raise HTTPException(503, 'Missing schema')
    monkeypatch.setattr('app.business_packs.discovery._installed', partial)
    response = p.client.get('/api/v1/access/me')
    assert response.status_code == 200 and response.json()['companyId'] == 1
    data = response.json()['businessPacks']
    assert data['state'] == 'unavailable' and data['reason'] == 'schema_unavailable'
    assert data['contexts'] == [] and data['selectedContextId'] is None


def test_discovery_ignores_stale_bound_branch_cache_and_freshly_checks_native_grants(discovery):
    p = discovery
    p.db.info['branch_context'] = p.ctx()  # Previously allowed broader branches.
    p.db.query(BranchGrant).filter_by(user_id=p.users['doctor'].id).delete(); p.db.commit()
    data = p.client.get('/api/v1/access/me').json()['businessPacks']
    assert data['contexts'] == [] and data['selectedContextId'] is None


def test_discovery_hides_context_when_native_module_license_is_unavailable(discovery, monkeypatch):
    p = discovery
    monkeypatch.setattr('app.access.entitlements.states', lambda db, company: {'srm': False})
    response = p.client.get('/api/v1/access/me')
    assert response.status_code == 200 and response.json()['businessPacks']['contexts'] == []
