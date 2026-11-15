from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.operations import Operations


def migration():
    path = Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261116_120_rest_split.py'
    spec = spec_from_file_location('restaurant_split_120', path)
    module = module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_split_120_empty_upgrade_downgrade_and_frozen_model_columns_match():
    from app.business_packs.restaurant.split_models import MODELS
    module = migration()
    assert module.revision == 'pg_20261116_120_rest_split' and len(module.revision) <= 32
    assert module.down_revision == 'pg_20261116_119_cash_intent'
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        inspector = sa.inspect(connection)
        for model in MODELS:
            assert set(model.__table__.c.keys()) == {c['name'] for c in inspector.get_columns(model.__tablename__)}
            assert all(fk['options']['ondelete'] == 'RESTRICT' for fk in inspector.get_foreign_keys(model.__tablename__))
        module.downgrade()
        assert not set(model.__tablename__ for model in MODELS) & set(sa.inspect(connection).get_table_names())
        module.upgrade()
    engine.dispose()


def test_split_120_refuses_to_erase_even_one_historical_source():
    module = migration()
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        # Synthetic history only for downgrade refusal; never an authorization
        # fixture. Omitted parents prevent source insertion with guards active.
        connection.exec_driver_sql('DROP TRIGGER rest_split_0_insert')
        connection.execute(sa.text('''INSERT INTO business_restaurant_bill_groups
            (service_order_id,organization_id,branch_id,pack_context_id,created_by,request_key,request_sha256)
            VALUES (1,1,1,1,1,:key,:digest)'''), {'key': str(uuid4()), 'digest': 'a'*64})
        with pytest.raises(RuntimeError, match='history cannot be erased'): module.downgrade()
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql('DELETE FROM business_restaurant_bill_groups')
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM business_restaurant_bill_groups').scalar_one() == 1
    engine.dispose()
