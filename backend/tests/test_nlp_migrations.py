import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.migration import MigrationContext


@pytest.mark.parametrize('folder,names',[
 ('alembic',['20261110_078_nlp_queries','20261110_079_nlp_training']),
 ('alembic_postgresql',['pg_20261110_095_nlp_queries','pg_20261110_096_nlp_training'])])
def test_new_tables_and_training_job_index_are_additive_repeatable(folder,names):
    engine=sa.create_engine('sqlite://')
    with engine.begin() as conn:
        for name in ('companies','users','pms_workspaces','ai_suite_runs'):conn.execute(sa.text(f'CREATE TABLE {name} (id INTEGER PRIMARY KEY)'))
        conn.execute(sa.text('CREATE TABLE automation_scheduled_jobs (id INTEGER PRIMARY KEY, organization_id INTEGER, created_by INTEGER, job_type TEXT, payload_json JSON)'))
        conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (1,1,1,'existing','{}')"))
        modules=[]
        for name in names:
            path=Path(__file__).resolve().parents[1]/folder/'versions'/(name+'.py')
            spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.op=Operations(MigrationContext.configure(conn));module.upgrade();module.upgrade();modules.append(module)
        assert {'ai_nlp_queries','ai_nlp_datasets'}<=set(sa.inspect(conn).get_table_names())
        conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (2,1,1,'ai_nlp_training','{\"ai_request_key\":\"same\"}')"))
        with pytest.raises(sa.exc.IntegrityError):conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (3,1,1,'ai_nlp_training','{\"ai_request_key\":\"same\"}')"))
        for module in reversed(modules):module.downgrade();module.downgrade()
        assert conn.execute(sa.text('SELECT job_type FROM automation_scheduled_jobs WHERE id=1')).scalar()=='existing'
