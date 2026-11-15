from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from app.apps.srm.models import SRMProduct,SRMInventoryBatch
from tests.test_pharma_receipts import pharma,command,BASE
from tests.test_service_checkout import scenario,catalog,directory_identity


def test_real_catalog_medicine_setup_receive_and_fefo_pos_quantity(client,db,pharma):
    headers=pharma[0]
    payload={'kind':'product','name':'Native medicine','code':'MED-'+uuid4().hex,'price':'100','currency':'INR','tax':'18','unit':'unit',
        'pharma_lot_tracking':True,'pharma_warehouse_id':pharma[5]}
    created=client.post('/api/v1/catalog/items?source=srm',headers=headers,json=payload)
    assert created.status_code==201,created.text
    item=created.json();assert item['pharma_lot_tracking'] is True and item['pharma_warehouse_id']==pharma[5]
    assert item['features']['pharma_lot_tracking'] is True
    medicine=db.get(SRMProduct,item['id'])
    assert medicine.batch_tracking and medicine.expiry_tracking and medicine.track_inventory
    options=client.get('/api/v1/srm/pharma/options',headers=headers)
    assert options.status_code==200,options.text
    assert any(row['id']==item['id'] for row in options.json()['products'])
    receipt=client.post(BASE,headers=headers,json={**command(pharma),'product_id':item['id']})
    assert receipt.status_code==201,receipt.text
    catalog=client.get('/api/v1/srm/pos/catalog',headers=headers)
    assert catalog.status_code==200,catalog.text
    pos=next(row for row in catalog.json()['items'] if row['id']==item['id'])
    assert pos['checkout_supported'] and pos['lot_allocation']=='fefo' and Decimal(pos['stock']['available_quantity'])==Decimal('2.5')
    db.connection().execute(SRMInventoryBatch.__table__.update().where(SRMInventoryBatch.id==receipt.json()['batch_id']).values(status='quarantined'));db.commit()
    catalog=client.get('/api/v1/srm/pos/catalog',headers=headers)
    pos=next(row for row in catalog.json()['items'] if row['id']==item['id'])
    assert Decimal(pos['stock']['available_quantity'])==0
    listed=client.get('/api/v1/srm/pharma/batches',headers=headers)
    assert listed.status_code==200,listed.text
    lot=next(row for row in listed.json()['items'] if row['id']==receipt.json()['batch_id'])
    assert lot['fefo_eligible'] is False and 'unit_cost' not in lot
    changed={key:value for key,value in item.items() if key not in ('id','features','can_edit')}
    changed['pharma_lot_tracking']=False
    denied=client.put(f"/api/v1/catalog/items/product/{item['id']}?source=srm",headers=headers,json=changed)
    assert denied.status_code==409,denied.text


def test_catalog_medicine_requires_real_available_warehouse(client,db,pharma):
    payload={'kind':'product','name':'Medicine missing warehouse','code':'MED-'+uuid4().hex,'pharma_lot_tracking':True}
    before=db.query(SRMProduct).count()
    response=client.post('/api/v1/catalog/items?source=srm',headers=pharma[0],json=payload)
    assert response.status_code==422,response.text
    assert db.query(SRMProduct).count()==before
    response=client.post('/api/v1/catalog/items?source=srm',headers=pharma[0],json={**payload,'pharma_warehouse_id':2147483647})
    assert response.status_code==404,response.text
    assert db.query(SRMProduct).count()==before
