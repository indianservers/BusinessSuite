from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.business_packs.request_scope import bind_request_scope, classify_route, RouteKind, authorization_fingerprint
from app.business_packs.access import resolve_context
from app.business_packs.models import PackUserGrant
from app.branches.models import BranchGrant
from app.branches.service import context
from tests.test_business_pack_access import packs


def request(path='/api/v1/srm/products', *, method='GET', branch=None, selected=None,expected=None):
    headers = []
    if expected is not None:headers.append((b'x-suite-expected-pack-realm',str(expected).encode()))
    if branch is not None: headers.append((b'x-suite-branch', str(branch).encode()))
    if selected is not None: headers.append((b'x-suite-pack-context', str(selected).encode()))
    return Request({'type': 'http', 'method': method, 'path': path, 'headers': headers, 'query_string': b'', 'scheme': 'http', 'server': ('test', 80)})


@pytest.fixture
def bound(packs):
    p = packs
    p.db.add(BranchGrant(company_id=1, branch_id=p.branches['a'].id, user_id=p.users['doctor'].id, can_write=True))
    p.db.commit()
    return p


def test_real_scope_raw_selector_nested_binding_and_exception_cleanup(bound):
    p, actor = bound, bound.users['doctor']
    r = request(branch=p.branches['a'].id, selected=p.contexts['doctor'].id)
    fresh = context(p.db, actor, 1, str(p.branches['a'].id))
    with pytest.raises(RuntimeError):
        with bind_request_scope(p.db, actor, r, fresh) as scope:
            assert scope.context_id == p.contexts['doctor'].id
            assert p.db.info['business_pack_scope'] == scope
            with bind_request_scope(p.db, actor, r) as nested: assert nested == scope
            assert p.db.info['business_pack_scope'] == scope
            raise RuntimeError('native route failed')
    assert 'business_pack_scope' not in p.db.info and 'business_pack_request_binding' not in p.db.info


@pytest.mark.parametrize('selected', ['', 'invalid', '0', '-1', '1.5', '１２', '999999'])
def test_explicit_bad_selector_never_falls_back(bound, selected):
    p = bound
    with pytest.raises(HTTPException) as error:
        with bind_request_scope(p.db, p.users['doctor'], request(branch=p.branches['a'].id, selected=selected)): pass
    assert error.value.status_code == 403
    assert 'business_pack_scope' not in p.db.info


def test_prebound_context_and_even_explicit_legacy_none_cannot_switch(bound):
    p = bound; actor = p.users['doctor']
    r = request(branch=p.branches['a'].id, selected=p.contexts['doctor'].id)
    p.db.info['business_pack_scope'] = None
    with pytest.raises(HTTPException):
        with bind_request_scope(p.db, actor, r): pass
    assert p.db.info['business_pack_scope'] is None
    p.db.info.pop('business_pack_scope')
    with bind_request_scope(p.db, actor, r) as scope:
        p.db.add(PackUserGrant(company_id=1, branch_id=p.branches['a'].id, context_id=p.contexts['chef'].id,
            user_id=actor.id, role='chef'))
        p.db.commit()
        with pytest.raises(HTTPException):
            with bind_request_scope(p.db, actor, request(branch=p.branches['a'].id, selected=p.contexts['chef'].id)): pass
        assert p.db.info['business_pack_scope'] == scope


def test_personal_and_exact_control_recovery_preserve_existing_scope(bound):
    p = bound; actor = p.users['doctor']
    r = request(branch=p.branches['a'].id, selected=p.contexts['doctor'].id)
    with bind_request_scope(p.db, actor, r) as scope:
        for path, method in [('/api/v1/auth/logout', 'POST'), ('/api/v1/access/settings/business-packs/configuration', 'GET')]:
            with bind_request_scope(p.db, actor, request(path, method=method, selected='invalid', branch='invalid')) as nested:
                assert nested == scope and p.db.info['business_pack_scope'] == scope
    with bind_request_scope(p.db, actor, request('/api/v1/auth/logout', method='POST', selected='invalid')) as scope:
        assert scope is None
    assert 'business_pack_scope' not in p.db.info


