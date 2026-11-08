import csv
from io import StringIO
from decimal import Decimal
from tests.fam_test_utils import fam_admin_headers, ledger_by_nature


def test_dated_statements_use_posted_entries_and_reuse_export(client, db):
    headers = fam_admin_headers(client, db)
    client.get('/api/v1/fam/dashboard', headers=headers)
    asset = ledger_by_nature(client, headers, 'asset')
    equity = ledger_by_nature(client, headers, 'equity')
    income = ledger_by_nature(client, headers, 'income')
    expense = ledger_by_nature(client, headers, 'expense')
    years = client.get('/api/v1/fam/financial-years', headers=headers).json()['items']
    year = next(row for row in years if row['start_date'] <= '2026-06-01' <= row['end_date'])
    kinds = client.get('/api/v1/fam/voucher-types', headers=headers).json()['items']
    kind = next(row for row in kinds if row['category'] == 'journal')
    for ledger, dr, cr in [(asset,1000,0),(equity,0,1000)]:
        response = client.post('/api/v1/fam/opening-balances', headers=headers,
            json={'financial_year_id':year['id'], 'ledger_id':ledger['id'], 'debit_amount':dr, 'credit_amount':cr})
        assert response.status_code == 201, response.text
    assert client.post('/api/v1/fam/opening-balances/post', headers=headers).status_code == 200

    def voucher(day, amount, debit, credit, posted=True):
        result = client.post('/api/v1/fam/vouchers', headers=headers, json={
            'voucher_type_id':kind['id'], 'voucher_date':day, 'lines':[
                {'ledger_id':debit['id'], 'debit_amount':amount, 'credit_amount':0},
                {'ledger_id':credit['id'], 'debit_amount':0, 'credit_amount':amount}]})
        assert result.status_code == 201, result.text
        if posted:
            post = client.post(f'/api/v1/fam/vouchers/{result.json()["id"]}/post', headers=headers)
            assert post.status_code == 200, post.text
        return result.json()['id']

    voucher('2026-05-06',100,asset,income)
    voucher('2026-06-06',500,asset,income)
    voucher('2026-06-07',200,expense,asset)
    voucher('2026-07-06',999,asset,income)
    voucher('2026-06-08',10000,asset,income,False)
    cancelled = voucher('2026-06-09',77,asset,income)
    assert client.post(f'/api/v1/fam/vouchers/{cancelled}/cancel', headers=headers,json={'reason':'Acceptance cancellation'}).status_code == 200
    original = voucher('2026-06-15',50,asset,income)
    reversal = client.post(f'/api/v1/fam/vouchers/{original}/reverse',headers=headers)
    assert reversal.status_code == 201, reversal.text
    # A draft reversal cannot erase the effective original entry.
    params = {'from_date':'2026-06-01','to_date':'2026-06-30'}
    def report(name):
        response = client.get('/api/v1/fam/financial-statements/'+name,headers=headers,params=params)
        assert response.status_code == 200, response.text
        return response.json()
    pl = report('profit_and_loss')
    assert pl['summary'] == {'income':'550.00','expense':'200.00','net_profit':'350.00'}
    sheet = report('balance_sheet')
    assert sheet['summary'] == {'asset':'1450.00','liability':'0.00','equity':'1450.00','difference':'0.00'}
    trial = report('trial_balance')
    row = next(row for row in trial['items'] if row['ledger_id']==asset['id'])
    assert row['opening_balance']=='1100.00'
    assert row['closing_balance']=='1450.00'
    assert trial['summary']['difference']=='0.00'
    exported=client.post('/api/v1/fam/exports',headers=headers,json={'export_type':'profit_and_loss','filters_json':params})
    assert exported.status_code==201,exported.text
    content=client.get(f'/api/v1/fam/exports/{exported.json()["id"]}/download',headers=headers)
    assert content.status_code==200,content.text
    rows=list(csv.DictReader(StringIO(content.json()['file_content'])))
    assert next(row for row in rows if row['ledger_name']=='net_profit')['amount']=='350.00'
    assert not any(row.get('nature')=='asset' for row in rows)
    bad=client.get('/api/v1/fam/financial-statements/trial_balance',headers=headers,
        params={'from_date':'2025-01-01','to_date':'2026-06-30'})
    assert bad.status_code==422
    changed=client.put('/api/v1/fam/settings',headers=headers,json={'country_code':'AE','base_currency':'AED'})
    assert changed.status_code==409
