"""Deployed additive Retail schema preserves source history against raw writes."""
from pathlib import Path
import runpy
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect,select
from sqlalchemy.exc import DBAPIError
from app.business_packs.retail.models import MODELS,RetailSaleStockSource,RetailReturn,RetailReturnLine
from tests.test_retail_return_http import retail_http,retail_setup,post_original,command,BASE,scenario,catalog,directory_identity

MIGRATION=Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261115_108_retail_returns.py'


def test_static_retail_108_is_repeatable_and_retains_native_sources(db,retail_http):
    source=db.query(RetailSaleStockSource).one()
    identity=source.id;original=source.quantity
    migration=runpy.run_path(str(MIGRATION))
    assert migration['down_revision']=='pg_20261115_107_pack_owner'
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['upgrade']();migration['upgrade']();migration['downgrade']()
    for model in MODELS:
        assert set(model.__table__.c.keys())<={column['name'] for column in inspect(db.connection()).get_columns(model.__tablename__)}
    table=RetailSaleStockSource.__table__
    for command in (table.update().where(table.c.id==identity).values(quantity=original+1),
                    table.delete().where(table.c.id==identity)):
        with pytest.raises(DBAPIError),db.begin_nested():
            db.connection().execute(command)
    assert db.connection().scalar(select(table.c.quantity).where(table.c.id==identity))==original


def test_issued_refund_and_cash_drawer_history_reject_raw_rewrites(client,db,retail_http):
    post_original(db,retail_http)
    response=client.post(BASE,headers=retail_http[0],json=command(retail_http))
    assert response.status_code==201,response.text
    root=db.get(RetailReturn,response.json()['id'])
    migration=runpy.run_path(str(MIGRATION))
    with Operations.context(MigrationContext.configure(db.connection())):migration['upgrade']()
    from app.apps.srm.models import SRMPOSCashMovement
    cash=SRMPOSCashMovement.__table__;returns=RetailReturn.__table__;lines=RetailReturnLine.__table__
    for statement in (
        returns.update().where(returns.c.id==root.id).values(net_amount=1,tax_amount=0,refund_amount=1,revision=root.revision+1),
        lines.delete().where(lines.c.return_id==root.id),
        cash.update().where(cash.c.id==root.cash_movement_id).values(amount=1),
        cash.delete().where(cash.c.id==root.cash_movement_id),
    ):
        with pytest.raises(DBAPIError),db.begin_nested():db.connection().execute(statement)
    assert db.connection().scalar(select(cash.c.amount).where(cash.c.id==root.cash_movement_id))==118
