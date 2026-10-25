import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.base import Base
import pytest


def test_shared_batch_upgrade_retains_legacy_records_and_is_retryable(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'synthetic-migration.db'))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP TABLE intern_application_documents')
        connection.exec_driver_sql('DROP TABLE intern_application_events')
        connection.exec_driver_sql('DROP TABLE intern_hub_applications')
        connection.exec_driver_sql('CREATE TABLE intern_hub_applications (id INTEGER PRIMARY KEY, reference VARCHAR(40), email VARCHAR(100), status VARCHAR(30))')
        connection.exec_driver_sql("INSERT INTO intern_hub_applications VALUES (1,'SYNTHETIC','synthetic@example.com','Pending')")
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261025_018_shared_batches.py'
        spec=importlib.util.spec_from_file_location('shared_batch_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.upgrade()
        row=connection.execute(text('SELECT reference,status,organization_id,lifecycle FROM intern_hub_applications WHERE id=1')).one()
        assert tuple(row)==('SYNTHETIC','Pending',1,'Pending Verification')
        assert {'uploader_hash','claim_hash','application_id'}.issubset({column['name'] for column in inspect(connection).get_columns('intern_application_documents')})


@pytest.mark.parametrize('migration',['alembic/versions/20261025_019_document_tenant_scope.py','alembic_postgresql/versions/pg_20261025_019_document_tenant_scope.py'])
def test_document_tenant_migration_preserves_legacy_partition_and_indexes(tmp_path,migration):
    engine=create_engine('sqlite:///'+str(tmp_path/'synthetic-document-migration.db'))
    with engine.begin() as connection:
        for table in ('document_templates','company_policies'):
            connection.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, name VARCHAR(100))')
            connection.exec_driver_sql(f"INSERT INTO {table} VALUES (1,'SYNTHETIC LEGACY')")
        path=Path(__file__).resolve().parents[1]/migration
        spec=importlib.util.spec_from_file_location('document_tenant_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.upgrade()
        for table in ('document_templates','company_policies'):
            assert connection.execute(text(f'SELECT organization_id FROM {table} WHERE id=1')).scalar()==1
            assert f'ix_{table}_organization_id' in {index['name'] for index in inspect(connection).get_indexes(table)}


@pytest.mark.parametrize('migration',['alembic/versions/20261025_020_upload_source_quota.py','alembic_postgresql/versions/pg_20261025_020_upload_source_quota.py'])
def test_quota_upgrade_handles_earlier_document_schema(tmp_path,migration):
    engine=create_engine('sqlite:///'+str(tmp_path/'synthetic-quota-migration.db'))
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE intern_application_documents (id INTEGER PRIMARY KEY, name VARCHAR(100))')
        connection.exec_driver_sql("INSERT INTO intern_application_documents VALUES (1,'SYNTHETIC')")
        path=Path(__file__).resolve().parents[1]/migration
        spec=importlib.util.spec_from_file_location('source_quota_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.upgrade()
        assert connection.execute(text('SELECT name FROM intern_application_documents WHERE id=1')).scalar()=='SYNTHETIC'
        assert 'uploader_hash' in {column['name'] for column in inspect(connection).get_columns('intern_application_documents')}
