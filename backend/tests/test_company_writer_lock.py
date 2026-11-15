"""Actual PostgreSQL transactions serialize lifecycle and checkout both ways."""
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.apps.srm.services.commercial import lock_tenant
from app.business_packs.service import _lock_company


@pytest.mark.parametrize('commercial_first', [True, False])
def test_lifecycle_and_commercial_writer_share_transaction_lock(db_engine, commercial_first):
    if db_engine.dialect.name != 'postgresql':
        pytest.skip('Requires independent PostgreSQL transaction locks')
    user = SimpleNamespace(id=1, organization_id=1)
    with Session(db_engine) as first, Session(db_engine) as second:
        first_lock = (lambda db: lock_tenant(db, user)) if commercial_first else (lambda db: _lock_company(db, 1))
        second_lock = (lambda db: _lock_company(db, 1)) if commercial_first else (lambda db: lock_tenant(db, user))
        first_lock(first)
        second.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(OperationalError) as error:
            second_lock(second)
        assert getattr(error.value.orig, 'sqlstate', None) == '55P03'
        second.rollback()
        first.rollback()
        second.execute(text("SET LOCAL lock_timeout = '1s'"))
        second_lock(second)
        second.rollback()
