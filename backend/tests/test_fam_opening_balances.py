from app.apps.fam.models import FAMFinancialYear, FAMLedger
from tests.fam_test_utils import fam_admin_headers
import pytest


@pytest.mark.parametrize("field", ["debit_amount", "credit_amount"])
def test_audit_opening_balance_rejects_negative_amount_without_writing(client, db, field):
    from app.apps.fam.models import FAMOpeningBalance
    headers = fam_admin_headers(client, db)
    assert client.get("/api/v1/fam/module-info", headers=headers).status_code == 200
    year = db.query(FAMFinancialYear).filter_by(name="FY 2026-27").first()
    ledger = db.query(FAMLedger).filter_by(ledger_name="Cash").first()
    before = db.query(FAMOpeningBalance).count()
    response = client.post("/api/v1/fam/opening-balances", headers=headers, json={
        "financial_year_id": year.id, "ledger_id": ledger.id, field: -100,
    })
    assert response.status_code == 422, response.text
    assert any(error["loc"][-1] == field for error in response.json()["detail"])
    assert db.query(FAMOpeningBalance).count() == before


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


def test_opening_posting_accumulates_company_totals_and_preserves_branch_views(client, db, superuser_headers):
    response = client.get("/api/v1/fam/module-info", headers=superuser_headers)
    assert response.status_code == 200, response.text
    year = db.query(FAMFinancialYear).filter_by(name="FY 2026-27").one()
    cash = db.query(FAMLedger).filter_by(ledger_name="Cash").one()
    capital = db.query(FAMLedger).filter_by(ledger_name="Opening Balance Difference").one()
    branch = client.post("/api/v1/branches",headers=superuser_headers,
        json={"name":"Second opening branch","code":"OPEN-SECOND","reason":"Verify independent branch opening balances"})
    assert branch.status_code == 201, branch.text
    second = {**superuser_headers,"X-Suite-Branch":str(branch.json()["id"])}
    next_year = client.post("/api/v1/fam/financial-years", headers=second, json={
        "name":"FY 2027-28", "start_date":"2027-04-01", "end_date":"2028-03-31", "is_current":False})
    assert next_year.status_code == 201, next_year.text
    def post_opening(headers, amount, year_id):
        for ledger, debit, credit in [(cash,amount,0),(capital,0,amount)]:
            response = client.post("/api/v1/fam/opening-balances",headers=headers,json={
                "financial_year_id":year_id,"ledger_id":ledger.id,"debit_amount":debit,"credit_amount":credit})
            assert response.status_code == 201, response.text
        response = client.post("/api/v1/fam/opening-balances/post",headers=headers)
        assert response.status_code == 200, response.text
    post_opening(superuser_headers,100,year.id)
    post_opening(second,200,next_year.json()["id"])
    db.refresh(cash)
    assert cash.current_balance_dr == 300 and cash.opening_balance_dr == 300
    for headers, amount in [(superuser_headers,100),(second,200)]:
        response = client.get("/api/v1/fam/ledgers",headers=headers)
        assert response.status_code == 200, response.text
        row = next(row for row in response.json()["items"] if row["id"]==cash.id)
        assert row["current_balance_dr"] == amount and row["opening_balance_dr"] == amount
        repeat = client.post("/api/v1/fam/opening-balances/post",headers=headers)
        assert repeat.status_code == 200 and repeat.json()["count"] == 0
    db.refresh(cash)
    assert cash.current_balance_dr == 300
