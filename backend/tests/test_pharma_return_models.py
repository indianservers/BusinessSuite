"""Foundation only: real sale provenance, constraints and static migration guards."""
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import runpy

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, inspect
from sqlalchemy.exc import DBAPIError

from app.business_packs.pharma.return_models import PharmaReturn,PharmaReturnLine,PharmaReturnLot,MODELS
from app.business_packs.pharma.models import PharmaBatchAllocation
from app.apps.srm.service_checkout_models import POSCheckoutLine
from app.apps.srm.models import SRMPOSReturn,SRMPOSReturnLine,SRMInventoryBatch
from tests.test_pharma_fefo import lots,sale
from tests.test_pharma_receipts import pharma
from tests.test_service_checkout import scenario,catalog,directory_identity

MIGRATION=Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261115_115_pharma_returns.py'


@pytest.fixture
def source(client,db,lots):
    response=client.post('/api/v1/srm/service-checkout',headers=lots[0][0],json=sale(lots,paid=True))
    assert response.status_code==201,response.text
    checkout=response.json();line=db.query(POSCheckoutLine).filter_by(checkout_id=checkout['id']).one()
    allocation=db.query(PharmaBatchAllocation).filter_by(sales_order_line_id=line.sales_order_line_id).order_by(PharmaBatchAllocation.id).first()
    return lots,checkout,line,allocation


def graph(db,source,**root_patch):
    lots,checkout,line,allocation=source;case=lots[0]
    native=SRMPOSReturn(organization_id=1,return_number='SOURCE-'+uuid4().hex,
        sales_order_id=checkout['sales_order_id'],session_id=lots[2],customer_id=101,created_by=case[1].id,
        subtotal=Decimal('.10'),tax_amount=Decimal('.02'),refund_amount=Decimal('.12'),refund_status='pending')
    db.add(native);db.flush()
    root=PharmaReturn(organization_id=1,branch_id=case[2],pack_context_id=case[3],checkout_id=checkout['id'],
        request_key=str(uuid4()),request_sha256='a'*64,created_by=case[1].id,
        sales_order_id=checkout['sales_order_id'],invoice_id=checkout['invoice']['id'],collection_session_id=lots[2],
        native_return_id=native.id,refund_method='cash',payment_reference='',currency='INR',reason='Original lot return',
        net_amount=Decimal('.10'),tax_amount=Decimal('.02'),refund_amount=Decimal('.12'),state='draft')
    for key,value in root_patch.items():setattr(root,key,value)
    db.add(root);db.flush()
    native_line=SRMPOSReturnLine(return_id=native.id,sales_order_line_id=line.sales_order_line_id,
        product_id=line.product_id,warehouse_id=allocation.warehouse_id,quantity=Decimal('.001'),
        unit_price=100,tax_amount=Decimal('.02'),line_total=Decimal('.12'),restock=False,condition='quarantine')
    db.add(native_line);db.flush()
    returned=PharmaReturnLine(return_id=root.id,checkout_id=root.checkout_id,organization_id=1,
        branch_id=root.branch_id,pack_context_id=root.pack_context_id,checkout_line_id=line.id,product_id=line.product_id,
        sales_order_line_id=line.sales_order_line_id,invoice_line_id=line.invoice_line_id,native_return_line_id=native_line.id,
        quantity=Decimal('.001'),net_amount=Decimal('.10'),tax_amount=Decimal('.02'),gross_amount=Decimal('.12'))
    db.add(returned);db.flush()
    original_batch=db.get(SRMInventoryBatch,allocation.batch_id)
    quarantine=SRMInventoryBatch(organization_id=1,product_id=line.product_id,warehouse_id=allocation.warehouse_id,
        batch_number='RETURN-'+uuid4().hex,expiry_date=allocation.expiry_date,quantity=Decimal('.001'),
        available_quantity=0,status='quarantined',unit_cost=original_batch.unit_cost,manufacture_date=original_batch.manufacture_date)
    db.add(quarantine);db.flush()
    lot=PharmaReturnLot(return_line_id=returned.id,return_id=root.id,checkout_id=root.checkout_id,
        checkout_line_id=line.id,organization_id=1,branch_id=root.branch_id,pack_context_id=root.pack_context_id,
        product_id=line.product_id,sales_order_line_id=line.sales_order_line_id,warehouse_id=allocation.warehouse_id,
        allocation_id=allocation.id,original_batch_id=allocation.batch_id,quarantine_batch_id=quarantine.id,
        original_batch_number=allocation.batch_number,original_expiry_date=allocation.expiry_date,
        quantity=Decimal('.001'),disposition='quarantine')
    return root,returned,lot,quarantine


