"""Migration proof for historical native quantities and exact medicine lots."""
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import runpy
import pytest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select

from app.apps.srm.models import SRMPOSReturn, SRMPOSReturnLine


MIGRATION = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261115_114_return_precision.py'


def test_native_return_precision_preserves_history_and_exact_fraction(db):
    parent = SRMPOSReturn(organization_id=1, return_number='PRECISION-' + uuid4().hex)
    db.add(parent)
    db.flush()
    # Reproduce deployed 113 storage inside the disposable fixture transaction.
    if db.get_bind().dialect.name == 'postgresql':
        db.connection().exec_driver_sql('ALTER TABLE srm_pos_return_lines ALTER COLUMN quantity TYPE NUMERIC(12,2)')
    before_column = next(c for c in inspect(db.connection()).get_columns('srm_pos_return_lines') if c['name'] == 'quantity')
    old = SRMPOSReturnLine(return_id=parent.id, quantity=Decimal('9999999999.99'), description='Historical exact quantity')
    db.add(old)
    db.flush()
    old_id = old.id
    migration = runpy.run_path(str(MIGRATION))
    assert migration['down_revision'] == 'pg_20261115_113_restaurant_tabs'
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['upgrade']()
        migration['upgrade']()
    after_column = next(c for c in inspect(db.connection()).get_columns('srm_pos_return_lines') if c['name'] == 'quantity')
    assert {key: after_column[key] for key in ('nullable', 'default')} == {
        key: before_column[key] for key in ('nullable', 'default')}
    db.expire_all()
    assert db.get(SRMPOSReturnLine, old_id).quantity == Decimal('9999999999.99')
    fractional = SRMPOSReturnLine(return_id=parent.id, quantity=Decimal('.001'), description='Exact original lot fraction')
    db.add(fractional)
    db.flush()
    fractional_id = fractional.id
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['downgrade']()
    db.expire_all()
    assert db.get(SRMPOSReturnLine, fractional_id).quantity == Decimal('.001')
    if db.get_bind().dialect.name == 'postgresql':
        column = next(c for c in inspect(db.connection()).get_columns('srm_pos_return_lines') if c['name'] == 'quantity')
        assert column['type'].scale >= 3
    assert db.connection().scalar(select(SRMPOSReturnLine.quantity).where(SRMPOSReturnLine.id == old_id)) == Decimal('9999999999.99')


def test_unexpected_native_return_capacity_requires_reconciliation(db):
    if db.get_bind().dialect.name != 'postgresql':
        pytest.skip('PostgreSQL enforces declared NUMERIC capacity')
    db.connection().exec_driver_sql('ALTER TABLE srm_pos_return_lines ALTER COLUMN quantity TYPE NUMERIC(13,3)')
    migration = runpy.run_path(str(MIGRATION))
    with Operations.context(MigrationContext.configure(db.connection())):
        with pytest.raises(RuntimeError, match='precision requires schema reconciliation'):
            migration['upgrade']()
