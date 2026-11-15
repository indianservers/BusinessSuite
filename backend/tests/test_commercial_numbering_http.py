"""Real company numbering across two private contexts and an unconfigured branch."""
from copy import deepcopy
from uuid import uuid4
from sqlalchemy import select,func
from tests.test_business_pack_http_integration import hospital_http,scenario,catalog,directory_identity,create,native_actor,grant
from app.business_packs.models import PackMasterAvailability
from app.apps.srm.models import SRMPOSSession,SRMSalesOrder,SRMReceipt
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_srm_native_transaction_operations import native_writer


def test_real_http_company_numbers_across_two_pack_contexts_and_legacy_branch(client,db,hospital_http):
    headers,actor,branch,context_id,_,payload=hospital_http
    first=create(client,headers,payload)
    retail,_=grant(db,actor,branch,'retail','store_manager')
    for table,ident in [('crm_companies',101),('srm_products',payload['lines'][0]['product_id'])]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=retail.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],retail.id)
        cleanup=install(db,scope,policy=native_srm_policy('retail').policy)
        try:
            register=SRMPOSSession(organization_id=1,session_number='NUMBER-'+uuid4().hex,status='open',cashier_user_id=actor.id,created_by=actor.id)
            db.add(register);db.commit();register_id=register.id
        finally:cleanup()
    second_payload=deepcopy(payload);second_payload.update(request_id=str(uuid4()),pos_session_id=register_id)
    second_payload['lines'][0].pop('booking');second_payload['lines'][0].update(client_line_key=str(uuid4()),line_kind='unscheduled_service')
    second_payload['payments'][0]['payment_key']=str(uuid4())
    retail_headers={**headers,'X-Suite-Pack-Context':str(retail.id)}
    second=create(client,retail_headers,second_payload)
    assert first['sales_order_id']!=second['sales_order_id']
    assert first['receipts'][0]['number']!=second['receipts'][0]['number']
    assert create(client,retail_headers,second_payload)==second
    for own_headers,own,other in [(headers,first,second),(retail_headers,second,first)]:
        response=client.get('/api/v1/srm/receipts/'+str(own['receipts'][0]['id']),headers=own_headers)
        assert response.status_code==200,response.text
        response=client.get('/api/v1/srm/receipts/'+str(other['receipts'][0]['id']),headers=own_headers)
        assert response.status_code==404,response.text
    from app.models.company import Branch
    from app.branches.models import BranchRecordShare
    legacy_branch=Branch(company_id=1,name='Numbering legacy branch',code='NUM-'+uuid4().hex[:8]);db.add(legacy_branch);db.commit()
    legacy_headers,legacy_actor=native_actor(db,legacy_branch.id,admin=True)
    db.add(BranchRecordShare(company_id=1,resource_table='crm_companies',resource_key='101',branch_id=legacy_branch.id));db.commit()
    with native_writer(db,legacy_actor,legacy_branch.id):
        from app.apps.srm.models import SRMProduct
        from app.shared.catalog_branches import set_availability
        # Native offering availability remains mandatory in an unconfigured
        # branch; sharing a pack master is not a substitute for this setting.
        product=db.get(SRMProduct,payload['lines'][0]['product_id'])
        set_availability(product,legacy_branch.id,True)
        register=SRMPOSSession(organization_id=1,session_number='LEG-NUM-'+uuid4().hex,status='open',cashier_user_id=legacy_actor.id,created_by=legacy_actor.id)
        db.add(register);db.commit();register_id=register.id
    legacy_payload=deepcopy(second_payload);legacy_payload.update(request_id=str(uuid4()),pos_session_id=register_id)
    legacy_payload['lines'][0]['client_line_key']=str(uuid4());legacy_payload['payments'][0]['payment_key']=str(uuid4())
    legacy=create(client,legacy_headers,legacy_payload)
    from app.business_packs.models import PackContext
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    assert db.connection().scalar(select(func.count()).select_from(PackContext.__table__).where(PackContext.branch_id==legacy_branch.id))==0
    assert db.connection().scalar(select(POSServiceCheckout.pack_context_id).where(POSServiceCheckout.id==legacy['id'])) is None
    assert len({item['receipts'][0]['number'] for item in (first,second,legacy)})==3
    order_table=SRMSalesOrder.__table__
    numbers=db.connection().execute(select(order_table.c.order_number).where(order_table.c.id.in_([first['sales_order_id'],second['sales_order_id'],legacy['sales_order_id']]))).scalars().all()
    assert sorted(numbers)==['SO-000001','SO-000002','SO-000003']
    assert [item['receipts'][0]['number'] for item in (first,second,legacy)]==['RCT-000001','RCT-000002','RCT-000003']
    assert all(number.startswith('SO-') for number in numbers)
    assert create(client,legacy_headers,legacy_payload)==legacy
    for private in (first,second):
        response=client.get('/api/v1/srm/receipts/'+str(private['receipts'][0]['id']),headers=legacy_headers)
        assert response.status_code==404,response.text


def test_number_allocator_does_not_promote_native_permissions_from_pack_role(client,db,hospital_http):
    from app.access.models import AccessPolicy
    headers,actor,_,_,_,payload=hospital_http
    policy=db.query(AccessPolicy).filter_by(user_id=actor.id,company_id=1).one()
    policy.grants={'srm':{'enabled':True,'permissions':['srm_view'],'actions':['view'],'scope':'organization'}};db.commit()
    response=client.post('/api/v1/srm/service-checkout',headers=headers,json=payload)
    assert response.status_code==403,response.text
    assert db.connection().scalar(select(func.count()).select_from(SRMSalesOrder.__table__))==0
    assert db.connection().scalar(select(func.count()).select_from(SRMReceipt.__table__))==0