def test_actual_original_allocation_binds_separate_unavailable_lot(db,source):
    root,line,lot,batch=graph(db,source)
    db.add(lot);db.flush()
    assert lot.original_batch_id!=lot.quarantine_batch_id and batch.available_quantity==0
    assert line.quantity==lot.quantity==Decimal('.001')
    with pytest.raises(ValueError,match='immutable'):
        with db.begin_nested():
            lot.original_batch_number='replaced';db.flush()


@pytest.mark.parametrize('field,value',[('allocation_id',999999),('original_batch_id',999999),
    ('product_id',999999),('warehouse_id',999999),('checkout_line_id',999999),
    ('quantity',Decimal('.0001')),('stock_movement_id',999999)])
def test_wrong_original_lot_or_precision_never_persists(db,source,field,value):
    root,line,lot,batch=graph(db,source)
    with pytest.raises(ValueError):
        with db.begin_nested():
            setattr(lot,field,value);db.add(lot);db.flush()
    assert db.query(PharmaReturnLot).count()==0


@pytest.mark.parametrize('field,value',[('status','available'),('available_quantity',Decimal('.001')),
                                      ('quantity',Decimal('.002'))])
def test_returned_batch_cannot_be_certified_as_sellable_or_different_quantity(db,source,field,value):
    root,line,lot,batch=graph(db,source)
    setattr(batch,field,value);db.flush()
    with pytest.raises(ValueError,match='quarantine'):
        with db.begin_nested():db.add(lot);db.flush()


def test_static115_repeat_and_raw_history_guards_preserve_native_stock(db,source):
    root,line,lot,batch=graph(db,source);db.add(lot);db.flush()
    migration=runpy.run_path(str(MIGRATION))
    assert migration['down_revision']=='pg_20261115_114_return_precision'
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['upgrade']();migration['upgrade']()
    for table,key,patch in ((PharmaReturn.__table__,root.id,{'reason':'rewrite'}),
                            (PharmaReturnLot.__table__,lot.id,{'quantity':Decimal('.002')}),
                            (SRMInventoryBatch.__table__,batch.id,{'available_quantity':Decimal('.001')}),
                            (SRMPOSReturn.__table__,root.native_return_id,{'customer_id':999999}),
                            (SRMPOSReturnLine.__table__,line.native_return_line_id,{'warehouse_id':999999})):
        with pytest.raises(DBAPIError):
            with db.begin_nested():db.connection().execute(table.update().where(table.c.id==key).values(**patch))
    native=SRMPOSReturn.__table__
    db.connection().execute(native.update().where(native.c.id==root.native_return_id).values(refund_status='refunded'))
    with pytest.raises(DBAPIError):
        with db.begin_nested():db.connection().execute(native.update().where(native.c.id==root.native_return_id).values(refund_status='pending'))
    original=SRMInventoryBatch.__table__
    # The new quarantine protection does not freeze an unrelated original lot.
    with db.begin_nested():
        db.connection().execute(original.update().where(original.c.id==lot.original_batch_id).values(status='recalled'))
    assert db.connection().scalar(select(original.c.available_quantity).where(original.c.id==batch.id))==0
    with Operations.context(MigrationContext.configure(db.connection())):migration['downgrade']()
    assert all(inspect(db.connection()).has_table(model.__tablename__) for model in MODELS)


def test_incomplete_quarantine_cannot_be_finalized_by_orm_or_raw_pointer_update(db,source):
    from datetime import datetime,timezone
    root,line,lot,batch=graph(db,source);db.add(lot);db.flush()
    with pytest.raises(ValueError,match='complete native quarantine'):
        with db.begin_nested():root.state='committed';db.flush()
    migration=runpy.run_path(str(MIGRATION))
    with Operations.context(MigrationContext.configure(db.connection())):migration['upgrade']()
    table=PharmaReturn.__table__
    with pytest.raises(DBAPIError,match='incomplete native quarantine'):
        with db.begin_nested():
            db.connection().execute(table.update().where(table.c.id==root.id).values(state='committed',
                revision=root.revision+1,credit_voucher_id=900001,refund_voucher_id=900002,
                cash_movement_id=900003,committed_at=datetime.now(timezone.utc)))
    assert db.get(PharmaReturn,root.id).state=='draft'
