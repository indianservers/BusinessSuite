"""Real native service checkout under the additive pack graph boundary."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from sqlalchemy import event,inspect,select
import pytest
from app.apps.srm.service_checkout import checkout,save_policy,save_eligibility
from app.apps.srm.service_checkout_schemas import CheckoutInput,PolicyInput,EligibilityInput
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMPOSSession
from app.business_packs.models import PackActivation,PackContext,PackUserGrant,PackMasterAvailability
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy,MASTER_TABLES,RECORD_TABLES
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def test_policy_is_current_manifest_and_private_resources_never_masters():
    from app.business_packs.registry import list_packs
    for pack in list_packs():
        definition=native_srm_policy(pack.key)
        assert definition.declared_workflows==frozenset(w.key for w in pack.workflows)
        assert not definition.runtime_ready
    assert MASTER_TABLES=={'employees','crm_companies','srm_products','srm_warehouses'}
    assert {'srm_industry_records','srm_pos_sessions','srm_invoices','srm_receipts'}<=RECORD_TABLES
    assert not MASTER_TABLES & RECORD_TABLES


@pytest.mark.parametrize("native_superuser",[True,False])
def test_actual_hospital_manager_checkout_creates_anchored_native_graph(db,scenario,native_superuser):
    user,branch,catalog,basket=scenario
    if not native_superuser:
        from tests.test_settings_hub import actor
        from app.access.models import AccessPolicy
        from app.branches.models import BranchGrant
        _,user=actor(db,role='srm_admin',permissions=['srm_admin','employee_view'],admin=False);user.organization_id=1
        db.add(BranchGrant(company_id=1,branch_id=branch,user_id=user.id,can_write=True))
        db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={
            'srm':{'enabled':True,'permissions':['srm_admin'],'actions':['view','create','edit','approve'],'scope':'organization'},
            'hrms':{'enabled':True,'permissions':['employee_view'],'actions':['view'],'scope':'organization'}}));db.commit()
    original=basket(False);old_provider=db.query(IndustryRecord).filter_by(kind='resource').one()
    activation=PackActivation(company_id=1,pack_key='hospital',pack_version=1,state='active');db.add(activation);db.flush()
    context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key='hospital',pack_version=1,state='active');db.add(context);db.flush()
    db.add(PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role='hospital_manager'))
    employee_id=old_provider.data['employee_id']
    for table,ident in [('employees',employee_id),('crm_companies',101),('srm_products',catalog[2][1])]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    provider_data={**old_provider.data,'resource_type':'doctor'}
    with native_writer(db,user,branch):
        scope=resolve_context(db,user,db.info['branch_context'],context.id)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            provider=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Owned hospital provider',status='active',request_id=str(uuid4()),created_by=user.id,data=provider_data)
            register=SRMPOSSession(organization_id=1,session_number='PACK-'+uuid4().hex,status='open',cashier_user_id=user.id,created_by=user.id)
            db.add_all([provider,register]);db.commit()
            policy=save_policy(PolicyInput(service_product_id=catalog[2][1],default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
            eligibility=save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=employee_id),db,user)
            start=(datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0)
            data=CheckoutInput.model_validate({'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register.id,
                'lines':[{'client_line_key':str(uuid4()),'line_kind':'booked_service','product_id':catalog[2][1],
                    'booking':{'policy_id':policy['id'],'expected_policy_revision':policy['revision'],'eligibility_id':eligibility['id'],
                        'expected_eligibility_revision':eligibility['revision'],'provider_resource_id':provider.id,'employee_id':employee_id,
                        'starts_at':start,'duration_minutes':30}}],
                'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]})
            flushes=[]
            def capture(session,*args):
                flushes.append(sorted({inspect(item).mapper.local_table.name for item in session.new|session.dirty|session.deleted}))
                for item in session.new:
                    if inspect(item).mapper.local_table.name=='email_outbox':
                        source=getattr(item,'_suite_source_record',None);state=inspect(source,raiseerr=False)
                        flushes.append({'email_source':None if state is None else (state.mapper.local_table.name,state.identity,state.persistent,[name for name in ('id','organization_id','company_id','branch_id') if name in state.attrs and state.attrs[name].history.has_changes()])})
            event.listen(db,'before_flush',capture,insert=True)
            try:
                try:result=checkout(data,db,user)
                except Exception as error:raise AssertionError(f'Native graph flushes: {flushes}') from error
            finally:event.remove(db,'before_flush',capture)
            assert result['invoice']['balance']=='0.00' and result['lines'][0]['appointment_id']
            assert checkout(data,db,user)==result
            from app.business_packs.models import PackRecordOwnership
            # Trusted test audit bypasses operational loaders, proving actual persisted anchors.
            anchors=db.connection().execute(select(PackRecordOwnership.__table__).where(PackRecordOwnership.context_id==context.id)).mappings().all()
            assert all((row['company_id'],row['branch_id'],row['context_id'])==(1,branch,context.id) for row in anchors)
            assert {'srm_sales_orders','srm_sales_order_lines','srm_invoice_drafts','srm_invoices','srm_invoice_lines',
                'srm_receipts','srm_receipt_allocations','business_invoice_contexts',
                'srm_pos_service_checkouts','srm_pos_checkout_lines','srm_pos_service_occurrences','srm_pos_checkout_payments',
                'communication_customer_events','email_outbox'} <= {row['resource_table'] for row in anchors}
        finally:cleanup()



def test_private_providers_registers_ignore_availability_and_chef_cannot_cross_context(db,scenario):
    from app.business_packs.models import PackRecordOwnership
    from fastapi import HTTPException
    user,branch,catalog,basket=scenario
    old_provider=db.query(IndustryRecord).filter_by(kind='resource').one();old_id=old_provider.id
    old_register=db.query(SRMPOSSession).one();old_register_id=old_register.id
    data=dict(old_provider.data)
    contexts={}
    for key,role in [('hospital','hospital_manager'),('restaurant','chef')]:
        activation=PackActivation(company_id=1,pack_key=key,pack_version=1,state='active');db.add(activation);db.flush()
        context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key=key,pack_version=1,state='active');db.add(context);db.flush();contexts[key]=context.id
        db.add(PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role=role))
        # Even explicit availability of a PRIVATE kind must never make it a master.
        for table,ident in [('srm_industry_records',old_id),('srm_pos_sessions',old_register_id),('employees',data['employee_id'])]:
            db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    denial_data=basket()
    with native_writer(db,user,branch):
        scope=resolve_context(db,user,db.info['branch_context'],contexts['hospital']);cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            assert db.get(IndustryRecord,old_id) is None and db.get(SRMPOSSession,old_register_id) is None
            owned=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Strict private doctor',status='active',request_id=str(uuid4()),created_by=user.id,data=data)
            db.add(owned);db.commit();owned_id=owned.id
            assert db.get(IndustryRecord,owned_id) is owned
        finally:cleanup()
        chef=resolve_context(db,user,db.info['branch_context'],contexts['restaurant']);cleanup=install(db,chef,policy=native_srm_policy('restaurant').policy)
        try:
            assert db.get(IndustryRecord,owned_id) is None
            assert db.query(IndustryRecord).filter_by(id=owned_id).count()==0
            with pytest.raises(HTTPException) as error:checkout(denial_data,db,user)
            assert error.value.status_code==403
        finally:cleanup()


def test_doctor_pack_capabilities_do_not_inherit_native_finance_admin(db,scenario):
    from fastapi import HTTPException
    user,branch,catalog,basket=scenario
    activation=PackActivation(company_id=1,pack_key='hospital',pack_version=1,state='active');db.add(activation);db.flush()
    context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key='hospital',pack_version=1,state='active');db.add(context);db.flush()
    db.add(PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role='doctor'));db.commit()
    denial_data=basket()
    with native_writer(db,user,branch):
        scope=resolve_context(db,user,db.info['branch_context'],context.id);cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            with pytest.raises(HTTPException) as error:checkout(denial_data,db,user)
            assert error.value.status_code==403
        finally:cleanup()


@pytest.mark.parametrize('native_actions', [['view'], ['view', 'create']])
def test_pack_manager_cannot_override_native_financial_permission_ceiling(db,scenario,native_actions):
    from fastapi import HTTPException
    from tests.test_settings_hub import actor
    from app.access.models import AccessPolicy
    from app.branches.models import BranchGrant
    _,branch,_,basket=scenario
    data=basket()
    _,user=actor(db,role='srm_admin',permissions=['srm_admin'],admin=False);user.organization_id=1
    db.add(BranchGrant(company_id=1,branch_id=branch,user_id=user.id,can_write=True))
    db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={'srm':{'enabled':True,'permissions':['srm_admin'],'actions':native_actions,'scope':'organization'}}))
    activation=PackActivation(company_id=1,pack_key='hospital',pack_version=1,state='active');db.add(activation);db.flush()
    context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key='hospital',pack_version=1,state='active');db.add(context);db.flush()
    db.add(PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role='hospital_manager'));db.commit()
    with pytest.raises(HTTPException) as error:
        with native_writer(db,user,branch):
            scope=resolve_context(db,user,db.info['branch_context'],context.id)
            cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
            try:checkout(data,db,user)
            finally:cleanup()
    assert error.value.status_code==403
