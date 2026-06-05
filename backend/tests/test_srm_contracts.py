from app.apps.srm.models import SRMAuditLog, SRMContract


def test_srm_contract_create_persists(client, db, superuser_headers):
    response = client.post("/api/v1/srm/contracts", headers=superuser_headers, json={
        "title": "Managed services MSA",
        "customer_id": 33,
        "contract_value": 300000,
        "currency": "INR",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["contract_number"].startswith("CTR-")
    assert db.query(SRMContract).filter(SRMContract.id == body["id"]).first() is not None

    view = client.get(f"/api/v1/srm/contracts/{body['id']}", headers=superuser_headers)
    assert view.status_code == 200
    patch = client.patch(f"/api/v1/srm/contracts/{body['id']}", headers=superuser_headers, json={"terms": "Net 30"})
    assert patch.status_code == 200, patch.text
    active = client.post(f"/api/v1/srm/contracts/{body['id']}/activate", headers=superuser_headers)
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "active"
    expired = client.post(f"/api/v1/srm/contracts/{body['id']}/expire", headers=superuser_headers)
    assert expired.status_code == 200, expired.text
    renewed = client.post(f"/api/v1/srm/contracts/{body['id']}/renew", headers=superuser_headers)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["status"] == "renewed"
    assert db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "contract", SRMAuditLog.entity_id == body["id"]).count() >= 4


def test_srm_contract_duplicate_number_is_blocked(client, db, superuser_headers):
    payload = {"contract_number": "CTR-DUP-001", "title": "Duplicate contract", "customer_id": 33}
    first = client.post("/api/v1/srm/contracts", headers=superuser_headers, json=payload)
    assert first.status_code == 201, first.text
    duplicate = client.post("/api/v1/srm/contracts", headers=superuser_headers, json=payload)
    assert duplicate.status_code == 409
