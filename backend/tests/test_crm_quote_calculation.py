def test_crm_quote_calculation_updates_totals_and_margin(client, superuser_headers):
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-CALC-001",
        "issueDate": "2026-06-01",
        "expiryDate": "2026-06-30",
    })
    quote_id = quote.json()["id"]
    client.post(f"/api/v1/crm/quotes/{quote_id}/lines", headers=superuser_headers, json={
        "name": "License",
        "quantity": 1,
        "unitPrice": 100000,
        "discountType": "amount",
        "discountValue": 10000,
        "taxRate": 18,
        "estimatedCost": 40000,
    })

    response = client.post(f"/api/v1/crm/quotes/{quote_id}/calculate", headers=superuser_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["calculation"]["subtotal"] == 100000
    assert body["calculation"]["discountTotal"] == 10000
    assert body["calculation"]["taxTotal"] == 16200
    assert body["calculation"]["grandTotal"] == 106200
    assert body["calculation"]["expectedMargin"] == 66200
