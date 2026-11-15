"""Independent committed native PostgreSQL HTTP requests and migration history."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.deps import get_db
from app.apps.srm.models import SRMPOSCashMovement, SRMAuditLog
from app.apps.business_os.services.module_service import ensure_business_os_seed
from tests.srm_test_utils import auth_headers_for
from tests.test_payroll_qa_concurrency import payroll_engine

PATH = '/api/v1/srm/pos/cash-movements'


@pytest.fixture
def live_cash(payroll_engine):
    engine = payroll_engine
    assert engine.dialect.name == 'postgresql'
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    overrides = dict(app.dependency_overrides)
    names = ('business_os_session_factory', 'business_os_close_session',
        'audit_session_factory', 'audit_close_session', 'audit_commit')
    previous = {name: getattr(app.state, name, None) for name in names}
    client = TestClient(app)
    seed = factory()
    seed.info['security_http_timeout'] = True
    try:
        def seed_db():
            yield seed
        app.dependency_overrides[get_db] = seed_db
        app.state.business_os_session_factory = lambda: seed
        app.state.business_os_close_session = False
        app.state.audit_session_factory = lambda: seed
        app.state.audit_close_session = False
        app.state.audit_commit = False
        ensure_business_os_seed(seed, company_id=1)
        headers = auth_headers_for(client, seed, 'pg-cash@srm.example.com', 'srm_sales_manager',
            permissions=['srm_view', 'srm_manage'])
        opened = client.post('/api/v1/srm/pos/sessions', headers=headers, json={'opening_cash': '100'})
        assert opened.status_code == 201, opened.text
        register = opened.json()['session']['id']
        seed.close()
        def request_db():
            with factory() as session:
                session.info['security_http_timeout'] = True
                try:
                    yield session
                except BaseException:
                    session.rollback()
                    raise
        app.dependency_overrides[get_db] = request_db
        app.state.business_os_session_factory = factory
        app.state.business_os_close_session = True
        app.state.audit_session_factory = factory
        app.state.audit_close_session = True
        app.state.audit_commit = True
        yield client, factory, headers, register
    finally:
        seed.close()
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        for name, value in previous.items():
            if value is None:
                if hasattr(app.state, name):
                    delattr(app.state, name)
            else:
                setattr(app.state, name, value)


@pytest.mark.parametrize('changed', [False, True])
def test_genuine_concurrent_cash_requests_share_one_movement_and_audit(live_cash, monkeypatch, changed):
    client, factory, headers, register = live_cash
    from app.apps.srm.services import commercial
    original = commercial.lock_tenant
    start = Barrier(2)
    pids = []
    def actual_wait(db, user):
        pids.append(db.connection().scalar(text('SELECT pg_backend_pid()')))
        start.wait(timeout=20)
        return original(db, user)
    monkeypatch.setattr(commercial, 'lock_tenant', actual_wait)
    body = {'session_id': register, 'request_key': str(uuid4()), 'movement_type': 'cash_in',
        'amount': '5.00', 'reason': 'Actual concurrent native cash'}
    bodies = [body, {**body, 'amount': '7.00'} if changed else body]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.post, PATH, headers=headers, json=payload) for payload in bodies]
        results = [future.result(timeout=30) for future in futures]
    assert len(set(pids)) == 2, 'Race must use two actual PostgreSQL connections'
    assert sorted(item.status_code for item in results) == ([201, 409] if changed else [201, 201]), [r.text for r in results]
    successes = [item.json() for item in results if item.status_code == 201]
    assert len({item['movement_id'] for item in successes}) == 1
    with factory() as db:
        item = db.query(SRMPOSCashMovement).filter_by(request_key=body['request_key']).one()
        assert db.query(SRMPOSCashMovement).count() == 1
        assert db.query(SRMAuditLog).filter_by(entity_type='pos_cash_movement', action='created').count() == 1
        assert successes[0]['expected_cash'] == 100 + float(item.amount)


def test_postgresql_rollback_then_same_key_retry(live_cash, monkeypatch):
    client, factory, headers, register = live_cash
    from fastapi import HTTPException
    from app.apps.srm.api import router
    original = router._audit
    def broken(db, actor, entity_type, *args, **kwargs):
        if entity_type == 'pos_cash_movement':
            raise HTTPException(503, 'Injected native audit failure before commit')
        return original(db, actor, entity_type, *args, **kwargs)
    body = {'session_id': register, 'request_key': str(uuid4()), 'movement_type': 'cash_out',
        'amount': '2.00', 'reason': 'Actual PostgreSQL rollback retry'}
    monkeypatch.setattr(router, '_audit', broken)
    failed = client.post(PATH, headers=headers, json=body)
    assert failed.status_code == 503, failed.text
    with factory() as db:
        assert db.query(SRMPOSCashMovement).count() == 0
    monkeypatch.setattr(router, '_audit', original)
    success = client.post(PATH, headers=headers, json=body)
    assert success.status_code == 201, success.text
    assert success.json()['expected_cash'] == 98
    with factory() as db:
        assert db.query(SRMPOSCashMovement).count() == 1
        assert db.query(SRMAuditLog).filter_by(entity_type='pos_cash_movement', action='created').count() == 1


def test_postgresql_119_upgrade_repeat_and_native_history(payroll_engine):
    """Real legacy table upgrade in an owned schema of the guarded race database."""
    from tests.test_cash_movement_intent_migration import exercise_migration
    schema = 'cash119_' + uuid4().hex
    assert schema.replace('_', '').isalnum()
    with payroll_engine.begin() as connection:
        quoted = connection.dialect.identifier_preparer.quote_identifier(schema)
        connection.exec_driver_sql(f'CREATE SCHEMA {quoted}')
    isolated = create_engine(payroll_engine.url,
        connect_args={'options': f'-c timezone=UTC -c search_path={schema} -c lock_timeout=20000 -c statement_timeout=30000'},
        hide_parameters=True)
    try:
        exercise_migration(isolated)
    finally:
        isolated.dispose()
        with payroll_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA {quoted} CASCADE')
