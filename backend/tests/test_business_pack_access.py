"""Operational contexts resolve exact verified grants, never branch/pack products."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData, Column, Integer, Table, create_engine, select
from sqlalchemy.orm import Session

from app.business_packs.access import available_contexts, resolve_context
from app.business_packs.models import PackActivation, PackContext, PackMasterAvailability, PackRecordOwnership, PackUserGrant
from app.branches.service import BranchContext
from app.branches.models import BranchLifecycle
from app.models.company import Company, Branch
from app.models.user import User, Role
from app.access.models import AccessMembership, AccessPolicy


@pytest.fixture
def packs(db):
    if db.get(Company, 1) is None:
        db.add(Company(id=1, name='Pack access company'))
    db.add(Company(id=2, name='Foreign pack company'))
    role = Role(name='pack_access_' + uuid4().hex, permissions=[])
    db.add(role); db.flush()
    users = {}
    for name in ('doctor', 'chef', 'builder', 'admin', 'foreign'):
        user = User(email=f'{name}-{uuid4().hex}@example.test', hashed_password='unused', is_active=True, is_superuser=False, role_id=role.id)
        db.add(user); db.flush()
        company = 2 if name == 'foreign' else 1
        db.add(AccessMembership(user_id=user.id, company_id=company, active=True, is_admin=name == 'admin'))
        user.organization_id = company
        users[name] = user
    branches = {}
    for name, company in [('a', 1), ('b', 1), ('unconfigured', 1), ('foreign', 2)]:
        branch = Branch(name='Pack branch ' + name, company_id=company, is_active=True)
        db.add(branch); db.flush(); branches[name] = branch
    activations, contexts, grants = {}, {}, {}
    for pack, branch_name, actor, role_name in [('hospital', 'a', 'doctor', 'doctor'), ('restaurant', 'a', 'chef', 'chef'), ('construction', 'b', 'builder', 'site_engineer'), ('hospital', 'foreign', 'foreign', 'doctor')]:
        company = branches[branch_name].company_id
        activation = PackActivation(company_id=company, pack_key=pack, pack_version=1, state='active')
        db.add(activation); db.flush()
        context = PackContext(company_id=company, branch_id=branches[branch_name].id, activation_id=activation.id, pack_key=pack, pack_version=1, state='active')
        db.add(context); db.flush()
        grant = PackUserGrant(company_id=company, branch_id=branches[branch_name].id, context_id=context.id, user_id=users[actor].id, role=role_name)
        db.add(grant); db.flush()
        activations[actor], contexts[actor], grants[actor] = activation, context, grant
    db.commit()
    def ctx(branch='a', *, all_branches=False, writable=True, allowed=None):
        permitted = frozenset(allowed if allowed is not None else (branches['a'].id, branches['b'].id, branches['unconfigured'].id))
        return BranchContext(company_id=1, branch_id=None if all_branches else branches[branch].id,
            allowed=permitted, writable=permitted if writable else frozenset(), all_branches=all_branches,
            manage_access=False, superuser=False, company_admin=False)
    return SimpleNamespace(db=db, users=users, branches=branches, activations=activations, contexts=contexts, grants=grants, ctx=ctx)


def denied(operation, code=403):
    with pytest.raises(HTTPException) as error:
        operation()
    assert error.value.status_code == code


def test_request_binding_cannot_upgrade_legacy_none_to_pack(packs):
    p = packs
    p.db.info['business_pack_request_binding'] = None
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx()))
    assert resolve_context(p.db, p.users['doctor'], p.ctx('unconfigured')) is None


def test_request_binding_requires_unchanged_authority_revision(packs):
    p = packs
    scope = resolve_context(p.db, p.users['doctor'], p.ctx())
    p.db.info['business_pack_request_binding'] = scope
    assert resolve_context(p.db, p.users['doctor'], p.ctx()) == scope
    p.grants['doctor'].revision += 1
    p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx()))


def test_doctor_scope_is_immutable_and_grants_no_native_or_company_admin_authority(packs):
    p = packs
    scope = resolve_context(p.db, p.users['doctor'], p.ctx())
    assert (scope.company_id, scope.branch_id, scope.context_id, scope.pack_key, scope.role) == (1, p.branches['a'].id, p.contexts['doctor'].id, 'hospital', 'doctor')
    assert scope.version == 1 and scope.revisions == (1, 1, 1)
    assert scope.capabilities == frozenset({'hospital.appointments.view', 'hospital.visits.start', 'hospital.visits.complete'})
    assert not p.users['doctor'].is_superuser and p.users['doctor'].role.permissions == []
    assert not hasattr(scope, 'is_admin')
    with pytest.raises(FrozenInstanceError):
        scope.pack_key = 'restaurant'


@pytest.mark.parametrize('target', ['chef', 'builder', 'foreign'])
def test_doctor_cannot_select_restaurant_construction_or_foreign_company(packs, target):
    denied(lambda: resolve_context(packs.db, packs.users['doctor'], packs.ctx(), packs.contexts[target].id))


def test_grants_are_exact_pairs_not_independent_branch_and_pack_sets(packs):
    p = packs
    p.db.add(PackUserGrant(company_id=1, branch_id=p.branches['b'].id, context_id=p.contexts['builder'].id, user_id=p.users['doctor'].id, role='site_engineer'))
    p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), p.contexts['builder'].id))
    scopes = available_contexts(p.db, p.users['doctor'], p.ctx(all_branches=True))
    assert {(scope.branch_id, scope.pack_key) for scope in scopes} == {(p.branches['a'].id, 'hospital'), (p.branches['b'].id, 'construction')}
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx('b'), p.contexts['doctor'].id))
    chosen = resolve_context(p.db, p.users['doctor'], p.ctx('b'), p.contexts['builder'].id)
    assert chosen.pack_key == 'construction'


def test_all_branch_history_requires_explicit_context_even_for_one_grant(packs):
    p = packs
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(all_branches=True)))
    scope = resolve_context(p.db, p.users['doctor'], p.ctx(all_branches=True), str(p.contexts['doctor'].id))
    assert scope.branch_id == p.branches['a'].id


def test_ambiguity_requires_explicit_selector_and_never_guesses_primary(packs):
    p = packs
    p.db.add(PackUserGrant(company_id=1, branch_id=p.branches['a'].id, context_id=p.contexts['chef'].id, user_id=p.users['doctor'].id, role='chef'))
    p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx()))
    assert resolve_context(p.db, p.users['doctor'], p.ctx(), p.contexts['doctor'].id).pack_key == 'hospital'
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), 2147483647))


@pytest.mark.parametrize('selector', [True, False, 0, -1, '', '1.0', 'doctor', '１', 2147483648, [], {}])
def test_malformed_explicit_selector_never_falls_back(packs, selector):
    denied(lambda: resolve_context(packs.db, packs.users['doctor'], packs.ctx('unconfigured'), selector))


@pytest.mark.parametrize('target,field,value', [('grant', 'active', False), ('context', 'state', 'suspended'), ('context', 'state', 'retired'), ('activation', 'state', 'suspended'), ('activation', 'state', 'retired')])
def test_revocation_or_suspension_never_reverts_to_legacy(packs, target, field, value):
    p = packs
    row = {'grant': p.grants['doctor'], 'context': p.contexts['doctor'], 'activation': p.activations['doctor']}[target]
    setattr(row, field, value); p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx()))
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), p.contexts['doctor'].id))
    assert available_contexts(p.db, p.users['doctor'], p.ctx()) == ()


def test_role_from_another_pack_is_not_authority(packs):
    p = packs
    p.grants['doctor'].role = 'chef'; p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), p.contexts['doctor'].id))


def test_company_administrator_has_no_implicit_operational_grant(packs):
    p = packs
    p.users['admin']._suite_is_company_admin = True
    denied(lambda: resolve_context(p.db, p.users['admin'], p.ctx()))
    denied(lambda: resolve_context(p.db, p.users['admin'], p.ctx(), p.contexts['doctor'].id))


def test_platform_owner_also_needs_an_explicit_operational_grant(packs):
    p = packs
    p.users['admin'].is_superuser = True; p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['admin'], p.ctx(), p.contexts['doctor'].id))


def test_readonly_branch_scope_does_not_become_writable_from_pack_role(packs):
    scope = resolve_context(packs.db, packs.users['doctor'], packs.ctx(writable=False))
    assert scope.writable is False


def test_branch_access_revocation_is_respected(packs):
    p = packs
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(allowed=[]), p.contexts['doctor'].id))


@pytest.mark.parametrize('change', ['inactive_branch', 'deleted_branch', 'inactive_company', 'inactive_user', 'revoked_membership', 'suspended_policy'])
def test_native_identity_and_lifecycle_checks_are_revalidated(packs, change):
    p = packs
    if change == 'inactive_branch':
        p.branches['a'].is_active = False
    elif change == 'deleted_branch':
        deleted_at = datetime.now(timezone.utc)
        p.db.add(BranchLifecycle(company_id=1, branch_id=p.branches['a'].id, deleted_at=deleted_at, retain_until=deleted_at + timedelta(days=45)))
    elif change == 'inactive_company':
        p.db.get(Company, 1).is_active = False
    elif change == 'inactive_user':
        p.users['doctor'].is_active = False
    elif change == 'revoked_membership':
        p.db.query(AccessMembership).filter_by(user_id=p.users['doctor'].id, company_id=1).one().active = False
    else:
        p.db.add(AccessPolicy(user_id=p.users['doctor'].id, company_id=1, status='suspended', grants={}))
    p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), p.contexts['doctor'].id))


def test_actual_branch_company_is_checked_not_just_new_table_fk_pair(packs):
    p = packs
    bad = PackContext(company_id=1, branch_id=p.branches['foreign'].id, activation_id=p.activations['doctor'].id, pack_key='hospital', pack_version=1, state='active')
    p.db.add(bad); p.db.flush()
    p.db.add(PackUserGrant(company_id=1, branch_id=bad.branch_id, context_id=bad.id, user_id=p.users['doctor'].id, role='doctor')); p.db.commit()
    forged_branch_ctx = BranchContext(company_id=1, branch_id=bad.branch_id, allowed=frozenset({bad.branch_id}), writable=frozenset({bad.branch_id}), all_branches=False, manage_access=False, superuser=False)
    denied(lambda: resolve_context(p.db, p.users['doctor'], forged_branch_ctx, bad.id))


def test_future_or_uninstalled_manifest_version_is_not_current_authority(packs):
    p = packs
    activation = PackActivation(company_id=1, pack_key='hospital', pack_version=2, state='active')
    p.db.add(activation); p.db.flush()
    context = PackContext(company_id=1, branch_id=p.branches['a'].id, activation_id=activation.id, pack_key='hospital', pack_version=2, state='active')
    p.db.add(context); p.db.flush()
    p.db.add(PackUserGrant(company_id=1, branch_id=context.branch_id, context_id=context.id, user_id=p.users['doctor'].id, role='doctor')); p.db.commit()
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), context.id))


@pytest.mark.parametrize('gate', ['installed', 'entitlement'])
def test_pack_requires_approved_installed_native_modules_even_for_admin_reads(packs, monkeypatch, gate):
    p = packs
    p.db.info.update(admin_read_company=1, security_write_request=False)
    if gate == 'installed':
        from app import module_registry
        original = module_registry.is_app_enabled
        monkeypatch.setattr(module_registry, 'is_app_enabled', lambda key: key != 'srm' and original(key))
    else:
        from app.access import entitlements
        monkeypatch.setattr(entitlements, 'states', lambda db, company: {'srm': False})
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(), p.contexts['doctor'].id))


def test_unconfigured_concrete_branch_stays_legacy_but_all_branch_cannot_bypass_other_pack_history(packs):
    p = packs
    assert resolve_context(p.db, p.users['doctor'], p.ctx('unconfigured')) is None
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx(all_branches=True, allowed=[p.branches['unconfigured'].id])))


def test_new_draft_context_allows_legacy_without_explicit_selector(packs):
    p = packs
    draft = PackContext(company_id=1, branch_id=p.branches['unconfigured'].id, activation_id=p.activations['doctor'].id, pack_key='hospital', pack_version=1)
    p.db.add(draft); p.db.commit()
    assert resolve_context(p.db, p.users['doctor'], p.ctx('unconfigured')) is None
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx('unconfigured'), draft.id))


def test_retagging_used_context_back_to_draft_does_not_restore_legacy(packs):
    p = packs
    p.contexts['doctor'].state = 'draft'; p.db.commit()
    assert p.contexts['doctor'].revision == 2
    assert p.contexts['doctor'].ever_activated is True
    denied(lambda: resolve_context(p.db, p.users['doctor'], p.ctx()))


def test_schema_entirely_absent_preserves_legacy_but_explicit_selection_requires_installation():
    with create_engine('sqlite://').connect() as connection, Session(bind=connection) as db:
        assert resolve_context(db, SimpleNamespace(), SimpleNamespace()) is None
        assert available_contexts(db, SimpleNamespace(), SimpleNamespace()) == ()
        denied(lambda: resolve_context(db, SimpleNamespace(), SimpleNamespace(), 1), 503)


def test_partially_installed_pack_schema_never_falls_back_to_legacy():
    engine = create_engine('sqlite://')
    metadata = MetaData()
    Table('business_pack_activations', metadata, Column('id', Integer, primary_key=True))
    metadata.create_all(engine)
    with Session(engine) as db:
        denied(lambda: resolve_context(db, SimpleNamespace(), SimpleNamespace()), 503)
        denied(lambda: available_contexts(db, SimpleNamespace(), SimpleNamespace()), 503)
    engine.dispose()


def test_missing_column_in_otherwise_present_pack_tables_is_incomplete():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        for model in (PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability):
            connection.exec_driver_sql(f'CREATE TABLE {model.__tablename__} (id INTEGER PRIMARY KEY)')
    with Session(engine) as db:
        denied(lambda: resolve_context(db, SimpleNamespace(), SimpleNamespace()), 503)
    engine.dispose()
