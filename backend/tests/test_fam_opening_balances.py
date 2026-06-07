from app.apps.fam.models import FAMFinancialYear, FAMLedger
from tests.fam_test_utils import fam_admin_headers


def test_fam_opening_balances_must_balance_before_posting(client, db):
    headers = fam_admin_headers(client, db)
    assert client.get("/api/v1/fam/module-info", headers=headers).status_code == 200
    fy = db.query(FAMFinancialYear).filter_by(name="FY 2026-27").first()
    cash = db.query(FAMLedger).filter_by(ledger_name="Cash").first()
    capital = db.query(FAMLedger).filter_by(ledger_name="Opening Balance Difference").first()

    response = client.post("/api/v1/fam/opening-balances", headers=headers, json={
        "financial_year_id": fy.id,
        "ledger_id": cash.id,
        "debit_amount": 10000,
        "credit_amount": 0,
        "narration": "Opening cash",
    })
    assert response.status_code == 201, response.text
    assert client.post("/api/v1/fam/opening-balances/post", headers=headers).status_code == 409

    response = client.post("/api/v1/fam/opening-balances", headers=headers, json={
        "financial_year_id": fy.id,
        "ledger_id": capital.id,
        "debit_amount": 0,
        "credit_amount": 10000,
        "narration": "Opening capital",
    })
    assert response.status_code == 201, response.text

    posted = client.post("/api/v1/fam/opening-balances/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["posted"] is True
    db.refresh(cash)
    assert float(cash.current_balance_dr) == 10000


def test_fam_opening_balance_rejects_both_debit_and_credit(client, db):
    headers = fam_admin_headers(client, db)
    assert client.get("/api/v1/fam/module-info", headers=headers).status_code == 200
    fy = db.query(FAMFinancialYear).filter_by(name="FY 2026-27").first()
    cash = db.query(FAMLedger).filter_by(ledger_name="Cash").first()
    response = client.post("/api/v1/fam/opening-balances", headers=headers, json={
        "financial_year_id": fy.id,
        "ledger_id": cash.id,
        "debit_amount": 1,
        "credit_amount": 1,
    })
    assert response.status_code == 422
