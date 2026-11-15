from pathlib import Path
from uuid import uuid4
import runpy
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.business_packs.restaurant.models import RestaurantServiceOrder
from tests.test_restaurant_kitchen import restaurant, setup_order, scenario, catalog, directory_identity


def test_actual_pre113_paid_row_survives_additive_unpaid_migration(client, db, restaurant):
    if db.bind.dialect.name != 'postgresql':
        pytest.skip('Actual deployed PostgreSQL ALTER and paid source FK preservation')
    assert db.bind.engine.url.host in {'127.0.0.1', 'localhost'} and db.bind.engine.url.database.endswith('_test')
    result = setup_order(client, restaurant, table=False)
    connection = db.connection()
    original = connection.execute(sa.select(RestaurantServiceOrder.__table__).where(RestaurantServiceOrder.id == result['id'])).mappings().one()
    versions = Path(__file__).parents[1]/'alembic_postgresql/versions'
    old = runpy.run_path(str(versions/'pg_20261115_110_restaurant.py'))
    migration = runpy.run_path(str(versions/'pg_20261115_113_restaurant_tabs.py'))
    assert migration['down_revision'] == 'pg_20261115_112_pharma_recall'
    name = 'restaurant_113_owned_'+uuid4().hex
    quoted = connection.dialect.identifier_preparer.quote_identifier(name)
    previous = connection.scalar(sa.text("SELECT current_setting('search_path')"))
    connection.exec_driver_sql('CREATE SCHEMA '+quoted)
    try:
        connection.execute(sa.text("SELECT set_config('search_path', :value, true)"), {'value': quoted+', public'})
        _, ddl, indexes = next(row for row in old['_DDL']['postgresql'] if row[0] == 'business_restaurant_service_orders')
        connection.exec_driver_sql(ddl)
        for _, sql in indexes:
            connection.exec_driver_sql(sql)
        legacy = sa.Table('business_restaurant_service_orders', sa.MetaData(), autoload_with=connection, resolve_fks=False)
        assert 'source_kind' not in legacy.c
        connection.execute(legacy.insert().values(**{key: original[key] for key in legacy.c.keys()}))
        with Operations.context(MigrationContext.configure(connection)):
            migration['upgrade']()
            migration['upgrade']()
            migration['downgrade']()
        current = sa.Table('business_restaurant_service_orders', sa.MetaData(), autoload_with=connection, resolve_fks=False)
        actual = connection.execute(sa.select(current).where(current.c.id == result['id'])).mappings().one()
        assert actual['source_kind'] == 'paid_pos' and actual['checkout_id'] == restaurant['checkout']['id']
        assert all(actual[key] == original[key] for key in legacy.c.keys())
        assert current.c.checkout_id.nullable
        keys = sa.inspect(connection).get_foreign_keys('business_restaurant_service_orders')
        assert any(key['name'] == 'fk_restaurant_order_checkout_scope' and key['referred_table'] == 'srm_pos_service_checkouts' for key in keys)
    finally:
        connection.execute(sa.text("SELECT set_config('search_path', :value, true)"), {'value': previous})
        # Only this UUID schema in the verified owned test database is removed.
        connection.exec_driver_sql('DROP SCHEMA '+quoted+' CASCADE')
