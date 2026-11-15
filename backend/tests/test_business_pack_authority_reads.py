"""Native denials stay visible; authority/config reads grant no operational writes."""
from dataclasses import replace

import pytest
from fastapi import HTTPException
from app.access.models import AccessPolicy, AccessMembership
from app.apps.business_os.models import BOSEnabledModule
from app.shared.models import ServicePolicy
from app.business_packs.boundary import install
from tests.test_business_pack_boundary import native, POLICY, forbidden
from tests.test_business_pack_access import packs


def authority_policy():
    return replace(POLICY,
        record_tables=POLICY.record_tables | {'suite_service_policies'},
        shared_read_tables=frozenset({'suite_access_memberships', 'suite_access_policies',
                                    'bos_enabled_modules', 'suite_service_policies'}))


def test_revoked_native_policy_and_disabled_module_cannot_disappear(native):
    from sqlalchemy import update
    n = native
    own = AccessPolicy(company_id=1, user_id=n.scope.user_id, status='active', grants={})
    foreign = AccessPolicy(company_id=1, user_id=n.foreign_scope.user_id, status='active', grants={'private': True})
    disabled = BOSEnabledModule(company_id=1, module_key='srm', display_name='Sales', enabled=False)
    n.db.add_all([own, foreign, disabled]); n.db.commit()
    cleanup = install(n.db, n.scope, policy=authority_policy())
    try:
        # Native policy revalidation must observe the actual denial row, rather
        # than treating a pack-filtered missing row as legacy authorization.
        n.db.connection().execute(update(AccessPolicy.__table__).where(
            AccessPolicy.id == own.id).values(status='suspended'))
        n.db.expire(own)
        assert n.db.query(AccessPolicy).one().status == 'suspended'
        assert [row.user_id for row in n.db.query(AccessPolicy)] == [n.scope.user_id]
        assert not n.db.query(BOSEnabledModule).filter_by(module_key='srm').one().enabled
        assert all(row.user_id == n.scope.user_id for row in n.db.query(AccessMembership))
        with pytest.raises(HTTPException) as error, n.db.begin_nested():
            n.db.query(BOSEnabledModule).one().enabled = True
            n.db.flush()
        assert error.value.status_code == 403
    finally:
        cleanup()


def test_shared_control_settings_exact_keys_and_read_only_even_with_private_snapshots(native):
    n = native
    def policy(key, kind, company=1):
        return ServicePolicy(scope_key=key, organization_id=company, kind=kind,
                             values_json={'currency': 'INR'}, updated_by=n.scope.user_id)
    rows = [policy('form-defaults:company:1', 'form_defaults'),
            policy(f'form-defaults:company:1:branch:{n.scope.branch_id}:module:srm', 'form_defaults'),
            policy('company:1:module:srm', 'settings'),
            policy('company:1:module:hrms', 'settings'),
            policy('platform', 'settings', None),
            policy('business-profile:company:2', 'business_profile', 2),
            policy('private:other-pack', 'form_snapshot')]
    n.db.add_all(rows); n.db.commit()
    expected = {row.scope_key for row in (rows[0], rows[1], rows[2], rows[4])}
    cleanup = install(n.db, n.scope, policy=authority_policy())
    try:
        assert {row.scope_key for row in n.db.query(ServicePolicy)} == expected
        with pytest.raises(HTTPException) as error, n.db.begin_nested():
            n.db.query(ServicePolicy).filter_by(scope_key='company:1:module:srm').one().values_json = {'currency': 'USD'}
            n.db.flush()
        assert error.value.status_code == 403
        # The same native table can still create an independently anchored
        # private form snapshot without making company settings writable.
        snapshot = policy('private:own-pack', 'form_snapshot')
        n.db.add(snapshot); n.db.flush()
        assert n.db.get(ServicePolicy, snapshot.id) is snapshot
        assert 'private:other-pack' not in {row.scope_key for row in n.db.query(ServicePolicy)}
    finally:
        cleanup()


def test_arbitrary_native_tables_cannot_be_declared_shared_authority():
    with pytest.raises(ValueError):
        replace(POLICY, shared_read_tables=frozenset({'srm_invoices'}))
    with pytest.raises(ValueError):
        replace(POLICY, record_tables=POLICY.record_tables | {'suite_access_policies'})


def test_fixed_commercial_writer_lock_works_without_opening_session_sql(native):
    from sqlalchemy import text
    from app.apps.srm.services.commercial import lock_tenant
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        lock_tenant(n.db, n.current_user)
        forbidden(lambda: n.db.execute(text('SELECT title FROM srm_sales_orders')).all())
        forbidden(lambda: lock_tenant(n.db, n.cached_foreign_user))
        n.db.info['security_boundary'] = 2
        forbidden(lambda: lock_tenant(n.db, n.current_user))
    finally:
        n.db.info.pop('security_boundary', None)
        cleanup()
