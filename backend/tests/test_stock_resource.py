"""Actual selected-pack sale stock uses canonical resources, private movements."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBalance,SRMInventoryMovement,SRMPOSSession,SRMSalesOrder,SRMInvoice,SRMReceipt
from app.apps.srm.service_checkout import checkout
from app.apps.srm.service_checkout_schemas import CheckoutInput
from app.business_packs.models import PackMasterAvailability,PackRecordOwnership
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_business_pack_http_integration import native_actor,grant,create
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer


def raw_count(db,model):return db.connection().scalar(select(func.count()).select_from(model.__table__))


def quantity(db,product,warehouse):
    return db.connection().scalar(select(SRMInventoryBalance.quantity).where(SRMInventoryBalance.product_id==product,SRMInventoryBalance.warehouse_id==warehouse,SRMInventoryBalance.organization_id==1))


@pytest.fixture
def stock(client,db,scenario):
    legacy_actor,branch,catalog,_=scenario
    product,service=catalog[2][:2];warehouse=catalog[1]
    register=db.query(SRMPOSSession).one()
    legacy_payload={'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register.id,
        'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':product,'quantity':'1'}],
        'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]}
    # Genuine legacy before enabling fixture contexts uses the very same native
    # balance later shared by both contexts. No manufactured legacy fallback.
    legacy=create(client,catalog[0],legacy_payload)
    assert quantity(db,product,warehouse)==4
    headers,actor=native_actor(db,branch)
    contexts={};sessions={}
    for key,role in [('hospital','hospital_manager'),('retail','store_manager')]:
        context,_=grant(db,actor,branch,key,role);contexts[key]=context.id
        for table,ident in [('crm_companies',101),('srm_products',product),('srm_products',service),('srm_warehouses',warehouse)]:
            db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
        db.commit()
        with native_writer(db,actor,branch):
            scope=resolve_context(db,actor,db.info['branch_context'],context.id)
            cleanup=install(db,scope,policy=native_srm_policy(key).policy)
            try:
                register=SRMPOSSession(organization_id=1,session_number='STOCK-'+uuid4().hex,status='open',cashier_user_id=actor.id,created_by=actor.id)
                db.add(register);db.commit();sessions[key]=register.id
            finally:cleanup()
    def payload(key='hospital',qty='1',mixed=True,payment='100'):
        lines=[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':product,'quantity':qty}]
        if mixed:lines.append({'client_line_key':str(uuid4()),'line_kind':'unscheduled_service','product_id':service})
        return {'request_id':str(uuid4()),'customer_id':101,'pos_session_id':sessions[key],'lines':lines,
            'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':payment}] if payment else []}
    return SimpleNamespace(actor=actor,branch=branch,product=product,service=service,warehouse=warehouse,contexts=contexts,
        headers=lambda key='hospital':{**headers,'X-Suite-Pack-Context':str(contexts[key])},payload=payload,legacy=legacy)


def test_actual_http_legacy_then_two_pack_mixed_sales_share_one_balance_but_private_history(client,db,stock):
    s=stock;first_payload=s.payload();second_payload=s.payload('retail',payment='50')
    first=create(client,s.headers(),first_payload);second=create(client,s.headers('retail'),second_payload)
    assert first['invoice']['total']=='236.00' and first['invoice']['paid']=='100.00' and first['invoice']['balance']=='136.00'
    assert second['invoice']['paid']=='50.00' and second['invoice']['balance']=='186.00'
    assert create(client,s.headers(),first_payload)==first
    assert create(client,s.headers('retail'),second_payload)==second
    assert quantity(db,s.product,s.warehouse)==2
    assert db.connection().scalar(select(SRMProduct.current_quantity).where(SRMProduct.id==s.product))==2
    assert db.connection().scalar(select(func.count()).select_from(SRMInventoryBalance.__table__).where(SRMInventoryBalance.product_id==s.product,SRMInventoryBalance.warehouse_id==s.warehouse))==1
    anchors=PackRecordOwnership.__table__
    assert db.connection().scalar(select(func.count()).select_from(anchors).where(anchors.c.resource_table.in_(['srm_inventory_balances','srm_products'])))==0
    for key in ('hospital','retail'):
        with native_writer(db,s.actor,s.branch):
            scope=resolve_context(db,s.actor,db.info['branch_context'],s.contexts[key]);cleanup=install(db,scope,policy=native_srm_policy(key).policy)
            try:
                movements=db.query(SRMInventoryMovement).all()
                assert len(movements)==1 and movements[0].quantity_out==1
                with pytest.raises(HTTPException) as error:db.query(SRMInventoryBalance).all()
                assert error.value.status_code==403
                movement=movements[0];movement.notes='Forbidden history rewrite'
                with pytest.raises(HTTPException):db.flush()
                db.rollback()
                product=db.get(SRMProduct,s.product);product.sales_rate=1
                with pytest.raises(HTTPException):db.flush()
                db.rollback()
            finally:cleanup()
    assert quantity(db,s.product,s.warehouse)==2
    assert client.get('/api/v1/srm/invoices/'+str(first['invoice']['id']),headers=s.headers('retail')).status_code==404
    response=client.get('/api/v1/srm/inventory/reports/stock-aging',headers=s.headers('retail'))
    assert response.status_code==503  # Stock-history adapter is not released.


@pytest.mark.parametrize('fault',['insufficient','duplicate_demand','warehouse_unenrolled','product_unenrolled','foreign_warehouse','tracked'])
def test_stock_preflight_denies_unsafe_resources_without_any_committed_effect(client,db,stock,fault):
    s=stock;data=s.payload(mixed=False,payment='')
    if fault=='insufficient':data['lines'][0]['quantity']='5'
    elif fault=='duplicate_demand':
        data['lines'][0]['quantity']='3';data['lines'].append({**data['lines'][0],'client_line_key':str(uuid4())})
    elif fault in ('warehouse_unenrolled','product_unenrolled'):
        table='srm_warehouses' if fault=='warehouse_unenrolled' else 'srm_products';ident=s.warehouse if fault=='warehouse_unenrolled' else s.product
        row=db.query(PackMasterAvailability).filter_by(context_id=s.contexts['hospital'],resource_table=table,resource_key=str(ident)).one();row.active=False;db.commit()
    elif fault=='foreign_warehouse':
        from app.models.company import Company
        if not db.get(Company,2):db.add(Company(id=2,name='Foreign stock company'));db.flush()
        row=SRMWarehouse(organization_id=2,warehouse_code='FOREIGN',warehouse_name='Secret foreign warehouse');db.add(row);db.commit();data['lines'][0]['warehouse_id']=row.id
    else:db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id==s.product).values(batch_tracking=True));db.commit()
    before=tuple(raw_count(db,m) for m in (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement))
    response=client.post('/api/v1/srm/service-checkout',headers=s.headers(),json=data)
    assert response.status_code in (403,404,409),response.text
    assert 'Secret foreign warehouse' not in response.text
    assert tuple(raw_count(db,m) for m in (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement))==before
    assert quantity(db,s.product,s.warehouse)==4


def test_stock_late_native_payment_failure_restores_canonical_resources(client,db,stock,monkeypatch):
    from app.apps.srm.api import router as native
    s=stock;before=tuple(raw_count(db,m) for m in (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement))
    original=native.allocate_receipt_operation
    def denied(*args,**kwargs):raise HTTPException(409,'Late native allocation conflict')
    monkeypatch.setattr(native,'allocate_receipt_operation',denied)
    response=client.post('/api/v1/srm/service-checkout',headers=s.headers(),json=s.payload())
    assert response.status_code==409,response.text
    assert quantity(db,s.product,s.warehouse)==4
    assert tuple(raw_count(db,m) for m in (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement))==before
    monkeypatch.setattr(native,'allocate_receipt_operation',original)


def test_stock_caller_outer_rollback_restores_canonical_resources(client,db,stock):
    s=stock;before=tuple(raw_count(db,m) for m in (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement))
    with native_writer(db,s.actor,s.branch):
        scope=resolve_context(db,s.actor,db.info['branch_context'],s.contexts['hospital']);cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            checkout(CheckoutInput.model_validate(s.payload()),db,s.actor,commit=False)
            assert quantity(db,s.product,s.warehouse)==3
            db.rollback()
            assert quantity(db,s.product,s.warehouse)==4
        finally:cleanup()
    assert tuple(raw_count(db,m) for m in (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement))==before


@pytest.mark.parametrize('attempt',['dirty','bulk','orm_update','delete'])
def test_existing_shared_master_mutations_stay_denied_in_pack_operation(db,stock,attempt):
    from sqlalchemy import update
    s=stock
    with native_writer(db,s.actor,s.branch):
        scope=resolve_context(db,s.actor,db.info['branch_context'],s.contexts['hospital']);cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            with pytest.raises(HTTPException):
                if attempt=='bulk':db.bulk_update_mappings(SRMProduct,[{'id':s.product,'sales_rate':1}])
                elif attempt=='orm_update':db.execute(update(SRMProduct).where(SRMProduct.id==s.product).values(sales_rate=1))
                else:
                    product=db.get(SRMProduct,s.product)
                    if attempt=='delete':db.delete(product)
                    else:product.sales_rate=1
                    db.flush()
            db.rollback()
        finally:cleanup()
    assert db.connection().scalar(select(SRMProduct.sales_rate).where(SRMProduct.id==s.product))==100


@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef')])
def test_stock_checkout_does_not_promote_doctor_or_chef_with_broad_native_rights(client,db,stock,pack,role):
    s=stock;headers,actor=native_actor(db,s.branch)
    from app.business_packs.models import PackContext
    existing=db.get(PackContext,s.contexts['hospital']) if pack=='hospital' else None
    context,_=grant(db,actor,s.branch,pack,role,existing)
    with native_writer(db,actor,s.branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context.id);cleanup=install(db,scope,policy=native_srm_policy(pack).policy)
        try:
            register=SRMPOSSession(organization_id=1,session_number='SPECIALIST-'+uuid4().hex,status='open',cashier_user_id=actor.id,created_by=actor.id)
            db.add(register);db.commit();ident=register.id
        finally:cleanup()
    data=s.payload();data['pos_session_id']=ident
    response=client.post('/api/v1/srm/service-checkout',headers={**headers,'X-Suite-Pack-Context':str(context.id)},json=data)
    assert response.status_code==403,response.text
    assert 'role' in str(response.json().get('detail','')).lower()
    assert quantity(db,s.product,s.warehouse)==4



def test_legacy_stock_receipt_updates_one_canonical_company_quantity_cache(client,db,stock):
    from app.models.company import Branch
    from app.shared.catalog_branches import set_availability
    s=stock
    branch=Branch(company_id=1,name='Legacy cache proof',code='CACHE');db.add(branch);db.commit()
    headers,actor=native_actor(db,branch.id,admin=True)
    with native_writer(db,actor,branch.id):
        product=db.get(SRMProduct,s.product);set_availability(product,branch.id,True);db.commit()
    response=client.post('/api/v1/srm/inventory/warehouses',headers=headers,json={'warehouse_code':'CACHE','warehouse_name':'Legacy cache warehouse'})
    assert response.status_code==201,response.text
    unchanged=('sales_rate','gst_rate','metadata_json','updated_at','cost_price')
    table=SRMProduct.__table__
    unchanged=tuple(name for name in unchanged if name in table.c)
    before=db.connection().execute(select(*(table.c[name] for name in unchanged)).where(table.c.id==s.product)).one()
    response=client.post('/api/v1/srm/inventory/opening-stock',headers=headers,json={'product_id':s.product,'warehouse_id':response.json()['id'],'quantity':5,'rate':40})
    assert response.status_code==201,response.text
    actual=db.connection().scalar(select(func.sum(SRMInventoryBalance.quantity)).where(SRMInventoryBalance.product_id==s.product,SRMInventoryBalance.organization_id==1))
    cached=db.connection().scalar(select(SRMProduct.current_quantity).where(SRMProduct.id==s.product))
    assert cached==actual==Decimal('9.000'),{'canonical_company_quantity':str(actual),'cached_product_quantity':str(cached)}
    assert db.connection().execute(select(*(table.c[name] for name in unchanged)).where(table.c.id==s.product)).one()==before


def test_legacy_quantity_cache_cannot_borrow_independent_native_core_purpose(db,stock):
    from app.apps.srm.stock_resource import refresh_legacy_quantity
    from app.business_packs.common_binding import CoreRequestBinding
    s=stock
    product=db.get(SRMProduct,s.product)
    movement=db.query(SRMInventoryMovement).filter_by(product_id=s.product,movement_type='pos_sale').one()
    with native_writer(db,s.actor,s.branch):
        db.info['business_pack_request_binding']=CoreRequestBinding(s.actor.id,1,'POST','/api/v1/hrms/employees')
        try:
            with pytest.raises(HTTPException) as rejected:refresh_legacy_quantity(db,product,s.actor,movement)
            assert rejected.value.status_code==403
        finally:db.info.pop('business_pack_request_binding',None)
    assert quantity(db,s.product,s.warehouse)==4
