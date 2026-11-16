"""Committed PostgreSQL writers race over the actual company selection CAS."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import sessionmaker

from app.access.models import AccessAudit, AccessMembership
from app.models.company import Company
from app.business_packs import schemas, service, theme_selection
from app.business_packs.models import PackActivation, PackContext, PackUserGrant
from app.models.user import User
from app.shared.models import ServicePolicy
from tests.test_settings_hub import actor as create_actor


@pytest.fixture
def committed_theme(db_engine):
    if db_engine.dialect.name != 'postgresql':
        pytest.skip('Requires independent committed PostgreSQL transactions')
    url = db_engine.url
    assert url.host in {'127.0.0.1', 'localhost', '::1'} and url.database.endswith('_test')
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        _, actor = create_actor(db, role='theme-pg-owner-' + uuid4().hex, admin=True)
        actor_id = actor.id
        company = Company(name='Theme PostgreSQL ' + uuid4().hex, is_active=True)
        db.add(company); db.flush()
        company_id = company.id
        db.add(AccessMembership(user_id=actor_id, company_id=company_id, active=True, is_admin=True))
        db.commit()
        actor.organization_id = company_id
        assert actor.is_superuser is False
        assert service.company_control(db, actor) == company_id
        for key in ('hospital', 'salon'):
            assert service.readiness(db, actor, key)['ready'] is True
        initial = theme_selection.configuration(db, actor)
        assert initial['active_key'] == 'general'
        db.commit()  # Genuine seed is visible to both independent connections.
    return factory, actor_id, company_id, initial['selection_revision']


def principal(db, actor_id, company_id):
    from app.core.tenant_boundary import company_ids
    actor = db.get(User, actor_id, populate_existing=True)
    assert actor is not None and actor.is_active and not actor.is_superuser
    assert company_id in company_ids(db, actor)
    actor.organization_id = company_id
    assert service.company_control(db, actor) == company_id
    return actor


def selection(key, token):
    return schemas.ActivateTheme(pack_key=key, expected_selection=token,
        reason='Reviewed independent PostgreSQL writer')


def test_simultaneous_company_theme_writers_one_wins_other_rolls_back_and_retries(committed_theme):
    factory, actor_id, company_id, token = committed_theme
    barrier = Barrier(2)
    def writer(key):
        with factory() as db:
            actor = principal(db, actor_id, company_id)
            assert theme_selection.configuration(db, actor)['selection_revision'] == token
            connection_id = db.connection().scalar(select(func.pg_backend_pid()))
            barrier.wait(timeout=10)
            try:
                result = theme_selection.activate(db, actor, selection(key, token))
                return {'status': 200, 'key': key, 'connection': connection_id, 'result': result}
            except HTTPException as denied:
                assert denied.status_code == 409, denied.detail
                db.rollback()
                # The actual losing Session remains usable after its rollback.
                fresh = theme_selection.configuration(db, principal(db, actor_id, company_id))
                assert fresh['selection_revision'] != token
                return {'status': 409, 'key': key, 'connection': connection_id, 'result': fresh}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer, key) for key in ('hospital', 'salon')]
        results = [future.result(timeout=20) for future in futures]
    assert len({row['connection'] for row in results}) == 2
    assert sorted(row['status'] for row in results) == [200, 409], results
    winner = next(row for row in results if row['status'] == 200)
    loser = next(row for row in results if row['status'] == 409)
    with factory() as db:
        actor = principal(db, actor_id, company_id)
        state = theme_selection.configuration(db, actor)
        assert state['active_key'] == winner['key']
        assert [row.pack_key for row in db.query(PackActivation).filter_by(company_id=company_id, state='active')] == [winner['key']]
        assert db.query(PackActivation).filter_by(company_id=company_id).count() == 1
        assert db.query(ServicePolicy).filter_by(organization_id=company_id, kind='business_pack_theme').count() == 1
        assert db.query(AccessAudit).filter_by(company_id=company_id, operation='settings.business-packs.theme.activated').count() == 1
        assert db.query(PackContext).filter_by(company_id=company_id).count() == db.query(PackUserGrant).filter_by(company_id=company_id).count() == 0
        # Retry the losing requested choice with a fresh actual CAS token.
        retry = theme_selection.activate(db, actor, selection(loser['key'], state['selection_revision']))
        assert retry['active_key'] == loser['key']
        assert [row.pack_key for row in db.query(PackActivation).filter_by(company_id=company_id, state='active')] == [loser['key']]
        assert db.query(PackActivation).filter_by(company_id=company_id).count() == 2
        assert db.query(PackContext).filter_by(company_id=company_id).count() == db.query(PackUserGrant).filter_by(company_id=company_id).count() == 0


def test_postgres_theme_late_commit_failure_preserves_winner_and_original_token_retry(committed_theme):
    factory, actor_id, company_id, token = committed_theme
    with factory() as db:
        actor = principal(db, actor_id, company_id)
        def fail(session):
            raise RuntimeError('PostgreSQL theme late commit fault')
        event.listen(db, 'before_commit', fail)
        try:
            with pytest.raises(RuntimeError, match='PostgreSQL theme late commit fault'):
                theme_selection.activate(db, actor, selection('hospital', token))
        finally:
            event.remove(db, 'before_commit', fail)
            db.rollback()
    with factory() as db:
        actor = principal(db, actor_id, company_id)
        assert theme_selection.configuration(db, actor)['selection_revision'] == token
        assert db.query(PackActivation).filter_by(company_id=company_id).count() == 0
        assert db.query(ServicePolicy).filter_by(organization_id=company_id, kind='business_pack_theme').count() == 0
        assert db.query(AccessAudit).filter_by(company_id=company_id, operation='settings.business-packs.theme.activated').count() == 0
        retry = theme_selection.activate(db, actor, selection('hospital', token))
        assert retry['active_key'] == 'hospital'
