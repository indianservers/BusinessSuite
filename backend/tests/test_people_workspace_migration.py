"""Execute the migration on a disposable legacy schema, including data backfill."""

import importlib.util
from pathlib import Path
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_people_team_migration_backfill_and_round_trip():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for ddl in [
            "CREATE TABLE users(id INTEGER PRIMARY KEY,role_id INTEGER,is_active BOOLEAN)",
            "CREATE TABLE pms_workspace_teams(id INTEGER PRIMARY KEY,workspace_id INTEGER,member_ids_json TEXT)",
            "CREATE TABLE pms_workspace_members(id INTEGER PRIMARY KEY,workspace_id INTEGER,user_id INTEGER,role TEXT)",
        ]:
            connection.execute(sa.text(ddl))
        connection.execute(
            sa.text("INSERT INTO users VALUES (1,NULL,1),(2,NULL,1),(3,NULL,1)")
        )
        connection.execute(
            sa.text("INSERT INTO pms_workspace_teams VALUES (1,10,'[1,1,2,3,999]')")
        )
        connection.execute(
            sa.text(
                "INSERT INTO pms_workspace_members VALUES (1,10,1,'Owner'),(2,10,2,'Member'),(3,10,3,'Guest')"
            )
        )
        path = (
            Path(__file__).parents[1]
            / "alembic_postgresql/versions/pg_20261031_045_people_workspace.py"
        )
        spec = importlib.util.spec_from_file_location("directory_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()  # Historical ORM bootstrap/retry must not duplicate memberships.
        assert connection.execute(
            sa.text(
                "SELECT team_id,user_id FROM pms_workspace_team_members ORDER BY user_id"
            )
        ).all() == [(1, 1), (1, 2)]
        assert connection.execute(
            sa.text("SELECT description,visibility FROM pms_workspace_teams")
        ).one() == ("", "workspace")
        module.downgrade()
        assert (
            "pms_workspace_team_members" not in sa.inspect(connection).get_table_names()
        )
        assert (
            connection.execute(
                sa.text("SELECT member_ids_json FROM pms_workspace_teams")
            ).scalar()
            == "[1,1,2,3,999]"
        )
