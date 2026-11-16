"""Request binding primitives, deliberately not mounted in authentication deps.

Classification exempts only enumerated identity/configuration endpoints from
operational context resolution. Their existing native authorization is mandatory.
Unknown paths, including unknown /access paths, are operational and fail closed.
This module installs no record boundary and enables no runtime pack support.
"""
from contextlib import contextmanager
from enum import Enum
import re

from fastapi import HTTPException
from app.branches.service import context as branch_context
from .access import PackScope, resolve_context


class RouteKind(str, Enum):
    PERSONAL = 'personal'
    CONTROL = 'control'
    OPERATIONAL = 'operational'


_PERSONAL = frozenset({
    ('GET', '/api/v1/auth/me'), ('POST', '/api/v1/auth/logout'),
    ('GET', '/api/v1/notifications/summary'),
    ('POST', '/api/v1/auth/change-password'), ('POST', '/api/v1/auth/mfa/setup'),
    ('POST', '/api/v1/auth/mfa/confirm'), ('DELETE', '/api/v1/auth/mfa/disable'),
    ('GET', '/api/v1/auth/sessions/me'), ('PUT', '/api/v1/auth/sessions/me/revoke-others'),
    ('POST', '/api/v1/auth/forgot-password'), ('POST', '/api/v1/auth/reset-password'),
    ('GET', '/api/v1/auth/mfa/status'), ('POST', '/api/v1/auth/mfa/regenerate-recovery-codes'),
})
_CONTROL = frozenset({
    ('GET', '/api/v1/access/me'), ('GET', '/api/v1/access/setup'),
    ('GET', '/api/v1/access/enterprise/branding'), ('GET', '/api/v1/business-os/modules'),
    ('GET', '/api/v1/access/settings'), ('GET', '/api/v1/branches/context'),
    ('GET', '/api/v1/branches/workspaces'), ('GET', '/api/v1/branches/manage'),
    ('POST', '/api/v1/branches'), ('GET', '/api/v1/branches/access/users'),
    ('POST', '/api/v1/branches/ownership/assign'),
    ('POST', '/api/v1/branches/records/share'),
    ('GET', '/api/v1/access/settings/company-profile'), ('PATCH', '/api/v1/access/settings/company-profile'),
    ('GET', '/api/v1/access/settings/defaults/configuration'), ('PUT', '/api/v1/access/settings/defaults/configuration'),
    ('GET', '/api/v1/access/settings/business-profile/configuration'), ('PUT', '/api/v1/access/settings/business-profile/configuration'),
    ('GET', '/api/v1/access/settings/business-profile/onboarding'),
})
_PACK_ROOT = '/api/v1/access/settings/business-packs'
_PACK_EXACT = frozenset({('GET', path) for path in ('catalog', 'configuration', 'readiness', 'history', 'theme')} | {
    ('POST', 'preview'), ('POST', 'activations'), ('POST', 'contexts'), ('POST', 'theme')})
