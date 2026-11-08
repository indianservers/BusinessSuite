import pytest
from tests.fam_test_utils import fam_admin_headers,create_bank_account,ledger_by_nature


def fixture(client,db,direction='withdrawal'):
    headers=fam_admin_headers(client,db)
    account=create_bank_account(client,headers)
    ledger=ledger_by_nature(client,headers,'expense' if direction=='withdrawal' else 'income')
    rule={'name':'Bank charges' if direction=='withdrawal' else 'Bank interest','bank_account_id':account['id'],
        'direction':direction,'text':'service fee','counter_ledger_id':ledger['id'],'minimum':'10','maximum':'100'}
    created=client.post('/api/v1/fam/bank-rules',headers=headers,json=rule)
    assert created.status_code==201,created.text
    statement=client.post('/api/v1/fam/bank-statements/import',headers=headers,json={
        'bank_account_id':account['id'],'statement_period_start':'2026-06-01','statement_period_end':'2026-06-30','imported_file_name':'rules.csv',
        'lines':[{'transaction_date':'2026-06-06','description':'Monthly SERVICE FEE','reference_number':'RULE-FEE',
                  'debit_amount':25 if direction=='withdrawal' else 0,'credit_amount':0 if direction=='withdrawal' else 25,'balance':1000}]})
    assert statement.status_code==201,statement.text
    return headers,created.json(),rule,statement.json()


@pytest.mark.parametrize('direction',['withdrawal','deposit'])
def test_reviewed_rule_posts_once_and_reconciles_native_line(client,db,direction):
    from app.apps.fam.models import FAMVoucher,FAMBankReconciliationMatch
    headers,rule,_,statement=fixture(client,db,direction)
    preview=client.get(f'/api/v1/fam/bank-rules/statements/{statement["id"]}/preview',headers=headers)
    assert preview.status_code==200,preview.text
    suggestion=preview.json()['suggestions'][0]
    body={'rule_id':rule['id'],'expected_version':rule['version'],'line_hash':suggestion['line_hash']}
    path=f'/api/v1/fam/bank-rules/lines/{suggestion["line_id"]}/apply'
    posted=client.post(path,headers=headers,json=body)
    assert posted.status_code==200,posted.text
    assert posted.json()['idempotent'] is False
    repeated=client.post(path,headers=headers,json=body)
    assert repeated.status_code==200,repeated.text
    assert repeated.json()['idempotent'] is True
    assert repeated.json()['voucher_id']==posted.json()['voucher_id']
    assert db.query(FAMVoucher).filter_by(source_record_type='bank_rule_line').count()==1
    assert db.query(FAMBankReconciliationMatch).filter_by(statement_line_id=suggestion['line_id'],match_type='confirmed').count()==1
    assert client.get(f'/api/v1/fam/bank-rules/statements/{statement["id"]}/preview',headers=headers).json()['suggestions']==[]


def test_rule_change_and_accounting_lock_require_review(client,db):
    headers,rule,body,statement=fixture(client,db)
    suggestion=client.get(f'/api/v1/fam/bank-rules/statements/{statement["id"]}/preview',headers=headers).json()['suggestions'][0]
    request={'rule_id':rule['id'],'expected_version':rule['version'],'line_hash':suggestion['line_hash']}
    body.update(expected_version=rule['version'],priority=50)
    changed=client.put(f'/api/v1/fam/bank-rules/{rule["id"]}',headers=headers,json=body)
    assert changed.status_code==200,changed.text
    path=f'/api/v1/fam/bank-rules/lines/{suggestion["line_id"]}/apply'
    assert client.post(path,headers=headers,json=request).status_code==409
    lock=client.put('/api/v1/fam/transaction-locks/banking',headers=headers,json={'locked_through':'2026-06-30','reason':'Closed month','expected_version':0})
    assert lock.status_code==200,lock.text
    request['expected_version']=changed.json()['version']
    assert client.post(path,headers=headers,json=request).status_code==409
    state=client.get(f'/api/v1/fam/bank-statements/{statement["id"]}',headers=headers).json()
    assert state['lines'][0]['matched_status']=='unmatched'


def test_bank_operator_options_do_not_require_or_expose_full_chart(client,db):
    from tests.fam_test_utils import auth_headers_for
    headers=auth_headers_for(client,db,'bank-rule-operator@example.com','bank_rule_operator',permissions=['fam_view','fam_banking_manage'])
    options=client.get('/api/v1/fam/bank-rules/options',headers=headers)
    assert options.status_code==200,options.text
    assert options.json()['ledgers']
    assert all(set(row)=={'id','ledger_name','nature','ledger_type','active'} for row in options.json()['ledgers'])
    assert client.get('/api/v1/fam/ledgers',headers=headers).status_code==403
