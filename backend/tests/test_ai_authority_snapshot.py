"""Fingerprint authority stays fresh without borrowing a business ORM graph."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, update

from ai_test_utils import auth_headers
from app.access import service, entitlements
from app.access.models import AccessMembership, AccessPolicy, AccessRole
from app.ai_agents.security import _fingerprint_state, fingerprint, limits
from app.ai_agents.authority_snapshot import read_authority
from app.models.user import User, Permission, role_permissions
from app.shared.models import ServicePolicy


@pytest.fixture
def actor(client, db):
    headers, user = auth_headers(client, db, email=f'authority-{uuid4()}@example.com',
        permissions=['ai_assistant', 'crm_manage', 'employee_view'])
    user.organization_id = 1
    return user, headers


def inputs(db, user):
    identity = db.connection().execute(select(User.id, User.role_id, User.is_superuser, User.is_active)
        .where(User.id == user.id)).mappings().one()
    permissions = db.connection().execute(select(Permission.id, Permission.name, Permission.module, Permission.description)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .where(role_permissions.c.role_id == user.role_id)).mappings().all()
    return identity, permissions


def managed(db, user):
    role = AccessRole(company_id=1, module_key='hrms', name='Exact native role', permissions=['leave_view'],
        actions=['view'], scope='own', active=True, version=1)
    db.add(role); db.flush()
    policy = AccessPolicy(company_id=1, user_id=user.id, status='active', version=1,
        grants={'hrms': {'enabled': True, 'roleId': role.id, 'scope': 'own'}})
    db.add(policy); db.commit()
    return policy, role


@pytest.mark.parametrize('is_managed', [False, True])
def test_snapshot_retains_native_grant_and_entitlement_shape(db, actor, is_managed):
    user, _ = actor
    policy = managed(db, user)[0] if is_managed else None
    expected = service.resolved_grants(db, policy) if policy else service.legacy_grants(db, user, 1, administrative_read=False)
    result = _fingerprint_state(db, user, 1)
    assert set(result) == {'aclEpoch', 'agent_state', 'actor', 'company', 'policyVersion', 'grants',
        'nativePermissions', 'entitlements', 'aiPolicy'}
    assert result['grants'] == expected
    assert result['entitlements'] == entitlements.states(db, 1)
    assert result['aiPolicy'] == limits(db, 1)['version']
    assert 'payroll_run' not in result['nativePermissions']


@pytest.mark.parametrize('change', ['policy', 'role', 'role_disabled', 'native_permission', 'membership', 'entitlement', 'ai_limit'])
def test_snapshot_revalidates_actual_authority_not_outer_cached_policy(db, actor, change):
    user, _ = actor
    policy, role = managed(db, user)
    before = fingerprint(db, user, 1)
    db.info['suite_access_policies'] = {1: {user.id: SimpleNamespace(status='active', version=999, grants={})}}
    try:
        if change == 'policy':
            db.connection().execute(update(AccessPolicy.__table__).where(AccessPolicy.id == policy.id).values(status='revoked', version=2))
        elif change == 'role':
            db.connection().execute(update(AccessRole.__table__).where(AccessRole.id == role.id).values(permissions=[], version=2))
        elif change == 'role_disabled':
            db.connection().execute(update(AccessRole.__table__).where(AccessRole.id == role.id).values(active=False, version=2))
        elif change == 'native_permission':
            db.connection().execute(role_permissions.delete().where(role_permissions.c.role_id == user.role_id))
        elif change == 'membership':
            row = db.query(AccessMembership).filter_by(user_id=user.id, company_id=1).first()
            if row: row.active = False
            else: db.add(AccessMembership(user_id=user.id, company_id=1, active=False))
            db.flush()
        elif change == 'entitlement':
            from app.apps.business_os.models import BOSEnabledModule
            row = db.query(BOSEnabledModule).filter_by(company_id=1, module_key='hrms').first()
            if row: row.enabled = False
            else: db.add(BOSEnabledModule(company_id=1, module_key='hrms', display_name='HRMS', enabled=False))
            db.flush()
        else:
            db.add(ServicePolicy(organization_id=1, kind='ai_security', scope_key='company:1:ai_security', version=3, values_json={}, updated_by=user.id))
            db.flush()
        if change in {'policy', 'membership'}:
            with pytest.raises(HTTPException) as denied: fingerprint(db, user, 1)
            assert denied.value.status_code == 403
        else:
            state = _fingerprint_state(db, user, 1)
            assert fingerprint(db, user, 1) != before
            assert state['policyVersion'] == 1
            if change == 'role': assert state['grants']['hrms']['permissions'] == []
            if change == 'role_disabled': assert state['grants']['hrms']['enabled'] is False
            if change == 'native_permission': assert state['nativePermissions'] == []
            if change == 'entitlement': assert state['entitlements']['hrms'] is False
            if change == 'ai_limit': assert state['aiPolicy'] == 3
    finally:
        db.info.pop('suite_access_policies', None)


@pytest.mark.parametrize('raise_error', [False, True])
def test_authority_close_preserves_exact_parent_transaction_and_business_flush(db, actor, raise_error):
    from app.apps.crm.models import CRMTask
    user, _ = actor
    baseline = _fingerprint_state(db, user, 1)
    captured = []
    def during_flush(session, context): captured.append(_fingerprint_state(session, user, 1))
    event.listen(db, 'after_flush', during_flush)
    try:
        row = CRMTask(organization_id=1, title='Native pending transaction proof')
        db.add(row); db.flush()
    finally: event.remove(db, 'after_flush', during_flush)
    assert captured and captured[-1] == baseline
    connection = db.connection(); transaction = connection.get_nested_transaction() or connection.get_transaction()
    identity, permissions = inputs(db, user)
    def read():
        with read_authority(db, user, 1, identity, permissions) as (snapshot, view, policy):
            assert snapshot.connection() is connection
            assert service.legacy_grants(snapshot, view, 1, administrative_read=False) == baseline['grants']
            for action in (snapshot.commit, snapshot.rollback, lambda: snapshot.bulk_save_objects([]),
                    lambda: snapshot.query(CRMTask).all(), lambda: snapshot.execute(update(AccessPolicy).values(status='revoked'))):
                with pytest.raises(HTTPException): action()
            if raise_error: raise RuntimeError('Owned authority observation failed')
    if raise_error:
        with pytest.raises(RuntimeError, match='Owned authority'): read()
    else: read()
    assert transaction.is_active
    assert (connection.get_nested_transaction() or connection.get_transaction()) is transaction
    assert connection.scalar(select(CRMTask.title).where(CRMTask.id == row.id)) == row.title


def test_legacy_intern_projection_is_fresh_and_native_identity_is_unique(db, actor):
    from app.models.employee import Employee
    user, headers = actor
    branch = int(headers['X-Suite-Branch'])
    employee = Employee(employee_id=uuid4().hex, user_id=user.id, first_name='Native', last_name='Intern',
        branch_id=branch, employment_type='Intern', date_of_joining=date.today())
    db.add(employee); db.flush(); db.expire(user, ['employee'])
    state = _fingerprint_state(db, user, 1)
    assert state['grants'] == service.legacy_grants(db, user, 1, administrative_read=False)
    assert all(not grant['enabled'] for key, grant in state['grants'].items() if key != 'interns_hub')
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Employee(employee_id=uuid4().hex, user_id=user.id, first_name='Ambiguous', last_name='Profile',
                branch_id=branch, employment_type='Permanent', date_of_joining=date.today())); db.flush()
    assert db.query(Employee.id).filter(Employee.user_id == user.id).count() == 1
    assert _fingerprint_state(db, user, 1)['grants'] == state['grants']


@pytest.mark.parametrize('company', [1, 2])
@pytest.mark.parametrize('ownership', ['unassigned_null', 'approved_null', 'foreign_marker'])
def test_ai_limit_snapshot_matches_native_null_company_provenance(client, db, company, ownership):
    from app.core.tenant_boundary import install
    from app.branches.models import BranchOwnership
    user_headers, user = auth_headers(client, db, email=f'limits-{uuid4()}@example.com', company_id=company,
        permissions=['ai_assistant'])
    user.organization_id = company
    table = ServicePolicy.__table__
    key = f'company:{company}:ai_security'
    identity = db.connection().scalar(table.insert().values(organization_id=None, kind='ai_security', scope_key=key,
        version=7, values_json={}, updated_by=user.id).returning(table.c.id))
    if ownership != 'unassigned_null':
        db.add(BranchOwnership(resource_table=table.name, resource_key=str(identity), company_id=company,
            branch_id=int(user_headers['X-Suite-Branch']), source='explicit-native-legacy-fixture'))
        db.flush()
    if ownership == 'foreign_marker':
        from app.models.company import Company
        foreign = 2 if company == 1 else 1
        if db.get(Company, foreign) is None:
            db.add(Company(id=foreign, name='Explicit foreign authority fixture')); db.flush()
        db.connection().execute(table.update().where(table.c.id == identity).values(organization_id=foreign))
    cleanup = install(db, user, company)
    try:
        expected = 0 if ownership == 'foreign_marker' or company == 2 and ownership == 'unassigned_null' else 7
        assert limits(db, company)['version'] == expected
        assert _fingerprint_state(db, user, company)['aiPolicy'] == expected
    finally: cleanup()


def test_employment_projection_keeps_original_private_exclusions(db, actor):
    from app.models.employee import Employee
    from app.business_packs.models import PackActivation, PackContext, PackRecordOwnership
    from app.business_packs.legacy_boundary import install
    user, headers = actor
    branch = int(headers['X-Suite-Branch'])
    hidden = Employee(employee_id=uuid4().hex, user_id=user.id, branch_id=branch, first_name='Private',
        last_name='Excluded', employment_type='Intern', date_of_joining=date.today())
    activation = PackActivation(company_id=1, pack_key='hospital', pack_version=1, state='draft')
    db.add_all([hidden, activation]); db.flush()
    context = PackContext(company_id=1, branch_id=branch, activation_id=activation.id, pack_key='hospital', pack_version=1, state='draft')
    db.add(context); db.flush()
    db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context.id,
        resource_table='employees', resource_key=str(hidden.id), source='created')); db.commit()
    cleanup = install(db, user, 1)
    try:
        db.expire(user, ['employee'])
        assert db.query(Employee.id).filter(Employee.user_id == user.id).all() == []
        assert _fingerprint_state(db, user, 1)['grants'] == service.legacy_grants(db, user, 1, administrative_read=False)
    finally: cleanup()
