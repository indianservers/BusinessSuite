"""Published native CRM Company purpose and canonical graph/source preservation."""
from types import MappingProxyType
from uuid import uuid4
import pytest
import os
import json
from pathlib import Path
from app.access.models import AccessPolicy
from app.branches.models import BranchGrant
from app.business_packs.models import PackMasterAvailability
from app.apps.crm.models import CRMCompany
from tests.test_accounts_engagements import fresh_accounts,scenario,catalog,directory_identity,engagement_input
from tests.test_settings_hub import actor
from tests.test_accounts_periods import body as period_body,send,prepared,revision


@pytest.mark.skipif(os.getenv('RUN_COMPANY_MASTER_BROWSER')!='1',reason='Opt-in original Companies component actual HTTP proof')
def test_original_default_companies_component_desktop_mobile():
    import subprocess,sys
    from app.core.managed_process import run
    root=Path(__file__).resolve().parents[2]
    result=run([sys.executable,str(root/'.local/run_company_master_browser.py')],cwd=root,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300)
    assert result.returncode==0,(result.stdout+result.stderr).decode('utf-8',errors='replace')


@pytest.fixture
def company_candidate(client,db,fresh_accounts,monkeypatch):
    from app.business_packs import common_core,company_master_core
    import traceback
    original_deny=common_core.deny
    def traced(message):
        if message in {'Company master raw SQL requires a separately reviewed native source','This source is outside the reviewed Company master graph'}:
            print('Static Company source frames:', ''.join(traceback.format_stack(limit=13)))
        return original_deny(message)
    monkeypatch.setattr(common_core,'deny',traced)
    expected=company_master_core.candidate_operations(common_core.CoreOperation)
    assert set(expected)<=set(common_core.OPERATIONS)
    assert all(common_core.OPERATIONS[key]==operation for key,operation in expected.items())
    case=fresh_accounts
    headers,user=actor(db,role='native-company-'+uuid4().hex,permissions=['crm_admin','srm_admin'],admin=True)
    user.organization_id=1
    db.add(BranchGrant(company_id=1,branch_id=case['branch'],user_id=user.id,can_write=True))
    db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={module:{'enabled':True,
        'permissions':[module+'_admin'],'actions':['view','create','edit','delete'],'scope':'organization'} for module in ('crm','srm')}))
    db.commit()
    return case,{**headers,'X-Suite-Branch':str(case['branch'])},user


def test_production_registration_publishes_only_eight_native_crm_company_routes():
    from app.business_packs import common_core,company_master_core
    from app.business_packs.runtime import RUNTIME_SUPPORT
    actual={key:operation for key,operation in common_core.OPERATIONS.items()
        if operation.purpose==company_master_core.PURPOSE}
    expected=company_master_core.candidate_operations(common_core.CoreOperation)
    assert actual==expected and len(actual)==8
    assert {operation.module for operation in actual.values()}=={'crm'}
    assert {method for method,path in actual}=={'GET','POST'}
    assert not RUNTIME_SUPPORT


def test_actual_unchanged_company_form_create_enroll_accounts_engagement_and_independent_review(client,db,company_candidate):
    case,headers,admin=company_candidate
    for path in ('/master-data/form-options','/master-data/companies/custom-fields','/master-data/company-directory/query'):
        response=client.get('/api/v1'+path,headers=headers,params={'source':'crm'})
        assert response.status_code==200,(path,response.text)
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json={
        'name':'Actual Company source '+uuid4().hex,'entityKind':'Company','roles':['Customer'],'country':'IN'})
    assert response.status_code==201,response.text
    born=response.json();assert born['entityKind']=='Company'
    assert not db.query(PackMasterAvailability).filter_by(resource_table='crm_companies',resource_key=str(born['id'])).count()
    before=client.get('/api/v1/srm/accounts/clients',headers=case['headers'])
    assert before.status_code==200 and born['id'] not in {row['id'] for row in before.json()['items']},before.text
    options=client.get(f"/api/v1/access/settings/business-packs/contexts/{case['context']}/master-options",headers=headers,params={'kind':'customers'})
    assert options.status_code==200,options.text
    choice=next(row for row in options.json()['items'] if row['id']==born['id'])
    enrolled=client.put(f"/api/v1/access/settings/business-packs/contexts/{case['context']}/masters",headers=headers,json={
        'kind':'customers','id':born['id'],'active':True,'expected_context_revision':options.json()['context_revision'],
        'expected_revision':choice['availability_revision'] or 0,'reason':'Explicit actual Company client enrollment'})
    assert enrolled.status_code==200,enrolled.text
    created=client.post('/api/v1/srm/accounts/engagements',headers=case['headers'],json=engagement_input(client_id=born['id']))
    assert created.status_code==201,created.text
    source={**case,'engagement':created.json()['id']}
    row=send(client,case['headers'],'',{**period_body(source),'client_id':born['id']},status=201)
    row=prepared(client,source,row)
    approved=send(client,case['reviewer']['headers'],f"/{row['id']}/approve",revision(row)|{
        'expected_work_revision':row['work_revision'],'reason':'Independent Company client review'})
    assert approved['state']=='approved'
    from app.business_packs.company_master_core import _births,_scopes
    assert not _births and not _scopes



