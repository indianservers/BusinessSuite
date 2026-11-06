import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from test_core import app_with_db
from app.extensions import db
from app.models import AdjustmentReview,ManufacturingSource,Product


def test_workflow_controls_migration_additive_roundtrip():
    app=app_with_db()
    file=Path(__file__).resolve().parents[1]/'migrations_postgresql/versions/20261106_workflow_controls.py'
    spec=importlib.util.spec_from_file_location('workflow_controls_migration',file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with app.app_context():
        ManufacturingSource.__table__.drop(db.engine);AdjustmentReview.__table__.drop(db.engine)
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                tables=set(inspect(connection).get_table_names())
                assert {'stock_adjustment_reviews','manufacturing_component_sources'} <= tables
                module.downgrade()
                assert 'stock_adjustment_reviews' not in inspect(connection).get_table_names()
                module.upgrade()
        assert db.session.get(Product,1).sku=='P1'
