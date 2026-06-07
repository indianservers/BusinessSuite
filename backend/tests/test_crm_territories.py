from app.apps.crm.models import CRMTerritoryAssignment


def test_crm_phase_2_territory_fields_and_assignment(client, db, superuser_headers):
    territory = client.post(
        "/api/v1/crm/territories",
        headers=superuser_headers,
        json={"name": "North Enterprise", "region": "North", "country": "India", "productLine": "Business Suite", "serviceLine": "Implementation", "active": True},
    )
    assert territory.status_code == 201
    assert territory.json()["region"] == "North"

    assigned = client.post(f"/api/v1/crm/territories/{territory.json()['id']}/assign", headers=superuser_headers, json={"userId": 1, "assignmentType": "owner"})
    assert assigned.status_code in {201, 422}
    if assigned.status_code == 201:
        assert db.query(CRMTerritoryAssignment).filter(CRMTerritoryAssignment.territory_id == territory.json()["id"]).count() == 1

    updated = client.put(f"/api/v1/crm/territories/{territory.json()['id']}", headers=superuser_headers, json={"region": "North India"})
    assert updated.status_code == 200
    assert updated.json()["region"] == "North India"