def test_full_native_company_fields_primary_channels_financial_and_branch_values_are_preserved(client,db,company_candidate):
    case,headers,admin=company_candidate
    payload=full_company_input()
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json=payload)
    assert response.status_code==201,response.text
    created=response.json()
    assert created['legalName']==payload['legalName'] and created['addresses']==payload['addresses'] and created['taxRegistrations']==payload['taxRegistrations']
    assert set(created['roles'])==set(payload['roles']) and created['primaryContactId']
    profile=client.get(f"/api/v1/master-data/companies/{created['id']}",headers=headers,params={'source':'crm'})
    assert profile.status_code==200,profile.text
    assert len(profile.json()['channels'])==3 and profile.json()['bankAccountCount']==1 and profile.json()['upiCount']==1
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.apps.crm.financial_models import ContactFinancialProfile
    link=db.query(ContactIdentityLink).filter_by(account_id=created['id']).one()
    saved=db.query(ContactFinancialProfile).filter_by(contact_id=link.contact_id).one()
    assert saved.bank_accounts[0]['accountNumber']=='1234567890' and saved.upi_ids[0]['upiId']=='native@oksbi'


def full_company_input():
    suffix=uuid4().hex
    payload={'name':'Complete native company '+suffix,'entityKind':'Company','roles':['Customer','Partner'],'country':'IN',
        'legalName':'Legal Native Company','tradeName':'Native Trade','industry':'Software','website':'https://example.com',
        'email':suffix+'@example.com','phone':'9876543210','phone_country_code':'+91','notes':'Native source notes','tags':['priority'],
        'addresses':[{'kind':'Billing','line1':'1 Example Road','city':'Bengaluru','state':'Karnataka','postalCode':'560001','country':'IN'}],
        'taxRegistrations':[{'type':'PAN','number':'ABCDE1234F','country':'IN'}],
        'newPrimaryContact':{'name':'Explicit Company Primary','email':'primary-'+suffix+'@example.com'},
        'communicationChannels':[{'kind':'email','label':'Work','value':suffix+'@example.com','primary':True},
            {'kind':'phone','label':'Mobile','value':'9876543210','countryCode':'+91','primary':True,'whatsapp':True},
            {'kind':'email','label':'Billing','value':'billing-'+suffix+'@example.com'}],
        'financialData':{'version':0,'bankAccounts':[{'holderName':'Legal Native Company','bankName':'Native Bank',
            'accountNumber':'1234567890','ifsc':'SBIN0001234','country':'IN','currency':'INR','primary':True}],
            'upiIds':[{'upiId':'native@oksbi','label':'Business','primary':True}]},
        'branch_availability':{'scope':'current'}}
    return payload



def test_same_full_payload_works_through_unchanged_unconfigured_native_branch(client,db,company_candidate,monkeypatch):
    from app.business_packs import common_core,company_master_core
    from app.models.company import Branch
    case,headers,admin=company_candidate
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({key:operation for key,operation in common_core.OPERATIONS.items() if operation.purpose!=company_master_core.PURPOSE}))
    branch=Branch(company_id=1,name='Genuine isolated native comparison branch')
    db.add(branch);db.flush();db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=admin.id,can_write=True));db.commit()
    native_headers={**headers,'X-Suite-Branch':str(branch.id)}
    payload=full_company_input()
    response=client.post('/api/v1/master-data/companies',headers=native_headers,params={'source':'crm'},json=payload)
    assert response.status_code==201,response.text
    created=response.json()
    profile=client.get(f"/api/v1/master-data/companies/{created['id']}",headers=native_headers,params={'source':'crm'})
    assert profile.status_code==200,profile.text
    assert created['primaryContactId'] and len(profile.json()['channels'])==3
    assert profile.json()['bankAccountCount']==profile.json()['upiCount']==1



