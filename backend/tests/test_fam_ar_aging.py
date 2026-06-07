from tests.fam_test_utils import create_bill, create_party, fam_admin_headers


def test_fam_ar_aging_and_outstanding_only_include_customers(client, db):
    headers = fam_admin_headers(client, db)
    customer = create_party(client, headers, "customer", "CUST-AGING", "Aging Customer")
    vendor = create_party(client, headers, "vendor", "VEND-AGING", "Aging Vendor")
    create_bill(client, headers, customer, "INV-AGING", "invoice", 1200)
    create_bill(client, headers, vendor, "BILL-AGING", "bill", 900)

    aging = client.get("/api/v1/fam/ar/aging", headers=headers)
    assert aging.status_code == 200, aging.text
    assert aging.json()["totalOutstanding"] == 1200.0
    assert len(aging.json()["items"]) == 1

    outstanding = client.get("/api/v1/fam/ar/outstanding", headers=headers)
    assert outstanding.status_code == 200, outstanding.text
    assert outstanding.json()["totalOutstanding"] == 1200.0
    assert outstanding.json()["items"][0]["bill_number"] == "INV-AGING"

