from app.apps.fam.models import FAMInventoryAILog
from tests.fam_inventory_test_utils import inventory_headers


def test_fam_inventory_ai_is_audited_and_not_faked_without_provider(client, db):
    headers = inventory_headers(client, db)
    response = client.post("/api/v1/fam/inventory/ai", headers=headers, json={"prompt": "Find reorder risk"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] in {"not_configured", "gateway_not_connected"}
    assert db.query(FAMInventoryAILog).count() == 1
