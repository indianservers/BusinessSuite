"""Migrate loopback app DB and provision/reuse a separate local mock accounting DB."""
from pathlib import Path
import json,os,secrets,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
os.chdir(ROOT/"backend")

def main():
    from app.core.config import settings
    from sqlalchemy import create_engine,text
    from sqlalchemy.engine import URL,make_url
    runtime=make_url(settings.SQLALCHEMY_DATABASE_URI)
    if runtime.host not in {"127.0.0.1","localhost"} or settings.POSTGRES_SERVER not in {"127.0.0.1","localhost"}:
        raise RuntimeError("Only verified loopback PostgreSQL targets are supported")
    if (runtime.port or 5432)!=settings.POSTGRES_PORT:raise RuntimeError("Maintenance and app database ports differ")
    admin=URL.create("postgresql+psycopg",username=settings.POSTGRES_USER,password=settings.POSTGRES_PASSWORD,host=settings.POSTGRES_SERVER,port=settings.POSTGRES_PORT,database="postgres")
    def migrate(target,app_database=False):
        env={**os.environ,"MIGRATION_DATABASE_URL":target.render_as_string(hide_password=False)}
        if not app_database:env.update(DATABASE_URL=target.render_as_string(hide_password=False),ENVIRONMENT="test",SERVERLESS="false",TENANT_DATABASES_ENABLED="false",PLATFORM_DATABASE_URL="",TENANT_REGISTRY_URL="",TENANT_PROVISIONING_URL="",ACCOUNTING_SYNC_WORKER_ENABLED="false")
        subprocess.run([sys.executable,"scripts/migrate_deployment.py"],env=env,check=True)
    migrate(admin.set(database=runtime.database),True)
    config_path=ROOT/".local/accounting-acceptance.env.json"
    if config_path.exists():
        saved=json.loads(config_path.read_text(encoding="utf-8"));target=make_url(saved['database_url']);name=target.database
        if target.host not in {"127.0.0.1","localhost"} or target.port!=admin.port or not name.startswith('business_suite_accounting_local_') or not name.endswith('_test'):
            raise RuntimeError("Existing QA configuration is outside the local accounting sandbox")
        target=admin.set(database=name)
    else:
        name='business_suite_accounting_local_'+secrets.token_hex(4)+'_test';target=admin.set(database=name)
    engine=create_engine(admin,isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        if not connection.execute(text('SELECT 1 FROM pg_database WHERE datname=:name'),{'name':name}).first():
            connection.exec_driver_sql('CREATE DATABASE '+engine.dialect.identifier_preparer.quote_identifier(name))
    engine.dispose()
    migrate(target)
    config_path.parent.mkdir(exist_ok=True)
    config_path.write_text(json.dumps({'database_url':target.render_as_string(hide_password=False),'database':name}),encoding='utf-8')
    print(json.dumps({'local_app_database':runtime.database,'qa_database':name,'qa_mock_only':True}))

if __name__=='__main__':main()
