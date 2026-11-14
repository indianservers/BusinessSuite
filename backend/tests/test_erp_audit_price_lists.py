import pytest

from app.apps.srm.models import SRMPriceList
from tests.test_erp_audit_procurement import procurement


@pytest.mark.parametrize("change", [{"discount_percent": -1}, {"discount_percent": 101}, {"discount_amount": -1}, {"discount_amount": 101}])
def test_price_lists_reject_discounts_outside_price_bounds(client, db, procurement, change):
    headers, line, _ = procurement
    response = client.post("/api/v1/srm/pricing/price-lists", headers=headers, json={"price_list_name": "Audit pricing", "lines": [{"product_id": line["product_id"], "price": 100, **change}]})
    assert response.status_code in {400, 422}, response.text
    assert db.query(SRMPriceList).count() == 0


@pytest.mark.parametrize("quantity", [0, -1])
def test_price_lookup_requires_positive_quantity(client, db, procurement, quantity):
    headers, line, _ = procurement
    response = client.post("/api/v1/srm/pricing/lookup", headers=headers, json={"product_ids": [line["product_id"]], "quantity": quantity})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field,limit", [("price_list_code", 80), ("channel", 80), ("customer_type", 80), ("currency", 10)])
def test_price_list_text_limits_match_storage(client, db, procurement, field, limit):
    headers, line, _ = procurement
    response = client.post("/api/v1/srm/pricing/price-lists", headers=headers, json={"price_list_name": "Audit pricing", field: "X" * (limit + 1), "lines": [{"product_id": line["product_id"], "price": 100}]})
    assert response.status_code == 422, response.text
    assert db.query(SRMPriceList).count() == 0


@pytest.mark.parametrize("price,percent,discount", [(100, 100, 0), (100, 0, 100), (0, 0, 0)])
def test_zero_net_prices_remain_valid(client, db, procurement, price, percent, discount):
    headers, line, _ = procurement
    created = client.post("/api/v1/srm/pricing/price-lists", headers=headers, json={"price_list_name": "Zero net price", "lines": [{"product_id": line["product_id"], "price": price, "discount_percent": percent, "discount_amount": discount}]})
    assert created.status_code == 201, created.text
    result = client.post("/api/v1/srm/pricing/lookup", headers=headers, json={"product_ids": [line["product_id"]]})
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["net_price"] == 0
    assert result.json()["items"][0]["price_list_id"] == created.json()["id"]


def test_price_list_identity_and_effective_discount_lookup(client, db, procurement):
    headers, line, _ = procurement
    base = "/api/v1/srm/pricing"
    blank = client.post(base + "/price-lists", headers=headers, json={"price_list_name": "   ", "lines": [{"product_id": line["product_id"], "price": 100}]})
    assert blank.status_code == 422
    created = client.post(base + "/price-lists", headers=headers, json={"price_list_name": "  Audit prices  ", "price_list_code": "  QA-PRICE  ", "effective_from": "2026-05-01", "effective_to": "2026-05-31", "lines": [{"product_id": line["product_id"], "price": 100, "discount_amount": 10, "discount_percent": 20}]})
    assert created.status_code == 201, created.text
    assert created.json()["price_list_name"] == "Audit prices"
    assert created.json()["price_list_code"] == "QA-PRICE"
    result = client.post(base + "/lookup", headers=headers, json={"product_ids": [line["product_id"]], "price_date": "2026-05-12", "quantity": 1})
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["net_price"] == 72
    assert result.json()["items"][0]["price_list_id"] == created.json()["id"]
    # Older invalid pricing must not be returned as a usable quote.
    price_list = db.get(SRMPriceList, created.json()["id"])
    price_list.lines[0].discount_amount = 101
    db.commit()
    rejected = client.post(base + "/lookup", headers=headers, json={"product_ids": [line["product_id"]], "price_date": "2026-05-12"})
    assert rejected.status_code == 409, rejected.text
    db.refresh(price_list.lines[0])
    assert price_list.lines[0].discount_amount == 101
