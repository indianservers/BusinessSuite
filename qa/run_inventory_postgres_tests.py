"""Run standalone Inventory/POS tests on a disposable PostgreSQL database."""
from pathlib import Path
import os
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

if __name__ == "__main__":
    source = make_url(settings.SQLALCHEMY_DATABASE_URI)
    target = source.set(database="business_suite_inventory_test")
    engine = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.exec_driver_sql('DROP DATABASE IF EXISTS "business_suite_inventory_test" WITH (FORCE)')
        conn.exec_driver_sql('CREATE DATABASE "business_suite_inventory_test"')
    engine.dispose()
    env = dict(os.environ, APP_ENV="testing", TEST_DATABASE_URI=target.render_as_string(hide_password=False),
               INVENTORY_DATABASE_URL=target.render_as_string(hide_password=False), PYTHONUNBUFFERED="1")
    folder = ROOT / "backend/app/apps/inventory/vyapara_erp"
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "tests", "-v", "--tb=short", *sys.argv[1:]], cwd=folder, env=env))
