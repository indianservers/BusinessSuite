"""Real independent PostgreSQL original-lot refund transactions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from threading import Event
from uuid import uuid4
from decimal import Decimal
import pytest
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live,race
from tests.test_service_checkout import catalog,directory_identity
from tests.test_business_suite_pos_concurrency import seed
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_retail_return_http import post_original
from tests.srm_test_utils import seed_invoice_parties
from app.access.models import AccessPolicy
from app.models.user import Permission
from app.branches.models import BranchOwnership
from app.business_packs.models import PackMasterAvailability,PackUserGrant
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.apps.srm.models import SRMProduct,SRMPOSSession,SRMPOSCashMovement
from app.business_packs.pharma.return_models import PharmaReturn,PharmaReturnLot
BASE='/api/v1/srm/pharma/returns'


def prepared(live):
    product=seed(live)
    with live.factory() as db:
        item=db.get(SRMProduct,product);warehouse=item.default_warehouse_id
        branch=db.query(BranchOwnership).filter_by(resource_table='srm_warehouses',resource_key=str(warehouse),company_id=1).one().branch_id
        item.batch_tracking=True;item.expiry_tracking=True
        seed_invoice_parties(db)
        headers,actor=native_actor(db,branch)
        permission=db.query(Permission).filter_by(name='fam_admin').one_or_none()
        if permission is None:permission=Permission(name='fam_admin',description='Native Accounting administrator');db.add(permission);db.flush()
        actor.role.permissions.append(permission)
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=actor.id).one()
        policy.grants={**policy.grants,'fam':{'enabled':True,'permissions':['fam_admin'],'actions':['view','create','edit','approve'],'scope':'organization'}}
        db.commit();context,_=grant(db,actor,branch,'pharma','business_owner')
        for table,ident in [('srm_products',product),('srm_warehouses',warehouse),('crm_companies',101)]:
            db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
        db.commit()
        with native_writer(db,actor,branch):
            scope=resolve_context(db,actor,db.info['branch_context'],context.id);cleanup=install(db,scope,policy=native_srm_policy('pharma').policy)
            try:
                register=SRMPOSSession(organization_id=1,session_number='PHARMA-RETURN-'+uuid4().hex,status='open',cashier_user_id=actor.id,created_by=actor.id)
                db.add(register);db.commit();register_id=register.id
            finally:cleanup()
        headers={**headers,'X-Suite-Pack-Context':str(context.id)};actor_id=actor.id;context_id=context.id
    receipt=live.client.post('/api/v1/srm/pharma/batch-receipts',headers=headers,json={'request_key':str(uuid4()),'product_id':product,'warehouse_id':warehouse,
        'batch_number':'RETURN-RACE-'+uuid4().hex,'received_date':date.today().isoformat(),'expiry_date':(date.today()+timedelta(days=100)).isoformat(),'quantity':'2','unit_cost':'40'})
    assert receipt.status_code==201,receipt.text
    sold=live.client.post('/api/v1/srm/service-checkout',headers=headers,json={'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register_id,
        'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':product,'quantity':'1'}],
        'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]})
    assert sold.status_code==201,sold.text
    checkout=sold.json();discovered=live.client.get(BASE+f'/sales/{checkout["id"]}/lots',headers=headers)
    assert discovered.status_code==200,discovered.text
    from app.models.user import User
    with live.factory() as db:
        actor=db.get(User,actor_id);actor.organization_id=1
        post_original(db,(headers,actor,branch,context_id,checkout,register_id,product,warehouse))
        assigned=db.query(PackUserGrant).filter_by(context_id=context_id,user_id=actor_id).one()
        assigned.role='pharmacy_manager';db.commit()
    body={'request_key':str(uuid4()),'checkout_id':checkout['id'],'expected_checkout_revision':checkout['revision'],
        'lots':[{'allocation_id':discovered.json()['lots'][0]['allocation_id'],'quantity':'1'}],
        'refund':{'method':'cash','session_id':register_id},'reason':'Original sealed medicine returned for quarantine'}
    return headers,body,actor_id,context_id


@pytest.mark.parametrize('same_key',[False,True])
def test_original_lot_last_quantity_and_exact_replay_are_atomic(live,same_key):
    headers,body,_,_=prepared(live)
    from app.apps.fam.models import FAMVoucher
    with live.factory() as db:before_vouchers=db.query(FAMVoucher).count()
    other=body if same_key else {**body,'request_key':str(uuid4())}
    results=race(lambda:live.client.post(BASE,headers=headers,json=body),lambda:live.client.post(BASE,headers=headers,json=other))
    statuses=sorted(row.status_code for row in results)
    allowed=([201,201],[201,503]) if same_key else ([201,409],[201,503])
    assert statuses in allowed,[row.text for row in results]
    winner=next(row.json() for row in results if row.status_code==201)
    # Default native lock budgets may bound contention with503. Recovery must
    # use each original immutable key, after the winning transaction commits.
    recovered=[live.client.post(BASE,headers=headers,json=payload) for payload in (body,other)]
    if same_key:
        assert [row.status_code for row in recovered]==[201,201],[row.text for row in recovered]
        assert all(row.json()==winner for row in recovered)
    else:
        assert sorted(row.status_code for row in recovered)==[201,409],[row.text for row in recovered]
        assert next(row.json() for row in recovered if row.status_code==201)==winner

    with live.factory() as db:
        assert db.query(PharmaReturn).count()==db.query(PharmaReturnLot).count()==1
        assert db.query(SRMPOSCashMovement).filter_by(movement_type='cash_out').count()==1
        assert db.query(PharmaReturn).one().refund_amount==Decimal('118')
        assert db.query(FAMVoucher).count()==before_vouchers+2


@pytest.mark.parametrize('revocation',['pack','fam_approve'])
def test_refund_rechecks_authority_after_company_writer_wait(live,monkeypatch,revocation):
    headers,body,actor,context=prepared(live)
    from app.apps.srm.services import commercial
    from app.core.company_writer import lock_company_writer
    original= commercial.lock_tenant;waiting=Event()
    def observed(db,user):waiting.set();return original(db,user)
    monkeypatch.setattr(commercial,'lock_tenant',observed)
    from app.apps.srm import industry_api
    monkeypatch.setattr(industry_api,'lock_tenant',observed)
    with live.factory() as blocker:
        lock_company_writer(blocker,1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(lambda:live.client.post(BASE,headers=headers,json=body))
            assert waiting.wait(timeout=20),'Refund never reached company writer'
            if revocation=='pack':
                table=PackUserGrant.__table__;blocker.connection().execute(table.update().where(table.c.user_id==actor,table.c.context_id==context).values(active=False,revision=table.c.revision+1))
            else:
                table=AccessPolicy.__table__;row=blocker.connection().execute(select(table.c.id,table.c.grants).where(table.c.company_id==1,table.c.user_id==actor)).mappings().one()
                grants={**row['grants'],'fam':{**row['grants']['fam'],'actions':['view','create','edit']}}
                blocker.connection().execute(table.update().where(table.c.id==row['id']).values(grants=grants,version=table.c.version+1))
            blocker.commit();response=future.result(timeout=45)
            assert response.status_code==403,response.text
    with live.factory() as db:
        assert db.query(PharmaReturn).count()==db.query(PharmaReturnLot).count()==0
        assert db.query(SRMPOSCashMovement).filter_by(movement_type='cash_out').count()==0


def test_authentic_race_preparation_executes_same_complete_http_workflow(client,db,catalog):
    """Exercise the exact PG actor/setup factory before spending a native cohort."""
    from contextlib import contextmanager
    from types import SimpleNamespace
    @contextmanager
    def factory():yield db
    headers,body,_,_=prepared(SimpleNamespace(client=client,oh=catalog[0],factory=factory))
    result=client.post(BASE,headers=headers,json=body)
    assert result.status_code==201,result.text
    assert result.json()['state']=='committed'

