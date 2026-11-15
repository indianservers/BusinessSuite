"""Exact canonical GRN parent mapping retains native tenant and pack ceilings."""
from datetime import date
import pytest
from fastapi import HTTPException
from app.apps.srm.models import SRMGoodsReceipt, SRMGoodsReceiptLine
from tests.test_retail_return_http import scenario, catalog, directory_identity
from tests.test_business_pack_http_integration import native_actor
from tests.test_srm_native_transaction_operations import native_writer


def test_non_superuser_legacy_native_grn_is_authorized_by_actual_parent(client, db, scenario):
    _, branch, products, _ = scenario
    headers, actor = native_actor(db, branch)
    assert not actor.is_superuser
    response = client.post('/api/v1/srm/procurement/grn', headers=headers, json={
        'lines': [{'product_id': products[2][0], 'quantity': 1, 'unit_price': 20}]})
    assert response.status_code == 201, response.text
    assert db.query(SRMGoodsReceipt).count() == db.query(SRMGoodsReceiptLine).count() == 1


def test_foreign_native_grn_parent_cannot_authorize_child_write(db, scenario):
    _, branch, _, _ = scenario
    _, actor = native_actor(db, branch)
    foreign = SRMGoodsReceipt(organization_id=2, grn_number='FOREIGN-PARENT', receipt_date=date.today())
    db.add(foreign); db.commit()
    ident = foreign.id
    with native_writer(db, actor, branch):
        db.add(SRMGoodsReceiptLine(goods_receipt_id=ident, quantity=1, accepted_quantity=1, unit_price=20))
        with pytest.raises(HTTPException) as denied:
            db.flush()
        assert denied.value.status_code == 403
        db.rollback()
    assert db.query(SRMGoodsReceiptLine).count() == 0


def test_shadow_model_cannot_claim_native_grn_parent_mapping():
    from app.access.scope import domain_parent_fields
    from sqlalchemy.orm import aliased
    class Shadow:
        __module__ = 'app.apps.srm.models'
        __tablename__ = 'srm_goods_receipt_lines'
        __table__ = SRMGoodsReceiptLine.__table__
    assert domain_parent_fields(SRMGoodsReceiptLine) == ('goods_receipt_id',)
    assert 'goods_receipt_id' not in domain_parent_fields(Shadow)
    assert 'goods_receipt_id' not in domain_parent_fields(aliased(SRMGoodsReceiptLine))
