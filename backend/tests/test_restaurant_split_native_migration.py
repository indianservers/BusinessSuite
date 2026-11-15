"""Actual 119→120 conversion and unavailable/partial-schema denial on owned PG."""
import os
from pathlib import Path

import pytest
from fastapi import HTTPException
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text

from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
from app.business_packs.restaurant.models import RestaurantTabLine
from app.business_packs.restaurant.service import ensure_schema
from tests.test_restaurant_settlement import settlement, unpaid, scenario, catalog, directory_identity
from tests.test_restaurant_split_migration import migration


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Requires a guarded owned PostgreSQL test database')
def test_actual_119_to_120_preserves_native_sources_and_requires_complete_provenance_schema(db, settlement):
    connection = db.connection()
    url = connection.engine.url
    assert url.get_backend_name() == 'postgresql' and url.host in {'127.0.0.1','localhost'} and url.database.endswith('_test')
    config = Config(str(Path(__file__).parents[1]/'alembic.ini'))
    config.attributes['connection'] = connection
    before = {model.__tablename__: [dict(row) for row in connection.execute(select(model.__table__)).mappings()]
        for model in (SRMSalesOrder, SRMSalesOrderLine, RestaurantTabLine)}
    assert before['srm_sales_orders'] and before['business_restaurant_tab_lines']
    command.downgrade(config, 'pg_20261116_119_cash_intent')
    assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'pg_20261116_119_cash_intent'
    with pytest.raises(HTTPException) as missing: ensure_schema(db)
    assert missing.value.status_code == 503
    module = migration()
    _, ddl, _ = module._DDL['postgresql'][0]
    connection.exec_driver_sql(ddl)
    with pytest.raises(HTTPException) as partial: ensure_schema(db)
    assert partial.value.status_code == 503
    connection.exec_driver_sql('DROP TABLE business_restaurant_bill_groups')
    command.upgrade(config, 'pg_20261116_120_rest_split')
    assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'pg_20261116_120_rest_split'
    ensure_schema(db)
    for model in (SRMSalesOrder, SRMSalesOrderLine, RestaurantTabLine):
        assert [dict(row) for row in connection.execute(select(model.__table__)).mappings()] == before[model.__tablename__]
    inspector = inspect(connection)
    for table, _, _ in module._DDL['postgresql']:
        assert inspector.has_table(table)
        assert all(fk['options'].get('ondelete') == 'RESTRICT' for fk in inspector.get_foreign_keys(table))
    triggers = connection.execute(text("""SELECT t.tgname,t.tgdeferrable,t.tginitdeferred FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=current_schema() AND t.tgname LIKE 'rest_split_%' AND NOT t.tgisinternal""")).all()
    assert {row.tgname for row in triggers} == {*(f'rest_split_{index}_source' for index in range(4)), 'rest_split_0_commit', 'rest_split_3_commit'}
    assert all(row.tgdeferrable and row.tginitdeferred for row in triggers if row.tgname.endswith('_commit'))
