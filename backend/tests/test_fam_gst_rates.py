from tests.fam_test_utils import fam_admin_headers


def test_fam_gst_rate_and_hsn_sac_master(client, db):
    headers = fam_admin_headers(client, db)
    rate = client.post("/api/v1/fam/gst/rates", headers=headers, json={
        "rate_name": "GST 18%",
        "tax_type": "goods",
        "cgst_rate": 9,
        "sgst_rate": 9,
        "igst_rate": 18,
        "cess_rate": 0,
        "effective_from": "2026-04-01",
    })
    assert rate.status_code == 201, rate.text
    hsn = client.post("/api/v1/fam/gst/hsn-sac", headers=headers, json={
        "code": "998314",
        "description": "IT consulting services",
        "type": "sac",
        "default_gst_rate_id": rate.json()["id"],
    })
    assert hsn.status_code == 201, hsn.text
    assert client.get("/api/v1/fam/gst/rates", headers=headers).json()["total"] == 1
    assert client.get("/api/v1/fam/gst/hsn-sac", headers=headers).json()["total"] == 1
