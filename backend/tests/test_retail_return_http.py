"""Actual production request binding and native source/accounting return flow."""
from decimal import Decimal
from uuid import uuid4
import pytest
from starlette.requests import Request
from app.models.user import Permission
from app.access.models import AccessPolicy
from app.business_packs.models import PackMasterAvailability
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.apps.srm.models import SRMPOSSession,SRMProduct,SRMInventoryBalance,SRMPOSReturn,SRMInventoryMovement,SRMPOSCashMovement
from app.apps.fam.models import FAMVoucher,FAMLedgerEntry,FAMLedger
from app.business_packs.retail.models import RetailReturn,RetailReturnLine,RetailSaleStockSource
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer

BASE='/api/v1/srm/retail/returns'


@pytest.fixture
def retail_setup(client,db,scenario):
    _,branch,catalog,_=scenario
    headers,actor=native_actor(db,branch)
    permission=db.query(Permission).filter_by(name='fam_admin').one_or_none()
    if permission is None:permission=Permission(name='fam_admin',description='Native Accounting administrator');db.add(permission);db.flush()
    actor.role.permissions.append(permission)
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=actor.id).one()
    policy.grants={**policy.grants,'fam':{'enabled':True,'permissions':['fam_admin'],'actions':['view','create','edit','approve'],'scope':'organization'}}
    db.commit()
    context,_=grant(db,actor,branch,'retail','store_manager')
    product=db.get(SRMProduct,catalog[2][0]);warehouse=product.default_warehouse_id
    for table,ident in [('crm_companies',101),('srm_products',product.id),('srm_warehouses',warehouse)]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context.id)
        cleanup=install(db,scope,policy=native_srm_policy('retail').policy)
        try:
            register=SRMPOSSession(organization_id=1,session_number='RETAIL-'+uuid4().hex,status='open',cashier_user_id=actor.id,created_by=actor.id)
            db.add(register);db.commit();register_id=register.id
        finally:cleanup()
    headers={**headers,'X-Suite-Pack-Context':str(context.id)}
    return headers,actor,branch,context.id,register_id,product.id,warehouse


@pytest.fixture
def retail_http(client,retail_setup):
    headers,actor,branch,context_id,register_id,product_id,warehouse=retail_setup
    sale=client.post('/api/v1/srm/service-checkout',headers=headers,json={
        'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register_id,
        'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':product_id,'quantity':2}],
        'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'236'}]})
    assert sale.status_code==201,sale.text
    return headers,actor,branch,context_id,sale.json(),register_id,product_id,warehouse


def post_original(db,case):
    _,actor,branch,_,sale,_,_,_=case
    from app.apps.fam.api.router import bootstrap,post_srm_invoice_to_fam,post_srm_receipt_to_fam
    request=Request({'type':'http','method':'POST','path':'/native-accounting-fixture','headers':[],'client':('127.0.0.1',12345)})
    # Legitimate native Accounting source setup, separate from the actual HTTP
    # return command. No fake journal, skipped native validation or actor override.
    with native_writer(db,actor,branch):
        from app.access.service import background_scope
        with background_scope(db,actor,'fam','approve',branch_id=branch):
            bootstrap(db,actor)
            post_srm_invoice_to_fam(db,request,actor,1,sale['invoice']['id'])
            for receipt in sale['receipts']:post_srm_receipt_to_fam(db,request,actor,1,receipt['id'])


def command(case):
    sale=case[4]
    return {'checkout_id':sale['id'],'expected_checkout_revision':sale['revision'],
        'request_key':str(uuid4()),'lines':[{'checkout_line_id':sale['lines'][0]['id'],'quantity':1,'restock':True}],
        'refund':{'method':'cash','session_id':case[5]},'reason':'Unopened item returned'}


