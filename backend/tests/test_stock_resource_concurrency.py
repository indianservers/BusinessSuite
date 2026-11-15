"""Selected-pack canonical stock competes in real independent PostgreSQL transactions."""
from uuid import uuid4
from sqlalchemy import select,func,event
from tests.test_pms_workflow_postgresql import live,race
from tests.test_business_suite_pos_concurrency import seed
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_srm_native_transaction_operations import native_writer
from tests.srm_test_utils import seed_invoice_parties
from app.apps.srm.models import SRMProduct,SRMPOSSession,SRMInventoryMovement,SRMInventoryBalance
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.models import PackMasterAvailability
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.branches.models import BranchOwnership


def configured(live):
    # This fully audited native graph is larger than the PMS fixture's five-
    # second wait budget. Only this disposable test engine gets a longer wait;
    # production timeouts and retry behavior remain unchanged.
    @event.listens_for(live.engine,"checkout")
    def stock_budget(connection,record,proxy):
        cursor=connection.cursor()
        try:
            cursor.execute("SET lock_timeout='20000ms'")
            cursor.execute("SET statement_timeout='30000ms'")
        finally:cursor.close()
    errors=[]
    @event.listens_for(live.engine,"handle_error")
    def capture(context):
        original=context.original_exception
        errors.append((getattr(original,"pgcode",None),getattr(getattr(original,"diag",None),"message_primary",None),context.statement))
    live.stock_errors=errors
    product=seed(live)
    with live.factory() as db:
        warehouse=db.get(SRMProduct,product).default_warehouse_id
        branch=db.query(BranchOwnership).filter_by(company_id=1,resource_table='srm_warehouses',resource_key=str(warehouse)).one().branch_id
        seed_invoice_parties(db)
        headers,actor=native_actor(db,branch)
        context,_=grant(db,actor,branch,'retail','store_manager')
        for table,ident in [('srm_products',product),('srm_warehouses',warehouse),('crm_companies',101)]:
            db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
        db.commit()
        with native_writer(db,actor,branch):
            scope=resolve_context(db,actor,db.info['branch_context'],context.id)
            cleanup=install(db,scope,policy=native_srm_policy('retail').policy)
            try:
                register=SRMPOSSession(organization_id=1,session_number='RACE-'+uuid4().hex,status='open',cashier_user_id=actor.id,created_by=actor.id)
                db.add(register);db.commit();register_id=register.id
            finally:cleanup()
        headers={**headers,'X-Suite-Pack-Context':str(context.id)}
    def payload():
        return {'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register_id,
            'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':product,'quantity':'1'}],
            'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]}
    return product,warehouse,headers,payload


def test_selected_pack_last_unit_is_not_sold_twice(live):
    product,warehouse,headers,payload=configured(live)
    call=lambda:live.client.post('/api/v1/srm/service-checkout',headers=headers,json=payload())
    results=race(call,call)
    assert sorted(row.status_code for row in results)==[201,409],([row.text for row in results],live.stock_errors)
    with live.factory() as db:
        assert db.get(SRMProduct,product).current_quantity==0
        assert db.query(SRMInventoryBalance).filter_by(product_id=product,warehouse_id=warehouse).one().quantity==0
        assert db.query(POSServiceCheckout).count()==1
        assert db.query(SRMInventoryMovement).filter_by(product_id=product,movement_type='pos_sale').count()==1


def test_selected_pack_concurrent_exact_replay_issues_stock_once(live):
    product,warehouse,headers,payload=configured(live);data=payload()
    call=lambda:live.client.post('/api/v1/srm/service-checkout',headers=headers,json=data)
    results=race(call,call)
    assert [row.status_code for row in results]==[201,201],([row.text for row in results],live.stock_errors)
    assert results[0].json()==results[1].json()
    with live.factory() as db:
        assert db.get(SRMProduct,product).current_quantity==0
        assert db.query(POSServiceCheckout).count()==1
        assert db.query(SRMInventoryMovement).filter_by(product_id=product,movement_type='pos_sale').count()==1
