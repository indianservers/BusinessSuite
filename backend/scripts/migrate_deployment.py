"""Apply production migrations before publishing the Vercel backend.

Preview builds never migrate a shared production database. Database credentials
stay inside Vercel; no schema changes happen in request handlers or cold starts.
"""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    if os.environ.get("VERCEL_ENV") != "production":
        print("Skipping deployment migrations outside production.")
        return
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text
    from app.db.session import engine

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '60s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(827460231)"))
        if not inspect(connection).has_table("alembic_version"):
            raise RuntimeError("Provision the database baseline before deploying the application")
        revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        print(f"Schema revisions before deployment: {revisions}; target: {head}")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        actual = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if actual != [head]:
            raise RuntimeError("Database migration did not reach the application head")
    print(f"Production schema verified at {head}.")


if __name__ == "__main__":
    main()
