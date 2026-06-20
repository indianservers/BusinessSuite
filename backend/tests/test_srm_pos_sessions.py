from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.main import app
from tests.srm_test_utils import auth_headers_for


def test_pos_session_cash_movement_and_cashier_closing(client, db):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        ensure_business_os_seed(db, company_id=1)
        headers = auth_headers_for(
            client,
            db,
            "pos-manager@srm.example.com",
            "srm_sales_manager",
            permissions=["srm_view", "srm_manage"],
        )

        opened = client.post(
            "/api/v1/srm/pos/sessions",
            headers=headers,
            json={"opening_cash": 5000, "branch": "Main Branch", "register_name": "Counter 1"},
        )
        assert opened.status_code == 201, opened.text
        opened_body = opened.json()
        session_id = opened_body["session"]["id"]
        assert opened_body["session"]["status"] == "open"
        assert opened_body["expected_cash"] == 5000.0

        moved = client.post(
            "/api/v1/srm/pos/cash-movements",
            headers=headers,
            json={"session_id": session_id, "movement_type": "cash_in", "amount": 500, "reason": "Float top-up"},
        )
        assert moved.status_code == 201, moved.text
        assert moved.json()["expected_cash"] == 5500.0

        closed = client.post(
            "/api/v1/srm/pos/cashier-closing",
            headers=headers,
            json={"session_id": session_id, "counted_cash": 5500, "notes": "Balanced"},
        )
        assert closed.status_code == 201, closed.text
        closed_body = closed.json()
        assert closed_body["session"]["status"] == "closed"
        assert closed_body["expected_cash"] == 5500.0
        assert closed_body["closing"]["variance"] == 0.0

        listed = client.get("/api/v1/srm/pos/sessions", headers=headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["session"]["id"] == session_id
    finally:
        delattr(app.state, "business_os_session_factory")
        delattr(app.state, "business_os_close_session")
