"""Upgrade an actual old schema and preserve existing assignment rows."""
import importlib.util
from pathlib import Path
from sqlalchemy import create_engine,inspect,text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.base import Base

def test_upgrade_017_preserves_legacy_rows_and_is_retryable(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.db'))
    Base.metadata.create_all(engine)
    new_tables=['pms_work_reviews','pms_work_submissions','intern_completion_reviews','intern_report_reviews','intern_task_schedules','intern_task_distribution_jobs','intern_batch_memberships','intern_batches','intern_legacy_file_maps','intern_legacy_task_maps']
    with engine.begin() as connection:
        for table in new_tables:connection.exec_driver_sql('DROP TABLE '+table)
        connection.exec_driver_sql('DROP TABLE pms_task_assignees')
        connection.exec_driver_sql('CREATE TABLE pms_task_assignees (task_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (task_id,user_id))')
        connection.exec_driver_sql('INSERT INTO pms_task_assignees VALUES (11,22)')
        connection.exec_driver_sql('DROP TABLE intern_hub_certificates')
        connection.exec_driver_sql('CREATE TABLE intern_hub_certificates (id INTEGER PRIMARY KEY, employee_id INTEGER, title VARCHAR(180))')
        connection.exec_driver_sql("INSERT INTO intern_hub_certificates VALUES (7,22,'Historical certificate')")
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261025_017_pms_intern_management.py'
        spec=importlib.util.spec_from_file_location('intern_pms_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.upgrade()
        row=connection.execute(text('SELECT task_id,user_id,execution_status,maximum_score FROM pms_task_assignees')).one()
        assert tuple(row)==(11,22,'To Do',100)
        assert connection.execute(text('SELECT title FROM intern_hub_certificates WHERE id=7')).scalar()=='Historical certificate'
        assert set(new_tables).issubset(inspect(connection).get_table_names())
        assert {'document_certificate_id','verification_id'}.issubset({c['name'] for c in inspect(connection).get_columns('intern_hub_certificates')})
    engine.dispose()