def test_revoked_history_does_not_fall_back_and_stale_native_branch_is_rejected(bound):
    p = bound; actor = p.users['doctor']
    r = request(branch=p.branches['a'].id)
    fresh = context(p.db, actor, 1, str(p.branches['a'].id))
    with pytest.raises(HTTPException):
        with bind_request_scope(p.db, actor, r, replace(fresh, writable=frozenset())): pass
    p.grants['doctor'].active = False; p.db.commit()
    with pytest.raises(HTTPException) as error:
        with bind_request_scope(p.db, actor, r): pass
    assert error.value.status_code == 403


@pytest.mark.parametrize('path', ['/api/v1/access/private-records', '/api/v1/access/settings/business-packs/configuration/export',
    '/api/v1/access/settings/business-profile/effective', '/api/v1/access/settings/defaults/effective',
    '/api/v1/auth/me/other', '/api/v1/branches/records/availability'])
def test_unknown_and_effective_paths_are_operational(path):
    assert classify_route('GET', path) is RouteKind.OPERATIONAL


def test_sync_identity_contains_exact_context_and_each_revision(bound):
    p = bound; actor = p.users['doctor']
    scope = resolve_context(p.db, actor, context(p.db, actor, 1, str(p.branches['a'].id)), p.contexts['doctor'].id)
    before = authorization_fingerprint(scope)
    for field in ('context_revision', 'activation_revision', 'grant_revision', 'context_id', 'branch_id'):
        assert authorization_fingerprint(replace(scope, **{field: getattr(scope, field) + 1})) != before
    assert authorization_fingerprint(None) != before
    with pytest.raises(TypeError): authorization_fingerprint(SimpleNamespace(context_id=scope.context_id))


def test_truly_unconfigured_branch_keeps_explicit_legacy_binding_immutable(bound):
    p = bound; actor = p.users['doctor']
    p.db.add(BranchGrant(company_id=1, branch_id=p.branches['unconfigured'].id, user_id=actor.id, can_write=True)); p.db.commit()
    with bind_request_scope(p.db, actor, request(branch=p.branches['unconfigured'].id)) as legacy:
        assert legacy is None and 'business_pack_scope' in p.db.info
        with pytest.raises(HTTPException):
            with bind_request_scope(p.db, actor, request(branch=p.branches['a'].id, selected=p.contexts['doctor'].id)): pass
        assert p.db.info['business_pack_scope'] is None
    assert 'business_pack_scope' not in p.db.info


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/v1/access/users'), ('POST', '/api/v1/access/changes/preview'),
    ('PUT', '/api/v1/access/roles/12'), ('GET', '/api/v1/access/control/security'),
    ('GET', '/api/v1/access/settings/options/security'), ('GET', '/api/v1/access/settings/history/business-profile'),
    ('POST', '/api/v1/access/settings/starter-values/apply'), ('GET', '/api/v1/access/onboarding'),
    ('PUT', '/api/v1/auth/sessions/12/revoke'), ('POST', '/api/v1/auth/password-policies/12/enforce-mfa'),
    ('POST', '/api/v1/company/departments/'), ('PUT', '/api/v1/company/designations/3'),
    ('POST', '/api/v1/access/control/units/branches'), ('PUT', '/api/v1/access/control/modules/hrms'),
    ('POST', '/api/v1/branches/ownership/assign'), ('POST', '/api/v1/branches/records/share'),
])
def test_audited_administration_method_paths_are_control(method, path):
    assert classify_route(method, path) is RouteKind.CONTROL


