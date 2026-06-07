from app.apps.crm.models import CRMPriceBook, CRMPriceBookItem, CRMProduct


def test_crm_price_book_and_item_api_database(client, db, superuser_headers):
    product = CRMProduct(organization_id=1, name="CRM Starter", sku="CRM-ST", product_code="CRM-ST", unit_price=25000, list_price=25000)
    db.add(product)
    db.commit()

    response = client.post("/api/v1/crm/price-books", headers=superuser_headers, json={
        "name": "India Standard",
        "currency": "INR",
        "region": "India",
        "customerSegment": "SMB",
        "status": "active",
    })
    assert response.status_code == 201, response.text
    price_book_id = response.json()["id"]
    assert db.query(CRMPriceBook).filter(CRMPriceBook.id == price_book_id).count() == 1

    item = client.post("/api/v1/crm/price-book-items", headers=superuser_headers, json={
        "priceBookId": price_book_id,
        "itemType": "product",
        "productId": product.id,
        "currency": "INR",
        "listPrice": 25000,
        "sellingPrice": 22000,
    })
    assert item.status_code == 201, item.text
    assert db.query(CRMPriceBookItem).filter(CRMPriceBookItem.price_book_id == price_book_id).count() == 1
