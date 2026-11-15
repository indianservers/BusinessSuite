from pathlib import Path
import runpy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.business_packs.restaurant.models import MODELS


def test_static_restaurant_extension_is_repeatable_and_retains_fulfillment_schema(db):
    path = Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261115_110_restaurant.py'
    migration = runpy.run_path(str(path))
    assert migration['down_revision'] == 'pg_20261115_109_pharma_stock'
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['upgrade']()
        migration['upgrade']()
        migration['downgrade']()
    for model in MODELS:
        assert set(model.__table__.c.keys()) <= {column['name'] for column in inspect(db.connection()).get_columns(model.__tablename__)}
    constraints = inspect(db.connection()).get_foreign_keys('business_restaurant_service_orders')
    assert any(row['referred_table'] == 'srm_pos_service_checkouts' and row['constrained_columns'] ==
        ['checkout_id', 'organization_id', 'branch_id', 'pack_context_id'] for row in constraints)
