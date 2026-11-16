"""Actual additive migration, no historical source inference."""
import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from tests.test_pack_delivery_static_guards import _migration,schema


def _baseline(connection):
    schema(connection)
    connection.exec_driver_sql('DROP TABLE business_pack_delivery_sources')


def test_actual_upgrade_repeats_without_backfilling_private_history(monkeypatch):
    engine=sa.create_engine('sqlite://')
    with engine.begin() as connection:
        _baseline(connection)
        monkeypatch.setattr(_migration,'op',Operations(MigrationContext.configure(connection)))
        _migration.upgrade();_migration.upgrade()
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM business_pack_delivery_sources'))==0
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM business_pack_record_ownership'))==1
        assert set(_migration.COLUMNS)=={c['name'] for c in sa.inspect(connection).get_columns(_migration.TABLE)}
        with pytest.raises(RuntimeError,match='Retained private origin'):_migration.downgrade()
    engine.dispose()


def test_actual_empty_downgrade_removes_only_new_provenance_table(monkeypatch):
    engine=sa.create_engine('sqlite://')
    with engine.begin() as connection:
        _baseline(connection)
        connection.exec_driver_sql('DELETE FROM business_pack_record_ownership')
        monkeypatch.setattr(_migration,'op',Operations(MigrationContext.configure(connection)))
        _migration.upgrade();_migration.downgrade()
        inspector=sa.inspect(connection)
        assert not inspector.has_table(_migration.TABLE)
        assert inspector.has_table('business_pack_record_ownership')
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM email_outbox'))==2
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM notifications'))==2
    engine.dispose()
