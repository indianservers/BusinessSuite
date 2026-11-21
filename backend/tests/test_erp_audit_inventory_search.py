"""IMP-18 literal inventory item lookup searches in Sales and Finance."""
from uuid import uuid4
import pytest
from tests.fam_inventory_test_utils import inventory_headers,create_stock_item
from tests.test_erp_audit_procurement import procurement

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_finance_item_search_is_literal(client,db,needle):
    headers=inventory_headers(client,db)
    template,_=create_stock_item(client,headers,'LITERAL')
    rows=[]
    for name in ['QA'+needle+'Literal','QAplainLiteral']:
        result=client.post('/api/v1/fam/inventory/items',headers=headers,json={'sku':uuid4().hex[:12],'item_name':name,'stock_group_id':template['stock_group_id'],'unit_id':template['unit_id']})
        assert result.status_code==201,result.text
        rows.append(result.json())
    result=client.get('/api/v1/fam/inventory/items',headers=headers,params={'search':needle})
    assert result.status_code==200,result.text
    ids={x['id'] for x in result.json()['items']}
    assert rows[0]['id'] in ids
    assert rows[1]['id'] not in ids
    normal=client.get('/api/v1/fam/inventory/items',headers=headers,params={'search':'qaplain'})
    assert {x['id'] for x in normal.json()['items']}=={rows[1]['id']}

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_sales_item_search_is_literal(client,procurement,needle):
    headers,_,_=procurement
    rows=[]
    for name in ['QA'+needle+'Literal','QAplainLiteral']:
        result=client.post('/api/v1/srm/inventory/items',headers=headers,json={'sku':uuid4().hex[:12],'item_name':name})
        assert result.status_code==201,result.text
        rows.append(result.json())
    result=client.get('/api/v1/srm/inventory/items',headers=headers,params={'search':needle,'page':1,'per_page':1})
    assert result.status_code==200,result.text
    assert result.json()['total']==1
    assert [x['id'] for x in result.json()['items']]==[rows[0]['id']]
    normal=client.get('/api/v1/srm/inventory/items',headers=headers,params={'search':'qaplain'})
    assert {x['id'] for x in normal.json()['items']}=={rows[1]['id']}


def test_native_pos_catalog_uses_only_sellable_default_warehouse_stock(client, procurement):
    headers, line, _ = procurement
    overflow_warehouse = client.post(
        '/api/v1/srm/inventory/warehouses', headers=headers,
        json={'warehouse_code': 'OVERFLOW', 'warehouse_name': 'Overflow'},
    )
    assert overflow_warehouse.status_code == 201
    overflow = client.post(
        '/api/v1/srm/inventory/opening-stock', headers=headers,
        json={'product_id': line['product_id'], 'warehouse_id': overflow_warehouse.json()['id'], 'quantity': 85},
    )
    assert overflow.status_code == 201

    params = {'search': 'AUDIT-PAPER', 'page': 1}
    endpoint = '/api/v1/srm/inventory/items'
    ordinary = client.get(endpoint, headers=headers, params=params)
    assert ordinary.status_code == 200
    assert ordinary.json()['items'][0]['current_quantity'] == 85
    assert 'stock' not in ordinary.json()['items'][0]

    pos = client.get(endpoint, headers=headers, params={**params, 'pos_stock': True})
    assert pos.status_code == 200
    assert float(pos.json()['items'][0]['stock']['available_quantity']) == 0

    default = client.post(
        '/api/v1/srm/inventory/opening-stock', headers=headers,
        json={'product_id': line['product_id'], 'warehouse_id': line['warehouse_id'], 'quantity': 3},
    )
    assert default.status_code == 201
    pos = client.get(endpoint, headers=headers, params={**params, 'pos_stock': True})
    assert pos.status_code == 200
    assert float(pos.json()['items'][0]['stock']['available_quantity']) == 3
