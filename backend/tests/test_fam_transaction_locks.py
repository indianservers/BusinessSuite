from tests.fam_test_utils import fam_admin_headers, balanced_voucher_payload

def test_sales_lock_blocks_mutations_and_backdate_bypass_but_not_journals(client,db):
    headers=fam_admin_headers(client,db)
    payload=balanced_voucher_payload(client,headers)
    types=client.get('/api/v1/fam/voucher-types',headers=headers).json()
    rows=types.get('items',[]) if isinstance(types,dict) else types
    payload['voucher_type_id']=next(row['id'] for row in rows if row['category']=='sales')
    draft=client.post('/api/v1/fam/vouchers',json=payload,headers=headers)
    assert draft.status_code==201,draft.text
    ident=draft.json()['id']
    lock=client.put('/api/v1/fam/transaction-locks/sales',headers=headers,json={'locked_through':'2026-06-30','reason':'Sales close reviewed','expected_version':0})
    assert lock.status_code==200,lock.text
    assert client.post(f'/api/v1/fam/vouchers/{ident}/post',headers=headers).status_code==409
    assert client.post(f'/api/v1/fam/vouchers/{ident}/cancel',headers=headers,json={'reason':'Cannot change locked transaction'}).status_code==409
    assert client.post(f'/api/v1/fam/vouchers/{ident}/clone',headers=headers,json={'voucher_date':'2026-06-06'}).status_code==409
    payload['voucher_date']='2026-07-01'
    assert client.put(f'/api/v1/fam/vouchers/{ident}',headers=headers,json=payload).status_code==409
    assert client.post('/api/v1/fam/vouchers',headers=headers,json=payload).status_code==201
    journal=balanced_voucher_payload(client,headers)
    assert client.post('/api/v1/fam/vouchers',headers=headers,json=journal).status_code==201

def test_global_lock_version_and_explicit_unlock(client,db):
    headers=fam_admin_headers(client,db)
    payload=balanced_voucher_payload(client,headers)
    url='/api/v1/fam/transaction-locks/all'
    lock=client.put(url,headers=headers,json={'locked_through':'2026-06-30','reason':'Reviewed closing','expected_version':0})
    assert lock.status_code==200,lock.text
    assert client.post('/api/v1/fam/vouchers',headers=headers,json=payload).status_code==409
    stale=client.put(url,headers=headers,json={'locked_through':None,'reason':'Stale unlock','expected_version':0})
    assert stale.status_code==409
    unlocked=client.put(url,headers=headers,json={'locked_through':None,'reason':'Authorized correction','expected_version':lock.json()['version']})
    assert unlocked.status_code==200,unlocked.text
    assert client.post('/api/v1/fam/vouchers',headers=headers,json=payload).status_code==201
