from datetime import date,timedelta
import pytest
from test_core import app_with_db,login
from app.extensions import db
from app.models import Customer,PriceList,PriceListItem


def add_list(name,price,**kwargs):
    row=PriceList(name=name,**kwargs)
    db.session.add(row);db.session.flush()
    db.session.add(PriceListItem(price_list_id=row.id,product_id=1,sales_price=price,min_qty=1))
    return row


@pytest.mark.parametrize('rule',['expired','future','inactive','valid'])
def test_219_customer_list_validity_and_deterministic_default(rule):
    app=app_with_db(); on=date(2026,11,6)
    with app.app_context():
        assigned=add_list('Assigned',750,status=rule!='inactive',
            valid_from=on+timedelta(days=1) if rule=='future' else on-timedelta(days=1),
            valid_to=on-timedelta(days=1) if rule=='expired' else on+timedelta(days=1))
        first=add_list('First valid default',900,status=True,is_default=True,valid_from=on,valid_to=on)
        add_list('Second valid default',850,status=True,is_default=True)
        add_list('Expired default',700,status=True,is_default=True,valid_to=on-timedelta(days=1))
        Customer.query.one().price_list_id=assigned.id
        expected=assigned.id if rule=='valid' else first.id
        db.session.commit()
    with app.test_client() as client:
        login(client)
        for _ in range(2):
            response=client.get('/api/customer/1/price-list?on=2026-11-06')
            assert response.status_code==200
            data=response.json
            assert data['price_list_id']==expected
            assert data['items']['1']==(750 if rule=='valid' else 900)
            assert data['source']==('customer' if rule=='valid' else 'default')
            assert bool(data['fallback_reason'])==(rule!='valid')
        assert client.get('/api/customer/1/price-list?on=bad-date').status_code==400


def test_219_catalog_fallback_and_220_zero_price():
    app=app_with_db()
    with app.app_context():
        expired=add_list('Expired',750,status=True,valid_to=date(2025,1,1))
        Customer.query.one().price_list_id=expired.id; db.session.commit()
    with app.test_client() as client:
        login(client)
        data=client.get('/api/customer/1/price-list?on=2026-11-06').json
        assert data['source']=='catalog' and data['price_list_id'] is None and data['items']=={}
        with app.app_context():
            add_list('Free eligible default',0,status=True,is_default=True);db.session.commit()
        data=client.get('/api/customer/1/price-list?on=2026-11-06').json
        assert data['items']['1']==0 and data['source']=='default'
