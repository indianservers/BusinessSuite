from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_gl_reconciliation_endpoint_returns_status(client, db):
    headers, _, _, _ = accounting_setup(client, db, "GLREC")

    response = client.get("/api/v1/fam/inventory/reconciliation/gl", headers=headers)

    assert response.status_code == 200, response.text
    assert "difference" in response.json()
    assert response.json()["status"] in {"matched", "variance"}


def test_inventory_gl_reconciliation_uses_company_currency_and_preserves_cents(client,db):
    from tests.fam_inventory_test_utils import inventory_headers,create_stock_item,post_opening_stock
    from app.apps.fam.models import FAMCompanyFinancialSettings
    from decimal import Decimal
    headers=inventory_headers(client,db,'qa-reconciliation-currency@example.com')
    item,warehouse=create_stock_item(client,headers,'QA-CENTS')
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one()
    settings.base_currency='USD';db.commit()
    post_opening_stock(client,headers,item,warehouse,quantity=3.1,rate=5.2,suffix='QA-CENTS')
    response=client.get('/api/v1/fam/inventory/reconciliation/gl',headers=headers)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['currency']=='USD'
    assert Decimal(str(result['stock_valuation']))==Decimal('16.12')
    assert Decimal(str(result['difference']))==Decimal(str(result['stock_valuation']))-Decimal(str(result['ledger_balance']))
