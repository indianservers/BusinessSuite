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


@pytest.mark.parametrize('path', ['alembic/versions/20261116_085_telegram_experience.py', 'alembic_postgresql/versions/pg_20261116_124_telegram_experience.py'])
def test_telegram_experience_migration_preserves_existing_conversations(path):
    spec = importlib.util.spec_from_file_location('telegram_experience_migration', Path(__file__).parents[1] / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        metadata = sa.MetaData()
        for name in ['companies', 'power_apps_resources', 'power_telegram_identities', 'power_telegram_link_challenges', 'power_telegram_conversations']:
            sa.Table(name, metadata, sa.Column('id', sa.Integer(), primary_key=True))
        metadata.create_all(connection)
        connection.execute(metadata.tables['power_telegram_conversations'].insert().values(id=1))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert connection.execute(sa.text('select context from power_telegram_conversations where id=1')).scalar_one() == '{}'
            inspector = sa.inspect(connection)
            for name in ['power_telegram_identities', 'power_telegram_link_challenges']:
                assert 'customer_id' in {column['name'] for column in inspector.get_columns(name)}
            assert 'power_telegram_action_approvals' in inspector.get_table_names()
            module.downgrade()
            assert 'power_telegram_action_approvals' not in sa.inspect(connection).get_table_names()
            assert connection.execute(sa.text('select id from power_telegram_conversations')).scalar_one() == 1
    engine.dispose()
