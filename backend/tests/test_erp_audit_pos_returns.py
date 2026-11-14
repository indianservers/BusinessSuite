from datetime import datetime

import pytest

from app.apps.srm.models import SRMInventoryMovement, SRMInventoryBalance, SRMPOSReturn
from tests.test_erp_audit_procurement import procurement
from tests.srm_test_utils import seed_invoice_parties


@pytest.fixture
def pos_sale(client, db, procurement):
    headers, product, _ = procurement
    seed_invoice_parties(db)
    opening = client.post("/api/v1/srm/inventory/opening-stock", headers=headers, json={"product_id": product["product_id"], "warehouse_id": product["warehouse_id"], "quantity": 20, "rate": 5})
    assert opening.status_code == 201
    sale = client.post("/api/v1/srm/sales-orders", headers=headers, json={"title": "Audit POS sale", "customer_id": 101, "metadata_json": {"source": "pos"}, "lines": [{"product_id": product["product_id"], "description": "Paper", "service_type": "product", "quantity": 2, "unit_price": 10}]})
    assert sale.status_code == 201, sale.text
    return headers, product, sale.json()


def test_explicit_unknown_sale_line_cannot_fall_back_to_product(client, db, pos_sale):
    headers, product, sale = pos_sale
    movements = db.query(SRMInventoryMovement).count()
    before = db.query(SRMInventoryBalance).filter_by(product_id=product["product_id"]).one().quantity
    response = client.post("/api/v1/srm/pos/returns", headers=headers, json={"sales_order_id": sale["id"], "lines": [{"sales_order_line_id": 999999, "product_id": product["product_id"], "quantity": 1}]})
    assert response.status_code == 422
    assert db.query(SRMPOSReturn).count() == 0
    assert db.query(SRMInventoryMovement).count() == movements
    assert db.query(SRMInventoryBalance).filter_by(product_id=product["product_id"]).one().quantity == before


def test_unambiguous_product_only_return_still_uses_original_value(client, db, pos_sale):
    headers, product, sale = pos_sale
    response = client.post("/api/v1/srm/pos/returns", headers=headers, json={"sales_order_id": sale["id"], "lines": [{"product_id": product["product_id"], "quantity": 1}]})
    assert response.status_code == 201, response.text
    assert response.json()["refund_amount"] == 10
    assert response.json()["lines"][0]["sales_order_line_id"] == sale["lines"][0]["id"]
    assert db.query(SRMInventoryBalance).filter_by(product_id=product["product_id"]).one().quantity == 19


def test_repeated_product_requires_explicit_line_and_keeps_correct_price(client, db, pos_sale):
    headers, product, _ = pos_sale
    sale = client.post("/api/v1/srm/sales-orders", headers=headers, json={"title": "Two-price POS sale", "customer_id": 101, "metadata_json": {"source": "pos"}, "lines": [{"product_id": product["product_id"], "description": "Paper", "service_type": "product", "quantity": 1, "unit_price": price} for price in [10, 20]]})
    assert sale.status_code == 201, sale.text
    sale = sale.json()
    movements = db.query(SRMInventoryMovement).count()
    payload = {"sales_order_id": sale["id"], "lines": [{"product_id": product["product_id"], "quantity": 1}]}
    response = client.post("/api/v1/srm/pos/returns", headers=headers, json=payload)
    assert response.status_code == 422
    assert db.query(SRMPOSReturn).count() == 0
    assert db.query(SRMInventoryMovement).count() == movements
    payload["lines"][0]["sales_order_line_id"] = sale["lines"][0]["id"]
    response = client.post("/api/v1/srm/pos/returns", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["refund_amount"] == 10
    assert response.json()["lines"][0]["sales_order_line_id"] == sale["lines"][0]["id"]


def test_return_sales_lookup_pages_literal_search_and_returnable_quantity(client, db, pos_sale):
    headers, product, sale = pos_sale
    from app.apps.srm.models import SRMSalesOrder
    from test_identity_utils import own_workflow_records
    seed = db.get(SRMSalesOrder, sale["id"])
    seed.order_number = "OLD_%\\SALE"
    added = [SRMSalesOrder(organization_id=seed.organization_id, created_by=seed.created_by, order_number=f"PAGE-{index}", title=f"Sale {index}", customer_id=seed.customer_id, metadata_json={"source": "pos"}) for index in range(105)]
    regular = SRMSalesOrder(organization_id=seed.organization_id, created_by=seed.created_by, order_number="NOT-POS", title="Regular sale", customer_id=seed.customer_id)
    deleted = SRMSalesOrder(organization_id=seed.organization_id, created_by=seed.created_by, order_number="DELETED-POS", title="Deleted sale", metadata_json={"source": "pos"}, deleted_at=datetime.now())
    db.add_all([*added, regular, deleted])
    own_workflow_records(db, *added, regular, deleted, company_id=seed.organization_id)
    db.commit()
    base = "/api/v1/srm/pos/return-sales"
    first = client.get(base, headers=headers, params={"per_page": 100}).json()
    second = client.get(base, headers=headers, params={"per_page": 100, "page": 2}).json()
    assert first["total"] == 106 and first["has_more"]
    assert len(first["items"]) == 100 and len(second["items"]) == 6 and not second["has_more"]
    assert sale["id"] in {row["id"] for row in second["items"]}
    for term in ["%", "_", "\\", "Audit POS"]:
        response = client.get(base, headers=headers, params={"search": term})
        assert response.status_code == 200
        assert [row["id"] for row in response.json()["items"]] == [sale["id"]]
    refunded = client.post("/api/v1/srm/pos/returns", headers=headers, json={"sales_order_id": sale["id"], "lines": [{"sales_order_line_id": sale["lines"][0]["id"], "quantity": 1}]})
    assert refunded.status_code == 201
    from sqlalchemy import event
    reads = []
    def observe(conn, cursor, statement, params, context, many):
        if "from srm_pos_return_lines" in statement.lower():
            reads.append(statement)
    event.listen(db.bind, "before_cursor_execute", observe)
    try:
        result = client.get(base, headers=headers, params={"search": "OLD_%"}).json()
    finally:
        event.remove(db.bind, "before_cursor_execute", observe)
    assert len(reads) == 1
    line = result["items"][0]["lines"][0]
    assert line["returned_quantity"] == 1 and line["returnable_quantity"] == 1
    assert client.get(base, headers=headers, params={"page": 0}).status_code == 422
    assert client.get(base, headers=headers, params={"per_page": 101}).status_code == 422
