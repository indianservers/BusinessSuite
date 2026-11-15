"""Actual independent PostgreSQL receipt/checkout/payment native revocation waits."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import date,timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.access.models import AccessPolicy
from app.apps.srm.models import SRMProduct,SRMPOSSession,SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement,SRMInventoryBatch
from app.apps.srm.service_checkout import checkout,append_payment
from app.apps.srm.service_checkout_schemas import CheckoutInput,AppendPaymentInput
from app.business_packs.models import PackMasterAvailability,PackUserGrant
from app.business_packs.pharma.schemas import ReceiptInput
from app.business_packs.pharma.receipts import create as receive
from tests.test_pharma_recall_concurrency import writer,seed,snapshot
from tests.test_payroll_qa_concurrency import payroll_engine


def prepare_sale(engine,case,pack):
    from tests.srm_test_utils import seed_invoice_parties
    from tests.test_business_pack_http_integration import grant
    with Session(engine) as db:
        seed_invoice_parties(db)
        if pack=='hospital':
            from app.models.user import User
            actor=db.get(User,case['actor']);actor.organization_id=1
            context,_=grant(db,actor,case['branch'],'hospital','hospital_manager')
            case={**case,'pack':'hospital','context':context.id}
        else:
            role=db.query(PackUserGrant).filter_by(context_id=case['context'],user_id=case['actor']).one();role.role='business_owner';db.commit()
        db.add(PackMasterAvailability(company_id=1,branch_id=case['branch'],context_id=case['context'],resource_table='crm_companies',resource_key='101',active=True));db.commit()
    with writer(engine,case) as (db,actor):
        if pack=='hospital':
            product=SRMProduct(organization_id=1,sku='WAIT-SERVICE-'+uuid4().hex,item_name='Wait authority consultation',product_type='service',track_inventory=False,
                sales_rate=100,gst_rate=18,active=True,created_by=actor.id)
            db.add(product);db.flush();case={**case,'product':product.id}
        register=SRMPOSSession(organization_id=1,session_number='WAIT-'+uuid4().hex,status='open',created_by=actor.id,cashier_user_id=actor.id)
        db.add(register);db.commit();case={**case,'register':register.id}
    data=CheckoutInput(request_id=uuid4(),customer_id=101,pos_session_id=case['register'],lines=[{
        'client_line_key':str(uuid4()),'line_kind':'unscheduled_service' if pack=='hospital' else 'product','product_id':case['product'],'quantity':'1'}],payments=[])
    with writer(engine,case) as (db,actor):
        # Prove this exact native setup can really issue a sale before testing
        # revocation; an unrelated missing source cannot masquerade as denial.
        issued=checkout(data,db,actor)
        assert issued['invoice']['total']=='118.00' and issued['invoice']['balance']=='118.00'
    return case,issued


def counts(engine):
    from app.apps.srm.service_checkout_models import POSServiceCheckout,POSCheckoutPayment
    from app.business_packs.pharma.models import PharmaBatchReceipt,PharmaBatchAllocation
    with Session(engine) as db:
        return tuple(db.connection().scalar(select(func.count()).select_from(model.__table__)) for model in
            (SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement,SRMInventoryBatch,POSServiceCheckout,POSCheckoutPayment,PharmaBatchReceipt,PharmaBatchAllocation))


@pytest.mark.parametrize('operation',['receipt','pharma_checkout','hospital_checkout','append_payment'])
def test_native_permissions_revoked_during_actual_company_wait_do_not_commit(payroll_engine,monkeypatch,operation):
    engine=payroll_engine;case=seed(engine);issued=None
    if operation!='receipt':case,issued=prepare_sale(engine,case,'hospital' if operation=='hospital_checkout' else 'pharma')
    before_counts=counts(engine)
    # Hospital service product has no stock row. Preserve the original managed
    # medicine source for this physical inventory snapshot in every case.
    with Session(engine) as db:
        batch= db.connection().execute(select(SRMInventoryBatch.product_id,SRMInventoryBatch.warehouse_id).where(SRMInventoryBatch.id==case['batch'])).first()
    physical={**case,'product':batch.product_id,'warehouse':batch.warehouse_id};before_stock=snapshot(engine,physical)
    waiting=Event()
    from app.apps.srm.services import commercial
    from app.apps.srm import industry_api,service_checkout
    from app.core.company_writer import lock_company_writer
    original=commercial.lock_tenant
    def observed(db,actor):waiting.set();return original(db,actor)
    monkeypatch.setattr(commercial,'lock_tenant',observed)
    monkeypatch.setattr(industry_api,'lock_tenant',observed)
    monkeypatch.setattr(service_checkout,'lock_tenant',observed)
    def run():
        with writer(engine,case) as (db,actor):
            try:
                if operation=='receipt':
                    return receive(ReceiptInput(request_key=uuid4(),product_id=case['product'],warehouse_id=case['warehouse'],batch_number='WAIT-'+uuid4().hex,
                        received_date=date.today(),expiry_date=date.today()+timedelta(days=365),quantity=1,unit_cost=1),db,actor)
                if operation=='append_payment':
                    return append_payment(issued['id'],AppendPaymentInput(expected_revision=issued['revision'],pos_session_id=case['register'],
                        payment={'payment_key':str(uuid4()),'method':'card','amount':'10','reference':'Native wait regression'}),db,actor)
                return checkout(CheckoutInput(request_id=uuid4(),customer_id=101,pos_session_id=case['register'],lines=[{
                    'client_line_key':str(uuid4()),'line_kind':'unscheduled_service' if operation=='hospital_checkout' else 'product','product_id':case['product'],'quantity':'1'}],payments=[]),db,actor)
            except HTTPException as error:db.rollback();return error.status_code
    with Session(engine) as blocker:
        lock_company_writer(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(run)
            assert waiting.wait(timeout=20),'Native operation did not reach the actual company lock'
            t=AccessPolicy.__table__
            row=blocker.connection().execute(select(t.c.id,t.c.grants).where(t.c.company_id==1,t.c.user_id==case['actor'])).mappings().one()
            removed='approve' if operation in {'pharma_checkout','hospital_checkout'} else 'create'
            grants={**row['grants'],'srm':{**row['grants']['srm'],'actions':[action for action in row['grants']['srm']['actions'] if action!=removed]}}
            blocker.connection().execute(t.update().where(t.c.id==row['id']).values(grants=grants,version=t.c.version+1));blocker.commit()
            assert future.result(timeout=30)==403
    assert counts(engine)==before_counts and snapshot(engine,physical)==before_stock
