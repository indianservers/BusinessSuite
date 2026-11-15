"""Independent native PostgreSQL transactions; no shared-session thread simulation."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date,timedelta
from threading import Barrier,Event
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.company import Branch
from app.models.user import User
from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBatch,SRMInventoryBalance,SRMInventoryMovement
from app.business_packs.models import PackMasterAvailability,PackUserGrant
from app.business_packs.pharma.recall_models import PharmaRecall,PharmaRecallEvent,PharmaBatchControl
from app.business_packs.pharma.schemas import ReceiptInput
from app.business_packs.pharma.recall_schemas import RecallInput
from app.business_packs.pharma.receipts import create as receive
from app.business_packs.pharma.recalls import create
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_srm_native_transaction_operations import native_writer
# This existing guarded fixture owns a NEW migrated local database for every
# case, cleans exactly that database, and asserts shared source counts unchanged.
from tests.test_payroll_qa_concurrency import payroll_engine


@contextmanager
def writer(engine,case):
    with Session(engine) as db:
        actor=db.get(User,case['actor'])
        from app.access.models import AccessMembership
        membership=db.query(AccessMembership).filter_by(user_id=actor.id,company_id=1,active=True).one()
        # organization_id is the native request-bound identity, not a User
        # database column. Bind it from this freshly verified actual membership.
        actor.organization_id=membership.company_id
        with native_writer(db,actor,case['branch']):
            scope=resolve_context(db,actor,db.info['branch_context'],case['context']);cleanup=install(db,scope,policy=native_srm_policy(case.get('pack','pharma')).policy)
            try:yield db,actor
            finally:cleanup()


def seed(engine):
    with Session(engine) as db:
        branch=Branch(company_id=1,organization_id=1,name='Recall race branch',code='RACE-'+uuid4().hex[:10],is_active=True)
        db.add(branch);db.commit()
        # The native branch guard intentionally excludes unresolved historical
        # branches. This is the branch just created here, with actual company FK.
        from app.branches.models import BranchOwnership
        db.add(BranchOwnership(company_id=1,branch_id=branch.id,resource_table='branches',resource_key=str(branch.id),source='independent-fixture-created'))
        db.commit()
        _,actor=native_actor(db,branch.id)
        with native_writer(db,actor,branch.id):
            warehouse=SRMWarehouse(organization_id=1,warehouse_code='RACE-'+uuid4().hex,warehouse_name='Recall race warehouse',active=True,created_by=actor.id)
            db.add(warehouse);db.flush()
            product=SRMProduct(organization_id=1,sku='RACE-'+uuid4().hex,item_name='Recall race medicine',product_type='stock',track_inventory=True,
                batch_tracking=True,expiry_tracking=True,serial_tracking=False,default_warehouse_id=warehouse.id,active=True,created_by=actor.id,sales_rate=100,gst_rate=18)
            db.add(product);db.commit();product_id,warehouse_id=product.id,warehouse.id
        context,_=grant(db,actor,branch.id,'pharma','pharmacy_manager')
        for table,ident in [('srm_products',product_id),('srm_warehouses',warehouse_id)]:
            db.add(PackMasterAvailability(company_id=1,branch_id=branch.id,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
        db.commit();case={'actor':actor.id,'branch':branch.id,'context':context.id,'product':product_id,'warehouse':warehouse_id}
    with writer(engine,case) as (db,actor):
        result=receive(ReceiptInput(request_key=uuid4(),product_id=product_id,warehouse_id=warehouse_id,batch_number='RACE-'+uuid4().hex,
            received_date=date.today(),expiry_date=date.today()+timedelta(days=365),quantity=10,unit_cost=1),db,actor)
        case['batch']=result['batch_id']
    return case


def payload(case,key=None):
    return RecallInput(request_key=key or uuid4(),batch_id=case['batch'],expected_batch_revision=0,expected_batch_status='available',action='quarantine',reason='Concurrent quality review')


def snapshot(engine,case):
    with Session(engine) as db:
        count=lambda model:db.connection().scalar(select(func.count()).select_from(model.__table__))
        return {'roots':count(PharmaRecall),'events':count(PharmaRecallEvent),'controls':count(PharmaBatchControl),'movements':count(SRMInventoryMovement),
            'status':db.connection().scalar(select(SRMInventoryBatch.status).where(SRMInventoryBatch.id==case['batch'])),
            'available':db.connection().scalar(select(SRMInventoryBatch.available_quantity).where(SRMInventoryBatch.id==case['batch'])),
            'balance':db.connection().scalar(select(SRMInventoryBalance.quantity).where(SRMInventoryBalance.product_id==case['product'],SRMInventoryBalance.warehouse_id==case['warehouse']))}


@pytest.mark.parametrize('same_key',[False,True])
def test_postgresql_same_batch_version_and_uuid_races_are_atomic(payroll_engine,same_key):
    engine=payroll_engine;case=seed(engine);start=Barrier(2);key=uuid4() if same_key else None
    before=snapshot(engine,case)
    def run(_):
        with writer(engine,case) as (db,actor):
            data=payload(case,key);start.wait(timeout=20)
            try:return 201,create(data,db,actor)
            except HTTPException as error:db.rollback();return error.status_code,error.detail
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sorted(code for code,_ in results)==([201,201] if same_key else [201,409]),results
    if same_key:assert results[0][1]==results[1][1]
    after=snapshot(engine,case)
    assert after['roots']==after['events']==after['controls']==1 and after['status']=='quarantined'
    assert (after['available'],after['balance'],after['movements'])==(before['available'],before['balance'],before['movements'])


@pytest.mark.parametrize('revocation',['pack','native_edit'])
def test_postgresql_authority_revoked_while_waiting_cannot_quarantine(payroll_engine,monkeypatch,revocation):
    engine=payroll_engine;case=seed(engine);before=snapshot(engine,case);waiting=Event()
    from app.apps.srm.services import commercial
    from app.core.company_writer import lock_company_writer
    original=commercial.lock_tenant
    def observed(db,actor):
        waiting.set();return original(db,actor)
    monkeypatch.setattr(commercial,'lock_tenant',observed)
    from app.apps.srm import industry_api
    monkeypatch.setattr(industry_api,'lock_tenant',observed)
    def run():
        with writer(engine,case) as (db,actor):
            try:return create(payload(case),db,actor)
            except HTTPException as error:db.rollback();return error.status_code
    with Session(engine) as blocker:
        # An authorized control-plane transaction commits revocation before
        # releasing the same company writer lock the operational worker awaits.
        lock_company_writer(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(run)
            assert waiting.wait(timeout=20),'Recall never reached the company writer wait'
            if revocation=='pack':
                t=PackUserGrant.__table__
                blocker.connection().execute(t.update().where(t.c.user_id==case['actor'],t.c.context_id==case['context']).values(role='cashier',revision=t.c.revision+1))
            else:
                from app.access.models import AccessPolicy
                t=AccessPolicy.__table__
                row=blocker.connection().execute(select(t.c.id,t.c.grants).where(t.c.company_id==1,t.c.user_id==case['actor'])).mappings().one()
                values={**row['grants'],'srm':{**row['grants']['srm'],'actions':['view','create','approve']}}
                blocker.connection().execute(t.update().where(t.c.id==row['id']).values(grants=values,version=t.c.version+1))
            blocker.commit()
            assert future.result(timeout=30)==403
    assert snapshot(engine,case)==before
