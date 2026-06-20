from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.main import app
from tests.srm_test_utils import auth_headers_for


def test_pos_held_bill_recall_lifecycle_is_database_backed(client, db):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        ensure_business_os_seed(db, company_id=1)
        headers = auth_headers_for(
            client,
            db,
            "pos-held@srm.example.com",
            "srm_sales_manager",
            permissions=["srm_view", "srm_manage"],
        )

        held = client.post(
            "/api/v1/srm/pos/held-bills",
            headers=headers,
            json={
                "customer_id": 1,
                "customer_name": "Cash Customer",
                "notes": "Counter bill",
                "amount": 128,
                "item_count": 1,
                "cart_json": [{"id": 10, "name": "A4 Notebook", "sku": "NOTE-A4", "qty": 2, "rate": 64}],
            },
        )
        assert held.status_code == 201, held.text
        held_body = held.json()
        assert held_body["holdNo"].startswith("HOLD-")
        assert held_body["status"] == "held"
        assert held_body["cart"][0]["qty"] == 2

        listed = client.get("/api/v1/srm/pos/held-bills", headers=headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1

        recalled = client.post(f"/api/v1/srm/pos/held-bills/{held_body['id']}/recall", headers=headers)
        assert recalled.status_code == 200, recalled.text
        assert recalled.json()["status"] == "recalled"
        assert recalled.json()["cart"][0]["sku"] == "NOTE-A4"

        after_recall = client.get("/api/v1/srm/pos/held-bills", headers=headers)
        assert after_recall.status_code == 200, after_recall.text
        assert after_recall.json()["total"] == 0
    finally:
        delattr(app.state, "business_os_session_factory")
        delattr(app.state, "business_os_close_session")
