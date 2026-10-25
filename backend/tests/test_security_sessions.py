"""Synthetic regression cases for shared access/refresh session boundaries."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from app.core.deps import token_record_id
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserSession


@pytest.mark.parametrize('value', [None, True, {}, [], 'abc', '-1', '0', '1.2', '9'*100, '\u0661'])
def test_invalid_identifier_claims_fail_closed(value):
    with pytest.raises(HTTPException) as exc:
        token_record_id(value)
    assert exc.value.status_code == 401


def test_signed_invalid_subject_is_unauthorized(client):
    token = create_access_token('not-a-record-id')
    response = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer '+token})
    assert response.status_code == 401


def test_expired_session_cannot_mint_fresh_tokens(client, db, superuser_headers):
    user = db.query(User).filter_by(email='testadmin@test.com').one()
    session = UserSession(user_id=user.id, session_token_hash='synthetic-only', status='Active',
                          expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    db.add(session); db.commit()
    token = create_refresh_token(user.id, session_id=session.id)
    response = client.post('/api/v1/auth/refresh', json={'refresh_token': token})
    assert response.status_code == 401
    assert 'access_token' not in response.json()


def test_signed_invalid_refresh_subject_is_unauthorized(client):
    response = client.post('/api/v1/auth/refresh', json={'refresh_token': create_refresh_token('invalid')})
    assert response.status_code == 401


def test_access_token_without_expiration_is_rejected():
    import jwt
    from app.core.config import settings
    from app.core.security import verify_access_token
    token=jwt.encode({'sub':'1','type':'access'},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
    assert verify_access_token(token) is None


def test_email_logging_never_records_reset_links_or_codes(caplog):
    import logging
    from app.core.email import send_email
    with caplog.at_level(logging.INFO):
        send_email('synthetic@example.com','Synthetic reset','SYNTHETIC-SECRET-CODE')
    assert 'SYNTHETIC-SECRET-CODE' not in caplog.text
    assert 'synthetic@example.com' not in caplog.text


def test_configuration_validation_redacts_secret_inputs():
    from app.core.config import Settings
    secret='SYNTHETIC-VALIDATION-SECRET-DO-NOT-LOG'
    with pytest.raises(ValueError) as exc:
        Settings(_env_file=None,SECRET_KEY=secret,MAX_UPLOAD_SIZE_MB='not-an-integer')
    assert secret not in str(exc.value)


def test_recent_session_reads_avoid_writes_but_recheck_revocation(client,db,superuser_headers):
    user=db.query(User).filter_by(email='testadmin@test.com').one()
    session=db.query(UserSession).filter_by(user_id=user.id).one()
    before=session.last_seen_at
    assert client.get('/api/v1/auth/me',headers=superuser_headers).status_code==200
    db.refresh(session)
    assert session.last_seen_at==before
    session.status='Revoked';db.commit()
    assert client.get('/api/v1/auth/me',headers=superuser_headers).status_code==401