@pytest.mark.parametrize('method,path', [
    ('POST', '/api/v1/access/users/export'), ('GET', '/api/v1/access/roles/12/records'),
    ('GET', '/api/v1/access/settings/options/private-records'), ('GET', '/api/v1/access/control/units/customers'),
    ('POST', '/api/v1/access/control/units/payroll'), ('GET', '/api/v1/company/org-chart'),
    ('POST', '/api/v1/company/headcount-plans'), ('GET', '/api/v1/branches/ownership/unassigned'),
    ('POST', '/api/v1/access/control/security'), ('GET', '/api/v1/access/ai/search'),
])
def test_operational_lookalikes_and_wrong_methods_stay_scoped(method, path):
    assert classify_route(method, path) is RouteKind.OPERATIONAL


def test_actual_admin_repair_without_operational_grant_still_uses_native_authority(bound):
    from app.business_packs import service
    p = bound; actor = p.users['admin']
    # Active history exists, but company admin has no operational PackUserGrant.
    r = request('/api/v1/access/settings/business-packs/configuration', selected='stale', branch='stale')
    with bind_request_scope(p.db, actor, r):
        assert service.configuration(p.db, actor)['company_id'] == 1
        assert 'business_pack_scope' not in p.db.info
    with pytest.raises(HTTPException):
        with bind_request_scope(p.db, actor, request(branch=p.branches['a'].id)): pass


def test_personal_method_inventory_matches_actual_native_decorators():
    import ast
    from pathlib import Path
    from app.business_packs.request_scope import _PERSONAL
    actual = set()
    for module in ('auth', 'notifications'):
        tree = ast.parse((Path(__file__).parents[1] / f'app/api/v1/{module}.py').read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.args and isinstance(decorator.args[0], ast.Constant):
                    actual.add((decorator.func.attr.upper(), f'/api/v1/{module}' + decorator.args[0].value))
    assert _PERSONAL <= actual
    assert {(method, path) for method, path in _PERSONAL if path.startswith('/api/v1/notifications')} == {('GET', '/api/v1/notifications/summary')}
    assert ('PUT', '/api/v1/auth/sessions/me/{session_id}/revoke') in actual


def test_control_inventory_has_no_invented_native_methods_or_routes():
    import ast
    from pathlib import Path
    from app.business_packs.request_scope import _ADMIN_ROUTES
    root = Path(__file__).parents[1] / 'app'
    modules = {'access/api.py': '/api/v1/access', 'access/control.py': '/api/v1/access/control',
        'access/homepage_banner.py': '/api/v1/access/homepage-banner', 'access/launcher_preferences.py': '/api/v1/access/launcher-preferences',
        'access/signup_onboarding.py': '/api/v1/access/onboarding', 'access/settings_hub.py': '/api/v1/access/settings',
        'api/v1/auth.py': '/api/v1/auth', 'api/v1/company.py': '/api/v1/company', 'branches/api.py': '/api/v1/branches'}
    actual = set()
    for filename, prefix in modules.items():
        for node in ast.walk(ast.parse((root / filename).read_text())):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.args and isinstance(decorator.args[0], ast.Constant):
                    actual.add((decorator.func.attr.upper(), prefix + decorator.args[0].value))
    assert set(_ADMIN_ROUTES) <= actual



def test_expected_realm_is_restrictive_and_does_not_trap_repair(bound):
    p=bound;actor=p.users['doctor'];branch=p.branches['a'].id;selected=p.contexts['doctor'].id
    with bind_request_scope(p.db,actor,request(branch=branch,selected=selected,expected='pack')) as scope:
        assert scope.context_id==selected
    for expected,status in [('legacy',409),('invalid',403),('',403)]:
        with pytest.raises(HTTPException) as error:
            with bind_request_scope(p.db,actor,request(branch=branch,selected=selected,expected=expected)):pass
        assert error.value.status_code==status
        assert 'business_pack_scope' not in p.db.info
    with bind_request_scope(p.db,actor,request('/api/v1/auth/logout',method='POST',expected='invalid')) as scope:
        assert scope is None
