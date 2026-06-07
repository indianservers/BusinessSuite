def test_crm_quote_pdf_endpoint_generates_pdf(client, superuser_headers):
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-PDF-001",
        "issueDate": "2026-06-01",
        "expiryDate": "2026-06-30",
        "terms": "Net 15",
    })
    quote_id = quote.json()["id"]
    response = client.get(f"/api/v1/crm/quotes/{quote_id}/pdf", headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
