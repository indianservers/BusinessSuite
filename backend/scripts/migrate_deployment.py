"""Apply PostgreSQL migrations, including a fresh baseline, before API startup."""
from pathlib import Path
import sys
import os
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Lock namespace v2 is used only on direct migration sessions. The retired key
# 827460231 may be orphaned in a transaction-pool backend after older failed
# builds. All those builds are terminal; leave their application sessions alone.
MIGRATION_LOCK_ID = 827460232


def migration_url(runtime_url):
    """Session locks and Alembic commits require a direct Postgres session."""
    from sqlalchemy.engine import make_url

    url = make_url(os.environ.get("MIGRATION_DATABASE_URL") or runtime_url)
    host = url.host or ""
    if host.endswith(".neon.tech") and "-pooler." in host:
        url = url.set(host=host.replace("-pooler.", ".", 1))
    return url


@contextmanager
def migration_lock(connection):
    from sqlalchemy import text

    connection.execute(text("SET lock_timeout = '60s'"))
    connection.execute(text(f"SELECT pg_advisory_lock({MIGRATION_LOCK_ID})"))
    try:
        yield
    finally:
        # A failed DDL statement leaves the transaction aborted. Roll it back
        # before releasing the session lock, including when verification fails.
        connection.rollback()
        connection.execute(text(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})"))
        connection.commit()


def main():
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    from app.db.base import Base
    from app.db.schema_health import require_model_schema

    engine = create_engine(migration_url(settings.SQLALCHEMY_DATABASE_URI), poolclass=NullPool, pool_pre_ping=True,
        connect_args={**settings.SQLALCHEMY_CONNECT_ARGS, "application_name": "businesssuite-migrate"})

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.connect() as connection, migration_lock(connection):
        # The baseline commits bounded DDL batches. A session lock survives those
        # commits; an outer engine.begin() would prevent Alembic autocommit blocks.
        revisions = (connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                     if inspect(connection).has_table("alembic_version") else [])
        print(f"Schema revisions before deployment: {revisions}; target: {head}")
        connection.commit()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        actual = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if actual != [head]:
            raise RuntimeError("Database migration did not reach the application head")
        report = require_model_schema(connection, Base.metadata)
        print(f"Runtime schema verified: {report['checked_tables']} tables, {report['checked_columns']} columns.")
    print(f"Production schema verified at {head}.")


if __name__ == "__main__":
    main()
