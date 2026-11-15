from pathlib import Path
import runpy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.business_packs.accounting_firm.models import MODELS


def test_accounts_static_migration_repeatable_and_retains_history(db):
    migration=runpy.run_path(str(Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261115_111_accounts.py'))
    assert migration['down_revision']=='pg_20261115_110_restaurant'
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['upgrade']();migration['upgrade']();migration['downgrade']()
    for model in MODELS:
        assert set(model.__table__.c.keys()) <= {col['name'] for col in inspect(db.connection()).get_columns(model.__tablename__)}
    assert any(fk['referred_table']=='business_accounts_periods' and len(fk['constrained_columns'])==4
        for fk in inspect(db.connection()).get_foreign_keys('business_accounts_commands'))
