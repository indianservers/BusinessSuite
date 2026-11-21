"""Atomic native checkout integration; existing stock and money remain authoritative."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.models.user import User
from app.models.employee import Employee
from app.apps.srm.models import SRMPOSSession,SRMProduct,SRMSalesOrder,SRMInvoice,SRMReceipt,SRMReceiptAllocation,SRMInventoryMovement
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.service_checkout_models import MODELS,POSServiceCheckout,POSCheckoutLine,POSServiceOccurrence,POSCheckoutPayment,ServiceBookingPolicy
from app.apps.srm.service_checkout import checkout,save_policy,save_eligibility
from app.apps.srm.service_checkout_schemas import CheckoutInput,PolicyInput,EligibilityInput
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_business_suite_pos_integrity import catalog
from tests.test_contact_directory import directory_identity
from tests.srm_test_utils import seed_invoice_parties

@pytest.fixture
def scenario(client,db,catalog):
    for model in MODELS:model.__table__.create(db.bind,checkfirst=True)
    seed_invoice_parties(db)
    user=db.query(User).filter_by(email='testadmin@test.com').one();user.organization_id=1
    branch=int(catalog[0]['X-Suite-Branch'])
    with native_writer(db,user,branch):
        employee=Employee(employee_id='CHECKOUT-'+uuid4().hex,first_name='QA',last_name='Specialist',branch_id=branch,status='Active',date_of_joining=datetime.now().date())
        register=SRMPOSSession(organization_id=1,session_number='SERVICE-'+uuid4().hex,created_by=user.id,status='open')
        db.add_all([employee,register]);db.flush()
        provider=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Checkout provider',status='active',request_id=str(uuid4()),created_by=user.id,
            data={'resource_type':'stylist','employee_id':employee.id,'user_id':None,'timezone':'UTC','weekdays':list(range(7)),'opens':'00:00:00','closes':'23:59:00'})
        db.add(provider);db.commit()
        policy=save_policy(PolicyInput(service_product_id=catalog[2][1],default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
        eligibility=save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=employee.id),db,user)
    start=(datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
    def basket(payments=True):
        booking={'policy_id':policy['id'],'expected_policy_revision':policy['revision'],'eligibility_id':eligibility['id'],
            'expected_eligibility_revision':eligibility['revision'],'provider_resource_id':provider.id,'employee_id':employee.id,'starts_at':start,'duration_minutes':30}
        return CheckoutInput.model_validate({'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register.id,
            'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':catalog[2][0],'quantity':1},
                {'client_line_key':str(uuid4()),'line_kind':'booked_service','product_id':catalog[2][1],'booking':booking},
                {'client_line_key':str(uuid4()),'line_kind':'booked_service','product_id':catalog[2][1],'booking':{**booking,'starts_at':start+timedelta(hours=1)}}],
            'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'100'},{'payment_key':str(uuid4()),'method':'card','amount':'50','reference':'terminal receipt'}] if payments else []})
    return user,branch,catalog,basket


def test_checkout_recovery_probe_is_read_only_but_checks_write_authority(db, scenario):
    from app.apps.srm.service_checkout import checkout_capabilities
    user, branch, _, _ = scenario
    before = (db.query(SRMSalesOrder).count(), db.query(SRMInvoice).count(), db.query(SRMReceipt).count())
    with native_writer(db, user, branch):
        db.info['security_write_request'] = False
        try:
            assert checkout_capabilities(db, user) == {'checkout_create': True, 'checkout_collect': True}
        finally:
            db.info.pop('security_write_request', None)
    assert before == (db.query(SRMSalesOrder).count(), db.query(SRMInvoice).count(), db.query(SRMReceipt).count())


def test_mixed_basket_two_occurrences_native_invoice_split_receipts_and_replay(db,scenario):
    user,branch,catalog,basket=scenario;data=basket()
    before=db.query(SRMInventoryMovement).count()
    with native_writer(db,user,branch):
        result=checkout(data,db,user)
        replay=checkout(data,db,user)
    assert result==replay
    assert len(result['lines'])==3 and len({x['invoice_line_id'] for x in result['lines']})==3
    assert len({x['appointment_id'] for x in result['lines'] if x['appointment_id']})==2
    assert Decimal(result['invoice']['total'])==354 and Decimal(result['invoice']['paid'])==150 and Decimal(result['invoice']['balance'])==204
    assert db.query(SRMInventoryMovement).count()==before+1
    assert db.get(SRMProduct,catalog[2][0]).current_quantity==4
    assert db.query(SRMSalesOrder).count()==1 and db.query(SRMInvoice).count()==1
    assert db.query(SRMReceipt).count()==2 and db.query(SRMReceiptAllocation).count()==2
    assert all(x.invoice_id is None for x in db.query(IndustryRecord).filter_by(kind='appointment'))
    from app.apps.project_management.models import PMSTimesheet
    assert db.query(PMSTimesheet).count()==0


def test_second_slot_conflict_is_atomic(db,scenario):
    user,branch,catalog,basket=scenario;data=basket()
    data.lines[2].booking.starts_at=data.lines[1].booking.starts_at
    before=db.query(SRMInventoryMovement).count()
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:checkout(data,db,user)
    assert error.value.status_code==409
    assert db.query(SRMSalesOrder).count()==db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==0
    assert db.query(POSServiceCheckout).count()==db.query(POSServiceOccurrence).count()==0
    assert db.query(SRMInventoryMovement).count()==before


def test_late_native_payment_failure_rolls_back_whole_basket(db,scenario,monkeypatch):
    user,branch,catalog,basket=scenario
    from app.apps.srm.api import router as native
    def abort(*args,**kwargs):raise HTTPException(409,'Allocation changed')
    monkeypatch.setattr(native,'allocate_receipt_operation',abort)
    before=db.query(SRMInventoryMovement).count()
    with native_writer(db,user,branch),pytest.raises(HTTPException):checkout(basket(),db,user)
    assert db.query(SRMSalesOrder).count()==db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==0
    assert db.query(POSServiceCheckout).count()==db.query(POSServiceOccurrence).count()==0
    assert db.query(IndustryRecord).filter_by(kind='appointment').count()==0
    assert db.query(SRMInventoryMovement).count()==before


def test_changed_request_replay_and_stale_policy_denied(db,scenario):
    user,branch,catalog,basket=scenario;data=basket(False)
    with native_writer(db,user,branch):
        checkout(data,db,user)
        data.lines[0].quantity=2
        with pytest.raises(HTTPException) as error:checkout(data,db,user)
        assert error.value.status_code==409
        data=basket(False);data.lines[1].booking.expected_policy_revision+=1
        with pytest.raises(HTTPException) as error:checkout(data,db,user)
        assert error.value.status_code==409
    assert db.query(SRMSalesOrder).count()==1


def test_caller_rollback_removes_all_checkout_sources(db,scenario):
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        with pytest.raises(RuntimeError):
            with db.begin_nested():
                checkout(basket(),db,user,commit=False)
                raise RuntimeError('outer failed')
    assert db.query(SRMSalesOrder).count()==db.query(SRMInvoice).count()==db.query(SRMReceipt).count()==0
    assert db.query(POSCheckoutLine).count()==db.query(POSCheckoutPayment).count()==0

@pytest.mark.parametrize('case',['readonly','inactive','overpay','stock','past','employee'])
def test_validation_fails_before_native_side_effects(db,scenario,case):
    user,branch,catalog,basket=scenario;data=basket()
    with native_writer(db,user,branch):
        if case=='readonly':db.info['security_write_request']=False
        elif case=='inactive':user.is_active=False;db.flush()
        elif case=='overpay':data.payments[0].amount=Decimal(10000)
        elif case=='stock':data.lines[0].quantity=6
        elif case=='past':data.lines[1].booking.starts_at=datetime.now(timezone.utc)-timedelta(days=1)
        elif case=='employee':data.lines[1].booking.employee_id=999999
        with pytest.raises(HTTPException):checkout(data,db,user)
    assert db.query(SRMSalesOrder).count()==0


def test_credit_group_append_payment_revision_idempotency_and_state(db,scenario):
    from app.apps.srm.service_checkout import append_payment,servicecheckout_state
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        group=checkout(basket(False),db,user)
        data=AppendPaymentInput.model_validate({'expected_revision':group['revision'],'payment':{'payment_key':str(uuid4()),'method':'upi','amount':'54','reference':'native receipt'}})
        paid=append_payment(group['id'],data,db,user)
        assert paid['revision']==group['revision']+1 and Decimal(paid['invoice']['balance'])==300
        assert append_payment(group['id'],data,db,user)==paid
        assert servicecheckout_state(db,user,db.info['branch_context'],group['id'])==paid
        data.payment.amount=Decimal('55')
        with pytest.raises(HTTPException) as e:append_payment(group['id'],data,db,user)
        assert e.value.status_code==409
        data.payment.payment_key=uuid4()
        with pytest.raises(HTTPException) as e:append_payment(group['id'],data,db,user)
        assert e.value.status_code==409
    assert db.query(SRMReceipt).count()==1


def enable_pack(db,user,branch,catalog,role='hospital_manager'):
    from app.business_packs.models import PackActivation,PackContext,PackUserGrant,PackMasterAvailability
    activation=PackActivation(company_id=1,pack_key='hospital',pack_version=1,state='active');db.add(activation);db.flush()
    context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key='hospital',pack_version=1,state='active');db.add(context);db.flush()
    grant=PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role=role);db.add(grant)
    provider=db.query(IndustryRecord).filter_by(kind='resource').one()
    register=db.query(SRMPOSSession).one()
    for table,ident in [('srm_products',catalog[2][0]),('srm_products',catalog[2][1]),('srm_industry_records',provider.id),('srm_pos_sessions',register.id)]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    return context,grant,provider,register



from contextlib import contextmanager

@contextmanager
def audited_pack_writer(db,user,branch,context):
    """Actual reviewed operational boundary, in addition to native authorization."""
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    with native_writer(db,user,branch):
        scope=resolve_context(db,user,db.info['branch_context'],context.id)
        cleanup=install(db,scope,policy=native_srm_policy(scope.pack_key).policy)
        try:yield scope
        finally:cleanup()


def enable_audited_pack(db,user,branch,catalog):
    """Enroll only native masters; create private resources through their writer."""
    from app.business_packs.models import PackMasterAvailability
    context,grant,old_provider,old_register=enable_pack(db,user,branch,catalog)
    provider_data=dict(old_provider.data)
    for table,ident in [('srm_industry_records',old_provider.id),('srm_pos_sessions',old_register.id)]:
        row=db.query(PackMasterAvailability).filter_by(context_id=context.id,resource_table=table,resource_key=str(ident)).one()
        db.delete(row)
    # Provider/register availability is not private operational ownership.
    # Replace the legacy fixture objects with genuinely new contextual sources.
    for table,ident in [('employees',provider_data['employee_id']),('crm_companies',101),('srm_warehouses',catalog[1])]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    with audited_pack_writer(db,user,branch,context):
        provider=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Private checkout provider',status='active',request_id=str(uuid4()),created_by=user.id,data=provider_data)
        register=SRMPOSSession(organization_id=1,session_number='PRIVATE-'+uuid4().hex,created_by=user.id,cashier_user_id=user.id,status='open')
        db.add_all([provider,register]);db.commit()
    return context,grant,provider,register

def test_pack_checkout_stamps_native_sources_and_revoked_grant_fails(db,scenario):
    from app.business_packs.models import PackRecordOwnership
    user,branch,catalog,basket=scenario
    context,grant,provider,register=enable_audited_pack(db,user,branch,catalog)
    data=basket();data.pos_session_id=register.id
    with audited_pack_writer(db,user,branch,context):
        from app.business_packs.access import resolve_context
        assert resolve_context(db,user,db.info['branch_context']) is not None, (context.id,context.state,context.branch_id,branch)
        policy=save_policy(PolicyInput(service_product_id=catalog[2][1],default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
        eligibility=save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=provider.data['employee_id']),db,user)
        for line in data.lines:
            if line.booking:
                line.booking.provider_resource_id=provider.id
                line.booking.policy_id=policy['id'];line.booking.expected_policy_revision=policy['revision']
                line.booking.eligibility_id=eligibility['id'];line.booking.expected_eligibility_revision=eligibility['revision']
        result=checkout(data,db,user)
        from sqlalchemy import select
        anchors=db.connection().execute(select(PackRecordOwnership).where(PackRecordOwnership.context_id==context.id)).mappings().all()
        assert {'srm_sales_orders','srm_invoices','srm_sales_order_lines','srm_invoice_lines','srm_receipts','srm_pos_service_occurrences'}<={a.resource_table for a in anchors}
    grant.active=False;db.commit()
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:checkout(data,db,user)
    assert error.value.status_code==403
    assert db.query(SRMSalesOrder).count()==1

@pytest.mark.parametrize('role',['doctor','cashier'])
def test_pack_role_never_inherits_native_superuser_checkout_power(db,scenario,role):
    user,branch,catalog,basket=scenario;enable_pack(db,user,branch,catalog,role)
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:checkout(basket(),db,user)
    assert error.value.status_code==403 and db.query(SRMSalesOrder).count()==0

@pytest.mark.parametrize('permissions',[['srm_manage'],['srm_manage','srm_invoice_create'],['srm_manage','srm_invoice_create','srm_invoice_approve']])
def test_native_permission_intersection_is_mandatory(db,scenario,permissions):
    from tests.test_settings_hub import actor
    user,branch,catalog,basket=scenario
    _,limited=actor(db,role='srm_sales_manager',permissions=permissions,admin=True);limited.organization_id=1
    with native_writer(db,limited,branch),pytest.raises(HTTPException) as error:checkout(basket(),db,limited)
    assert error.value.status_code==403 and db.query(SRMSalesOrder).count()==0

@pytest.mark.parametrize('pointer',['invoice','receipt','invoice_line'])
def test_group_read_rejects_trusted_core_corrupted_native_pointers(db,scenario,pointer):
    from sqlalchemy import update
    from app.apps.srm.service_checkout import servicecheckout_state
    from app.apps.srm.models import SRMInvoiceLine
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        group=checkout(basket(),db,user)
        if pointer=='invoice':
            db.connection().execute(update(SRMInvoice.__table__).where(SRMInvoice.id==group['invoice']['id']).values(customer_id=None))
        elif pointer=='receipt':
            db.connection().execute(update(SRMReceipt.__table__).where(SRMReceipt.id==group['receipts'][0]['id']).values(currency='USD'))
        else:
            db.connection().execute(update(SRMInvoiceLine.__table__).where(SRMInvoiceLine.id==group['lines'][0]['invoice_line_id']).values(source_id=999999))
        db.expire_all()
        with pytest.raises(HTTPException) as error:servicecheckout_state(db,user,db.info['branch_context'],group['id'])
        assert error.value.status_code in {403,409}


def test_new_http_router_rejects_invalid_pack_selector_and_client_source_stamps(client,db,scenario):
    from app.apps.srm.service_checkout_api import router
    user,branch,catalog,basket=scenario
    before=list(client.app.router.routes)
    client.app.include_router(router,prefix='/api/v1')
    try:
        response=client.post('/api/v1/srm/service-checkout',headers={**catalog[0],'X-Suite-Pack-Context':'not-an-id'},json=basket().model_dump(mode='json'))
        assert response.status_code==403,response.text
        response=client.post('/api/v1/srm/service-checkout',headers=catalog[0],json={**basket().model_dump(mode='json'),'pack_context_id':100})
        assert response.status_code==422,response.text
        assert db.query(SRMSalesOrder).count()==0
    finally:client.app.router.routes[:]=before


def test_pack_foreign_provider_cannot_be_adopted_as_specialist(db,scenario):
    from app.business_packs.models import PackActivation,PackContext,PackRecordOwnership
    user,branch,catalog,basket=scenario
    context,grant,provider,register=enable_pack(db,user,branch,catalog)
    other=PackActivation(company_id=1,pack_key='restaurant',pack_version=1,state='active');db.add(other);db.flush()
    foreign=PackContext(company_id=1,branch_id=branch,activation_id=other.id,pack_key='restaurant',pack_version=1,state='active');db.add(foreign);db.flush()
    db.add(PackRecordOwnership(company_id=1,branch_id=branch,context_id=foreign.id,resource_table='srm_industry_records',resource_key=str(provider.id),source='created'));db.commit()
    with audited_pack_writer(db,user,branch,context):
        policy=save_policy(PolicyInput(service_product_id=catalog[2][1],default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
        with pytest.raises(HTTPException) as error:
            save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=provider.data['employee_id']),db,user)
        assert error.value.status_code==403
    assert db.query(SRMSalesOrder).count()==0


def test_schema_incomplete_fails_before_checkout_write(db,scenario,monkeypatch):
    import app.apps.srm.service_checkout as service
    user,branch,catalog,basket=scenario
    monkeypatch.setattr(service,'installation_ready',lambda db:False)
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:checkout(basket(),db,user)
    assert error.value.status_code==503 and db.query(SRMSalesOrder).count()==0


def test_append_late_failure_preserves_balance_revision_and_receipts(db,scenario,monkeypatch):
    from app.apps.srm.service_checkout import append_payment
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    from app.apps.srm.api import router as native
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        group=checkout(basket(False),db,user)
        def abort(*args,**kwargs):raise HTTPException(409,'Allocation changed')
        monkeypatch.setattr(native,'allocate_receipt_operation',abort)
        data=AppendPaymentInput.model_validate({'expected_revision':group['revision'],'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'50'}})
        with pytest.raises(HTTPException):append_payment(group['id'],data,db,user)
    assert db.query(SRMReceipt).count()==0
    assert db.get(POSServiceCheckout,group['id']).revision==group['revision']
    assert db.get(SRMInvoice,group['invoice']['id']).balance_amount==Decimal(group['invoice']['balance'])


def test_catalog_rate_line_and_bill_discounts_note_and_followup_preserved(db,scenario):
    from app.apps.srm.service_checkout_schemas import CheckoutFollowUp
    from app.apps.srm.models import SRMSalesOrderLine
    from app.shared.follow_ups import FollowUp
    user,branch,catalog,basket=scenario;data=basket()
    data.lines[0].discount_amount=Decimal('10')
    data.lines[0].note='Keep the existing cart instruction'
    data.lines[0].follow_up=CheckoutFollowUp.model_validate({'required':True,'type':'days','reference':'completion','interval_days':45,'notes':'Call for service check'})
    data.bill_discount_amount=Decimal('20')
    with native_writer(db,user,branch):result=checkout(data,db,user)
    assert Decimal(result['invoice']['total'])==Decimal('318.60')
    assert sum(Decimal(line['discount']) for line in result['lines'])==30
    native=db.get(SRMSalesOrderLine,db.get(POSCheckoutLine,result['lines'][0]['id']).sales_order_line_id)
    assert native.unit_price==100 and native.metadata_json['note']==data.lines[0].note
    assert native.metadata_json['follow_up']['notes']=='Call for service check'
    row=db.query(FollowUp).one()
    assert row.order_line_id==native.id and row.configuration['reference']=='completion'


def test_authorized_pack_operator_cannot_override_catalog_price(db, scenario):
    user, branch, catalog, basket = scenario
    context, _, _, register = enable_audited_pack(db, user, branch, catalog)
    data = basket(False)
    data.pos_session_id = register.id
    data.lines = [data.lines[0]]
    data.lines[0].unit_price = Decimal('90')
    with audited_pack_writer(db, user, branch, context), pytest.raises(HTTPException) as error:
        checkout(data, db, user)
    assert error.value.status_code == 409
    assert 'POS price changed' in error.value.detail
    assert db.query(SRMSalesOrder).count() == 0


def test_unknown_followup_fields_and_untrusted_tax_are_rejected():
    from pydantic import ValidationError
    from app.apps.srm.service_checkout_schemas import CheckoutFollowUp,CheckoutLineInput
    with pytest.raises(ValidationError):CheckoutFollowUp.model_validate({'required':True,'unexpected_source_id':1})
    with pytest.raises(ValidationError):CheckoutLineInput.model_validate({'client_line_key':str(uuid4()),'line_kind':'product','product_id':1,'tax_amount':'0'})


def test_quote_total_mismatch_retains_cart_without_native_effects(db,scenario):
    user,branch,catalog,basket=scenario;data=basket();data.expected_total=Decimal('1')
    with native_writer(db,user,branch),pytest.raises(HTTPException) as error:checkout(data,db,user)
    assert error.value.status_code==409
    assert db.query(SRMSalesOrder).count()==db.query(POSServiceCheckout).count()==0
    assert db.get(SRMProduct,catalog[2][0]).current_quantity==5


def test_later_cash_uses_actual_new_register_and_replay_keeps_original_collection(db,scenario):
    from app.apps.srm.service_checkout import append_payment
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        group=checkout(basket(False),db,user)
        original=db.query(SRMPOSSession).one();original.status='closed';db.flush()
        current=SRMPOSSession(organization_id=1,session_number='CURRENT-'+uuid4().hex,status='open',cashier_user_id=user.id,created_by=user.id)
        db.add(current);db.commit()
        data=AppendPaymentInput.model_validate({'expected_revision':group['revision'],'pos_session_id':current.id,'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'50'}})
        result=append_payment(group['id'],data,db,user)
        assert result['receipts'][0]['collection_session_id']==current.id!=original.id
        current.status='closed';db.commit()
        assert append_payment(group['id'],data,db,user)==result
        data.pos_session_id=original.id
        with pytest.raises(HTTPException) as error:append_payment(group['id'],data,db,user)
        assert error.value.status_code==409

@pytest.mark.parametrize('method',['cash','card'])
def test_no_open_register_cash_denied_noncash_unbound(db,scenario,method):
    from app.apps.srm.service_checkout import append_payment
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        group=checkout(basket(False),db,user)
        original=db.query(SRMPOSSession).one();original.status='closed';db.commit()
        data=AppendPaymentInput.model_validate({'expected_revision':group['revision'],'payment':{'payment_key':str(uuid4()),'method':method,'amount':'50'}})
        if method=='cash':
            with pytest.raises(HTTPException) as error:append_payment(group['id'],data,db,user)
            assert error.value.status_code==409 and db.query(SRMReceipt).count()==0
        else:
            result=append_payment(group['id'],data,db,user)
            assert result['receipts'][0]['collection_session_id'] is None


def test_multiple_open_registers_require_explicit_selection(db,scenario):
    from app.apps.srm.service_checkout import append_payment
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    user,branch,catalog,basket=scenario
    with native_writer(db,user,branch):
        group=checkout(basket(False),db,user)
        extra=SRMPOSSession(organization_id=1,session_number='EXTRA-'+uuid4().hex,status='open',cashier_user_id=user.id,created_by=user.id)
        db.add(extra);db.commit()
        data=AppendPaymentInput.model_validate({'expected_revision':group['revision'],'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'50'}})
        with pytest.raises(HTTPException) as error:append_payment(group['id'],data,db,user)
        assert error.value.status_code==409 and db.query(SRMReceipt).count()==0
        data.pos_session_id=extra.id
        assert append_payment(group['id'],data,db,user)['receipts'][0]['collection_session_id']==extra.id


def test_checkout_reserves_optional_room_and_rejects_conflicting_reuse(db, scenario):
    user, branch, _, basket = scenario
    with native_writer(db, user, branch):
        room = IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title='Treatment room',
            status='active', request_id=str(uuid4()), created_by=user.id,
            data={'resource_type': 'room', 'timezone': 'UTC', 'weekdays': list(range(7)), 'opens': '00:00:00', 'closes': '23:59:00'})
        db.add(room); db.commit()
        data = basket(False)
        data.lines[1].booking.additional_resource_ids = [room.id]
        result = checkout(data, db, user)
        appointment = db.get(IndustryRecord, result['lines'][1]['appointment_id'])
        assert room.id in appointment.data['resource_ids']
        # A different employee must still be blocked by the room reservation.
        employee = Employee(employee_id='ROOM-QA-' + uuid4().hex, first_name='Other', last_name='Employee',
            branch_id=branch, status='Active', date_of_joining=datetime.now().date())
        db.add(employee); db.flush()
        provider = IndustryRecord(organization_id=1, branch_id=branch, kind='resource', title='Other provider',
            status='active', request_id=str(uuid4()), created_by=user.id,
            data={'resource_type':'employee', 'employee_id':employee.id, 'timezone':'UTC',
                'weekdays':list(range(7)), 'opens':'00:00:00', 'closes':'23:59:00'})
        db.add(provider); db.commit()
        eligibility = save_eligibility(EligibilityInput(policy_id=data.lines[1].booking.policy_id,
            expected_policy_revision=data.lines[1].booking.expected_policy_revision,
            provider_resource_id=provider.id, employee_id=employee.id), db, user)
        retry = basket(False)
        retry.lines = [retry.lines[1]]
        retry.lines[0].booking.provider_resource_id = provider.id
        retry.lines[0].booking.employee_id = employee.id
        retry.lines[0].booking.eligibility_id = eligibility['id']
        retry.lines[0].booking.expected_eligibility_revision = eligibility['revision']
        retry.lines[0].booking.additional_resource_ids = [room.id]
        with pytest.raises(HTTPException) as conflict:
            checkout(retry, db, user)
        assert conflict.value.status_code == 409
