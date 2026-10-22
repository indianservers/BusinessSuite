"""Run selected tests on a dedicated PostgreSQL database, never the app DB."""
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import settings


if __name__ == "__main__":
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("PostgreSQL required")
    name = os.environ.get("POSTGRES_TEST_DATABASE", "business_suite_integration_test")
    if not name.startswith("business_suite_") or not name.endswith("_test") or name == url.database:
        raise RuntimeError("Test database must be a separate business_suite_*_test database")
    target = url.set(database=name)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        # Fixed disposable test DB only; this never targets the configured app DB.
        quoted = admin.dialect.identifier_preparer.quote_identifier(name)
        conn.exec_driver_sql(f'DROP DATABASE IF EXISTS {quoted} WITH (FORCE)')
        conn.exec_driver_sql(f'CREATE DATABASE {quoted}')
    admin.dispose()
    env = dict(os.environ, TEST_DATABASE_URL=target.render_as_string(hide_password=False), ENVIRONMENT="test", DEBUG="false")
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]], env=env))
