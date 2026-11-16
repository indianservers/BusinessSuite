import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text, inspect


def test_category_migration_preserves_existing_rows_and_is_repeatable():
    path = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261116_122_employee_categories.py'
    spec = importlib.util.spec_from_file_location('employee_category_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        for table in ('employees', 'srm_service_booking_policies'):
            connection.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)'))
            connection.execute(text(f'INSERT INTO {table} (id) VALUES (1)'))
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        module.upgrade()
        assert connection.scalar(text('SELECT work_categories FROM employees WHERE id=1')) == '[]'
        assert connection.scalar(text('SELECT employee_categories FROM srm_service_booking_policies WHERE id=1')) == '[]'
        assert inspect(connection).get_columns('employees')[1]['nullable'] is False
