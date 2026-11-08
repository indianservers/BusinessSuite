from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.apps.fam.uae_tax import VATCalculation, VATWorking, VATBox, CorporateTax, calculate_vat, vat201, corporate_tax
from tests.test_contact_directory import directory_identity  # noqa: F401

def test_vat_inclusive_exclusive_and_zero_rated():
    assert calculate_vat(VATCalculation(amount='105',inclusive=True)) == {'net':'100.00','vat':'5.00','gross':'105.00','currency':'AED'}
    assert calculate_vat(VATCalculation(amount='100'))['gross'] == '105.00'
    assert calculate_vat(VATCalculation(amount='100',treatment='zero_rated'))['vat'] == '0.00'

def test_vat201_refunds_reverse_charge_and_recoverability():
    result=vat201(VATWorking(period_start=date(2026,1,1),period_end=date(2026,3,31),rows=[VATBox(box='1b',amount=1000,vat=50),VATBox(box='2',amount=-100,vat=-5),VATBox(box='9',amount=400,vat=20),VATBox(box='3',amount=200,vat=10),VATBox(box='10',amount=200,vat=10)]))
    assert result['output_vat']=='55.00'
    assert result['recoverable_vat']=='30.00'
    assert result['net_vat_due']=='25.00'
    assert result['standard_due_date']=='2026-04-28'
    assert result['filing_status']=='not_submitted'
    with pytest.raises(ValidationError): VATBox(box='2',vat=10)
    with pytest.raises(ValidationError): VATBox(box='4',vat=1)

@pytest.mark.parametrize('income,tax',[('375000','0.00'),('1000000','56250.00'),('-1000','0.00')])
def test_ordinary_ct_threshold_and_losses(income,tax):
    assert corporate_tax(CorporateTax(adjusted_taxable_income=income,regime='standard'))['estimated_tax']==tax

def test_special_ct_regime_is_not_silently_treated_as_ordinary():
    with pytest.raises(HTTPException): corporate_tax(CorporateTax(adjusted_taxable_income=1000000,regime='qualifying_free_zone'))

def test_vat_working_is_versioned_without_duplicate_period_or_india_changes(client,db,superuser_headers):
    from app.apps.fam.models import FAMCompanyFinancialSettings
    assert client.get('/api/v1/fam/settings',headers=superuser_headers).status_code==200
    before=db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one().country_code
    body={'period_start':'2026-01-01','period_end':'2026-03-31','rows':[{'box':'1b','amount':'1000','vat':'50'}]}
    first=client.post('/api/v1/fam/uae-tax/vat201/workings',json=body,headers=superuser_headers)
    assert first.status_code==200,first.text
    body['rows'][0]['vat']='40'
    stale=client.post('/api/v1/fam/uae-tax/vat201/workings',json=body,headers=superuser_headers)
    assert stale.status_code==409
    body['expected_version']=first.json()['version']
    second=client.post('/api/v1/fam/uae-tax/vat201/workings',json=body,headers=superuser_headers)
    assert second.status_code==200,second.text
    assert second.json()['id']==first.json()['id']
    assert second.json()['version']==2
    assert second.json()['result']['net_vat_due']=='40.00'
    assert len(client.get('/api/v1/fam/uae-tax/vat201/workings',headers=superuser_headers).json())==1
    db.expire_all()
    assert db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one().country_code==before

