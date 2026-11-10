import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.migration import MigrationContext


@pytest.mark.parametrize('directory,name', [('alembic', '20261110_077_ai_job_requests'), ('alembic_postgresql', 'pg_20261110_094_ai_job_requests')])
def test_assistant_request_index_is_additive_repeatable_and_enforces_dedup(directory, name):
    path = Path(__file__).resolve().parents[1] / directory / 'versions' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE automation_scheduled_jobs (id INTEGER PRIMARY KEY, organization_id INTEGER, created_by INTEGER, job_type TEXT, payload_json JSON)'))
        conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (1, 1, 1, 'existing_job', '{}')"))
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade(); module.upgrade()
        conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (2,1,1,'ai_reminder','{\"ai_request_key\":\"unique\"}')"))
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (3,1,1,'ai_reminder','{\"ai_request_key\":\"unique\"}')"))
        conn.execute(sa.text("INSERT INTO automation_scheduled_jobs VALUES (4,2,1,'ai_reminder','{\"ai_request_key\":\"unique\"}')"))
        module.downgrade(); module.downgrade()
        assert conn.execute(sa.text('SELECT job_type FROM automation_scheduled_jobs WHERE id=1')).scalar() == 'existing_job'