def test_actual_http_paid_sale_partial_return_stock_restore_native_refund_once(client,db,retail_http):
    headers,_,_,_,sale,_,product,warehouse=retail_http
    assert db.query(RetailSaleStockSource).count()==1
    post_original(db,retail_http)
    before=db.query(FAMVoucher).count()
    response=client.post(BASE,headers=headers,json=command(retail_http))
    assert response.status_code==201,response.text
    result=response.json()
    assert Decimal(result['refund_amount'])==118
    assert result['state']=='committed' and result['accounting']['credit_note']['status']=='posted'
    assert result['accounting']['refund']['status']=='posted'
    assert db.query(FAMVoucher).count()==before+2
    assert db.query(SRMInventoryBalance).filter_by(product_id=product,warehouse_id=warehouse).one().quantity==4
    assert db.get(SRMProduct,product).current_quantity==4
    assert db.query(RetailReturn).count()==db.query(RetailReturnLine).count()==db.query(SRMPOSReturn).count()==1
    source=db.get(RetailReturn,result['id'])
    replay=client.post(BASE,headers=headers,json={**command(retail_http),'request_key':source.request_key})
    assert replay.status_code==201,replay.text
    assert replay.json()==result
    assert db.query(FAMVoucher).count()==before+2
    assert db.query(SRMInventoryMovement).filter_by(movement_type='pos_return').count()==1
    assert db.query(SRMPOSCashMovement).filter_by(movement_type='cash_out').count()==1
    drawer=client.get('/api/v1/srm/pos/sessions/active',headers=headers)
    assert drawer.status_code==200,drawer.text
    assert Decimal(str(drawer.json()['expected_cash']))==118
    read=client.get(BASE+'/'+str(result['id']),headers=headers)
    assert read.status_code==200,read.text
    assert read.json()==result
    recovered=client.get(BASE+'/requests/'+source.request_key,headers=headers)
    assert recovered.status_code==200,recovered.text
    assert recovered.json()=={'state':'committed','result':result}
    excessive=command(retail_http);excessive['lines'][0]['quantity']=2
    denied=client.post(BASE,headers=headers,json=excessive)
    assert denied.status_code==409,denied.text
    assert db.query(FAMVoucher).count()==before+2


def test_unposted_sale_explicitly_rejects_without_stock_or_return_effects(client,db,retail_http):
    before=db.query(SRMInventoryMovement).count()
    response=client.post(BASE,headers=retail_http[0],json=command(retail_http))
    assert response.status_code==409,response.text
    assert 'Accounting' in response.text
    assert db.query(RetailReturn).count()==db.query(SRMPOSReturn).count()==0
    assert db.query(SRMInventoryMovement).count()==before


@pytest.mark.parametrize('failure',['late_payment','swapped_ledger','forged_running_balance','mutated_plan'])
def test_financial_failure_rolls_back_stock_return_and_all_native_journals(client,db,retail_http,monkeypatch,failure):
    from fastapi import HTTPException
    from app.apps.fam.api import router as native
    from app.business_packs.retail import accounting,posting_plan
    post_original(db,retail_http)
    before={model:db.query(model).count() for model in (FAMVoucher,FAMLedgerEntry,SRMInventoryMovement,SRMPOSCashMovement)}
    if failure in ('late_payment','swapped_ledger'):
        original=native.create_and_post_voucher
        def broken(*args,**kwargs):
            if args[4]=='PV' and failure=='late_payment':raise HTTPException(409,'Synthetic native payment failure')
            values=list(args)
            if args[4]=='CN' and failure=='swapped_ledger':
                values[10]=[dict(line) for line in args[10]]
                values[10][0]['ledger_id']=values[10][-1]['ledger_id']
            return original(*values,**kwargs)
        monkeypatch.setattr(native,'create_and_post_voucher',broken)
    elif failure=='forged_running_balance':
        original=native.apply_ledger_movement
        monkeypatch.setattr(native,'apply_ledger_movement',lambda *args:original(*args)+1)
    else:
        original=posting_plan.build
        def changed(*args):
            plan=original(*args)
            plan.snapshots[0][1]['id']+=1000000
            return plan
        monkeypatch.setattr(posting_plan,'build',changed)
    response=client.post(BASE,headers=retail_http[0],json=command(retail_http))
    assert response.status_code in (403,409),response.text
    assert db.query(RetailReturn).count()==db.query(SRMPOSReturn).count()==0
    assert all(db.query(model).count()==count for model,count in before.items())
    assert db.get(SRMProduct,retail_http[6]).current_quantity==3
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_http[6],warehouse_id=retail_http[7]).one().quantity==3
    assert db not in accounting._ACTIVE


def test_native_accounting_ceiling_is_independent_of_retail_pack_role(client,db,retail_http):
    post_original(db,retail_http)
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=retail_http[1].id).one()
    policy.grants={**policy.grants,'fam':{**policy.grants['fam'],'enabled':False}}
    db.commit()
    response=client.post(BASE,headers=retail_http[0],json=command(retail_http))
    assert response.status_code==403,response.text
    assert db.query(RetailReturn).count()==0


