import importlib.util
from pathlib import Path
import sqlalchemy as sa
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.apps.crm.models import CRMProduct, CRMService
from app.apps.srm.models import SRMProduct
from app.db.pos_catalog_upgrade import upgrade


@pytest.mark.parametrize("migration", ["alembic/versions/20261102_056_shared_catalog.py", "alembic_postgresql/versions/pg_20261102_057_shared_catalog.py"])
def test_migration_reuses_pos_and_preserves_links_stock_and_history(migration):
    engine = sa.create_engine("sqlite://")
    schema = sa.MetaData()
    tables = {}
    for model in (CRMProduct, CRMService, SRMProduct):
        tables[model.__tablename__] = sa.Table(model.__tablename__, schema, *[sa.Column(c.name, c.type, primary_key=c.primary_key) for c in model.__table__.columns])
    sa.Table("pms_workspaces", schema, sa.Column("id", sa.Integer, primary_key=True))
    deals = sa.Table("crm_deals", schema, sa.Column("id", sa.Integer, primary_key=True), sa.Column("catalog_items", sa.JSON))
    quotes = sa.Table("crm_quotation_items", schema, sa.Column("id", sa.Integer, primary_key=True), sa.Column("product_id", sa.Integer, sa.ForeignKey("crm_products.id", ondelete="SET NULL")), sa.Column("service_id", sa.Integer, sa.ForeignKey("crm_services.id", ondelete="SET NULL")), sa.Column("unit_price", sa.Numeric(14, 2)))
    schema.create_all(engine)
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        spec = importlib.util.spec_from_file_location("old_catalog", Path(__file__).parents[1] / migration)
        previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(previous)
        previous.op = operations; previous.upgrade()
        pos = tables["srm_products"]
        connection.execute(pos.insert().values(id=10, organization_id=1, sku="EXISTING", item_name="POS name", product_type="stock", current_quantity=31, sales_rate=90, active=True))
        connection.execute(tables["crm_products"].insert().values(id=1, organization_id=1, sku="EXISTING", name="CRM name", list_price=80, active=True))
        connection.execute(tables["crm_services"].insert().values(id=1, organization_id=1, service_code="SERVICE", name="Setup", default_rate=25, active=True))
        details = sa.Table("shared_catalog_details", sa.MetaData(), autoload_with=connection)
        links = sa.Table("shared_catalog_links", sa.MetaData(), autoload_with=connection)
        connection.execute(details.insert().values(id=1, organization_id=1, product_id=1, unit="pcs", images=["https://example.com/item.png"], custom_fields={"Edition": "Pro"}, pricing_options=[], version=2))
        connection.execute(links.insert().values(id=1, organization_id=1, target_type="lead", target_id=3, product_id=1, quantity=2, unit_price=80, discount=0, tax_rate=0, currency="INR"))
        connection.execute(deals.insert().values(id=1, catalog_items=[{"kind": "service", "item_id": 1, "quantity": 1, "unit_price": 25}]))
        connection.execute(quotes.insert().values(id=1, service_id=1, unit_price=25))
        upgrade(operations)
        rows = connection.execute(sa.select(pos)).mappings().all()
        assert len(rows) == 2
        existing = next(row for row in rows if row["id"] == 10)
        assert existing["current_quantity"] == 31 and existing["sales_rate"] == 90
        assert existing["metadata_json"]["images"] == ["https://example.com/item.png"]
        assert connection.execute(sa.select(links.c.product_id)).scalar_one() == 10
        assert connection.execute(sa.select(details.c.product_id)).scalar_one() == 10
        service = next(row for row in rows if row["product_type"] == "service")
        assert service["track_inventory"] is False
        assert connection.execute(sa.select(deals.c.catalog_items)).scalar_one()[0]["item_id"] == service["id"]
        quote = connection.execute(sa.select(quotes)).one()
        assert quote.service_id == service["id"] and quote.unit_price == 25
        for table in (details, links):
            assert all(fk["referred_table"] == "srm_products" for fk in sa.inspect(connection).get_foreign_keys(table.name) if fk["constrained_columns"] in (["product_id"], ["service_id"]))
        assert connection.execute(sa.select(sa.func.count()).select_from(tables["crm_products"])).scalar_one() == 1
    engine.dispose()
