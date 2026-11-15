"""The migration preserves history, currency types and wider existing storage."""
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import runpy

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine

MIGRATION = Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261116_118_pharma_dispensing_precision.py'


def apply(db, operation='upgrade'):
    script = runpy.run_path(str(MIGRATION))
    assert script['revision'] == 'pg_20261116_118_pharma_qty'
    assert script['down_revision'] == 'pg_20261115_117_rest_cancel'
    with Operations.context(MigrationContext.configure(db.connection())):
        script[operation]()


def columns(db):
    return {column['name']: column for column in inspect(db.connection()).get_columns('srm_sales_order_lines')}


def test_postgresql_quantity_upgrade_preserves_historical_maximum_and_exact_fraction(db):
    if db.get_bind().dialect.name != 'postgresql':
        pytest.skip('Native PostgreSQL NUMERIC storage proof')
    db.connection().exec_driver_sql('ALTER TABLE srm_sales_order_lines ALTER COLUMN quantity TYPE NUMERIC(12,2)')
    before = columns(db)
    order = SRMSalesOrder(organization_id=1, order_number='PRECISION-'+uuid4().hex, title='Historical quantity capacity')
    db.add(order)
    db.flush()
    old = SRMSalesOrderLine(sales_order_id=order.id, quantity=Decimal('9999999999.99'), unit_price=0)
    db.add(old)
    db.flush()
    old_id = old.id
    apply(db)
    apply(db)
    after = columns(db)
    assert after['quantity']['type'].scale >= 3
    assert after['quantity']['type'].precision-after['quantity']['type'].scale >= 10
    assert {name: after['quantity'][name] for name in ('nullable', 'default')} == {
        name: before['quantity'][name] for name in ('nullable', 'default')}
    for name in ('unit_price', 'discount_amount', 'tax_amount', 'line_total'):
        assert str(before[name]['type']) == str(after[name]['type'])
    db.expire_all()
    assert db.get(SRMSalesOrderLine, old_id).quantity == Decimal('9999999999.99')
    fraction = SRMSalesOrderLine(sales_order_id=order.id, quantity=Decimal('.001'), unit_price=100)
    db.add(fraction)
    db.flush()
    fraction_id = fraction.id
    apply(db, 'downgrade')
    db.expire_all()
    assert db.get(SRMSalesOrderLine, fraction_id).quantity == Decimal('.001')
    assert db.connection().scalar(select(SRMSalesOrderLine.quantity).where(SRMSalesOrderLine.id == old_id)) == Decimal('9999999999.99')


@pytest.mark.parametrize('storage', ['NUMERIC(24,10)', 'NUMERIC'])
def test_postgresql_upgrade_preserves_already_wider_quantity_storage(db, storage):
    if db.get_bind().dialect.name != 'postgresql':
        pytest.skip('Native PostgreSQL NUMERIC storage proof')
    # Both storage strings are fixed test parameters, never request input.
    db.connection().exec_driver_sql(f'ALTER TABLE srm_sales_order_lines ALTER COLUMN quantity TYPE {storage}')
    before = str(columns(db)['quantity']['type'])
    apply(db)
    assert str(columns(db)['quantity']['type']) == before


def test_postgresql_unexpected_quantity_capacity_requires_reconciliation(db):
    if db.get_bind().dialect.name != 'postgresql':
        pytest.skip('Native PostgreSQL NUMERIC storage proof')
    db.connection().exec_driver_sql('ALTER TABLE srm_sales_order_lines ALTER COLUMN quantity TYPE NUMERIC(10,2)')
    with pytest.raises(RuntimeError, match='capacity requires schema reconciliation'):
        apply(db)
