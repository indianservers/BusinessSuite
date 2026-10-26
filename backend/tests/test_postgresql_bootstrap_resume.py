from sqlalchemy import text
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_baseline_can_resume_after_committed_schema_without_losing_rows(db_engine):
    if db_engine.dialect.name != "postgresql":
        import pytest
        pytest.skip("PostgreSQL migration integration")
    assert db_engine.url.database.endswith("_test")
    # Interrupt only the baseline, not an already fully migrated database.
    # An isolated schema also prevents a failed recovery from poisoning other tests.
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    with db_engine.connect() as db:
        db.execute(text("CREATE SCHEMA bootstrap_resume_test"))
        db.execute(text("SET search_path TO bootstrap_resume_test"))
        db.commit()
        config.attributes["connection"] = db
        try:
            command.upgrade(config, "pg_20261022_001")
            db.commit()
            db.execute(text("INSERT INTO companies (name) VALUES ('Recovery sentinel')"))
            db.execute(text("DELETE FROM alembic_version"))
            db.commit()
            command.upgrade(config, "head")
            db.commit()
            assert db.execute(text("SELECT name FROM companies")).scalars().all() == ["Recovery sentinel"]
            assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
            assert db.execute(text("SELECT count(*) FROM scheduled_job_runs")).scalar() == 0
        finally:
            db.rollback()
            db.execute(text("SET search_path TO public"))
            db.execute(text("DROP SCHEMA bootstrap_resume_test CASCADE"))
            db.commit()
