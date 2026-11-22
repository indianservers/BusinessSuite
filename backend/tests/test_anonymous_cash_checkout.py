"""Dedicated anonymous cash account uses real native customer/invoice/receipts."""
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select,update,insert
from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
from app.apps.srm.anonymous_cash_schemas import CashAccountSetup
from app.apps.srm.anonymous_cash import configure,_KEY
from app.apps.srm.service_checkout import checkout
from app.apps.srm.service_checkout_schemas import CheckoutInput
from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt,SRMSalesOrderLine
from app.apps.crm.models import CRMContact,CRMCompany
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer

@pytest.fixture
def anonymous(db,scenario):
    AnonymousCashAccount.__table__.create(db.bind,checkfirst=True)
    user,branch,cat,basket=scenario
    with native_writer(db,user,branch):
        account=configure(CashAccountSetup(action='create',label='Anonymous counter cash control',jurisdiction_country='IN',reason='Explicit anonymous counter setup'),db,user)
    def sale():
        original=basket(False)
        return CheckoutInput.model_validate({'buyer_mode':'anonymous_cash','customer_id':0,'request_id':str(uuid4()),'pos_session_id':original.pos_session_id,
            'lines':[original.lines[0].model_dump(mode='json')],
            'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]})
    return user,branch,account,sale


@pytest.mark.parametrize("captured_at", [None, "2026-11-21T09:15:00+05:30"])
def test_anonymous_native_full_payment_and_exact_replay_no_person(db,anonymous,captured_at):
    user,branch,account,sale=anonymous
    data=CheckoutInput.model_validate({**sale().model_dump(mode="json"),"captured_at":captured_at})
    before=db.query(CRMContact).count()
    with native_writer(db,user,branch):
        result=checkout(data,db,user)
        assert checkout(data,db,user)==result
    invoice=db.get(SRMInvoice,result['invoice']['id']);receipt=db.get(SRMReceipt,result['receipts'][0]['id'])
    order=db.get(SRMSalesOrder,result['sales_order_id'])
    assert order.metadata_json.get('pos_captured_at') == ("2026-11-21T03:45:00+00:00" if captured_at else None)
    assert invoice.customer_id==receipt.customer_id==account['customer_id']
    assert invoice.total_amount==invoice.paid_amount==118 and invoice.balance_amount==0
    assert db.query(CRMContact).count()==before
    from app.apps.srm.commercial_models import InvoiceContext
    snapshot=db.get(InvoiceContext,invoice.id).customer_snapshot
    assert snapshot['name']=='Anonymous counter cash control' and not snapshot['address'] and not snapshot['email'] and not snapshot['phone']
    assert _KEY not in db.connection().info

@pytest.mark.parametrize('case',['partial','booked','registered_spoof'])
def test_anonymous_no_credit_booking_or_customer_spoof(db,anonymous,scenario,case):
    user,branch,account,sale=anonymous;data=sale()
    if case=='partial':data.payments[0].amount=Decimal('1')
    elif case=='booked':data.lines=[scenario[3](False).lines[1]]
    else:data=CheckoutInput.model_validate({**data.model_dump(mode='json'),'buyer_mode':'registered','customer_id':account['customer_id']})
    with native_writer(db,user,branch),pytest.raises(HTTPException):checkout(data,db,user)
    assert db.query(SRMSalesOrder).count()==db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==0
    assert _KEY not in db.connection().info


def test_control_source_generic_mutations_and_bulk_are_denied(db,anonymous):
    user,branch,account,sale=anonymous
    with native_writer(db,user,branch):result=checkout(sale(),db,user)
    with native_writer(db,user,branch):
        for method in ('orm','core','bulk'):
            try:
                with db.begin_nested():
                    if method=='orm':
                        invoice=db.get(SRMInvoice,result['invoice']['id']);invoice.status='draft';db.flush()
                    elif method=='core':db.execute(update(SRMInvoice).where(SRMInvoice.id==result['invoice']['id']).values(status='draft'))
                    else:db.bulk_update_mappings(SRMInvoice,[{'id':result['invoice']['id'],'status':'draft'}])
            except HTTPException as error:assert error.status_code==403
            else:pytest.fail('Generic anonymous financial mutation escaped')
    assert db.get(SRMInvoice,result['invoice']['id']).status=='paid'


def test_native_fam_reuses_control_party_and_balances_to_zero(client,db,anonymous,scenario):
    from app.apps.srm.models import SRMReceiptAllocation
    from app.apps.fam.models import FAMParty,FAMLedgerEntry
    user,branch,account,sale=anonymous
    with native_writer(db,user,branch):result=checkout(sale(),db,user)
    headers=scenario[2][0]
    response=client.post(f"/api/v1/fam/integrations/srm/post-invoice/{result['invoice']['id']}",headers=headers)
    assert response.status_code==200,response.text
    allocations=db.query(SRMReceiptAllocation).all()
    for allocation in allocations:
        response=client.post(f'/api/v1/fam/integrations/srm/post-allocation/{allocation.id}',headers=headers)
        assert response.status_code==200,response.text
    parties=db.query(FAMParty).filter_by(party_code=f"SRM-CUST-{account['customer_id']}").all()
    assert len(parties)==1
    entries=db.query(FAMLedgerEntry).filter_by(ledger_id=parties[0].ledger_id).all()
    assert entries and sum((entry.debit_amount-entry.credit_amount for entry in entries),Decimal(0))==0
    assert db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==1


def test_native_account_identity_is_company_link_without_fake_person(db,scenario):
    from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
    from app.common.models import CommonPerson
    from app.models.user import User
    from app.models.employee import Employee
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails
    AnonymousCashAccount.__table__.create(db.bind,checkfirst=True)
    user,branch,cat,basket=scenario
    before=[db.query(model).count() for model in (CommonPerson,User,Employee)]
    data=CashAccountSetup(action='create',label='Explicit counter ledger',jurisdiction_country='IN',reason='Dedicated anonymous cash counter account')
    with native_writer(db,user,branch):
        first=configure(data,db,user);assert configure(data,db,user)==first
    assert [db.query(model).count() for model in (CommonPerson,User,Employee)]==before
    links=db.query(ContactIdentityLink).filter_by(account_id=first['customer_id']).all()
    assert len(links)==1 and links[0].person_id is None and links[0].employee_id is None and links[0].lead_id is None
    details=db.get(CompanyMasterDetails,first['customer_id']);assert details.primary_contact_id is None and not details.addresses and not details.tax_registrations

@pytest.mark.parametrize('method',['customer_edit','contact_create','receipt_confirm','order_cancel','child_append','core_insert','text_update','bulk_insert','insert_select'])
def test_generic_source_and_account_bypasses_are_denied(db,anonymous,method):
    from sqlalchemy import text,literal
    from app.apps.srm.api import router as native
    user,branch,account,sale=anonymous
    with native_writer(db,user,branch):result=checkout(sale(),db,user)
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:
        with db.begin_nested():
            if method=='customer_edit':db.get(CRMCompany,account['customer_id']).email='fake@example.com';db.flush()
            elif method=='contact_create':
                db.add(CRMContact(organization_id=1,company_id=account['customer_id'],full_name='Invented person',first_name='Invented'));db.flush()
            elif method=='receipt_confirm':native.confirm_receipt_operation(result['receipts'][0]['id'],db,user,commit=False)
            elif method=='order_cancel':db.get(SRMSalesOrder,result['sales_order_id']).status='cancelled';db.flush()
            elif method=='child_append':
                db.add(SRMSalesOrderLine(sales_order_id=result['sales_order_id'],description='Credit addition',quantity=1,unit_price=10,line_total=10));db.flush()
            elif method=='core_insert':db.execute(insert(SRMReceipt).values(organization_id=1,receipt_number='BYPASS-'+uuid4().hex,customer_id=account['customer_id'],amount=50))
            elif method=='text_update':db.execute(text('UPDATE srm_invoices SET status=:status WHERE id=:id'),{'status':'draft','id':result['invoice']['id']})
            elif method=='bulk_insert':db.bulk_insert_mappings(SRMReceipt,[{'organization_id':1,'receipt_number':'BULK-'+uuid4().hex,'customer_id':account['customer_id'],'amount':10}])
            else:db.execute(insert(SRMReceipt).from_select(['organization_id','receipt_number','customer_id','amount'],select(literal(1),literal('SELECT-'+uuid4().hex),literal(account['customer_id']),literal(10))))
    assert error.value.status_code in {400,403,409}
    assert db.get(CRMCompany,account['customer_id']).email is None
    assert db.query(SRMReceipt).count()==1 and db.query(SRMSalesOrderLine).count()==1


def test_disabled_control_account_history_readable_but_not_credit(client,db,anonymous,scenario):
    user,branch,account,sale=anonymous
    with native_writer(db,user,branch):
        result=checkout(sale(),db,user)
        configure(CashAccountSetup(action='status',expected_revision=account['revision'],active=False,reason='Disable new anonymous counter sales'),db,user)
        with pytest.raises(HTTPException):checkout(sale(),db,user)
    headers=scenario[2][0]
    assert client.get(f"/api/v1/srm/invoices/{result['invoice']['id']}",headers=headers).status_code==200
    assert client.get(f"/api/v1/srm/receipts/{result['receipts'][0]['id']}",headers=headers).status_code==200
    with native_writer(db,user,branch),pytest.raises(HTTPException):
        db.execute(update(SRMInvoice).where(SRMInvoice.id==result['invoice']['id']).values(status='draft'))


def test_imported_draft_receipt_cannot_confirm_outside_checkout(db,anonymous):
    from app.apps.srm.api import router as native
    from app.branches.models import BranchOwnership
    user,branch,account,sale=anonymous
    # Trusted audit/import setup bypasses the public write barrier deliberately.
    connection=db.connection()
    if connection.dialect.name=='sqlite':
        connection.exec_driver_sql("INSERT INTO srm_receipts (organization_id,receipt_number,customer_id,status,currency,amount,unallocated_amount,created_by) VALUES (?,?,?,?,?,?,?,?)",(1,'IMPORTED-DRAFT',account['customer_id'],'draft','INR',50,50,user.id))
    else:
        connection.exec_driver_sql("INSERT INTO srm_receipts (organization_id,receipt_number,customer_id,status,currency,amount,unallocated_amount,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",(1,'IMPORTED-DRAFT',account['customer_id'],'draft','INR',50,50,user.id))
    ident=connection.execute(select(SRMReceipt.id).where(SRMReceipt.receipt_number=='IMPORTED-DRAFT')).scalar_one()
    connection.execute(BranchOwnership.__table__.insert().values(resource_table='srm_receipts',resource_key=str(ident),company_id=1,branch_id=branch,source='trusted-audit-test'))
    db.commit()
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:
        with db.begin_nested():native.confirm_receipt_operation(ident,db,user,commit=False)
    assert error.value.status_code==403 and db.get(SRMReceipt,ident).status=='draft'


def test_named_financial_core_stays_writable_when_control_account_exists(db,anonymous,scenario):
    from app.apps.srm.api import router as native
    from app.apps.srm.schemas import SRMReceiptCreate
    user,branch,account,sale=anonymous
    with native_writer(db,user,branch):
        receipt=native.create_receipt_operation(SRMReceiptCreate(customer_id=101,amount=12),db,user,commit=False)
        native.confirm_receipt_operation(receipt['id'],db,user,commit=False)
        db.execute(update(SRMReceipt).where(SRMReceipt.id==receipt['id']).values(reference_number='Named core unaffected'));db.commit()
    assert db.get(SRMReceipt,receipt['id']).reference_number=='Named core unaffected'


def test_failed_anonymous_checkout_and_nested_permits_clean_up(db,anonymous):
    from app.apps.srm.anonymous_cash import checkout_permit,resolve_account
    from app.apps.srm.service_checkout import _authority
    user,branch,account,sale=anonymous
    with native_writer(db,user,branch):
        company,selected,scope=_authority(db,user,billing=True,payments=True)
        descriptor=resolve_account(db,user,company,selected,scope)
        with checkout_permit(db,user,descriptor,scope):
            outer=db.connection().info[_KEY]
            with pytest.raises(HTTPException):
                with checkout_permit(db,user,descriptor,scope):pass
            assert db.connection().info[_KEY] is outer
        assert _KEY not in db.connection().info
        data=sale();data.payments[0].amount=Decimal('1')
        with pytest.raises(HTTPException):checkout(data,db,user)
        assert _KEY not in db.connection().info


def test_setup_requires_actual_company_admin_even_native_pos_manager(db,scenario):
    from tests.test_settings_hub import actor
    AnonymousCashAccount.__table__.create(db.bind,checkfirst=True)
    user,branch,cat,basket=scenario
    _,manager=actor(db,role='srm_sales_manager',permissions=['srm_manage'],admin=False);manager.organization_id=1
    from app.branches.models import BranchGrant
    db.add(BranchGrant(company_id=1,user_id=manager.id,branch_id=branch,can_write=True));db.commit()
    with native_writer(db,manager,branch),pytest.raises(HTTPException) as error:
        configure(CashAccountSetup(action='create',label='Unauthorized counter',jurisdiction_country='IN',reason='Attempt without company admin authority'),db,manager)
    assert error.value.status_code==403 and db.query(AnonymousCashAccount).count()==0


def test_static_migration_repeatable_and_scope_identity_immutable(db,anonymous):
    import runpy
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    user,branch,account,sale=anonymous
    migration=runpy.run_path(str(Path(__file__).parents[1]/'alembic_postgresql/versions/pg_20261114_105_anonymous_cash.py'))
    with Operations.context(MigrationContext.configure(db.connection())):
        migration['upgrade']();migration['upgrade']();migration['downgrade']()
    row=db.get(AnonymousCashAccount,account['id']);row.customer_id=101
    with pytest.raises(ValueError):db.flush()


def test_missing_and_partial_schema_fail_without_default_anonymous(db):
    from sqlalchemy import create_engine,MetaData,Table,Column,Integer
    from app.apps.srm.anonymous_cash import installed
    metadata=MetaData();engine=create_engine('sqlite://')
    with engine.begin() as connection:
        assert installed(connection) is False
        Table('srm_anonymous_cash_accounts',metadata,Column('id',Integer,primary_key=True)).create(connection)
        with pytest.raises(HTTPException) as error:installed(connection)
        assert error.value.status_code==503
    engine.dispose()


def test_anonymous_scope_never_falls_back_to_other_pack_or_unknown_role(db,scenario):
    from tests.test_service_checkout import enable_audited_pack,audited_pack_writer
    from app.business_packs.models import PackActivation,PackContext,PackUserGrant
    from app.business_packs.access import resolve_context
    AnonymousCashAccount.__table__.create(db.bind,checkfirst=True)
    user,branch,cat,basket=scenario
    context,grant,provider,register=enable_audited_pack(db,user,branch,cat)
    original=basket(False)
    with audited_pack_writer(db,user,branch,context):
        account=configure(CashAccountSetup(action='create',label='Hospital counter ledger',jurisdiction_country='IN',reason='Explicit hospital counter ledger setup'),db,user)
        data=CheckoutInput.model_validate({'buyer_mode':'anonymous_cash','customer_id':0,'request_id':str(uuid4()),'pos_session_id':register.id,
            'lines':[original.lines[0].model_dump(mode='json')],'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]})
    with audited_pack_writer(db,user,branch,context):
        checkout(data,db,user)
    other=PackActivation(company_id=1,pack_key='restaurant',pack_version=1,state='active');db.add(other);db.flush()
    foreign=PackContext(company_id=1,branch_id=branch,activation_id=other.id,pack_key='restaurant',pack_version=1,state='active');db.add(foreign);db.flush()
    other_grant=PackUserGrant(company_id=1,branch_id=branch,context_id=foreign.id,user_id=user.id,role='restaurant_manager');db.add(other_grant);db.commit()
    with native_writer(db,user,branch):
        db.info['business_pack_scope']=resolve_context(db,user,db.info['branch_context'],foreign.id)
        with pytest.raises(HTTPException) as error:checkout(data.model_copy(update={'request_id':uuid4()}),db,user)
        assert error.value.status_code==409
        db.info.pop('business_pack_scope',None)
    grant.role='unknown_role';db.commit()
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:
        resolve_context(db,user,db.info['branch_context'],context.id)
    assert error.value.status_code==403
    assert db.query(SRMInvoice).count()==1


def test_selected_foreign_customer_cannot_become_counter_account(db,scenario):
    from app.models.company import Company
    AnonymousCashAccount.__table__.create(db.bind,checkfirst=True)
    user,branch,cat,basket=scenario
    db.add(Company(id=2,name='Foreign company'))
    foreign=CRMCompany(organization_id=2,name='Foreign ledger',account_type='Customer',country='IN');db.add(foreign);db.commit()
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:
        configure(CashAccountSetup(action='select',customer_id=foreign.id,label='Foreign ledger',jurisdiction_country='IN',reason='Cannot select another tenant account'),db,user)
    assert error.value.status_code==404 and db.query(AnonymousCashAccount).count()==0


def test_guard_import_does_not_register_optional_model_or_duplicate_table():
    import subprocess,sys
    code='''from app.db.base_class import Base
before=set(Base.metadata.tables)
from app.apps.srm import anonymous_cash
assert set(Base.metadata.tables)==before
from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
assert Base.metadata.tables[AnonymousCashAccount.__tablename__] is AnonymousCashAccount.__table__
assert AnonymousCashAccount.__table__ is not anonymous_cash._CONTROL
assert set(AnonymousCashAccount.__table__.c.keys())==set(anonymous_cash._CONTROL.c.keys())
'''
    from pathlib import Path
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,cwd=Path(__file__).parents[1])
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef')])
def test_doctor_chef_cannot_read_or_configure_cash_account_even_native_admin(db,scenario,pack,role):
    from app.business_packs.models import PackActivation,PackContext,PackUserGrant
    from app.business_packs.access import resolve_context
    from app.apps.srm.anonymous_cash_api import configuration
    user,branch,cat,basket=scenario
    activation=PackActivation(company_id=1,pack_key=pack,pack_version=1,state='active');db.add(activation);db.flush()
    context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key=pack,pack_version=1,state='active');db.add(context);db.flush()
    db.add(PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role=role));db.commit()
    with native_writer(db,user,branch):
        scope=resolve_context(db,user,db.info['branch_context'],context.id);db.info['business_pack_scope']=scope
        try:
            with pytest.raises(HTTPException) as error:configuration(db,user,scope)
            assert error.value.status_code==403
            with pytest.raises(HTTPException) as error:configure(CashAccountSetup(action='create',label='Disallowed counter',jurisdiction_country='IN',reason='No financial settings capability'),db,user)
            assert error.value.status_code==403
        finally:db.info.pop('business_pack_scope',None)


@pytest.mark.parametrize('corruption',[None,'personal_contact','foreign_link'])
def test_audited_anonymous_http_uses_only_canonical_counter_identity(db,client,scenario,corruption):
    from tests.test_service_checkout import enable_audited_pack,audited_pack_writer
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.business_packs.models import PackMasterAvailability
    user,branch,cat,basket=scenario
    original=basket(False)
    context,_,_,register=enable_audited_pack(db,user,branch,cat)
    with audited_pack_writer(db,user,branch,context):
        account=configure(CashAccountSetup(action='create',label='Scoped canonical counter',jurisdiction_country='IN',reason='Explicit isolated cash setup'),db,user)
    enrollment=db.query(PackMasterAvailability).filter_by(context_id=context.id,resource_table='crm_companies',resource_key=str(account['customer_id'])).one()
    assert enrollment.active
    if corruption:
        link=db.query(ContactIdentityLink).filter_by(account_id=account['customer_id']).one()
        if corruption=='personal_contact':
            statement=update(CRMContact.__table__).where(CRMContact.id==link.contact_id).values(email='private@example.test')
        else:
            statement=update(ContactIdentityLink.__table__).where(ContactIdentityLink.id==link.id).values(organization_id=2)
        # Trusted corruption fixture bypasses the intentionally stronger generic
        # mutation barrier, proving the fixed validation independently.
        connection=db.connection();compiled=statement.compile(dialect=connection.dialect)
        parameters=tuple(compiled.params[key] for key in compiled.positiontup) if compiled.positiontup else compiled.params
        connection.exec_driver_sql(str(compiled),parameters)
        db.commit()
    payload={'buyer_mode':'anonymous_cash','customer_id':0,'request_id':str(uuid4()),'pos_session_id':register.id,
        'lines':[original.lines[0].model_dump(mode='json')],'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]}
    headers={**cat[0],'X-Suite-Pack-Context':str(context.id)}
    response=client.post('/api/v1/srm/service-checkout',headers=headers,json=payload)
    if corruption:
        assert response.status_code==422,response.text
        assert 'private@example.test' not in response.text
        assert db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==0
    else:
        assert response.status_code==201,response.text
        assert response.json()['invoice']['total']=='118.00'
        replay=client.post('/api/v1/srm/service-checkout',headers=headers,json=payload)
        assert replay.status_code==201 and replay.json()==response.json()
        assert db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==1


def test_counter_creation_enrollment_rolls_back_with_outer_transaction(db,scenario):
    from tests.test_service_checkout import enable_audited_pack,audited_pack_writer
    from app.business_packs.models import PackMasterAvailability
    from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
    user,branch,cat,_=scenario
    context,_,_,_=enable_audited_pack(db,user,branch,cat)
    before=db.query(CRMCompany).count()
    with audited_pack_writer(db,user,branch,context):
        transaction=db.begin_nested()
        result=configure(CashAccountSetup(action='create',label='Rollback counter',jurisdiction_country='IN',reason='Verify atomic canonical enrollment'),db,user,commit=False)
        key=str(result['customer_id'])
        assert db.query(PackMasterAvailability).filter_by(context_id=context.id,resource_table='crm_companies',resource_key=key).count()==1
        transaction.rollback()
    assert db.query(CRMCompany).count()==before
    assert db.query(AnonymousCashAccount).count()==0
    assert db.query(PackMasterAvailability).filter_by(context_id=context.id,resource_table='crm_companies',resource_key=key).count()==0
