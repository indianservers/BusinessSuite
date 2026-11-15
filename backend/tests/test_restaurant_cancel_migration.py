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