def test_uae_invoice_posts_to_vat_mapping_instead_of_india_tax_ledgers(client,db,superuser_headers):
    from app.apps.fam.models import FAMCompanyFinancialSettings,FAMLedger,FAMLedgerGroup,FAMLedgerEntry
    from tests.srm_test_utils import seed_invoice_parties
    client.get('/api/v1/fam/settings',headers=superuser_headers)
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=1).one()
    settings.country_code='AE';settings.base_currency='AED'
    group=db.query(FAMLedgerGroup).filter_by(company_id=1,group_code='LIAB-DUTIES-TAXES').one()
    asset=db.query(FAMLedgerGroup).filter_by(company_id=1,group_code='ASSET-CURRENT').one()
    output=FAMLedger(company_id=1,ledger_code='UAE-OUTPUT-VAT',ledger_name='UAE output VAT',ledger_group_id=group.id,nature='liability',ledger_type='tax',active=True)
    inputs=FAMLedger(company_id=1,ledger_code='UAE-INPUT-VAT',ledger_name='UAE input VAT',ledger_group_id=asset.id,nature='asset',ledger_type='tax',active=True)
    db.add_all([output,inputs]);db.commit()
    configured=client.put('/api/v1/fam/uae-tax/settings',headers=superuser_headers,json={'trn':'100000000000003','emirate':'1b','output_vat_ledger_id':output.id,'input_vat_ledger_id':inputs.id})
    assert configured.status_code==200,configured.text
    seed_invoice_parties(db,(501,))
    created=client.post('/api/v1/srm/invoices/manual',headers=superuser_headers,json={'customer_id':501,'currency':'AED','issue_date':'2026-06-06','lines':[{'description':'UAE services','quantity':1,'unit_price':1000,'tax_amount':50}]})
    assert created.status_code==201,created.text
    invoice=created.json()
    approved=client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve',headers=superuser_headers)
    assert approved.status_code==200,approved.text
    posted=client.post(f'/api/v1/fam/integrations/srm/post-invoice/{invoice["id"]}',headers=superuser_headers)
    assert posted.status_code==200,posted.text
    entries=db.query(FAMLedgerEntry).filter_by(voucher_id=posted.json()['voucher']['id']).all()
    assert sum(Decimal(row.credit_amount or 0) for row in entries if row.ledger_id==output.id)==50
    india_ids={row.id for row in db.query(FAMLedger).filter(FAMLedger.ledger_code.in_(['OUTPUT-CGST','OUTPUT-SGST'])).all()}
    assert not any(row.ledger_id in india_ids for row in entries)
    # Purchases and expenses reuse their native vouchers and the same UAE mapping.
    from tests.fam_test_utils import create_party, ledger_by_nature
    vendor = create_party(client, superuser_headers, 'vendor', 'UAE-VENDOR', 'Synthetic UAE vendor')
    expense = ledger_by_nature(client, superuser_headers, 'expense')
    liability = {'id': vendor['ledger_id']}
    line = {'expense_ledger_id':expense['id'], 'description':'Recoverable business input',
            'taxable_value':1000, 'gst_amount':50}
    for resource, body in [
        ('purchase-bills', {'vendor_id':vendor['id'], 'bill_number':'UAE-BILL', 'bill_date':'2026-06-06', 'lines':[line]}),
        ('expenses', {'claim_number':'UAE-EXPENSE', 'claim_date':'2026-06-06', 'payable_ledger_id':liability['id'], 'lines':[line]}),
    ]:
        created = client.post(f'/api/v1/fam/{resource}', headers=superuser_headers, json=body)
        assert created.status_code == 201, created.text
        posted = client.post(f'/api/v1/fam/{resource}/{created.json()["id"]}/post', headers=superuser_headers)
        assert posted.status_code == 200, posted.text
        entries = db.query(FAMLedgerEntry).filter_by(voucher_id=posted.json()['voucher']['id']).all()
        assert sum(Decimal(row.debit_amount or 0) for row in entries if row.ledger_id==inputs.id)==50
        assert not any(row.ledger_id in india_ids for row in entries)
    from app.apps.fam.api.router import purchase_input_tax
    with pytest.raises(HTTPException):
        purchase_input_tax(db, 1, Decimal('50'), Decimal('10'))
    working={'period_start':'2026-06-01','period_end':'2026-06-30',
        'rows':[{'box':'1b','amount':1000,'vat':50},{'box':'9','amount':2000,'vat':100}]}
    saved=client.post('/api/v1/fam/uae-tax/vat201/workings',headers=superuser_headers,json=working)
    assert saved.status_code==200,saved.text
    register=client.get('/api/v1/fam/uae-tax/register',headers=superuser_headers,
        params={'period_start':'2026-06-01','period_end':'2026-06-30'})
    assert register.status_code==200,register.text
    result=register.json()
    assert len(result['items'])==3
    assert result['output_vat']=='50.00'
    assert result['recoverable_vat']=='100.00'
    assert result['net_vat']=='-50.00'
    assert result['comparison']['net_difference']=='0.00'
