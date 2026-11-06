"""Record-native personalization: actual fields, billing snapshots and access scope."""
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from tests.test_crm_associations_merge import superuser_headers, post, contact
from tests.rich_text_test_utils import organization_context
from app.models.company import Company
from app.models.user import User
from app.apps.crm.models import CRMCompany, CRMContact, CRMLead, CRMDeal
from app.apps.srm.models import SRMInvoice, SRMInvoiceLine
from app.apps.srm.commercial_models import InvoiceContext

ROOT = '/api/v1/record-templates'


def design(module, category='email', text='Hello {{name}} at {{company}}. {{email}}. From {{organization.name}}.'):
    return {'name': 'Record design', 'category':category,'document_type':'invoice' if category=='inventory' else 'email',
            'module':module,'subject':'An update for {{name}}','status':'ready','design':{'blocks':[{'id':'body','type':'text','text':text}]}}


@pytest.fixture
def records(client, db, superuser_headers):
    h = superuser_headers
    seller = db.get(Company, 1); seller.name = 'Actual Seller'; seller.legal_name = 'Actual Seller Limited'; seller.email = 'seller@example.com'; seller.gstin = 'ACTUAL-TAX'; seller.address = 'Seller address'
    db.commit()
    company = post(client,h,'crm/companies',{'name':'Actual Account','email':'account@example.com','address':'Actual account street','city':'Hyderabad'})
    person = contact(client,h,full_name='Actual Contact',first_name='Actual',email='contact@example.com',company_id=company['id'],company_name='Outdated company text')
    lead = post(client,h,'crm/leads',{'first_name':'Actual','full_name':'Actual Lead','company_name':'Lead Company','email':'lead@example.com'})
    pipeline = post(client,h,'crm/pipelines',{'name':'Record templates pipeline'})
    stage = post(client,h,f'crm/pipelines/{pipeline["id"]}/stages',{'name':'Discovery','probability':20})
    deal = post(client,h,'crm/deals',{'name':'Actual Opportunity','company_id':company['id'],'contact_id':person['id'],'pipeline_id':pipeline['id'],'stage_id':stage['id'],'amount':1234.5,'currency':'INR'})
    invoice = SRMInvoice(organization_id=1,invoice_number='ACTUAL-INV-42',customer_id=company['id'],status='draft',created_by=db.query(User).filter_by(email='testadmin@test.com').one().id,issue_date=date(2026,11,7),due_date=date(2026,11,21),currency='INR',subtotal=200,discount_amount=10,tax_amount=34.2,total_amount=224.2,paid_amount=24.2,balance_amount=200)
    db.add(invoice);db.flush()
    db.add(SRMInvoiceLine(invoice_id=invoice.id,description='Actual consulting',quantity=2,unit_price=100,discount_amount=10,tax_amount=34.2,line_total=224.2))
    db.add(InvoiceContext(invoice_id=invoice.id,seller_id=1,contact_id=person['id'],request_id='template-record-invoice',origin='srm'))
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,invoice)
    from app.branches.models import BranchOwnership
    from app.branches.catalog import resource_key
    key=resource_key(invoice.__table__,{'id':invoice.id})
    db.query(BranchOwnership).filter_by(resource_table=invoice.__tablename__,resource_key=key).update({'branch_id':int(h['X-Suite-Branch'])})
    db.commit()
    return h, {'lead':lead['id'],'contact':person['id'],'account':company['id'],'deal':deal['id'],'invoice':invoice.id}


@pytest.mark.parametrize(('entity','expected_name','expected_company','expected_email'),[
    ('lead','Actual Lead','Lead Company','lead@example.com'),('contact','Actual Contact','Actual Account','contact@example.com'),
    ('account','Actual Account','Actual Account','account@example.com'),('deal','Actual Contact','Actual Account','contact@example.com')])
def test_auto_fills_actual_crm_record(client, records, entity, expected_name, expected_company, expected_email):
    h, ids = records
    t = design(entity)
    if entity=='deal': t['design']['blocks'][0]['text'] += ' {{deal.name}} {{deal.amount}} {{deal.status}}'
    response = client.post(f'{ROOT}/{entity}/{ids[entity]}/render',headers=h,json={'template':t})
    assert response.status_code==200, response.text
    result=response.json()
    assert not result['unresolved']
    assert expected_name in result['html'] and expected_company in result['html'] and expected_email in result['html']
    assert 'Actual Seller Limited' in result['html'] and 'Ananya Rao' not in result['html']
    if entity=='deal': assert 'Actual Opportunity' in result['html'] and '1,234.50' in result['html'] and 'Open' in result['html']


def test_saved_ready_templates_are_filtered_to_record_module(client, records):
    h, ids = records
    for module,status in [('lead','ready'),('contact','ready'),('lead','draft')]:
        t=design(module);t['status']=status
        saved=client.post('/api/v1/crm/template-studio/templates',headers=h,json=t)
        assert saved.status_code==201,saved.text
    choices=client.get(f'{ROOT}/lead/{ids["lead"]}',headers=h)
    assert choices.status_code==200,choices.text
    assert len(choices.json()['items'])==1
    chosen=choices.json()['items'][0]
    assert client.post(f'{ROOT}/lead/{ids["lead"]}/render',headers=h,json={'template_id':chosen['id']}).status_code==200
    assert client.post(f'{ROOT}/contact/{ids["contact"]}/render',headers=h,json={'template_id':chosen['id']}).status_code==422


