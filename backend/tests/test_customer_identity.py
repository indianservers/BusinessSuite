import pytest
from app.services.customer_identity import CustomerIndex, phone_key, match_whatsapp, match_recipient
from app.apps.crm.models import CRMContact, CRMLead
from app.apps.communication.customer_models import CustomerRecipient, CustomerBinding
from app.shared.whatsapp_models import WhatsAppContact
from app.models.company import Company, Branch
from app.branches.models import BranchOwnership


@pytest.fixture
def identities(db):
    company=Company(name='Identity test');other=Company(name='Other identity tenant')
    db.add_all([company,other]);db.flush()
    branches=[Branch(company_id=company.id,name='Identity main'),Branch(company_id=company.id,name='Identity other')]
    db.add_all(branches);db.flush()
    return db,company,other,branches


def customer(db,company,branch,**values):
    row=CRMContact(organization_id=company.id,branch_id=branch.id,first_name='Synthetic',full_name='Synthetic Customer',**values)
    db.add(row);db.flush();return row


def test_normalization_is_exact_and_country_aware():
    assert phone_key('09876 543210','+91')=='919876543210'
    assert phone_key('+91 (98765) 43210')=='919876543210'
    assert phone_key('00919876543210')=='919876543210'
    assert phone_key('9876543210',country='India')=='919876543210'
    assert phone_key('9876543210') is None
    assert phone_key('9876543210 ext 5','91') is None
    assert phone_key('1234','91') is None


def test_unique_alternate_phone_and_email_match_without_changing_consent(identities):
    db,company,other,branches=identities
    record=customer(db,company,branches[0],alternate_phone='98765-43210',alternate_phone_country_code='+91',email='Customer@Example.invalid')
    customer(db,other,branches[0],phone='+919876543210')
    customer(db,company,branches[1],phone='+919876543210')
    wa=WhatsAppContact(organization_id=company.id,recipient='919876543210',consent='unknown')
    db.add(wa);db.flush()
    db.add(BranchOwnership(resource_table=wa.__tablename__,resource_key=str(wa.id),company_id=company.id,branch_id=branches[0].id,source='test'));db.flush()
    index=CustomerIndex(db,company.id,branches[0].id)
    assert match_whatsapp(db,wa,index,True)['status']=='matched'
    assert (wa.entity_type,wa.entity_id)==('contact',record.id)
    assert wa.consent=='unknown'
    from app.models.user import User
    actor=User(email='identity-actor@example.invalid',hashed_password='unused',is_active=True)
    db.add(actor);db.flush()
    recipient=CustomerRecipient(organization_id=company.id,branch_id=branches[0].id,name='Customer',email=' customer@example.invalid ',active=True,preferences={},created_by=actor.id)
    db.add(recipient);db.flush()
    assert match_recipient(db,recipient,index,True)['status']=='matched'
    db.flush()
    assert recipient.crm_contact_id==record.id
    assert recipient.preferences=={}
    assert db.query(CustomerBinding).filter_by(recipient_id=recipient.id).count()==1
    assert match_recipient(db,recipient,index,True)['status']=='linked'


def test_duplicates_conflicts_and_converted_leads_are_not_guessed(identities):
    db,company,_,branches=identities
    first=customer(db,company,branches[0],phone='+919876543210',email='one@example.invalid')
    customer(db,company,branches[0],phone='+919876543211',email='two@example.invalid')
    lead=CRMLead(organization_id=company.id,branch_id=branches[0].id,first_name='Lead',full_name='Duplicate Lead',phone='9876543210',phone_country_code='91')
    db.add(lead);db.flush()
    index=CustomerIndex(db,company.id,branches[0].id)
    assert index.match(phone='919876543210')['status']=='ambiguous'
    assert index.match(phone='919876543210',email='two@example.invalid')['status']=='conflict'
    assert index.match(phone='919876543210',email='one@example.invalid')['candidates'][0]['entityId']==first.id
    lead.is_converted=True;db.flush()
    assert CustomerIndex(db,company.id,branches[0].id).match(phone='919876543210')['status']=='matched'
    assert CustomerIndex(db,company.id,None).match(phone='919876543210')['status']=='unmatched'


def test_existing_links_are_preserved(identities):
    db,company,_,branches=identities
    record=customer(db,company,branches[0],phone='+919876543210')
    wa=WhatsAppContact(organization_id=company.id,recipient='919876543210',consent='opted_out',entity_type='lead',entity_id=999)
    db.add(wa);db.flush()
    assert match_whatsapp(db,wa,CustomerIndex(db,company.id,branches[0].id),True)['status']=='linked'
    assert wa.entity_id==999 and wa.consent=='opted_out'


def test_signed_inbound_automatically_links_unique_customer(identities):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppConnection
    db,company,_,branches=identities
    record=customer(db,company,branches[0],phone='9876543210',phone_country_code='+91')
    connection=WhatsAppConnection(organization_id=company.id,waba_id='8001',phone_number_id='8002',routing_key='8002',status='connected',inbound_branch_id=branches[0].id)
    db.add(connection);db.flush()
    wa.ingest(db,{'object':'whatsapp_business_account','entry':[{'id':'8001','changes':[{'value':{'metadata':{'phone_number_id':'8002'},'messages':[{'id':'wamid.identity','from':'919876543210','type':'text','text':{'body':'Hi'}}]}}]}]})
    row=db.query(WhatsAppContact).filter_by(organization_id=company.id).one()
    assert (row.entity_type,row.entity_id)==('contact',record.id)