def test_linked_native_accounting_projection_matches_legacy_and_unlinked_is_not_inferred(client,db,company_candidate,monkeypatch):
    from datetime import date
    from app.business_packs import common_core,company_master_core
    from app.models.company import Branch
    from app.apps.fam.models import FAMParty,FAMSRMMapping,FAMPurchaseBill
    from app.branches.models import BranchOwnership
    native_operations=MappingProxyType({key:op for key,op in common_core.OPERATIONS.items() if op.purpose!=company_master_core.PURPOSE})
    candidate_operations=common_core.OPERATIONS
    case,headers,admin=company_candidate
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=admin.id).one()
    policy.grants={**policy.grants,'fam':{'enabled':True,'permissions':['fam_admin'],'actions':['view'],'scope':'organization'}}
    policy.version+=1
    branch=Branch(company_id=1,name='Native Company financial comparison')
    db.add(branch);db.flush();db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=admin.id,can_write=True));db.commit()
    headers={**headers,'X-Suite-Branch':str(branch.id)}
    monkeypatch.setattr(common_core,'OPERATIONS',native_operations)
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json={'name':'Linked Company '+uuid4().hex,'roles':['Customer'],'entityKind':'Company'})
    assert response.status_code==201,response.text
    ident=response.json()['id']
    party=FAMParty(company_id=1,party_code='LINK-'+uuid4().hex,party_type='customer',legal_name='Explicit mapped party')
    db.add(party);db.flush()
    mapping=FAMSRMMapping(company_id=1,srm_record_type='customer',srm_record_id=ident,fam_record_type='party',fam_record_id=party.id,mapping_status='active')
    purchase=FAMPurchaseBill(company_id=1,vendor_id=party.id,bill_number='Native bill',bill_date=date(2026,1,1),grand_total=123,status='draft')
    db.add_all([mapping,purchase]);db.flush()
    for row in (party,mapping,purchase):
        db.add(BranchOwnership(company_id=1,branch_id=branch.id,resource_table=row.__tablename__,resource_key=str(row.id),source='explicit-known-financial-fixture'))
    db.commit()
    path=f'/api/v1/master-data/companies/{ident}'
    native=client.get(path,headers=headers,params={'source':'crm'})
    assert native.status_code==200,native.text
    assert native.json()['financialNote'].startswith('Verified accounting') and native.json()['purchases']
    monkeypatch.setattr(common_core,'OPERATIONS',candidate_operations)
    actual=client.get(path,headers=headers,params={'source':'crm'})
    assert actual.status_code==200,actual.text
    for key in ('financialNote','purchases','payables'):
        assert actual.json()[key]==native.json()[key]
    mapping.mapping_status='inactive';db.commit()
    absent=client.get(path,headers=headers,params={'source':'crm'})
    assert absent.status_code==200 and absent.json()['purchases']==[] and absent.json()['payables'] is None,absent.text
    assert absent.json()['financialNote'].startswith('No verified')
    # A forged same-company mapping cannot turn a foreign-company party into a match.
    from app.models.company import Company
    foreign_company=Company(name='Foreign financial Company '+uuid4().hex);db.add(foreign_company);db.flush()
    foreign_party=FAMParty(company_id=foreign_company.id,party_code='FOREIGN-'+uuid4().hex,
        party_type='customer',legal_name='Private foreign legal name');db.add(foreign_party);db.flush()
    mapping.mapping_status='active';mapping.fam_record_id=foreign_party.id;db.commit()
    foreign=client.get(path,headers=headers,params={'source':'crm'})
    assert foreign.status_code==200,foreign.text
    assert foreign.json()['purchases']==[] and foreign.json()['payables'] is None
    assert foreign.json()['financialNote'].startswith('No verified')
    assert 'Private foreign legal name' not in foreign.text