def test_invoice_uses_real_lines_amounts_and_preserves_issued_identity(client, db, records):
    h,ids=records
    t=design('contact','inventory','{{name}} {{company}} {{address}} {{organization.name}} {{organization.tax_id}} {{document.number}} {{document.date}} {{document.due_date}} {{document.currency}}')
    t['design']['blocks'] += [{'id':'items','type':'items'},{'id':'totals','type':'totals'}]
    endpoint=f'{ROOT}/invoice/{ids["invoice"]}/render'
    result=client.post(endpoint,headers=h,json={'template':t,'values':{'document.total':'0.01'}})
    assert result.status_code==200,result.text
    draft=result.json()
    assert not draft['unresolved'] and not draft['snapshot']
    assert '224.20' in draft['html'] and '0.01' not in draft['html']
    assert 'Actual consulting' in draft['html'] and 'ACTUAL-INV-42' in draft['html'] and '21 November 2026' in draft['html']
    ctx=db.get(InvoiceContext,ids['invoice']);ctx.issued_at=datetime.now(timezone.utc)
    ctx.customer_snapshot={'name':'Issued Account','address':'Issued address','email':'issued@example.com'}
    ctx.contact_snapshot={'name':'Issued Contact','email':'issued-contact@example.com'}
    ctx.seller_snapshot={'name':'Issued Seller','address':'Issued seller address','gstin':'ISSUED-TAX'}
    invoice=db.get(SRMInvoice,ids['invoice']);invoice.status='approved'
    db.get(CRMCompany,ids['account']).name='Changed Account'
    db.get(CRMContact,ids['contact']).full_name='Changed Contact'
    db.commit()
    issued=client.post(endpoint,headers=h,json={'template':t}).json()
    assert issued['snapshot'] and 'Issued Contact' in issued['html'] and 'Issued Seller' in issued['html']
    assert 'Changed Account' not in issued['html'] and 'Changed Contact' not in issued['html']


def test_missing_values_and_tenant_boundaries(client,db,records):
    h,ids=records
    t=design('lead',text='{{name}} {{contract.start_date}}')
    endpoint=f'{ROOT}/lead/{ids["lead"]}/render'
    response=client.post(endpoint,headers=h,json={'template':t}).json()
    assert response['unresolved']==['contract.start_date']
    result=client.post(endpoint,headers=h,json={'template':t,'values':{'name':'FAKE PERSON','contract.start_date':'1 December 2026'}}).json()
    assert not result['unresolved'] and 'Actual Lead' in result['html'] and 'FAKE PERSON' not in result['html']
    other=Company(name='Foreign organization',is_active=True);db.add(other);db.flush()
    lead=db.get(CRMLead,ids['lead']);lead.organization_id=other.id;db.commit()
    assert client.post(endpoint,headers=h,json={'template':t}).status_code==404
    assert client.get(f'{ROOT}/lead/{ids["lead"]}',headers=h).status_code==404


def test_foreign_template_missing_record_and_unauthenticated_access(client, db, records):
    h, ids = records
    assert client.get(f'{ROOT}/lead/{ids["lead"]}').status_code in (401,403)
    assert client.get(f'{ROOT}/lead/999999',headers=h).status_code==404
    saved=client.post('/api/v1/crm/template-studio/templates',headers=h,json=design('lead')).json()
    from app.apps.crm.template_models import CRMVisualTemplate
    other=Company(name='Other layout tenant',is_active=True);db.add(other);db.flush()
    db.get(CRMVisualTemplate,saved['id']).organization_id=other.id;db.commit()
    assert client.post(f'{ROOT}/lead/{ids["lead"]}/render',headers=h,json={'template_id':saved['id']}).status_code==404
    assert client.get(f'{ROOT}/lead/{ids["lead"]}',headers=h).json()['items']==[]


def test_crm_reader_cannot_read_invoice_and_linked_contact_requires_permission(client,db,records):
    from app.models.user import Role,Permission
    from app.core.security import get_password_hash
    from test_identity_utils import attach_test_identity,attach_workflow_branch
    h,ids=records
    permission=db.query(Permission).filter_by(name='crm_deals_view').first()
    if not permission:
        permission=Permission(name='crm_deals_view',description='View own deals',module='crm');db.add(permission);db.flush()
    role=Role(name='crm_sales_executive',is_system=True);role.permissions=[permission];db.add(role);db.flush()
    reader=User(email='template-reader@example.com',hashed_password=get_password_hash('TemplateReader@123'),is_active=True,role_id=role.id)
    db.add(reader);attach_test_identity(db,reader);branch=attach_workflow_branch(db,reader);db.flush()
    deal=db.get(CRMDeal,ids['deal']);deal.owner_user_id=reader.id;deal.branch_id=branch.id
    from app.branches.models import BranchOwnership
    from app.branches.catalog import resource_key
    key=resource_key(deal.__table__,{'id':deal.id})
    db.query(BranchOwnership).filter_by(resource_table=deal.__tablename__,resource_key=key).update({'branch_id':branch.id})
    db.commit()
    login=client.post('/api/v1/auth/login',json={'email':reader.email,'password':'TemplateReader@123','module':'crm'})
    assert login.status_code==200,login.text
    headers={'Authorization':'Bearer '+login.json()['access_token'],'X-Suite-Branch':str(branch.id)}
    assert client.get(f'{ROOT}/invoice/{ids["invoice"]}',headers=headers).status_code==403
    response=client.post(f'{ROOT}/deal/{ids["deal"]}/render',headers=headers,json={'template':design('deal',text='{{deal.name}} {{name}} {{email}}')})
    assert response.status_code==200,response.text
    assert 'Actual Opportunity' in response.json()['html']
    assert 'Actual Contact' not in response.json()['html'] and 'contact@example.com' not in response.json()['html']
    assert set(response.json()['unresolved'])=={'name','email'}
