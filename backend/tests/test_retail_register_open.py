"""Retail native register opening, drawer movements and transaction-derived day."""
from datetime import date, timedelta
import pytest
from decimal import Decimal
from app.apps.srm.models import SRMPOSSession, SRMPOSCashierClosing
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity
from tests.test_retail_workflows import cart


def test_open_replay_cash_sale_movements_close_and_daily_report(client, db, retail_setup):
    headers = retail_setup[0]
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=headers,
                         json={'session_id': retail_setup[4], 'counted_cash': '0'})
    assert closed.status_code == 201, closed.text
    opening = {'register_name': 'Retail front till', 'opening_cash': '20'}
    opened = client.post('/api/v1/srm/pos/sessions', headers=headers, json=opening)
    assert opened.status_code == 201, opened.text
    ident = opened.json()['session']['id']
    replay = client.post('/api/v1/srm/pos/sessions', headers=headers, json=opening)
    assert replay.status_code == 201, replay.text
    assert replay.json()['session']['id'] == ident
    assert db.query(SRMPOSSession).count() == 3  # scenario's legacy + closed Retail + new Retail
    data = cart(retail_setup)
    data['pos_session_id'] = ident
    sale = client.post('/api/v1/srm/service-checkout', headers=headers, json=data)
    assert sale.status_code == 201, sale.text
    for kind, amount in [('cash_in', '5'), ('cash_out', '2')]:
        moved = client.post('/api/v1/srm/pos/cash-movements', headers=headers,
            json={'session_id': ident, 'movement_type': kind, 'amount': amount, 'reason': 'Actual drawer movement'})
        assert moved.status_code == 201, moved.text
    day = client.get('/api/v1/srm/retail/reports/daily', headers=headers, params={'day': date.today().isoformat()})
    assert day.status_code == 200, day.text
    register = next(row for row in day.json()['registers'] if row['session_id'] == ident)
    assert Decimal(register['cash_collected']) == 118
    assert Decimal(register['cash_in']) == 5
    assert Decimal(register['cash_out']) == 2
    assert Decimal(register['net_cash_change']) == 121
    assert Decimal(str(register['lifetime_reconciliation']['expected_cash'])) == 141
    finish = client.post('/api/v1/srm/pos/cashier-closing', headers=headers,
                         json={'session_id': ident, 'counted_cash': '141'})
    assert finish.status_code == 201, finish.text
    assert Decimal(str(finish.json()['closing']['variance'])) == 0
    assert db.query(SRMPOSCashierClosing).filter_by(session_id=ident).count() == 1


@pytest.mark.parametrize('first_receipt_yesterday', [False, True])
def test_daily_register_never_sums_unlike_cash_currencies(client, db, retail_setup, first_receipt_yesterday, monkeypatch):
    from app.apps.srm.models import SRMProduct
    from tests.test_retail_workflows import cart
    headers = retail_setup[0]
    # Seed genuine pre-protection receipts; current cash writes reject this mix.
    import app.apps.srm.register_currency as currencies
    with monkeypatch.context() as legacy:
        legacy.setattr(currencies, 'require_cash_currency', lambda *args, **kwargs: None)
        first = client.post('/api/v1/srm/service-checkout', headers=headers, json=cart(retail_setup))
    assert first.status_code == 201, first.text
    if first_receipt_yesterday:
        from app.apps.srm.models import SRMReceipt
        original_receipt = db.get(SRMReceipt, first.json()['receipts'][0]['id'])
        original_receipt.receipt_date = date.today() - timedelta(days=1)
        db.commit()
    product = db.get(SRMProduct, retail_setup[5])
    product.metadata_json = {**(product.metadata_json or {}), 'currency': 'USD'}
    db.commit()
    data = cart(retail_setup)
    data['currency'] = 'USD'
    with monkeypatch.context() as legacy:
        legacy.setattr(currencies, 'require_cash_currency', lambda *args, **kwargs: None)
        second = client.post('/api/v1/srm/service-checkout', headers=headers, json=data)
    assert second.status_code == 201, second.text
    response = client.get('/api/v1/srm/retail/reports/daily', headers=headers, params={'day': date.today().isoformat()})
    assert response.status_code == 200, response.text
    register = next(row for row in response.json()['registers'] if row['session_id'] == retail_setup[4])
    expected = [{'currency': 'USD', 'amount': '118.00'}] if first_receipt_yesterday else [{'currency': 'INR', 'amount': '118.00'}, {'currency': 'USD', 'amount': '118.00'}]
    assert register['cash_collected_by_currency'] == expected
    assert register['cash_collected'] is register['net_cash_change'] is None
    assert register['currency_reconciliation_required']
    assert register['lifetime_reconciliation']['expected_cash'] is None


@pytest.mark.parametrize('offset', [None, 'UTC'])
def test_business_day_converts_native_utc_at_company_midnight(offset):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from app.business_packs.retail.reports import _business_day
    stamp = datetime(2026, 11, 15, 18, 45, tzinfo=timezone.utc if offset else None)
    assert _business_day(stamp, ZoneInfo('Asia/Kolkata')) == date(2026, 11, 16)
    assert _business_day(stamp, ZoneInfo('America/New_York')) == date(2026, 11, 15)


def test_daily_sales_follow_actual_company_timezone(client, db, retail_setup):
    from datetime import timezone
    from zoneinfo import ZoneInfo
    from app.models.company import Company
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    db.get(Company, 1).default_timezone = 'Pacific/Kiritimati'
    db.commit()
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=cart(retail_setup))
    assert response.status_code == 201, response.text
    root = db.get(POSServiceCheckout, response.json()['id'])
    instant = root.committed_at
    instant = instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant
    day = instant.astimezone(ZoneInfo('Pacific/Kiritimati')).date()
    report = client.get('/api/v1/srm/retail/reports/daily', headers=retail_setup[0], params={'day': day.isoformat()})
    assert report.status_code == 200, report.text
    assert report.json()['timezone'] == 'Pacific/Kiritimati'
    assert report.json()['sales'] == [{'currency': 'INR', 'count': 1, 'gross': '118.00', 'tax': '18.00'}]
