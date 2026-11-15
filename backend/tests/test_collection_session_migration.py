"""Static additive provenance migration; ambiguous history stays unassigned."""
from pathlib import Path
import os
import runpy

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

MIGRATION = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261114_104_collection_session.py'


def test_additive_migration_preserves_ambiguous_history_explicit_claims_and_native_ledgers():
    url = os.environ.get('SERVICE_CHECKOUT_TEST_DATABASE_URL', 'sqlite://')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'sqlite':
        assert parsed.host in {'localhost', '127.0.0.1', '::1'}
        assert parsed.database.startswith('business_suite_service_models_') and parsed.database.endswith('_test')
    engine = create_engine(url)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def foreign_keys(connection, record):
            connection.execute('PRAGMA foreign_keys=ON')
    migration = runpy.run_path(str(MIGRATION))
    with engine.begin() as connection:
        for statement in (
            'CREATE TABLE srm_pos_sessions (id INTEGER PRIMARY KEY, organization_id INTEGER, cash_total INTEGER)',
            'CREATE TABLE srm_pos_service_checkouts (id INTEGER PRIMARY KEY, organization_id INTEGER, pos_session_id INTEGER)',
            'CREATE TABLE srm_pos_checkout_payments (id INTEGER PRIMARY KEY, organization_id INTEGER, checkout_id INTEGER)',
            'CREATE TABLE srm_receipts (id INTEGER PRIMARY KEY, amount INTEGER)',
            'INSERT INTO srm_pos_sessions VALUES (1,1,500),(2,2,900),(3,1,700)',
            'INSERT INTO srm_pos_service_checkouts VALUES (1,1,1),(2,1,2),(3,2,1)',
            'INSERT INTO srm_pos_checkout_payments VALUES (1,1,1),(2,1,2),(3,1,3)',
            'INSERT INTO srm_receipts VALUES (1,500)',
        ):
            connection.exec_driver_sql(statement)
        before = connection.exec_driver_sql('SELECT * FROM srm_pos_sessions ORDER BY id').all()
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
            # Even same-company roots do not prove when/where a later cash
            # balance was collected; old payments remain unassigned.
            assert connection.exec_driver_sql('SELECT collection_session_id FROM srm_pos_checkout_payments ORDER BY id').scalars().all() == [None, None, None]
            connection.exec_driver_sql('UPDATE srm_pos_checkout_payments SET collection_session_id=3 WHERE id=1')
            migration['upgrade'](); migration['downgrade']()
        assert connection.exec_driver_sql('SELECT collection_session_id FROM srm_pos_checkout_payments ORDER BY id').scalars().all() == [3, None, None]
        assert connection.exec_driver_sql('SELECT * FROM srm_pos_sessions ORDER BY id').all() == before
        assert connection.exec_driver_sql('SELECT amount FROM srm_receipts').scalar_one() == 500
        assert inspect(connection).get_columns('srm_pos_checkout_payments')[-1]['default'] is None
        connection.exec_driver_sql('INSERT INTO srm_pos_checkout_payments (id,organization_id,checkout_id) VALUES (4,1,1)')
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
        assert connection.exec_driver_sql('SELECT collection_session_id FROM srm_pos_checkout_payments WHERE id=4').scalar_one_or_none() is None
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.exec_driver_sql('UPDATE srm_pos_checkout_payments SET collection_session_id=999 WHERE id=4')
    engine.dispose()