_CONTROL_PATTERNS = (
    ('PATCH|DELETE', r'/api/v1/branches/[1-9][0-9]*'),
    ('POST', r'/api/v1/branches/[1-9][0-9]*/(?:trash|protect|restore)'),
    ('GET|PUT', r'/api/v1/branches/access/[1-9][0-9]*'),
    ('PUT', _PACK_ROOT + r'/contexts/[1-9][0-9]*/grants/[1-9][0-9]*'),
    ('POST', _PACK_ROOT + r'/(?:contexts|activations)/[1-9][0-9]*/activate'),
    ('GET', _PACK_ROOT + r'/contexts/[1-9][0-9]*/(?:master-options|user-options)'),
    ('PUT', _PACK_ROOT + r'/contexts/[1-9][0-9]*/masters'),
    ('POST', _PACK_ROOT + r'/contexts/[1-9][0-9]*/grant-preview'),
)
# Audited native identity/authorization/configuration routes. Dynamic values
# are constrained here and remain independently validated by each native API.
_ADMIN_ROUTES = (
    ('POST', '/api/v1/access/step-up'),
    ('GET', '/api/v1/access/me'),
    ('GET', '/api/v1/access/catalog'),
    ('GET', '/api/v1/access/statistics'),
    ('GET', '/api/v1/access/users'),
    ('GET', '/api/v1/access/users/{user_id}'),
    ('POST', '/api/v1/access/changes/preview'),
    ('POST', '/api/v1/access/changes/apply'),
    ('POST', '/api/v1/access/roles'),
    ('PUT', '/api/v1/access/roles/{role_id}'),
    ('GET', '/api/v1/access/roles/{role_id}/users'),
    ('GET', '/api/v1/access/templates'),
    ('POST', '/api/v1/access/templates'),
    ('PUT', '/api/v1/access/templates/{template_id}'),
    ('POST', '/api/v1/access/users'),
    ('POST', '/api/v1/access/memberships'),
    ('GET', '/api/v1/access/audit'),
    ('GET', '/api/v1/access/report'),
    ('GET', '/api/v1/access/control/organizations'),
    ('POST', '/api/v1/access/control/organizations'),
    ('PUT', '/api/v1/access/control/organizations/{company_id}'),
    ('POST', '/api/v1/access/control/units/{kind}'),
    ('PUT', '/api/v1/access/control/units/{kind}/{unit_id}'),
    ('GET', '/api/v1/access/control/dashboard'),
    ('GET', '/api/v1/access/control/modules'),
    ('PUT', '/api/v1/access/control/modules/{module_key}'),
    ('GET', '/api/v1/access/control/users/{user_id}/360'),
    ('PUT', '/api/v1/access/control/users/{user_id}/identity'),
    ('GET', '/api/v1/access/control/security'),
    ('POST', '/api/v1/access/control/sessions/revoke'),
    ('PUT', '/api/v1/access/control/password-policy'),
    ('GET', '/api/v1/access/control/audit'),
    ('POST', '/api/v1/access/control/super-admins'),
    ('GET', '/api/v1/access/homepage-banner'),
    ('PUT', '/api/v1/access/homepage-banner'),
    ('POST', '/api/v1/access/homepage-banner/upload'),
    ('GET', '/api/v1/access/launcher-preferences'),
    ('PUT', '/api/v1/access/launcher-preferences'),
    ('GET', '/api/v1/access/onboarding'),
    ('POST', '/api/v1/access/onboarding'),
    ('GET', '/api/v1/auth/users'),
    ('POST', '/api/v1/auth/users'),
    ('GET', '/api/v1/auth/permissions'),
    ('GET', '/api/v1/auth/roles'),
    ('POST', '/api/v1/auth/roles'),
    ('PUT', '/api/v1/auth/roles/{role_id}'),
    ('DELETE', '/api/v1/auth/roles/{role_id}'),
    ('GET', '/api/v1/auth/sessions'),
    ('POST', '/api/v1/auth/sessions'),
    ('PUT', '/api/v1/auth/sessions/{session_id}/revoke'),
    ('GET', '/api/v1/auth/mfa-methods'),
    ('POST', '/api/v1/auth/mfa-methods'),
    ('PUT', '/api/v1/auth/mfa-methods/{method_id}/verify'),
    ('GET', '/api/v1/auth/password-policies'),
    ('POST', '/api/v1/auth/password-policies'),
    ('PUT', '/api/v1/auth/password-policies/{policy_id}'),
    ('POST', '/api/v1/auth/password-policies/{policy_id}/enforce-mfa'),
    ('GET', '/api/v1/auth/login-attempts'),
    ('GET', '/api/v1/auth/ip-policies'),
    ('POST', '/api/v1/auth/ip-policies'),
    ('PUT', '/api/v1/auth/ip-policies/{policy_id}'),
    ('GET', '/api/v1/company/'),
    ('POST', '/api/v1/company/'),
    ('GET', '/api/v1/company/settings'),
    ('PUT', '/api/v1/company/settings'),
    ('GET', '/api/v1/company/branches'),
    ('GET', '/api/v1/company/branches/'),
    ('POST', '/api/v1/company/branches/'),
    ('PUT', '/api/v1/company/branches/{branch_id}'),
    ('DELETE', '/api/v1/company/branches/{branch_id}'),
    ('GET', '/api/v1/company/{company_id}'),
    ('PUT', '/api/v1/company/{company_id}'),
    ('POST', '/api/v1/company/{company_id}/logo'),
    ('DELETE', '/api/v1/company/{company_id}'),
    ('GET', '/api/v1/access/settings/starter-values/catalog'),
    ('POST', '/api/v1/access/settings/starter-values/apply'),
    ('GET', '/api/v1/access/settings/crm-lead-sources/options'),
    ('PUT', '/api/v1/access/settings/crm-lead-sources/options'),
    ('GET', '/api/v1/branches/ownership/inventory'),
    ('PUT', '/api/v1/branches/accounting-map'),
    ('GET', '/api/v1/company/departments'),
    ('GET', '/api/v1/company/departments/'),
    ('POST', '/api/v1/company/departments/'),
    ('PUT', '/api/v1/company/departments/{dept_id}'),
    ('DELETE', '/api/v1/company/departments/{dept_id}'),
    ('GET', '/api/v1/company/designations'),
    ('GET', '/api/v1/company/designations/'),
    ('POST', '/api/v1/company/designations/'),
    ('PUT', '/api/v1/company/designations/{desig_id}'),
    ('DELETE', '/api/v1/company/designations/{desig_id}'),
    ('GET', '/api/v1/company/business-units'),
    ('POST', '/api/v1/company/business-units'),
    ('GET', '/api/v1/company/cost-centers'),
    ('POST', '/api/v1/company/cost-centers'),
    ('GET', '/api/v1/company/locations'),
    ('POST', '/api/v1/company/locations'),
    ('GET', '/api/v1/company/grade-bands'),
    ('POST', '/api/v1/company/grade-bands'),
    ('GET', '/api/v1/company/job-families'),
    ('POST', '/api/v1/company/job-families'),
    ('GET', '/api/v1/company/job-profiles'),
    ('POST', '/api/v1/company/job-profiles'),
    ('GET', '/api/v1/company/positions'),
    ('POST', '/api/v1/company/positions'),
)
_SETTINGS_KEYS = frozenset(('business-packs', 'business-profile', 'files-storage', 'shared-companies', 'appearance', 'account', 'preferences', 'company-profile', 'branches', 'departments', 'designations', 'shifts', 'holidays', 'leaveTypes', 'salaryComponents', 'internships', 'documents', 'users', 'security', 'audit', 'modules', 'connections', 'communication', 'global', 'pms', 'task-packs', 'crm', 'sales', 'finance', 'ai'))