def test_other_pack_financial_role_cannot_return_original_retail_source(client,db,retail_http):
    headers,actor,branch,_,sale,_,_,_=retail_http
    context,_=grant(db,actor,branch,'hospital','hospital_manager')
    response=client.post(BASE,headers={**headers,'X-Suite-Pack-Context':str(context.id)},json=command(retail_http))
    assert response.status_code in (403,404),response.text
    assert sale['invoice']['number'] not in response.text
    assert db.query(RetailReturn).count()==0


@pytest.mark.parametrize('kind',['closed','foreign_cashier','unfunded'])
def test_cash_refund_requires_its_actual_open_owned_funded_register(client,db,retail_http,kind):
    headers,actor,branch,context,sale,register,_,_=retail_http
    post_original(db,retail_http)
    payload=command(retail_http)
    if kind=='closed':
        db.get(SRMPOSSession,register).status='closed';db.commit()
    else:
        selected_actor=actor
        if kind=='foreign_cashier':
            _,selected_actor=native_actor(db,branch)
            from app.business_packs.models import PackContext
            grant(db,selected_actor,branch,'retail','store_manager',db.get(PackContext,context))
        with native_writer(db,selected_actor,branch):
            scope=resolve_context(db,selected_actor,db.info['branch_context'],context)
            cleanup=install(db,scope,policy=native_srm_policy('retail').policy)
            try:
                other=SRMPOSSession(organization_id=1,session_number='OTHER-'+uuid4().hex,status='open',
                    cashier_user_id=selected_actor.id,created_by=selected_actor.id,opening_cash=0)
                db.add(other);db.commit();payload['refund']['session_id']=other.id
            finally:cleanup()
    before=db.query(FAMVoucher).count()
    response=client.post(BASE,headers=headers,json=payload)
    assert response.status_code in (403,409),response.text
    assert db.query(FAMVoucher).count()==before
    assert db.query(RetailReturn).count()==db.query(SRMPOSCashMovement).count()==0


def test_card_refund_records_original_posted_funding_without_cash_drawer_movement(client,db,retail_setup):
    headers,actor,branch,context,register,product,warehouse=retail_setup
    sold=client.post('/api/v1/srm/service-checkout',headers=headers,json={
        'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register,
        'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':product,'quantity':2}],
        'payments':[{'payment_key':str(uuid4()),'method':'card','amount':'236','reference':'Original terminal receipt'}]})
    assert sold.status_code==201,sold.text
    case=(headers,actor,branch,context,sold.json(),register,product,warehouse)
    post_original(db,case)
    payload=command(case);payload['refund']={'method':'card','session_id':register,'reference':'Completed terminal refund reference'}
    response=client.post(BASE,headers=headers,json=payload)
    assert response.status_code==201,response.text
    assert response.json()['refund_method']=='card'
    assert db.query(SRMPOSCashMovement).count()==0
    assert db.query(SRMInventoryBalance).filter_by(product_id=product,warehouse_id=warehouse).one().quantity==4


def test_refund_restores_original_warehouse_after_catalog_default_changes(client,db,retail_http):
    headers,actor,branch,_,_,_,product_id,warehouse=retail_http
    post_original(db,retail_http)
    from app.apps.srm.models import SRMWarehouse
    with native_writer(db,actor,branch):
        other=SRMWarehouse(organization_id=1,warehouse_code='OTHER-'+uuid4().hex,warehouse_name='New default warehouse',active=True,created_by=actor.id)
        db.add(other);db.flush()
        product=db.get(SRMProduct,product_id);product.default_warehouse_id=other.id
        db.commit()
    response=client.post(BASE,headers=headers,json=command(retail_http))
    assert response.status_code==201,response.text
    restored=db.query(SRMInventoryMovement).filter_by(movement_type='pos_return').one()
    assert restored.warehouse_id==warehouse


def test_changed_original_posted_amounts_require_reconciliation_before_refund(client,db,retail_http):
    post_original(db,retail_http)
    table=FAMVoucher.__table__
    # Trusted fixture corruption exercises persisted source validation, not a
    # public override or permission to edit issued accounting records.
    db.connection().execute(table.update().where(table.c.source_record_type=='invoice',
        table.c.source_record_id==str(retail_http[4]['invoice']['id'])).values(total_debit=1,total_credit=1))
    before=db.query(FAMVoucher).count()
    response=client.post(BASE,headers=retail_http[0],json=command(retail_http))
    assert response.status_code==409,response.text
    assert 'reconciliation' in response.text
    assert db.query(FAMVoucher).count()==before
    assert db.query(RetailReturn).count()==db.query(SRMPOSCashMovement).count()==0
    assert db.get(SRMProduct,retail_http[6]).current_quantity==3
