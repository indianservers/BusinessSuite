"""Preserve production session isolation for real nested canonical HTTP calls."""
import pytest


@pytest.fixture(autouse=True)
def canonical_employee_request_session(client, db):
    from fastapi import Request
    from sqlalchemy.orm import Session
    from app.core.deps import get_db
    previous = client.app.dependency_overrides[get_db]

    def isolated(request: Request):
        if request.url.hostname == 'suite-internal' and request.url.path.startswith(('/api/v1/employees/', '/api/v1/leave/')):
            with Session(bind=db.get_bind(), join_transaction_mode='create_savepoint') as session:
                assert session is not db
                try:
                    yield session
                finally:
                    assert 'business_pack_request_binding' not in session.info
                    assert 'business_common_core_scope' not in session.info
        else:
            yield from previous()

    client.app.dependency_overrides[get_db] = isolated
    try:
        yield
    finally:
        client.app.dependency_overrides[get_db] = previous
