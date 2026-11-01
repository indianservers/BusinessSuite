"""Exercise the real deployment chain in a newly created, loopback-only test DB."""
from pathlib import Path
import os, subprocess, sys, uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.chdir(ROOT/'backend')
from app.core.config import settings
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
if __name__=='__main__':
 source=make_url(settings.SQLALCHEMY_DATABASE_URI)
 if source.host not in {'127.0.0.1','localhost'}: raise RuntimeError('Only a local PostgreSQL server may host this test')
 name='business_suite_pms_upgrade_'+uuid.uuid4().hex[:10]+'_test'
 engine=create_engine(source.set(database='postgres'),isolation_level='AUTOCOMMIT')
 with engine.connect() as c: c.exec_driver_sql(f'CREATE DATABASE "{name}"')
 target=source.set(database=name)
 env=dict(os.environ,TEST_DATABASE_URL=target.render_as_string(hide_password=False),FAST_TEST_PASSWORD_HASHES='1')
 try:
  result=subprocess.call([sys.executable,'-m','pytest','tests/test_pms_postgresql_upgrade.py','tests/test_postgresql_configuration.py',*sys.argv[1:],'-q','--disable-warnings','--tb=short'],cwd=ROOT/'backend',env=env)
 finally:
  # Exact locally generated disposable test DB; never reuse the configured app DB.
  with engine.connect() as c: c.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
  engine.dispose()
 raise SystemExit(result)
