"""Exercise both migration variants without connecting to a real database."""
import importlib.util
from pathlib import Path
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from app.db.base import Base


@pytest.mark.parametrize("relative", [
    "alembic/versions/20261026_029_workforce_operations.py",
    "alembic_postgresql/versions/pg_20261026_029_workforce_operations.py",
])
def test_workforce_migration_round_trip_preserves_existing_data(relative):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE workforce_job_failures")
        connection.exec_driver_sql("DROP TABLE workforce_messages")
        connection.exec_driver_sql("DROP TABLE workforce_jobs")
        connection.execute(text("INSERT INTO companies (id,name) VALUES (1,'Existing customer')"))
        path = Path(__file__).resolve().parents[1] / relative
        spec = importlib.util.spec_from_file_location("workforce_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {"workforce_messages", "workforce_jobs"}.issubset(inspect(connection).get_table_names())
        assert "result" in {c["name"] for c in inspect(connection).get_columns("workforce_jobs")}
        assert any(i["name"] == "ix_workforce_message_inbox" for i in inspect(connection).get_indexes("workforce_messages"))
        migration.downgrade()
        assert "workforce_jobs" not in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT name FROM companies WHERE id=1")).scalar_one() == "Existing customer"
        migration.upgrade()
    engine.dispose()
