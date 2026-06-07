from tests.fam_test_utils import create_bill, create_party, fam_admin_headers


def test_fam_ap_aging_and_outstanding_only_include_vendors(client, db):
    headers = fam_admin_headers(client, db)
    customer = create_party(client, headers, "customer", "CUST-AP", "AP Customer")
    vendor = create_party(client, headers, "vendor", "VEND-AP", "AP Vendor")
    create_bill(client, headers, customer, "INV-AP", "invoice", 700)
    create_bill(client, headers, vendor, "BILL-AP", "bill", 1800)

    aging = client.get("/api/v1/fam/ap/aging", headers=headers)
    assert aging.status_code == 200, aging.text
    assert aging.json()["totalOutstanding"] == 1800.0
    assert len(aging.json()["items"]) == 1

    outstanding = client.get("/api/v1/fam/ap/outstanding", headers=headers)
    assert outstanding.status_code == 200, outstanding.text
    assert outstanding.json()["totalOutstanding"] == 1800.0
    assert outstanding.json()["items"][0]["bill_number"] == "BILL-AP"

