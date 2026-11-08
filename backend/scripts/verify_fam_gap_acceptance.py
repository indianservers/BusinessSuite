"""Synthetic HTTP acceptance on the disposable loopback FAM fixture only."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import json
import time
import httpx

client=httpx.Client(base_url='http://127.0.0.1:1568/api/v1',timeout=30)
def call(method,path,body=None,status=200):
    response=client.request(method,path,json=body)
    assert response.status_code==status,f'{method} {path}: {response.status_code} {response.text[:800]}'
    return response.json()
token=call('POST','/auth/login',{'email':'admin@suiteqa.example.com','password':'SuiteQA@12345','module':'fam'})['access_token']
client.headers.update({'Authorization':'Bearer '+token,'X-Suite-Organization':'1','X-Suite-Branch':'1'})
today=date.today();day=today.isoformat();start=today.replace(day=1).isoformat();suffix=str(time.time_ns())[-10:]
results={}

def ledger(nature):
    return next(r for r in call('GET','/fam/ledgers')['items'] if r['nature']==nature and r['active'])
def vendor(code):
    return call('POST','/fam/parties',{'party_type':'vendor','party_code':code,'legal_name':'Synthetic acceptance vendor','create_ledger':True},201)
def new_source(kind,supplier,expense,number,tax=0,amount=100):
    line={'expense_ledger_id':expense['id'],'description':'Acceptance supplier service','taxable_value':amount,'gst_amount':tax}
    if kind=='bill':
        return call('POST','/fam/purchase-bills',{'vendor_id':supplier['id'],'bill_number':number,'bill_date':day,'lines':[line]},201)
    return call('POST','/fam/expenses',{'claim_number':number,'claim_date':day,'payable_ledger_id':supplier['ledger_id'],'lines':[line]},201)

call('GET','/fam/settings')
supplier=vendor('REC-'+suffix);expense=ledger('expense')
profiles=[]
for kind in ('bill','expense'):
    source=new_source(kind,supplier,expense,'SOURCE-'+kind+'-'+suffix)
    body={'kind':kind,'source_id':source['id'],'name':'Acceptance '+kind+' '+suffix,'start_date':day,'rule':'monthly','occurrences':2,'payment_terms_days':14}
    created=call('POST','/fam/recurring-purchases',body,201)
    call('POST','/fam/recurring-purchases',body,409)
    profiles.append(created)
print('Native purchase profiles saved; waiting for the actual minute worker.',flush=True)
deadline=time.monotonic()+75
while time.monotonic()<deadline:
    current=call('GET','/fam/recurring-purchases')
    if all(next(r for r in current if r['id']==p['id'])['next_index']==1 for p in profiles): break
    time.sleep(2)
else: raise AssertionError('Purchase worker did not generate both drafts')
for p in profiles:
    current=next(r for r in call('GET','/fam/recurring-purchases') if r['id']==p['id'])
    assert len(current['history'])==1 and not current.get('last_error')
    resource='purchase-bills' if p['kind']=='bill' else 'expenses'
    records=call('GET','/fam/'+resource)['items']
    generated=[r for r in records if r['id']==current['history'][0]['record_id']]
    assert len(generated)==1 and generated[0]['status']=='draft'
    paused=call('PUT',f'/fam/recurring-purchases/{p["id"]}/status',{'status':'paused','expected_version':current['version']})
    call('PUT',f'/fam/recurring-purchases/{p["id"]}/status',{'status':'active','expected_version':current['version']},409)
    call('PUT',f'/fam/recurring-purchases/{p["id"]}/status',{'status':'active','expected_version':paused['version']})
results['recurring_bill_and_expense_drafts']=True
results['recurring_duplicate_and_stale_updates_blocked']=True

banks=call('GET','/fam/bank-accounts')['items']
if banks: bank=banks[0]
else:
    bank_ledger=next(r for r in call('GET','/fam/ledgers')['items'] if r['ledger_type']=='bank')
    bank=call('POST','/fam/bank-accounts',{'ledger_id':bank_ledger['id'],'bank_name':'Acceptance bank','account_number_masked':'XXXX0000','account_type':'current'},201)
rule=call('POST','/fam/bank-rules',{'name':'Acceptance fee '+suffix,'bank_account_id':bank['id'],'direction':'withdrawal',
    'text':'Acceptance fee '+suffix,'counter_ledger_id':expense['id']},201)
statement=call('POST','/fam/bank-statements/import',{'bank_account_id':bank['id'],'statement_period_start':start,'statement_period_end':day,
    'imported_file_name':'acceptance-'+suffix+'.csv','lines':[{'transaction_date':day,'description':'Acceptance fee '+suffix,
    'reference_number':'FEE-'+suffix,'debit_amount':25,'credit_amount':0,'balance':0}]},201)
suggestion=call('GET',f'/fam/bank-rules/statements/{statement["id"]}/preview')['suggestions'][0]
body={'rule_id':rule['id'],'expected_version':rule['version'],'line_hash':suggestion['line_hash']}
applied=call('POST',f'/fam/bank-rules/lines/{suggestion["line_id"]}/apply',body)
assert call('POST',f'/fam/bank-rules/lines/{suggestion["line_id"]}/apply',body)['idempotent'] is True
assert call('GET',f'/fam/bank-statements/{statement["id"]}')['lines'][0]['matched_status']=='matched'
pl=call('GET',f'/fam/financial-statements/profit_and_loss?from_date={start}&to_date={day}')
assert Decimal(pl['summary']['expense'])>=25
sheet=call('GET',f'/fam/financial-statements/balance_sheet?from_date={start}&to_date={day}')
assert Decimal(sheet['summary']['difference'])==0
job=call('POST','/fam/exports',{'export_type':'profit_and_loss','filters_json':{'from_date':start,'to_date':day}},201)
exported=call('GET',f'/fam/exports/{job["id"]}/download')
assert 'net_profit' in exported['file_content'] and 'row_type' in exported['file_content']
results['bank_rule_post_and_reconcile_once']=True
results['dated_statements_and_existing_csv_export']=True
call('PUT','/fam/settings',{'country_code':'AE','base_currency':'AED'},409)
results['posted_india_country_currency_preserved']=True

# The second synthetic company is independent of the India books.
client.headers.update({'X-Suite-Organization':'2','X-Suite-Branch':'2'})
settings=call('GET','/fam/settings')
if settings['country_code']!='AE': call('PUT','/fam/settings',{'country_code':'AE','base_currency':'AED','financial_year_start_month':1})
groups=call('GET','/fam/ledger-groups')['items']
tax_accounts=[]
for code,nature,group_code in [('VAT-OUT','liability','LIAB-DUTIES-TAXES'),('VAT-IN','asset','ASSET-CURRENT')]:
    existing=next((r for r in call('GET','/fam/ledgers')['items'] if r['ledger_code']==code),None)
    tax_accounts.append(existing or call('POST','/fam/ledgers',{'ledger_code':code,'ledger_name':'Acceptance '+code,
        'ledger_group_id':next(r['id'] for r in groups if r['group_code']==group_code),'nature':nature,'ledger_type':'tax'},201))
call('PUT','/fam/uae-tax/settings',{'trn':'100000000000003','emirate':'1b','output_vat_ledger_id':tax_accounts[0]['id'],'input_vat_ledger_id':tax_accounts[1]['id']})
buyer=call('POST','/master-data/companies?source=srm',{'name':'UAE acceptance buyer '+suffix,'entityKind':'Company','country':'AE','roles':['Customer'],
    'addresses':[{'type':'Billing','line1':'Synthetic Dubai office','city':'Dubai','country':'AE'}]},201)
invoice=call('POST','/srm/invoices/manual',{'customer_id':buyer['id'],'currency':'AED','issue_date':day,
    'lines':[{'description':'UAE acceptance services','quantity':1,'unit_price':1000,'tax_amount':50}]},201)
call('POST',f'/srm/invoices/{invoice["id"]}/approve')
call('POST',f'/fam/integrations/srm/post-invoice/{invoice["id"]}')
supplier=vendor('UAE-'+suffix);expense=ledger('expense')
for kind,amount,tax in [('bill',1000,50),('expense',200,10)]:
    source=new_source(kind,supplier,expense,'UAE-'+kind+'-'+suffix,tax,amount)
    resource='purchase-bills' if kind=='bill' else 'expenses'
    call('POST',f'/fam/{resource}/{source["id"]}/post')
register=call('GET',f'/fam/uae-tax/register?period_start={start}&period_end={day}')
assert Decimal(register['output_vat'])>=50 and Decimal(register['recoverable_vat'])>=60
existing=next((r for r in call('GET','/fam/uae-tax/vat201/workings') if r['data']['input']['period_start']==start and r['data']['input']['period_end']==day),None)
working={'period_start':start,'period_end':day,'expected_version':existing['version'] if existing else 0,
    'rows':[{'box':'1b','amount':1000,'vat':register['output_vat']},{'box':'9','amount':1200,'vat':register['recoverable_vat']}]}
call('POST','/fam/uae-tax/vat201/workings',working)
register=call('GET',f'/fam/uae-tax/register?period_start={start}&period_end={day}')
assert Decimal(register['comparison']['net_difference'])==0
sheet=call('GET',f'/fam/financial-statements/balance_sheet?from_date={start}&to_date={day}')
assert Decimal(sheet['summary']['difference'])==0
results['separate_uae_sales_purchase_expense_vat_posting']=True
results['uae_register_reconciles_to_saved_working']=True
results['uae_balance_sheet_balanced']=True
path=Path(__file__).resolve().parents[2]/'outputs'/'recurring-acceptance'/'fam-gap-e2e.json'
path.write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2),flush=True)
