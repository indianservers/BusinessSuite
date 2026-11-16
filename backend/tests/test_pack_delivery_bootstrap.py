"""Registration must work before tests import any delivery mapper."""
import json,os,subprocess,sys
from pathlib import Path


def test_fresh_default_model_bootstrap_creates_private_delivery_table(tmp_path):
    code="""
import json
from sqlalchemy import create_engine,inspect
from app.db.base import Base
assert 'business_pack_delivery_sources' in Base.metadata.tables
engine=create_engine('sqlite://')
with engine.begin() as connection:
 Base.metadata.create_all(connection)
 columns={row['name'] for row in inspect(connection).get_columns('business_pack_delivery_sources')}
 assert {'email_outbox_id','notification_id','context_id','payload_sha256','source_key'}<=columns
 assert connection.exec_driver_sql('SELECT COUNT(*) FROM business_pack_delivery_sources').scalar_one()==0
 print(json.dumps({'columns':len(columns),'empty':True}))
engine.dispose()
"""
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(tmp_path/'owned-bootstrap.db')}
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout.splitlines()[-1])=={'columns':17,'empty':True}
