"""Retail screen projections preserve native documents and authorization."""
from uuid import uuid4
from hashlib import sha256
import json
from app.apps.srm.models import SRMGoodsReceipt, SRMGoodsReceiptLine
from app.business_packs.retail.stock_receipts import ReceiptInput
from tests.test_retail_stock_receipts import receipt
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity
BASE='/api/v1/srm/retail'


def test_receipt_history_pages_and_old_hash_and_native_notes(client,db,retail_setup):
    data=receipt(retail_setup)
    expected=sha256(json.dumps(ReceiptInput.model_validate(data).model_dump(mode='json',exclude={'reference_number','notes'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    first=client.post(BASE+'/stock-receipts',headers=retail_setup[0],json=data)
    assert first.status_code==201,first.text
    assert db.get(SRMGoodsReceipt,first.json()['id']).metadata_json['request_sha256']==expected
    second=client.post(BASE+'/stock-receipts',headers=retail_setup[0],json={**data,'request_key':str(uuid4()),'reference_number':'DELIVERY-123','notes':'Counted unopened stock'})
    assert second.status_code==201,second.text
    source=db.get(SRMGoodsReceipt,second.json()['id'])
    assert (source.reference_number,source.notes)==('DELIVERY-123','Counted unopened stock')
    page=client.get(BASE+'/stock-receipts?limit=1',headers=retail_setup[0])
    assert page.status_code==200,page.text
    assert [row['id'] for row in page.json()['items']]==[first.json()['id']]
    next_page=client.get(BASE+'/stock-receipts',params={'after':page.json()['next_after'],'limit':1},headers=retail_setup[0])
    assert next_page.status_code==200,next_page.text
    assert [row['id'] for row in next_page.json()['items']]==[second.json()['id']]
    assert next_page.json()['next_after'] is None
    assert next_page.json()['items'][0]['reference_number']=='DELIVERY-123'
    assert db.query(SRMGoodsReceipt).count()==db.query(SRMGoodsReceiptLine).count()==2


def test_closed_stock_options_native_receive_ceiling(client,db,retail_setup):
    response=client.get(BASE+'/stock',headers=retail_setup[0])
    assert response.status_code==200,response.text
    assert response.json()['can_receive']
    assert [row['id'] for row in response.json()['warehouses']]==[retail_setup[6]]
    assert next(row for row in response.json()['items'] if row['product_id']==retail_setup[5])['currency']=='INR'
    from app.access.models import AccessPolicy
    policy=db.query(AccessPolicy).filter_by(user_id=retail_setup[1].id,company_id=1).one()
    policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'actions':['view']}}
    db.commit()
    read=client.get(BASE+'/stock',headers=retail_setup[0])
    assert read.status_code==200,read.text
    assert read.json()['can_receive'] is False
    denied=client.post(BASE+'/stock-receipts',headers=retail_setup[0],json=receipt(retail_setup))
    assert denied.status_code==403,denied.text
    assert db.query(SRMGoodsReceipt).count()==0


def test_history_other_pack_denial(client,db,retail_setup):
    created=client.post(BASE+'/stock-receipts',headers=retail_setup[0],json=receipt(retail_setup))
    assert created.status_code==201,created.text
    from tests.test_business_pack_http_integration import grant
    for pack,role in [('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')]:
        context,_=grant(db,retail_setup[1],retail_setup[2],pack,role)
        denied=client.get(BASE+'/stock-receipts',headers={**retail_setup[0],'X-Suite-Pack-Context':str(context.id)})
        assert denied.status_code==403,denied.text
        assert created.json()['number'] not in denied.text



def test_report_initial_day_uses_actual_company_timezone(client,db,retail_setup,monkeypatch):
    from datetime import datetime,timezone
    from app.business_packs.retail import reports
    from app.models.company import Company
    company=db.get(Company,1);company.default_timezone='Pacific/Kiritimati';db.commit()
    class Clock:
        @staticmethod
        def now(zone):
            return datetime(2026,11,15,15,30,tzinfo=timezone.utc).astimezone(zone)
    monkeypatch.setattr(reports,'datetime',Clock)
    response=client.get(BASE+'/reports/daily',headers=retail_setup[0])
    assert response.status_code==200,response.text
    assert response.json()['day']=='2026-11-16'
    assert response.json()['timezone']=='Pacific/Kiritimati'
