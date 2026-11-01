"""Historical AI history is attributed only from a uniquely recorded parent tenant."""
from pathlib import Path
import importlib.util
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_ai_log_migration_keeps_unattributed_and_ambiguous_history_private():
    path=Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261101_050_ai_log_tenant.py'
    spec=importlib.util.spec_from_file_location('ai_log_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=sa.create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(sa.text('CREATE TABLE companies (id INTEGER PRIMARY KEY)'))
        c.execute(sa.text('INSERT INTO companies VALUES (1),(2)'))
        c.execute(sa.text('CREATE TABLE ai_prompt_runs (id INTEGER PRIMARY KEY)'))
        c.execute(sa.text('INSERT INTO ai_prompt_runs VALUES (10),(20),(30)'))
        c.execute(sa.text('CREATE TABLE ai_action_logs (id INTEGER PRIMARY KEY,prompt_run_id INTEGER)'))
        c.execute(sa.text('CREATE TABLE security_resource_ownership (resource_table TEXT,resource_id INTEGER,company_id INTEGER)'))
        c.execute(sa.text("INSERT INTO security_resource_ownership VALUES ('ai_prompt_runs',10,1),('ai_prompt_runs',20,1),('ai_prompt_runs',20,2)"))
        c.execute(sa.text('INSERT INTO ai_action_logs VALUES (1,10),(2,NULL),(3,20),(4,30)'))
        for table in ('ai_agent_actions','ai_user_feedback'):
            c.execute(sa.text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY,prompt_run_id INTEGER)'))
            c.execute(sa.text(f'INSERT INTO {table} VALUES (1,10),(2,NULL),(3,20),(4,30)'))
        migration.op=Operations(MigrationContext.configure(c));migration.upgrade()
        assert c.execute(sa.text('SELECT id,organization_id FROM ai_action_logs ORDER BY id')).all()==[(1,1),(2,None),(3,None),(4,None)]
        for table in ('ai_agent_actions','ai_user_feedback'):
            assert c.execute(sa.text(f'SELECT id,organization_id FROM {table} ORDER BY id')).all()==[(1,1),(2,None),(3,None),(4,None)]
        assert c.execute(sa.text('SELECT id,organization_id FROM ai_prompt_runs ORDER BY id')).all()==[(10,1),(20,None),(30,None)]
        migration.downgrade()
        assert c.execute(sa.text('SELECT count(*) FROM ai_action_logs')).scalar_one()==4
