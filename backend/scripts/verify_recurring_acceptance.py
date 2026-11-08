"""End-to-end checks ONLY against the disposable serve_recurring_acceptance app."""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import time
import httpx
from pypdf import PdfReader

BASE = 'http://127.0.0.1:1568/api/v1'
output = Path(__file__).resolve().parents[2] / 'outputs' / 'recurring-acceptance'
output.mkdir(parents=True, exist_ok=True)
client = httpx.Client(base_url=BASE, timeout=30)


def call(method, path, body=None, status=200):
    response = client.request(method, path, json=body)
    assert response.status_code == status, f'{method} {path}: {response.status_code} {response.text[:1000]}'
    return response.json()


login = call('POST', '/auth/login', {'email':'admin@suiteqa.example.com', 'password':'SuiteQA@12345', 'module':'srm'})
client.headers.update({'Authorization':'Bearer ' + login['access_token']})
client.headers.update({'X-Suite-Branch':'1', 'X-Suite-Organization':'1'})
today = date.today()
suffix = str(time.time_ns())[-10:]
buyer = call('POST', '/master-data/companies?source=srm', {
    'name':'Acceptance buyer ' + suffix, 'entityKind':'Company', 'roles':['Customer'],
    'country':'IN', 'addresses':[{'type':'Billing', 'line1':'Synthetic billing office',
    'city':'Hyderabad', 'country':'IN'}]}, 201)
engagement = call('POST', '/srm/engagements', {'name':'Acceptance recurring services',
    'customer_id':buyer['id'], 'billing_type':'recurring', 'currency':'INR'}, 201)
plan = call('POST', '/srm/billing-plans', {'engagement_id':engagement['id'],
    'name':'Acceptance monthly plan', 'billing_type':'recurring', 'currency':'INR', 'recurrence_rule':'monthly'}, 201)
call('POST', f'/srm/billing-plans/{plan["id"]}/activate')
schedule = {'start_date':today.replace(day=1).isoformat(), 'amount':'1250', 'occurrences':2,
    'payment_terms_days':14, 'automatic_drafts':True, 'notify_on_creation':True,
    'invoice_template':'detailed', 'subject':'Monthly acceptance support',
    'customer_notes':'Acceptance customer notes', 'terms':'Pay within fourteen days'}
path = f'/srm/billing-plans/{plan["id"]}/recurring-schedule'
assert call('POST', path, schedule)['created'] == 2
assert call('POST', path, schedule)['created'] == 0
print('Schedule and duplicate protection passed; waiting for the real worker tick.', flush=True)
invoice = None
deadline = time.monotonic() + 75
while time.monotonic() < deadline:
    invoices = call('GET', '/srm/invoices')
    invoice = next((row for row in invoices if row.get('engagement_id') == engagement['id']), None)
    if invoice:
        break
    time.sleep(2)
assert invoice is not None, 'The background worker did not create the due invoice'
assert invoice['status'] == 'draft'
assert invoice['due_date'] == (today.replace(day=1) + timedelta(days=14)).isoformat()
assert call('POST', '/srm/recurring-invoices/process-due')['created'] == 0
notifications = call('GET', '/notifications/?app=srm&per_page=100')['items']
assert len([row for row in notifications if row['title'] == 'Recurring invoice draft created'
            and row['related_entity_id'] == invoice['id']]) == 1
report = call('GET', '/srm/reports')['recurring_invoice_details']
assert len([row for row in report if row['plan_id'] == plan['id']]) == 2
assert any(row['invoice_id'] == invoice['id'] for row in report)
ident = invoice['id']
pdf = client.get(f'/srm/invoices/{ident}/pdf')
pdf.raise_for_status()
text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
for expected in ('Synthetic billing office', 'Acceptance customer notes', 'Pay within fourteen days'):
    assert expected in text, f'Missing PDF content: {expected}'
(output / 'latest-recurring-invoice.pdf').write_bytes(pdf.content)
call('POST', f'/srm/invoices/{ident}/approve')
locks = call('GET', '/fam/transaction-locks')
version = next(row['version'] for row in locks if row['module'] == 'sales')
locked = call('PUT', '/fam/transaction-locks/sales', {'locked_through':schedule['start_date'],
    'reason':'Disposable acceptance close', 'expected_version':version})
call('POST', f'/fam/integrations/srm/post-invoice/{ident}', status=409)
call('PUT', '/fam/transaction-locks/sales', {'locked_through':None,
    'reason':'Disposable acceptance reopen', 'expected_version':locked['version']})
posted = call('POST', f'/fam/integrations/srm/post-invoice/{ident}')
repeated = call('POST', f'/fam/integrations/srm/post-invoice/{ident}')
assert repeated['idempotent'] is True
assert repeated['voucher']['id'] == posted['voucher']['id']
working = {'period_start':'2026-01-01', 'period_end':'2026-03-31',
    'rows':[{'box':'1b', 'amount':'1000', 'vat':'50'}, {'box':'9', 'amount':'400', 'vat':'20'}]}
previous = next((row for row in call('GET', '/fam/uae-tax/vat201/workings')
    if row['data']['input']['period_start'] == working['period_start']
    and row['data']['input']['period_end'] == working['period_end']), None)
working['expected_version'] = previous['version'] if previous else 0
saved = call('POST', '/fam/uae-tax/vat201/workings', working)
assert Decimal(saved['result']['net_vat_due']) == 30
call('POST', '/fam/uae-tax/vat201/workings', working, status=409)
working['expected_version'] = saved['version']
assert call('POST', '/fam/uae-tax/vat201/workings', working)['version'] == saved['version'] + 1
assert Decimal(call('POST', '/fam/uae-tax/corporate-tax/preview',
    {'adjusted_taxable_income':'1000000', 'regime':'standard'})['estimated_tax']) == 56250
result = {'background_invoice_id':ident, 'plan_id':plan['id'], 'voucher_id':posted['voucher']['id'],
    'duplicate_occurrences':0, 'duplicate_invoices':0, 'repeat_post_idempotent':True,
    'pdf_shared_address_and_terms':True, 'sales_lock_blocked_posting':True, 'draft_notification_once':True,
    'uae_working_version_conflict':True, 'uae_net_vat':'30.00', 'ordinary_ct_estimate':'56250.00'}
(output / 'latest-e2e.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2), flush=True)
