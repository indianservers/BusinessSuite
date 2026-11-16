import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize('path', ['alembic/versions/20261116_084_telegram_operations.py', 'alembic_postgresql/versions/pg_20261116_123_telegram_operations.py'])
def test_telegram_migration_upgrade_and_downgrade(path):
    path = Path(__file__).parents[1] / path
    spec = importlib.util.spec_from_file_location('telegram_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        metadata = sa.MetaData()
        for table in ['companies', 'users', 'employees', 'power_apps_resources', 'power_apps_executions']:
            sa.Table(table, metadata, sa.Column('id', sa.Integer(), primary_key=True))
        metadata.create_all(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            inspector = sa.inspect(connection)
            assert 'power_telegram_messages' in inspector.get_table_names()
            assert {'employee_id', 'telegram_id', 'verified_at', 'revoked_at'} <= {column['name'] for column in inspector.get_columns('power_telegram_identities')}
            assert any(constraint['name'] == 'uq_telegram_message_update' for constraint in inspector.get_unique_constraints('power_telegram_messages'))
            module.downgrade()
            assert 'power_telegram_identities' not in sa.inspect(connection).get_table_names()
    engine.dispose()
