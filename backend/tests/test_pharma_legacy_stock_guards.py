"""Quantity-only native commands cannot consume canonical Pharma-managed lots."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.apps.srm.api.router import (_post_stock_movement, _require_quantity_only_inventory,
    create_srm_opening_stock, update_srm_product)
from app.apps.srm.schemas import SRMOpeningStockCreate, SRMProductUpdate
from app.apps.srm.models import SRMProduct
from app.business_packs.pharma.models import PackBatchAvailability
from tests.test_pharma_receipts import pharma, command, balance, counts, scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


@pytest.mark.parametrize('incoming', [False, True])
def test_native_quantity_adjustment_cannot_bypass_managed_lots(client, db, pharma, incoming):
    response = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=command(pharma))
    assert response.status_code == 201, response.text
    product = db.get(SRMProduct, pharma[4])
    original_stock, original_counts = balance(db, pharma), counts(db)
    with native_writer(db, pharma[1], pharma[2]):
        with pytest.raises(HTTPException) as denied:
            _post_stock_movement(db, 1, product, pharma[5], 'adjustment',
                Decimal('1') if incoming else Decimal('0'),
                Decimal('0') if incoming else Decimal('1'), Decimal('12'), date.today(),
                'not-a-lot-command', None, pharma[1])
        assert denied.value.status_code == 409
    assert balance(db, pharma) == original_stock and counts(db) == original_counts


def test_deactivating_availability_does_not_remove_managed_stock_protection(client, db, pharma):
    response = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=command(pharma))
    assert response.status_code == 201, response.text
    availability = PackBatchAvailability.__table__
    db.connection().execute(availability.update().where(
        availability.c.pack_context_id == pharma[3]).values(active=False))
    db.commit()
    with pytest.raises(HTTPException) as denied:
        _require_quantity_only_inventory(db, 1, db.get(SRMProduct, pharma[4]))
    assert denied.value.status_code == 409


def test_unmanaged_legacy_product_retains_native_quantity_path(db, scenario):
    product_id = scenario[2][2][0]
    _require_quantity_only_inventory(db, 1, db.get(SRMProduct, product_id))


def test_native_opening_stock_cannot_add_unattributed_managed_quantity(client, db, pharma):
    response = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=command(pharma))
    assert response.status_code == 201, response.text
    original_stock, original_counts = balance(db, pharma), counts(db)
    with native_writer(db, pharma[1], pharma[2]):
        with pytest.raises(HTTPException) as denied:
            create_srm_opening_stock(SRMOpeningStockCreate(product_id=pharma[4],
                warehouse_id=pharma[5], quantity=Decimal('1'), rate=Decimal('12')),
                db=db, current_user=pharma[1])
        assert denied.value.status_code == 409
    assert balance(db, pharma) == original_stock and counts(db) == original_counts


def test_native_product_update_cannot_reclassify_managed_medicine_as_service(client, db, pharma):
    response = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=command(pharma))
    assert response.status_code == 201, response.text
    original_stock, original_counts = balance(db, pharma), counts(db)
    with native_writer(db, pharma[1], pharma[2]):
        with pytest.raises(HTTPException) as denied:
            update_srm_product(pharma[4], SRMProductUpdate(product_type='service', track_inventory=False),
                db=db, current_user=pharma[1])
        assert denied.value.status_code == 409
    db.expire_all()
    product = db.get(SRMProduct, pharma[4])
    assert product.product_type != 'service' and product.track_inventory
    assert balance(db, pharma) == original_stock and counts(db) == original_counts


@pytest.mark.parametrize('managed_output', [False, True])
def test_native_manufacturing_cannot_consume_or_create_managed_lot_quantity(
        client, db, pharma, catalog, scenario, managed_output):
    from app.apps.srm.models import SRMInventoryBalance, SRMProductionOrder
    from app.apps.srm.api.router import create_srm_product, create_bom, create_production_order, _post_production_inventory
    from app.apps.srm.schemas import SRMProductCreate, SRMBillOfMaterialCreate, SRMProductionOrderCreate
    from sqlalchemy import select
    received = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=command(pharma))
    assert received.status_code == 201, received.text
    actor, branch = scenario[:2]
    with native_writer(db, actor, branch):
        finished = create_srm_product(SRMProductCreate(sku='UNMANAGED-OUTPUT-' + uuid4().hex,
            item_name='Native legacy output', default_warehouse_id=pharma[5]), db=db, current_user=actor)
    output_id = pharma[4] if managed_output else finished['id']
    components = [{'component_product_id': catalog[2][2], 'warehouse_id': pharma[5],
                   'quantity': 1, 'unit_cost': 1}]
    if not managed_output:
        # The protected component is deliberately second: no earlier component
        # may be consumed before every managed-product check has passed.
        components.append({'component_product_id': pharma[4], 'warehouse_id': pharma[5],
                           'quantity': 1, 'unit_cost': 1})
    with native_writer(db, actor, branch):
        bom = create_bom(SRMBillOfMaterialCreate(bom_name='Canonical stock protection',
            finished_product_id=output_id, output_quantity=1, components=components), db=db, current_user=actor)
        order = create_production_order(SRMProductionOrderCreate(bom_id=bom['id'],
            warehouse_id=pharma[5], planned_quantity=1), db=db, current_user=actor)
    inventory = SRMInventoryBalance.__table__
    projection = select(inventory.c.id, inventory.c.quantity, inventory.c.average_cost).order_by(inventory.c.id)
    before = list(db.connection().execute(projection))
    original_counts = counts(db)
    with native_writer(db, actor, branch):
        with pytest.raises(HTTPException) as denied:
            _post_production_inventory(db, db.get(SRMProductionOrder, order['id']), Decimal('1'), pharma[5], actor)
        assert denied.value.status_code == 409 and 'lot-aware Pharma' in denied.value.detail
    assert list(db.connection().execute(projection)) == before and counts(db) == original_counts
    db.expire_all()
    actual = db.get(SRMProductionOrder, order['id'])
    assert actual.status == 'planned' and actual.completed_quantity == 0


def test_native_grn_cannot_add_unattributed_managed_lot_quantity(client, db, pharma, scenario):
    from app.apps.srm.models import SRMGoodsReceipt, SRMGoodsReceiptLine
    from app.apps.srm.api.router import create_goods_receipt
    from app.apps.srm.schemas import SRMGoodsReceiptCreate
    received = client.post('/api/v1/srm/pharma/batch-receipts', headers=pharma[0], json=command(pharma))
    assert received.status_code == 201, received.text
    original_stock, original_counts = balance(db, pharma), counts(db)
    original_documents = (db.query(SRMGoodsReceipt).count(), db.query(SRMGoodsReceiptLine).count())
    actor, branch = scenario[:2]
    with native_writer(db, actor, branch):
        with pytest.raises(HTTPException) as denied:
            with db.begin_nested():
                create_goods_receipt(SRMGoodsReceiptCreate(vendor_name='Fictional native supplier',
                    lines=[{'product_id': pharma[4], 'warehouse_id': pharma[5], 'quantity': 1,
                            'accepted_quantity': 1, 'unit_price': 12}]), db=db, current_user=actor)
        assert denied.value.status_code == 409 and 'lot-aware Pharma' in denied.value.detail
    assert balance(db, pharma) == original_stock and counts(db) == original_counts
    assert (db.query(SRMGoodsReceipt).count(), db.query(SRMGoodsReceiptLine).count()) == original_documents
