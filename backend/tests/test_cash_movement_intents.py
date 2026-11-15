"""Durable native cash intent retries never duplicate movement or audit."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
import pytest
from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.apps.srm.models import SRMPOSCashMovement, SRMPOSSession, SRMAuditLog
from tests.srm_test_utils import auth_headers_for

PATH = '/api/v1/srm/pos/cash-movements'


@pytest.fixture
def till(client, db):
    ensure_business_os_seed(db, company_id=1)
    headers = auth_headers_for(client, db, 'cash-intent@srm.example.com', 'srm_sales_manager',
        permissions=['srm_view', 'srm_manage'])
    response = client.post('/api/v1/srm/pos/sessions', headers=headers, json={'opening_cash': '100'})
    assert response.status_code == 201, response.text
    return headers, response.json()['session']['id']


def command(till, **changes):
    return {'session_id': till[1], 'request_key': str(uuid4()), 'movement_type': 'cash_in',
            'amount': '10.00', 'reason': 'Verified till float', **changes}


def test_lost_reply_retries_same_native_movement_and_fresh_summary(client, db, till):
    body = command(till)
    first = client.post(PATH, headers=till[0], json=body)
    assert first.status_code == 201, first.text
    assert first.json()['expected_cash'] == 110
    assert first.json()['cash_intent_version'] == 119
    active = client.get('/api/v1/srm/pos/sessions/active', headers=till[0])
    assert active.status_code == 200, active.text
    assert active.json()['session']['id'] == till[1]
    assert active.json()['cash_intent_version'] == 119
    other = client.post(PATH, headers=till[0], json=command(till, amount='5'))
    assert other.status_code == 201, other.text
    body['amount'] = '10'
    replay = client.post(PATH, headers=till[0], json=body)
    assert replay.status_code == 201, replay.text
    assert replay.json()['movement_id'] == first.json()['movement_id']
    assert replay.json()['request_key'] == body['request_key']
    assert replay.json()['expected_cash'] == 115
    assert db.query(SRMPOSCashMovement).count() == 2
    assert db.query(SRMAuditLog).filter_by(entity_type='pos_cash_movement', action='created').count() == 2


@pytest.mark.parametrize('changes', [{'amount': '11'}, {'reason': 'Changed purpose'}, {'movement_type': 'cash_out'}])
def test_same_key_changed_body_conflicts_without_cash_or_audit(client, db, till, changes):
    body = command(till)
    first = client.post(PATH, headers=till[0], json=body)
    assert first.status_code == 201, first.text
    rejected = client.post(PATH, headers=till[0], json={**body, **changes})
    assert rejected.status_code == 409, rejected.text
    assert db.query(SRMPOSCashMovement).count() == 1
    assert db.query(SRMAuditLog).filter_by(entity_type='pos_cash_movement', action='created').count() == 1


def test_durable_committed_outcome_recovers_after_response_failure(client, db, till, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm import cash_movement_intents as intents
    body = command(till)
    original = intents._result
    def lost(*args):
        raise HTTPException(503, 'Simulated lost response after durable commit')
    monkeypatch.setattr(intents, '_result', lost)
    response = client.post(PATH, headers=till[0], json=body)
    assert response.status_code == 503, response.text
    item = db.query(SRMPOSCashMovement).one()
    identity = item.id
    assert not intents._BIRTHS
    monkeypatch.setattr(intents, '_result', original)
    replay = client.post(PATH, headers=till[0], json=body)
    assert replay.status_code == 201, replay.text
    assert replay.json()['movement_id'] == identity
    assert replay.json()['expected_cash'] == 110
    assert db.query(SRMPOSCashMovement).count() == 1
    assert db.query(SRMAuditLog).filter_by(entity_type='pos_cash_movement', action='created').count() == 1


def test_currency_corruption_blocks_replay_and_new_cash(client, db, till):
    body = command(till)
    response = client.post(PATH, headers=till[0], json=body)
    assert response.status_code == 201, response.text
    session = db.get(SRMPOSSession, till[1])
    session.metadata_json = {**session.metadata_json, 'cash_currency': 'USD'}
    db.commit()
    for candidate in (body, command(till)):
        rejected = client.post(PATH, headers=till[0], json=candidate)
        assert rejected.status_code == 409, rejected.text
    assert db.query(SRMPOSCashMovement).count() == 1


def test_closed_register_replay_and_changed_register_conflict(client, db, till):
    body = command(till)
    first = client.post(PATH, headers=till[0], json=body)
    assert first.status_code == 201, first.text
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=till[0],
        json={'session_id': till[1], 'counted_cash': '110'})
    assert closed.status_code == 201, closed.text
    replay = client.post(PATH, headers=till[0], json=body)
    assert replay.status_code == 201, replay.text
    assert replay.json()['movement_id'] == first.json()['movement_id']
    opened = client.post('/api/v1/srm/pos/sessions', headers=till[0], json={'opening_cash': '20'})
    assert opened.status_code == 201, opened.text
    changed = client.post(PATH, headers=till[0], json={**body, 'session_id': opened.json()['session']['id']})
    assert changed.status_code == 409, changed.text
    assert db.query(SRMPOSCashMovement).count() == 1


@pytest.mark.parametrize('amount', ['0', '-1', '0.001', '1000000000000'])
def test_keyed_cash_rejects_invalid_exact_minor_units(client, db, till, amount):
    response = client.post(PATH, headers=till[0], json=command(till, amount=amount))
    assert response.status_code == 422, response.text
    assert db.query(SRMPOSCashMovement).count() == 0


def test_failed_audit_rolls_back_and_same_key_can_retry(client, db, till, monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.core.deps import get_db
    from app.apps.srm.api import router
    previous = app.dependency_overrides[get_db]
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False,
        join_transaction_mode='create_savepoint')
    def request_db():
        with factory() as session:
            try:
                yield session
            except BaseException:
                session.rollback()
                raise
    body = command(till)
    original = router._audit
    def failed(db, user, entity_type, *args, **kwargs):
        if entity_type == 'pos_cash_movement':
            raise HTTPException(503, 'Simulated audit failure before commit')
        return original(db, user, entity_type, *args, **kwargs)
    app.dependency_overrides[get_db] = request_db
    try:
        monkeypatch.setattr(router, '_audit', failed)
        response = client.post(PATH, headers=till[0], json=body)
        assert response.status_code == 503, response.text
        assert db.query(SRMPOSCashMovement).count() == 0
        monkeypatch.setattr(router, '_audit', original)
        response = client.post(PATH, headers=till[0], json=body)
        assert response.status_code == 201, response.text
        assert response.json()['expected_cash'] == 110
        assert db.query(SRMPOSCashMovement).count() == 1
    finally:
        app.dependency_overrides[get_db] = previous


def test_replay_requires_current_native_cash_permission(client, db, till):
    from app.models.user import User
    body = command(till)
    first = client.post(PATH, headers=till[0], json=body)
    assert first.status_code == 201, first.text
    actor = db.query(User).filter_by(email='cash-intent@srm.example.com').one()
    actor.role.permissions = [permission for permission in actor.role.permissions if permission.name != 'srm_manage']
    db.commit()
    rejected = client.post(PATH, headers=till[0], json=body)
    assert rejected.status_code == 403, rejected.text
    assert 'movement_id' not in rejected.json()
    assert db.query(SRMPOSCashMovement).count() == 1


def test_authority_revocation_during_writer_acquisition_prevents_cash(client, db, till, monkeypatch):
    from app.apps.srm.services import commercial
    original = commercial.lock_tenant
    def revoke(db, user):
        original(db, user)
        user.role.permissions = [permission for permission in user.role.permissions if permission.name != 'srm_manage']
        db.flush()
    monkeypatch.setattr(commercial, 'lock_tenant', revoke)
    rejected = client.post(PATH, headers=till[0], json=command(till))
    assert rejected.status_code == 403, rejected.text
    assert db.query(SRMPOSCashMovement).count() == 0


def test_other_authorized_actor_conflicts_without_disclosing_or_replaying_key(client, db, till):
    body = command(till)
    first = client.post(PATH, headers=till[0], json=body)
    assert first.status_code == 201, first.text
    foreign = auth_headers_for(client, db, 'other-cash@srm.example.com', 'srm_sales_manager',
        permissions=['srm_view', 'srm_manage'])
    rejected = client.post(PATH, headers=foreign, json=body)
    assert rejected.status_code == 409, rejected.text
    assert 'movement_id' not in rejected.json()
    assert db.query(SRMPOSCashMovement).count() == 1


@pytest.mark.parametrize('mutation', ['amount', 'clear_proof', 'delete'])
def test_orm_cannot_rewrite_confirmed_native_intent(client, db, till, mutation):
    body = command(till)
    response = client.post(PATH, headers=till[0], json=body)
    assert response.status_code == 201, response.text
    item = db.query(SRMPOSCashMovement).one()
    with pytest.raises(ValueError), db.begin_nested():
        if mutation == 'amount':
            item.amount = Decimal('99')
        elif mutation == 'clear_proof':
            item.request_key = item.request_sha256 = item.request_currency = item.request_branch_id = None
        else:
            item.request_key = None
            db.delete(item)
        db.flush()
    db.refresh(item)
    assert item.amount == Decimal('10')
    assert item.request_key == body['request_key']


def test_missing_schema_fails_before_register_opening_commit(client, db, till, monkeypatch):
    from app.db import schema_columns
    original = schema_columns.table_columns
    def old_schema(connection, tables):
        result = original(connection, tables)
        if SRMPOSCashMovement.__tablename__ in result:
            result = {**result, SRMPOSCashMovement.__tablename__: result[SRMPOSCashMovement.__tablename__] - {'request_key'}}
        return result
    monkeypatch.setattr(schema_columns, 'table_columns', old_schema)
    before = db.query(SRMPOSSession).count()
    response = client.post('/api/v1/srm/pos/sessions', headers=till[0], json={'opening_cash': '70'})
    assert response.status_code == 503, response.text
    assert db.query(SRMPOSSession).count() == before
    response = client.post(PATH, headers=till[0], json=command(till))
    assert response.status_code == 503, response.text
    assert db.query(SRMPOSCashMovement).count() == 0


def test_legacy_keyless_orm_update_and_delete_remain_native(client, db, till):
    body = command(till)
    body.pop('request_key')
    created = client.post(PATH, headers=till[0], json=body)
    assert created.status_code == 201, created.text
    item = db.query(SRMPOSCashMovement).one()
    item.reason = 'Legacy correction'
    db.commit()
    assert item.reason == 'Legacy correction'
    db.delete(item)
    db.commit()
    assert db.query(SRMPOSCashMovement).count() == 0
