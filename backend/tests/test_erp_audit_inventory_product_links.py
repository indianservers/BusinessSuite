"""Explicit stock/product mappings must be valid and unambiguous."""
from tests.fam_inventory_test_utils import inventory_headers,create_stock_item
from app.apps.srm.models import SRMProduct
from app.apps.fam.models import FAMInventoryIntegrationLink,FAMAuditLog
from test_identity_utils import own_workflow_records

def test_inventory_product_link_validates_before_write_and_rejects_duplicate_owner(client,db):
    headers=inventory_headers(client,db,'qa-product-link@example.com')
    first,_=create_stock_item(client,headers,'QA-LINK-1');second,_=create_stock_item(client,headers,'QA-LINK-2')
    products=[SRMProduct(organization_id=company,sku=name,item_name=name,product_type=kind,active=active) for name,company,kind,active in [('QA% product',1,'product',True),('Foreign',2,'product',True),('Inactive',1,'product',False),('Service',1,'service',True)]]
    db.add_all(products);own_workflow_records(db,products[0],products[2],products[3]);db.commit()
    path=f"/api/v1/fam/inventory/items/{first['id']}/link"
    def body(identity,item=first):return {'stock_item_id':item['id'],'target_module':'srm','target_record_type':'product','target_record_id':str(identity)}
    before=db.query(FAMAuditLog).count()
    for identity in [products[1].id,products[2].id,products[3].id,2147483647,'bad','-1','0']:
        result=client.post(path,headers=headers,json=body(identity))
        assert result.status_code==422,result.text
        assert db.query(FAMInventoryIntegrationLink).count()==0
        assert db.query(FAMAuditLog).count()==before
    result=client.post(path,headers=headers,json=body(products[0].id))
    assert result.status_code==200,result.text
    saved=result.json()
    duplicate=client.post(f"/api/v1/fam/inventory/items/{second['id']}/link",headers=headers,json=body(products[0].id,second))
    assert duplicate.status_code==409,duplicate.text
    assert db.query(FAMInventoryIntegrationLink).count()==1
    repeated=client.post(path,headers=headers,json=body(products[0].id))
    assert repeated.status_code==200,repeated.text
    assert repeated.json()['id']==saved['id']

    options=client.get('/api/v1/fam/inventory/sales-products',headers=headers,params={'search':'%'})
    assert options.status_code==200,options.text
    assert options.json()['items']==[{'id':products[0].id,'label':'QA% product (QA% product)'}]
    assert options.json()['total']==1
    mapped=client.get(f"/api/v1/fam/inventory/items/{first['id']}/sales-products",headers=headers)
    assert mapped.status_code==200,mapped.text
    assert mapped.json()['items'][0]['product_id']==products[0].id
    assert mapped.json()['items'][0]['available'] is True
    unlink=f"/api/v1/fam/inventory/items/{first['id']}/sales-products/{saved['id']}"
    assert client.delete(f"/api/v1/fam/inventory/items/{second['id']}/sales-products/{saved['id']}",headers=headers).status_code==404
    assert client.delete(unlink,headers=headers).status_code==200
    audits=db.query(FAMAuditLog).count()
    assert client.delete(unlink,headers=headers).status_code==200
    assert db.query(FAMAuditLog).count()==audits
    assert client.get(f"/api/v1/fam/inventory/items/{first['id']}/sales-products",headers=headers).json()['items']==[]
    moved=client.post(f"/api/v1/fam/inventory/items/{second['id']}/link",headers=headers,json=body(products[0].id,second))
    assert moved.status_code==200,moved.text
    products[0].active=False;db.commit()
    mapped=client.get(f"/api/v1/fam/inventory/items/{second['id']}/sales-products",headers=headers)
    assert mapped.json()['items'][0]['available'] is False
    assert client.delete(f"/api/v1/fam/inventory/items/{second['id']}/sales-products/{moved.json()['id']}",headers=headers).status_code==200
    assert client.get('/api/v1/fam/inventory/sales-products').status_code in (401,403)


def test_inventory_product_options_paginate_and_search_literal(client,db):
    headers=inventory_headers(client,db,'qa-product-options@example.com')
    products=[SRMProduct(organization_id=1,sku=f'QA-{i}',item_name=f'QA {i:02}',product_type='product',active=True) for i in range(30)]
    db.add_all(products);own_workflow_records(db,*products);db.commit()
    path='/api/v1/fam/inventory/sales-products'
    first=client.get(path,headers=headers).json();second=client.get(path,headers=headers,params={'page':2}).json()
    assert first['total']==30 and len(first['items'])==25 and first['has_more']
    assert second['total']==30 and len(second['items'])==5 and not second['has_more']
    assert {r['id'] for r in first['items']}.isdisjoint(r['id'] for r in second['items'])
    for needle in ['%', '_',chr(92),chr(92)+'%',chr(92)+'_','/']:
        products[0].item_name='QA'+needle+'Literal';db.commit()
        result=client.get(path,headers=headers,params={'search':needle})
        assert result.status_code==200,result.text
        assert result.json()['total']==1
        assert [r['id'] for r in result.json()['items']]==[products[0].id]
