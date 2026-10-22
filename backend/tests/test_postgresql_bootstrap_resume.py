from sqlalchemy import text
from app.db.migrations import upgrade_schema


def test_baseline_can_resume_after_committed_schema_without_losing_rows(db_engine):
    if db_engine.dialect.name != "postgresql":
        import pytest
        pytest.skip("PostgreSQL migration integration")
    assert db_engine.url.database.endswith("_test")
    # Reproduce an interrupted bootstrap: baseline DDL committed, version stamp
    # not committed. Only the disposable test database is changed.
    with db_engine.begin() as db:
        before = db.execute(text("SELECT count(*) FROM companies")).scalar()
        db.execute(text("DROP TABLE pms_collaboration_events"))
        db.execute(text("DROP TABLE scheduled_job_runs"))
        db.execute(text("DELETE FROM alembic_version"))
    upgrade_schema()
    with db_engine.connect() as db:
        assert db.execute(text("SELECT count(*) FROM companies")).scalar() == before
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar() == "pg_20261022_002"
        assert db.execute(text("SELECT count(*) FROM scheduled_job_runs")).scalar() == 0
