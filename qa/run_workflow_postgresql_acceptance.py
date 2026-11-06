"""Run migration, concurrency, browser and production-mode acceptance on local test DBs."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    from app.core.config import settings
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    source = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if source.get_backend_name() != "postgresql" or source.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Use a local PostgreSQL acceptance server with database-creation privileges")
    name = "business_suite_workflow_accept_" + uuid4().hex[:10] + "_test"
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    quote = admin.dialect.identifier_preparer.quote_identifier
    with admin.connect() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE {quote(name)}")
    target = source.set(database=name)
    env = {**os.environ, "TEST_DATABASE_URL": target.render_as_string(hide_password=False),
           "PLATFORM_DATABASE_URL": "", "TENANT_DATABASES_ENABLED": "false",
           "TENANT_REGISTRY_URL": "", "TENANT_PROVISIONING_URL": "", "TENANT_ALLOW_REMOTE_OPERATIONS": "false",
           "FAST_TEST_PASSWORD_HASHES": "1", "RUN_PMS_WORKFLOW_BROWSER": "1", "ENVIRONMENT": "test", "DEBUG": "false"}
    try:
        return subprocess.call([sys.executable, "-m", "pytest",
            "tests/test_pms_workflow_postgresql.py", "tests/test_pms_workflow_schemes.py",
            "tests/test_pms_workflow_types.py", "tests/test_pms_transition_approvals.py",
            "tests/test_postgresql_configuration.py", "-q", "--tb=short", "--disable-warnings",
            f"--junitxml={ROOT / 'outputs' / 'workflow-postgresql-acceptance.xml'}", *sys.argv[1:]],
            cwd=ROOT / "backend", env=env)
    finally:
        # Exact generated test name on the verified loopback server only.
        with admin.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE {quote(name)} WITH (FORCE)")
        admin.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
