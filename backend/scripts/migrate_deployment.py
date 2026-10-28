"""Apply PostgreSQL migrations, including a fresh baseline, before API startup."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.pool import NullPool
    from app.core.config import settings

    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, poolclass=NullPool, pool_pre_ping=True,
        connect_args=settings.SQLALCHEMY_CONNECT_ARGS)

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.connect() as connection:
        # The baseline commits bounded DDL batches. A session lock survives those
        # commits; an outer engine.begin() would prevent Alembic autocommit blocks.
        connection.execute(text("SET lock_timeout = '60s'"))
        connection.execute(text("SELECT pg_advisory_lock(827460231)"))
        revisions = (connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                     if inspect(connection).has_table("alembic_version") else [])
        print(f"Schema revisions before deployment: {revisions}; target: {head}")
        connection.commit()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        actual = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if actual != [head]:
            raise RuntimeError("Database migration did not reach the application head")
        connection.execute(text("SELECT pg_advisory_unlock(827460231)"))
        connection.commit()
    print(f"Production schema verified at {head}.")


if __name__ == "__main__":
    main()
