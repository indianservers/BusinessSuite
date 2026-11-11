import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_schedule_migration_is_additive_idempotent_and_deduplicates():
    engine=sa.create_engine('sqlite://')
    metadata=sa.MetaData()
    table=sa.Table('automation_scheduled_jobs',metadata,sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer),sa.Column('created_by',sa.Integer),sa.Column('job_type',sa.String),sa.Column('payload_json',sa.JSON))
    metadata.create_all(engine)
    path=Path(__file__).resolve().parents[1]/'alembic/versions/20261111_080_agent_schedules.py'
    spec=importlib.util.spec_from_file_location('agent_schedule_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade();migration.upgrade()
            value={'organization_id':1,'created_by':1,'job_type':'ai_agent_schedule','payload_json':{'ai_request_key':'test'}}
            connection.execute(table.insert(),value)
            with pytest.raises(sa.exc.IntegrityError):connection.execute(table.insert(),value)
            # Different actors and tenants remain independent. Other scheduler
            # job kinds retain their existing behavior and indexes.
            connection.execute(table.insert(),{**value,'created_by':2})
            connection.execute(table.insert(),{**value,'organization_id':2})
            connection.execute(table.insert(),[{**value,'job_type':'other'},{**value,'job_type':'other'}])
            migration.downgrade()
            assert connection.scalar(sa.select(sa.func.count()).select_from(table))==5
    engine.dispose()
