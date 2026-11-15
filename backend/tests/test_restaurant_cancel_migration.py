from pathlib import Path
import runpy
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_original_identity_backfill_live_fk_and_provenance_safe_downgrade():
    migration = runpy.run_path(str(Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261115_117_restaurant_cancel.py'))
    assert migration['down_revision'] == 'pg_20261115_116_accounts_birth'
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        connection.exec_driver_sql('CREATE TABLE srm_sales_order_lines (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE business_restaurant_tab_lines (id INTEGER PRIMARY KEY, sales_order_line_id INTEGER NOT NULL UNIQUE REFERENCES srm_sales_order_lines(id) ON DELETE RESTRICT, quantity NUMERIC NOT NULL CHECK(quantity > 0))')
        connection.exec_driver_sql('INSERT INTO srm_sales_order_lines VALUES (17)')
        connection.exec_driver_sql('INSERT INTO business_restaurant_tab_lines VALUES (4,17,2.5)')
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
        row = connection.exec_driver_sql('SELECT * FROM business_restaurant_tab_lines').mappings().one()
        assert row['original_sales_order_line_id'] == row['sales_order_line_id'] == 17 and row['quantity'] == 2.5
        assert sa.inspect(connection).get_foreign_keys('business_restaurant_tab_lines')[0]['options']['ondelete'] == 'SET NULL'
        connection.exec_driver_sql('DELETE FROM srm_sales_order_lines WHERE id=17')
        row = connection.exec_driver_sql('SELECT * FROM business_restaurant_tab_lines').mappings().one()
        assert row['sales_order_line_id'] is None and row['original_sales_order_line_id'] == 17 and row['quantity'] == 2.5
        with Operations.context(MigrationContext.configure(connection)), pytest.raises(RuntimeError, match='provenance'):
            migration['downgrade']()
    engine.dispose()


import os
from uuid import uuid4
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data
from tests.test_restaurant_kitchen import post


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Requires actual owned PostgreSQL migration conversion')
def test_actual_pre117_charge_rows_survive_native_conversion(client, db, unpaid):
    from app.business_packs.restaurant.models import RestaurantTabLine
    assert db.bind.dialect.name == 'postgresql'
    assert db.bind.engine.url.host in {'127.0.0.1', 'localhost'} and db.bind.engine.url.database.endswith('_test')
    post(client, unpaid['headers'], '/tabs', data(unpaid))
    connection = db.connection()
    original = dict(connection.execute(sa.select(RestaurantTabLine.__table__)).mappings().one())
    versions = Path(__file__).parents[1] / 'alembic_postgresql/versions'
    old = runpy.run_path(str(versions / 'pg_20261115_113_restaurant_tabs.py'))
    migration = runpy.run_path(str(versions / 'pg_20261115_117_restaurant_cancel.py'))
    name = 'restaurant_117_owned_' + uuid4().hex
    quoted = connection.dialect.identifier_preparer.quote_identifier(name)
    previous = connection.scalar(sa.text('SHOW search_path'))
    connection.exec_driver_sql('CREATE SCHEMA ' + quoted)
    savepoint = connection.begin_nested()
    try:
        connection.execute(sa.text("SELECT set_config('search_path', :value, true)"), {'value': quoted + ', public'})
        _, ddl, indexes = next(row for row in old['_DDL']['postgresql'] if row[0] == 'business_restaurant_tab_lines')
        connection.exec_driver_sql(ddl)
        for _, sql in indexes: connection.exec_driver_sql(sql)
        legacy = sa.Table('business_restaurant_tab_lines', sa.MetaData(), autoload_with=connection, resolve_fks=False)
        assert 'original_sales_order_line_id' not in legacy.c
        connection.execute(legacy.insert().values(**{key: original[key] for key in legacy.c.keys()}))
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
        current = sa.Table('business_restaurant_tab_lines', sa.MetaData(), autoload_with=connection, resolve_fks=False)
        actual = connection.execute(sa.select(current)).mappings().one()
        assert all(actual[key] == original[key] for key in legacy.c.keys())
        assert actual['original_sales_order_line_id'] == original['sales_order_line_id']
        assert current.c.sales_order_line_id.nullable and not current.c.original_sales_order_line_id.nullable
        fk = next(key for key in sa.inspect(connection).get_foreign_keys(current.name) if key['constrained_columns'] == ['sales_order_line_id'])
        assert fk['options']['ondelete'] == 'SET NULL'
        with Operations.context(MigrationContext.configure(connection)):
            migration['downgrade']()
            migration['upgrade']()
        connection.execute(current.update().values(sales_order_line_id=None))
        with Operations.context(MigrationContext.configure(connection)), pytest.raises(RuntimeError, match='provenance'):
            migration['downgrade']()
    finally:
        if savepoint.is_active:
            savepoint.rollback()
        connection.execute(sa.text("SELECT set_config('search_path', :value, true)"), {'value': previous})
        connection.exec_driver_sql('DROP SCHEMA ' + quoted + ' CASCADE')
