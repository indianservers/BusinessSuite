"""A writer lock must serialize without changing native company metadata."""
from datetime import datetime
import sqlite3

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.company_writer import lock_company_writer
from app.models.company import Company


@pytest.fixture
def store(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'writer.sqlite'),
                           connect_args={'timeout': 0}, poolclass=NullPool)

    @event.listens_for(engine, 'connect')
    def clock(connection, _):
        connection.create_function('current_timestamp', 0, lambda: '2099-01-02 03:04:05')

    Company.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(Company.__table__.insert().values(
            id=1, name='Writer metadata fixture', updated_at=datetime(2020, 1, 1)))
    try:
        yield engine
    finally:
        engine.dispose()


def test_lock_preserves_every_company_column_and_real_edits_still_update_timestamp(store):
    with Session(store) as session:
        before = dict(session.execute(select(Company.__table__)).mappings().one())
        lock_company_writer(session, 1)
        lock_company_writer(session, 1)
        assert dict(session.execute(select(Company.__table__)).mappings().one()) == before
        session.execute(Company.__table__.update().where(Company.id == 1).values(name='Real edit'))
        after = session.execute(select(Company.__table__)).mappings().one()
        assert after['name'] == 'Real edit'
        assert after['updated_at'] == datetime(2099, 1, 2, 3, 4, 5)
        session.rollback()


def test_metadata_preserving_lock_still_blocks_an_independent_sqlite_writer(store):
    with Session(store) as first, Session(store) as second:
        assert first.connection().connection.driver_connection is not second.connection().connection.driver_connection
        lock_company_writer(first, 1)
        with pytest.raises(OperationalError) as denied:
            lock_company_writer(second, 1)
        assert denied.value.orig.sqlite_errorcode == sqlite3.SQLITE_BUSY
        second.rollback()
        first.rollback()
        lock_company_writer(second, 1)
        second.rollback()