def test_native_company_branch_visibility_is_identical_to_original(client,db,company_candidate,monkeypatch):
    from app.business_packs import common_core,company_master_core
    from app.models.company import Branch
    case,headers,admin=company_candidate
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json={
        'name':'Native branch Company '+uuid4().hex,'roles':['Customer'],'entityKind':'Company'})
    assert response.status_code==201,response.text
    branch=Branch(company_id=1,name='Other native branch '+uuid4().hex,is_active=True);db.add(branch);db.flush()
    db.add(BranchGrant(company_id=1,branch_id=branch.id,user_id=admin.id,can_write=True));db.commit()
    other={**headers,'X-Suite-Branch':str(branch.id)};path=f"/api/v1/master-data/companies/{response.json()['id']}"
    operations=common_core.OPERATIONS
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({key:op for key,op in operations.items()
        if op.purpose!=company_master_core.PURPOSE}))
    native=client.get(path,headers=other,params={'source':'crm'})
    monkeypatch.setattr(common_core,'OPERATIONS',operations)
    actual=client.get(path,headers=other,params={'source':'crm'})
    assert actual.status_code==native.status_code==404,(native.text,actual.text)



def test_native_scope_projection_parity_and_no_hrms_or_metadata_body_grants(client,db,company_candidate,monkeypatch):
    from app.business_packs import company_master_core
    from app.apps.crm.api import router as crm
    from app.models.employee import Employee
    from app.apps.crm.models import CRMOwner,CRMTeam
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.common_binding import MARKER
    from fastapi import HTTPException
    from datetime import date
    case,headers,admin=company_candidate
    with native_writer(db,case['manager'],case['branch']):
        row=Employee(employee_id='META-'+uuid4().hex,first_name='Current',last_name='Actor',user_id=admin.id,
            branch_id=case['branch'],status='Active',date_of_joining=date(2025,1,1))
        db.add(row);db.commit()
    assert company_master_core.native_scope_projection(db,admin) is None
    original=company_master_core.install;seen=[]
    def checked(session,actor,scope):
        expected=crm._crm_user_scope(session,actor)
        cleanup=original(session,actor,scope)
        try:
            assert company_master_core.native_scope_projection(session,actor)==expected
            assert expected['branch_id']==case['branch']
            for model in (Employee,CRMOwner,CRMTeam):
                with pytest.raises(HTTPException) as denied:session.query(model).all()
                assert denied.value.status_code==403
            with pytest.raises(HTTPException):company_master_core.native_scope_projection(session,case['manager'])
            marker=session.info[MARKER]
            try:
                session.info[MARKER]={'purpose':company_master_core.PURPOSE}
                with pytest.raises(HTTPException):company_master_core.native_scope_projection(session,actor)
            finally:session.info[MARKER]=marker
            seen.append(True)
        except BaseException:
            cleanup();raise
        return cleanup
    monkeypatch.setattr(company_master_core,'install',checked)
    response=client.get('/api/v1/master-data/form-options',headers=headers,params={'source':'crm'})
    assert response.status_code==200,response.text
    assert seen and company_master_core.native_scope_projection(db,admin) is None


def test_company_financial_scalar_lease_does_not_grant_bodies_or_survive_its_source_block(client,db,company_candidate,monkeypatch):
    from contextlib import contextmanager
    from fastapi import HTTPException
    from app.business_packs import company_master_core
    from app.apps.fam.models import FAMParty
    case,headers,admin=company_candidate
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json={
        'name':'Scalar source Company '+uuid4().hex,'roles':['Customer'],'entityKind':'Company'})
    assert response.status_code==201,response.text
    original=company_master_core.profile_financial_read;seen=[]
    @contextmanager
    def checked(session,actor,row,ident):
        with pytest.raises(HTTPException) as outside:session.query(FAMParty.id).all()
        assert outside.value.status_code==403
        with original(session,actor,row,ident):
            with pytest.raises(HTTPException) as body:session.query(FAMParty).all()
            assert body.value.status_code==403
            with pytest.raises(HTTPException):session.query(FAMParty.legal_name).all()
            session.query(FAMParty.id).all()
            yield
        with pytest.raises(HTTPException) as after:session.query(FAMParty.id).all()
        assert after.value.status_code==403
        seen.append(True)
    monkeypatch.setattr(company_master_core,'profile_financial_read',checked)
    profile=client.get(f"/api/v1/master-data/companies/{response.json()['id']}",headers=headers,params={'source':'crm'})
    assert profile.status_code==200,profile.text
    assert seen and not company_master_core._financial_reads