def _administration_route(method, path):
    for verb, template in _ADMIN_ROUTES:
        if verb != method: continue
        pattern = re.escape(template)
        for key in re.findall(r"\{([a-z_]+)\}", template):
            allowed = r"[1-9][0-9]*"
            if key == "kind": allowed = r"(?:branches|departments)"
            if key == "module_key": allowed = r"[a-z][a-z0-9_]{0,63}"
            pattern = pattern.replace(re.escape("{" + key + "}"), allowed)
        if re.fullmatch(pattern, path): return True
    prefix = "/api/v1/access/settings/"
    if method == "GET" and path.startswith(prefix):
        tail = path[len(prefix):]
        for group in ("", "options/", "history/"):
            if tail.startswith(group) and tail[len(group):] in _SETTINGS_KEYS: return True
    return False

_ABSENT = object()
_MARKER = 'business_pack_request_binding'


def classify_route(method: str, path: str) -> RouteKind:
    method = method.upper()
    if (method, path) in _PERSONAL or method == 'PUT' and re.fullmatch(r'/api/v1/auth/sessions/me/[1-9][0-9]*/revoke', path):
        return RouteKind.PERSONAL
    if _administration_route(method, path):
        return RouteKind.CONTROL
    if (method, path) in _CONTROL or (method, path.removeprefix(_PACK_ROOT + '/')) in _PACK_EXACT and path.startswith(_PACK_ROOT + '/'):
        return RouteKind.CONTROL
    if any(re.fullmatch(verbs, method) and re.fullmatch(pattern, path) for verbs, pattern in _CONTROL_PATTERNS):
        return RouteKind.CONTROL
    return RouteKind.OPERATIONAL


def assert_expected_realm(scope,expected):
    """A restrictive request precondition, never an operational grant."""
    if expected is None:return
    if expected not in {'legacy','pack'}:
        raise HTTPException(403,'Invalid expected operational realm')
    if expected!=('pack' if scope is not None else 'legacy'):
        raise HTTPException(409,'Operational context changed. Reload before continuing.')


@contextmanager
def bind_request_scope(db, actor, request, branch_ctx=None):
    """Resolve raw selectors against fresh native authority, then bind immutably.

    Personal/control requests deliberately ignore even stale/malformed selectors
    so account recovery and company-admin repair remain reachable. They neither
    clear nor replace an already bound operational scope. No exemption here
    grants access to an endpoint; native route authorization must still run.
    """
    kind = classify_route(request.method, request.url.path)
    previous = db.info.get('business_pack_scope', _ABSENT)
    marker = db.info.get(_MARKER, _ABSENT)
    if kind is not RouteKind.OPERATIONAL:
        yield None if previous is _ABSENT else previous
        return
    company = getattr(actor, 'organization_id', None)
    if type(company) is not int or company <= 0:
        raise HTTPException(403, 'A verified company is required for Business Pack binding')
    selected_branch = request.headers.get('X-Suite-Branch')
    if selected_branch is None and getattr(actor, '_suite_admin_read', False):
        selected_branch = 'all'
    fresh = branch_context(db, actor, company, selected_branch)
    if branch_ctx is not None and fresh != branch_ctx:
        raise HTTPException(403, 'Native branch authorization changed before Business Pack binding')
    scope = resolve_context(db, actor, fresh, requested_context_id=request.headers.get('X-Suite-Pack-Context'))
    assert_expected_realm(scope,request.headers.get('X-Suite-Expected-Pack-Realm'))
    if previous is not _ABSENT and previous != scope or marker is not _ABSENT and marker != scope:
        raise HTTPException(403, 'Business Pack context cannot change inside a bound request')
    db.info['business_pack_scope'] = scope
    db.info[_MARKER] = scope
    try:
        yield scope
    finally:
        for key, value in (('business_pack_scope', previous), (_MARKER, marker)):
            if value is _ABSENT:
                db.info.pop(key, None)
            else:
                db.info[key] = value


def authorization_fingerprint(scope: PackScope | None):
    """JSON-safe exact pack namespace to append to native record-sync identity.

    This adds no native permission. A freshly resolved scope is required; native
    actor/company/branch/session/grant identity must remain in the outer digest.
    """
    if scope is None:
        return ('business-pack-v1', 'legacy')
    if not isinstance(scope, PackScope):
        raise TypeError('A verified PackScope is required')
    return ('business-pack-v1', scope.company_id, scope.branch_id, scope.context_id,
        scope.activation_id, scope.pack_key, scope.pack_version, scope.user_id,
        scope.grant_id, scope.role, tuple(sorted(scope.capabilities)), scope.writable,
        scope.activation_revision, scope.context_revision, scope.grant_revision)
