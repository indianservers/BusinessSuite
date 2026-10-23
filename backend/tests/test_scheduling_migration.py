from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


@pytest.mark.parametrize("folder,prefix", [("alembic", ""), ("alembic_postgresql", "pg_")])
def test_schedule_table_round_trip(folder, prefix):
    path = Path(__file__).resolve().parents[1] / folder / "versions" / f"{prefix}20261023_008_scheduling.py"
    spec = spec_from_file_location("scheduling_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
        migration.upgrade()
        assert {column["name"] for column in inspect(connection).get_columns("schedule_boards")} == {"id", "tenant_key", "module", "source", "revision", "starts", "links"}
        assert inspect(connection).get_unique_constraints("schedule_boards")[0]["column_names"] == ["tenant_key", "module", "source"]
        migration.downgrade()
        assert "schedule_boards" not in inspect(connection).get_table_names()
    engine.dispose()