def graph_counts(db):
    from sqlalchemy import select,func
    from app.apps.crm.models import CRMContact,CRMCustomFieldValue
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails,BusinessRelationship,ContactChannel,CompanyContactLink
    from app.apps.crm.financial_models import ContactFinancialProfile
    return tuple(db.connection().scalar(select(func.count()).select_from(model.__table__)) for model in (
        CRMCompany,CRMContact,ContactIdentityLink,CompanyMasterDetails,BusinessRelationship,ContactChannel,
        CompanyContactLink,ContactFinancialProfile,CRMCustomFieldValue))


@pytest.mark.parametrize('fault',['no_create','no_manage','hidden_required','late_audit','internal_commit','duplicate'])
def test_company_native_create_and_validation_failures_leave_no_orphan_graph(client,db,company_candidate,monkeypatch,fault):
    from app.apps.crm.models import CRMCustomField
    from app.shared import master_data
    from fastapi import HTTPException
    case,headers,admin=company_candidate
    body={'name':'Company failure source '+uuid4().hex,'roles':['Customer'],'entityKind':'Company','country':'IN'}
    if fault in ('no_create','no_manage'):
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=admin.id).one()
        grant={**policy.grants['crm']}
        if fault=='no_create':grant['actions']=['view']
        else:grant['permissions']=['crm_view']
        policy.grants={**policy.grants,'crm':grant};policy.version+=1;db.commit()
    elif fault=='hidden_required':
        db.add(CRMCustomField(organization_id=1,entity='companies',field_key='hidden_required_company',label='Required native field',field_type='text',is_required=True,is_active=True,is_visible=False))
        db.commit()
    elif fault in ('late_audit','internal_commit'):
        original=master_data.audit
        def fail_after_source(session,actor,action,*args,**kwargs):
            if action=='COMPANY_MASTER_SAVED':
                if fault=='internal_commit':session.commit()
                raise HTTPException(409,'Injected canonical Company audit failure')
            return original(session,actor,action,*args,**kwargs)
        monkeypatch.setattr(master_data,'audit',fail_after_source)
    elif fault=='duplicate':
        created=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json=body)
        assert created.status_code==201,created.text
    before=graph_counts(db)
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json=body)
    expected={'no_create':403,'no_manage':403,'hidden_required':422,'late_audit':409,'internal_commit':409,'duplicate':409}[fault]
    assert response.status_code==expected,response.text
    assert graph_counts(db)==before
    if fault=='duplicate':assert response.json()['detail']['matches']
    from app.business_packs.company_master_core import _births,_scopes,_financial_reads
    assert not _births and not _scopes and not _financial_reads


def test_foreign_required_custom_definition_is_not_adopted(client,db,company_candidate):
    from app.apps.crm.models import CRMCustomField
    from app.models.company import Company
    case,headers,admin=company_candidate
    foreign=Company(name='Foreign custom field source '+uuid4().hex);db.add(foreign);db.flush()
    db.add(CRMCustomField(organization_id=foreign.id,entity='companies',field_key='foreign_required',label='Foreign required',field_type='text',is_required=True,is_active=True))
    db.commit()
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json={'name':'Local company '+uuid4().hex,'roles':['Customer'],'entityKind':'Company'})
    assert response.status_code==201,response.text


def test_native_scope_ignores_raw_pack_selector_without_granting_other_source_modules(client,db,company_candidate):
    case,headers,admin=company_candidate
    body={'name':'Independent native source '+uuid4().hex,'roles':['Customer'],'entityKind':'Company'}
    created=client.post('/api/v1/master-data/companies',headers={**headers,'X-Suite-Pack-Context':'not-a-pack-scope'},params={'source':'crm'},json=body)
    assert created.status_code==201,created.text
    alternate=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'srm'},json={**body,'name':'Different native module'})
    assert alternate.status_code in (403,503),alternate.text


@pytest.mark.parametrize('channels',[[],[{'kind':'email','value':'replacement@example.com','primary':True}]])
def test_explicit_native_channel_replacement_removes_only_born_compatibility_channels(client,db,company_candidate,channels):
    case,headers,admin=company_candidate
    response=client.post('/api/v1/master-data/companies',headers=headers,params={'source':'crm'},json={
        'name':'Native channel replacement '+uuid4().hex,'roles':['Customer'],'entityKind':'Company',
        'email':'original@example.com','communicationChannels':channels})
    assert response.status_code==201,response.text
    assert response.json()['email']==('replacement@example.com' if channels else None)
