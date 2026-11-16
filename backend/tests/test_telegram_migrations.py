import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
import os
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_power_runtime import db
from tests.test_power_apps import actors
from tests.test_telegram_operations import bot


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


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Requires disposable PostgreSQL')
def test_postgres_experience_upgrade_preserves_existing_identity_and_conversation(db, bot):
    from tests.test_telegram_experience import deliver
    from app.apps.power_apps.models import TelegramConversation, TelegramIdentity
    deliver(db, bot, 1, text='/start')
    thread = db.query(TelegramConversation).one()
    linked = db.query(TelegramIdentity).one()
    ident, identity_id, original_state = thread.id, linked.id, dict(thread.state)
    counts = {name: db.execute(sa.text('select count(*) from ' + name)).scalar_one() for name in ['users', 'employees', 'power_apps_resources', 'power_telegram_messages']}
    path = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261116_124_telegram_experience.py'
    spec = importlib.util.spec_from_file_location('telegram_pg_live_upgrade', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(db.connection())):
        module.downgrade()
        assert 'context' not in {column['name'] for column in sa.inspect(db.connection()).get_columns('power_telegram_conversations')}
        module.upgrade()
    db.expire_all()
    upgraded = db.get(TelegramConversation, ident)
    assert upgraded.identity_id == identity_id and upgraded.state == original_state and upgraded.context == {}
    assert db.get(TelegramIdentity, identity_id).customer_id is None
    for name, count in counts.items():
        assert db.execute(sa.text('select count(*) from ' + name)).scalar_one() == count


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
