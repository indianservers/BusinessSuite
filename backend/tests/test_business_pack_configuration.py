"""Real SQLite configuration, authority, revisions and nonactivation contracts."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import event

from app.business_packs import schemas, service
from app.business_packs.models import PackActivation, PackContext, PackUserGrant
from app.access.models import AccessAudit, AccessMembership, AccessPolicy
from app.branches.models import BranchGrant, BranchLifecycle
from app.models.company import Branch, Company
from app.models.user import User
from tests.test_branch_access import setup
from tests.tenant_test_utils import assign_company


@pytest.fixture
def owner(db):
    actor, a, b, *_ = setup(db)
    member = db.query(AccessMembership).filter_by(company_id=1, user_id=actor.id).first()
    if member is None:
        member = AccessMembership(company_id=1, user_id=actor.id, active=True)
        db.add(member)
    member.is_admin = True
    actor.organization_id = 1
    target = User(email='pack.doctor@example.test', hashed_password='unused', is_active=True)
    db.add(target); db.flush(); assign_company(db, target, 1)
    db.add(BranchGrant(company_id=1, branch_id=a.id, user_id=target.id, can_write=True))
    db.commit()
    return actor, a, b, target


def activation(db, actor, key='hospital'):
    return service.draft_activation(db, actor, schemas.DraftActivation(
        pack_key=key, expected_revision=0, reason='Reviewed draft setup'))


def context(db, actor, branch, key='hospital'):
    parent = activation(db, actor, key)
    row = service.draft_context(db, actor, schemas.DraftContext(activation_id=parent['id'],
        activation_revision=parent['revision'], branch_id=branch.id, expected_revision=0,
        reason='Reviewed branch setup'))
    return parent, row


def grant_input(ctx, revision=0, role='doctor', active=True):
    return schemas.GrantRole(context_revision=ctx['revision'], role=role, active=active,
        expected_revision=revision, reason='Explicit reviewed role assignment')


def error(code, operation):
    with pytest.raises(HTTPException) as result:
        operation()
    assert result.value.status_code == code, result.value.detail
    return result.value


def ready_runtime(monkeypatch):
    monkeypatch.setattr(service, '_runtime_status', lambda *args: {
        'ready': True, 'schema_ready': True, 'isolation_ready': True,
        'workflows_ready': True, 'reasons': []})


def test_catalog_and_readiness_never_claim_registry_is_active(db, owner):
    actor, a, *_ = owner
    catalog = service.catalog(db, actor)
    assert len(catalog['items']) == 7 and catalog['company_id'] == 1
    hospital = next(row for row in catalog['items'] if row['key'] == 'hospital')
    assert hospital['activation_ready'] is False and hospital['isolation_ready'] is False
    assert all(role['grants_company_admin'] is False for role in hospital['roles'])
    ready = service.readiness(db, actor, 'hospital', a.id)
    assert ready['ready'] is False and ready['reasons']
    assert service.configuration(db, actor)['activations'] == []


def test_drafts_preview_roles_and_revisions_are_explicit_and_audited(db, owner):
    actor, a, _, target = owner
    memberships = [(row.user_id, row.is_admin) for row in db.query(AccessMembership)]
    preview = service.preview(db, actor, schemas.PreviewActivation(action='draft_activation',
        pack_key='hospital', expected_revision=0, reason='Review before setup'))
    assert preview['allowed'] is True and preview['persists'] is False
    assert preview['after']['state'] == 'draft'
    assert db.query(PackActivation).count() == 0 and db.query(AccessAudit).count() == 0
    parent, ctx = context(db, actor, a)
    grant = service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx))
    assert parent['state'] == ctx['state'] == 'draft'
    assert grant['role'] == 'doctor' and grant['active'] and grant['revision'] == 1
    assert [(row.user_id, row.is_admin) for row in db.query(AccessMembership)] == memberships
    assert not db.query(AccessPolicy).filter_by(user_id=target.id).first()
    error(409, lambda: service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx)))
    revoked = service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx, 1, active=False))
    assert not revoked['active'] and revoked['revision'] == 2
    audits = service.history(db, actor)['items']
    assert [row['operation'] for row in audits] == [
        'settings.business-packs.role.revoked', 'settings.business-packs.role.assigned',
        'settings.business-packs.context.drafted', 'settings.business-packs.activation.drafted']
    assert audits[0]['before_json']['active'] is True
    assert audits[0]['after_json']['active'] is False


def test_activation_is_blocked_until_integration_proves_readiness(db, owner):
    actor, a, *_ = owner
    parent, ctx = context(db, actor, a)
    data = schemas.Activate(expected_revision=parent['revision'], reason='Attempt activation')
    preview = service.preview(db, actor, schemas.PreviewActivate(action='activate', activation_id=parent['id'], **data.model_dump()))
    assert not preview['allowed'] and preview['reasons']
    error(409, lambda: service.activate(db, actor, parent['id'], data))
    assert db.get(PackActivation, parent['id']).state == 'draft'
    assert db.get(PackContext, ctx['id']).state == 'draft'
    assert db.query(AccessAudit).count() == 2


def test_runtime_authority_can_enable_explicit_activation_without_autoactivating_context(db, owner, monkeypatch):
    actor, a, *_ = owner
    parent, ctx = context(db, actor, a)
    ready_runtime(monkeypatch)
    active = service.activate(db, actor, parent['id'], schemas.Activate(expected_revision=1, reason='Verified native integration'))
    assert active['state'] == 'active' and active['revision'] == 2
    assert db.get(PackContext, ctx['id']).state == 'draft'
    error(409, lambda: service.activate_context(db, actor, ctx['id'], schemas.ActivateContext(
        expected_revision=1, activation_revision=1, reason='Stale parent version')))
    branch = service.activate_context(db, actor, ctx['id'], schemas.ActivateContext(
        expected_revision=1, activation_revision=2, reason='Explicit verified branch activation'))
    assert branch['state'] == 'active' and branch['revision'] == 2


@pytest.mark.parametrize('result', [
    {'ready': 'true', 'schema_ready': True, 'isolation_ready': True, 'workflows_ready': True, 'reasons': []},
    {'ready': True, 'schema_ready': True, 'isolation_ready': False, 'workflows_ready': True, 'reasons': []},
    {'ready': True, 'schema_ready': True, 'isolation_ready': True, 'workflows_ready': True, 'reasons': ['Unresolved source ownership']},
    {'ready': True},
])
def test_malformed_or_incomplete_runtime_proof_cannot_enable_activation(db, owner, monkeypatch, result):
    actor, a, *_ = owner
    monkeypatch.setattr(service, 'import_module', lambda name: SimpleNamespace(activation_readiness=lambda *args, **kwargs: result))
    assert service.readiness(db, actor, 'hospital', a.id)['ready'] is False


def test_company_admin_is_required_even_with_a_pack_manager_role_and_hr_configuration(db, owner):
    actor, a, _, target = owner
    parent, ctx = context(db, actor, a)
    service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx, role='hospital_manager'))
    db.add(AccessPolicy(user_id=target.id, company_id=1, status='active', grants={
        'hrms': {'enabled': True, 'scope': 'organization', 'permissions': ['company_manage'], 'actions': ['view', 'configure']}}))
    db.commit()
    for operation in [lambda: service.catalog(db, target), lambda: service.configuration(db, target),
        lambda: service.readiness(db, target, 'hospital', a.id),
        lambda: service.draft_activation(db, target, schemas.DraftActivation(pack_key='restaurant', expected_revision=0, reason='Not company authority'))]:
        error(403, operation)
    assert not db.query(AccessMembership).filter_by(user_id=target.id, is_admin=True).first()


@pytest.mark.parametrize('role', ['chef', 'site_engineer', 'company_admin'])
def test_wrong_pack_and_administrative_roles_are_rejected(db, owner, role):
    actor, a, _, target = owner
    _, ctx = context(db, actor, a)
    error(422, lambda: service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx, role=role)))
    assert db.query(PackUserGrant).count() == 0


def test_context_and_grant_ids_cannot_cross_company_or_branch_pairs(db, owner):
    actor, a, b, target = owner
    parent, ctx = context(db, actor, a)
    foreign = Company(name='Foreign packs', is_active=True)
    db.add(foreign); db.flush()
    foreign_branch = Branch(company_id=foreign.id, name='Foreign branch', is_active=True)
    foreign_user = User(email='foreign.pack@example.test', hashed_password='unused', is_active=True)
    db.add_all([foreign_branch, foreign_user]); db.flush(); assign_company(db, foreign_user, foreign.id)
    foreign_activation = PackActivation(company_id=foreign.id, pack_key='hospital', pack_version=1, state='draft')
    db.add(foreign_activation); db.commit()
    error(404, lambda: service.draft_context(db, actor, schemas.DraftContext(activation_id=parent['id'],
        activation_revision=1, branch_id=foreign_branch.id, expected_revision=0, reason='Foreign branch denied')))
    error(404, lambda: service.draft_context(db, actor, schemas.DraftContext(activation_id=foreign_activation.id,
        activation_revision=1, branch_id=a.id, expected_revision=0, reason='Foreign activation denied')))
    error(404, lambda: service.grant_role(db, actor, ctx['id'], foreign_user.id, grant_input(ctx)))
    second = service.draft_context(db, actor, schemas.DraftContext(activation_id=parent['id'], activation_revision=1,
        branch_id=b.id, expected_revision=0, reason='Second authorized branch setup'))
    error(403, lambda: service.grant_role(db, actor, second['id'], target.id, grant_input(second)))
    assert db.query(PackUserGrant).count() == 0


@pytest.mark.parametrize('case', ['inactive', 'retired'])
def test_inactive_or_retired_native_branch_cannot_be_configured(db, owner, case):
    actor, a, *_ = owner
    parent = activation(db, actor)
    if case == 'inactive': a.is_active = False
    else:
        from datetime import datetime, timedelta, timezone
        deleted_at = datetime.now(timezone.utc)
        db.add(BranchLifecycle(branch_id=a.id, company_id=1, deleted_at=deleted_at, retain_until=deleted_at + timedelta(days=45)))
    db.commit()
    error(404, lambda: service.draft_context(db, actor, schemas.DraftContext(activation_id=parent['id'],
        activation_revision=1, branch_id=a.id, expected_revision=0, reason='Closed branch denied')))


def test_required_native_module_entitlements_cannot_be_bypassed(db, owner, monkeypatch):
    actor, a, *_ = owner
    from app.apps.business_os.models import BOSEnabledModule
    row = db.query(BOSEnabledModule).filter_by(company_id=1, module_key='srm').first()
    if row is None:
        row = BOSEnabledModule(company_id=1, module_key='srm', display_name='Sales', enabled=False)
        db.add(row)
    row.enabled = False; db.commit()
    ready_runtime(monkeypatch)
    ready = service.readiness(db, actor, 'hospital', a.id)
    assert ready['missing_modules'] == ['srm'] and ready['ready'] is False
    error(403, lambda: activation(db, actor))
    assert db.query(PackActivation).count() == 0


def test_alias_is_canonical_and_existing_version_or_stale_parent_is_not_overwritten(db, owner):
    actor, a, *_ = owner
    parent = activation(db, actor, 'saloon')
    assert parent['pack_key'] == 'salon'
    error(409, lambda: activation(db, actor, 'salon'))
    error(409, lambda: service.draft_context(db, actor, schemas.DraftContext(activation_id=parent['id'],
        activation_revision=2, branch_id=a.id, expected_revision=0, reason='Stale version denied')))
    assert db.query(PackActivation).count() == 1 and db.query(PackContext).count() == 0


def test_configuration_get_without_pack_schema_is_read_only_and_reports_installation_state(db, owner, monkeypatch):
    actor, a, *_ = owner
    monkeypatch.setattr(service, 'schema_status', lambda db: {'schema_ready': False, 'missing_tables': list(service.TABLES)})
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany): statements.append(statement.upper().lstrip())
    event.listen(db.get_bind(), 'before_cursor_execute', record)
    try:
        result = service.configuration(db, actor)
        ready = service.readiness(db, actor, 'hospital', a.id)
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', record)
    assert not result['schema_ready'] and result['activations'] == result['contexts'] == result['grants'] == []
    assert not ready['ready'] and ready['missing_tables']
    assert not any(statement.startswith(('CREATE ', 'ALTER ', 'DROP ', 'INSERT ', 'UPDATE ', 'DELETE ')) for statement in statements)


def test_partial_pack_schema_reports_missing_columns_without_querying_incompatible_models(db, owner, monkeypatch):
    actor, *_ = owner
    original = service.inspect
    class PartialInspector:
        def __init__(self, connection): self.native = original(connection)
        def has_table(self, name): return self.native.has_table(name)
        def get_columns(self, name):
            columns = self.native.get_columns(name)
            return [column for column in columns if column['name'] != 'created_at'] if name == 'business_pack_activations' else columns
    monkeypatch.setattr(service, 'inspect', PartialInspector)
    config = service.configuration(db, actor)
    assert not config['schema_ready'] and config['activations'] == []
    assert config['missing_columns'] == {'business_pack_activations': ['created_at']}


def test_explicit_revocation_remains_possible_after_native_membership_is_revoked(db, owner):
    actor, a, _, target = owner
    _, ctx = context(db, actor, a)
    service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx))
    membership = db.query(AccessMembership).filter_by(user_id=target.id, company_id=1).first()
    if membership is None:
        membership = AccessMembership(user_id=target.id, company_id=1, active=False)
        db.add(membership)
    membership.active = False; db.commit()
    revoked = service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx, 1, active=False))
    assert not revoked['active'] and revoked['revision'] == 2
    error(404, lambda: service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx, 2)))


def test_configuration_limit_signals_truncation_without_unbounded_queries(db, owner):
    actor, a, *_ = owner
    context(db, actor, a)
    config = service.configuration(db, actor, limit=1)
    assert len(config['branches']) == 1 and config['has_more']['branches']
    assert len(config['activations']) == 1 and not config['has_more']['activations']
    error(422, lambda: service.configuration(db, actor, limit=0))


@pytest.mark.parametrize('model,payload', [
    (schemas.DraftActivation, {'pack_key': 'hospital', 'expected_revision': False, 'reason': 'Denied malformed revision'}),
    (schemas.DraftActivation, {'pack_key': 'hospital', 'expected_revision': 0, 'reason': 'Denied forced state', 'state': 'active'}),
    (schemas.DraftContext, {'activation_id': True, 'activation_revision': 1, 'branch_id': 1, 'expected_revision': 0, 'reason': 'Denied malformed id'}),
    (schemas.GrantRole, {'context_revision': 1, 'role': 'doctor', 'active': True, 'expected_revision': 0, 'reason': 'Denied company escalation', 'is_admin': True}),
    (schemas.GrantRole, {'context_revision': 1, 'role': 'doctor', 'active': 'true', 'expected_revision': 0, 'reason': 'Denied malformed bool'}),
])
def test_inputs_reject_unknown_authority_fields_and_coercion(model, payload):
    with pytest.raises(ValidationError): model.model_validate(payload)


def test_preview_discriminator_rejects_conflicting_operations():
    with pytest.raises(ValidationError):
        TypeAdapter(schemas.PreviewInput).validate_python({'action': 'draft_activation', 'pack_key': 'hospital',
            'expected_revision': 0, 'reason': 'Conflicting operation denied', 'user_id': 123, 'role': 'doctor'})


@pytest.fixture
def pack_client(client):
    from app.main import app
    from app.business_packs.api import router
    existing = {id(route) for route in app.router.routes}
    if not any(getattr(route, 'path', '') == '/api/v1/access/settings/business-packs/catalog' for route in app.router.routes):
        app.include_router(router, prefix='/api/v1/access/settings')
    try:
        yield client
    finally:
        app.router.routes[:] = [route for route in app.router.routes if id(route) in existing]


def test_http_settings_routes_use_native_auth_and_company_control(pack_client, db, owner):
    from app.core.security import create_access_token
    actor, a, _, target = owner
    root = '/api/v1/access/settings/business-packs'
    headers = {'Authorization': 'Bearer ' + create_access_token(actor.id), 'X-Suite-Organization': '1', 'X-Suite-Branch': str(a.id)}
    peer = {**headers, 'Authorization': 'Bearer ' + create_access_token(target.id)}
    # Preserve the existing HTTPBearer unauthenticated response contract.
    assert pack_client.get(root + '/catalog').status_code == 403
    assert pack_client.get(root + '/catalog', headers=peer).status_code == 403
    catalog = pack_client.get(root + '/catalog', headers=headers)
    assert catalog.status_code == 200, catalog.text
    assert len(catalog.json()['items']) == 7
    malformed = pack_client.post(root + '/activations', headers=headers, json={
        'pack_key': 'hospital', 'expected_revision': 0, 'reason': 'No forced authority', 'state': 'active'})
    assert malformed.status_code == 422
    created = pack_client.post(root + '/activations', headers=headers, json={
        'pack_key': 'hospital', 'expected_revision': 0, 'reason': 'Native authorized draft'})
    assert created.status_code == 201, created.text
    assert created.json()['state'] == 'draft'
    parent = created.json()
    branch = pack_client.post(root + '/contexts', headers=headers, json={
        'activation_id': parent['id'], 'activation_revision': parent['revision'], 'branch_id': a.id,
        'expected_revision': 0, 'reason': 'Native branch setup'})
    assert branch.status_code == 201, branch.text
    ctx = branch.json()
    assignment = pack_client.put(root + f'/contexts/{ctx["id"]}/grants/{target.id}', headers=headers,
        json=grant_input(ctx).model_dump())
    assert assignment.status_code == 200, assignment.text
    assert assignment.json()['role'] == 'doctor'
    attempted = pack_client.post(root + f'/activations/{parent["id"]}/activate', headers=headers,
        json={'expected_revision': parent['revision'], 'reason': 'Unproven activation blocked'})
    assert attempted.status_code == 409, attempted.text
    assert attempted.json()['detail']['readiness']['ready'] is False
    history = pack_client.get(root + '/history', headers=headers)
    assert history.status_code == 200 and len(history.json()['items']) == 3
