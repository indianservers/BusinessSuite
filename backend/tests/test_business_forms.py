"""Country-aware form validation and preservation of canonical identities."""
import pytest
from app.core.input_validation import normalize_phone
from app.core.business_validation import business_type, registration, bank_code, postal, website
from app.apps.crm.models import CRMCompany
from app.shared.master_data_models import ContactChannel
from tests.test_contact_directory import directory_identity

ROOT='/api/v1/master-data'

@pytest.mark.parametrize('number,code,e164',[
    ('9876543210','+91','+919876543210'),('501234567','+971','+971501234567'),
    ('15123456789','+49','+4915123456789'),('0236618300','+39','+390236618300'),
    ('+1 (202) 555-0101','+1','+12025550101')])
def test_country_numbers_and_normalized_e164(number,code,e164):
    assert normalize_phone(number,code)[1]==e164

@pytest.mark.parametrize('number,code', [('98765432101','+91'),('50123','+971'),('abc','+1'),('0000000000','+91'),('9876543210','+999')])
def test_invalid_phone_country_pairs(number,code):
    with pytest.raises(ValueError): normalize_phone(number,code)

def test_indian_mobile_prefix_is_distinct_from_office_numbers():
    with pytest.raises(ValueError): normalize_phone('1234567890','+91',mobile=True)

def test_legal_types_urls_tax_and_bank_checks():
    assert business_type('PVT LTD')==business_type('Private Ltd')=='private_limited'
    assert website('Example.com')=='https://example.com'
    assert registration('GSTIN','27AAPFU0939F1ZV')=='27AAPFU0939F1ZV'
    assert registration('TRN','100123456789012','AE')=='100123456789012'
    assert bank_code('IBAN','GB82 WEST 1234 5698 7654 32','GB')=='GB82WEST12345698765432'
    assert bank_code('IFSC','SBIN0001234','IN')=='SBIN0001234'
    for function,args in [(business_type,('arbitrary entity',)),(website,('javascript:alert(1)',)),
        (registration,('GSTIN','27AAPFU0939F1ZA')),(registration,('PAN','ABCDE1234F','AE')),
        (bank_code,('IBAN','GB00WEST12345698765432','GB')),(bank_code,('IFSC','SBIN1001234','IN')),
        (postal,('12345','IN'))]:
        with pytest.raises(ValueError): function(*args)

def test_shared_company_role_add_preserves_customer_and_other_details(client,db,superuser_headers,directory_identity):
    created=client.post(ROOT+'/companies',headers=superuser_headers,json={'name':'Both customer and vendor','email':'both@example.com','roles':['Customer'],'website':'example.com','businessType':'Pvt Ltd'})
    assert created.status_code==201,created.text
    row=created.json()
    saved=client.patch(ROOT+f"/companies/{row['id']}",headers=superuser_headers,json={'name':row['name'],'version':row['version'],'roles':['Vendor'],'vendorClassification':'Service Provider','paymentTerms':'Net 30'})
    assert saved.status_code==200,saved.text
    assert set(saved.json()['roles'])=={'Customer','Vendor'}
    assert saved.json()['email']=='both@example.com'
    assert saved.json()['businessType']=='private_limited'
    assert saved.json()['vendorClassification']=='Service Provider'
    assert db.query(CRMCompany).filter_by(name=row['name']).count()==1
    for source in ['crm','srm','project_management']:
        result=client.get(ROOT+'/companies',headers=superuser_headers,params={'source':source,'role':'Vendor'} )
        assert result.status_code==200,result.text
        assert row['id'] in [item['id'] for item in result.json()['items']]
    stale=client.patch(ROOT+f"/companies/{row['id']}",headers=superuser_headers,json={'name':'Stale overwrite','version':row['version']})
    assert stale.status_code==409

def test_vendor_alias_and_multiple_communication_numbers(client,db,superuser_headers,directory_identity):
    response=client.post(ROOT+'/companies',headers=superuser_headers,json={'name':'Legacy supplier','roles':['Supplier'],'phone':'501234567','phone_country_code':'+971','communicationChannels':[
        {'kind':'phone','value':'501234567','countryCode':'+971','primary':True},
        {'kind':'phone','value':'15123456789','countryCode':'+49','label':'Work','primary':False}]})
    assert response.status_code==201,response.text
    row=response.json()
    result=client.get(ROOT+'/companies',headers=superuser_headers,params={'role':'Vendor'})
    assert row['id'] in [item['id'] for item in result.json()['items']]
    channels=db.query(ContactChannel).filter_by(account_id=row['id'],kind='phone').all()
    assert {item.normalized_value for item in channels}=={'+971501234567','+4915123456789'}
    assert sum(item.is_primary for item in channels)==1

def test_invalid_form_bypass_is_atomic(client,db,superuser_headers,directory_identity):
    for suffix,extra in [('Phone',{'phone':'98765432101','phone_country_code':'+91'}),
        ('Legal',{'businessType':'arbitrary spelling'}),('GST',{'taxRegistrations':[{'type':'GSTIN','number':'27AAPFU0939F1ZA','country':'IN'}]}),
        ('Country',{'country':'ZZ'}),('IBAN',{'financialData':{'bankAccounts':[{'accountNumber':'000123456','country':'GB','currency':'GBP','iban':'GB00WEST12345698765432'}]}})]:
        name='Invalid bypass '+suffix
        result=client.post(ROOT+'/companies',headers=superuser_headers,json={'name':name,**extra})
        assert result.status_code==422,result.text
        assert db.query(CRMCompany).filter_by(name=name).count()==0
