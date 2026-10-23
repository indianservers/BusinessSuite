from pathlib import Path
import ast


def test_feature_migration_chains_reference_existing_revisions():
    backend = Path(__file__).resolve().parents[1]
    for folder, expected in [("alembic_postgresql", "pg_20261023_008"), ("alembic", "20261023_008")]:
        revisions = {}
        for path in (backend / folder / "versions").glob("*.py"):
            values = {}
            for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"revision", "down_revision"}:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
            if "revision" in values:
                assert values["revision"] not in revisions
                revisions[values["revision"]] = values.get("down_revision")
        for revision, parent in revisions.items():
            for predecessor in parent if isinstance(parent, tuple) else [parent] if parent else []:
                assert predecessor in revisions, f"{folder}: {revision} references missing {predecessor}"
        referenced = {p for parent in revisions.values() for p in (parent if isinstance(parent, tuple) else [parent] if parent else [])}
        assert len(set(revisions) - referenced) == 1
        assert expected in revisions


def test_feature_migrations_upgrade_an_existing_schema_twice():
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.apps.project_management import models
    from app.models.user import User
    backend = Path(__file__).resolve().parents[1]
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for name in ["users", "pms_projects", "pms_tasks", "pms_workspaces"]:
            connection.execute(sa.text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("INSERT INTO pms_tasks (id) VALUES (42)"))
        for path in sorted((backend / "alembic_postgresql/versions").glob("pg_20261023_00[1-7]_*.py")):
            spec = importlib.util.spec_from_file_location(path.stem, path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
        inspector = sa.inspect(connection)
        for table in ["pms_custom_fields", "pms_custom_field_values", "pms_task_types", "pms_running_timers", "pms_documents", "pms_document_revisions"]:
            assert inspector.has_table(table)
        assert "task_type" in {column["name"] for column in inspector.get_columns("pms_custom_fields")}
        assert connection.execute(sa.text("SELECT id FROM pms_tasks")).scalar() == 42
    engine.dispose()
