"""Static additive cash-intent migration preserves native money and references."""
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import runpy
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_cash_intent_upgrade_preserves_legacy_and_protects_bound_native_history():
    engine = sa.create_engine('sqlite://')
    @sa.event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    exercise_migration(engine)
    engine.dispose()


def exercise_migration(engine):
    metadata = sa.MetaData()
    users = sa.Table('users', metadata, sa.Column('id', sa.Integer, primary_key=True))
    sessions = sa.Table('srm_pos_sessions', metadata, sa.Column('id', sa.Integer, primary_key=True), sa.Column('organization_id', sa.Integer))
    old = sa.Table('srm_pos_cash_movements', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('organization_id', sa.Integer), sa.Column('session_id', sa.Integer, sa.ForeignKey('srm_pos_sessions.id', ondelete='CASCADE')),
        sa.Column('movement_type', sa.String(40)), sa.Column('amount', sa.Numeric(14, 2)), sa.Column('reason', sa.Text),
        sa.Column('created_by', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()))
    reference = sa.Table('existing_refund_sources', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('cash_id', sa.Integer, sa.ForeignKey('srm_pos_cash_movements.id', ondelete='RESTRICT')))
    owners = sa.Table('suite_branch_ownership', metadata, sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('company_id', sa.Integer), sa.Column('branch_id', sa.Integer),
        sa.Column('resource_table', sa.String), sa.Column('resource_key', sa.String),
        sa.UniqueConstraint('resource_table', 'resource_key'))
    metadata.create_all(engine)
    migration = runpy.run_path(str(Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261116_119_cash_intent.py'))
    assert migration['down_revision'] == 'pg_20261116_118_pharma_qty'
    with engine.begin() as connection:
        connection.execute(users.insert().values(id=1))
        connection.execute(sessions.insert(), [{'id': 1, 'organization_id': 1}, {'id': 2, 'organization_id': 1}])
        connection.execute(old.insert().values(id=10, organization_id=1, session_id=1, movement_type='cash_out',
            amount=Decimal('12.30'), reason='Legacy refund source', created_by=1))
        connection.execute(reference.insert().values(id=1, cash_id=10))
        connection.execute(owners.insert().values(id=1, company_id=1, branch_id=7,
            resource_table='srm_pos_sessions', resource_key='1'))
        before = dict(connection.execute(sa.select(old)).mappings().one())
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade'](); migration['upgrade'](); migration['downgrade']()
        assert dict(connection.execute(sa.select(old)).mappings().one()) == before
        assert connection.scalar(sa.select(reference.c.cash_id)) == 10
        cash = sa.Table('srm_pos_cash_movements', sa.MetaData(), autoload_with=connection)
        legacy = connection.execute(sa.select(cash).where(cash.c.id == 10)).mappings().one()
        assert all(legacy[name] is None for name in ('request_key','request_sha256','request_currency','request_branch_id','request_context_id'))
        key = str(uuid4())
        values = dict(id=11, organization_id=1, session_id=1, movement_type='cash_in', amount=Decimal('3.25'),
            reason='Native durable intent', created_by=1, request_key=key, request_sha256='a'*64,
            request_currency='INR', request_branch_id=7, request_context_id=None)
        connection.execute(cash.insert().values(**values))
        for mutation in ({'amount': Decimal('9.99')}, {'session_id': 2}, {'created_by': None},
                         {'request_key': None, 'request_sha256': None, 'request_currency': None, 'request_branch_id': None}):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(cash.update().where(cash.c.id == 11).values(**mutation))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(cash.delete().where(cash.c.id == 11))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(cash.insert().values(**{**values, 'id': 12, 'session_id': 2}))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(users.delete().where(users.c.id == 1))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(owners.update().where(owners.c.id == 1).values(branch_id=8))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(owners.delete().where(owners.c.id == 1))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(owners.insert().values(id=2, company_id=1, branch_id=8,
                resource_table='srm_pos_cash_movements', resource_key='11'))
        connection.execute(owners.insert().values(id=2, company_id=1, branch_id=7,
            resource_table='srm_pos_cash_movements', resource_key='11'))
        connection.execute(old.update().where(old.c.id == 10).values(reason='Legacy edit remains native'))
        assert connection.scalar(sa.select(cash.c.amount).where(cash.c.id == 11)) == Decimal('3.25')
def test_partial_sqlite_key_without_check_fails_closed_before_adding_columns():
    engine = sa.create_engine('sqlite://')
    migration = runpy.run_path(str(Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261116_119_cash_intent.py'))
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE srm_pos_cash_movements (id INTEGER PRIMARY KEY, request_key VARCHAR(36))')
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match='CHECK reconciliation'):
                migration['upgrade']()
        assert {item['name'] for item in sa.inspect(connection).get_columns('srm_pos_cash_movements')} == {'id', 'request_key'}
    engine.dispose()
